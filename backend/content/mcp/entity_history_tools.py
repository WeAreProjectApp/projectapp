"""History adapters scoped to one connector's entity, without secret reveal."""
from copy import deepcopy
import logging

from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, object_schema
from content.mcp.protocol import ToolError

logger = logging.getLogger(__name__)

PRIVATE_FIELDS = {'archived_pdf', 'generated_file', 'file', 'secrets'}


def _public(value):
    if isinstance(value, list):
        return [_public(item) for item in value]
    if not isinstance(value, dict):
        return value
    # File storage paths are private; download through the credential-owned
    # artifact operation instead. Secret values already remain masked by API.
    if isinstance(value.get('field'), str) and value['field'].split('.')[-1] in PRIVATE_FIELDS:
        return {key: _public(item) for key, item in value.items()
                if key not in {'old', 'new', 'lines', 'old_value', 'new_value'}}
    return {key: _public(item) for key, item in value.items()
            if key not in PRIVATE_FIELDS}


def _validate_arguments(arguments, schema):
    if set(arguments) - set(schema['properties']):
        raise ToolError('Sólo se admite el historial del módulo autorizado.')
    for key in schema['required']:
        if isinstance(arguments.get(key), bool) or not isinstance(arguments.get(key), int) or arguments[key] < 1:
            raise ToolError(f'{key} debe ser un identificador positivo.')


def _schemas(tool, path, *, action, entity):
    properties = {
        'object_id': {'type': 'integer', 'minimum': 1,
                      'description': 'Identificador del registro cuyo historial se consulta.'},
    }
    if 'revision_id' in path:
        properties['revision_id'] = {
            'type': 'integer', 'minimum': 1,
            'description': 'ID de versión obtenido al listar el historial de este registro.',
        }
    required = list(path)
    if action == 'list':
        properties.update(
            page={'type': 'integer', 'minimum': 1, 'description': 'Página de 20 versiones; comienza en 1.'},
            order={'type': 'string', 'enum': ['recent', 'oldest'],
                   'description': 'Orden de versiones: recientes primero o antiguas primero.'},
        )
    elif action == 'compare':
        properties.update({key: {'type': 'integer', 'minimum': 1,
            'description': f'ID de versión de list_{entity}_history para comparar.'}
            for key in ('from', 'to')})
        required.extend(['from', 'to'])
    tool['input_schema'] = object_schema(properties, required)
    tool['accepted_arguments_schema'] = object_schema({
        **properties, 'query': object_schema(deepcopy(properties)),
        'if_match': {'type': 'string', 'description': 'ETag obsoleto; se sigue aceptando.'},
    }, path)


def _arguments(arguments, tool):
    args = deepcopy(arguments)
    schema = tool.get('accepted_arguments_schema') or tool['input_schema']
    query = args.pop('query', {})
    query = {} if query is None else query
    if not isinstance(query, dict):
        raise ToolError('query debe ser un objeto JSON.')
    check_known_fields(args, schema)
    check_known_fields(query, schema['properties'].get('query', schema))
    for key in schema['required']:
        if key not in args:
            raise ToolError(f'{key} debe ser un identificador positivo.')
    conflicts = {key for key in query.keys() & args.keys() if query[key] != args[key]}
    if conflicts:
        raise ToolError('No envíes valores distintos en query y en los argumentos: ' + ', '.join(sorted(conflicts)))
    if 'query' in arguments:
        logger.info('[MCP] deprecated_envelope tool=%s keys=%s', tool['name'], sorted({'query'}))
    args.update(query)
    _validate_arguments(args, schema)
    return args


def history_tools(entity):
    tools = []
    for action, route, description, path in (
        ('list', 'entity-history-list', 'Lista las versiones históricas en páginas de 20; page y order (recent u oldest) son opcionales.', ('object_id',)),
        ('get', 'entity-history-version', 'Lee una versión histórica completa manteniendo protegidas las credenciales.', ('object_id', 'revision_id')),
        ('compare', 'entity-history-compare', f'Compara dos versiones; from y to son IDs de versión de list_{entity}_history.', ('object_id',)),
    ):
        name = f'{action}_{entity}_history' if action != 'get' else f'get_{entity}_history_version'
        tool = _op(name, description, route, path=('entity_type', *path))
        bridge = tool['handler']
        _schemas(tool, path, action=action, entity=entity)

        def handler(arguments, bridge=bridge, tool=tool):
            return _public(bridge({**_arguments(arguments, tool), 'entity_type': entity}))

        tool['handler'] = handler
        tools.append(tool)
    if entity == 'proposal':
        file_tool = _op('download_proposal_history_file',
                        'Descarga el PDF conservado de una versión histórica como asset temporal de esta credencial.',
                        'entity-history-file', path=('entity_type', 'object_id', 'revision_id'))
        bridge = file_tool['handler']
        _schemas(file_tool, ('object_id', 'revision_id'), action='get', entity=entity)

        def download(arguments, bridge=bridge, tool=file_tool):
            return bridge({**_arguments(arguments, tool), 'entity_type': entity})

        file_tool['handler'] = download
        tools.append(file_tool)
    return tools
