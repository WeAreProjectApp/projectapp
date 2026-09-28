"""Shared panel/MCP video validation, transactional replacement and descriptors."""
import hashlib
import json
import logging
import math
from pathlib import Path
import subprocess
import tempfile

from django.conf import settings
from django.core.files import File
from django.core.files.storage import storages
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from content.models import ExplainerVideoSettings, VideoResource

logger = logging.getLogger(__name__)
VIDEO_MAX_BYTES = 250 * 1024 * 1024
VIDEO_MODULES = ('financing', 'additional-modules', 'proposal')


class VideoConflict(APIException):
    status_code = 409
    default_detail = 'El video cambió. Actualiza el recurso antes de volver a guardar.'


def resource_key(module, language, proposal=None):
    if module not in VIDEO_MODULES or language not in ('es', 'en'):
        raise ValidationError({'resource': 'Módulo o idioma inválido.'})
    if proposal is not None:
        if module != 'proposal':
            raise ValidationError({'resource': 'El video personalizado pertenece a una propuesta.'})
        return f'proposal-{proposal.pk}'
    return f'{module}:{language}'


def get_resource(module, language, proposal=None):
    return VideoResource.objects.filter(key=resource_key(module, language, proposal)).first()


def video_descriptor(resource):
    if resource is None or resource.mode != 'uploaded' or not resource.file:
        return None
    base = f'/api/video-resources/{resource.id}/{resource.revision}'
    return {
        'source': 'uploaded',
        'src': f'{base}/video/', 'poster': f'{base}/poster/',
        'durationSeconds': resource.duration_seconds,
        'width': resource.width, 'height': resource.height,
        'language': resource.language,
    }


def public_resource(module, language, proposal=None):
    resource = get_resource(module, language, proposal)
    return {
        'mode': resource.mode if resource else ('none' if proposal else 'default'),
        'video': video_descriptor(resource),
    }


def resource_payload(module, language, proposal=None):
    resource = get_resource(module, language, proposal)
    from content.services.explainer_video_service import explainer_video_visible
    return {
        'visible': explainer_video_visible(module) if proposal is None else bool(video_descriptor(resource)),
        'key': resource_key(module, language, proposal),
        'module': module, 'language': language,
        'mode': resource.mode if resource else ('none' if proposal else 'default'),
        'revision': resource.revision if resource else 0,
        'video': video_descriptor(resource),
        'filename': resource.filename if resource else '',
        'size': resource.size if resource else 0,
        'sha256': resource.sha256 if resource else '',
        'updated_at': resource.updated_at if resource else None,
        'max_bytes': VIDEO_MAX_BYTES,
    }


def probe_video(path):
    """Only local uploaded bytes; external protocols and playlists are disabled."""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-protocol_whitelist', 'file',
            '-f', 'mov', '-show_entries', 'stream=codec_type,codec_name,pix_fmt,width,height:format=duration', '-of', 'json', str(path),
        ], capture_output=True, timeout=30, check=True)
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        videos = [stream for stream in streams if stream.get('codec_type') == 'video']
        audio = [stream for stream in streams if stream.get('codec_type') == 'audio']
        duration = float(data.get('format', {}).get('duration', 0))
        if (len(videos) != 1 or videos[0].get('codec_name') != 'h264'
                or videos[0].get('pix_fmt') not in ('yuv420p', 'yuvj420p')
                or any(stream.get('codec_name') != 'aac' for stream in audio)
                or not math.isfinite(duration) or duration <= 0):
            raise ValueError('Unsupported video')
        width, height = int(videos[0]['width']), int(videos[0]['height'])
        if width < 1 or height < 1 or max(width, height) > 4096:
            raise ValueError('Unsupported dimensions')
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        raise ValidationError({'file': 'Usa un MP4 válido con video H.264 de hasta 4K y audio AAC opcional.'}) from exc
    return {'duration_seconds': duration, 'width': width, 'height': height}


def _delete_files(names):
    for name in names:
        if name:
            try:
                storages['private'].delete(name)
            except OSError:
                logger.exception('Could not remove obsolete commercial video')


def _save_resource(module, language, proposal, actor, revision, mode, source=None, poster=None, metadata=None):
    new_names = []
    try:
        with transaction.atomic():
            # Serialize initial slot creation as well as updates (including absent slots).
            singleton = ExplainerVideoSettings.load()
            ExplainerVideoSettings.objects.select_for_update().get(pk=singleton.pk)
            resource = get_resource(module, language, proposal)
            if revision != (resource.revision if resource else 0):
                raise VideoConflict()
            if resource is None:
                resource = VideoResource(key=resource_key(module, language, proposal), module=module, proposal=proposal)
            old_names = [resource.file.name, resource.poster.name]
            resource.language = language
            resource.mode = mode
            resource.file = ''
            resource.poster = ''
            resource.filename = ''
            resource.size = resource.duration_seconds = resource.width = resource.height = 0
            resource.sha256 = ''
            if source is not None:
                resource.file.save('video.mp4', File(source), save=False)
                new_names.append(resource.file.name)
                resource.poster.save('poster.webp', File(poster), save=False)
                new_names.append(resource.poster.name)
                for field, value in metadata.items():
                    setattr(resource, field, value)
            resource.revision += 1
            resource.updated_by = actor
            resource.save()
            if proposal:
                from content.services.proposal_audit import log_proposal_change
                log_proposal_change(proposal, 'updated', description='Video personalizado actualizado', field_name='video_resource', old_value=str(revision), new_value=str(resource.revision))
            transaction.on_commit(lambda: _delete_files(old_names))
            if proposal is None:
                from content.services.frontend_build import schedule_rebuild_after_publish
                transaction.on_commit(lambda: schedule_rebuild_after_publish(reason='video-resource'))
    except Exception:
        _delete_files(new_names)
        raise
    return resource_payload(module, language, proposal)


def update_resource(module, language, *, proposal=None, actor, revision, action, uploaded_file=None):
    resource_key(module, language, proposal)
    if action not in ('upload', 'remove', 'restore-default'):
        raise ValidationError({'action': 'Usa upload, remove o restore-default.'})
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ValidationError({'revision': 'Indica la revisión leída antes de editar.'})
    if action == 'restore-default' and proposal:
        raise ValidationError({'action': 'Una propuesta no tiene video personalizado predeterminado.'})
    if action != 'upload':
        return _save_resource(module, language, proposal, actor, revision, 'none' if action == 'remove' else 'default')
    if uploaded_file is None:
        raise ValidationError({'file': 'Selecciona un archivo MP4.'})
    filename = Path(uploaded_file.name).name
    if len(filename) > 255 or Path(filename).suffix.lower() != '.mp4':
        raise ValidationError({'file': 'Selecciona un archivo .mp4 con nombre de hasta 255 caracteres.'})
    if getattr(uploaded_file, 'content_type', 'video/mp4') != 'video/mp4':
        raise ValidationError({'file': 'El tipo del archivo debe ser video/mp4.'})
    digest, size = hashlib.sha256(), 0
    with tempfile.TemporaryDirectory(prefix='commercial-video-') as directory:
        path = Path(directory) / 'video.mp4'
        with path.open('wb') as target:
            for chunk in uploaded_file.chunks(1024 * 1024):
                size += len(chunk)
                if size > VIDEO_MAX_BYTES:
                    raise ValidationError({'file': 'El video no puede superar 250 MB.'})
                digest.update(chunk)
                target.write(chunk)
        if not size:
            raise ValidationError({'file': 'El archivo está vacío.'})
        with path.open('rb') as source:
            if source.read(12)[4:8] != b'ftyp':
                raise ValidationError({'file': 'El contenido no es un MP4.'})
        metadata = {**probe_video(path), 'filename': filename, 'size': size, 'sha256': digest.hexdigest()}
        poster_path = Path(directory) / 'poster.webp'
        try:
            subprocess.run([
                'ffmpeg', '-nostdin', '-v', 'error', '-threads', '1',
                '-protocol_whitelist', 'file', '-f', 'mov', '-i', str(path),
                '-frames:v', '1', '-vf', 'scale=1280:-2', '-threads', '1', str(poster_path),
            ], capture_output=True, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValidationError({'file': 'No se pudo obtener la portada del video.'}) from exc
        with path.open('rb') as source, poster_path.open('rb') as poster:
            return _save_resource(module, language, proposal, actor, revision, 'uploaded', source, poster, metadata)
