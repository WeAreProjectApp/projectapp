"""Immutable, private copies of the operator-confirmed project package."""
from django.conf import settings
from django.db import models
from content.storage import get_private_storage


class ProposalApprovalFile(models.Model):
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.PROTECT, related_name='approval_files')
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='proposal_approval_files')
    deliverable = models.ForeignKey('accounts.Deliverable', on_delete=models.PROTECT, related_name='proposal_approval_files')
    package = models.ForeignKey('content.ProposalApprovalPackage', on_delete=models.PROTECT, null=True, related_name='files')
    binding = models.ForeignKey('content.ProposalDocumentBinding', on_delete=models.PROTECT, null=True, related_name='revisions')
    source_key = models.CharField(max_length=100)
    title = models.CharField(max_length=300)
    document_type = models.CharField(max_length=30)
    filename = models.CharField(max_length=255)
    file = models.FileField(storage=get_private_storage, upload_to='proposal_approvals/%Y/%m/', max_length=500)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'documento del cierre de propuesta'
        verbose_name_plural = 'Documentos del cierre de propuestas'
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['package', 'source_key'], name='unique_package_approval_source')]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values('file', 'sha256', 'size').first()
            if old and (old['file'] != self.file.name or old['sha256'] != self.sha256 or old['size'] != self.size):
                raise ValueError('Approved bytes cannot be overwritten.')
        return super().save(*args, **kwargs)
