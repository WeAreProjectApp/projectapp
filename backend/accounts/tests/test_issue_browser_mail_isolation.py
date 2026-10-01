"""The real browser fixture cannot fall back to an external mail alias."""
import pytest
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMessage
from django.test import override_settings

from accounts.tests.issue_browser_server import assert_memory_mailers, memory_mailers


def test_fixture_mailers_replace_every_effective_alias(mailoutbox):
    """Fails if an additional alias retains SMTP while default alone uses memory."""
    external = {'default': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'},
                'transactional': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
                                  'OPTIONS': {'host': 'must-not-connect.example.test'}}}
    with override_settings(MAILERS=external):
        isolated = memory_mailers(settings)

    with override_settings(MAILERS=isolated):
        assert_memory_mailers()
        EmailMessage('Default sink', 'Private fixture body.', to=['client@example.test']).send()
        EmailMessage('Alias sink', 'Private fixture body.', to=['client@example.test']).send(using='transactional')

    assert [message.subject for message in mailoutbox] == ['Default sink', 'Alias sink']
    assert isolated['transactional'] == {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}


@pytest.mark.parametrize('configured', [
    {'default': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'}},
    {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'},
     'extra': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'}},
    {'extra': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
])
def test_fixture_rejects_an_unisolated_mailer_before_sending(configured, mailoutbox):
    """Fails if a malformed or remote effective mailer passes the fixture boundary."""
    with override_settings(MAILERS=configured), pytest.raises(SystemExit, match='memory-only'):
        assert_memory_mailers()

    assert mailoutbox == []
