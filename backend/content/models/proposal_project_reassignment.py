"""Durable administrative routing events; source projects may later be removed."""
from django.conf import settings
from django.db import models


class ProposalProjectReassignment(models.Model):
    proposal = models.ForeignKey('content.BusinessProposal', on_delete=models.PROTECT, related_name='project_reassignments')
    request_id = models.CharField(max_length=100, unique=True)
    payload_hash = models.CharField(max_length=64)
    source_project_id = models.PositiveBigIntegerField()
    target_project_id = models.PositiveBigIntegerField()
    reason = models.TextField()
    impact = models.JSONField()
    result = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
