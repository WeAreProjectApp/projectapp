from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from content.models import (
    CommunicationAttachment,
    CommunicationMessage,
    CommunicationMessageDateCorrection,
    CommunicationMessageRevision,
    CommunicationThread,
    Document,
)


class CommunicationError(ValueError):
    """A business-rule violation safe to expose through the panel API."""


def _require_operational_thread(thread):
    if thread.retention_context_id:
        raise CommunicationError('Los datos conservados sin proyecto sólo permiten consulta.')


def _validate_thread(thread):
    _require_operational_thread(thread)
    try:
        thread.full_clean()
    except DjangoValidationError as exc:
        raise CommunicationError(exc.message_dict) from exc


def _validate_message_shape(*, thread, channel, direction, status, subject, reply_to):
    _require_operational_thread(thread)
    if thread.status == CommunicationThread.Status.CLOSED:
        raise CommunicationError('El hilo está cerrado. Reábrelo antes de registrar mensajes.')
    if direction == CommunicationMessage.Direction.INCOMING:
        if status != CommunicationMessage.Status.RECEIVED:
            raise CommunicationError('Un mensaje entrante debe registrarse como recibido.')
    elif status == CommunicationMessage.Status.RECEIVED:
        raise CommunicationError('Un mensaje saliente no puede tener estado recibido.')
    if channel == CommunicationMessage.Channel.EMAIL and not subject.strip():
        raise CommunicationError('El asunto es obligatorio para mensajes de correo.')
    if channel == CommunicationMessage.Channel.WHATSAPP and subject.strip():
        raise CommunicationError('Los mensajes de WhatsApp no llevan asunto.')
    if reply_to:
        if reply_to.thread_id != thread.id:
            raise CommunicationError('La respuesta debe apuntar a un mensaje del mismo hilo.')
        if reply_to.direction == direction:
            raise CommunicationError('Una respuesta debe tener la dirección opuesta al mensaje original.')
        if reply_to.voided_at:
            raise CommunicationError('No se puede responder a un mensaje anulado.')
        if reply_to.status == CommunicationMessage.Status.DRAFT:
            raise CommunicationError('No se puede responder a un borrador.')


def _validate_documents(thread, documents, *, require_client_owner=False):
    for document in documents:
        if require_client_owner and not document.client_user_id:
            raise CommunicationError(
                f'El documento “{document.title}” no pertenece al cliente del hilo.'
            )
        if document.client_user_id and document.client_user_id != thread.client.user_id:
            raise CommunicationError(
                f'El documento “{document.title}” pertenece a otro cliente.'
            )


def _recalculate_last_activity(thread, *, actor=None):
    latest = thread.messages.filter(voided_at__isnull=True).aggregate(
        latest=Max('occurred_at'),
    )['latest']
    thread.last_activity_at = latest or thread.created_at or timezone.now()
    if actor is not None:
        thread.updated_by = actor
    thread.save(update_fields=['last_activity_at', 'updated_by', 'updated_at'])


def _revision_value(field, value):
    if field == 'reply_to':
        return value.pk if value else None
    if field == 'occurred_at':
        return value.isoformat()
    return value


def _draft_revision_changes(
    message, validated_data, *, previous_document_ids=None, document_ids=None,
):
    changes = []
    for field, new_value in validated_data.items():
        old_value = getattr(message, field)
        audit_field = 'reply_to_id' if field == 'reply_to' else field
        changes.append({
            'field': audit_field,
            'old': _revision_value(field, old_value),
            'new': _revision_value(field, new_value),
        })
    if document_ids is not None:
        changes.append({
            'field': 'document_ids',
            'old': sorted(previous_document_ids or []),
            'new': sorted(set(document_ids)),
        })
    return changes


@transaction.atomic
def create_thread(*, actor, **validated_data):
    from content.services.communication_folder_service import lock_client, validate_thread_folder
    lock_client(validated_data['client'].pk)
    thread = CommunicationThread(
        created_by=actor,
        updated_by=actor,
        **validated_data,
    )
    validate_thread_folder(thread)
    _validate_thread(thread)
    thread.save()
    return thread


@transaction.atomic
def update_thread(thread, *, actor, **validated_data):
    from content.services.communication_folder_service import lock_client, validate_thread_folder
    lock_client(thread.client_id)
    thread = CommunicationThread.objects.select_for_update().get(pk=thread.pk)
    if thread.status == CommunicationThread.Status.CLOSED and set(validated_data) != {'folder'}:
        raise CommunicationError('Reabre el hilo antes de editarlo.')
    client = validated_data.get('client')
    if client is not None and client.pk != thread.client_id:
        raise CommunicationError(
            'El cliente de un hilo es histórico y no se puede cambiar.',
        )
    for field, value in validated_data.items():
        setattr(thread, field, value)
    if 'project' in validated_data and 'folder' not in validated_data and thread.folder_id:
        if thread.folder.project_id and thread.folder.project_id != thread.project_id:
            thread.folder = None
    validate_thread_folder(thread)
    thread.updated_by = actor
    _validate_thread(thread)
    thread.save()
    return thread


@transaction.atomic
def close_thread(thread, *, actor):
    if thread.status == CommunicationThread.Status.CLOSED:
        raise CommunicationError('El hilo ya está cerrado.')
    thread.status = CommunicationThread.Status.CLOSED
    thread.closed_at = timezone.now()
    thread.updated_by = actor
    thread.save(update_fields=['status', 'closed_at', 'updated_by', 'updated_at'])
    return thread


@transaction.atomic
def reopen_thread(thread, *, actor):
    if thread.status == CommunicationThread.Status.OPEN:
        raise CommunicationError('El hilo ya está abierto.')
    thread.status = CommunicationThread.Status.OPEN
    thread.closed_at = None
    thread.updated_by = actor
    thread.save(update_fields=['status', 'closed_at', 'updated_by', 'updated_at'])
    return thread


@transaction.atomic
def archive_thread(thread, *, actor):
    """Saca el hilo de la vista sin decir nada sobre la conversación.

    Es otro eje que cerrar: un hilo cerrado sigue listándose, y uno abierto se
    puede archivar. Sin cascada — los hilos son planos y los mensajes viven
    dentro del suyo, así que no hay nada que arrastrar ni que revertir después.
    """
    if thread.thread_kind != 'manual':
        raise CommunicationError(
            'Esta es la comunicación madre de su proyecto o cliente: es el punto '
            'de entrada de esa entidad y no puede archivarse.'
        )
    if thread.is_archived:
        raise CommunicationError('El hilo ya está archivado.')
    thread.is_archived = True
    thread.archived_at = timezone.now()
    thread.updated_by = actor
    thread.save(update_fields=['is_archived', 'archived_at', 'updated_by', 'updated_at'])
    return thread


@transaction.atomic
def unarchive_thread(thread, *, actor):
    if not thread.is_archived:
        raise CommunicationError('El hilo no está archivado.')
    thread.is_archived = False
    thread.archived_at = None
    thread.updated_by = actor
    thread.save(update_fields=['is_archived', 'archived_at', 'updated_by', 'updated_at'])
    return thread


@transaction.atomic
def create_message(*, thread, actor, document_ids=None, **validated_data):
    documents = list(Document.objects.filter(pk__in=document_ids or []))
    if len(documents) != len(set(document_ids or [])):
        raise CommunicationError('Uno o más documentos no existen.')
    _validate_message_shape(thread=thread, **{
        key: validated_data.get(key, '')
        for key in ('channel', 'direction', 'status', 'subject', 'reply_to')
    })
    _validate_documents(thread, documents)
    message = CommunicationMessage.objects.create(
        thread=thread,
        created_by=actor,
        updated_by=actor,
        **validated_data,
    )
    CommunicationAttachment.objects.bulk_create([
        CommunicationAttachment(message=message, document=document)
        for document in documents
    ])
    _recalculate_last_activity(thread, actor=actor)
    return message


@transaction.atomic
def update_draft(message, *, actor, document_ids=None, **validated_data):
    message = (
        CommunicationMessage.objects.select_for_update()
        .select_related('thread__client__user', 'reply_to')
        .get(pk=message.pk)
    )
    if not validated_data and document_ids is None:
        raise CommunicationError('Envía al menos un campo para actualizar.')
    if (
        message.direction != CommunicationMessage.Direction.OUTGOING
        or message.status != CommunicationMessage.Status.DRAFT
        or message.voided_at
    ):
        raise CommunicationError(
            'Sólo los borradores salientes activos se pueden editar.',
        )

    documents = None
    previous_document_ids = None
    if document_ids is not None:
        documents = list(Document.objects.filter(pk__in=document_ids))
        if len(documents) != len(set(document_ids)):
            raise CommunicationError('Uno o más documentos no existen.')
        _validate_documents(
            message.thread,
            documents,
            require_client_owner=True,
        )
        previous_document_ids = list(
            message.attachments.values_list('document_id', flat=True),
        )

    candidate = {
        'thread': message.thread,
        'channel': validated_data.get('channel', message.channel),
        'direction': validated_data.get('direction', message.direction),
        'status': CommunicationMessage.Status.DRAFT,
        'subject': validated_data.get('subject', message.subject),
        'reply_to': validated_data.get('reply_to', message.reply_to),
    }
    _validate_message_shape(**candidate)
    changes = _draft_revision_changes(
        message,
        validated_data,
        previous_document_ids=previous_document_ids,
        document_ids=document_ids,
    )
    for field, value in validated_data.items():
        setattr(message, field, value)
    message.updated_by = actor
    message.save()
    if document_ids is not None:
        message.attachments.all().delete()
        CommunicationAttachment.objects.bulk_create([
            CommunicationAttachment(message=message, document=document)
            for document in documents
        ])
    CommunicationMessageRevision.objects.create(
        message=message,
        changes=changes,
        edited_by=actor,
    )
    _recalculate_last_activity(message.thread, actor=actor)
    return message


@transaction.atomic
def delete_draft(message, *, actor):
    _require_operational_thread(message.thread)
    if message.status != CommunicationMessage.Status.DRAFT or message.voided_at:
        raise CommunicationError('Sólo los borradores activos se pueden eliminar.')
    thread = message.thread
    message.delete()
    _recalculate_last_activity(thread, actor=actor)


@transaction.atomic
def mark_sent(message, *, actor, occurred_at=None):
    _require_operational_thread(message.thread)
    if message.thread.status == CommunicationThread.Status.CLOSED:
        raise CommunicationError('Reabre el hilo antes de marcar el envío.')
    if message.direction != CommunicationMessage.Direction.OUTGOING:
        raise CommunicationError('Sólo un mensaje saliente puede marcarse como enviado.')
    if message.status != CommunicationMessage.Status.DRAFT or message.voided_at:
        raise CommunicationError('Sólo un borrador activo puede marcarse como enviado.')
    message.status = CommunicationMessage.Status.SENT
    if occurred_at is not None:
        message.occurred_at = occurred_at
    message.updated_by = actor
    message.save(update_fields=['status', 'occurred_at', 'updated_by', 'updated_at'])
    _recalculate_last_activity(message.thread, actor=actor)
    return message


@transaction.atomic
def void_message(message, *, actor, reason):
    _require_operational_thread(message.thread)
    if message.status == CommunicationMessage.Status.DRAFT:
        raise CommunicationError('Elimina el borrador en lugar de anularlo.')
    if message.voided_at:
        raise CommunicationError('El mensaje ya está anulado.')
    reason = reason.strip()
    if not reason:
        raise CommunicationError('El motivo de anulación es obligatorio.')
    message.voided_at = timezone.now()
    message.void_reason = reason
    message.voided_by = actor
    message.updated_by = actor
    message.save(update_fields=[
        'voided_at', 'void_reason', 'voided_by', 'updated_by', 'updated_at',
    ])
    _recalculate_last_activity(message.thread, actor=actor)
    return message


@transaction.atomic
def correct_message_date(message, *, actor, occurred_at, reason):
    _require_operational_thread(message.thread)
    if message.status == CommunicationMessage.Status.DRAFT:
        raise CommunicationError('Edita el borrador para cambiar su fecha.')
    if message.voided_at:
        raise CommunicationError('No se puede corregir la fecha de un mensaje anulado.')
    reason = reason.strip()
    if not reason:
        raise CommunicationError('El motivo de la corrección es obligatorio.')
    if message.occurred_at == occurred_at:
        raise CommunicationError('La fecha corregida debe ser distinta de la actual.')
    previous = message.occurred_at
    CommunicationMessageDateCorrection.objects.create(
        message=message,
        previous_occurred_at=previous,
        corrected_occurred_at=occurred_at,
        reason=reason,
        corrected_by=actor,
    )
    message.occurred_at = occurred_at
    message.updated_by = actor
    message.save(update_fields=['occurred_at', 'updated_by', 'updated_at'])
    _recalculate_last_activity(message.thread, actor=actor)
    return message
