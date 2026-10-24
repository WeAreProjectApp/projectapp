"""Projects MCP manages the same tutorial resources as the panel."""
import hashlib
import subprocess
from urllib.parse import urlsplit

import pytest
from rest_framework.test import APIClient

from content.models import McpConnector, VideoResource

pytestmark = pytest.mark.django_db


@pytest.fixture(scope='module')
def video_bytes(tmp_path_factory):
    path = tmp_path_factory.mktemp('help-video') / 'tutorial.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=green:s=32x32:r=1', '-t', '1', '-c:v', 'libx264',
                    '-threads', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path)],
                   check=True, timeout=20)
    return path.read_bytes()


@pytest.fixture
def rpc(django_user_model):
    django_user_model.objects.create_superuser('tutorial-mcp-admin', password='test-password')
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Proyectos'})
    connector.is_active = True
    connector.save()
    endpoint = f'/api/mcp/projects/{connector.generate_token()}/'
    client = APIClient()

    def call(name, arguments, *, expect_error=False):
        response = client.post(endpoint, {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }, format='json')
        result = response.data['result']
        assert result['isError'] is expect_error, result
        return result['structuredContent']
    return call


def confirmed(rpc, name, arguments):
    preview = rpc(name, arguments)
    return rpc('confirm_action', {'confirmation_id': preview['confirmation_id']})['result']


def assign(rpc, client, content, revision):
    upload = rpc('begin_upload', {
        'filename': 'tutorial.mp4', 'content_type': 'video/mp4',
        'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
    })
    assert client.put(urlsplit(upload['upload_url']).path, content, content_type='video/mp4').status_code == 200
    rpc('complete_upload', {'asset_id': upload['asset_id']})
    return rpc('set_platform_help_video', {
        'topic': 'general', 'language': 'es', 'asset_id': upload['asset_id'], 'revision': revision,
    })


def test_mcp_upload_publishes_playable_tutorial(rpc, client, video_bytes):
    result = assign(rpc, client, video_bytes, 0)
    resource = VideoResource.objects.get(key='platform-overview:es')
    assert resource.mode == 'uploaded'
    current = rpc('get_platform_help_video', {'topic': 'general'})
    assert current['revision'] == 1
    response = client.get(current['video']['src'], HTTP_RANGE='bytes=0-15')
    assert response.status_code == 206
    assert b''.join(response.streaming_content) == video_bytes[:16]


def test_mcp_replacement_invalidates_the_previous_url(rpc, client, video_bytes):
    original = assign(rpc, client, video_bytes, 0)
    replacement = assign(rpc, client, video_bytes, 1)
    assert replacement['revision'] == 2
    assert client.get(original['video']['src']).status_code == 404
    assert client.get(replacement['video']['src']).status_code == 200


def test_mcp_removal_requires_confirmation(rpc):
    preview = rpc('remove_platform_help_video', {'topic': 'general', 'revision': 0})
    assert preview['confirmation_required'] is True
    assert not VideoResource.objects.filter(key='platform-overview:es').exists()
    rpc('confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert rpc('get_platform_help_video', {'topic': 'general'})['mode'] == 'none'


def test_mcp_restore_preserves_stale_revision_conflict(rpc):
    confirmed(rpc, 'remove_platform_help_video', {'topic': 'general', 'revision': 0})
    result = rpc('restore_default_platform_help_video', {'topic': 'general', 'revision': 0}, expect_error=True)
    assert result['error']['code'] == 'CONFLICT'
    assert rpc('get_platform_help_video', {'topic': 'general'})['mode'] == 'none'
