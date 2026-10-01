"""Fail closed before billing fixtures can use any external mail backend."""
from django.conf import settings
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.locmem import EmailBackend


LOCMEM_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


def assert_billing_mailers_isolated():
    aliases = settings.MAILERS
    if 'default' not in aliases or any(
        config.get('BACKEND') != LOCMEM_BACKEND for config in aliases.values()
    ):
        raise ImproperlyConfigured('Billing tests require default and every MAILERS alias to use locmem.')
    if any(not isinstance(mail.mailers[alias], EmailBackend) for alias in aliases):
        raise ImproperlyConfigured('Billing tests refuse a mailer outside locmem.')
