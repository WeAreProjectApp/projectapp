from content.services.entity_history import historical_write
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from content.models import (
    Document,
    DocumentNote,
    DocumentNoteEvent,
    DocumentState,
    DocumentStateEpisode,
)
from content.services.document_state_service import (
    active_episode_for_key,
    close_episode,
    open_state,
)


class DocumentNoteError(ValueError):
    def __init__(self, message, *, code='invalid_note_operation'):
        super().__init__(message)
        self.code = code


def sync_legacy_notes(document, *, actor=None):
    """Expand legacy JSON notes once without overwriting normalized history."""
    if document.document_notes.exists():
        return
    notes = document.client_custom_notes or []
    DocumentNote.objects.bulk_create([
        DocumentNote(
            document=document,
            title=str(note.get('title') or '').strip(),
            content=str(note.get('content') or '').strip(),
            text_formats=note.get('text_formats') or {},
            order=index,
            created_by=actor,
            created_at_known=False,
        )
        for index, note in enumerate(notes)
        if str(note.get('title') or '').strip() or str(note.get('content') or '').strip()
    ])


@historical_write
@transaction.atomic
def create_note(
    document,
    *,
    title='',
    content,
    text_formats=None,
    actor=None,
    mark_needs_fix=False,
):
    content = str(content or '').strip()
    title = str(title or '').strip()
    if not content:
        raise DocumentNoteError('La observación no puede estar vacía.')

    episode = None
    if mark_needs_fix:
        episode = active_episode_for_key(document, 'needs_fix')
        if episode is None:
            state = DocumentState.objects.filter(
                system_key='needs_fix', is_active=True,
            ).first()
            if state:
                episode, _ = open_state(
                    document,
                    state,
                    actor=actor,
                    origin=DocumentStateEpisode.Origin.NOTE,
                    idempotent=True,
                )

    order = (
        document.document_notes.aggregate(max_order=Max('order'))['max_order']
        or 0
    )
    if document.document_notes.exists():
        order += 1
    from content.services.editorial_format import validate_formats
    formats = validate_formats('documentnote', {'content': content}, text_formats or {})
    return DocumentNote.objects.create(
        document=document,
        episode=episode,
        title=title,
        content=content,
        text_formats=formats,
        order=order,
        created_by=actor,
    )


@historical_write
def update_note(note, *, title=None, content=None, text_formats=None):
    if note.deleted_at is not None:
        raise DocumentNoteError(
            'La observación está en la papelera.',
            code='note_deleted',
        )
    if note.status != DocumentNote.Status.OPEN:
        raise DocumentNoteError('Sólo se pueden editar observaciones pendientes.')
    update_fields = ['updated_at']
    if title is not None:
        note.title = str(title).strip()
        update_fields.append('title')
    if content is not None:
        content = str(content).strip()
        if not content:
            raise DocumentNoteError('La observación no puede estar vacía.')
        note.content = content
        update_fields.append('content')
    from content.services.editorial_format import validate_formats
    formats = note.text_formats if text_formats is None else text_formats
    note.text_formats = validate_formats('documentnote', {'content': note.content}, formats, instance=note)
    update_fields.append('text_formats')
    note.save(update_fields=update_fields)
    return note


@historical_write
@transaction.atomic
def finish_note(
    note,
    *,
    actor=None,
    outcome=DocumentNote.Status.RESOLVED,
    resolution_note='',
    close_linked_state=False,
    move_cycle_to_bug_attended=False,
):
    locked_document = Document.objects.select_for_update().get(pk=note.document_id)
    note = DocumentNote.objects.select_for_update().select_related(
        'episode__state', 'document',
    ).get(pk=note.pk, document=locked_document)
    if note.deleted_at is not None:
        raise DocumentNoteError(
            'La observación está en la papelera.',
            code='note_deleted',
        )
    if note.status != DocumentNote.Status.OPEN:
        raise DocumentNoteError('La observación ya no está pendiente.')
    if outcome not in (DocumentNote.Status.RESOLVED, DocumentNote.Status.DISCARDED):
        raise DocumentNoteError('El resultado de la observación no es válido.')

    note.status = outcome
    note.resolution_note = str(resolution_note or '').strip()
    note.resolved_by = actor
    note.resolved_at = timezone.now()
    note.save(update_fields=(
        'status', 'resolution_note', 'resolved_by', 'resolved_at', 'updated_at',
    ))

    state_closed = False
    cycle_moved = False
    if (
        note.episode_id
        and note.episode.closed_at is None
        and note.episode.origin == DocumentStateEpisode.Origin.NOTE
    ):
        still_open = DocumentNote.objects.filter(
            episode_id=note.episode_id,
            status=DocumentNote.Status.OPEN,
            deleted_at__isnull=True,
        ).exists()
        if not still_open:
            state_outcome = (
                DocumentStateEpisode.Outcome.COMPLETED
                if outcome == DocumentNote.Status.RESOLVED
                else DocumentStateEpisode.Outcome.REMOVED
            )
            close_episode(
                note.episode,
                actor=actor,
                outcome=state_outcome,
                close_note=note.resolution_note,
            )
            state_closed = True
            if move_cycle_to_bug_attended and outcome == DocumentNote.Status.RESOLVED:
                state = DocumentState.objects.filter(
                    system_key='bug_resolved', is_active=True,
                ).first()
                if state:
                    open_state(
                        note.document,
                        state,
                        actor=actor,
                        origin=DocumentStateEpisode.Origin.NOTE,
                        idempotent=True,
                    )
                    cycle_moved = True

    return note, {
        'state_closed': state_closed,
        'cycle_moved': cycle_moved,
    }


@historical_write
@transaction.atomic
def delete_notes(document, *, note_ids, actor=None):
    """Soft-delete one or more notes atomically and reconcile note states."""
    note_ids = list(note_ids)
    if not note_ids:
        raise DocumentNoteError(
            'Selecciona al menos una observación.',
            code='empty_note_selection',
        )
    if len(note_ids) != len(set(note_ids)):
        raise DocumentNoteError(
            'La selección contiene observaciones repetidas.',
            code='duplicate_note_ids',
        )

    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    notes = list(
        DocumentNote.objects.select_for_update()
        .filter(pk__in=note_ids, document=locked_document)
        .select_related('episode__state')
    )
    if len(notes) != len(note_ids):
        raise DocumentNoteError(
            'Una o más observaciones no pertenecen a este documento.',
            code='note_selection_invalid',
        )
    if any(note.deleted_at is not None for note in notes):
        raise DocumentNoteError(
            'Una o más observaciones ya están en la papelera.',
            code='note_already_deleted',
        )

    affected_episode_ids = {
        note.episode_id
        for note in notes
        if note.episode_id and note.status == DocumentNote.Status.OPEN
    }
    episodes = {
        episode.id: episode
        for episode in DocumentStateEpisode.objects.select_for_update()
        .filter(pk__in=affected_episode_ids)
        .select_related('state')
    }
    now = timezone.now()
    for note in notes:
        note.deleted_at = now
        note.deleted_by = actor
        note.updated_at = now
    DocumentNote.objects.bulk_update(notes, ('deleted_at', 'deleted_by', 'updated_at'))

    closed_episode_ids = set()
    for episode in episodes.values():
        if (
            episode.closed_at is not None
            or episode.origin != DocumentStateEpisode.Origin.NOTE
        ):
            continue
        has_open_notes = DocumentNote.objects.filter(
            episode=episode,
            status=DocumentNote.Status.OPEN,
            deleted_at__isnull=True,
        ).exists()
        if not has_open_notes:
            close_episode(
                episode,
                actor=actor,
                outcome=DocumentStateEpisode.Outcome.REMOVED,
                close_note='Sin observaciones pendientes.',
            )
            closed_episode_ids.add(episode.id)

    DocumentNoteEvent.objects.bulk_create([
        DocumentNoteEvent(
            document=locked_document,
            note=note,
            event_type=DocumentNoteEvent.EventType.DELETED,
            actor=actor,
            details=(
                {'closed_episode_id': note.episode_id}
                if note.episode_id in closed_episode_ids
                else {}
            ),
        )
        for note in notes
    ])
    return {
        'deleted_note_ids': sorted(note.id for note in notes),
        'closed_episode_ids': sorted(closed_episode_ids),
        'state_closed': bool(closed_episode_ids),
    }


@historical_write
@transaction.atomic
def restore_note(note, *, actor=None):
    """Restore a soft-deleted note, reopening its note-origin state if needed."""
    locked_document = Document.objects.select_for_update().get(pk=note.document_id)
    note = (
        DocumentNote.objects.select_for_update()
        .select_related('document', 'episode__state')
        .get(pk=note.pk, document=locked_document)
    )
    if note.deleted_at is None:
        raise DocumentNoteError(
            'La observación no está en la papelera.',
            code='note_not_deleted',
        )

    restored_episode_id = None
    deletion_event = (
        note.events.filter(event_type=DocumentNoteEvent.EventType.DELETED)
        .order_by('-recorded_at', '-id')
        .first()
    )
    closed_episode_id = (
        (deletion_event.details or {}).get('closed_episode_id')
        if deletion_event
        else None
    )
    if note.status == DocumentNote.Status.OPEN and closed_episode_id:
        closed_episode = (
            DocumentStateEpisode.objects.select_for_update()
            .select_related('state')
            .get(pk=closed_episode_id, document=note.document)
        )
        episode, _ = open_state(
            note.document,
            closed_episode.state,
            actor=actor,
            origin=DocumentStateEpisode.Origin.NOTE,
            idempotent=True,
        )
        note.episode = episode
        restored_episode_id = episode.id

    note.deleted_at = None
    note.deleted_by = None
    update_fields = ['deleted_at', 'deleted_by', 'updated_at']
    if restored_episode_id:
        update_fields.append('episode')
    note.save(update_fields=update_fields)
    DocumentNoteEvent.objects.create(
        document=note.document,
        note=note,
        event_type=DocumentNoteEvent.EventType.RESTORED,
        actor=actor,
        details=(
            {'restored_episode_id': restored_episode_id}
            if restored_episode_id
            else {}
        ),
    )
    return note, {
        'restored_episode_id': restored_episode_id,
        'state_reopened': bool(restored_episode_id),
    }
