"""Contractual replies for tickets through a narrow, provider-owned boundary.

The provider reads its own ticket domain; this module never imports ticket
models, changes states, posts responses, sends messages or grants approvals.
Sources, extraction, frozen contexts and citations use delivery_authoring.
"""
import copy
import hashlib

from django.db import transaction
from rest_framework.exceptions import NotFound

from accounts.services import delivery_authoring as authoring
from accounts.services.delivery_access import DeliveryConflict, fail, project_for_actor, require_admin


def _hash(value):
    return hashlib.sha256(authoring._json_bytes(value)).hexdigest()


def capture_destination(project, actor, values, target_provider, *, lock=False):
    """Provider signature: (project, actor, destination, *, lock) -> snapshot.

    Required snapshot keys: kind, id, project_id, project_client_id,
    ticket_version, is_archived, origin, conversation; optional ticket carries
    report fields. Snapshots originate on the server, never in request JSON.
    """
    if not callable(target_provider):
        fail('La revisión contractual de tickets no está disponible.', 'reply_provider_unavailable')
    target = values['destination']
    raw = target_provider(project=project, actor=actor, destination=copy.deepcopy(target), lock=lock)
    if not isinstance(raw, dict) or not all(key in raw for key in (
        'kind', 'id', 'project_id', 'project_client_id', 'ticket_version', 'is_archived', 'origin', 'conversation',
    )):
        fail('El destino no incluye su identidad y conversación congelables.', 'reply_destination_snapshot')
    if (raw['kind'] != target['kind'] or raw['id'] != target['id'] or raw['project_id'] != project.pk
            or raw['project_client_id'] != project.client_id):
        raise NotFound('Ticket no encontrado en el proyecto y cliente actuales.')
    if raw['is_archived'] is not False:
        fail('El ticket está archivado; no prepares una respuesta contractual nueva.', 'reply_destination_archived')
    if type(raw['ticket_version']) is not int or raw['ticket_version'] != values['expected_ticket_version']:
        raise DeliveryConflict('El ticket cambió. Revisa su versión antes de preparar o compartir la respuesta.')
    if not isinstance(raw['origin'], dict) or not isinstance(raw['conversation'], (dict, list)):
        fail('El origen y la conversación del ticket deben estar estructurados.', 'reply_destination_snapshot')
    if raw['origin'].get('project_id', project.pk) != project.pk:
        raise NotFound('El origen pertenece a otro proyecto.')
    content = copy.deepcopy({'origin': raw['origin'], 'ticket': raw.get('ticket', {}),
                             'conversation': raw['conversation']})
    identity = {key: raw[key] for key in ('kind', 'id', 'project_id', 'project_client_id', 'ticket_version')}
    identity.update(origin_sha256=_hash(content['origin']), conversation_sha256=_hash(content))
    return {'identity': identity, 'origin': content['origin'], 'content': content}


def create_contract_reply_context(project_id, actor, data, *, target_provider):
    """Freeze ticket evidence and an explicit optional contractual selection."""
    if not callable(target_provider):
        fail('La revisión contractual de tickets no está disponible.', 'reply_provider_unavailable')
    return authoring.create_prompt_context(project_id, actor, data, target_provider=target_provider)


def _revalidated_context(project_id, actor, context_id, expected_version, expected_ticket_version,
                         target_provider, *, lock=False):
    context = authoring._context_for_actor(project_id, actor, context_id)
    if context.mode != 'reply' or not context.destination or context.stage_id:
        fail('Selecciona un contexto preparado para este ticket.', 'context_mode')
    if context.actor_id != actor.pk:
        fail('La preparación pertenece a otro administrador.', 'context_owner')
    if lock:
        if not transaction.get_connection().in_atomic_block:
            fail('Valida la respuesta dentro de la operación bloqueada del ticket.', 'reply_transaction_required')
        context.project = project_for_actor(project_id, actor, lock=True)
    if context.client_id != context.project.client_id:
        raise DeliveryConflict('El cliente del proyecto cambió; no reutilices evidencia del propietario anterior.')
    version = authoring._workspace_version(context.project)
    if type(expected_version) is not int or expected_version != version:
        raise DeliveryConflict()
    values = {'destination': {key: context.destination[key] for key in ('kind', 'id')},
              'expected_ticket_version': expected_ticket_version}
    live = capture_destination(context.project, actor, values, target_provider, lock=lock)
    if live['identity'] != context.destination:
        raise DeliveryConflict('El origen o la conversación del ticket cambió. Prepara un contexto actualizado.')
    if context.contract_id:
        origin_contract = live['origin'].get('contract_id')
        if origin_contract and origin_contract != context.contract_id:
            fail('El contexto no conserva el contrato del origen del ticket.', 'context_scope')
    return context, version


def preview_contract_reply(project_id, actor, payload, *, expected_version, expected_ticket_version, target_provider):
    """No writes, notifications or ticket conversions; citations use core."""
    require_admin(actor)
    values = authoring._validate(authoring.ReplyPayloadSerializer, payload)
    context, version = _revalidated_context(project_id, actor, values['context_id'], expected_version,
                                            expected_ticket_version, target_provider)
    result = authoring._preview_contract_reply(context, values, version)
    return {**result, 'destination': copy.deepcopy(context.destination), 'ticket_version': expected_ticket_version}


def validate_contract_reply_for_publish(project_id, actor, data, *, target_provider):
    """Call inside P1's project→ticket locked mutation, before response insert.

    Return private provenance separately from the safe public review_evidence.
    A caller must persist the private context ID/refs without serializing them
    through an unrestricted client-facing evidence JSON field.
    """
    require_admin(actor)
    if data.get('human_reviewed') is not True:
        fail('Revisa el texto y las fuentes antes de compartir la respuesta.', 'human_review_required')
    values = authoring._validate(authoring.ReplyPayloadSerializer, {
        'schema_version': 2, 'context_id': data.get('context_id'),
        'response_text': data.get('message'), 'classifications': data.get('classifications', []),
    })
    context, version = _revalidated_context(project_id, actor, values['context_id'], data.get('expected_version'),
                                            data.get('expected_ticket_version'), target_provider, lock=True)
    destination = data.get('destination')
    if destination != {key: context.destination[key] for key in ('kind', 'id')}:
        fail('La respuesta debe conservar el destino del contexto.', 'context_destination')
    result = authoring._preview_contract_reply(context, values, version)
    provided = authoring.validate_references(context, data.get('source_references', []))
    if provided != result['source_references']:
        fail('Conserva las citas verificadas de la respuesta.', 'citation_message')
    kinds = {item['classification'] for item in result['classifications']}
    classification = next(iter(kinds)) if len(kinds) == 1 else 'indeterminate'
    scope_result = 'within_scope' if classification == 'inside_scope' else classification
    public_evidence = {
        'scope_result': scope_result, 'human_reviewed': True,
        'contract_id': context.contract_id, 'prepared_at': context.created_at.isoformat(),
        'source_text_not_shared': True,
    }
    return {
        'context': context, 'context_id': str(context.pk), 'contract_id': context.contract_id,
        'source_references': result['source_references'], 'classifications': result['classifications'],
        'scope_result': scope_result, 'review_evidence': public_evidence,
    }
