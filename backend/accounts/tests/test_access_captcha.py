"""CAPTCHA remains mandatory at each alternative-login challenge boundary."""

import pytest
from rest_framework.test import APIClient

from accounts.access_models import LoginChallenge

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('surface', ['panel', 'platform'])
@pytest.mark.parametrize('operation', ['email-request', 'google-challenge'])
def test_alternative_challenge_requires_captcha(settings, surface, operation):
    """Fails if a direct API caller can issue an access challenge without CAPTCHA."""
    settings.RECAPTCHA_ENABLED = True
    settings.RECAPTCHA_SITE_KEY = 'test-site-key'
    settings.RECAPTCHA_SECRET_KEY = 'test-only-secret'
    settings.RECAPTCHA_ALLOWED_HOSTNAMES = ['testserver']

    response = APIClient().post(
        f'/api/auth/{surface}/{operation}/',
        {'email': 'existing@example.test'},
        format='json',
    )

    assert response.status_code == 400
    assert response.json()['code'] == 'captcha_required'
    assert not LoginChallenge.objects.exists()
