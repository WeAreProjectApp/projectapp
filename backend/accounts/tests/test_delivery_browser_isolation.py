"""The real browser harness must never select a network mailer."""
import pytest
from django.core import mail

from accounts.tests.delivery_browser_server import assert_memory_mailers


def test_browser_mailer_resolves_to_memory(settings):
    """Fails if the effective default connection ignores the memory-only guard."""
    settings.MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
    mail.outbox = []

    assert_memory_mailers()
    mail.EmailMessage('Harness boundary', 'Memory only', to=['fixture@example.test']).send()

    assert [(message.subject, message.to) for message in mail.outbox] == [
        ('Harness boundary', ['fixture@example.test']),
    ]


@pytest.mark.parametrize('alias', ['default', 'secondary'])
def test_browser_mailer_rejects_a_network_alias(settings, alias):
    """Fails if default or secondary SMTP can reach fixtures or transport."""
    settings.MAILERS = {
        'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'},
        alias: {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'},
    }

    with pytest.raises(SystemExit, match='memory-only mailers'):
        assert_memory_mailers()
