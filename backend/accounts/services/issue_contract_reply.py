"""Ticket-owned wrappers around P3's source, context and citation engine."""
from copy import deepcopy
from collections.abc import Mapping
from functools import partial

from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_contract_reply as core
from accounts.services.delivery_access import DeliveryConflict, fail, project_for_actor, require_admin
from accounts.services.issue_reports import get_ticket
from accounts.services.issue_review_context import contract_reply_target

PUBLIC_EVIDENCE_FIELDS = frozenset({
    'scope_result', 'human_reviewed', 'contract_id', 'prepared_at', 'source_text_not_shared',
})


def public_review_evidence(stored):
    """An allowlist also protects legacy JSON and future private provenance keys."""
    value = stored.get('public', stored) if isinstance(stored, dict) else {}
    if not isinstance(value, dict):
        return {}
    return {key: deepcopy(value[key]) for key in PUBLIC_EVIDENCE_FIELDS if key in value}


def _ticket(project_id, actor, kind, ticket_id, *, include_archived=False):
    from rest_framework import serializers
    serializers.ChoiceField(choices=('bug', 'change')).run_validation(kind)
    return get_ticket(project_id, actor, kind, ticket_id, include_archived=include_archived)


def _context(project_id, actor, kind, ticket_id, context_id):
    require_admin(actor)
    project = project_for_actor(project_id, actor)
    _ticket(project_id, actor, kind, ticket_id, include_archived=True)
    context = authoring.get_prompt_context(project_id, actor, context_id)
    destination = context.get('destination', {})
    if destination.get('kind') != kind or destination.get('id') != ticket_id:
        fail('La preparación pertenece a otro ticket.', 'context_destination')
    if destination.get('project_client_id') != project.client_id:
        raise DeliveryConflict('El cliente cambió; conserva la evidencia del propietario original.')
    return context


def reply_options(project_id, actor, kind, ticket_id):
    require_admin(actor)
    ticket = _ticket(project_id, actor, kind, ticket_id)
    options = authoring.prompt_options(project_id, actor)
    return {**{key: options[key] for key in (
        'version', 'contracts', 'amendments', 'documents', 'proposal_documents', 'warnings',
    )}, 'ticket_version': ticket.version}


def prepare_reply(project_id, actor, kind, ticket_id, data):
    require_admin(actor)
    _ticket(project_id, actor, kind, ticket_id)
    if not isinstance(data, Mapping):
        fail('La preparación debe ser un objeto de datos.', 'issue_reply_payload')
    if 'destination' in data:
        fail('El destino se obtiene del ticket seleccionado.', 'context_destination')
    return core.create_contract_reply_context(project_id, actor, {
        **data, 'destination': {'kind': kind, 'id': ticket_id},
    }, target_provider=partial(contract_reply_target, contract_id=data.get('contract_id')))


def get_reply_context(project_id, actor, kind, ticket_id, context_id):
    return _context(project_id, actor, kind, ticket_id, context_id)


def preview_reply(project_id, actor, kind, ticket_id, data):
    require_admin(actor)
    from accounts.serializers_issue_reports import IssueReplyPreviewFields
    serializer = IssueReplyPreviewFields(data=data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    context = _context(project_id, actor, kind, ticket_id, values['payload']['context_id'])
    return core.preview_contract_reply(
        project_id, actor, values['payload'], expected_version=values['expected_version'],
        expected_ticket_version=values['expected_ticket_version'],
        target_provider=partial(contract_reply_target, contract_id=context['contract_id']),
    )


def reply_source_file(project_id, actor, kind, ticket_id, context_id, source_key):
    _context(project_id, actor, kind, ticket_id, context_id)
    return authoring.prompt_source_file(project_id, actor, context_id, source_key)


def validate_reply(project, actor, kind, ticket, values):
    """Runs inside issue_reports._run, before inserting or changing any state."""
    review = values.get('contract_reply')
    if review is None:
        return None
    context = _context(project.pk, actor, kind, ticket.pk, review['context_id'])
    if values.get('contract_id') != context['contract_id']:
        fail('Conserva el contrato seleccionado al preparar la respuesta.', 'issue_contract_context')
    message = values.get('admin_response', '').strip()
    if not message:
        fail('Escribe la respuesta revisada antes de compartirla.', 'issue_message_required')
    result = core.validate_contract_reply_for_publish(project.pk, actor, {
        **review, 'message': message, 'destination': {'kind': kind, 'id': ticket.pk},
    }, target_provider=partial(contract_reply_target, contract_id=context['contract_id']))
    return {
        'scope_result': result['scope_result'],
        'review_evidence': {
            'public': public_review_evidence(result['review_evidence']),
            'private': {
                'context_id': result['context_id'],
                'source_references': deepcopy(result['source_references']),
                'classifications': deepcopy(result['classifications']),
                'reviewed_by': actor.pk, 'workspace_version': review['expected_version'],
                'ticket_version': review['expected_ticket_version'],
            },
        },
    }
