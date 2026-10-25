"""Panel contracts for the versioned Platform AI administration controls."""
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.test import RequestFactory
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.models_ai import (
    PlatformAICredential,
    PlatformAIEvent,
    PlatformAISettings,
    PlatformAIUsage,
)
from accounts.services.platform_ai_cipher import encrypt

pytestmark = pytest.mark.django_db


SETTINGS_URL = '/api/platform/ai/admin/settings/'


@pytest.fixture
def panel_admin(admin_user):
    """Create an administrator allowed to change Platform AI settings."""
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    return admin_user


@pytest.fixture
def panel_client(panel_admin):
    """Build a panel session with a valid CSRF token."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(panel_admin)
    request = RequestFactory().get('/')
    csrf_token = get_token(request)
    client.cookies['csrftoken'] = request.META['CSRF_COOKIE']
    return client, {'HTTP_X_CSRFTOKEN': csrf_token}


def configure_settings(**overrides):
    """Persist the global configuration used by an administration contract."""
    defaults = {
        'chatbot_enabled': True,
        'voice_reporting_enabled': True,
        'ai_request_limit': 20,
        'ai_window_minutes': 300,
        'cache_epoch': 1,
        'version': 1,
    }
    defaults.update(overrides)
    return PlatformAISettings.objects.update_or_create(pk=1, defaults=defaults)[0]


def test_settings_patch_rejects_session_without_csrf_before_changing_configuration(panel_admin):
    """Fails if a forged panel session can enable voice reporting without CSRF."""
    config = configure_settings(voice_reporting_enabled=False)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(panel_admin)

    response = client.patch(
        SETTINGS_URL,
        {'expected_version': config.version, 'voice_reporting_enabled': True}, format='json',
    )

    config.refresh_from_db()
    assert response.status_code == 403
    assert config.voice_reporting_enabled is False
    assert PlatformAIEvent.objects.filter(action='settings.update').count() == 0


def test_settings_patch_versions_configuration_with_session_csrf(panel_client):
    """Fails if an authorized panel save does not version the global configuration."""
    client, headers = panel_client
    config = configure_settings(voice_reporting_enabled=False)

    response = client.patch(
        SETTINGS_URL,
        {
            'expected_version': config.version,
            'voice_reporting_enabled': True,
            'ai_request_limit': 9,
        },
        format='json',
        **headers,
    )

    config.refresh_from_db()
    assert response.status_code == 200, response.data
    assert response['Cache-Control'] == 'no-store'
    assert response.data['version'] == 2
    assert config.voice_reporting_enabled is True
    assert config.ai_request_limit == 9
    assert config.version == 2
    assert PlatformAIEvent.objects.get(action='settings.update').metadata == {
        'fields': ['ai_request_limit', 'voice_reporting_enabled'], 'version': 2,
    }


def test_settings_patch_rejects_stale_version_without_writing_an_event(panel_client):
    """Fails if an outdated settings form overwrites a newer panel configuration."""
    client, headers = panel_client
    config = configure_settings(version=2, ai_request_limit=17)

    response = client.patch(
        SETTINGS_URL,
        {'expected_version': 1, 'ai_request_limit': 3}, format='json', **headers,
    )

    config.refresh_from_db()
    assert response.status_code == 409
    assert config.ai_request_limit == 17
    assert config.version == 2
    assert PlatformAIEvent.objects.filter(action='settings.update').count() == 0


def test_client_override_patch_saves_the_complete_quota_pair(panel_client, client_user):
    """Fails if a panel client override loses either quota setting during persistence."""
    client, headers = panel_client
    profile = UserProfile.objects.get(user=client_user)

    response = client.patch(
        f'/api/platform/ai/admin/clients/{client_user.pk}/',
        {
            'expected_version': profile.updated_at.isoformat(),
            'voice_reporting_enabled': True,
            'ai_request_limit': 5,
            'ai_window_minutes': 90,
        },
        format='json',
        **headers,
    )

    profile.refresh_from_db()
    assert response.status_code == 200, response.data
    assert profile.voice_reporting_enabled is True
    assert profile.ai_request_limit == 5
    assert profile.ai_window_minutes == 90
    assert PlatformAIEvent.objects.get(action='client.update').metadata['fields'] == [
        'ai_request_limit', 'ai_window_minutes', 'voice_reporting_enabled',
    ]


def test_client_override_rejects_an_incomplete_quota_pair(panel_client, client_user):
    """Fails if a client can inherit half a quota window after a rejected panel save."""
    client, headers = panel_client
    profile = UserProfile.objects.get(user=client_user)
    profile.ai_request_limit = None
    profile.ai_window_minutes = None
    profile.save(update_fields=['ai_request_limit', 'ai_window_minutes', 'updated_at'])
    profile.refresh_from_db()
    previous_voice_flag = profile.voice_reporting_enabled

    response = client.patch(
        f'/api/platform/ai/admin/clients/{client_user.pk}/',
        {
            'expected_version': profile.updated_at.isoformat(),
            'voice_reporting_enabled': not previous_voice_flag,
            'ai_request_limit': 4,
        },
        format='json',
        **headers,
    )

    profile.refresh_from_db()
    assert response.status_code == 400
    assert profile.voice_reporting_enabled is previous_voice_flag
    assert profile.ai_request_limit is None
    assert profile.ai_window_minutes is None
    assert PlatformAIEvent.objects.filter(action='client.update').count() == 0


def test_client_override_rejects_a_stale_profile_version(panel_client, client_user):
    """Fails if two panel edits can silently replace a client's feature flags."""
    client, headers = panel_client
    profile = UserProfile.objects.get(user=client_user)
    profile.chatbot_enabled = True
    profile.save(update_fields=['chatbot_enabled', 'updated_at'])

    response = client.patch(
        f'/api/platform/ai/admin/clients/{client_user.pk}/',
        {
            'expected_version': '2000-01-01T00:00:00+00:00',
            'chatbot_enabled': False,
        },
        format='json',
        **headers,
    )

    profile.refresh_from_db()
    assert response.status_code == 409
    assert profile.chatbot_enabled is True
    assert PlatformAIEvent.objects.filter(action='client.update').count() == 0


def test_credential_delete_clears_the_provider_secret(panel_client):
    """Fails if deleting a provider key leaves encrypted credentials usable on the server."""
    client, headers = panel_client
    PlatformAICredential.objects.create(
        provider='openai', encrypted_value='former-encrypted-key', version=4,
    )

    response = client.delete(
        '/api/platform/ai/admin/credentials/openai/',
        {'expected_version': 4},
        format='json',
        **headers,
    )

    credential = PlatformAICredential.objects.get(provider='openai')
    assert response.status_code == 200, response.data
    assert response.json()['configured'] is False
    assert response.json()['version'] == 5
    assert credential.encrypted_value == ''
    assert credential.version == 5
    assert PlatformAIEvent.objects.get(action='credential.delete').target == 'openai'


def test_credential_test_records_the_provider_connection_result(panel_client, settings, monkeypatch):
    """Fails if a successful provider check is not recorded for the panel operator."""
    client, headers = panel_client
    settings.PLATFORM_AI_CIPHER_KEY = Fernet.generate_key().decode()
    PlatformAICredential.objects.create(
        provider='openai', encrypted_value=encrypt('openai-test-key-12345'), version=1,
    )

    class ProviderResponse:
        status_code = 204

    monkeypatch.setattr(
        'accounts.services.platform_ai_providers.requests.get',
        lambda *args, **kwargs: ProviderResponse(),
    )
    response = client.post(
        '/api/platform/ai/admin/credentials/openai/test/', {}, format='json', **headers,
    )

    credential = PlatformAICredential.objects.get(provider='openai')
    assert response.status_code == 200, response.data
    assert response.json()['last_test_status'] == 'valid'
    assert credential.last_test_status == 'valid'
    assert credential.tested_at is not None


@freeze_time('2026-10-24 15:00:00')
def test_usage_endpoint_excludes_records_from_a_previous_month(panel_client, client_user, project):
    """Fails if dashboard cost totals include an AI request outside the current month."""
    client, _ = panel_client
    PlatformAIUsage.objects.create(
        actor=client_user, project=project, purpose='voice_report', operation='generation',
        provider='anthropic', model='claude-haiku-5-5', status='succeeded', input_tokens=15,
        output_tokens=4, cache_read_tokens=3, cache_write_tokens=2,
    )
    previous = PlatformAIUsage.objects.create(
        actor=client_user, project=project, purpose='voice_report', operation='generation',
        provider='anthropic', model='claude-haiku-5-5', status='succeeded', input_tokens=100,
    )
    PlatformAIUsage.objects.filter(pk=previous.pk).update(created_at=timezone.now() - timedelta(days=31))

    response = client.get('/api/platform/ai/admin/usage/')

    result = response.json()
    assert (response.status_code, response['Cache-Control'], result['month']) == (200, 'no-store', '2026-10')
    assert len(result['groups']) == 1
    assert tuple(result['groups'][0][field] for field in (
        'requests', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens',
    )) == (1, 15, 4, 3, 2)


def test_cache_invalidation_advances_the_global_epoch(panel_client):
    """Fails if clearing every AI cache leaves prior results valid for the next request."""
    client, headers = panel_client
    config = configure_settings()

    response = client.post(
        '/api/platform/ai/admin/cache/invalidate/', {'function': 'all'}, format='json', **headers,
    )

    config.refresh_from_db()
    assert response.status_code == 200, response.data
    assert response.json() == {'invalidated': True, 'cache_epoch': 2}
    assert config.cache_epoch == 2
    assert config.version == 2
    assert PlatformAIEvent.objects.get(action='cache.invalidate').target == 'all'


def test_credential_delete_requires_the_current_version(panel_client):
    """Fails if an incomplete delete request can erase a provider credential."""
    client, headers = panel_client
    PlatformAICredential.objects.create(
        provider='anthropic', encrypted_value='former-encrypted-key', version=3,
    )

    response = client.delete(
        '/api/platform/ai/admin/credentials/anthropic/', {}, format='json', **headers,
    )

    credential = PlatformAICredential.objects.get(provider='anthropic')
    assert response.status_code == 400
    assert credential.encrypted_value == 'former-encrypted-key'
    assert credential.version == 3
    assert PlatformAIEvent.objects.filter(action='credential.delete').count() == 0


def test_cache_invalidation_rejects_an_unknown_function(panel_client):
    """Fails if a misspelled cache target can create an ambiguous invalidation event."""
    client, headers = panel_client
    config = configure_settings()

    response = client.post(
        '/api/platform/ai/admin/cache/invalidate/', {'function': 'everything'}, format='json', **headers,
    )

    config.refresh_from_db()
    assert response.status_code == 400
    assert config.cache_epoch == 1
    assert config.version == 1
    assert PlatformAIEvent.objects.filter(action='cache.invalidate').count() == 0


def test_clients_search_returns_matching_clients_without_panel_administrators(panel_client, client_user, admin_user):
    """Fails if the AI client switcher exposes panel administrators or unrelated clients."""
    client, _ = panel_client
    UserProfile.objects.filter(user=admin_user).update(company_name='ClientCo')
    other = get_user_model().objects.create_user(
        username='other-ai-client', email='other-ai-client@test.com', password='pass12345',
    )
    UserProfile.objects.create(
        user=other, role=UserProfile.ROLE_CLIENT, company_name='Other company', created_by=admin_user,
    )

    response = client.get('/api/platform/ai/admin/clients/?search=ClientCo')

    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert response.json()['count'] == 1
    assert response.json()['page'] == 1
    assert [row['user_id'] for row in response.json()['results']] == [client_user.pk]
    assert admin_user.pk not in [row['user_id'] for row in response.json()['results']]


@pytest.mark.parametrize('page', ['not-a-page', '0'])
def test_clients_list_rejects_an_invalid_page(panel_client, page):
    """Fails if malformed pagination can make the panel client configuration ambiguous."""
    client, _ = panel_client

    response = client.get(f'/api/platform/ai/admin/clients/?page={page}')

    assert response.status_code == 400
    assert response['Cache-Control'] == 'no-store'


def test_credential_put_with_session_csrf_encrypts_the_secret(panel_client, settings):
    """Fails if a panel credential save stores plaintext or omits its audit record."""
    client, headers = panel_client
    cipher_key = Fernet.generate_key()
    settings.PLATFORM_AI_CIPHER_KEY = cipher_key.decode()
    secret = 'jev-panel-key-not-for-response'

    response = client.put(
        '/api/platform/ai/admin/credentials/jev/',
        {'api_key': secret, 'expected_version': 0}, format='json', **headers,
    )

    credential = PlatformAICredential.objects.get(provider='jev')
    audit = PlatformAIEvent.objects.get(action='credential.set')
    assert (response.status_code, response['Cache-Control'], response.json()['configured']) == (200, 'no-store', True)
    assert response.json()['version'] == 1
    assert credential.encrypted_value != secret
    assert Fernet(cipher_key).decrypt(credential.encrypted_value.encode()).decode() == secret
    assert secret not in response.content.decode()
    assert (audit.target, audit.metadata) == ('jev', {'version': 1})


def test_credential_put_without_a_cipher_key_does_not_persist_a_secret(panel_client, settings, monkeypatch, tmp_path):
    """Fails if an unavailable server cipher accepts a provider key or writes an audit event."""
    client, headers = panel_client
    settings.PLATFORM_AI_CIPHER_KEY = ''
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY', '')
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY_FILE', str(tmp_path / 'missing-platform-ai.key'))

    response = client.put(
        '/api/platform/ai/admin/credentials/anthropic/',
        {'api_key': 'anthropic-key-without-cipher', 'expected_version': 0}, format='json', **headers,
    )

    assert (response.status_code, response['Cache-Control']) == (503, 'no-store')
    assert not PlatformAICredential.objects.filter(provider='anthropic').exists()
    assert PlatformAIEvent.objects.filter(action='credential.set').count() == 0


@pytest.mark.parametrize(('suffix', 'method'), [
    ('', 'get'),
    ('versions/', 'get'),
    ('preview/', 'post'),
])
def test_missing_template_routes_return_not_found(panel_client, suffix, method):
    """Fails if any template review route turns an unknown identifier into editable content."""
    client, headers = panel_client

    response = getattr(client, method)(
        f'/api/platform/ai/admin/templates/999999/{suffix}', {}, format='json', **headers,
    )

    assert response.status_code == 404
    assert response['Cache-Control'] == 'no-store'
