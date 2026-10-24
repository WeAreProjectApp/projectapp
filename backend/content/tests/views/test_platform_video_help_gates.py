"""Tutorial visibility exercises the real shared Help configuration."""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import UserProfile
from accounts.models_platform_help import PlatformHelpSettings, ClientPlatformHelpSettings

pytestmark = pytest.mark.django_db


def tutorial_client(django_user_model, *, onboarded=True):
    user = django_user_model.objects.create_user('video-gates-client', password='test-password')
    UserProfile.objects.create(user=user, role='client', is_onboarded=onboarded)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return user, client


@pytest.mark.parametrize(('global_on', 'client_on', 'visible'), [
    (True, True, True), (False, True, False), (True, False, False), (False, False, False),
])
def test_shared_help_switches_govern_tutorials(django_user_model, global_on, client_on, visible):
    user, client = tutorial_client(django_user_model)
    PlatformHelpSettings.objects.create(pk=1, video_enabled=global_on)
    ClientPlatformHelpSettings.objects.create(user=user, video_enabled=client_on)
    response = client.get('/api/platform/help/videos/')
    assert response.status_code == 200
    assert response.data['enabled'] is visible
    assert bool(response.data['videos']) is visible


def test_incomplete_onboarding_cannot_read_videos(django_user_model):
    user, client = tutorial_client(django_user_model, onboarded=False)
    response = client.get('/api/platform/help/videos/')
    assert response.status_code == 403
