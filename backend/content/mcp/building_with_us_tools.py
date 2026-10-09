"""Dedicated presentation tools using durable, version-bound confirmation."""
from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.operation_catalogs import _op
from content.mcp.protocol import ToolError
from content.services import building_with_us_program_service as service
from content.services.building_with_us_content import BuildingWithUsError, section_json_schema


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
    return _run(service.read_program)


def _versions(arguments):
    _known(arguments, ['limit', 'offset', 'include_content'])
    return _run(service.list_versions, **arguments)


def _preview(arguments):
    _known(arguments, ['sections', 'if_match'])
    return _run(service.prepare_update, arguments)


def resource_etags(arguments=None):
    return _run(service.resource_etags, arguments)


def _prepare_sensitive(arguments, *, restore=False):
    prepared = _run(service.prepare_update, arguments, restore=restore, require_match=True)
    return {**arguments, '_expected_etags': prepared['resource_etags']}


def _impact(arguments, *, restore=False):
    public = {key: value for key, value in arguments.items() if key != '_expected_etags'}
    prepared = _run(service.prepare_update, public, restore=restore, require_match=True)
    return {'summary': 'Publica una nueva versión de la presentación y solicita reconstruir la página pública.', **prepared}


def _apply(arguments, *, restore=False):
    context = current_mcp_context()
    if context is None or not context.confirmation_bypass:
        raise ToolError('La operación requiere confirm_action.', code='CONFIRMATION_REQUIRED')
    arguments = dict(arguments)
    expected = arguments.pop('_expected_etags', None)
    if expected is None:
        raise ToolError('La confirmación no conserva la versión previsualizada.', code='STALE_VERSION')
    return _run(service.apply_update, arguments, actor=mcp_actor(), credential=context.credential,
                restore=restore, expected_etags=expected)


def _schema(*, sensitive=False, restore=False):
    source = 'version_id' if restore else 'sections'
    properties = {source: {'type': 'integer', 'minimum': 1} if restore else section_json_schema(),
                  'if_match': {'type': 'string', 'minLength': 1}}
    if sensitive:
        properties['change_note'] = {'type': 'string', 'minLength': 1, 'maxLength': 4000}
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': [source, *(['if_match', 'change_note'] if sensitive else [])]}


_WRITE_ANNOTATIONS = {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}
_RENDER = _op(
    'render_building_with_us_program_pdf',
    'Genera el PDF vigente de Building with Us en es o en como artefacto temporal firmado y descargable.',
    'public-building-with-us-program-pdf', 'GET', risk='read',
)
_RENDER['input_schema'] = {'type': 'object', 'additionalProperties': False,
                           'properties': {'lang': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'}}}
_render_handler = _RENDER['handler']


def _render(arguments):
    _known(arguments, ['lang'])
    if arguments.get('lang', 'es') not in ('es', 'en'):
        raise ToolError('Usa es o en.', code='INVALID_LANGUAGE', details={'path': 'lang'})
    return _render_handler(arguments)


_RENDER['handler'] = _render
BUILDING_WITH_US_TOOLS = [
    {'name': 'get_building_with_us_program', 'risk': 'read',
     'description': 'Lee la presentación completa en español e inglés con secciones, autor, motivo, versión y etag vigente.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {}}, 'handler': _read,
     'output_schema': {'type': 'object', 'properties': {'content': {'type': 'object'}, 'etag': {'type': 'string'},
                       'version': {'type': 'integer'}, 'version_id': {'type': 'integer'}, 'sections': {'type': 'array', 'items': {'type': 'string'}}},
                       'required': ['content', 'etag', 'version', 'version_id', 'sections']}},
    {'name': 'preview_building_with_us_program_update', 'risk': 'read',
     'description': 'Valida secciones completas en es y en y muestra el diff sin guardar. Conserva las secciones omitidas; rechaza porcentajes e importes.',
     'input_schema': _schema(), 'handler': _preview},
    {'name': 'update_building_with_us_program', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza una publicación con if_match y change_note. confirm_action valida etags, crea una versión inmutable y solicita reconstruir la página.',
     'input_schema': _schema(sensitive=True), 'handler': _apply, 'annotations': dict(_WRITE_ANNOTATIONS),
     'prepare_arguments': _prepare_sensitive, 'impact_builder': _impact, 'etag_resolver': resource_etags},
    {'name': 'list_building_with_us_program_versions', 'risk': 'read',
     'description': 'Lista versiones inmutables con autor, fecha, motivo y origen de restauración. include_content agrega el contenido bilingüe; limit entre 1 y 50.',
     'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {
         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}, 'offset': {'type': 'integer', 'minimum': 0},
         'include_content': {'type': 'boolean'}}}, 'handler': _versions},
    {'name': 'restore_building_with_us_program_version', 'risk': 'sensitive', 'requires_confirmation': True,
     'description': 'Previsualiza una restauración como nueva versión con version_id, if_match y change_note. confirm_action revalida contenido y solicita reconstruir la página.',
     'input_schema': _schema(sensitive=True, restore=True), 'handler': lambda args: _apply(args, restore=True),
     'annotations': dict(_WRITE_ANNOTATIONS), 'prepare_arguments': lambda args: _prepare_sensitive(args, restore=True),
     'impact_builder': lambda args: _impact(args, restore=True), 'etag_resolver': resource_etags},
    _RENDER,
]
