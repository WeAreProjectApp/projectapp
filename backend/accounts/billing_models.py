"""Project billing identity and evidence; financial sources remain unchanged."""
from django.conf import settings
from django.db import models

from content.models.history_tracked import HistoryTrackedModel


class ProjectHosting(models.Model):
    project = models.OneToOneField('accounts.Project', on_delete=models.PROTECT, related_name='billing_hosting')
    subscription = models.OneToOneField('accounts.HostingSubscription', on_delete=models.PROTECT, null=True, blank=True, related_name='billing_context')
    operational_accounting_source = models.OneToOneField('accounts.ProjectHostingAccountingSource', on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProjectHostingAccountingSource(models.Model):
    hosting = models.ForeignKey(ProjectHosting, on_delete=models.PROTECT, related_name='accounting_sources')
    hosting_record = models.OneToOneField('content.HostingRecord', on_delete=models.PROTECT, related_name='billing_source')
    created_at = models.DateTimeField(auto_now_add=True)


class CollectionAccountContext(HistoryTrackedModel):
    class Nature(models.TextChoices):
        CONTRACT = 'contract', 'Contrato'
        HOSTING = 'hosting', 'Hosting'

    document = models.OneToOneField('content.Document', on_delete=models.CASCADE, related_name='billing_context')
    nature = models.CharField(max_length=12, choices=Nature.choices)
    contract = models.ForeignKey('accounts.ProjectContract', on_delete=models.PROTECT, null=True, blank=True, related_name='collection_contexts')
    amendment = models.ForeignKey('accounts.ContractAmendment', on_delete=models.PROTECT, null=True, blank=True, related_name='collection_contexts')
    hosting = models.ForeignKey(ProjectHosting, on_delete=models.PROTECT, null=True, blank=True, related_name='collection_contexts')
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(nature='contract', contract__isnull=False, hosting__isnull=True)
                       | models.Q(nature='hosting', contract__isnull=True, amendment__isnull=True, hosting__isnull=False)),
            name='billing_account_exclusive_nature',
        )]


class HostingEvidenceGroup(models.Model):
    """Explicit equivalence of existing evidence, never a new financial entry."""
    hosting = models.ForeignKey(ProjectHosting, on_delete=models.PROTECT, related_name='evidence_groups')
    label = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class HostingEvidence(models.Model):
    group = models.ForeignKey(HostingEvidenceGroup, on_delete=models.PROTECT, related_name='evidence')
    payment = models.OneToOneField('accounts.Payment', on_delete=models.PROTECT, null=True, blank=True, related_name='billing_evidence')
    cycle = models.OneToOneField('content.HostingCycle', on_delete=models.PROTECT, null=True, blank=True, related_name='billing_evidence')
    document = models.OneToOneField('content.Document', on_delete=models.PROTECT, null=True, blank=True, related_name='hosting_evidence')

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(payment__isnull=False, cycle__isnull=True, document__isnull=True)
                       | models.Q(payment__isnull=True, cycle__isnull=False, document__isnull=True)
                       | models.Q(payment__isnull=True, cycle__isnull=True, document__isnull=False)),
            name='billing_evidence_one_reference',
        )]


class BillingContextEvent(models.Model):
    """Append-only administrative context decisions, separate from money."""
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='billing_context_events')
    document = models.ForeignKey('content.Document', on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_context_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    operation = models.CharField(max_length=64)
    reason = models.TextField()
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
