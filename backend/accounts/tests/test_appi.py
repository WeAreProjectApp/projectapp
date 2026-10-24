"""Client-visible answers, isolation, freshness and the shared logical quota."""
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import NotFound, Throttled
from rest_framework.test import APIClient

from accounts.models import BugReport, Project, ProjectContract, UserProfile
from accounts.models_ai import PlatformAICredential, PlatformAISettings, PlatformAITemplate
from accounts.models_appi import AppiConversation, AppiTurn
from accounts.services import appi, appi_answers, appi_jev
from accounts.services.platform_ai import AIUnavailable
from accounts.services.platform_ai_cipher import encrypt
from accounts.services.platform_ai_quota import consume, reserve, snapshot
from content.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_context(settings, monkeypatch):
    settings.PLATFORM_AI_CIPHER_KEY = Fernet.generate_key()
    actor = get_user_model().objects.create_user('appi-client', email='appi@example.test')
    UserProfile.objects.update_or_create(user=actor, defaults={'role': 'client', 'chatbot_enabled': True})
    config, _ = PlatformAISettings.objects.update_or_create(pk=1, defaults={'chatbot_enabled': True})
    PlatformAICredential.objects.create(provider='jev', encrypted_value=encrypt('test-jev-key'))
    PlatformAICredential.objects.create(provider='anthropic', encrypted_value=encrypt('test-anthropic-key'))
    project = Project.objects.create(client=actor, name='Client project', progress=25)
    router = Mock(return_value={'scenario': 'project_status', 'topic': 'general', 'explain': False})
    monkeypatch.setattr(appi_jev, 'classify', router)
    monkeypatch.setattr(appi_jev, 'select_entity', Mock(return_value='all'))
    writer = Mock(side_effect=AssertionError('A template response must not call the writer'))
    monkeypatch.setattr(appi_answers, 'generate_text', writer)
    monkeypatch.setattr('accounts.tasks_appi.process_appi_turn', Mock())
    api = APIClient()
    api.force_authenticate(actor)
    return SimpleNamespace(actor=actor, project=project, router=router, writer=writer, api=api, config=config)


@pytest.fixture
def ask(client_context):
    def perform(question='Estado del proyecto', *, project=True, conversation=None, request_id=None):
        conversation = conversation or appi.create_conversation(client_context.actor, {
            'project_id': client_context.project.pk if project else None, 'language': 'es'})
        turn = appi.submit(client_context.actor, conversation.pk, {'question': question, 'request_id': request_id or uuid.uuid4()})
        appi.process(str(turn.pk))
        turn.refresh_from_db()
        return turn
    return perform


def test_anonymous_client_cannot_read_conversations():
    response = APIClient().get('/api/platform/chatbot/conversations/')

    assert response.status_code in (401, 403)
    assert 'no-store' in response['Cache-Control']


def test_global_off_blocks_queries(client_context):
    client_context.config.chatbot_enabled = False
    client_context.config.save()

    response = client_context.api.post('/api/platform/chatbot/conversations/', {'language': 'es'}, format='json')

    assert response.status_code == 403
    client_context.router.assert_not_called()


def test_outside_question_never_calls_writer(client_context, ask):
    client_context.router.return_value = {'scenario': 'out_of_scope', 'topic': 'general', 'explain': True}

    turn = ask('¿Qué clima hace hoy?')

    assert 'propósito' in turn.answer['text']
    assert turn.answer['sources'] == []
    assert snapshot(client_context.actor)['used'] == 1
    client_context.writer.assert_not_called()


def test_exact_repetition_reuses_verified_answer(client_context, ask):
    first = ask()

    second = ask(conversation=first.conversation)

    assert second.answer['provenance'] == 'cache'
    assert second.answer['text'] == first.answer['text']
    assert client_context.router.call_count == 1
    assert snapshot(client_context.actor)['used'] == 2


def test_changed_progress_refreshes_template_without_routing_again(client_context, ask):
    first = ask()
    Project.objects.filter(pk=client_context.project.pk).update(progress=75)

    second = ask(conversation=first.conversation)

    assert '75 %' in second.answer['text']
    assert '25 %' not in second.answer['text']
    assert second.answer['provenance'] == 'template'
    assert client_context.router.call_count == 1


def test_new_bug_invalidates_previously_empty_result(client_context, ask):
    client_context.router.return_value = {'scenario': 'bugs', 'topic': 'general', 'explain': False}
    first = ask('Bugs del proyecto')
    BugReport.objects.create(project=client_context.project, reported_by=client_context.actor, title='Checkout fails')

    second = ask('Bugs del proyecto', conversation=first.conversation)

    assert 'Checkout fails' in second.answer['text']
    assert second.answer['provenance'] == 'template'


def test_all_projects_excludes_another_client(client_context, ask):
    other = get_user_model().objects.create_user('other-client')
    Project.objects.create(client=other, name='OTHER CLIENT CONFIDENTIAL')

    turn = ask(project=False)

    assert 'Client project' in turn.answer['text']
    assert 'OTHER CLIENT CONFIDENTIAL' not in json.dumps(turn.answer)


def test_revoked_project_hides_historical_answer(client_context, ask):
    turn = ask(project=False)
    other = get_user_model().objects.create_user('new-owner')
    Project.objects.filter(pk=client_context.project.pk).update(client=other)

    result = appi.turn_data(client_context.actor, turn)

    assert result['answer'] is None
    assert result['question'] == ''
    assert result['status'] == 'unavailable'


def test_another_client_cannot_open_conversation(client_context, ask):
    turn = ask()
    other = get_user_model().objects.create_user('guessing-client')
    UserProfile.objects.update_or_create(user=other, defaults={'role': 'client', 'chatbot_enabled': True})

    with pytest.raises(NotFound):
        appi.detail(other, turn.conversation_id)


def test_guide_does_not_require_assigned_project(client_context, ask):
    other = get_user_model().objects.create_user('unassigned-project-owner')
    Project.objects.filter(pk=client_context.project.pk).update(client=other)
    client_context.router.return_value = {'scenario': 'guide_profile', 'topic': 'general', 'explain': True}

    turn = ask('¿Cómo edito mi perfil?', project=False)

    assert 'Guardar cambios' in turn.answer['text']
    assert turn.answer['actions'][0]['href'] == '/platform/profile'
    client_context.writer.assert_not_called()


def test_report_bug_guide_links_to_owned_project(client_context, ask):
    client_context.router.return_value = {'scenario': 'guide_report_bug', 'topic': 'general', 'explain': False}

    turn = ask('Necesito reportar un bug')

    assert 'Reportar bug' in turn.answer['text']
    assert turn.answer['actions'][0]['href'] == f'/platform/projects/{client_context.project.pk}/bugs'
    assert BugReport.objects.count() == 0


def test_report_guide_requests_project_selection(client_context, ask):
    client_context.router.return_value = {'scenario': 'guide_report_bug', 'topic': 'general', 'explain': False}

    turn = ask('Necesito reportar un bug', project=False)

    assert 'Selecciona un proyecto' in turn.answer['text']
    assert turn.answer['actions'] == []


def test_shared_voice_consumption_blocks_chat_before_models(client_context):
    client_context.config.ai_request_limit = 1
    client_context.config.save()
    receipt = reserve(client_context.actor, uuid.uuid4(), 'voice_report', 'voice-fingerprint')
    consume(receipt.pk)
    conversation = appi.create_conversation(client_context.actor, {'language': 'es'})

    with pytest.raises(Throttled):
        appi.submit(client_context.actor, conversation.pk, {'question': 'Estado', 'request_id': uuid.uuid4()})

    client_context.router.assert_not_called()


def test_retry_uses_one_logical_request(client_context, ask):
    request_id = uuid.uuid4()
    turn = ask(request_id=request_id)

    retried = appi.submit(client_context.actor, turn.conversation_id, {'question': 'Estado del proyecto', 'request_id': request_id})

    assert retried.pk == turn.pk
    assert snapshot(client_context.actor)['used'] == 1
    assert AppiTurn.objects.count() == 1


def test_provider_failure_refunds_unused_reservation(client_context):
    client_context.router.side_effect = AIUnavailable()
    conversation = appi.create_conversation(client_context.actor, {'language': 'es'})
    turn = appi.submit(client_context.actor, conversation.pk, {'question': 'Estado', 'request_id': uuid.uuid4()})

    with pytest.raises(AIUnavailable):
        appi.process(str(turn.pk))

    turn.refresh_from_db()
    assert turn.status == 'failed'
    assert snapshot(client_context.actor)['remaining'] == 20


def test_signed_contract_never_uses_new_live_text(client_context, ask):
    document = Document.objects.create(title='Contract', project=client_context.project, client_user=client_context.actor,
        requires_signature=True, signed_at=timezone.now(), signed_by=client_context.actor, content_markdown='NEW PRIVATE DRAFT: propiedad intelectual nueva')
    ProjectContract.objects.create(project=client_context.project, document=document, title='Signed contract', key='contract', client_visible=True)
    client_context.router.return_value = {'scenario': 'contract_clause', 'topic': 'intellectual_property', 'explain': False}

    turn = ask('¿Qué dice propiedad intelectual?')

    assert 'NEW PRIVATE DRAFT' not in turn.answer['text']
    assert 'fragmento verificable' in turn.answer['text']


def test_expired_history_is_deleted(client_context, ask):
    turn = ask()
    AppiConversation.objects.filter(pk=turn.conversation_id).update(expires_at=timezone.now() - timedelta(seconds=1))

    appi.cleanup()

    assert not AppiTurn.objects.filter(pk=turn.pk).exists()


def test_deleting_history_does_not_restore_quota(client_context, ask):
    turn = ask()

    appi.delete_conversation(client_context.actor, turn.conversation_id)

    assert not AppiTurn.objects.exists()
    assert snapshot(client_context.actor)['used'] == 1
