"""Private cell contract operations with dependency-bound MCP confirmation."""
from copy import deepcopy
from functools import partial

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.contract_template_tools import PATCH
from content.mcp.operation_builder import _op
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import closed_object
from content.services import building_on_demand_contract_service as service
from content.services.building_on_demand_content import BuildingOnDemandError


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except BuildingOnDemandError as exc:
        raise ToolError(str(exc), code=exc.code, details=exc.details) from exc


def _known(arguments, fields):
    if not isinstance(arguments, dict) or set(arguments) - set(fields):
        raise ToolError('Hay argumentos desconocidos.')


def _read(arguments):
    _known(arguments, [])
    return _run(service.read_contract)


def _versions(arguments):
    _known(arguments, ['limit', 'offset', 'include_content'])
    return _run(service.list_versions, **arguments)


def resource_etags(arguments=None):
    return _run(service.resource_etags, arguments)


def _preview(arguments):
    _known(arguments, ['markdown', 'patches', 'if_match'])
    return _run(service.prepare_update, arguments)


def _prepare_sensitive(arguments, *, restore=False):
    prepared = _run(service.prepare_update, arguments, restore=restore, require_match=True)
    _run(service.prepare_sync)
    return {**arguments, '_expected_etags': prepared['resource_etags']}


def _impact(arguments, *, restore=False):
    public = {key: value for key, value in arguments.items() if key != '_expected_etags'}
    prepared = _run(service.prepare_update, public, restore=restore, require_match=True)
    return {'summary': 'Crea una revisión del contrato privado y sincroniza el PDF y las notas del Gestor en una transacción.', **prepared}


def _confirmed_arguments(arguments):
    context = current_mcp_context()
    if context is None or not context.confirmation_bypass:
        raise ToolError('La operación requiere confirm_action.', code='CONFIRMATION_REQUIRED')
    arguments = dict(arguments)
    expected = arguments.pop('_expected_etags', None)
    if expected is None:
        raise ToolError('La confirmación no conserva la versión previsualizada.', code='STALE_VERSION')
    return arguments, expected, context


def _apply(arguments, *, restore=False):
    arguments, expected, context = _confirmed_arguments(arguments)
    return _run(service.apply_update, arguments, actor=mcp_actor(), credential=context.credential,
                restore=restore, expected_etags=expected)


def _prepare_sync(arguments):
    _known(arguments, ['folder_id'])
    prepared = _run(service.prepare_sync, arguments.get('folder_id'))
    return {**arguments, '_expected_etags': prepared['resource_etags']}


def _sync_impact(arguments):
    prepared = _run(service.prepare_sync, arguments.get('folder_id'))
    return {'summary': 'Sincroniza el espejo interno de sólo lectura, su PDF y notas; sin folder_id usa la carpeta contractual fijada.', **prepared}


def _sync(arguments):
    arguments, expected, _ = _confirmed_arguments(arguments)
    _known(arguments, ['folder_id'])
    return _run(service.sync_mirror, actor=mcp_actor(), folder_id=arguments.get('folder_id'), expected_etags=expected)


def _schema(*, sensitive=False, restore=False):
    properties = {'if_match': {'type': 'string', 'minLength': 1,
                              'description': 'ETag vigente del contrato obtenido en la consulta previa.'}}
    if restore:
        properties['version_id'] = {'type': 'integer', 'minimum': 1,
                                    'description': 'Identificador de la revisión del contrato que se restaura.'}
    else:
        properties.update({
            'markdown': {'type': 'string', 'minLength': 1, 'maxLength': 250000,
                         'description': 'Contrato Markdown completo; envía exactamente markdown o patches, nunca ambos.'},
            'patches': {'type': 'array', 'minItems': 1, 'maxItems': 50, 'items': deepcopy(PATCH),
                        'description': 'Cambios literales del contrato; envía exactamente patches o markdown, nunca ambos.'},
        })
    if sensitive:
        properties['change_note'] = {'type': 'string', 'minLength': 1, 'maxLength': 4000,
                                     'description': 'Motivo de la revisión o restauración, guardado en el historial.'}
    required = [*(['version_id'] if restore else []), *(['if_match', 'change_note'] if sensitive else [])]
    return closed_object(properties, required)


_READ_ANNOTATIONS = {'readOnlyHint': True, 'destructiveHint': False,
                     'idempotentHint': True, 'openWorldHint': False}
_WRITE_ANNOTATIONS = {**_READ_ANNOTATIONS, 'readOnlyHint': False}
_RENDER = _op(
    'render_building_on_demand_contract_pdf',
    'Genera el PDF vigente del contrato privado de Building on Demand como artefacto temporal firmado y descargable.',
    'admin-building-on-demand-contract-pdf', 'GET', risk='read',
)
_RENDER['input_schema'] = closed_object({})
_RENDER['annotations'] = dict(_READ_ANNOTATIONS)
_RENDER['strict_arguments'] = True
_render_handler = _RENDER['handler']


def _render(arguments):
    _known(arguments, [])
    return _render_handler(arguments)


_RENDER['handler'] = _render
BUILDING_ON_DEMAND_CONTRACT_TOOLS = [
    {'name': 'get_building_on_demand_contract', 'risk': 'read', 'strict_arguments': True,
     'description': 'Lee el contrato privado vigente: markdown, versión, autor, motivo, etag y estado del espejo de sólo lectura del Gestor.',
     'input_schema': closed_object({}), 'handler': _read, 'annotations': dict(_READ_ANNOTATIONS)},
    {'name': 'preview_building_on_demand_contract_update', 'risk': 'read', 'strict_arguments': True,
     'description': 'Valida exactamente markdown o patches literales y muestra diff y espejo por sincronizar sin guardar; if_match es opcional y no admite placeholders.',
     'input_schema': _schema(), 'handler': _preview, 'annotations': dict(_READ_ANNOTATIONS)},
    {'name': 'update_building_on_demand_contract', 'risk': 'sensitive', 'requires_confirmation': True, 'strict_arguments': True,
     'description': 'Previsualiza markdown o patches con if_match y change_note; confirm_action crea la revisión, PDF y notas privadas en la carpeta fijada. Sin carpeta válida no aplica cambios.',
     'input_schema': _schema(sensitive=True), 'handler': _apply, 'annotations': dict(_WRITE_ANNOTATIONS),
     'prepare_arguments': _prepare_sensitive, 'impact_builder': _impact, 'etag_resolver': resource_etags},
    {'name': 'list_building_on_demand_contract_versions', 'risk': 'read', 'strict_arguments': True,
     'description': 'Lista revisiones inmutables del contrato con autor, fecha, motivo y versión de origen; include_content añade markdown y limit admite de una a cincuenta.',
     'input_schema': closed_object({
         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'description': 'Cantidad máxima de revisiones que se devuelven.'},
         'offset': {'type': 'integer', 'minimum': 0, 'description': 'Cantidad de revisiones que se omiten al paginar.'},
         'include_content': {'type': 'boolean', 'description': 'Incluye el Markdown completo de cada revisión.'},
     }), 'handler': _versions, 'annotations': dict(_READ_ANNOTATIONS)},
    {'name': 'restore_building_on_demand_contract_version', 'risk': 'sensitive', 'requires_confirmation': True, 'strict_arguments': True,
     'description': 'Previsualiza restaurar version_id como nueva revisión con if_match y change_note; confirm_action sincroniza el PDF y las notas sin modificar la historia. Requiere carpeta fijada válida.',
     'input_schema': _schema(sensitive=True, restore=True), 'handler': partial(_apply, restore=True),
     'annotations': dict(_WRITE_ANNOTATIONS), 'prepare_arguments': partial(_prepare_sensitive, restore=True),
     'impact_builder': partial(_impact, restore=True), 'etag_resolver': resource_etags},
    {'name': 'sync_building_on_demand_contract_mirror', 'risk': 'sensitive', 'requires_confirmation': True, 'strict_arguments': True,
     'description': 'Previsualiza crear o resincronizar el espejo de lectura con PDF y notas privadas; sin folder_id usa la carpeta contractual fijada, o permite Contratos interna explícita si no hay pin. confirm_action revalida todas las dependencias; sincronizado devuelve noop.',
     'input_schema': closed_object({'folder_id': {
         'type': 'integer', 'minimum': 1,
         'description': 'ID opcional de la carpeta fijada; sin pin sólo admite una carpeta interna, activa y manual Contratos.',
     }}), 'handler': _sync, 'annotations': dict(_WRITE_ANNOTATIONS),
     'prepare_arguments': _prepare_sync, 'impact_builder': _sync_impact, 'etag_resolver': resource_etags},
    _RENDER,
]
