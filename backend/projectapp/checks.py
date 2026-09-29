"""Deployment checks for the authentication boundary."""
from django.core.checks import Error, Tags, register

from accounts.services.credential_cipher import cipher_configuration_errors
from projectapp.recaptcha import captcha_configuration_errors, captcha_enabled


@register(Tags.security, deploy=True)
def check_login_captcha(app_configs, **kwargs):
    if not captcha_enabled():
        return []
    return [Error(message, id='projectapp.E001') for message in captcha_configuration_errors()]


@register(Tags.security, deploy=True)
def check_project_access_cipher(app_configs, **kwargs):
    return [Error(message, id='projectapp.E002') for message in cipher_configuration_errors()]
