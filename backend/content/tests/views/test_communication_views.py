from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Project, UserProfile
from accounts.services import proposal_client_service
from content.models import (
    CommunicationMessage,
    CommunicationMessageDateCorrection,
    CommunicationMessageRevision,
    CommunicationThread,
    Document,
    DocumentType,
    ProjectRetentionContext,
)
from content.services import communication_service, project_service


pytestmark = pytest.mark.django_db
User = get_user_model()
FIXED_OCCURRED_AT = datetime(2026, 8, 25, 14, 0, tzinfo=UTC)


def make_client(email, *, first_name='Ana'):
    user = User.objects.create_user(
        username=email,
        email=email,
        first_name=first_name,
        password='testpass123',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


@pytest.fixture
def communication_context(admin_user):
    client = make_client('ana@example.com')
    project = Project.objects.create(name='Portal de Ana', client=client.user)
    thread = communication_service.create_thread(
        actor=admin_user,
        client=client,
        project=project,
        title='Aprobación de alcance',
    )
    return {'client': client, 'project': project, 'thread': thread}


def create_message(admin_client, thread, **overrides):
    payload = {
        'channel': 'whatsapp',
        'direction': 'outgoing',
        'status': 'draft',
        'subject': '',
        'content': 'Texto de seguimiento',
        'occurred_at': FIXED_OCCURRED_AT.isoformat(),
        **overrides,
    }
    return admin_client.post(
        reverse('communication-thread-messages', args=[thread.id]),
        payload,
        format='json',
    )


def test_thread_creation_rejects_project_from_another_client(admin_client):
    owner = make_client('owner@example.com')
    other = make_client('other@example.com')
    project = Project.objects.create(name='Proyecto ajeno', client=other.user)

    response = admin_client.post(reverse('communication-threads'), {
        'client': owner.id,
        'project': project.id,
        'title': 'Hilo inválido',
    }, format='json')

    assert response.status_code == 400
    assert 'project' in response.data


def test_thread_list_filters_by_client(admin_client, admin_user):
    first = make_client('first@example.com')
    second = make_client('second@example.com')
    communication_service.create_thread(actor=admin_user, client=first, title='Primero')
    communication_service.create_thread(actor=admin_user, client=second, title='Segundo')

    response = admin_client.get(reverse('communication-threads'), {'client': first.id})

    assert response.status_code == 200
    assert [row['title'] for row in response.data['results']] == ['Primero']


def test_thread_list_requires_admin(api_client):
    response = api_client.get(reverse('communication-threads'))

    assert response.status_code in (401, 403)


def test_thread_client_is_immutable(admin_client, communication_context):
    replacement = make_client('replacement@example.com')

    response = admin_client.patch(
        reverse(
            'communication-thread-detail',
            args=[communication_context['thread'].id],
        ),
        {'client': replacement.id, 'project': None},
        format='json',
    )

    assert response.status_code == 400
    assert 'histórico' in response.data['detail']


def test_message_references_existing_document(admin_client, communication_context):
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    document = Document.objects.create(
        title='Alcance aprobado',
        document_type=document_type,
        client_user=communication_context['client'].user,
    )

    response = create_message(
        admin_client,
        communication_context['thread'],
        document_ids=[document.id],
    )

    assert response.status_code == 201
    assert response.data['documents'][0]['id'] == document.id


def test_document_usage_returns_originating_thread(admin_client, communication_context):
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    document = Document.objects.create(
        title='Acta', document_type=document_type,
        client_user=communication_context['client'].user,
    )
    create_message(
        admin_client,
        communication_context['thread'],
        document_ids=[document.id],
    )

    response = admin_client.get(
        reverse('document-communication-usage', args=[document.id]),
    )

    assert response.status_code == 200
    assert response.data['results'][0]['thread']['id'] == communication_context['thread'].id


def test_document_delete_is_blocked_while_referenced(admin_client, communication_context):
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    document = Document.objects.create(
        title='Contrato', document_type=document_type,
        client_user=communication_context['client'].user,
    )
    create_message(
        admin_client,
        communication_context['thread'],
        document_ids=[document.id],
    )

    response = admin_client.delete(reverse('delete-document', args=[document.id]))

    assert response.status_code == 409
    assert response.data['code'] == 'document_used_in_communication'


def test_incoming_message_defaults_to_received(admin_client, communication_context):
    response = create_message(
        admin_client,
        communication_context['thread'],
        direction='incoming',
        status='received',
        content='Confirmo la aprobación.',
    )

    assert response.status_code == 201
    assert response.data['status'] == 'received'


def test_closed_thread_rejects_new_message(admin_client, admin_user, communication_context):
    communication_service.close_thread(
        communication_context['thread'], actor=admin_user,
    )

    response = create_message(admin_client, communication_context['thread'])

    assert response.status_code == 400
    assert 'cerrado' in response.data['detail']


def test_mark_sent_transitions_outgoing_draft(admin_client, communication_context):
    created = create_message(admin_client, communication_context['thread'])

    response = admin_client.post(
        reverse('mark-communication-message-sent', args=[created.data['id']]),
        {'occurred_at': (FIXED_OCCURRED_AT + timedelta(hours=1)).isoformat()},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == 'sent'


def test_closed_thread_rejects_mark_sent(
    admin_client, admin_user, communication_context,
):
    created = create_message(admin_client, communication_context['thread'])
    communication_service.close_thread(
        communication_context['thread'], actor=admin_user,
    )

    response = admin_client.post(
        reverse('mark-communication-message-sent', args=[created.data['id']]),
        format='json',
    )

    assert response.status_code == 400
    assert 'Reabre' in response.data['detail']


def test_sent_message_rejects_direct_edit(admin_client, communication_context):
    created = create_message(
        admin_client, communication_context['thread'], status='sent',
    )

    response = admin_client.patch(
        reverse('communication-message-detail', args=[created.data['id']]),
        {'content': 'Texto reescrito'},
        format='json',
    )

    assert response.status_code == 400
    assert 'borradores' in response.data['detail']


def test_retained_thread_rejects_draft_edit(admin_client, admin_user, communication_context):
    """Fails if an archived project's retained draft can be changed through the panel."""
    created = create_message(admin_client, communication_context['thread'])
    context = ProjectRetentionContext.objects.create(
        client=communication_context['client'].user,
        original_project_id=communication_context['project'].pk,
        project_name=communication_context['project'].name,
        retained_records={},
        created_by=admin_user,
    )
    CommunicationThread.objects.filter(pk=communication_context['thread'].pk).update(
        project=None,
        retention_context=context,
    )

    response = admin_client.patch(
        reverse('communication-message-detail', args=[created.data['id']]),
        {'content': 'Texto que no debe persistir'},
        format='json',
    )

    message = CommunicationMessage.objects.get(pk=created.data['id'])
    assert response.status_code == 400
    assert response.data['detail'] == 'Los datos conservados sin proyecto sólo permiten consulta.'
    assert message.content == 'Texto de seguimiento'
    assert not CommunicationMessageRevision.objects.filter(message=message).exists()


def test_retained_thread_rejects_draft_deletion(admin_client, admin_user, communication_context):
    """Fails if deleting a retained draft removes its history through the panel."""
    created = create_message(admin_client, communication_context['thread'])
    context = ProjectRetentionContext.objects.create(
        client=communication_context['client'].user,
        original_project_id=communication_context['project'].pk,
        project_name=communication_context['project'].name,
        retained_records={},
        created_by=admin_user,
    )
    CommunicationThread.objects.filter(pk=communication_context['thread'].pk).update(
        project=None,
        retention_context=context,
    )

    response = admin_client.delete(
        reverse('communication-message-detail', args=[created.data['id']]),
    )

    assert response.status_code == 400
    assert response.data['detail'] == 'Los datos conservados sin proyecto sólo permiten consulta.'
    assert CommunicationMessage.objects.filter(pk=created.data['id']).exists()
    assert not CommunicationMessageRevision.objects.filter(message_id=created.data['id']).exists()


def test_date_correction_creates_audit_record(admin_client, communication_context):
    created = create_message(
        admin_client, communication_context['thread'], status='sent',
    )
    corrected_at = FIXED_OCCURRED_AT - timedelta(days=2)

    response = admin_client.post(
        reverse('correct-communication-message-date', args=[created.data['id']]),
        {'occurred_at': corrected_at.isoformat(), 'reason': 'Fecha del envío real'},
        format='json',
    )

    assert response.status_code == 200
    correction = CommunicationMessageDateCorrection.objects.get(
        message_id=created.data['id'],
    )
    assert correction.reason == 'Fecha del envío real'


def test_reply_requires_opposite_direction(admin_client, communication_context):
    original = create_message(
        admin_client, communication_context['thread'], status='sent',
    )

    response = create_message(
        admin_client,
        communication_context['thread'],
        status='sent',
        reply_to=original.data['id'],
    )

    assert response.status_code == 400
    assert 'dirección opuesta' in response.data['detail']


def test_client_with_thread_is_not_orphan(admin_client, admin_user):
    client = make_client('history@example.com')
    communication_service.create_thread(actor=admin_user, client=client, title='Histórico')

    response = admin_client.get(reverse('list-proposal-clients'))

    row = next(item for item in response.data if item['id'] == client.id)
    assert row['is_orphan'] is False


def test_client_delete_guard_preserves_communication_history(admin_user):
    client = make_client('protected@example.com')
    communication_service.create_thread(actor=admin_user, client=client, title='Histórico')

    with pytest.raises(ValueError, match='client_has_communications:1'):
        proposal_client_service.delete_orphan_client(client)


def test_project_client_change_detaches_historical_threads(admin_user):
    owner = make_client('old@example.com')
    target = make_client('new@example.com')
    project = Project.objects.create(name='Proyecto transferido', client=owner.user)
    thread = communication_service.create_thread(
        actor=admin_user, client=owner, project=project, title='Conversación histórica',
    )

    result = project_service.change_client_apply(
        project, target, project_service.MODE_MOVE, admin_user,
    )

    thread.refresh_from_db()
    # Dos: la conversacion historica y la comunicacion madre que el proyecto
    # tenia con su cliente anterior. Ninguna correspondencia cambia de dueno.
    assert result['detached_communications'] == 2
    assert thread.project_id is None
    # Y el proyecto estrena madre bajo su nuevo dueno, sin perder el invariante
    # de una sola por proyecto.
    fresh = CommunicationThread.objects.get(managed_project=project)
    assert fresh.client_id == target.id
    assert fresh.pk != thread.pk


def test_fake_command_creates_bidirectional_demo_thread(admin_user):
    make_client('demo-history@example.com')

    call_command('create_fake_communications', count=1, verbosity=0)

    thread = CommunicationThread.objects.get(title__startswith='[Demo]')
    assert list(thread.messages.values_list('direction', 'status')) == [
        (CommunicationMessage.Direction.OUTGOING, CommunicationMessage.Status.SENT),
        (CommunicationMessage.Direction.INCOMING, CommunicationMessage.Status.RECEIVED),
        (CommunicationMessage.Direction.OUTGOING, CommunicationMessage.Status.DRAFT),
    ]
