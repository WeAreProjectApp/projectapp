"""Audited correction of an existing proposal/project association."""
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, guarded_arguments, writable_schema
from content.mcp.protocol import ToolError
from rest_framework.exceptions import ValidationError
from content.serializers.proposal_project_reassignment import ProposalProjectReassignmentSerializer


PREVIEW = _op('preview_proposal_project_reassignment',
              'Revisa fases, recursos, archivos y bloqueos antes de trasladar la propuesta a otro proyecto del mismo cliente, también desde los datos conservados de un proyecto eliminado.',
              'proposal-project-reassignment', path=('proposal_id',))
HOSTING_OPTIONS = {
    'hosting_start_date': {'type': 'string', 'format': 'date',
                           'description': 'Nueva fecha de inicio de hosting para las fases trasladadas (AAAA-MM-DD).'},
    'accept_hosting_start': {'type': 'boolean',
                             'description': 'Acepta que una fase vencida empiece a cobrarse en el hosting activo del destino.'},
}
PREVIEW['input_schema']['properties']['target_project_id'] = {'type': 'integer', 'minimum': 1}
PREVIEW['input_schema']['properties'].update(HOSTING_OPTIONS)
PREVIEW['input_schema']['properties']['query'].update(properties={
    'target_project_id': {'type': 'integer', 'minimum': 1}, **HOSTING_OPTIONS,
}, additionalProperties=False)

REASSIGN = _op('reassign_proposal_project',
               'Corrige el proyecto conservando fases, recursos, archivos aprobados e historial (desde un proyecto eliminado, con los mismos ids); requiere impacto vigente, motivo y request_id estable.',
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
    validated = dict(serializer.validated_data)
    if validated.get('hosting_start_date'):
        # Confirmations store their arguments as JSON.
        validated['hosting_start_date'] = validated['hosting_start_date'].isoformat()
    return {**args, **validated}


def _preview(arguments):
    args = _prepare(arguments)
    query = {'proposal_id': args['proposal_id'], 'target_project_id': args['target_project_id']}
    if args.get('hosting_start_date'):
        query['hosting_start_date'] = args['hosting_start_date']
    if args.get('accept_hosting_start'):
        query['accept_hosting_start'] = 'true'
    return PREVIEW['handler'](query)


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
