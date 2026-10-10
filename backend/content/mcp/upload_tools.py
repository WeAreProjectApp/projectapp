import base64
import binascii
import codecs
import hashlib
import re
import zipfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from content.mcp.context import current_mcp_context
from content.models import McpUpload

UPLOAD_TTL_MINUTES = 15
VIDEO_UPLOAD_TTL_MINUTES = 60
VIDEO_CONNECTORS = {'partnership-program', 'additional-modules', 'proposals', 'commercial'}
MAX_CHUNK_BYTES = 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')
ALLOWED_CONTENT_TYPES = {
    'application/zip',
    'video/mp4',
    'application/pdf',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/gif',
    'image/jpeg',
    'image/png',
    'image/webp',
    'text/markdown',
    'text/plain',
}
CONTENT_TYPE_EXTENSIONS = {
    'application/zip': {'.zip'},
    'video/mp4': {'.mp4'},
    'application/pdf': {'.pdf'},
    'application/msword': {'.doc'},
    'application/vnd.ms-excel': {'.xls'},
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {'.xlsx'},
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
        '.docx',
    },
    'image/gif': {'.gif'},
    'image/jpeg': {'.jpeg', '.jpg'},
    'image/png': {'.png'},
    'image/webp': {'.webp'},
    'text/markdown': {'.markdown', '.md'},
    'text/plain': {'.text', '.txt'},
}
SIGNING_SALT = 'content.mcp.upload'
DOWNLOAD_SIGNING_SALT = 'content.mcp.download'


def max_upload_bytes(content_type):
    if content_type == 'video/mp4':
        from content.services.video_resource_service import VIDEO_MAX_BYTES
        return VIDEO_MAX_BYTES
    return getattr(settings, 'MCP_UPLOAD_MAX_BYTES', DEFAULT_MAX_UPLOAD_BYTES)


def _tool_error(message, code='VALIDATION_ERROR', details=None):
    from content.mcp.protocol import ToolError
    return ToolError(message, code=code, details=details)


def _context_or_error():
    context = current_mcp_context()
    if context is None or context.credential is None:
        raise _tool_error('El upload requiere una credencial MCP.', 'FORBIDDEN')
    return context


def _upload_or_error(upload_id, *, lock=False):
    context = _context_or_error()
    queryset = McpUpload.objects
    if lock:
        queryset = queryset.select_for_update()
    try:
        upload = queryset.get(
            pk=upload_id,
            connector=context.connector,
            credential=context.credential,
        )
    except (McpUpload.DoesNotExist, ValueError) as exc:
        raise _tool_error('No existe ese upload para esta credencial.', 'NOT_FOUND') from exc
    if upload.expires_at <= timezone.now():
        raise _tool_error('El upload expiró; inicia uno nuevo.', 'CONFIRMATION_EXPIRED')
    return upload


def _delete_file(upload):
    if upload.file:
        upload.file.delete(save=False)


def _purge_expired_uploads():
    expired = list(McpUpload.objects.filter(
        expires_at__lte=timezone.now(),
        status__in=[McpUpload.STATUS_PENDING, McpUpload.STATUS_COMPLETE],
    )[:100])
    for upload in expired:
        _delete_file(upload)
        upload.status = McpUpload.STATUS_ABORTED
        upload.save(update_fields=['status', 'updated_at'])


def begin_upload(arguments):
    context = _context_or_error()
    _purge_expired_uploads()
    filename = Path(str(arguments.get('filename') or '')).name.strip()
    content_type = str(arguments.get('content_type') or '').lower().strip()
    expected_sha256 = str(arguments.get('sha256') or '').lower().strip()
    try:
        expected_size = int(arguments.get('size'))
    except (TypeError, ValueError) as exc:
        raise _tool_error('size debe ser un entero positivo.') from exc
    max_bytes = max_upload_bytes(content_type)
    if content_type == 'video/mp4' and context.connector.slug not in VIDEO_CONNECTORS:
        raise _tool_error('Este conector no admite videos.', 'FORBIDDEN')
    if content_type == 'application/zip' and context.connector.slug != 'projects':
        raise _tool_error('Solo el Gestor de la plataforma admite archivos ZIP.', 'FORBIDDEN')
    if not filename or filename in {'.', '..'}:
        raise _tool_error('filename es obligatorio y debe ser un nombre seguro.')
    if len(filename) > McpUpload._meta.get_field('filename').max_length:
        raise _tool_error('filename no puede superar 255 caracteres.')
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise _tool_error(
            'Tipo de archivo no permitido.',
            details={'allowed_content_types': sorted(ALLOWED_CONTENT_TYPES)},
        )
    suffix = Path(filename).suffix.lower()
    if suffix not in CONTENT_TYPE_EXTENSIONS[content_type]:
        raise _tool_error(
            'La extensión del archivo no coincide con el tipo MIME declarado.',
            details={
                'content_type': content_type,
                'allowed_extensions': sorted(CONTENT_TYPE_EXTENSIONS[content_type]),
            },
        )
    if expected_size < 1 or expected_size > max_bytes:
        raise _tool_error(f'size debe estar entre 1 y {max_bytes} bytes.')
    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise _tool_error('sha256 debe contener 64 caracteres hexadecimales.')
    upload = McpUpload.objects.create(
        connector=context.connector,
        credential=context.credential,
        filename=filename,
        content_type=content_type,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
        expires_at=timezone.now() + timedelta(minutes=(VIDEO_UPLOAD_TTL_MINUTES if content_type == 'video/mp4' else UPLOAD_TTL_MINUTES)),
    )
    signature = signing.dumps(
        {'upload_id': str(upload.id), 'credential_id': context.credential.id},
        salt=SIGNING_SALT,
        compress=True,
    )
    upload_path = f'/api/mcp-uploads/{upload.id}/{signature}/'
    upload_url = (
        context.request.build_absolute_uri(upload_path)
        if context.request is not None else upload_path
    )
    return {
        'asset_id': str(upload.id),
        'upload_url': upload_url,
        'method': 'PUT',
        'expires_at': upload.expires_at.isoformat(),
        'max_chunk_bytes': MAX_CHUNK_BYTES,
    }


def signed_asset_download_url(upload, request):
    signature = signing.dumps(
        {'asset_id': str(upload.id), 'credential_id': upload.credential_id},
        salt=DOWNLOAD_SIGNING_SALT,
        compress=True,
    )
    path = f'/api/mcp-assets/{upload.id}/{signature}/'
    return request.build_absolute_uri(path) if request is not None else path


def store_artifact(*, connector, credential, filename, content_type, content, request):
    max_bytes = getattr(settings, 'MCP_UPLOAD_MAX_BYTES', DEFAULT_MAX_UPLOAD_BYTES)
    if len(content) > max_bytes:
        raise _tool_error(
            f'El artefacto excede el máximo de {max_bytes} bytes.',
            'CONFLICT',
        )
    digest = hashlib.sha256(content).hexdigest()
    with transaction.atomic():
        artifact = McpUpload.objects.create(
            connector=connector,
            credential=credential,
            filename=Path(filename or 'artifact.bin').name,
            content_type=content_type or 'application/octet-stream',
            expected_size=len(content),
            expected_sha256=digest,
            received_size=len(content),
            status=McpUpload.STATUS_COMPLETE,
            expires_at=timezone.now() + timedelta(minutes=UPLOAD_TTL_MINUTES),
            completed_at=timezone.now(),
        )
        artifact.file.save(artifact.filename, ContentFile(content), save=True)
    return {
        'asset_id': str(artifact.id),
        'filename': artifact.filename,
        'content_type': artifact.content_type,
        'size': artifact.received_size,
        'sha256': artifact.expected_sha256,
        'download_url': signed_asset_download_url(artifact, request),
        'expires_at': artifact.expires_at.isoformat(),
    }


def upload_asset_chunk(arguments):
    raw_chunk = arguments.get('base64')
    if not isinstance(raw_chunk, str):
        raise _tool_error('base64 debe ser texto.')
    try:
        chunk = base64.b64decode(raw_chunk, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _tool_error('base64 no contiene datos válidos.') from exc
    if not chunk or len(chunk) > MAX_CHUNK_BYTES:
        raise _tool_error(f'Cada chunk debe medir entre 1 y {MAX_CHUNK_BYTES} bytes.')
    try:
        chunk_index = int(arguments.get('index'))
    except (TypeError, ValueError) as exc:
        raise _tool_error('index debe ser un entero.') from exc
    chunk_sha256 = str(arguments.get('chunk_sha256') or '').lower()
    if hashlib.sha256(chunk).hexdigest() != chunk_sha256:
        raise _tool_error('El hash del chunk no coincide.', 'CONFLICT')
    with transaction.atomic():
        upload = _upload_or_error(arguments.get('asset_id'), lock=True)
        if upload.status != McpUpload.STATUS_PENDING:
            raise _tool_error('El upload ya no acepta chunks.', 'CONFLICT')
        if chunk_index != upload.next_chunk_index:
            raise _tool_error(
                'El índice del chunk no es el esperado.',
                'CONFLICT',
                {'expected_index': upload.next_chunk_index},
            )
        if upload.received_size + len(chunk) > upload.expected_size:
            raise _tool_error('El chunk excede el tamaño declarado.', 'CONFLICT')
        if upload.file:
            with upload.file.storage.open(upload.file.name, 'ab') as target:
                target.write(chunk)
        else:
            upload.file.save(upload.filename, ContentFile(chunk), save=False)
        upload.received_size += len(chunk)
        upload.next_chunk_index += 1
        upload.save(update_fields=[
            'file', 'received_size', 'next_chunk_index', 'updated_at',
        ])
    return {
        'asset_id': str(upload.id),
        'received_size': upload.received_size,
        'next_chunk_index': upload.next_chunk_index,
    }


def _file_sha256(upload):
    digest = hashlib.sha256()
    with upload.file.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_declared_content(upload):
    """Validate common file signatures after transport integrity succeeds."""
    content_type = upload.content_type
    if content_type == 'video/mp4':
        from rest_framework.exceptions import ValidationError

        from content.services.video_resource_service import probe_video
        try:
            with upload.file.open('rb') as source:
                if source.read(12)[4:8] != b'ftyp':
                    raise ValidationError('El contenido no es MP4.')
            probe_video(upload.file.path)
        except ValidationError as exc:
            raise _tool_error(str(exc.detail), 'INVALID_FILE_CONTENT') from exc
        return
    with upload.file.open('rb') as source:
        if content_type == 'application/zip':
            try:
                with zipfile.ZipFile(source) as archive:
                    members = archive.infolist()
                    if not members or len(members) > 1000:
                        raise ValueError('El ZIP necesita de uno a mil archivos.')
                    for member in members:
                        name = member.filename.replace('\\', '/')
                        parts = name.split('/')
                        if name.startswith('/') or '..' in parts or ':' in name or member.flag_bits & 1:
                            raise ValueError('El ZIP contiene rutas inseguras o archivos cifrados.')
                    if sum(member.file_size for member in members) > 100 * 1024 * 1024:
                        raise ValueError('El ZIP supera el tamaño descomprimido permitido.')
            except (OSError, zipfile.BadZipFile, ValueError) as exc:
                raise _tool_error('El archivo no contiene un ZIP permitido.', 'INVALID_FILE_CONTENT') from exc
            return
        if content_type in {'text/markdown', 'text/plain'}:
            decoder = codecs.getincrementaldecoder('utf-8')()
            try:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    decoder.decode(chunk)
                decoder.decode(b'', final=True)
            except UnicodeDecodeError as exc:
                raise _tool_error(
                    'El contenido de texto no es UTF-8 válido.',
                    'INVALID_FILE_CONTENT',
                ) from exc
            return
        if content_type.endswith('wordprocessingml.document'):
            try:
                with zipfile.ZipFile(source) as archive:
                    names = set(archive.namelist())
            except (OSError, zipfile.BadZipFile) as exc:
                raise _tool_error(
                    'El archivo no contiene un DOCX válido.',
                    'INVALID_FILE_CONTENT',
                ) from exc
            if not {'[Content_Types].xml', 'word/document.xml'} <= names:
                raise _tool_error(
                    'El archivo no contiene un DOCX válido.',
                    'INVALID_FILE_CONTENT',
                )
            return
        if content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            try:
                with zipfile.ZipFile(source) as archive:
                    valid = {'[Content_Types].xml', 'xl/workbook.xml'} <= set(archive.namelist())
            except (OSError, zipfile.BadZipFile) as exc:
                raise _tool_error('El archivo no contiene un XLSX válido.', 'INVALID_FILE_CONTENT') from exc
            if not valid:
                raise _tool_error('El archivo no contiene un XLSX válido.', 'INVALID_FILE_CONTENT')
            return
        header = source.read(1024)
    signature_matches = {
        'application/pdf': header.lstrip().startswith(b'%PDF-'),
        'application/msword': header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
        'application/vnd.ms-excel': header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
        'image/gif': header.startswith((b'GIF87a', b'GIF89a')),
        'image/jpeg': header.startswith(b'\xff\xd8\xff'),
        'image/png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'image/webp': (
            len(header) >= 12
            and header.startswith(b'RIFF')
            and header[8:12] == b'WEBP'
        ),
    }
    if not signature_matches.get(content_type, False):
        raise _tool_error(
            'El contenido no coincide con el tipo MIME declarado.',
            'INVALID_FILE_CONTENT',
        )


def complete_upload(arguments):
    with transaction.atomic():
        upload = _upload_or_error(arguments.get('asset_id'), lock=True)
        if upload.status == McpUpload.STATUS_COMPLETE:
            return _complete_payload(upload)
        if upload.status != McpUpload.STATUS_PENDING or not upload.file:
            raise _tool_error('El upload no tiene datos pendientes para completar.', 'CONFLICT')
        if upload.received_size != upload.expected_size:
            raise _tool_error(
                'El tamaño recibido no coincide.',
                'CONFLICT',
                {'expected': upload.expected_size, 'received': upload.received_size},
            )
        actual_sha256 = _file_sha256(upload)
        if actual_sha256 != upload.expected_sha256:
            raise _tool_error(
                'El SHA-256 final no coincide.',
                'CONFLICT',
                {'expected': upload.expected_sha256, 'actual': actual_sha256},
            )
        _validate_declared_content(upload)
        upload.status = McpUpload.STATUS_COMPLETE
        upload.completed_at = timezone.now()
        upload.save(update_fields=['status', 'completed_at', 'updated_at'])
    return _complete_payload(upload)


def _complete_payload(upload):
    return {
        'asset_id': str(upload.id),
        'status': upload.status,
        'filename': upload.filename,
        'content_type': upload.content_type,
        'size': upload.received_size,
        'sha256': upload.expected_sha256,
        'expires_at': upload.expires_at.isoformat(),
    }


def abort_upload(arguments):
    with transaction.atomic():
        upload = _upload_or_error(arguments.get('asset_id'), lock=True)
        if upload.status == McpUpload.STATUS_CONSUMED:
            raise _tool_error('El archivo ya fue consumido.', 'CONFLICT')
        _delete_file(upload)
        upload.status = McpUpload.STATUS_ABORTED
        upload.save(update_fields=['status', 'updated_at'])
    return {'asset_id': str(upload.id), 'aborted': True}


def consume_upload(asset_id, *, allowed_content_types=None):
    """Lock and return a completed upload for a domain service to consume."""
    upload = _upload_or_error(asset_id, lock=True)
    if upload.status != McpUpload.STATUS_COMPLETE:
        raise _tool_error('El asset debe estar completo antes de usarlo.', 'CONFLICT')
    if allowed_content_types and upload.content_type not in allowed_content_types:
        raise _tool_error('El tipo del asset no es válido para esta acción.')
    return upload


UPLOAD_TOOLS = [
    {
        'name': 'begin_upload',
        'description': 'Inicia un upload binario temporal validado por tamaño, MIME y SHA-256.',
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {
                'filename': {'type': 'string',
                             'description': 'Nombre del archivo; tras descartar la ruta debe tener hasta 255 caracteres y una extensión que coincida con el MIME.'},
                'content_type': {'type': 'string', 'enum': sorted(ALLOWED_CONTENT_TYPES),
                                 'description': 'Tipo MIME permitido para este conector; debe coincidir con la extensión y el contenido del archivo.'},
                'size': {'type': 'integer', 'minimum': 1,
                         'description': 'Tamaño total en bytes, desde 1 hasta el límite del servidor para este MIME; debe coincidir al completar.'},
                'sha256': {'type': 'string', 'pattern': '^[0-9a-fA-F]{64}$',
                           'description': 'SHA-256 del archivo completo: 64 caracteres hexadecimales, en mayúsculas o minúsculas.'},
            },
            'required': ['filename', 'content_type', 'size', 'sha256'],
            'additionalProperties': False,
        },
        'handler': begin_upload,
    },
    {
        'name': 'upload_asset_chunk',
        'description': 'Sube el siguiente chunk cuando el cliente no puede ejecutar el PUT firmado.',
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {
                'asset_id': {'type': 'string', 'format': 'uuid',
                             'description': 'UUID del upload pendiente devuelto por begin_upload, de esta credencial y conector.'},
                'index': {'type': 'integer', 'minimum': 0,
                          'description': 'Índice del siguiente chunk, desde 0; debe coincidir con next_chunk_index.'},
                'base64': {'type': 'string',
                           'description': 'Chunk en Base64 válido; al decodificar debe medir de 1 a 1048576 bytes (1 MiB).'},
                'chunk_sha256': {'type': 'string', 'pattern': '^[0-9a-fA-F]{64}$',
                                 'description': 'SHA-256 de este chunk decodificado: 64 caracteres hexadecimales, en mayúsculas o minúsculas.'},
            },
            'required': ['asset_id', 'index', 'base64', 'chunk_sha256'],
            'additionalProperties': False,
        },
        'handler': upload_asset_chunk,
    },
    {
        'name': 'complete_upload',
        'description': 'Valida tamaño y SHA-256 del archivo y habilita su asset_id.',
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {'asset_id': {'type': 'string', 'format': 'uuid',
                                        'description': 'UUID del upload de esta credencial y conector; valida los bytes recibidos o devuelve el resultado si ya está completo.'}},
            'required': ['asset_id'],
            'additionalProperties': False,
        },
        'handler': complete_upload,
    },
    {
        'name': 'abort_upload',
        'description': 'Descarta un upload temporal que todavía no fue consumido.',
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {'asset_id': {'type': 'string', 'format': 'uuid',
                                        'description': 'UUID del upload de esta credencial y conector que se descartará; no puede estar consumido ni expirado.'}},
            'required': ['asset_id'],
            'additionalProperties': False,
        },
        'handler': abort_upload,
    },
]
