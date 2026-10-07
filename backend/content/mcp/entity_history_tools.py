"""History adapters scoped to one connector's entity, without secret reveal."""
from copy import deepcopy

from content.mcp.operation_builder import _op
from content.mcp.protocol import ToolError

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


def history_tools(entity):
    tools = []
    for action, route, description, path in (
        ('list', 'entity-history-list', 'Lista las versiones históricas con página y orden explícitos.', ('object_id',)),
        ('get', 'entity-history-version', 'Lee una versión histórica completa manteniendo protegidas las credenciales.', ('object_id', 'revision_id')),
        ('compare', 'entity-history-compare', 'Compara dos versiones históricas usando from y to en query.', ('object_id',)),
    ):
        name = f'{action}_{entity}_history' if action != 'get' else f'get_{entity}_history_version'
        tool = _op(name, description, route, path=('entity_type', *path))
        bridge = tool['handler']
        tool['input_schema']['properties'].pop('entity_type')
        tool['input_schema']['properties'].pop('data')
        tool['input_schema']['required'].remove('entity_type')
        tool['input_schema']['additionalProperties'] = False

        def handler(arguments, bridge=bridge, schema=deepcopy(tool['input_schema'])):
            _validate_arguments(arguments, schema)
            return _public(bridge({**arguments, 'entity_type': entity}))

        tool['handler'] = handler
        tools.append(tool)
    if entity == 'proposal':
        file_tool = _op('download_proposal_history_file',
                        'Descarga el PDF conservado de una versión histórica como asset temporal de esta credencial.',
                        'entity-history-file', path=('entity_type', 'object_id', 'revision_id'))
        bridge = file_tool['handler']
        file_tool['input_schema']['properties'].pop('entity_type')
        file_tool['input_schema']['properties'].pop('data')
        file_tool['input_schema']['required'].remove('entity_type')
        file_tool['input_schema']['additionalProperties'] = False

        def download(arguments, bridge=bridge, schema=deepcopy(file_tool['input_schema'])):
            _validate_arguments(arguments, schema)
            return bridge({**arguments, 'entity_type': entity})

        file_tool['handler'] = download
        tools.append(file_tool)
    return tools
