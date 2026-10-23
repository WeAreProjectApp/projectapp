from content.models.editorial_text import EditorialTextModel
from django.conf import settings
from django.db import models

from content.models.history_tracked import HistoryTrackedModel


class DocumentNote(EditorialTextModel, HistoryTrackedModel):
    """Private, actionable note that may explain a state episode."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Pendiente'
        RESOLVED = 'resolved', 'Resuelta'
        DISCARDED = 'discarded', 'Descartada'

    document = models.ForeignKey(
        'content.Document',
        on_delete=models.CASCADE,
        related_name='document_notes',
    )
    episode = models.ForeignKey(
        'content.DocumentStateEpisode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes',
    )
    title = models.CharField(max_length=120, blank=True, default='')
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.OPEN,
    )
    resolution_note = models.CharField(max_length=500, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_at_known = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('order', 'created_at', 'id')
        indexes = [
            models.Index(fields=('document', 'deleted_at', 'status')),
            models.Index(fields=('episode', 'deleted_at', 'status')),
        ]

    def __str__(self):
        return self.title or self.content[:60]


class DocumentNoteEvent(models.Model):
    """Append-only audit entry without a snapshot of note content."""

    class EventType(models.TextChoices):
        DELETED = 'deleted', 'Eliminada'
        RESTORED = 'restored', 'Restaurada'

    document = models.ForeignKey(
        'content.Document',
        on_delete=models.CASCADE,
        related_name='document_note_events',
    )
    note = models.ForeignKey(
        DocumentNote,
        on_delete=models.SET_NULL,
        null=True,
        related_name='events',
    )
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-recorded_at', '-id')
        indexes = [models.Index(fields=('document', 'recorded_at'))]

    def __str__(self):
        return f'{self.note_id} — {self.event_type}'
