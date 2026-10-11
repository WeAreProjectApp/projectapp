"""Hardened Chromium launch for Linktree template validation."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from content.services.linktree_templates import validation

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


def candidate():
    """Build the smallest candidate the validator can prepare without a database."""
    template = SimpleNamespace(warnings=[], manifest={'fonts': [], 'motion': False})
    return SimpleNamespace(id=uuid4(), template=template, profile={}, assets={}, document='<main>Hola</main>')


def captured_launch(monkeypatch):
    """Run the validator until Chromium would start and return the launch options."""
    calls = []
    monkeypatch.setattr(validation, 'sync_playwright', capturing_playwright(calls))
    with pytest.raises(LaunchCaptured):
        validation.validate_in_browser(candidate())
    return calls[0]


def test_launch_hides_process_secrets_and_disables_jit(monkeypatch, settings):
    """Fails if Chromium inherits the worker's secrets again or V8 regains its JIT."""
    monkeypatch.setenv('DJANGO_SECRET_KEY', SENTINEL)

    options = captured_launch(monkeypatch)

    assert set(options['env']) == {'HOME', 'PATH', 'LANG'}
    assert SENTINEL not in options['env'].values()
    assert '--js-flags=--jitless' in options['args']
    assert 'executable_path' not in options


def test_configured_chromium_executable_is_launched(monkeypatch, settings):
    """Fails if a relocated browser binary is ignored, blocking the move out of ~/.cache."""
    settings.LINKTREE_CHROMIUM_EXECUTABLE = '/opt/linktree/chrome-headless-shell'

    options = captured_launch(monkeypatch)

    assert options['executable_path'] == '/opt/linktree/chrome-headless-shell'
