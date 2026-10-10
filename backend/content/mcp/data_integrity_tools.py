"""Data-integrity tools of the projects connector: catalog, findings, fixes, log and undo.

Fixes and undos require the current preview's impact hash, a reason and a
stable request_id, and always go through the confirmation step, exactly like
the retention exits (``project_retention_tools``): MCP never skips the preview.
"""
from copy import deepcopy

from rest_framework.exceptions import ValidationError

from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, guarded_arguments, writable_schema
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import closed_object, open_object
from content.serializers.data_integrity import FixApplySerializer, FixPreviewSerializer, UndoSerializer

RULES = _op(
    'describe_integrity_rules',
    'Describe el catálogo versionado de reglas de integridad de datos: qué revisa cada regla (clientes, '
    'proyectos, documentos, comunicaciones, contabilidad, propuestas y nombres), su gravedad y cómo se corrige.',
    'panel-data-integrity-rules',
)
FINDINGS = _op(
    'list_integrity_findings',
    'Busca datos huérfanos, duplicados e inconsistentes. query.scope_kind (all, client, project, proposal, '
    'document, thread) con query.scope_id, o query.scope_query (texto) para un cliente o proyecto: si no hay '
    'exactamente una coincidencia devuelve scope_candidates. query.domains, query.rule_ids y query.severity '
    'filtran (separados por comas); query.page pagina de a 50. Cada hallazgo trae fingerprint, entradas a '
    'elegir, sugerencia y, si aplica, la herramienta existente que lo corrige.',
    'panel-data-integrity-findings',
)
PREVIEW = _op(
    'preview_integrity_fixes',
    'Calcula sin escribir qué cambiaría un lote de hasta 20 correcciones (scope y fixes con fingerprint, '
    'rule_id, fix_kind opcional y params), sus bloqueos y el impact_hash que exige apply_integrity_fixes.',
    'panel-data-integrity-fix-preview', 'POST', payload_schema=writable_schema(FixPreviewSerializer),
)
APPLY = _op(
    'apply_integrity_fixes',
    'Aplica un lote de correcciones de integridad revisado. Requiere el impact_hash vigente de '
    'preview_integrity_fixes con el mismo scope y fixes, un motivo y un request_id estable; queda '
    'registrado con valores antes/después y se puede deshacer.',
    'panel-data-integrity-fix-apply', 'POST', risk='sensitive', confirm=True,
    payload_schema=writable_schema(FixApplySerializer),
)
OPERATIONS = _op(
    'list_integrity_operations',
    'Lista el registro de correcciones de integridad y sus deshacer, de la más reciente a la más antigua; '
    'query.rule_id filtra por regla y query.page pagina de a 20.',
    'panel-data-integrity-operations',
)
UNDO_PREVIEW = _op(
    'preview_integrity_operation_undo',
    'Revisa si una corrección de integridad se puede deshacer exactamente (nada cambió después) y qué '
    'registros volverían a su valor anterior.',
    'panel-data-integrity-operation-undo', path=('operation_id',),
)
UNDO = _op(
    'undo_integrity_operation',
    'Deshace una corrección de integridad y restaura los valores anteriores. Requiere el impacto vigente de '
    'preview_integrity_operation_undo, motivo y request_id estable.',
    'panel-data-integrity-operation-undo', 'POST', ('operation_id',), 'sensitive', True,
    payload_schema=writable_schema(UndoSerializer),
)


_FIELD_DESCRIPTIONS = {
    'scope': 'Ámbito de la revisión: tipo de registro e identificador.',
    'fixes': 'Correcciones seleccionadas, con la huella vigente de cada hallazgo.',
    'reason': 'Motivo de la corrección o del deshacer; queda en el registro.',
    'request_id': 'Identificador estable de esta solicitud para evitar repetirla.',
    'expected_impact_hash': 'Hash de impacto obtenido en la vista previa vigente.',
}


def _close_integrity_input(tool, query_properties=None):
    properties = deepcopy(tool['input_schema']['properties'])
    properties.pop('query', None)
    properties.pop('data', None)
    payload = tool['_panel_operation']['payload_schema']
    if payload is not None:
        for name, field in payload['properties'].items():
            field['description'] = _FIELD_DESCRIPTIONS[name]
        if 'fixes' in payload['properties']:
            payload['properties']['fixes']['maxItems'] = 20
            payload['properties']['fixes']['minItems'] = 1
            payload['properties']['fixes']['items']['properties']['params'] = open_object(
                'Parámetros específicos de la corrección elegida.',
                'Las claves dependen de rule_id y fix_kind; el motor valida sus valores por regla.',
            )
        properties.update(deepcopy(payload['properties']))
        properties['data'] = {**deepcopy(payload), 'description': 'Datos de la corrección, validados por el serializer del Panel.'}
    elif query_properties is not None:
        properties['query'] = closed_object(query_properties, description='Filtros de la consulta de integridad.')
    for name in tool['_panel_operation']['path_params']:
        properties[name]['description'] = 'Identificador de la operación de integridad registrada.'
    tool['input_schema'] = closed_object(properties, tool['input_schema'].get('required', ()))


_close_integrity_input(RULES, {})
_close_integrity_input(FINDINGS, {
    'scope_kind': {'type': 'string', 'enum': ['all', 'client', 'project', 'proposal', 'document', 'thread'],
                   'description': 'Tipo de registro que delimita la revisión.', 'default': 'all'},
    'scope_id': {'type': 'integer', 'minimum': 1, 'description': 'Identificador del registro que se revisa.'},
    'scope_query': {'type': 'string', 'maxLength': 200, 'description': 'Texto para buscar un cliente o proyecto sin un id conocido.'},
    'domains': {'type': ['string', 'array'], 'items': {'type': 'string'}, 'description': 'Dominios que se revisan, como lista o texto separado por comas.'},
    'rule_ids': {'type': ['string', 'array'], 'items': {'type': 'string'}, 'description': 'Reglas que se revisan, como lista o texto separado por comas.'},
    'severity': {'type': ['string', 'array'], 'items': {'type': 'string'}, 'description': 'Gravedades que se incluyen, como lista o texto separado por comas.'},
    'page': {'type': 'integer', 'minimum': 1, 'description': 'Página de resultados, con 50 hallazgos por página.', 'default': 1},
})
_close_integrity_input(OPERATIONS, {
    'rule_id': {'type': 'string', 'description': 'Regla de integridad por la que se filtra el registro.'},
    'page': {'type': 'integer', 'minimum': 1, 'description': 'Página del registro, con 20 operaciones por página.', 'default': 1},
})
_close_integrity_input(UNDO_PREVIEW, {})
for _integrity_tool in (PREVIEW, APPLY, UNDO):
    _close_integrity_input(_integrity_tool)


def _prepare(tool, serializer_class, arguments):
    check_known_fields(arguments, tool['input_schema'])
    arguments = guarded_arguments(arguments, tool)
    data = arguments.pop('data', {})
    args = {**arguments, **data}
    serializer = serializer_class(data={
        key: value for key, value in args.items()
        if key in tool['_panel_operation']['payload_schema']['properties']
    })
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        raise ToolError('Revisa los datos de la operación.', details=exc.detail) from exc
    return {**args, **serializer.validated_data}


def _confirmed(preview, args, summary):
    if preview['impact_hash'] != args['expected_impact_hash']:
        raise ToolError('El impacto cambió. Vuelve a revisar la vista previa.', code='STALE_VERSION')
    if preview['blocked']:
        blockers = list(preview['blockers']) + [entry for step in preview.get('steps', [])
                                                for entry in step.get('blockers', [])]
        raise ToolError('La operación tiene bloqueos.', code='CONFLICT', details={'blockers': blockers})
    return {**summary, 'impact_hash': preview['impact_hash'], 'reason': args['reason']}


def _fixes_preview(arguments):
    args = _prepare(APPLY, FixApplySerializer, arguments)
    return PREVIEW['handler']({'scope': args['scope'], 'fixes': args['fixes']}), args


def _fixes_impact(arguments):
    preview, args = _fixes_preview(arguments)
    # Compact on purpose: the confirmation intent stores it.
    return _confirmed(preview, args, {
        'scope': preview['scope'], 'records': preview['records'],
        'steps': [{'rule_id': step['rule_id'], 'fix_kind': step['fix_kind'],
                   'subjects': [subject['label'] or f"{subject['model']}#{subject['id']}"
                                for subject in step['subjects']][:10],
                   'changes': len(step['changes'])} for step in preview['steps']],
    })


def _undo_preview(arguments):
    args = _prepare(UNDO, UndoSerializer, arguments)
    return UNDO_PREVIEW['handler']({'operation_id': args['operation_id']}), args


def _undo_impact(arguments):
    preview, args = _undo_preview(arguments)
    return _confirmed(preview, args, {'operation_id': preview['operation_id'], 'steps': preview['steps']})


APPLY['prepare_arguments'] = lambda arguments: _prepare(APPLY, FixApplySerializer, arguments)
APPLY['impact_builder'] = _fixes_impact
APPLY['etag_resolver'] = lambda arguments: {'integrity_fixes': _fixes_preview(arguments)[0]['impact_hash']}
UNDO['prepare_arguments'] = lambda arguments: _prepare(UNDO, UndoSerializer, arguments)
UNDO['impact_builder'] = _undo_impact
UNDO['etag_resolver'] = lambda arguments: {'integrity_undo': _undo_preview(arguments)[0]['impact_hash']}

DATA_INTEGRITY_TOOLS = [RULES, FINDINGS, PREVIEW, APPLY, OPERATIONS, UNDO_PREVIEW, UNDO]
