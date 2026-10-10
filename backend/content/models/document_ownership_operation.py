"""Durable receipts for document-tree migrations and their exact reversal."""

from typing import ClassVar

from django.conf import settings
from django.db import models


class DocumentOwnershipOperation(models.Model):
    class Kind(models.TextChoices):
        MIGRATION = 'migration', 'Migración'
        ADOPTION = 'adoption', 'Adopción'
        UNDO = 'undo', 'Deshacer'

    class Origin(models.TextChoices):
        MCP = 'mcp', 'MCP'
        PANEL = 'panel', 'Panel'
        AUTO = 'auto', 'Automática'

    kind = models.CharField(max_length=12, choices=Kind.choices)
    origin = models.CharField(max_length=8, choices=Origin.choices)
    request_id = models.CharField(max_length=100, unique=True)
    plan_hash = models.CharField(max_length=64)
    input = models.JSONField(default=dict)
    reason = models.TextField()
    # Only ownership, placement and archive values; never mutable contents or updated_at.
    items = models.JSONField(default=list)
    created_folder_ids = models.JSONField(default=list)
    deleted_folder_snapshots = models.JSONField(default=list)
    # A receipt must survive the eventual deletion of the project it created.
    created_project_id = models.PositiveBigIntegerField(null=True, blank=True)
    report = models.JSONField(default=dict)
    reverts = models.OneToOneField(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='reverted_by',
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    credential = models.ForeignKey(
        'content.McpCredential', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ['-created_at', '-id']

    def __str__(self):
        return f'{self.get_kind_display()} · {self.request_id}'
