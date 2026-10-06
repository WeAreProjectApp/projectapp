"""Ticket-owned history; delivery publications and approvals remain untouched."""

from accounts.retention import RetainedProjectModel
from django.conf import settings
from django.db import models

from content.storage import get_private_storage


def _ticket_constraint(name):
    return models.CheckConstraint(
        condition=(models.Q(bug_report__isnull=False, change_request__isnull=True)
                   | models.Q(bug_report__isnull=True, change_request__isnull=False)),
        name=name,
    )


class IssueContext(RetainedProjectModel, models.Model):
    """Original published guide and its ancestry, captured once on submission."""
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, null=True, blank=True)
    bug_report = models.OneToOneField(
        'accounts.BugReport', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_context',
    )
    change_request = models.OneToOneField(
        'accounts.ChangeRequest', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_context',
    )
    publication = models.ForeignKey(
        'accounts.DeliveryPublication', null=True, blank=True,
        on_delete=models.PROTECT, related_name='issue_contexts',
    )
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [_ticket_constraint('issue_context_one_ticket')]


class IssueResponse(models.Model):
    """A team response is history, never an acceptance of a delivery guide."""
    bug_report = models.ForeignKey(
        'accounts.BugReport', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_responses',
    )
    change_request = models.ForeignKey(
        'accounts.ChangeRequest', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_responses',
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    message = models.TextField()
    status = models.CharField(max_length=25)
    is_internal = models.BooleanField(default=False)
    contract = models.ForeignKey(
        'accounts.ProjectContract', null=True, blank=True,
        on_delete=models.PROTECT, related_name='issue_responses',
    )
    scope_result = models.CharField(max_length=20, default='indeterminate', choices=[
        ('within_scope', 'Dentro del alcance'), ('outside_scope', 'Fuera del alcance'),
        ('indeterminate', 'Indeterminado'),
    ])
    # Populated only by the shared review adapter, never from client-supplied claims.
    review_evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [_ticket_constraint('issue_response_one_ticket')]


class IssueAttachment(models.Model):
    """Private, immutable PDF bytes attached to one response or existing comment."""
    response = models.ForeignKey(
        IssueResponse, null=True, blank=True, on_delete=models.CASCADE,
        related_name='attachments',
    )
    bug_comment = models.ForeignKey(
        'accounts.BugComment', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_attachments',
    )
    change_comment = models.ForeignKey(
        'accounts.ChangeRequestComment', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_attachments',
    )
    document = models.ForeignKey(
        'content.Document', on_delete=models.PROTECT, related_name='issue_attachments',
    )
    title = models.CharField(max_length=300)
    file = models.FileField(storage=get_private_storage, upload_to='issue_evidence/%Y/%m/')
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(
                models.Q(response__isnull=False, bug_comment__isnull=True, change_comment__isnull=True)
                | models.Q(response__isnull=True, bug_comment__isnull=False, change_comment__isnull=True)
                | models.Q(response__isnull=True, bug_comment__isnull=True, change_comment__isnull=False)
            ), name='issue_attachment_one_message',
        )]


class IssueEvent(RetainedProjectModel, models.Model):
    """Append-only state transitions and owned retry receipts."""
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, null=True, blank=True)
    bug_report = models.ForeignKey(
        'accounts.BugReport', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_events',
    )
    change_request = models.ForeignKey(
        'accounts.ChangeRequest', null=True, blank=True, on_delete=models.CASCADE,
        related_name='issue_events',
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    previous_status = models.CharField(max_length=25, blank=True, default='')
    status = models.CharField(max_length=25)
    is_internal = models.BooleanField(default=False)
    request_id = models.UUIDField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True, default='')
    receipt = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [
            _ticket_constraint('issue_event_one_ticket'),
            models.UniqueConstraint(fields=['project', 'actor', 'request_id'], name='issue_retry_receipt'),
        ]
