"""Tutorial access uses JWT, feature capabilities and versioned resources."""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import UserProfile
from content.models import VideoResource
from content.services import platform_video_service as service

pytestmark = pytest.mark.django_db
CATALOG = '/api/platform/help/videos/'
RESOURCE = '/api/video-resources/admin/modules/platform-overview/es/'


@pytest.fixture
def tutorial_user(django_user_model, monkeypatch):
    user = django_user_model.objects.create_user('tutorial-client', password='test-password')
    UserProfile.objects.create(user=user, role='client', is_onboarded=True)
    monkeypatch.setattr(service, '_help_enabled', lambda actor: True)
    monkeypatch.setattr(service, '_ai_capabilities', lambda actor: {})
    return user


def jwt_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def test_client_receives_general_without_ai(tutorial_user):
    response = jwt_client(tutorial_user).get(CATALOG)
    assert response.status_code == 200
    assert response.data['videos'] == [{
        'topic': 'general', 'module': 'platform-overview', 'language': 'es',
        'resource': {'mode': 'default', 'video': None},
    }]
    assert response['Cache-Control'] == 'no-store'


@pytest.mark.parametrize(('chatbot', 'voice', 'topics'), [
    (False, False, ['general']),
    (True, False, ['general', 'chatbot']),
    (False, True, ['general', 'voice-reporting']),
    (True, True, ['general', 'chatbot', 'voice-reporting']),
])
def test_clips_follow_effective_capabilities(tutorial_user, monkeypatch, chatbot, voice, topics):
    monkeypatch.setattr(service, '_ai_capabilities', lambda actor: {
        'chatbot': {'enabled': True, 'available': chatbot, 'voice_available': False},
        'voice_reporting': {'enabled': True, 'available': voice},
    })
    response = jwt_client(tutorial_user).get(CATALOG)
    assert [item['topic'] for item in response.data['videos']] == topics


def test_disabled_help_returns_empty_catalog(tutorial_user, monkeypatch):
    monkeypatch.setattr(service, '_help_enabled', lambda actor: False)
    response = jwt_client(tutorial_user).get(CATALOG)
    assert response.data == {'enabled': False, 'videos': []}


def test_ai_error_keeps_general(tutorial_user, monkeypatch):
    def unavailable(actor):
        raise RuntimeError('AI configuration unavailable')
    monkeypatch.setattr(service, '_ai_capabilities', unavailable)
    response = jwt_client(tutorial_user).get(CATALOG)
    assert [item['topic'] for item in response.data['videos']] == ['general']


def test_removed_piece_stays_hidden(tutorial_user):
    VideoResource.objects.create(key='platform-overview:es', module='platform-overview', language='es', mode='none')
    response = jwt_client(tutorial_user).get(CATALOG)
    assert response.data['videos'] == []


def test_session_login_cannot_read_client_catalog(tutorial_user):
    client = APIClient()
    client.force_login(tutorial_user)
    assert client.get(CATALOG).status_code == 401


def test_verification_token_cannot_read_client_catalog(tutorial_user):
    token = AccessToken.for_user(tutorial_user)
    token['purpose'] = 'verify_email'
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    assert client.get(CATALOG).status_code == 401


def test_client_cannot_administer_tutorial(tutorial_user):
    assert jwt_client(tutorial_user).post(RESOURCE, {'action': 'remove', 'revision': 0}, format='json').status_code == 403


def test_panel_can_restore_removed_tutorial(tutorial_user):
    tutorial_user.is_staff = True
    tutorial_user.save(update_fields=['is_staff'])
    client = APIClient()
    client.force_login(tutorial_user)
    removed = client.post(RESOURCE, {'action': 'remove', 'revision': 0}, format='json')
    assert removed.status_code == 200
    assert removed.data['mode'] == 'none'
    restored = client.post(RESOURCE, {'action': 'restore-default', 'revision': 1}, format='json')
    assert restored.status_code == 200
    assert jwt_client(tutorial_user).get(CATALOG).data['videos'][0]['resource']['mode'] == 'default'


def test_stale_panel_revision_preserves_removal(tutorial_user):
    tutorial_user.is_staff = True
    tutorial_user.save(update_fields=['is_staff'])
    client = APIClient()
    client.force_login(tutorial_user)
    client.post(RESOURCE, {'action': 'remove', 'revision': 0}, format='json')
    response = client.post(RESOURCE, {'action': 'restore-default', 'revision': 0}, format='json')
    assert response.status_code == 409
    assert jwt_client(tutorial_user).get(CATALOG).data['videos'] == []
