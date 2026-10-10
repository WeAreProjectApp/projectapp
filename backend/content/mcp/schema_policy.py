"""Construction and auditing helpers for the published MCP input contract."""
from copy import deepcopy


OPEN_REASON_KEY = 'x-mcp-open-reason'
_COMBINATORS = ('anyOf', 'oneOf', 'allOf')


def closed_object(properties, required=(), description=None):
    schema = {
        'type': 'object',
        'properties': properties,
        'additionalProperties': False,
    }
    if required:
        schema['required'] = list(required)
    if description is not None:
        schema['description'] = description
    return schema


def close_root_schemas(tools):
    """Close legacy roots without overriding an explicit openness decision."""
    for tool in tools:
        tool['input_schema'].setdefault('additionalProperties', False)
    return tools


def open_object(description, reason):
    return {
        'type': 'object',
        'additionalProperties': True,
        'description': description,
        OPEN_REASON_KEY: reason,
    }


def strip_private(schema):
    """Copy a schema while removing private policy metadata at every depth."""
    if isinstance(schema, dict):
        return {
            key: strip_private(value) for key, value in schema.items()
            if not (isinstance(key, str) and key.startswith('x-mcp-'))
        }
    if isinstance(schema, list):
        return [strip_private(value) for value in schema]
    return deepcopy(schema)


def is_generic(tool):
    return tool.get('input_schema', {}).get('additionalProperties') is not False


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def undescribed_root_properties(tool):
    properties = tool.get('input_schema', {}).get('properties', {})
    if not isinstance(properties, dict):
        return []
    return sorted(
        name for name, schema in properties.items()
        if not isinstance(schema, dict)
        or not _nonempty_text(schema.get('description'))
    )


def _typed(schema):
    if not isinstance(schema, dict):
        return False
    if schema.get('type') or 'enum' in schema or 'const' in schema:
        return True
    return any(
        isinstance(schema.get(key), list) and bool(schema[key])
        and all(_typed(branch) for branch in schema[key])
        for key in _COMBINATORS
    )


def _pointer(path, key):
    escaped = str(key).replace('~', '~0').replace('/', '~1')
    return f'{path}/{escaped}'


def schema_problems(tool, *, generic_ok=False, undescribed_ok=False):
    """Report policy violations with escaped JSON pointers into input_schema.

    Generic adapters may retain their server-validated payloads. A caller can
    also defer structural auditing of a closed schema with generic_ok while
    keeping root shape and closure checks in force.
    """
    problems = []
    name = tool.get('name', '<unnamed>')
    root = tool.get('input_schema')

    def report(path, message):
        problems.append(f'{name}:{path or "/"}: {message}')

    if not isinstance(root, dict):
        report('', 'root must be an object schema with a properties dict')
        return problems
    if root.get('type') != 'object':
        report('/type', 'root type must be object')
    if not isinstance(root.get('properties'), dict):
        report('/properties', 'root properties must be a dict')
    if root.get('additionalProperties') is not False and not generic_ok:
        report('/additionalProperties', 'root must set additionalProperties to false')

    def walk(node, path, parent_properties=None, needs_type=False):
        if not isinstance(node, dict):
            report(path, 'node must be a schema dict')
            return
        if needs_type and not _typed(node):
            report(path, 'property or items must declare a type, enum, const or typed combinator')

        node_type = node.get('type')
        object_typed = node_type == 'object' or (
            isinstance(node_type, list) and 'object' in node_type
        )
        additional = node.get('additionalProperties')
        if OPEN_REASON_KEY in node:
            if not object_typed or additional is False:
                report(path, 'open marker must belong to an open object')
            if not _nonempty_text(node.get('description')):
                report(_pointer(path, 'description'), 'open object needs a description')
            if not _nonempty_text(node[OPEN_REASON_KEY]):
                report(_pointer(path, OPEN_REASON_KEY), 'open object needs a non-empty reason')
            return

        properties = node.get('properties')
        if object_typed:
            if 'properties' in node:
                if additional is not False:
                    report(_pointer(path, 'additionalProperties'), 'object with properties must be closed')
            elif not isinstance(additional, dict):
                report(path, 'object without properties needs a typed map or an open reason')
        if 'properties' in node and not isinstance(properties, dict):
            report(_pointer(path, 'properties'), 'properties must be a dict')

        constraint = bool(node) and set(node) <= {'required', 'not'}
        available = parent_properties if constraint else properties
        available = available if isinstance(available, dict) else {}
        required = node.get('required', [])
        if not isinstance(required, list):
            report(_pointer(path, 'required'), 'required must be a list')
        else:
            for index, required_name in enumerate(required):
                if not isinstance(required_name, str) or required_name not in available:
                    report(_pointer(_pointer(path, 'required'), index), 'required name is absent from properties')

        if isinstance(properties, dict):
            for key, child in properties.items():
                walk(child, _pointer(_pointer(path, 'properties'), key), needs_type=True)
        if 'items' in node:
            items = node['items']
            if isinstance(items, list):
                for index, child in enumerate(items):
                    walk(child, _pointer(_pointer(path, 'items'), index), needs_type=True)
            else:
                walk(items, _pointer(path, 'items'), needs_type=True)
        if isinstance(additional, dict):
            walk(additional, _pointer(path, 'additionalProperties'), needs_type=True)
        for key in _COMBINATORS:
            if key not in node:
                continue
            branches = node[key]
            if not isinstance(branches, list):
                report(_pointer(path, key), 'combinator branches must be a list')
                continue
            for index, branch in enumerate(branches):
                scope = properties if isinstance(properties, dict) else parent_properties
                walk(branch, _pointer(_pointer(path, key), index), scope)
        if 'not' in node:
            walk(node['not'], _pointer(path, 'not'), available)

    if not generic_ok:
        for key in _COMBINATORS:
            if key in root:
                report(_pointer('', key), 'root combinators are not supported by MCP clients')
        walk(root, '')
    if not undescribed_ok:
        for key in undescribed_root_properties(tool):
            report(_pointer(_pointer('', 'properties'), key), 'root property needs a description')
    return problems
