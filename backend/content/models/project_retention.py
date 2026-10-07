"""Durable client ownership without keeping an operational project alive."""
from django.conf import settings
from django.db import models


class ProjectRetentionContext(models.Model):
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    original_project_id = models.PositiveBigIntegerField(unique=True)
    project_name = models.CharField(max_length=200)
    retained_records = models.JSONField(default=dict)
    category_counts = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.project_name


class ProjectRetentionOperation(models.Model):
    """Audited exit from retention, with the ownership values needed to undo it.

    Project ids are plain integers on purpose: the audit must never block a
    later deletion of the project that received the records.
    """

    class Operation(models.TextChoices):
        ADOPT = 'adopt', 'Traslado a un proyecto vigente'
        UNDO = 'undo', 'Deshacer un traslado'
        DISCARD = 'discard', 'Descarte de contenedores vacíos'
        PROPOSAL_REASSIGNMENT = 'proposal_reassignment', 'Reasignación de propuesta'

    context = models.ForeignKey(
        ProjectRetentionContext, on_delete=models.PROTECT, related_name='operations',
    )
    operation = models.CharField(max_length=24, choices=Operation.choices)
    origin = models.CharField(max_length=40)
    target_project_id = models.PositiveBigIntegerField(null=True, blank=True)
    target_project_name = models.CharField(max_length=200, blank=True, default='')
    request_id = models.CharField(max_length=100, unique=True)
    payload_hash = models.CharField(max_length=64, blank=True, default='')
    reason = models.TextField(blank=True, default='')
    # [{model, id, before, after}] — ownership fields only, never contents.
    items = models.JSONField(default=list)
    # {model_label: [ids]} taken out of context.retained_records.
    removed_records = models.JSONField(default=dict)
    reverts = models.OneToOneField(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='reverted_by',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.get_operation_display()} · {self.context.project_name}'
