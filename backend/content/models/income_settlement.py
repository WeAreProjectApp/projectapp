"""An income settlement and the financial effects that must reverse together."""
import uuid

from django.conf import settings
from django.db import models


class IncomeSettlement(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Activa'
        REVERSED = 'reversed', 'Revertida'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    revision = models.PositiveIntegerField(default=1)
    pocket_movement = models.OneToOneField(
        'content.PocketMovement', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='income_settlement',
    )
    # JSON-safe monetary strings, input and effects are written only by the
    # settlement service. Effects retain tombstones after a reversal.
    input_snapshot = models.JSONField(default=dict)
    effects = models.JSONField(default=dict)
    revisions = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
