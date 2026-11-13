"""Tutorial visibility exercises the real shared Help configuration."""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import UserProfile
from accounts.tests.feature_flag_helpers import set_global_flags, set_client_flags

pytestmark = pytest.mark.django_db


def tutorial_client(django_user_model, *, onboarded=True):
    user = django_user_model.objects.create_user('video-gates-client', password='test-password')
    UserProfile.objects.create(user=user, role='client', is_onboarded=onboarded)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return user, client


@pytest.mark.parametrize(('global_on', 'client_on', 'visible'), [
    (True, True, True), (False, True, True), (True, False, False), (False, False, False),
])
def test_shared_help_switches_govern_tutorials(django_user_model, global_on, client_on, visible):
    user, client = tutorial_client(django_user_model)
    set_global_flags({'platform.help_videos': global_on})
    set_client_flags(user, {'platform.help_videos': client_on})
    response = client.get('/api/platform/help/videos/')
    assert response.status_code == 200
    assert response.data['enabled'] is visible
    assert bool(response.data['videos']) is visible


def test_incomplete_onboarding_cannot_read_videos(django_user_model):
    user, client = tutorial_client(django_user_model, onboarded=False)
    response = client.get('/api/platform/help/videos/')
    assert response.status_code == 403
