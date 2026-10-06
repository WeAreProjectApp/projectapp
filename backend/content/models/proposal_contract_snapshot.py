"""Permanent, immutable recovery points for proposal contract changes."""
import uuid

from django.conf import settings
from django.db import models

from content.models.entity_history import RevisionQuerySet


class ImmutableContractRecord(models.Model):
    objects = RevisionQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Contract snapshots cannot be edited.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Contract snapshots cannot be deleted.')


class ProposalContractSnapshot(ImmutableContractRecord):
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.PROTECT,
                                 related_name='contract_snapshots')
    payload = models.JSONField(default=dict)
    actor_id_snapshot = models.PositiveBigIntegerField(null=True)
    actor_label = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    change_note = models.TextField(blank=True)
    from_modality = models.CharField(max_length=8)
    to_modality = models.CharField(max_length=8)
    restored_from_id = models.PositiveBigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class ProposalContractSnapshotFile(ImmutableContractRecord):
    snapshot = models.ForeignKey(ProposalContractSnapshot, on_delete=models.PROTECT,
                                 related_name='files')
    source_document_id = models.PositiveBigIntegerField()
    pdf_content = models.BinaryField()
    sha256 = models.CharField(max_length=64)


class ProposalContractChangeIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    arguments = models.JSONField(default=dict)
    source_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=12, default='pending')
    expires_at = models.DateTimeField()
    result = models.JSONField(null=True)
