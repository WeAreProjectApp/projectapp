"""Fail closed before billing fixtures can use any external mail backend."""
import pytest
from django.conf import settings
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.locmem import EmailBackend


LOCMEM_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


@pytest.fixture(scope='session', autouse=True)
def billing_mailer_isolation(django_test_environment):
    from django.test import override_settings
    aliases = {alias: {'BACKEND': LOCMEM_BACKEND} for alias in settings.MAILERS}
    aliases['default'] = {'BACKEND': LOCMEM_BACKEND}
    with override_settings(MAILERS=aliases):
        assert_billing_mailers_isolated()
        yield


@pytest.fixture(scope='session')
def django_db_setup(billing_mailer_isolation, django_db_setup):
    return django_db_setup


def assert_billing_mailers_isolated():
    aliases = settings.MAILERS
    if 'default' not in aliases or any(
        config.get('BACKEND') != LOCMEM_BACKEND for config in aliases.values()
    ):
        raise ImproperlyConfigured('Billing tests require default and every MAILERS alias to use locmem.')
    if any(not isinstance(mail.mailers[alias], EmailBackend) for alias in aliases):
        raise ImproperlyConfigured('Billing tests refuse a mailer outside locmem.')
