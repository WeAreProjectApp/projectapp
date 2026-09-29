"""Short-lived private preparations, separate from immutable delivery evidence."""
import uuid

from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from content.storage import get_private_storage


class ProposalFormalization(models.Model):
    class Status(models.TextChoices):
        PREPARED = 'prepared', 'Preparado'
        SENDING = 'sending', 'Enviando'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Fallido'
        UNKNOWN = 'unknown', 'Entrega incierta'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.CASCADE, related_name='formalizations')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mcp_credential = models.ForeignKey(
        'content.McpCredential', on_delete=models.PROTECT, null=True, blank=True,
        related_name='proposal_formalizations',
    )
    payload = models.JSONField(default=dict)
    source_hash = models.CharField(max_length=64)
    html_body = models.TextField()
    text_body = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PREPARED)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)


class ProposalFormalizationFile(models.Model):
    preparation = models.ForeignKey(ProposalFormalization, on_delete=models.CASCADE, related_name='files')
    key = models.CharField(max_length=50)
    filename = models.CharField(max_length=255)
    description = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100)
    file = models.FileField(storage=get_private_storage, upload_to='formalizations/%Y/%m/', max_length=500)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['preparation', 'key'], name='unique_formalization_file_key')]


@receiver(post_delete, sender=ProposalFormalizationFile)
def delete_preparation_file(sender, instance, **kwargs):
    """Also remove private files when their proposal is deleted."""
    if instance.file:
        storage, name = instance.file.storage, instance.file.name
        transaction.on_commit(lambda: storage.delete(name))
