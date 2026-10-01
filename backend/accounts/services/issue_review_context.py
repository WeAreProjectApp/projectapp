"""Server-owned ticket input for the shared contractual review provider."""
from copy import deepcopy

from django.db import transaction
from rest_framework import serializers

from accounts.services.delivery_access import DeliveryConflict, fail, project_for_actor, require_admin
from accounts.services.issue_context import applicable_contract, original_context
from accounts.services.issue_reports import CREATE_FIELDS, MODELS, get_ticket


def _capture(project, kind, ticket, contract_id=None, request_id=None):
    contract = applicable_contract(project, ticket, contract_id)
    responses = list(ticket.issue_responses.filter(is_internal=False).prefetch_related('attachments'))
    applicable_responses = [response for response in responses
                            if contract is None or response.contract_id in (None, contract.pk)]
    comments = list(ticket.comments.filter(is_internal=False).prefetch_related('issue_attachments'))
    events = list(ticket.issue_events.filter(is_internal=False))
    response_versions = {event.receipt.get('response_id'): event.receipt.get('ticket_version')
                         for event in events if event.receipt.get('response_id')}
    comment_versions = {event.receipt.get('comment_id'): event.receipt.get('ticket_version')
                        for event in events if event.receipt.get('comment_id')}
    report = {field: deepcopy(getattr(ticket, field))
              for field in CREATE_FIELDS[kind] if field != 'screenshot'}
    conversation = [{
        'source_type': 'bug_report' if kind == 'bug' else 'change_request',
        'source_id': ticket.pk,
        'actor_id': ticket.reported_by_id if kind == 'bug' else ticket.created_by_id,
        'created_at': ticket.created_at.isoformat(), 'report': report,
        'screenshot_present': bool(ticket.screenshot), 'captured_ticket_version': ticket.version,
    }]
    conversation.extend({
        'source_type': 'issue_response', 'source_id': response.pk,
        'actor_id': response.actor_id, 'created_at': response.created_at.isoformat(),
        'content': response.message, 'status': response.status,
        'contract_id': response.contract_id, 'version': response_versions.get(response.pk),
        'attachments': _attachments(response.attachments.all()),
    } for response in applicable_responses)
    conversation.extend({
        'source_type': 'bug_comment' if kind == 'bug' else 'change_request_comment',
        'source_id': comment.pk, 'actor_id': comment.user_id,
        'created_at': comment.created_at.isoformat(), 'content': comment.content,
        'version': comment_versions.get(comment.pk),
        'attachments': _attachments(comment.issue_attachments.all()),
    } for comment in comments)
    conversation.sort(key=lambda entry: (entry['created_at'], entry['source_type'], entry['source_id']))
    return {
        'project_id': project.pk, 'kind': kind, 'ticket_id': ticket.pk,
        'ticket_version': ticket.version, 'request_id': str(request_id) if request_id else None,
        'applicable_contract': {'id': contract.pk, 'version': contract.version} if contract else None,
        'origin_context': deepcopy(original_context(ticket)),
        'status': ticket.status, 'conversation': conversation,
        # Legacy text is server-owned, but its original author/time are unknown.
        'legacy_response': ticket.admin_response if not responses else None,
        'history': [{
            'event_id': event.pk, 'actor_id': event.actor_id,
            'created_at': event.created_at.isoformat(), 'action': event.action,
            'previous_status': event.previous_status, 'status': event.status,
            'version': event.receipt.get('ticket_version'),
        } for event in events],
    }


def _attachments(items):
    return [{
        'attachment_id': item.pk, 'document_id': item.document_id,
        'title': item.title, 'sha256': item.sha256,
    } for item in items]


def build_ticket_review_input(project_id, actor, kind, ticket_id, *,
                            ticket_version, request_id, contract_id=None):
    """Capture only a real ticket's public conversation at the requested version.

    No caller-provided origin, conversation, document bytes or scope decisions
    are accepted. A missing explicit contract remains missing for the provider
    to classify as indeterminate; the ticket itself may be entirely general.
    The shared provider must enforce this version again when applying a reply.
    """
    require_admin(actor)
    if kind not in MODELS:
        fail('Indica el tipo de ticket.', 'issue_kind')
    version = serializers.IntegerField(min_value=0).run_validation(ticket_version)
    operation_id = serializers.UUIDField().run_validation(request_id)
    selected_id = serializers.IntegerField(min_value=1, allow_null=True).run_validation(contract_id)
    with transaction.atomic():
        # All ticket mutations lock the project before the ticket, so collection
        # cannot interleave with an evaluation, comment or reopen operation.
        project = project_for_actor(project_id, actor, lock=True)
        ticket = get_ticket(project_id, actor, kind, ticket_id, lock=True)
        if ticket.version != version:
            raise DeliveryConflict('El ticket cambió. Actualiza antes de preparar la respuesta.')
        return _capture(project, kind, ticket, selected_id, operation_id)


def contract_reply_target(*, project, actor, destination, lock=False, contract_id=None):
    """P3 provider: project is locked by core before requesting a ticket lock."""
    require_admin(actor)
    kind = destination['kind']
    if kind not in MODELS:
        fail('Indica el tipo de ticket.', 'issue_kind')
    ticket = get_ticket(project.pk, actor, kind, destination['id'], lock=lock)
    captured = _capture(project, kind, ticket, contract_id)
    return {
        'kind': kind, 'id': ticket.pk, 'project_id': ticket.project_id,
        'project_client_id': project.client_id, 'ticket_version': ticket.version,
        'is_archived': ticket.is_archived, 'origin': captured['origin_context'],
        'ticket': {'title': ticket.title, 'status': ticket.status, 'version': ticket.version,
                   'legacy_response': captured['legacy_response']},
        'conversation': {'messages': captured['conversation'], 'history': captured['history']},
    }
