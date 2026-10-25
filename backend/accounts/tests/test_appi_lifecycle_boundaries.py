"""Boundary failures preserve Appi's private, quota-backed lifecycle."""
from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests
from django.utils import timezone

from accounts.models_ai import PlatformAIQuotaReservation, PlatformAIUsage
from accounts.models_appi import AppiConversation, AppiTurn
from accounts.services import appi, appi_jev
from accounts.services.platform_ai import AIConflict, AIUnavailable

from .appi_test_support import conversation
from .test_appi_jev import ProviderReply, routing_payload

pytest_plugins = ('accounts.tests.appi_test_support',)
pytestmark = pytest.mark.django_db


def entity_payload(choice):
    """Return the one closed entity answer accepted by Jev's boundary."""
    options = ('all', 'uncertain', 'bug-7')
    return {
        'answers': {
            'entity': {
                'type': 'choice',
                'choice': choice,
                'confidence': 0.99,
                'probabilities': {name: int(name == choice) for name in options},
            },
        },
        'usage': {'input_tokens': 7},
    }


@pytest.mark.parametrize(('payload', 'field'), [
    ({'question': 'Estado\x01', 'request_id': str(uuid4())}, 'question'),
    ({'question': 'Estado', 'request_id': 'no-es-un-uuid'}, 'request_id'),
])
def test_invalid_message_payload_preserves_private_state(appi_context, payload, field):
    """Fails if malformed chatbot input creates a turn or a billable reservation."""
    item = conversation(appi_context)

    response = appi_context.api.post(
        f'/api/platform/chatbot/conversations/{item.pk}/messages/', payload, format='json',
    )

    assert response.status_code == 400
    assert field in response.json()
    assert 'no-store' in response['Cache-Control']
    assert AppiConversation.objects.filter(actor=appi_context.actor).count() == 1
    assert AppiTurn.objects.filter(actor=appi_context.actor).count() == 0
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor).count() == 0


def test_invalid_history_cursor_preserves_private_state(appi_context):
    """Fails if an invalid history cursor creates a private Appi record."""
    item = conversation(appi_context)

    response = appi_context.api.get(f'/api/platform/chatbot/conversations/{item.pk}/?before=no-es-un-uuid')

    assert response.status_code == 400
    assert 'before' in response.json()
    assert 'no-store' in response['Cache-Control']
    assert AppiConversation.objects.filter(actor=appi_context.actor).count() == 1
    assert AppiTurn.objects.filter(actor=appi_context.actor).count() == 0
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor).count() == 0


def test_unknown_conversation_message_returns_private_not_found(appi_context):
    """Fails if a guessed conversation UUID creates state or produces a cacheable response."""
    response = appi_context.api.post(
        f'/api/platform/chatbot/conversations/{uuid4()}/messages/',
        {'question': 'Estado', 'request_id': str(uuid4())},
        format='json',
    )

    assert response.status_code == 404
    assert 'no-store' in response['Cache-Control']
    assert AppiConversation.objects.filter(actor=appi_context.actor).count() == 0
    assert AppiTurn.objects.filter(actor=appi_context.actor).count() == 0
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor).count() == 0


def test_pending_turn_rejects_another_logical_request(appi_context):
    """Fails if a client can reserve a second quota while its first Appi turn is pending."""
    item = conversation(appi_context)
    first = appi.submit(appi_context.actor, item.pk, {'question': 'Estado', 'request_id': uuid4()})

    with pytest.raises(AIConflict, match='Espera a que termine'):
        appi.submit(appi_context.actor, item.pk, {'question': 'Entregables', 'request_id': uuid4()})

    assert AppiTurn.objects.filter(actor=appi_context.actor).count() == 1
    assert AppiTurn.objects.get(pk=first.pk).status == 'pending'
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor, status='reserved').count() == 1


def test_request_identifier_rejects_different_question(appi_context):
    """Fails if one request identifier can be reused to create a different private query."""
    item = conversation(appi_context)
    request_id = uuid4()
    first = appi.submit(appi_context.actor, item.pk, {'question': 'Estado', 'request_id': request_id})

    with pytest.raises(AIConflict, match='identificador ya pertenece'):
        appi.submit(appi_context.actor, item.pk, {'question': 'Entregables', 'request_id': request_id})

    assert AppiTurn.objects.filter(actor=appi_context.actor, request_id=request_id).count() == 1
    assert AppiTurn.objects.get(pk=first.pk).question == 'Estado'
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor).count() == 1


def test_cleanup_refunds_an_abandoned_pending_turn(appi_context):
    """Fails if cleanup leaves an abandoned Appi turn billable after marking it failed."""
    item = conversation(appi_context)
    turn = appi.submit(appi_context.actor, item.pk, {'question': 'Estado', 'request_id': uuid4()})
    AppiTurn.objects.filter(pk=turn.pk).update(created_at=timezone.now() - timedelta(minutes=6))

    appi.cleanup()

    turn.refresh_from_db()
    receipt = PlatformAIQuotaReservation.objects.get(pk=turn.quota_id)
    assert turn.status == 'failed'
    assert turn.query == {}
    assert receipt.status == 'refunded'


def test_non_successful_jev_response_fails_the_turn_without_charging_quota(appi_context, monkeypatch):
    """Fails if a rejected Jev HTTP response leaves a chatbot request charged or pending."""
    reply = ProviderReply(routing_payload())
    reply.status_code = 503
    monkeypatch.setattr(appi_jev.requests, 'post', Mock(return_value=reply))
    item = conversation(appi_context)
    turn = appi.submit(appi_context.actor, item.pk, {'question': 'Estado', 'request_id': uuid4()})

    with pytest.raises(AIUnavailable):
        appi.process(str(turn.pk))

    turn.refresh_from_db()
    routing = PlatformAIUsage.objects.get(actor=appi_context.actor, operation='routing')
    receipt = PlatformAIQuotaReservation.objects.get(pk=turn.quota_id)
    assert turn.status == 'failed'
    assert routing.status == 'failed'
    assert receipt.status == 'refunded'


def test_jev_request_exception_records_failed_routing_usage(appi_context, monkeypatch):
    """Fails if a transport outage leaves Jev routing usage marked as successful or pending."""
    monkeypatch.setattr(appi_jev.requests, 'post', Mock(side_effect=requests.RequestException('offline')))

    with pytest.raises(AIUnavailable):
        appi_jev.classify(appi_context.actor, appi_context.project, 'Estado', {})

    routing = PlatformAIUsage.objects.get(actor=appi_context.actor, operation='routing')
    assert routing.status == 'failed'
    assert routing.latency_ms >= 0


@pytest.mark.parametrize(('choice', 'expected'), [
    ('all', 'all'),
    ('uncertain', 'uncertain'),
    ('bug-7', 'bug-7'),
])
def test_entity_selection_returns_only_the_closed_provider_choice(appi_context, monkeypatch, choice, expected):
    """Fails if Appi expands Jev entity selection beyond the authorized candidate set."""
    monkeypatch.setattr(appi_jev.requests, 'post', Mock(return_value=ProviderReply(entity_payload(choice))))

    selected = appi_jev.select_entity(
        appi_context.actor,
        appi_context.project,
        'Estado del reporte',
        [{'id': 'bug-7', 'title': 'Checkout'}],
    )

    assert selected == expected


def test_jev_request_redacts_secret_before_sending_state(appi_context, monkeypatch):
    """Fails if an API-looking secret from a client question is sent to the Jev provider."""
    provider = Mock(return_value=ProviderReply(routing_payload()))
    monkeypatch.setattr(appi_jev.requests, 'post', provider)

    result = appi_jev.classify(appi_context.actor, appi_context.project, 'Revisa sk-abcdefghijklmnop', {})

    assert result['scenario'] == 'project_status'
    assert provider.call_args.kwargs['json']['state']['message'] == 'Revisa [secret omitted]'
