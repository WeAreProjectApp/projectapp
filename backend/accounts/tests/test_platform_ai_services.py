"""Behavioral coverage for Platform AI configuration and template controls."""

import pytest
from cryptography.fernet import Fernet
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import UserProfile
from accounts.models_ai import (
    PlatformAICredential,
    PlatformAISettings,
    PlatformAITemplate,
    PlatformAITemplateRevision,
)
from accounts.services import platform_ai
from accounts.services import platform_ai_templates
from accounts.services.platform_ai_cipher import decrypt


pytestmark = pytest.mark.django_db


@pytest.fixture
def ai_cipher(settings):
    settings.PLATFORM_AI_CIPHER_KEY = Fernet.generate_key().decode()


@pytest.fixture
def staff_admin(admin_user):
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    return admin_user


def configure_voice(client_user):
    profile = UserProfile.objects.get(user=client_user)
    profile.voice_reporting_enabled = True
    profile.chatbot_enabled = True
    profile.save(update_fields=['voice_reporting_enabled', 'chatbot_enabled'])
    PlatformAISettings.objects.update_or_create(
        pk=1,
        defaults={'voice_reporting_enabled': True, 'chatbot_enabled': True},
    )
    PlatformAICredential.objects.bulk_create([
        PlatformAICredential(provider='anthropic', encrypted_value='configured'),
        PlatformAICredential(provider='openai', encrypted_value='configured'),
        PlatformAICredential(provider='jev', encrypted_value='configured'),
    ])


def chat_template():
    template, created = PlatformAITemplate.objects.get_or_create(
        family='chatbot', scenario='project_status', language='es',
        defaults={'content': '{scope_label}\n\n{facts_text}'},
    )
    if created:
        PlatformAITemplateRevision.objects.create(
            template=template, version=1, content=template.content,
        )
    return template


def test_global_disable_overrides_an_enabled_client_with_configured_providers(client_user):
    """Fails if a client can use voice reports while the global switch is off."""
    configure_voice(client_user)
    PlatformAISettings.objects.filter(pk=1).update(voice_reporting_enabled=False)

    capabilities = platform_ai.ai_capabilities(client_user)

    assert capabilities['voice_reporting'] == {'enabled': False, 'available': False}


def test_feature_gate_reloads_client_flag_before_a_worker_uses_voice(client_user):
    """Fails if a queued worker trusts a stale enabled client profile."""
    configure_voice(client_user)
    _ = client_user.profile
    UserProfile.objects.filter(user=client_user).update(voice_reporting_enabled=False)

    with pytest.raises(PermissionDenied, match='apagada'):
        platform_ai.require_ai_feature(client_user, 'voice_reporting')


def test_admin_credential_projection_excludes_the_saved_secret(staff_admin, ai_cipher):
    """Fails if an administrator can retrieve a saved provider API key."""
    secret = 'anthropic-test-key-not-for-output'

    state = platform_ai.set_credential(
        staff_admin, 'anthropic', expected_version=0, api_key=secret,
    )
    projection = platform_ai.admin_settings(staff_admin)
    stored = PlatformAICredential.objects.get(provider='anthropic')

    assert state == {
        'configured': True, 'version': 1, 'last_test_status': '', 'tested_at': None,
    }
    assert stored.encrypted_value != secret
    assert decrypt(stored.encrypted_value) == secret
    assert projection['credentials']['anthropic']['configured'] is True
    assert secret not in str(projection)
    assert 'encrypted_value' not in str(projection)


def test_mcp_credential_preparation_removes_plaintext_before_confirmation(staff_admin, ai_cipher, monkeypatch):
    """Fails if a pending MCP confirmation retains the plaintext API key."""
    from content.mcp import platform_ai_tools

    secret = 'openai-test-key-not-for-confirmation'
    monkeypatch.setattr(platform_ai_tools, 'mcp_actor', lambda: staff_admin)

    prepared = platform_ai_tools._prepare_key({
        'provider': 'openai', 'api_key': secret, 'expected_version': 0,
    })

    assert prepared['provider'] == 'openai'
    assert prepared['expected_version'] == 0
    assert 'api_key' not in prepared
    assert decrypt(prepared['_encrypted_value']) == secret


def test_template_update_rejects_missing_required_slot_without_a_revision(staff_admin):
    """Fails if a chatbot template can drop facts_text and still be saved."""
    template = chat_template()

    with pytest.raises(ValidationError, match='marcadores'):
        platform_ai_templates.update_template(
            template.pk, staff_admin, '{scope_label}', template.version,
        )

    template.refresh_from_db()
    assert template.content == '{scope_label}\n\n{facts_text}'
    assert template.version == 1
    assert template.revisions.count() == 1


def test_template_restore_creates_a_new_version_without_rewriting_history(staff_admin):
    """Fails if restoring a template overwrites the version that was reviewed."""
    template = chat_template()
    revised = platform_ai_templates.update_template(
        template.pk, staff_admin, 'Estado: {scope_label}\n{facts_text}', template.version,
    )

    restored = platform_ai_templates.update_template(
        template.pk, staff_admin, '', revised['version'], restore_version=1,
    )
    versions = list(template.revisions.order_by('version').values_list('version', 'content'))

    assert restored['version'] == 3
    assert restored['content'] == '{scope_label}\n\n{facts_text}'
    assert versions == [
        (1, '{scope_label}\n\n{facts_text}'),
        (2, 'Estado: {scope_label}\n{facts_text}'),
        (3, '{scope_label}\n\n{facts_text}'),
    ]


@pytest.mark.parametrize('reservation_count', [0, 20])
def test_capabilities_query_budget_is_independent_of_consumption(client_user, django_assert_num_queries, reservation_count):
    """Falla si consultar el marcador carga reservas una por una o repite lecturas de perfil."""
    from accounts.models_ai import PlatformAIQuotaReservation
    configure_voice(client_user)
    PlatformAIQuotaReservation.objects.bulk_create(make_reservations(client_user, reservation_count))

    with django_assert_num_queries(4):
        capabilities = platform_ai.ai_capabilities(client_user)

    assert capabilities['quota']['used'] == reservation_count
    assert capabilities['quota']['remaining'] == 20 - reservation_count


def make_reservations(actor, count):
    from uuid import UUID
    from accounts.models_ai import PlatformAIQuotaReservation
    return [PlatformAIQuotaReservation(actor=actor, request_id=UUID(int=index + 1),
            purpose='chatbot', fingerprint=str(index), status='consumed') for index in range(count)]


def test_invalidating_voice_preserves_the_chatbot_cache_version(staff_admin):
    """Falla si vaciar la caché de voz obliga a pagar de nuevo respuestas del chatbot."""
    chat_before = platform_ai.cache_version('chatbot')
    voice_before = platform_ai.cache_version('voice_report')

    platform_ai.invalidate_cache(staff_admin, 'voice_report')

    assert platform_ai.cache_version('chatbot') == chat_before
    assert platform_ai.cache_version('voice_report') != voice_before


def test_invalidating_all_refreshes_each_function_cache(staff_admin):
    """Falla si vaciar ambas cachés deja reutilizable una respuesta anterior."""
    chat_before = platform_ai.cache_version('chatbot')
    voice_before = platform_ai.cache_version('voice_report')

    platform_ai.invalidate_cache(staff_admin, 'all')

    assert platform_ai.cache_version('chatbot') != chat_before
    assert platform_ai.cache_version('voice_report') != voice_before
