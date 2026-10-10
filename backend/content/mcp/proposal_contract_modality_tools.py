"""Owned MCP confirmations over the same contract plan as the panel."""
import logging

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.models import BusinessProposal
from content.serializers.proposal import ProposalDetailSerializer
from content.services import proposal_contract_modality as service

logger = logging.getLogger(__name__)

SERVICE_PARAMS = {'type': 'object', 'additionalProperties': False, 'properties': {
    key: {'oneOf': [{'type': 'integer', 'minimum': 1, 'maximum': 999}, {'type': 'string'}]}
    for key in ('service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days')
}}
CHANGE_PROPERTIES = {
    'contract_modality': {'type': 'string', 'enum': ['single', 'split']},
    'change_note': {'type': 'string', 'maxLength': 4000}, 'contract_params': SERVICE_PARAMS,
    'conflict_resolution': {'type': 'string', 'enum': ['use_origin']},
}


def _positive_id(identifier, field):
    if type(identifier) is int and 0 < identifier <= 9223372036854775807:
        return identifier
    if isinstance(identifier, str) and len(identifier) <= 19 and identifier.isascii() and identifier.isdigit():
        value = int(identifier)
        if 0 < value <= 9223372036854775807:
            return value
    raise ToolError(f'{field} debe ser un identificador entero positivo.')


def _proposal(identifier):
    identifier = _positive_id(identifier, 'proposal_id')
    try:
        return BusinessProposal.objects.get(pk=identifier)
    except BusinessProposal.DoesNotExist as exc:
        raise ToolError('No existe esa propuesta.', code='NOT_FOUND') from exc


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except service.ContractModalityError as exc:
        raise ToolError(str(exc), code=exc.code, details=exc.details) from exc


def _payload(arguments, *, restore=False):
    fields = {'snapshot_id', 'change_note'} if restore else set(CHANGE_PROPERTIES)
    allowed = {'proposal_id', 'data', *fields}
    if set(arguments) - allowed or not isinstance(arguments.get('data', {}), dict):
        raise ToolError('Hay argumentos desconocidos.')
    payload = dict(arguments.get('data', {}))
    if 'data' in arguments:
        name = 'restore_proposal_contract_snapshot' if restore else 'update_proposal_contract_modality'
        logger.info('[MCP] deprecated_envelope tool=%s keys=%s', name, sorted({'data'}))
    if set(payload) - fields:
        raise ToolError('Hay campos no editables en data.')
    for field in fields & set(arguments):
        if field in payload and payload[field] != arguments[field]:
            raise ToolError(f'{field} y data.{field} deben coincidir.')
        payload[field] = arguments[field]
    return payload


def _prepare(arguments, *, restore=False):
    proposal = _proposal(arguments.get('proposal_id'))
    plan = _run(service.prepare, proposal, _payload(arguments, restore=restore), restore=restore)
    return {'proposal_id': proposal.pk, **plan['arguments'], '_expected_hash': plan['source_hash']}


def _impact(arguments, *, restore=False):
    public = {key: value for key, value in arguments.items() if key != '_expected_hash'}
    proposal = _proposal(public.pop('proposal_id'))
    return {'summary': 'Cambia los contratos de esta propuesta, conserva los anteriores y no envía documentos.',
            **_run(service.prepare, proposal, public, restore=restore)}


def _etags(arguments):
    return {'proposal_contracts': _run(service.resource_hash, _proposal(arguments.get('proposal_id')))}


def _needs_confirmation(arguments):
    proposal = _proposal(arguments.get('proposal_id'))
    payload = _payload(arguments)
    return proposal.status != 'negotiating' and payload.get('contract_modality') != proposal.contract_modality


def _apply(arguments, *, restore=False):
    arguments = dict(arguments)
    context = current_mcp_context()
    confirmed = bool(context and context.confirmation_bypass)
    if '_expected_hash' in arguments and not confirmed:
        raise ToolError('La confirmación pertenece al servidor.', code='FORBIDDEN')
    expected = arguments.pop('_expected_hash', None)
    proposal = _proposal(arguments.get('proposal_id'))
    proposal, outcome = _run(service.apply, proposal.pk, _payload(arguments, restore=restore), actor=mcp_actor(),
                            confirmed=confirmed, expected_hash=expected, restore=restore)
    return {**ProposalDetailSerializer(proposal, context={'is_admin': True}).data, 'contract_change': outcome}


def configure_modality_tool(tool):
    tool.update(risk='sensitive', requires_confirmation=True,
        confirmation_predicate=_needs_confirmation, prepare_arguments=_prepare,
        impact_builder=_impact, etag_resolver=_etags, handler=_apply,
        description='Cambia single/split en cualquier estado. Fuera de negociación exige change_note y devuelve una vista previa para confirm_action o cancel_action. Conserva personalizados y documentos anteriores; split exige los tres plazos del servicio.')
    tool['input_schema'] = {'type': 'object', 'additionalProperties': False,
        'properties': {'proposal_id': {'type': 'integer', 'minimum': 1}, **CHANGE_PROPERTIES},
        'required': ['proposal_id', 'contract_modality']}
    tool['accepted_arguments_schema'] = {**tool['input_schema'],
        'properties': {**tool['input_schema']['properties'],
            'data': {'type': 'object', 'additionalProperties': False, 'properties': CHANGE_PROPERTIES}},
        'required': ['proposal_id']}


RESTORE_PROPERTIES = {'snapshot_id': {'type': 'integer', 'minimum': 1},
    'change_note': {'type': 'string', 'minLength': 1, 'maxLength': 4000}}


def _list(arguments):
    if set(arguments) - {'proposal_id', 'offset'}:
        raise ToolError('Hay argumentos desconocidos.')
    offset = arguments.get('offset', 0)
    if type(offset) is not int or offset < 0:
        raise ToolError('offset debe ser un entero positivo o cero.')
    from content.views.proposal_contract_modality import snapshot_summary
    rows = _proposal(arguments.get('proposal_id')).contract_snapshots.all()
    return {'total': rows.count(), 'snapshots': [snapshot_summary(row) for row in rows[offset:offset + 20]]}


def _read(arguments):
    if set(arguments) != {'proposal_id', 'snapshot_id'}:
        raise ToolError('Indica proposal_id y snapshot_id.')
    proposal = _proposal(arguments['proposal_id'])
    identifier = _positive_id(arguments['snapshot_id'], 'snapshot_id')
    row = _run(service._restore_snapshot, proposal, identifier)
    from content.views.proposal_contract_modality import snapshot_summary
    return {**snapshot_summary(row), 'payload': row.payload}


CONTRACT_SNAPSHOT_TOOLS = [
    {'name': 'list_proposal_contract_snapshots', 'risk': 'read',
     'description': 'Lista las instantáneas permanentes de contratos, con autor, nota, fecha y modalidades; páginas de 20 filas.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {
         'proposal_id': {'type': 'integer', 'minimum': 1}, 'offset': {'type': 'integer', 'minimum': 0}}, 'required': ['proposal_id']}, 'handler': _list},
    {'name': 'read_proposal_contract_snapshot', 'risk': 'read',
     'description': 'Lee modalidad, parámetros y Markdown literal de los contratos anteriores conservados en una instantánea de esta propuesta.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {
         'proposal_id': {'type': 'integer', 'minimum': 1}, 'snapshot_id': {'type': 'integer', 'minimum': 1}}, 'required': ['proposal_id', 'snapshot_id']}, 'handler': _read},
    {'name': 'restore_proposal_contract_snapshot', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza restaurar contratos de una instantánea sin cambiar el estado comercial. Exige nota; confirm_action restaura y conserva primero el estado actual.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {
         'proposal_id': {'type': 'integer', 'minimum': 1}, **RESTORE_PROPERTIES}, 'required': ['proposal_id', 'snapshot_id', 'change_note']},
     'prepare_arguments': lambda args: _prepare(args, restore=True), 'impact_builder': lambda args: _impact(args, restore=True),
     'etag_resolver': _etags, 'handler': lambda args: _apply(args, restore=True)},
]

CONTRACT_SNAPSHOT_TOOLS[-1]['accepted_arguments_schema'] = {
    **CONTRACT_SNAPSHOT_TOOLS[-1]['input_schema'],
    'properties': {**CONTRACT_SNAPSHOT_TOOLS[-1]['input_schema']['properties'],
        'data': {'type': 'object', 'additionalProperties': False, 'properties': RESTORE_PROPERTIES}},
    'required': ['proposal_id'],
}
