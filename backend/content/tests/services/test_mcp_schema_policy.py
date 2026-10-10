"""Published MCP contracts and the shrink-only exceptions, without a database."""
from copy import deepcopy

import pytest

from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG
from content.mcp.registry import public_tool
from content.mcp.schema_backlog import (
    DEFERRED_SCHEMA_BACKLOG,
    GENERIC_ADAPTER_BACKLOG,
    UNDESCRIBED_ARGUMENT_BACKLOG,
)
from content.mcp.schema_policy import (
    OPEN_REASON_KEY,
    closed_object,
    close_root_schemas,
    is_generic,
    open_object,
    schema_problems,
    strip_private,
    undescribed_root_properties,
)


GENERIC_ADAPTER_CEILING = 272
UNDESCRIBED_CEILING = 273
DEFERRED_CEILING = 7
ALL_TOOLS = tuple(tool for tools in TOOLS_BY_SLUG.values() for tool in tools)
ALL_NAMES = {tool['name'] for tool in ALL_TOOLS}
TEXT = {'type': 'string', 'description': 'Texto de ejemplo.'}


def _policy_problems(tools):
    deferred = set(DEFERRED_SCHEMA_BACKLOG)
    return [
        problem for tool in tools
        for problem in schema_problems(
            tool,
            generic_ok=tool['name'] in GENERIC_ADAPTER_BACKLOG | deferred,
            # Generic payloads and deferred contracts also defer prose checks.
            undescribed_ok=tool['name'] in (
                UNDESCRIBED_ARGUMENT_BACKLOG | GENERIC_ADAPTER_BACKLOG | deferred
            ),
        )
    ]


def _private_keys(value):
    if isinstance(value, dict):
        return [key for key in value if key.startswith('x-mcp-')] + [
            key for child in value.values() for key in _private_keys(child)
        ]
    if isinstance(value, list):
        return [key for child in value for key in _private_keys(child)]
    return []


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_connector_input_schemas_follow_policy(slug):
    assert _policy_problems(TOOLS_BY_SLUG[slug]) == []


def test_generic_backlog_matches_current_tools():
    computed = {tool['name'] for tool in ALL_TOOLS if is_generic(tool)}
    assert computed == GENERIC_ADAPTER_BACKLOG


def test_undescribed_backlog_matches_current_tools():
    computed = {
        tool['name'] for tool in ALL_TOOLS
        if not is_generic(tool) and undescribed_root_properties(tool)
    }
    assert computed == UNDESCRIBED_ARGUMENT_BACKLOG


def test_deferred_backlog_matches_current_violations():
    computed = {
        tool['name'] for tool in ALL_TOOLS
        if not is_generic(tool) and schema_problems(tool, undescribed_ok=True)
    }
    assert computed == set(DEFERRED_SCHEMA_BACKLOG)


def test_deferred_backlog_explains_every_exception():
    assert all(isinstance(reason, str) and reason.strip() for reason in DEFERRED_SCHEMA_BACKLOG.values())


@pytest.mark.parametrize('backlog', [
    GENERIC_ADAPTER_BACKLOG, UNDESCRIBED_ARGUMENT_BACKLOG, DEFERRED_SCHEMA_BACKLOG,
], ids=['generic', 'undescribed', 'deferred'])
def test_backlog_has_no_stale_names(backlog):
    assert set(backlog) <= ALL_NAMES


@pytest.mark.parametrize('backlog,ceiling', [
    (GENERIC_ADAPTER_BACKLOG, GENERIC_ADAPTER_CEILING),
    (UNDESCRIBED_ARGUMENT_BACKLOG, UNDESCRIBED_CEILING),
    (DEFERRED_SCHEMA_BACKLOG, DEFERRED_CEILING),
], ids=['generic', 'undescribed', 'deferred'])
def test_backlog_stays_within_initial_ceiling(backlog, ceiling):
    assert len(backlog) <= ceiling


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_public_projection_hides_policy_metadata(slug):
    private_keys = [
        key for tool in TOOLS_BY_SLUG[slug]
        for key in _private_keys(public_tool(tool))
    ]
    assert private_keys == []


@pytest.mark.parametrize('schema,pointer,message', [
    (
        {'type': 'object', 'properties': {'value': TEXT}},
        '/additionalProperties', 'root must set additionalProperties to false',
    ),
    (
        closed_object({'value': {
            **closed_object({}), 'description': 'Objeto cerrado.', OPEN_REASON_KEY: 'Motivo antiguo.',
        }}),
        '/properties/value', 'open marker must belong to an open object',
    ),
    (
        closed_object({}, ['missing']),
        '/required/0', 'required name is absent from properties',
    ),
    (
        closed_object({'values': {'type': 'array', 'description': 'Valores.', 'items': {}}}),
        '/properties/values/items', 'property or items must declare a type, enum, const or typed combinator',
    ),
    (
        {**closed_object({'value': TEXT}), 'anyOf': [{'required': ['value']}]},
        '/anyOf', 'root combinators are not supported by MCP clients',
    ),
], ids=['missing-closure', 'stale-open-marker', 'unknown-required', 'untyped-item', 'root-combinator'])
def test_schema_policy_reports_invalid_contract(schema, pointer, message):
    problems = schema_problems({'name': 'example', 'input_schema': schema})
    assert f'example:{pointer}: {message}' in problems


@pytest.mark.parametrize('value', [
    closed_object({'value': TEXT}, description='Objeto cerrado.'),
    {**closed_object({'value': TEXT}, description='Objeto nullable.'), 'type': ['object', 'null']},
    {'type': 'object', 'description': 'Mapa de texto.', 'additionalProperties': {'type': 'string'}},
    {'type': 'array', 'description': 'Objetos.', 'items': closed_object({'value': TEXT})},
    {'description': 'Valor o null.', 'oneOf': [{'type': 'string'}, {'type': 'null'}]},
    {'description': 'Opciones.', 'enum': ['one', 'two']},
    {'description': 'Constante.', 'const': 'one'},
    {
        **closed_object({'a': TEXT, 'b': TEXT}, description='Una opción.'),
        'oneOf': [
            {'required': ['a'], 'not': {'anyOf': [{'required': ['b']}]}},
            {'required': ['b'], 'not': {'required': ['a']}},
        ],
    },
], ids=['closed', 'nullable', 'typed-map', 'array', 'typed-combinator', 'enum', 'const', 'constraint'])
def test_schema_policy_accepts_typed_nested_values(value):
    schema = closed_object({'payload': value})
    assert schema_problems({'name': 'example', 'input_schema': schema}) == []


@pytest.mark.parametrize('node,fragment', [
    ({'type': 'array', 'properties': {}, 'additionalProperties': False}, '/type:'),
    ({'type': 'object', 'properties': [], 'additionalProperties': False}, '/properties:'),
    (closed_object({'value': {'type': 'string', 'description': '  '}}), '/properties/value:'),
    (closed_object({'value': {**open_object('Libre.', '  ')}}), f'/{OPEN_REASON_KEY}:'),
    (closed_object({'value': open_object('', 'Claves variables.')}), '/description:'),
    (closed_object({'value': {'type': 'object', 'description': 'Sin contrato.'}}), '/properties/value:'),
], ids=['root-type', 'root-properties', 'missing-description', 'empty-reason', 'open-description', 'bare-object'])
def test_schema_policy_identifies_invalid_nodes(node, fragment):
    problems = schema_problems({'name': 'example', 'input_schema': node})
    assert any(fragment in problem for problem in problems)


def test_open_reason_keeps_freeform_children_opaque():
    freeform = {**open_object('Contenido libre.', 'Lo valida el importador.'), 'properties': {'arbitrary': {}}}
    tool = {'name': 'example', 'input_schema': closed_object({'payload': freeform})}
    assert schema_problems(tool) == []


def test_root_closure_preserves_explicit_open_schema():
    nested = {'type': 'object'}
    tools = [
        {'input_schema': {'type': 'object', 'properties': {'payload': nested}}},
        {'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': True}},
    ]
    result = close_root_schemas(tools)
    assert result is tools
    assert tools[0]['input_schema']['additionalProperties'] is False
    assert 'additionalProperties' not in nested
    assert tools[1]['input_schema']['additionalProperties'] is True


@pytest.mark.parametrize('additional,expected', [(False, False), (True, True), ({'type': 'string'}, True)])
def test_generic_detection_respects_explicit_closure(additional, expected):
    tool = {'input_schema': {'additionalProperties': additional}}
    assert is_generic(tool) is expected


def test_generic_detection_recognizes_legacy_roots():
    assert is_generic({'input_schema': {'type': 'object', 'properties': {}}}) is True


def test_generic_allowance_preserves_argument_description_rule():
    schema = {'type': 'object', 'properties': {'value': {'type': 'string'}}}
    tool = {'name': 'example', 'input_schema': schema}
    assert schema_problems(tool, generic_ok=True) == [
        'example:/properties/value: root property needs a description',
    ]


def test_undescribed_arguments_ignore_nested_fields():
    tool = {'input_schema': closed_object({
        'blank': {'type': 'string', 'description': ' '},
        'missing': {'type': 'string'},
        'nested': closed_object({'undocumented': {'type': 'string'}}, description='Objeto.'),
    })}
    assert undescribed_root_properties(tool) == ['blank', 'missing']


def test_public_projection_copies_both_schemas():
    """Input/output policy metadata stays private without altering registry data."""
    tool = {
        'name': 'example', 'description': 'Ejemplo.',
        'input_schema': closed_object({'payload': open_object('Entrada libre.', 'Importador.')}),
        'output_schema': {'oneOf': [{**open_object('Salida libre.', 'Proveedor.'), 'x-mcp-internal': True}]},
    }
    original = deepcopy(tool)
    published = public_tool(tool)
    assert _private_keys(published) == []
    published['inputSchema']['properties']['payload']['description'] = 'Cambiado.'
    published['outputSchema']['oneOf'][0]['description'] = 'Cambiado.'
    assert tool == original


def test_strip_private_preserves_public_extensions():
    schema = {'x-vendor-public': [{'const': 'x-mcp-literal', 'x-mcp-hidden': True}], 'x-mcp-root': True}
    assert strip_private(schema) == {'x-vendor-public': [{'const': 'x-mcp-literal'}]}


def test_blog_update_accepts_legacy_html_arguments():
    tool = next(tool for tool in TOOLS_BY_SLUG['blog'] if tool['name'] == 'update_blog_post')
    properties = tool['accepted_arguments_schema']['properties']
    assert set(properties) - set(tool['input_schema']['properties']) == {'content_es', 'content_en'}
    assert tool['accepted_arguments_schema']['required'] == ['post_id']


@pytest.mark.parametrize('name', [
    'create_income', 'create_expense', 'create_hosting', 'create_pocket',
    'create_recurring', 'create_ads', 'create_card_snapshot', 'create_notification_recipient',
])
def test_ledger_creation_accepts_ignored_legacy_record_id(name):
    tool = next(tool for tool in TOOLS_BY_SLUG['accounting'] if tool['name'] == name)
    properties = tool['accepted_arguments_schema']['properties']
    assert set(properties) - set(tool['input_schema']['properties']) == {'record_id'}
    assert tool['accepted_arguments_schema']['required'] == tool['input_schema']['required']
