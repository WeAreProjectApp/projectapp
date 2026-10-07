"""Audited correction of an existing proposal/project association."""
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, guarded_arguments, writable_schema
from content.mcp.protocol import ToolError
from rest_framework.exceptions import ValidationError
from content.serializers.proposal_project_reassignment import ProposalProjectReassignmentSerializer


PREVIEW = _op('preview_proposal_project_reassignment',
              'Revisa fases, recursos, archivos y bloqueos antes de trasladar la propuesta a otro proyecto del mismo cliente.',
              'proposal-project-reassignment', path=('proposal_id',))
PREVIEW['input_schema']['properties']['target_project_id'] = {'type': 'integer', 'minimum': 1}
PREVIEW['input_schema']['properties']['query'].update(properties={
    'target_project_id': {'type': 'integer', 'minimum': 1},
}, additionalProperties=False)

REASSIGN = _op('reassign_proposal_project',
               'Corrige el proyecto conservando fases, recursos, archivos aprobados e historial; requiere impacto vigente, motivo y request_id estable.',
               'proposal-project-reassignment', 'POST', ('proposal_id',), 'sensitive', True,
               payload_schema=writable_schema(ProposalProjectReassignmentSerializer))
REASSIGN['input_schema']['anyOf'] = [
    {'required': ['data']},
    {'required': ['target_project_id', 'reason', 'expected_impact_hash', 'request_id']},
]


def _prepare(arguments):
    check_known_fields(arguments, REASSIGN['input_schema'])
    arguments = guarded_arguments(arguments, REASSIGN)
    data = arguments.pop('data', {})
    args = {**arguments, **data}
    serializer = ProposalProjectReassignmentSerializer(data={
        key: value for key, value in args.items()
        if key in REASSIGN['_panel_operation']['payload_schema']['properties']
    })
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        raise ToolError('Revisa los datos de la reasignación.', details=exc.detail) from exc
    return {**args, **serializer.validated_data}


def _preview(arguments):
    args = _prepare(arguments)
    return PREVIEW['handler']({'proposal_id': args['proposal_id'], 'target_project_id': args['target_project_id']})


def _impact(arguments):
    args = _prepare(arguments)
    impact = _preview(args)
    if impact['impact_hash'] != args['expected_impact_hash']:
        raise ToolError('Las relaciones cambiaron. Revisa otra vez el impacto.', code='STALE_VERSION')
    if impact['blockers']:
        raise ToolError('Resuelve las dependencias antes de reasignar.', code='CONFLICT', details={'blockers': impact['blockers']})
    return {**impact, 'reason': args['reason'], 'financial_effect': 'none'}


REASSIGN['prepare_arguments'] = _prepare
REASSIGN['impact_builder'] = _impact
REASSIGN['etag_resolver'] = lambda arguments: {'proposal_project': _preview(arguments)['impact_hash']}
PROPOSAL_PROJECT_TOOLS = [PREVIEW, REASSIGN]
