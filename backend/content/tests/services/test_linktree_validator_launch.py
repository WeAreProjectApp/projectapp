"""Hardened Chromium launch for Linktree template validation."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from content.services.linktree_templates import validation
from content.services.linktree_templates.contract import ValidatorError
from linktree_sandbox import worker

SENTINEL = 'sentinel-secret-not-for-chromium'


class LaunchCaptured(Exception):
    """Stops validation right after Chromium's launch options are recorded."""


def capturing_playwright(calls):
    """Return a sync_playwright stand-in whose launch records its options and stops."""
    def launch(**options):
        calls.append(options)
        raise LaunchCaptured

    class Manager:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))

        def __exit__(self, *exc_info):
            return False

    return Manager


def minimal_request():
    """The smallest request the worker accepts."""
    return worker.parse_request(json.dumps({
        'v': 1, 'document': '<main>Hola</main>', 'csp': "default-src 'none'", 'widths': [320],
        'resources': {}, 'fonts': {}, 'google_css': '', 'motion_declared': False, 'pwa_enabled': False,
    }).encode())


def test_launch_hides_process_secrets_and_disables_jit(monkeypatch):
    """Fails if Chromium inherits the worker's secrets again or V8 regains its JIT."""
    monkeypatch.setenv('DJANGO_SECRET_KEY', SENTINEL)
    calls = []
    monkeypatch.setattr(worker, 'sync_playwright', capturing_playwright(calls))

    with pytest.raises(LaunchCaptured):
        worker.run(minimal_request())

    assert set(calls[0]['env']) == {'HOME', 'PATH', 'LANG'}
    assert SENTINEL not in calls[0]['env'].values()
    assert '--js-flags=--jitless' in calls[0]['args']
    assert 'executable_path' not in calls[0]


def test_configured_chromium_executable_reaches_the_launch(monkeypatch, settings):
    """Fails if a relocated browser binary is ignored, blocking the move out of ~/.cache."""
    settings.LINKTREE_CHROMIUM_EXECUTABLE = '/opt/linktree/chrome-headless-shell'
    calls = []
    monkeypatch.setattr(worker, 'sync_playwright', capturing_playwright(calls))
    template = SimpleNamespace(warnings=[], manifest={'fonts': [], 'motion': False})
    candidate = SimpleNamespace(id=uuid4(), template=template, profile={}, assets={}, document='<main>Hola</main>')

    with pytest.raises(ValidatorError):
        validation.validate_in_browser(candidate)

    assert calls[0]['executable_path'] == '/opt/linktree/chrome-headless-shell'
