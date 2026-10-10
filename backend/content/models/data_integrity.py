"""Append-only log of data-integrity fixes, with the values an exact undo needs."""
from django.conf import settings
from django.db import models


class DataIntegrityOperationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError('Data integrity operations are append-only.')


class DataIntegrityOperation(models.Model):
    """One applied batch of fixes (``apply``) or the exact reversal of one (``undo``).

    ``steps`` holds ``[{fingerprint, rule_id, rule_version, fix_kind, params,
    subjects, guards, items: [{model, pk, field, before, after, guard}]}]``:
    field values only, never document contents or secrets. ``history_operation_id``
    links the entity revisions written by the same request.
    """

    class Kind(models.TextChoices):
        APPLY = 'apply', 'Corrección'
        UNDO = 'undo', 'Deshacer una corrección'

    kind = models.CharField(max_length=8, choices=Kind.choices)
    source = models.CharField(max_length=64)
    catalog_version = models.CharField(max_length=20)
    scope = models.JSONField(default=dict)
    request_id = models.CharField(max_length=100, unique=True)
    payload_hash = models.CharField(max_length=64)
    impact_hash = models.CharField(max_length=64)
    reason = models.TextField()
    steps = models.JSONField(default=list)
    history_operation_id = models.UUIDField(null=True, blank=True)
    reverts = models.OneToOneField(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='reverted_by',
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DataIntegrityOperationQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-id']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError('Data integrity operations are append-only.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_kind_display()} #{self.pk}'
