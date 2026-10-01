"""Fail-closed mail isolation for the P4 disposable browser server."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core import mail
from django.core.mail.backends.dummy import EmailBackend as DummyEmailBackend
from django.test import override_settings

from accounts.tests.project_collaboration_browser_server import (
    LOCMEM_BACKEND,
    certify_mail_isolation,
)


def test_isolation_certifies_memory_aliases():
    """Fails if a secondary mailer is omitted from the isolation certificate."""
    configured = {'default': {'BACKEND': LOCMEM_BACKEND}, 'notifications': {'BACKEND': LOCMEM_BACKEND}}
    with override_settings(MAILERS=configured):
        certificate = certify_mail_isolation()
    assert certificate == {'default': LOCMEM_BACKEND, 'notifications': LOCMEM_BACKEND}


@pytest.mark.parametrize('configured', [None, {}, [], {'notifications': {'BACKEND': LOCMEM_BACKEND}}])
def test_isolation_rejects_missing_default_mailer(configured):
    """Fails if absent MAILERS falls back to the application's mail transport."""
    with override_settings(MAILERS=configured), pytest.raises(SystemExit) as refusal:
        certify_mail_isolation()
    assert str(refusal.value) == 'P4 isolation requires MAILERS with a default alias'


@pytest.mark.parametrize('configured', [
    {'default': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'}},
    {'default': {'BACKEND': LOCMEM_BACKEND}, 'notifications': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'}},
    {'default': {}},
    {'default': {'BACKEND': LOCMEM_BACKEND}, 'notifications': {'BACKEND': 'django.core.mail.backends.dummy.EmailBackend'}},
])
def test_isolation_rejects_non_memory_aliases(configured):
    """Fails if an implicit SMTP or secondary transport passes the preflight."""
    with override_settings(MAILERS=configured), pytest.raises(SystemExit) as refusal:
        certify_mail_isolation()
    assert str(refusal.value) == 'P4 isolation requires an explicit locmem backend for every MAILERS alias'


def test_isolation_rejects_effective_backend_drift(monkeypatch):
    """Fails if checking BACKEND text alone certifies a different runtime class."""
    configured = {'default': {'BACKEND': LOCMEM_BACKEND}}
    monkeypatch.setattr('django.core.mail.handler.import_string', lambda path: DummyEmailBackend)
    with override_settings(MAILERS=configured), pytest.raises(SystemExit) as refusal:
        certify_mail_isolation()
    assert str(refusal.value) == 'P4 isolation requires the effective locmem backend for every alias'


def test_isolation_redacts_invalid_mailer_options():
    """Fails if a backend construction error leaks configuration values."""
    configured = {'default': {'BACKEND': LOCMEM_BACKEND, 'OPTIONS': {'alias': 'private-option-value'}}}
    with override_settings(MAILERS=configured), pytest.raises(SystemExit) as refusal:
        certify_mail_isolation()
    assert str(refusal.value) == 'P4 isolation could not certify the effective mailers'


@pytest.mark.parametrize('alias', ['default', 'notifications'])
def test_certified_mail_is_delivered_to_memory(alias, django_mail_patch_dns):
    """Fails if a certified alias delivers a message outside the memory outbox."""
    configured = {'default': {'BACKEND': LOCMEM_BACKEND}, 'notifications': {'BACKEND': LOCMEM_BACKEND}}
    with override_settings(MAILERS=configured):
        certify_mail_isolation()
        message = mail.EmailMessage('Isolation probe', 'Memory only', 'sender@example.test', ['recipient@example.test'])
        result = message.send(using=alias)
    assert result == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].sent_using == alias
    assert mail.outbox[0].to == ['recipient@example.test']


def test_server_preflight_reports_isolated_mail():
    """Fails if the real startup cannot certify settings before serving fixtures."""
    server = Path(__file__).with_name('project_collaboration_browser_server.py')
    environment = {**os.environ, 'DJANGO_EMAIL_BACKEND': LOCMEM_BACKEND}
    result = subprocess.run([sys.executable, str(server), '--check-isolation'], env=environment,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        'settings_module': 'projectapp.settings_test',
        'database_engine': 'django.db.backends.sqlite3',
        'mailers': {'default': LOCMEM_BACKEND},
    }
