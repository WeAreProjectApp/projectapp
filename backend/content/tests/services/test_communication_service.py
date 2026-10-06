from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import UserProfile
from content.models import (
    CommunicationMessage,
    CommunicationMessageRevision,
    Document,
    ProjectRetentionContext,
)
from content.services import communication_service


pytestmark = pytest.mark.django_db
User = get_user_model()
OCCURRED_AT = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)


def make_client(email):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='testpass123',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


@pytest.fixture
def communication_context(admin_user):
    client = make_client('draft-service@example.com')
    thread = communication_service.create_thread(
        actor=admin_user,
        client=client,
        title='Borrador editable',
    )
    message = communication_service.create_message(
        thread=thread,
        actor=admin_user,
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.OUTGOING,
        status=CommunicationMessage.Status.DRAFT,
        subject='Asunto inicial',
        content='Contenido inicial',
        occurred_at=OCCURRED_AT,
    )
    return {
        'client': client,
        'thread': thread,
        'message': message,
        'actor': admin_user,
    }


def update_email_draft(communication_context):
    message = communication_context['message']
    corrected_at = OCCURRED_AT + timedelta(hours=2)
    updated = communication_service.update_draft(
        message,
        actor=communication_context['actor'],
        subject='Asunto corregido',
        content='Contenido corregido',
        occurred_at=corrected_at,
    )
    updated.refresh_from_db()
    return updated, corrected_at


def test_update_draft_preserves_message_identity(communication_context):
    """Falla si editar un borrador crea otro mensaje o lo mueve de hilo."""
    message = communication_context['message']

    updated, _ = update_email_draft(communication_context)

    assert updated.pk == message.pk
    assert updated.thread_id == communication_context['thread'].pk


def retain_thread(context):
    retention = ProjectRetentionContext.objects.create(
        client=context['client'].user,
        original_project_id=context['thread'].pk + 1000,
        project_name='Archived communication project',
        retained_records={},
        created_by=context['actor'],
    )
    type(context['thread']).objects.filter(pk=context['thread'].pk).update(
        retention_context=retention,
    )
    context['thread'].refresh_from_db()
    context['message'].refresh_from_db()


def test_retained_thread_rejects_mark_sent(communication_context):
    """Fails if a retained outgoing draft can be marked sent."""
    retain_thread(communication_context)

    with pytest.raises(communication_service.CommunicationError, match='sólo permiten consulta'):
        communication_service.mark_sent(
            communication_context['message'], actor=communication_context['actor'],
        )

    communication_context['message'].refresh_from_db()
    assert communication_context['message'].status == CommunicationMessage.Status.DRAFT


def test_retained_thread_rejects_voiding_sent_message(communication_context):
    """Fails if a retained sent message can be voided."""
    message = communication_service.mark_sent(
        communication_context['message'], actor=communication_context['actor'],
    )
    retain_thread(communication_context)

    with pytest.raises(communication_service.CommunicationError, match='sólo permiten consulta'):
        communication_service.void_message(message, actor=communication_context['actor'], reason='No aplicar')

    message.refresh_from_db()
    assert message.voided_at is None


def test_retained_thread_rejects_sent_message_date_correction(communication_context):
    """Fails if a retained sent message can acquire a date-correction history row."""
    message = communication_service.mark_sent(
        communication_context['message'], actor=communication_context['actor'],
    )
    retain_thread(communication_context)

    with pytest.raises(communication_service.CommunicationError, match='sólo permiten consulta'):
        communication_service.correct_message_date(
            message,
            actor=communication_context['actor'],
            occurred_at=OCCURRED_AT + timedelta(days=1),
            reason='No aplicar',
        )

    assert message.date_corrections.count() == 0


def test_update_draft_preserves_immutable_message_metadata(communication_context):
    """Falla si editar un borrador modifica canal, dirección, estado o registro."""
    message = communication_context['message']
    previous_recorded_at = message.recorded_at

    updated, _ = update_email_draft(communication_context)

    assert updated.channel == CommunicationMessage.Channel.EMAIL
    assert updated.direction == CommunicationMessage.Direction.OUTGOING
    assert updated.status == CommunicationMessage.Status.DRAFT
    assert updated.recorded_at == previous_recorded_at


def test_update_draft_refreshes_updated_at(communication_context):
    """Falla si editar un borrador no actualiza su marca de modificación."""
    message = communication_context['message']
    previous_updated_at = OCCURRED_AT - timedelta(days=1)
    CommunicationMessage.objects.filter(pk=message.pk).update(
        updated_at=previous_updated_at,
    )
    message.refresh_from_db()

    updated, _ = update_email_draft(communication_context)

    assert updated.updated_at > previous_updated_at


def test_update_draft_records_email_revision(communication_context):
    """Falla si editar un borrador no conserva los valores anteriores auditados."""
    updated, corrected_at = update_email_draft(communication_context)

    revision = CommunicationMessageRevision.objects.get(message=updated)
    assert revision.changes == [
        {'field': 'subject', 'old': 'Asunto inicial', 'new': 'Asunto corregido'},
        {
            'field': 'content',
            'old': 'Contenido inicial',
            'new': 'Contenido corregido',
        },
        {
            'field': 'occurred_at',
            'old': OCCURRED_AT.isoformat(),
            'new': corrected_at.isoformat(),
        },
    ]
    assert revision.edited_by == communication_context['actor']


def test_update_draft_replaces_documents_with_audited_ids(communication_context):
    client_user = communication_context['client'].user
    original = Document.objects.create(title='Original', client_user=client_user)
    replacement = Document.objects.create(title='Reemplazo', client_user=client_user)
    message = communication_context['message']
    message.documents.add(original, through_defaults={})

    communication_service.update_draft(
        message,
        actor=communication_context['actor'],
        document_ids=[replacement.pk],
    )

    message.refresh_from_db()
    change = message.revisions.get().changes[0]
    assert list(message.documents.values_list('pk', flat=True)) == [replacement.pk]
    assert change == {
        'field': 'document_ids',
        'old': [original.pk],
        'new': [replacement.pk],
    }


def test_update_draft_rejects_cross_client_document_atomically(
    communication_context,
):
    owner_document = Document.objects.create(
        title='Documento vigente',
        client_user=communication_context['client'].user,
    )
    other_client = make_client('other-draft-service@example.com')
    foreign_document = Document.objects.create(
        title='Documento ajeno',
        client_user=other_client.user,
    )
    message = communication_context['message']
    message.documents.add(owner_document, through_defaults={})

    with pytest.raises(communication_service.CommunicationError, match='otro cliente'):
        communication_service.update_draft(
            message,
            actor=communication_context['actor'],
            subject='No debe persistir',
            document_ids=[foreign_document.pk],
        )

    message.refresh_from_db()
    assert message.subject == 'Asunto inicial'
    assert list(message.documents.values_list('pk', flat=True)) == [owner_document.pk]
    assert not message.revisions.exists()


def test_update_draft_rejects_document_without_client(communication_context):
    unowned_document = Document.objects.create(title='Documento sin cliente')
    message = communication_context['message']

    with pytest.raises(
        communication_service.CommunicationError,
        match='no pertenece al cliente del hilo',
    ):
        communication_service.update_draft(
            message,
            actor=communication_context['actor'],
            document_ids=[unowned_document.pk],
        )

    assert not message.documents.exists()
    assert not message.revisions.exists()


@pytest.mark.parametrize(
    ('status', 'direction', 'voided_at'),
    [
        (CommunicationMessage.Status.SENT, CommunicationMessage.Direction.OUTGOING, None),
        (CommunicationMessage.Status.RECEIVED, CommunicationMessage.Direction.INCOMING, None),
        (CommunicationMessage.Status.FAILED, CommunicationMessage.Direction.OUTGOING, None),
        (CommunicationMessage.Status.DRAFT, CommunicationMessage.Direction.INCOMING, None),
        (
            CommunicationMessage.Status.DRAFT,
            CommunicationMessage.Direction.OUTGOING,
            timezone.now(),
        ),
    ],
)
def test_update_draft_rejects_messages_that_are_not_active_outgoing_drafts(
    admin_user, status, direction, voided_at,
):
    client = make_client(f'{status}-{direction}-{bool(voided_at)}@example.com')
    thread = communication_service.create_thread(
        actor=admin_user,
        client=client,
        title='Mensaje no editable',
    )
    message = CommunicationMessage.objects.create(
        thread=thread,
        channel=CommunicationMessage.Channel.WHATSAPP,
        direction=direction,
        status=status,
        subject='',
        content='Contenido original',
        occurred_at=OCCURRED_AT,
        created_by=admin_user,
        updated_by=admin_user,
        voided_at=voided_at,
    )

    with pytest.raises(
        communication_service.CommunicationError,
        match='borradores salientes activos',
    ):
        communication_service.update_draft(
            message,
            actor=admin_user,
            content='Contenido alterado',
        )

    message.refresh_from_db()
    assert message.content == 'Contenido original'
    assert not message.revisions.exists()


def test_update_draft_rejects_an_empty_patch(communication_context):
    with pytest.raises(
        communication_service.CommunicationError,
        match='al menos un campo',
    ):
        communication_service.update_draft(
            communication_context['message'],
            actor=communication_context['actor'],
        )

    assert not communication_context['message'].revisions.exists()


def test_update_draft_accepts_reply_from_same_thread(
    communication_context,
):
    incoming = communication_service.create_message(
        thread=communication_context['thread'],
        actor=communication_context['actor'],
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.INCOMING,
        status=CommunicationMessage.Status.RECEIVED,
        subject='Respuesta recibida',
        content='Confirmado',
        occurred_at=OCCURRED_AT - timedelta(hours=1),
    )

    updated = communication_service.update_draft(
        communication_context['message'],
        actor=communication_context['actor'],
        reply_to=incoming,
    )

    assert updated.reply_to_id == incoming.pk
    assert updated.revisions.get().changes == [{
        'field': 'reply_to_id',
        'old': None,
        'new': incoming.pk,
    }]
