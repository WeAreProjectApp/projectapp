"""One document identity, live proposal sources and immutable approval packages."""
from django.conf import settings
from django.db import models
from content.storage import get_private_storage


class ProposalApprovalPackage(models.Model):
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.PROTECT, related_name='approval_packages')
    number = models.PositiveIntegerField()
    request_id = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    source_hash = models.CharField(max_length=64)
    manifest = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-number']
        constraints = [
            models.UniqueConstraint(fields=['proposal', 'number'], name='unique_approval_package_number'),
            models.UniqueConstraint(fields=['proposal', 'request_id'], name='unique_approval_package_request'),
        ]


class ProposalDocumentBinding(models.Model):
    document = models.OneToOneField('content.Document', on_delete=models.PROTECT, related_name='proposal_binding')
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.PROTECT, related_name='document_bindings')
    source_key = models.CharField(max_length=100)
    source_document = models.ForeignKey('content.ProposalDocument', on_delete=models.PROTECT, null=True, blank=True)
    current_file = models.ForeignKey('content.ProposalApprovalFile', on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    draft_file = models.FileField(storage=get_private_storage, upload_to='proposal_drafts/%Y/%m/', max_length=500, blank=True)
    draft_filename = models.CharField(max_length=255, blank=True)
    draft_sha256 = models.CharField(max_length=64, blank=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['proposal', 'source_key'], name='unique_proposal_document_binding')]
