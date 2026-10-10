"""Panel adapters preserve query intent and reject unsupported arguments."""

import json
from copy import deepcopy

import pytest

from content.mcp import panel_bridge
from content.mcp.operation_builder import _op
from content.mcp.panel_bridge import encode_query_value
from content.mcp.protocol import ToolError, handle_message
from content.mcp.registry import normalize_tool
from content.models import DocumentFolder
from content.tests.views import test_panel_project_deletion

pytestmark = pytest.mark.django_db
unused_project = test_panel_project_deletion.unused_project

QUERY_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'force': {'type': 'boolean'},
        'optional': {'type': ['string', 'null']},
        'ids': {'type': 'array', 'items': {'type': 'integer'}, 'x-query-encoding': 'repeat'},
    },
}


def _preview_tool(**kwargs):
    return _op(
        'preview_query_test', 'Comprueba las dependencias de un proyecto desde el Panel.',
        'panel-projects-delete-preview', path=('project_id',), **kwargs,
    )


@pytest.mark.parametrize(('value', 'encoding', 'expected'), [
    (True, 'csv', 'true'), (False, 'csv', 'false'), (0, 'csv', '0'),
    (3.5, 'csv', '3.5'), ('á b', 'csv', 'á b'),
    ([1, True, 'two'], 'csv', '1,true,two'),
    ([1, False], 'repeat', ['1', 'false']),
    ([], 'csv', ''), ([], 'repeat', []), (None, 'csv', None),
])
def test_query_encoder_preserves_scalar_values(value, encoding, expected):
    assert encode_query_value(value, encoding=encoding) == expected


@pytest.mark.parametrize('value', [{'force': True}, [[1]], [{'id': 1}]])
def test_query_encoder_rejects_nested_values(value):
    with pytest.raises(ToolError) as rejected:
        encode_query_value(value, field='filters')

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.details['errors'][0]['field'] == 'filters'
    assert rejected.value.details['errors'][0]['code'] == 'invalid'


@pytest.mark.parametrize('arguments', [{'force': True}, {'query': {'force': True}}])
def test_generic_get_boolean_reaches_the_forced_preview(superuser, unused_project, arguments):
    tool = _preview_tool()

    normal = tool['handler']({'project_id': unused_project.pk, 'query': {'force': False, 'optional': None}})
    forced = tool['handler']({'project_id': unused_project.pk, **arguments})

    assert normal['can_delete'] is True
    assert 'impact_token' not in normal
    assert forced['force'] is True
    assert forced['impact_token']
    assert forced['project']['id'] == unused_project.pk
    assert tool['input_schema']['properties']['project_id'] == {'type': ['integer', 'string']}


@pytest.mark.parametrize(('query_schema', 'expected'), [
    (None, ['1', 'true', 'two']),
    ({'type': 'object', 'additionalProperties': False,
      'properties': {'ids': {'type': 'array', 'items': {'type': 'string'}}}}, ['1,true,two']),
], ids=['generic-repeat', 'declared-csv'])
def test_get_query_list_uses_the_declared_encoding(query_schema, expected):
    query = panel_bridge._encode_query({'ids': [1, True, 'two']}, query_schema)

    request = panel_bridge._request_for(
        'GET', '/query-encoding/', query=query, data={}, files={}, if_match='',
    )

    assert request.GET.getlist('ids') == expected


@pytest.mark.parametrize('payload_schema', [None, {'type': 'object', 'properties': {}, 'additionalProperties': False}])
def test_post_rejects_an_undeclared_query(payload_schema):
    tool = _preview_tool(method='POST', payload_schema=payload_schema)

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': 1, 'query': {'force': True}})

    assert rejected.value.code == 'unknown_field'
    assert rejected.value.details['errors'] == [{
        'field': 'query', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.',
    }]
    assert 'query' not in tool['input_schema']['properties']


def test_query_only_post_rejects_a_body_without_a_payload_schema():
    tool = _op(
        'query_only_post', 'Comprueba un POST que sólo admite parámetros de consulta.',
        'create-document-folder', method='POST', query_schema=QUERY_SCHEMA,
    )

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'query': {'force': True}, 'data': {'name': 'Undeclared body'}})

    assert 'data' not in tool['input_schema']['properties']
    assert tool['input_schema']['additionalProperties'] is False
    assert rejected.value.code == 'unknown_field'
    assert rejected.value.details['errors'] == [{
        'field': 'data', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.',
    }]


def test_explicit_query_schema_publishes_a_closed_flat_contract(superuser, unused_project):
    schema = {**deepcopy(QUERY_SCHEMA), 'required': ['force']}
    tool = normalize_tool(_preview_tool(query_schema=schema), 'projects')

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': {
            'project_id': str(unused_project.pk), 'query': {'force': True, 'optional': None},
        }},
    }, [tool])

    published = tool['input_schema']
    accepted = tool['accepted_arguments_schema']
    assert published['additionalProperties'] is False
    assert {name: field for name, field in published['properties'].items() if name != 'if_match'} == {
        **schema['properties'], 'project_id': {'type': 'integer', 'minimum': 1},
    }
    assert published['required'] == ['project_id', 'force']
    assert accepted['properties'] == {**published['properties'], 'query': schema}
    assert accepted['required'] == ['project_id']
    assert accepted['additionalProperties'] is False
    assert response['result']['structuredContent']['force'] is True


@pytest.mark.parametrize('arguments', [
    {'typo': True}, {'query': {'typo': True}},
])
def test_explicit_query_rejects_unknown_fields(arguments):
    tool = _preview_tool(query_schema=QUERY_SCHEMA)

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': 1, **arguments})

    assert rejected.value.code == 'unknown_field'
    assert rejected.value.details['errors'] == [{
        'field': 'typo', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.',
    }]


def test_query_alias_conflicts_use_the_validation_contract():
    tool = _preview_tool(query_schema=QUERY_SCHEMA)

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': 1, 'force': True, 'query': {'force': False}})

    assert str(rejected.value) == 'Campos contradictorios entre query y argumentos.'
    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.details['errors'][0] == {
        'field': 'force', 'code': 'invalid', 'message': str(rejected.value),
    }


def test_declared_query_rejects_non_nullable_null():
    tool = _preview_tool(query_schema=QUERY_SCHEMA)

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': 1, 'query': {'force': None}})

    assert rejected.value.details['errors'] == [{
        'field': 'force', 'code': 'null', 'message': 'Este campo no puede ser nulo.',
    }]


def test_declared_query_requires_its_fields():
    tool = _preview_tool(query_schema={**QUERY_SCHEMA, 'required': ['force']})

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': 1})

    assert str(rejected.value) == 'force es obligatorio.'
    assert rejected.value.details['errors'][0]['code'] == 'required'


@pytest.mark.parametrize('convert', [int, str, lambda value: f'000{value}'], ids=['integer', 'digits', 'leading-zeroes'])
def test_explicit_path_accepts_positive_identifiers(superuser, unused_project, convert):
    tool = _preview_tool(query_schema=QUERY_SCHEMA)

    result = tool['handler']({'project_id': convert(unused_project.pk), 'query': {'force': False}})

    assert result['can_delete'] is True
    assert result['project']['id'] == unused_project.pk


@pytest.mark.parametrize('value', [True, 0, -1, 1.2, '1.0', '-1', 'abc', '²'])
def test_explicit_path_rejects_invalid_identifiers(value):
    tool = _preview_tool(query_schema=QUERY_SCHEMA)

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': value})

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.details['errors'][0]['field'] == 'project_id'
    assert rejected.value.details['errors'][0]['code'] == 'invalid'


def test_get_payload_alias_is_rejected_before_dispatch():
    tool = normalize_tool(_preview_tool(payload_schema={
        'type': 'object', 'properties': {'force': {'type': 'boolean'}},
    }), 'projects')

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': {'project_id': 1, 'data': {'force': True}}},
    }, [tool])

    error = response['result']['structuredContent']['error']
    assert error['code'] == 'unknown_field'
    assert error['details']['errors'][0]['field'] == 'data'


def test_post_declared_query_keeps_the_body_separate(monkeypatch, superuser):
    captured = []
    original_post = panel_bridge.factory.post

    def capture_request(*args, **kwargs):
        request = original_post(*args, **kwargs)
        captured.append(request)
        return request

    monkeypatch.setattr(panel_bridge.factory, 'post', capture_request)
    query_schema = {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'flags': {'type': 'array', 'items': {'type': 'boolean'}, 'x-query-encoding': 'repeat'},
            'ids': {'type': 'array', 'items': {'type': 'integer'}},
            'optional': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
        },
        'required': ['flags', 'ids'],
    }
    payload_schema = {
        'type': 'object', 'additionalProperties': False,
        'properties': {'name': {'type': 'string'}}, 'required': ['name'],
    }
    tool = normalize_tool(_op(
        'create_query_folder', 'Crea una carpeta con el contrato del Panel.', 'create-document-folder',
        method='POST', query_schema=query_schema, payload_schema=payload_schema,
    ), 'documents')

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': {
            'data': {'name': 'Query folder'},
            'flags': [True, False], 'query': {'flags': [True, False], 'ids': [2, 5], 'optional': None},
            'if_match': 'example-etag',
        }},
    }, [tool])

    result = response['result']['structuredContent']
    request = captured[0]
    assert dict(request.GET.lists()) == {'flags': ['true', 'false'], 'ids': ['2,5']}
    assert json.loads(request.body) == {'name': 'Query folder'}
    assert request.META['HTTP_IF_MATCH'] == 'example-etag'
    assert DocumentFolder.objects.get(pk=result['id']).name == 'Query folder'
    assert tool['input_schema']['properties'].keys() == {'name', 'flags', 'ids', 'optional', 'if_match'}
    assert tool['input_schema']['required'] == ['name', 'flags', 'ids']
    assert tool['accepted_arguments_schema'] == {
        'type': 'object', 'additionalProperties': False, 'required': [],
        'properties': {**tool['input_schema']['properties'], 'data': payload_schema, 'query': query_schema},
    }


def test_payload_alias_conflicts_use_field_errors():
    tool = _op('create_conflicting_folder', 'Crea una carpeta mediante el Panel.', 'create-document-folder',
               method='POST', payload_schema={'type': 'object', 'properties': {'name': {'type': 'string'}}})

    with pytest.raises(ToolError) as rejected:
        tool['handler']({'name': 'First', 'data': {'name': 'Second'}})

    assert str(rejected.value) == 'Campos contradictorios entre data y argumentos.'
    assert rejected.value.details['errors'][0]['field'] == 'name'
