"""Load a complete ticket conversation once for REST and MCP responses."""
from django.db.models import Prefetch

from accounts.models import (
    BugComment, BugReport, ChangeRequest, ChangeRequestComment, IssueEvent,
    IssueResponse,
)


def ticket_detail(ticket, kind):
    model, comment_model, author = {
        'bug': (BugReport, BugComment, 'reported_by'),
        'change': (ChangeRequest, ChangeRequestComment, 'created_by'),
    }[kind]
    return model.objects.select_related(
        author, 'source_requirement__stage__phase__scope', 'issue_context',
    ).prefetch_related(
        Prefetch(
            'comments',
            queryset=comment_model.objects.select_related('user').prefetch_related('issue_attachments'),
            to_attr='_detail_comments',
        ),
        Prefetch(
            'issue_responses',
            queryset=IssueResponse.objects.select_related('actor').prefetch_related('attachments'),
            to_attr='_issue_responses',
        ),
        Prefetch(
            'issue_events', queryset=IssueEvent.objects.select_related('actor'),
            to_attr='_issue_events',
        ),
    ).get(pk=ticket.pk, project_id=ticket.project_id)
