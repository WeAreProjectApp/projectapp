"""The billing harness uses real in-memory mailers and rejects external aliases."""
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.test import override_settings

from accounts.tests.billing.mail_safety import LOCMEM_BACKEND, assert_billing_mailers_isolated


def test_billing_mail_is_retained_in_memory(mailoutbox):
    message = EmailMessage('Billing harness', 'Only a local test.', to=['billing-fixture@example.test'])

    delivered = message.send()

    assert delivered == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['billing-fixture@example.test']


def test_billing_mail_guard_rejects_an_external_alias(mailoutbox):
    with override_settings(MAILERS={
        'default': {'BACKEND': LOCMEM_BACKEND},
        'secondary': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend'},
    }):
        with pytest.raises(ImproperlyConfigured, match='every MAILERS alias to use locmem'):
            assert_billing_mailers_isolated()

    assert mailoutbox == []
