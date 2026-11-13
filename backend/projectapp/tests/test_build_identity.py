"""Observable version contracts; filesystem fixtures never reach live artifacts."""

import json
import subprocess
from pathlib import Path

import pytest
from django.apps import apps

from projectapp import build_identity

COMMIT = 'a' * 40
OTHER_COMMIT = 'b' * 40


def write_manifest(path, commit=COMMIT):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 1, 'project': 'projectapp', 'commit': commit}))


@pytest.fixture
def artifacts(tmp_path, settings, monkeypatch):
    settings.BASE_DIR = tmp_path
    settings.STATIC_ROOT = tmp_path / 'staticfiles'
    # Each test represents a fresh worker startup, not a request-time refresh.
    monkeypatch.setattr(build_identity, '_captured', False)
    monkeypatch.setattr(build_identity, '_backend_commit', None)
    return (
        Path(settings.STATIC_ROOT) / 'frontend' / 'version.json',
        tmp_path / 'static' / 'frontend' / 'version.json',
    )


def test_backend_reports_its_startup_build(client, artifacts):
    write_manifest(artifacts[0])
    apps.get_app_config('content').ready()

    response = client.get('/api/version/')

    assert response.status_code == 200
    assert response.json() == {'schema_version': 1, 'project': 'projectapp', 'commit': COMMIT}


def test_frontend_reports_the_published_build(client, artifacts):
    write_manifest(artifacts[1])

    response = client.get('/version.json')

    assert response.status_code == 200
    assert response.json()['commit'] == COMMIT


def test_backend_keeps_its_identity_after_artifact_replacement(client, artifacts):
    write_manifest(artifacts[0])
    apps.get_app_config('content').ready()
    write_manifest(artifacts[0], OTHER_COMMIT)

    response = client.get('/api/version/')

    assert response.json()['commit'] == COMMIT


def test_reports_a_mixed_publication_without_relabeling_the_backend(client, artifacts):
    write_manifest(artifacts[0])
    apps.get_app_config('content').ready()
    write_manifest(artifacts[1], OTHER_COMMIT)

    backend = client.get('/api/version/').json()
    frontend = client.get('/version.json').json()

    assert backend['commit'] == COMMIT
    assert frontend['commit'] == OTHER_COMMIT


def test_missing_backend_identity_stays_unknown_after_later_publication(client, artifacts):
    apps.get_app_config('content').ready()
    write_manifest(artifacts[0])

    response = client.get('/api/version/')

    assert response.status_code == 503
    assert response.json()['commit'] is None


def test_missing_frontend_manifest_never_returns_the_spa(client, artifacts):
    artifacts[1].parent.mkdir(parents=True)
    (artifacts[1].parent / '200.html').write_text('<html>SPA fallback</html>')

    response = client.get('/version.json')

    assert response.status_code == 503
    assert response['Content-Type'] == 'application/json'
    assert response.json()['commit'] is None


@pytest.mark.parametrize('payload', [
    '{broken',
    '[]',
    json.dumps({'schema_version': 2, 'project': 'projectapp', 'commit': COMMIT}),
    json.dumps({'schema_version': 1, 'project': 'other', 'commit': COMMIT}),
    json.dumps({'schema_version': 1, 'project': 'projectapp', 'commit': 'abc123'}),
])
def test_invalid_frontend_manifest_is_unavailable(client, artifacts, payload):
    artifacts[1].parent.mkdir(parents=True)
    artifacts[1].write_text(payload)

    response = client.get('/version.json')

    assert response.status_code == 503
    assert response.json()['commit'] is None


def test_invalid_backend_manifest_is_unavailable(client, artifacts):
    artifacts[0].parent.mkdir(parents=True)
    artifacts[0].write_text('{broken')
    apps.get_app_config('content').ready()

    response = client.get('/api/version/')

    assert response.status_code == 503
    assert response.json()['commit'] is None


def test_oversized_manifest_is_unavailable(client, artifacts):
    artifacts[1].parent.mkdir(parents=True)
    artifacts[1].write_text(' ' * 4096 + json.dumps({'schema_version': 1, 'project': 'projectapp', 'commit': COMMIT}))

    response = client.get('/version.json')

    assert response.status_code == 503


@pytest.mark.parametrize('url', ['/api/version/', '/version.json'])
def test_version_endpoint_rejects_writes(client, artifacts, url):
    response = client.post(url, {})

    assert response.status_code == 405


@pytest.mark.parametrize('url', ['/api/version/', '/version.json'])
def test_version_endpoint_supports_head(client, artifacts, url):
    write_manifest(artifacts[0])
    write_manifest(artifacts[1])
    apps.get_app_config('content').ready()

    response = client.head(url)

    assert response.status_code == 200
    assert response.content == b''


@pytest.mark.parametrize('url', ['/api/version/', '/version.json'])
def test_version_response_cannot_be_cached(client, artifacts, url):
    response = client.get(url)

    assert 'no-store' in response['Cache-Control']


def test_version_reads_do_not_execute_git(client, artifacts, monkeypatch):
    write_manifest(artifacts[0])
    write_manifest(artifacts[1])

    def deny_process(*args, **kwargs):
        raise AssertionError('Version reads must not start subprocesses')

    monkeypatch.setattr(subprocess, 'Popen', deny_process)
    apps.get_app_config('content').ready()

    backend = client.get('/api/version/')
    frontend = client.get('/version.json')

    assert backend.json()['commit'] == COMMIT
    assert frontend.json()['commit'] == COMMIT
