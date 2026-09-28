"""A real HTTP boundary catches buffering/size regressions hidden by test clients."""
import hashlib
import struct
import subprocess
from urllib.parse import urlsplit

import pytest
import requests

from content.models import McpConnector, VideoResource
from content.services.video_resource_service import VIDEO_MAX_BYTES


@pytest.mark.django_db(transaction=True)
def test_signed_http_upload_accepts_a_video_at_the_size_limit(live_server, tmp_path):
    path = tmp_path / 'full-size.mp4'
    subprocess.run([
        'ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:r=1',
        '-t', '1', '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path),
    ], check=True, timeout=20)
    # ISO BMFF free atom: valid padding, not a mocked validator or fake codec.
    with path.open('ab') as target:
        target.write(struct.pack('>I4s', VIDEO_MAX_BYTES - path.stat().st_size, b'free'))
        target.truncate(VIDEO_MAX_BYTES)
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    connector, _ = McpConnector.objects.get_or_create(slug='partnership-program', defaults={'name': 'Alianza'})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()
    endpoint = f'{live_server.url}/api/mcp/partnership-program/{token}/'

    def call(tool, arguments):
        response = requests.post(endpoint, json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': tool, 'arguments': arguments},
        }, timeout=120)
        response.raise_for_status()
        result = response.json()['result']
        assert result['isError'] is False, result
        return result['structuredContent']

    upload = call('begin_upload', {
        'filename': path.name, 'content_type': 'video/mp4',
        'size': VIDEO_MAX_BYTES, 'sha256': digest,
    })
    upload_path = urlsplit(upload['upload_url']).path
    with path.open('rb') as source:
        transferred = requests.put(live_server.url + upload_path, data=source, headers={'Content-Type': 'video/mp4'}, timeout=120)
    assert transferred.status_code == 200
    call('complete_upload', {'asset_id': upload['asset_id']})
    assigned = call('set_partnership_program_video', {'asset_id': upload['asset_id'], 'revision': 0})
    assert assigned['size'] == VIDEO_MAX_BYTES
    assert assigned['sha256'] == digest
    served = requests.get(live_server.url + assigned['video']['src'], headers={'Range': 'bytes=0-15'}, timeout=30)
    assert served.status_code == 206
    assert served.content[4:8] == b'ftyp'
    stored = VideoResource.objects.get(key='financing:es')
    assert stored.file.size == VIDEO_MAX_BYTES
