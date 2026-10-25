"""Rejected tutorial replacements leave the published resource usable."""
import hashlib
import json
import subprocess
from unittest.mock import Mock

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import UserProfile
from content.models import VideoResource
from content.services import video_resource_service

pytestmark = pytest.mark.django_db
RESOURCE = '/api/video-resources/admin/modules/platform-overview/es/'
PUBLISHED_BYTES = b'previous tutorial'
PUBLISHED_SHA = hashlib.sha256(PUBLISHED_BYTES).hexdigest()
MP4_HEADER = b'\x00\x00\x00\x18ftypisom'
VIDEO_STREAM = {
    'codec_type': 'video', 'codec_name': 'h264', 'pix_fmt': 'yuv420p',
    'width': 32, 'height': 32,
}
PROBE_ERROR = 'Usa un MP4 válido con video H.264 de hasta 4K y audio AAC opcional.'


@pytest.fixture
def staff_api(django_user_model):
    user = django_user_model.objects.create_user(
        'tutorial-validation-admin', password='test-only', is_staff=True,
    )
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def published_tutorial():
    resource = VideoResource(
        key='platform-overview:es', module='platform-overview', language='es',
        mode='uploaded', revision=7, filename='previous.mp4',
        size=len(PUBLISHED_BYTES), sha256=PUBLISHED_SHA,
        duration_seconds=30, width=32, height=32,
    )
    resource.file.save('video.mp4', ContentFile(PUBLISHED_BYTES), save=False)
    resource.poster.save('poster.webp', ContentFile(b'previous poster'), save=False)
    resource.save()
    return resource


def replace_tutorial(client, *, filename='new.mp4', content_type='video/mp4'):
    return client.post(RESOURCE, {
        'action': 'upload', 'revision': 7,
        'file': SimpleUploadedFile(filename, MP4_HEADER, content_type=content_type),
    }, format='multipart')


def assert_published_tutorial_preserved(client, resource):
    original_file, original_poster = resource.file.name, resource.poster.name
    resource.refresh_from_db()
    assert resource.mode == 'uploaded'
    assert resource.revision == 7
    assert resource.sha256 == PUBLISHED_SHA
    assert resource.file.name == original_file
    assert resource.poster.name == original_poster
    current = client.get(RESOURCE)
    assert current.status_code == 200
    assert current.data['revision'] == 7
    assert current.data['filename'] == 'previous.mp4'
    response = client.get(current.data['video']['src'])
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == PUBLISHED_BYTES


def test_client_catalog_rejects_admin_session(django_user_model):
    """Fails if a valid administrator JWT exposes the client-only tutorial catalog."""
    user = django_user_model.objects.create_user('tutorial-non-client', password='test-only')
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    response = client.get('/api/platform/help/videos/')

    assert response.status_code == 403
    assert str(response.data['detail']) == 'Se requiere una cuenta de cliente activa.'


def test_client_catalog_rejects_missing_profile(django_user_model):
    """Fails if a JWT without a platform profile exposes the client tutorial catalog."""
    user = django_user_model.objects.create_user('tutorial-no-profile', password='test-only')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    response = client.get('/api/platform/help/videos/')

    assert response.status_code == 403
    assert str(response.data['detail']) == 'Se requiere una cuenta de cliente activa.'


@pytest.mark.parametrize('module', [
    'platform-overview', 'platform-chatbot', 'platform-voice-reporting',
])
def test_tutorial_resource_rejects_unpublished_language(staff_api, published_tutorial, module):
    """Fails if the panel advertises an English tutorial that this release does not provide."""
    response = staff_api.get(f'/api/video-resources/admin/modules/{module}/en/')

    assert response.status_code == 400
    assert str(response.data['resource']) == 'Módulo o idioma inválido.'
    assert_published_tutorial_preserved(staff_api, published_tutorial)


@pytest.mark.parametrize(('filename', 'content_type', 'message'), [
    ('new.webm', 'video/mp4', 'Selecciona un archivo .mp4 con nombre de hasta 255 caracteres.'),
    ('new.mp4', 'video/webm', 'El tipo del archivo debe ser video/mp4.'),
])
def test_incompatible_upload_preserves_tutorial(
    staff_api, published_tutorial, filename, content_type, message,
):
    """Fails if rejecting an incompatible upload erases the current tutorial."""
    response = replace_tutorial(staff_api, filename=filename, content_type=content_type)

    assert response.status_code == 400
    assert str(response.data['file']) == message
    assert_published_tutorial_preserved(staff_api, published_tutorial)


@pytest.mark.parametrize(('streams', 'duration'), [
    ([], '1'),
    ([{**VIDEO_STREAM, 'codec_name': 'hevc'}], '1'),
    ([{**VIDEO_STREAM, 'pix_fmt': 'yuv444p'}], '1'),
    ([VIDEO_STREAM, {'codec_type': 'audio', 'codec_name': 'mp3'}], '1'),
    ([VIDEO_STREAM], '0'),
    ([VIDEO_STREAM], 'nan'),
    ([{**VIDEO_STREAM, 'width': 8192}], '1'),
], ids=['no-video', 'hevc', 'unsupported-pixels', 'mp3', 'zero-duration', 'nonfinite-duration', 'over-4k'])
def test_unplayable_upload_preserves_tutorial(
    staff_api, published_tutorial, monkeypatch, streams, duration,
):
    """Fails if unsupported probed media replaces the playable published tutorial."""
    probe = {'streams': streams, 'format': {'duration': duration}}
    probe_runner = Mock(
        return_value=subprocess.CompletedProcess(['ffprobe'], 0, json.dumps(probe)),
    )
    monkeypatch.setattr(video_resource_service.subprocess, 'run', probe_runner)

    response = replace_tutorial(staff_api)

    assert response.status_code == 400
    assert str(response.data['file']) == PROBE_ERROR
    probe_runner.assert_called_once()
    assert_published_tutorial_preserved(staff_api, published_tutorial)


def test_probe_timeout_preserves_tutorial(staff_api, published_tutorial, monkeypatch):
    """Fails if an unavailable media probe deletes the currently published tutorial."""
    probe_runner = Mock(
        side_effect=subprocess.TimeoutExpired('ffprobe', 30),
    )
    monkeypatch.setattr(video_resource_service.subprocess, 'run', probe_runner)

    response = replace_tutorial(staff_api)

    assert response.status_code == 400
    assert str(response.data['file']) == PROBE_ERROR
    probe_runner.assert_called_once()
    assert_published_tutorial_preserved(staff_api, published_tutorial)


def test_poster_failure_preserves_tutorial(staff_api, published_tutorial, monkeypatch):
    """Fails if a poster generation failure discards the last usable tutorial."""
    probe = {'streams': [VIDEO_STREAM], 'format': {'duration': '1'}}
    media_runner = Mock(side_effect=[
        subprocess.CompletedProcess(['ffprobe'], 0, json.dumps(probe)),
        subprocess.CalledProcessError(1, ['ffmpeg']),
    ])
    monkeypatch.setattr(video_resource_service.subprocess, 'run', media_runner)

    response = replace_tutorial(staff_api)

    assert response.status_code == 400
    assert str(response.data['file']) == 'No se pudo obtener la portada del video.'
    media_runner.assert_called()
    assert media_runner.call_args.args[0][0] == 'ffmpeg'
    assert_published_tutorial_preserved(staff_api, published_tutorial)
