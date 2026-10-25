"""Provider boundary contracts for the paid Platform AI operations."""

from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from requests.exceptions import Timeout

from accounts.models_ai import PlatformAICredential, PlatformAIUsage
from accounts.services import platform_ai_providers
from accounts.services.platform_ai import AIUnavailable
from accounts.services.platform_ai_cipher import encrypt

pytestmark = pytest.mark.django_db


class ProviderResponse:
    """Represent the status and JSON body returned by an external provider."""

    def __init__(self, status_code, payload):
        """Keep the provider status and payload for the HTTP boundary."""
        self.status_code = status_code
        self.payload = payload

    def json(self):
        """Return the fixed JSON payload supplied by the provider fixture."""
        return self.payload


@pytest.fixture
def ai_cipher(settings):
    """Provide a per-test encryption key for stored provider credentials."""
    settings.PLATFORM_AI_CIPHER_KEY = Fernet.generate_key().decode()


@pytest.fixture
def provider_keys(ai_cipher):
    """Store encrypted test credentials for each supported provider."""
    PlatformAICredential.objects.bulk_create([
        PlatformAICredential(provider='anthropic', encrypted_value=encrypt('anthropic-contract-key')),
        PlatformAICredential(provider='openai', encrypted_value=encrypt('openai-contract-key')),
        PlatformAICredential(provider='jev', encrypted_value=encrypt('jev-contract-key')),
    ])


@pytest.fixture
def staff_admin(admin_user):
    """Give the administrator fixture staff permission to test credentials."""
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    return admin_user


def test_anthropic_generation_records_cache_tokens_from_a_completed_response(client_user, project, provider_keys, monkeypatch):
    """Fails if a completed Haiku response loses its cache usage or billable result."""
    response = ProviderResponse(200, {
        'content': [{'type': 'text', 'text': '{"title":"Guardar"}'}],
        'stop_reason': 'end_turn',
        'usage': {
            'input_tokens': 1000,
            'output_tokens': 200,
            'cache_read_input_tokens': 500,
            'cache_creation_input_tokens': 300,
        },
    })
    posted = {}

    def post(*args, **kwargs):
        posted.update(kwargs)
        return response

    monkeypatch.setattr(platform_ai_providers.requests, 'post', post)

    result, usage_id = platform_ai_providers.generate_text(
        actor=client_user,
        project=project,
        purpose='voice_report',
        model='claude-haiku-5-5',
        instructions='Reglas estables:\n' + ('Describe solamente los hechos confirmados.\n' * 80),
        text='El botón Guardar no responde en la etapa de diseño.',
        schema={'type': 'object', 'properties': {'title': {'type': 'string'}}},
    )
    usage = PlatformAIUsage.objects.get(pk=usage_id)

    assert result == '{"title":"Guardar"}'
    assert usage.status == 'succeeded'
    assert (usage.input_tokens, usage.output_tokens) == (1000, 200)
    assert (usage.cache_read_tokens, usage.cache_write_tokens) == (500, 300)
    assert usage.estimated_cost == Decimal('0.00024250')
    assert posted['json']['system'][0]['cache_control'] == {'type': 'ephemeral', 'ttl': '5m'}


def test_luna_generation_uses_cached_input_pricing_from_a_completed_response(client_user, project, provider_keys, monkeypatch):
    """Fails if Luna bills cached prompt tokens as fresh input after a successful response."""
    response = ProviderResponse(200, {
        'status': 'completed',
        'output': [{'content': [
            {'type': 'output_text', 'text': '{"title":"Guardar"}'},
            {'type': 'refusal', 'text': 'ignored'},
        ]}],
        'usage': {'input_tokens': 1000, 'output_tokens': 200, 'input_tokens_details': {'cached_tokens': 800}},
    })
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: response)

    result, usage_id = platform_ai_providers.generate_text(
        actor=client_user,
        project=project,
        purpose='chatbot',
        model='gpt-6-luna',
        instructions='Responde solamente con hechos autorizados del proyecto.',
        text='¿Qué falta para aprobar la entrega?',
        schema={'type': 'object', 'properties': {'title': {'type': 'string'}}},
    )
    usage = PlatformAIUsage.objects.get(pk=usage_id)

    assert result == '{"title":"Guardar"}'
    assert usage.status == 'succeeded'
    assert usage.cache_read_tokens == 800
    assert usage.estimated_cost == Decimal('0.00012800')


def test_generation_marks_usage_failed_when_openai_returns_an_incomplete_response(client_user, project, provider_keys, monkeypatch):
    """Fails if an incomplete provider response is shown as an approved AI draft."""
    response = ProviderResponse(200, {
        'status': 'incomplete',
        'output': [{'content': [{'type': 'output_text', 'text': 'texto parcial'}]}],
        'usage': {'input_tokens': 100, 'output_tokens': 10},
    })
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: response)

    with pytest.raises(AIUnavailable):
        platform_ai_providers.generate_text(
            actor=client_user,
            project=project,
            purpose='chatbot',
            model='gpt-6-luna',
            instructions='Responde con información del proyecto.',
            text='Consulta de estado.',
        )

    usage = PlatformAIUsage.objects.get(operation='generation')
    assert usage.status == 'failed'
    assert usage.output_tokens == 0


def test_generation_rejects_anthropic_output_cut_at_the_token_limit(client_user, project, provider_keys, monkeypatch):
    """Fails if a token-truncated provider answer is treated as a complete report."""
    response = ProviderResponse(200, {
        'content': [{'type': 'text', 'text': 'descripción incompleta'}],
        'stop_reason': 'max_tokens',
        'usage': {'input_tokens': 100, 'output_tokens': 1000},
    })
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: response)

    with pytest.raises(AIUnavailable):
        platform_ai_providers.generate_text(
            actor=client_user,
            project=project,
            purpose='voice_report',
            model='claude-haiku-5-5',
            instructions='Escribe el reporte estructurado.',
            text='El formulario no guarda.',
        )

    assert PlatformAIUsage.objects.get(operation='generation').status == 'failed'


def test_generation_marks_usage_failed_after_a_provider_http_error(client_user, project, provider_keys, monkeypatch):
    """Fails if a rejected paid request remains recorded as a usable generation."""
    monkeypatch.setattr(
        platform_ai_providers.requests,
        'post',
        lambda *args, **kwargs: ProviderResponse(429, {'error': {'message': 'rate limited'}}),
    )

    with pytest.raises(AIUnavailable):
        platform_ai_providers.generate_text(
            actor=client_user,
            project=project,
            purpose='voice_report',
            model='claude-haiku-5-5',
            instructions='Describe únicamente la incidencia.',
            text='El botón de pago queda cargando.',
        )

    assert PlatformAIUsage.objects.get(operation='generation').status == 'failed'


def test_generation_rejects_oversized_input_before_creating_a_billable_usage_row(client_user, project, provider_keys):
    """Fails if an oversized prompt can start a paid provider request despite the safety limit."""
    with pytest.raises(AIUnavailable):
        platform_ai_providers.generate_text(
            actor=client_user,
            project=project,
            purpose='voice_report',
            model='claude-haiku-5-5',
            instructions='Reglas.',
            text='x' * 24000,
        )

    assert PlatformAIUsage.objects.count() == 0


def test_transcription_records_a_billed_trimmed_result(client_user, project, provider_keys, monkeypatch):
    """Fails if a valid transcription retains blank padding or loses the audio charge."""
    response = ProviderResponse(200, {'text': '  El botón Guardar no responde.  '})
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: response)

    text = platform_ai_providers.transcribe(
        actor=client_user,
        project=project,
        purpose='voice_report',
        audio=b'bounded-audio-bytes',
        seconds=30,
        filename='report.webm',
    )
    usage = PlatformAIUsage.objects.get(operation='transcription')

    assert text == 'El botón Guardar no responde.'
    assert usage.status == 'succeeded'
    assert usage.audio_seconds == 30
    assert usage.estimated_cost == Decimal('0.00225000')


def test_transcription_marks_usage_failed_when_the_provider_returns_blank_text(client_user, project, provider_keys, monkeypatch):
    """Fails if a blank transcription can create an empty report draft after charging audio."""
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: ProviderResponse(200, {'text': '   '}))

    with pytest.raises(AIUnavailable):
        platform_ai_providers.transcribe(
            actor=client_user,
            project=project,
            purpose='voice_report',
            audio=b'bounded-audio-bytes',
            seconds=12,
            filename='report.webm',
        )

    assert PlatformAIUsage.objects.get(operation='transcription').status == 'failed'


def test_transcription_marks_usage_failed_when_the_provider_returns_invalid_json(client_user, project, provider_keys, monkeypatch):
    """Fails if a malformed transcription response becomes a usable voice report."""
    response = ProviderResponse(200, None)
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: response)

    with pytest.raises(AIUnavailable):
        platform_ai_providers.transcribe(
            actor=client_user,
            project=project,
            purpose='voice_report',
            audio=b'bounded-audio-bytes',
            seconds=12,
            filename='report.webm',
        )

    assert PlatformAIUsage.objects.get(operation='transcription').status == 'failed'


@pytest.mark.parametrize(
    ('provider', 'status_code', 'expected_status'),
    [('anthropic', 200, 'valid'), ('openai', 401, 'failed'), ('jev', 200, 'valid')],
)
def test_credential_check_persists_the_provider_connection_result(staff_admin, provider_keys, monkeypatch, provider, status_code, expected_status):
    """Fails if the panel reports a credential test without persisting its provider status."""
    response = ProviderResponse(status_code, {})
    monkeypatch.setattr(platform_ai_providers.requests, 'get', lambda *args, **kwargs: response)
    monkeypatch.setattr(platform_ai_providers.requests, 'post', lambda *args, **kwargs: response)

    result = platform_ai_providers.test_credential(staff_admin, provider)
    credential = PlatformAICredential.objects.get(provider=provider)

    assert result['last_test_status'] == expected_status
    assert credential.last_test_status == expected_status
    assert credential.tested_at is not None


def test_credential_check_records_failed_status_after_a_network_exception(staff_admin, provider_keys, monkeypatch):
    """Fails if a timed-out key test remains valid in the administrator panel."""
    def timed_out_request(*args, **kwargs):
        raise Timeout()

    monkeypatch.setattr(platform_ai_providers.requests, 'get', timed_out_request)

    result = platform_ai_providers.test_credential(staff_admin, 'openai')

    assert result['last_test_status'] == 'failed'
    assert PlatformAICredential.objects.get(provider='openai').last_test_status == 'failed'
