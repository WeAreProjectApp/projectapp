"""Private contract operations with durable, dependency-bound confirmation."""
from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.contract_template_tools import PATCH
from content.mcp.operation_builder import _op
from content.mcp.protocol import ToolError
from content.services import building_with_us_contract_service as service
from content.services.building_with_us_content import BuildingWithUsError


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except BuildingWithUsError as exc:
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


def _prepare_sensitive(arguments, *, restore=False):
    prepared = _run(service.prepare_update, arguments, restore=restore, require_match=True)
    return {**arguments, '_expected_etags': prepared['resource_etags']}


def _impact(arguments, *, restore=False):
    public = {key: value for key, value in arguments.items() if key != '_expected_etags'}
    prepared = _run(service.prepare_update, public, restore=restore, require_match=True)
    return {'summary': 'Crea una revisión del contrato privado y sincroniza el PDF y la nota del Gestor en una transacción.', **prepared}


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


def _prepare_initialization(arguments):
    _known(arguments, ['folder_id'])
    prepared = _run(service.prepare_initialization, arguments.get('folder_id'))
    return {**arguments, '_expected_etags': prepared['resource_etags']}


def _initialization_impact(arguments):
    prepared = _run(service.prepare_initialization, arguments.get('folder_id'))
    return {'summary': 'Inicializa o resincroniza el espejo interno de sólo lectura en Contratos, con PDF y notas privadas.', **prepared}


def _initialize(arguments):
    arguments, expected, _ = _confirmed_arguments(arguments)
    _known(arguments, ['folder_id'])
    return _run(service.initialize_mirror, arguments.get('folder_id'), actor=mcp_actor(), expected_etags=expected)


def _schema(*, sensitive=False, restore=False):
    properties = {'if_match': {'type': 'string', 'minLength': 1}}
    if restore:
        properties['version_id'] = {'type': 'integer', 'minimum': 1}
    else:
        properties.update({'markdown': {'type': 'string', 'minLength': 1, 'maxLength': 250000},
                           'patches': {'type': 'array', 'minItems': 1, 'maxItems': 50, 'items': PATCH}})
    if sensitive:
        properties['change_note'] = {'type': 'string', 'minLength': 1, 'maxLength': 4000}
    descriptions = {
        'version_id': 'Identificador de la revisión del contrato que se restaura.',
        'markdown': 'Contrato Markdown completo; envía markdown o patches, nunca ambos.',
        'patches': 'Cambios literales del contrato; envía patches o markdown, nunca ambos.',
        'if_match': 'ETag vigente del contrato obtenido en la consulta previa.',
        'change_note': 'Motivo de la revisión o restauración, guardado en el historial.',
    }
    for name, field in properties.items():
        field['description'] = descriptions[name]
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': [*(['version_id'] if restore else []), *(['if_match', 'change_note'] if sensitive else [])]}


_READ_ANNOTATIONS = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}
_WRITE_ANNOTATIONS = {**_READ_ANNOTATIONS, 'readOnlyHint': False}
_RENDER = _op(
    'render_building_with_us_contract_pdf',
    'Genera el PDF vigente del contrato privado de Building with Us como artefacto temporal firmado y descargable.',
    'admin-building-with-us-contract-pdf', 'GET', risk='read',
)
_RENDER['input_schema'] = {'type': 'object', 'additionalProperties': False, 'properties': {}}
_RENDER['annotations'] = dict(_READ_ANNOTATIONS)
_render_handler = _RENDER['handler']


def _render(arguments):
    _known(arguments, [])
    return _render_handler(arguments)


_RENDER['handler'] = _render
BUILDING_WITH_US_CONTRACT_TOOLS = [
    {'name': 'get_building_with_us_contract', 'risk': 'read', 'annotations': dict(_READ_ANNOTATIONS),
     'description': 'Lee el contrato privado vigente: markdown, versión, autor, motivo, etag y estado del espejo de sólo lectura del Gestor.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {}}, 'handler': _read,
     'output_schema': {'type': 'object', 'properties': {
         'markdown': {'type': 'string'}, 'version': {'type': 'integer'}, 'version_id': {'type': 'integer'},
         'updated_at': {'type': 'string'}, 'author': {'type': 'string'}, 'change_note': {'type': 'string'},
         'etag': {'type': 'string'}, 'mirror': {'type': 'object'},
     }, 'required': ['markdown', 'version', 'version_id', 'updated_at', 'author', 'change_note', 'etag', 'mirror']}},
    {'name': 'preview_building_with_us_contract_update', 'risk': 'read', 'annotations': dict(_READ_ANNOTATIONS),
     'description': 'Valida markdown o patches literales y muestra diff y documento por sincronizar sin guardar. if_match es opcional; no admite placeholders.',
     'input_schema': _schema(), 'handler': lambda args: _run(service.prepare_update, args)},
    {'name': 'update_building_with_us_contract', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza cambios con if_match y change_note. Sólo confirm_action crea la revisión, PDF y nota privada; un fallo revierte todo. Requiere espejo inicializado.',
     'input_schema': _schema(sensitive=True), 'handler': _apply, 'annotations': dict(_WRITE_ANNOTATIONS),
     'prepare_arguments': _prepare_sensitive, 'impact_builder': _impact, 'etag_resolver': resource_etags},
    {'name': 'list_building_with_us_contract_versions', 'risk': 'read', 'annotations': dict(_READ_ANNOTATIONS),
     'description': 'Lista revisiones inmutables con autor, fecha, motivo y versión de origen de restauración. include_content añade markdown; limit entre 1 y 50.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {
         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'description': 'Cantidad máxima de revisiones que se devuelven.'},
         'offset': {'type': 'integer', 'minimum': 0, 'description': 'Cantidad de revisiones que se omiten al paginar.'},
         'include_content': {'type': 'boolean', 'description': 'Incluye el Markdown completo de cada revisión.'}}}, 'handler': _versions},
    {'name': 'restore_building_with_us_contract_version', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza restaurar version_id como una nueva revisión. Exige if_match y change_note; confirm_action sincroniza el PDF y la nota sin modificar la historia.',
     'input_schema': _schema(sensitive=True, restore=True), 'handler': lambda args: _apply(args, restore=True),
     'annotations': dict(_WRITE_ANNOTATIONS), 'prepare_arguments': lambda args: _prepare_sensitive(args, restore=True),
     'impact_builder': lambda args: _impact(args, restore=True), 'etag_resolver': resource_etags},
    {'name': 'initialize_building_with_us_contract_mirror', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza la inicialización explícita e idempotente del espejo en la carpeta contractual interna fijada por ID (Contratos si aún no hay pin). confirm_action revalida carpeta, contrato y documento y guarda PDF y notas privadas.',
     'input_schema': {'type': 'object', 'additionalProperties': False,
                      'properties': {'folder_id': {'type': 'integer', 'minimum': 1,
                                                   'description': 'ID de la carpeta contractual interna fijada; sin pin previo debe ser una carpeta manual Contratos.'}}, 'required': ['folder_id']},
     'handler': _initialize, 'annotations': dict(_WRITE_ANNOTATIONS), 'prepare_arguments': _prepare_initialization,
     'impact_builder': _initialization_impact, 'etag_resolver': resource_etags},
    _RENDER,
]
