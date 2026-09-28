"""Commercial videos travel through the real upload and serving boundaries."""
import base64
import hashlib
from pathlib import Path
import subprocess

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from content.models import BusinessProposal, McpConnector, VideoResource

pytestmark = pytest.mark.django_db


@pytest.fixture(scope='module')
def mp4_bytes(tmp_path_factory):
    target = tmp_path_factory.mktemp('videos') / 'clip.mp4'
    subprocess.run([
        'ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:r=1',
        '-t', '1', '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target),
    ], check=True, timeout=20)
    return target.read_bytes()


@pytest.fixture
def staff_client(django_user_model):
    staff = django_user_model.objects.create_user('video-admin', password='test-only', is_staff=True)
    client = APIClient()
    client.force_authenticate(staff)
    return client


def upload(client, path, content, revision=0):
    return client.post(path, {
        'action': 'upload', 'revision': revision,
        'file': SimpleUploadedFile('clip.mp4', content, content_type='video/mp4'),
    }, format='multipart')


def test_panel_upload_produces_playable_resource(staff_client, mp4_bytes):
    response = upload(staff_client, '/api/video-resources/admin/modules/financing/es/', mp4_bytes)
    assert response.status_code == 200, response.data
    assert response.data['sha256'] == hashlib.sha256(mp4_bytes).hexdigest()
    assert response.data['video']['width'] == 32
    resource = VideoResource.objects.get(key='financing:es')
    assert Path(resource.file.path).read_bytes() == mp4_bytes


def test_failed_replacement_preserves_previous_video(staff_client, mp4_bytes):
    path = '/api/video-resources/admin/modules/proposal/es/'
    original = upload(staff_client, path, mp4_bytes).data
    response = upload(staff_client, path, b'not a video', revision=1)
    assert response.status_code == 400
    assert staff_client.get(path).data['video'] == original['video']


def test_stale_revision_cannot_replace_video(staff_client, mp4_bytes):
    path = '/api/video-resources/admin/modules/additional-modules/es/'
    original = upload(staff_client, path, mp4_bytes).data
    response = upload(staff_client, path, mp4_bytes)
    assert response.status_code == 409
    assert staff_client.get(path).data['video'] == original['video']


def test_remove_keeps_generic_empty_until_restored(staff_client):
    path = '/api/video-resources/admin/modules/proposal/es/'
    removed = staff_client.post(path, {'action': 'remove', 'revision': 0}, format='json')
    assert removed.data['mode'] == 'none'
    assert removed.data['video'] is None
    restored = staff_client.post(path, {'action': 'restore-default', 'revision': 1}, format='json')
    assert restored.data['mode'] == 'default'


def test_video_delivery_honors_range(staff_client, client, mp4_bytes):
    result = upload(staff_client, '/api/video-resources/admin/modules/proposal/es/', mp4_bytes).data
    response = client.get(result['video']['src'], HTTP_RANGE='bytes=0-15')
    assert response.status_code == 206
    assert b''.join(response.streaming_content) == mp4_bytes[:16]


def test_inactive_proposal_blocks_its_video(staff_client, client, mp4_bytes):
    proposal = BusinessProposal.objects.create(title='Video', client_name='Client', is_active=False)
    result = upload(staff_client, f'/api/video-resources/admin/proposals/{proposal.pk}/', mp4_bytes).data
    response = client.get(result['video']['src'])
    assert response.status_code == 404


def test_deleting_proposal_removes_private_video_files(staff_client, mp4_bytes, django_capture_on_commit_callbacks):
    proposal = BusinessProposal.objects.create(title='Video to delete', client_name='Client')
    upload(staff_client, f'/api/video-resources/admin/proposals/{proposal.pk}/', mp4_bytes)
    resource = VideoResource.objects.get(proposal=proposal)
    paths = [Path(resource.file.path), Path(resource.poster.path)]
    assert all(path.exists() for path in paths)

    with django_capture_on_commit_callbacks(execute=True):
        proposal.delete()

    assert not VideoResource.objects.filter(pk=resource.pk).exists()
    assert all(not path.exists() for path in paths)


def test_mcp_chunks_publish_a_playable_personalized_video(api_client, client, mp4_bytes):
    connector, _ = McpConnector.objects.get_or_create(slug='proposals', defaults={'name': 'Propuestas'})
    connector.is_active = True
    connector.save()
    endpoint = f'/api/mcp/proposals/{connector.generate_token()}/'
    proposal = BusinessProposal.objects.create(title='Video in chunks', client_name='Client')

    def call(name, arguments):
        response = api_client.post(endpoint, {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }, format='json')
        result = response.data['result']
        assert result['isError'] is False, result
        return result['structuredContent']

    temporary = call('begin_upload', {
        'filename': 'personalized.mp4', 'content_type': 'video/mp4',
        'size': len(mp4_bytes), 'sha256': hashlib.sha256(mp4_bytes).hexdigest(),
    })
    first, second = mp4_bytes[:600], mp4_bytes[600:]
    call('upload_asset_chunk', {
        'asset_id': temporary['asset_id'], 'index': 0,
        'base64': base64.b64encode(first).decode(), 'chunk_sha256': hashlib.sha256(first).hexdigest(),
    })
    call('upload_asset_chunk', {
        'asset_id': temporary['asset_id'], 'index': 1,
        'base64': base64.b64encode(second).decode(), 'chunk_sha256': hashlib.sha256(second).hexdigest(),
    })
    call('complete_upload', {'asset_id': temporary['asset_id']})
    assigned = call('set_proposal_personalized_video', {
        'proposal_id': proposal.pk, 'asset_id': temporary['asset_id'], 'revision': 0,
    })

    response = client.get(assigned['video']['src'])
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == mp4_bytes


@pytest.mark.parametrize('slug,tool,target', [
    ('partnership-program', 'set_partnership_program_video', 'language'),
    ('additional-modules', 'set_additional_modules_video', 'language'),
    ('proposals', 'set_proposal_generic_video', 'language'),
    ('proposals', 'set_proposal_personalized_video', 'proposal_id'),
])
def test_mcp_can_upload_new_video_then_replace_it(api_client, client, mp4_bytes, slug, tool, target):
    connector, _ = McpConnector.objects.get_or_create(slug=slug, defaults={'name': slug})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()
    endpoint = f'/api/mcp/{slug}/{token}/'
    arguments = {}
    # Parameterization chooses a target, never branches the tested action.
    proposal = BusinessProposal.objects.create(title='Video proposal', client_name='Client')
    arguments[target] = {'proposal_id': proposal.pk, 'language': 'es'}[target]

    def call(name, args):
        response = api_client.post(endpoint, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}}, format='json')
        result = response.data['result']
        assert result['isError'] is False, result
        return result['structuredContent']

    def assign(revision):
        temporary = call('begin_upload', {'filename': 'clip.mp4', 'content_type': 'video/mp4', 'size': len(mp4_bytes), 'sha256': hashlib.sha256(mp4_bytes).hexdigest()})
        from urllib.parse import urlsplit
        transferred = client.put(urlsplit(temporary['upload_url']).path, mp4_bytes, content_type='video/mp4')
        assert transferred.status_code == 200
        call('complete_upload', {'asset_id': temporary['asset_id']})
        return call(tool, {**arguments, 'asset_id': temporary['asset_id'], 'revision': revision})

    original = assign(0)
    replaced = assign(1)
    assert replaced['revision'] == 2
    assert replaced['filename'] == 'clip.mp4'
    assert replaced['video']['src'] != original['video']['src']
    assert client.get(original['video']['src']).status_code == 404
    current = client.get(replaced['video']['src'])
    assert b''.join(current.streaming_content) == mp4_bytes
