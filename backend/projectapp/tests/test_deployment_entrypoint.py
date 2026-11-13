"""Retired deploy entry point and preserved template smoke-check contract."""

import importlib.util
import json
import os
import subprocess
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('arguments', [
    [], ['--yes'], ['--dry-run'], ['--skip-frontend'], ['--sync-configs'],
    ['--help'], ['--unknown'], ['--yes', '--skip-frontend'],
])
def test_retired_script_refuses_to_deploy(tmp_path, arguments):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    marker = tmp_path / 'unexpected-command'
    for command in ['git', 'pip', 'python', 'npm', 'sudo', 'systemctl', 'curl']:
        executable = bin_dir / command
        executable.write_text('#!/bin/bash\nprintf unexpected >"$COMMAND_MARKER"\nexit 99\n')
        executable.chmod(0o755)

    result = subprocess.run(
        ['/bin/bash', str(REPO_ROOT / 'scripts' / 'deploy.sh'), *arguments],
        cwd=tmp_path,
        env={**os.environ, 'PATH': str(bin_dir), 'COMMAND_MARKER': str(marker)},
        capture_output=True, text=True, timeout=10,
    )

    assert result.returncode == 2
    assert '/deploy-and-check' in result.stderr
    assert 'Integrity' in result.stderr
    assert not marker.exists()


@pytest.fixture
def template_check():
    spec = importlib.util.spec_from_file_location('template_deployment_check', REPO_ROOT / 'scripts' / 'check-template-deploy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def http_response(status, content_type, payload):
    headers = Message()
    headers['Content-Type'] = content_type
    return HTTPError('https://example.test/templates/', status, 'fixture', headers, BytesIO(payload))


def test_template_check_accepts_the_authentication_boundary(template_check, monkeypatch):
    response = http_response(401, 'application/json', json.dumps({'detail': 'Authentication required'}).encode())
    requests = []

    def request_api(request, timeout):
        requests.append((request.full_url, timeout))
        raise response

    monkeypatch.setattr(template_check, 'urlopen', request_api)

    template_check.check_template_api('https://example.test')

    assert requests == [('https://example.test/api/linktrees/admin/11111111-1111-4111-8111-111111111111/templates/', 15)]


@pytest.mark.parametrize('status,content_type,payload', [
    (200, 'text/html', b'<html>SPA</html>'),
    (401, 'text/html', b'<html>Not JSON</html>'),
    (401, 'application/json', b'{broken'),
    (401, 'application/json', b'{"detail":""}'),
    (401, 'application/json', b'[]'),
])
def test_template_check_rejects_an_invalid_deployment_response(template_check, monkeypatch, status, content_type, payload):
    response = http_response(status, content_type, payload)
    monkeypatch.setattr(template_check, 'urlopen', lambda request, timeout: response)

    with pytest.raises(ValueError):
        template_check.check_template_api('https://example.test')
