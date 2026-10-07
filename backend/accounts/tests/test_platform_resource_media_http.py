"""Real isolated nginx HTTP proves legacy denial ahead of authenticated bytes."""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from accounts.services.tokens import get_tokens_for_user
from accounts.tests.platform_media_helpers import KINDS, download_url, legacy_files
from accounts.tests.platform_media_helpers import media_context as media_context

pytestmark = pytest.mark.django_db(transaction=True)
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def nginx_endpoint(tmp_path, live_server, settings):
    """Run only a private localhost process, using the shipped denial fragment."""
    binary = (os.environ.get('PLATFORM_MEDIA_NGINX_BINARY') or shutil.which('nginx')
        or str(ROOT / 'frontend/test-results/nginx-runtime/extracted/usr/sbin/nginx'))
    if not Path(binary).is_file():
        pytest.skip('No isolated nginx binary is available for this HTTP proof.')
    settings.ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    template = (ROOT / 'scripts/nginx/projectapp.conf').read_text()
    denial = template.split('# platform-resource-denial:begin', 1)[1].split('# platform-resource-denial:end', 1)[0]
    config = tmp_path / 'nginx.conf'
    config.write_text(f'''
daemon off;
worker_processes 1;
pid "{tmp_path / 'nginx.pid'}";
error_log stderr warn;
events {{ worker_connections 64; }}
http {{
  access_log off;
  client_body_temp_path "{tmp_path / 'client-body'}";
  proxy_temp_path "{tmp_path / 'proxy'}";
  fastcgi_temp_path "{tmp_path / 'fastcgi'}";
  uwsgi_temp_path "{tmp_path / 'uwsgi'}";
  scgi_temp_path "{tmp_path / 'scgi'}";
  server {{
    listen 127.0.0.1:{port};
    server_name localhost;
    {denial}
    location /media/ {{ alias "{storages['default'].location}/"; }}
    location /api/ {{ proxy_set_header Host 127.0.0.1; proxy_pass {live_server.url}; }}
  }}
}}
''')
    process = subprocess.Popen([binary, '-p', str(tmp_path), '-c', str(config)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    endpoint = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f'Isolated nginx failed to start: {process.stderr.read().decode()}')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail('Isolated nginx did not start within eight seconds.')
        yield endpoint
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stderr.close()


def http_get(url, user=None):
    """Read actual HTTP responses with real JWTs carried only in their header."""
    headers = {} if user is None else {'Authorization': f'Bearer {get_tokens_for_user(user)["access"]}'}
    try:
        with urlopen(Request(url, headers=headers), timeout=8) as response:
            return response.status, response.read(), dict(response.headers)
    except HTTPError as response:
        return response.code, response.read(), dict(response.headers)


@pytest.mark.parametrize('visitor', ['anonymous', 'owner', 'foreign'])
@pytest.mark.parametrize('kind', KINDS)
def test_nginx_denies_legacy_bytes_for_every_visitor(media_context, nginx_endpoint, visitor, kind):
    """Fails if nginx publishes any original, even for authenticated browser requests."""
    legacy_files(media_context)
    status, body, _ = http_get(f'{nginx_endpoint}/media/{media_context["rows"][kind].file.name}',
        media_context.get(visitor))
    assert status == 404
    assert media_context['bodies'][kind] not in body


@pytest.mark.parametrize('kind', KINDS)
def test_nginx_authorized_route_returns_the_exact_legacy_bytes(media_context, nginx_endpoint, kind):
    """Fails if denying public paths breaks the JWT route during conversion."""
    legacy_files(media_context)
    status, body, headers = http_get(nginx_endpoint + download_url(media_context, kind), media_context['owner'])
    assert status == 200
    assert body == media_context['bodies'][kind]
    assert headers['Cache-Control'] == 'no-store'


def test_nginx_preserves_unrelated_public_media(media_context, nginx_endpoint):
    """Fails if the focused legacy denial disables unrelated public resources."""
    name = storages['default'].save('public/preview.txt', ContentFile(b'public preview'))
    status, body, _ = http_get(f'{nginx_endpoint}/media/{name}')
    assert status == 200
    assert body == b'public preview'
