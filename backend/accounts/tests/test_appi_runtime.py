"""Appi keeps private turns unavailable across authorization and receipt boundaries."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from accounts.models import Project, UserProfile
from accounts.models_ai import PlatformAIJob, PlatformAIQuotaReservation
from accounts.models_appi import AppiConversation, AppiTurn
from accounts.services import appi, appi_answers, appi_jev, appi_sources
from accounts.services.platform_ai import AIConflict

from .appi_test_support import conversation, ready_history, ready_turn, select_count
from .test_appi_jev import ProviderReply, routing_payload

pytest_plugins = ('accounts.tests.appi_test_support',)
pytestmark = pytest.mark.django_db


def other_client():
    """Persist a second eligible client without inheriting the owner identity."""
    actor = get_user_model().objects.create_user('appi-other', email='other@appi.test')
    UserProfile.objects.update_or_create(
        user=actor,
        defaults={'role': UserProfile.ROLE_CLIENT, 'chatbot_enabled': True},
    )
    return actor


def test_project_transfer_during_routing_fails_and_hides_the_turn(appi_context, monkeypatch):
    """Fails if a worker persists a ready answer after the project changes clients during provider I/O."""
    recipient = other_client()
    item = conversation(appi_context)
    turn = appi.submit(appi_context.actor, item.pk, {'question': 'Estado', 'request_id': uuid4()})

    def transfer_then_reply(*args, **kwargs):
        Project.objects.filter(pk=appi_context.project.pk).update(client=recipient)
        return ProviderReply(routing_payload())

    monkeypatch.setattr(appi_jev.requests, 'post', Mock(side_effect=transfer_then_reply))

    with pytest.raises(NotFound):
        appi.process(str(turn.pk))

    turn.refresh_from_db()
    assert turn.status == 'failed'
    with pytest.raises(NotFound):
        appi.detail(appi_context.actor, item.pk)
    with pytest.raises(NotFound):
        appi.detail(recipient, item.pk)


def test_staff_client_cannot_create_a_chatbot_conversation_for_another_clients_project(appi_context):
    """Fails if staff privileges let a client role bypass Appi's explicit project-owner check."""
    appi_context.actor.is_staff = True
    appi_context.actor.save(update_fields=['is_staff'])
    owner = other_client()
    foreign_project = Project.objects.create(client=owner, name='Owner-only project')

    with pytest.raises(NotFound, match='Proyecto no disponible'):
        appi.create_conversation(
            appi_context.actor,
            {'project_id': foreign_project.pk, 'language': 'es'},
        )

    assert AppiConversation.objects.filter(actor=appi_context.actor).count() == 0
    assert AppiTurn.objects.filter(actor=appi_context.actor).count() == 0
    assert PlatformAIQuotaReservation.objects.filter(actor=appi_context.actor).count() == 0


def test_chatbot_quota_rejects_a_session_only_identity(appi_context):
    """Fails if a Django panel session can read a JWT-only private chatbot endpoint."""
    session_client = APIClient()
    session_client.force_login(appi_context.actor)

    response = session_client.get('/api/platform/chatbot/quota/')

    assert response.status_code == 401
    assert 'no-store' in response['Cache-Control']


def test_authenticated_chatbot_detail_disables_intermediary_caching(appi_context):
    """Fails if a private chatbot response can be stored by a browser or intermediary cache."""
    item = conversation(appi_context)

    response = appi_context.api.get(f'/api/platform/chatbot/conversations/{item.pk}/')

    assert response.status_code == 200
    assert 'no-store' in response['Cache-Control']


def test_revoked_voice_guide_hides_a_ready_answer_that_has_an_action(appi_context):
    """Fails if a ready dictation guide keeps its actionable link after voice capability is revoked."""
    appi_context.config.voice_reporting_enabled = True
    appi_context.config.save(update_fields=['voice_reporting_enabled'])
    UserProfile.objects.filter(user=appi_context.actor).update(voice_reporting_enabled=True)
    item = conversation(appi_context)
    query = {'scenario': 'guide_voice_report', 'topic': 'general', 'explain': False}
    data = appi_sources.snapshot(appi_context.actor, appi_context.project.pk, query, 'es')
    answer = appi_answers.template_answer(query, data, 'es')
    turn = ready_turn(
        appi_context,
        item,
        query=query,
        dependencies=appi_answers.dependencies(query, data, 'es', config=appi_context.config),
        answer=answer,
        exact_key='voice-guide',
    )
    UserProfile.objects.filter(user=appi_context.actor).update(voice_reporting_enabled=False)

    serialized = appi.turn_data(appi_context.actor, turn)
    turn.refresh_from_db()

    assert answer['actions'][0]['target_key'] == 'project-bugs'
    assert serialized['status'] == 'unavailable'
    assert serialized['question'] == ''
    assert serialized['answer'] is None
    assert turn.answer == answer


def test_ready_unavailable_voice_guide_without_actions_stays_visible(appi_context):
    """Fails if hiding a revoked guide also erases a newly created clarification with no action link."""
    item = conversation(appi_context)
    query = {'scenario': 'guide_voice_report', 'topic': 'general', 'explain': False}
    data = appi_sources.snapshot(appi_context.actor, appi_context.project.pk, query, 'es')
    answer = appi_answers.template_answer(query, data, 'es')
    turn = ready_turn(
        appi_context,
        item,
        query=query,
        dependencies=appi_answers.dependencies(query, data, 'es', config=appi_context.config),
        answer=answer,
        exact_key='voice-guide-unavailable',
    )

    serialized = appi.turn_data(appi_context.actor, turn)

    assert answer['actions'] == []
    assert serialized['status'] == 'ready'
    assert serialized['question'] == 'Estado del proyecto'
    assert serialized['answer'] == answer


def test_history_page_keeps_select_count_constant_for_twenty_ready_turns(appi_context):
    """Fails if rendering twenty ready history rows reintroduces one ownership query per message."""
    one = conversation(appi_context)
    ready_history(appi_context, one, 1)
    twenty = conversation(appi_context)
    ready_history(appi_context, twenty, 20)

    with CaptureQueriesContext(connection) as one_queries:
        one_result = appi.detail(appi_context.actor, one.pk)
    with CaptureQueriesContext(connection) as twenty_queries:
        twenty_result = appi.detail(appi_context.actor, twenty.pk)

    assert len(one_result['messages']) == 1
    assert len(twenty_result['messages']) == 20
    assert select_count(twenty_queries) == select_count(one_queries)


def test_chat_audio_receipt_is_redeemed_once_by_its_original_request(appi_context):
    """Fails if retrying a dictated Appi question charges again or creates a second turn."""
    receipt = PlatformAIQuotaReservation.objects.create(
        actor=appi_context.actor, request_id=uuid4(), purpose='chatbot', fingerprint='voice-receipt', status='consumed',
    )
    recording = PlatformAIJob.objects.create(
        actor=appi_context.actor, project=appi_context.project, purpose='chatbot', operation='transcription',
        request_id=uuid4(), fingerprint='voice-receipt', status='ready', payload={'quota_id': str(receipt.pk)},
        expires_at=timezone.now() + timedelta(hours=1),
    )
    item = conversation(appi_context)
    values = {'question': 'Estado dictado', 'request_id': uuid4(), 'transcription_id': recording.pk}

    first = appi.submit(appi_context.actor, item.pk, values)
    repeated = appi.submit(appi_context.actor, item.pk, values)

    receipt.refresh_from_db()
    assert first.pk == repeated.pk
    assert first.quota_id == receipt.pk
    assert receipt.redemption_request_id == values['request_id']
    assert AppiTurn.objects.filter(actor=appi_context.actor, request_id=values['request_id']).count() == 1


def test_chat_audio_receipt_rejects_another_actor_before_turn_creation(appi_context):
    """Fails if a ready dictated receipt can be replayed by another client or project."""
    receipt = PlatformAIQuotaReservation.objects.create(
        actor=appi_context.actor, request_id=uuid4(), purpose='chatbot', fingerprint='private-voice', status='consumed',
    )
    recording = PlatformAIJob.objects.create(
        actor=appi_context.actor, project=appi_context.project, purpose='chatbot', operation='transcription',
        request_id=uuid4(), fingerprint='private-voice', status='ready', payload={'quota_id': str(receipt.pk)},
        expires_at=timezone.now() + timedelta(hours=1),
    )
    intruder = other_client()
    foreign_project = Project.objects.create(client=intruder, name='Other project')
    foreign_conversation = appi.create_conversation(intruder, {'project_id': foreign_project.pk, 'language': 'es'})

    with pytest.raises(AIConflict, match='transcripción no está disponible'):
        appi.submit(intruder, foreign_conversation.pk, {
            'question': 'Reproduce el dictado', 'request_id': uuid4(), 'transcription_id': recording.pk,
        })

    assert AppiTurn.objects.filter(actor=intruder).count() == 0
