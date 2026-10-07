"""Confirmed exits from retention over MCP: undo an adoption, discard empty containers.

Both mutations require the current preview's impact hash, a reason and a stable
request_id, and always go through the confirmation step: MCP never skips the
preview the panel shows.
"""
from rest_framework.exceptions import ValidationError

from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, guarded_arguments, writable_schema
from content.mcp.protocol import ToolError
from content.serializers.project_retention import (
    CONTAINER_KINDS, RetainedCleanupSerializer, RetainedUndoSerializer,
)

UNDO_PREVIEW = _op(
    'preview_retained_operation_undo',
    'Revisa si un traslado de datos conservados se puede deshacer exactamente (nada cambió después) '
    'y qué registros volverían a quedar sin proyecto y de solo consulta.',
    'panel-projects-retained-operation-undo', path=('operation_id',),
)
UNDO = _op(
    'undo_retained_operation',
    'Deshace un traslado de datos conservados: los registros vuelven a quedar sin proyecto y de solo '
    'consulta. Requiere el impacto vigente de preview_retained_operation_undo, motivo y request_id estable.',
    'panel-projects-retained-operation-undo', 'POST', ('operation_id',), 'sensitive', True,
    payload_schema=writable_schema(RetainedUndoSerializer),
)
CLEANUP_PREVIEW = _op(
    'preview_retained_container_cleanup',
    'Lista los hilos, carpetas de comunicación y carpetas documentales conservados de un proyecto '
    'eliminado y si están vacíos. query.communication_threads, query.communication_folders y '
    'query.document_folders (ids separados por comas) limitan la selección.',
    'panel-projects-retained-context-cleanup', path=('context_id',),
)
CLEANUP = _op(
    'delete_empty_retained_containers',
    'Elimina contenedores conservados VACÍOS de un proyecto eliminado (hilos sin mensajes y carpetas '
    'sin contenido). Requiere el impacto vigente de preview_retained_container_cleanup con la misma '
    'selección, motivo y request_id estable.',
    'panel-projects-retained-context-cleanup', 'POST', ('context_id',), 'sensitive', True,
    payload_schema=writable_schema(RetainedCleanupSerializer),
)


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


def _confirmed_impact(preview, args):
    if preview['impact_hash'] != args['expected_impact_hash']:
        raise ToolError('El impacto cambió. Vuelve a revisar la vista previa.', code='STALE_VERSION')
    if preview['blockers']:
        raise ToolError('La operación tiene bloqueos.', code='CONFLICT', details={'blockers': preview['blockers']})
    return {**preview, 'reason': args['reason']}


def _undo_preview(arguments):
    args = _prepare(UNDO, RetainedUndoSerializer, arguments)
    return UNDO_PREVIEW['handler']({'operation_id': args['operation_id']})


def _cleanup_preview(arguments):
    args = _prepare(CLEANUP, RetainedCleanupSerializer, arguments)
    query = {'context_id': args['context_id']}
    for kind in CONTAINER_KINDS:
        ids = (args.get('selection') or {}).get(kind)
        if ids:
            query[kind] = ','.join(str(pk) for pk in ids)
    return CLEANUP_PREVIEW['handler'](query)


UNDO['prepare_arguments'] = lambda arguments: _prepare(UNDO, RetainedUndoSerializer, arguments)
UNDO['impact_builder'] = lambda arguments: _confirmed_impact(_undo_preview(arguments), _prepare(UNDO, RetainedUndoSerializer, arguments))
UNDO['etag_resolver'] = lambda arguments: {'retained_undo': _undo_preview(arguments)['impact_hash']}
CLEANUP['prepare_arguments'] = lambda arguments: _prepare(CLEANUP, RetainedCleanupSerializer, arguments)
CLEANUP['impact_builder'] = lambda arguments: _confirmed_impact(_cleanup_preview(arguments), _prepare(CLEANUP, RetainedCleanupSerializer, arguments))
CLEANUP['etag_resolver'] = lambda arguments: {'retained_cleanup': _cleanup_preview(arguments)['impact_hash']}

PROJECT_RETENTION_TOOLS = [UNDO_PREVIEW, UNDO, CLEANUP_PREVIEW, CLEANUP]
