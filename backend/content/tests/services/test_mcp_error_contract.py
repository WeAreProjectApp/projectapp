"""The shared error transport preserves machine-readable validation failures."""
import json
import logging

import pytest
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, Throttled

from content.mcp.common_tools import build_common_tools
from content.mcp.connectors import CONNECTORS
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.errors import normalize_error, transport_exception_handler
from content.mcp.panel_bridge import _error_message
from content.mcp.protocol import ToolError, handle_message
from content.models import McpActionIntent, McpConnector, McpCredential
from content.services import diagnostic_privacy

PRIVATE_MARKER = 'SYNTHETIC_PRIVATE_P5_20261001'


@pytest.mark.parametrize(('status', 'code'), [(403, 'FORBIDDEN'), (404, 'NOT_FOUND'), (409, 'CONFLICT')])
def test_panel_error_retains_status_code(status, code):
    message, actual_code, details = _error_message({'detail': 'Rechazado'}, status)

    assert (message, actual_code, details) == ('Rechazado', code, {'detail': 'Rechazado'})


def test_panel_error_preserves_nested_serializer_path():
    payload = {'items': [{'email': [serializers.ErrorDetail('Correo inválido.', code='invalid')]}]}

    message, code, details = _error_message(payload, 400)

    assert details['errors'] == [{'field': 'items.0.email', 'code': 'invalid', 'message': 'Correo inválido.'}]
    assert message == 'items.0.email: Correo inválido.'
    assert code == 'VALIDATION_ERROR'


def _serializer_failure(_arguments):
    raise serializers.ValidationError({
        'amount': [serializers.ErrorDetail(PRIVATE_MARKER, code='min_value')],
    })


def _internal_failure(_arguments):
    raise RuntimeError(PRIVATE_MARKER)


def test_dispatcher_keeps_public_validation_message_out_of_technical_log(caplog):
    """Fails if sanitizing the audit log changes a ToolError response to its caller."""
    with caplog.at_level(logging.INFO, logger='content.mcp.protocol'):
        _, response = handle_message(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'validate'}},
            [{'name': 'validate', 'handler': _serializer_failure}],
            context=McpExecutionContext(
                connector=None, credential=None,
                request_id='public-validation-request',
            ),
        )

    error = json.loads(response['result']['content'][0]['text'])['error']
    assert error == {
        'code': 'VALIDATION_ERROR',
        'message': f'amount: {PRIVATE_MARKER}',
        'details': {
            'amount': [PRIVATE_MARKER],
            'errors': [{
                'field': 'amount', 'code': 'min_value',
                'message': PRIVATE_MARKER,
            }],
        },
    }
    assert response['result']['_meta']['requestId'] == 'public-validation-request'
    assert PRIVATE_MARKER in json.dumps(response)
    assert PRIVATE_MARKER not in caplog.text


def test_internal_error_hides_exception_contents_from_protocol_log(caplog):
    """Fails if an unexpected tool exception reaches the technical protocol log."""
    with caplog.at_level(logging.ERROR, logger='content.mcp.protocol'):
        _, response = handle_message(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'fail'}},
            [{'name': 'fail', 'handler': _internal_failure}],
        )

    error = json.loads(response['result']['content'][0]['text'])['error']
    assert error['code'] == 'INTERNAL_ERROR'
    assert PRIVATE_MARKER not in json.dumps(response)
    assert PRIVATE_MARKER not in caplog.text


def test_transport_throttle_preserves_retry_metadata():
    response = transport_exception_handler(Throttled(wait=12), {})

    assert response.status_code == 429
    assert response['Retry-After'] == '12'
    assert response.data['error']['code'] == 'THROTTLED'
    assert '12' in response.data['error']['message']


def test_transport_internal_error_hides_exception_contents(caplog):
    """Fails if an unhandled transport exception leaks through its HTTP log or body."""
    with caplog.at_level(logging.ERROR, logger='content.mcp.errors'):
        response = transport_exception_handler(RuntimeError(PRIVATE_MARKER), {})

    assert (
        response.status_code, response.data['error'], PRIVATE_MARKER not in caplog.text,
    ) == (
        500,
        {'code': 'INTERNAL_ERROR', 'message': 'Error interno del servidor.'},
        True,
    )


def test_internal_error_logs_exception_type_and_code_frames(caplog):
    """Fails if a crash leaves no way to locate it in the technical log (or leaks its message)."""
    with caplog.at_level(logging.ERROR, logger='content.mcp.protocol'):
        handle_message(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'fail'}},
            [{'name': 'fail', 'handler': _internal_failure}],
        )

    assert 'RuntimeError at ' in caplog.text
    assert 'test_mcp_error_contract.py:' in caplog.text
    assert ':_internal_failure' in caplog.text
    assert PRIVATE_MARKER not in caplog.text


def _guarded_write(_arguments):
    raise PermissionDenied('Los datos conservados sin proyecto sólo permiten consulta.')


def test_domain_permission_denied_keeps_forbidden_code():
    """Fails if a model guard reached from a native tool turns into INTERNAL_ERROR."""
    _, response = handle_message(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'guarded'}},
        [{'name': 'guarded', 'handler': _guarded_write}],
    )

    error = json.loads(response['result']['content'][0]['text'])['error']
    assert error['code'] == 'FORBIDDEN'
    assert error['message'] == 'Los datos conservados sin proyecto sólo permiten consulta.'


@pytest.fixture
def confirmation_contract(db):
    connector, _ = McpConnector.objects.get_or_create(slug='tasks', defaults={'name': 'Tasks'})
    credential = McpCredential.objects.create(connector=connector, label='Error contract')
    return McpExecutionContext(connector=connector, credential=credential, request_id='confirmation-errors')


@pytest.mark.parametrize('confirmation_id', ['malformed-id', 123, None])
def test_cancel_action_rejects_a_malformed_id(confirmation_contract, confirmation_id):
    tools = build_common_tools(CONNECTORS['tasks'], lambda: tools)

    with use_mcp_context(confirmation_contract):
        _, response = handle_message({
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'cancel_action', 'arguments': {'confirmation_id': confirmation_id}},
        }, tools, context=confirmation_contract)

    assert response['result']['structuredContent']['error'] == {
        'code': 'NOT_FOUND', 'message': 'No existe una confirmación pendiente con ese id.', 'details': {},
    }
    assert not McpActionIntent.objects.filter(credential=confirmation_contract.credential).exists()


def test_confirm_action_preserves_domain_blockers(confirmation_contract):
    blockers = [{'code': 'new_dependency', 'message': 'Apareció una dependencia.'}]

    def blocked(_arguments):
        raise ToolError('La acción está bloqueada.', code='SOME_CODE', details={'blockers': blockers})

    tools = [{
        'name': 'blocked_action', 'description': 'Previsualiza una acción con bloqueos de dominio.',
        'requires_confirmation': True,
        'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        'handler': blocked,
    }]
    tools.extend(build_common_tools(CONNECTORS['tasks'], lambda: tools))
    with use_mcp_context(confirmation_contract):
        _, preview = handle_message({
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'blocked_action', 'arguments': {}},
        }, tools, context=confirmation_contract)
        confirmation_id = preview['result']['structuredContent']['confirmation_id']
        _, response = handle_message({
            'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
            'params': {'name': 'confirm_action', 'arguments': {'confirmation_id': confirmation_id}},
        }, tools, context=confirmation_contract)

    assert response['result']['structuredContent']['error'] == {
        'code': 'SOME_CODE', 'message': 'La acción está bloqueada.', 'details': {'blockers': blockers},
    }
    assert json.loads(response['result']['content'][0]['text']) == response['result']['structuredContent']
    intent = McpActionIntent.objects.get(pk=confirmation_id)
    assert intent.status == McpActionIntent.STATUS_PENDING


@pytest.mark.parametrize(('arguments', 'expected_code', 'field_codes'), [
    ({'record_id': 7, 'typo': True}, 'unknown_field', [('typo', 'unknown_field')]),
    ({}, 'VALIDATION_ERROR', [('record_id', 'required')]),
    ({'typo': True}, 'VALIDATION_ERROR', [('typo', 'unknown_field'), ('record_id', 'required')]),
])
def test_dispatcher_validates_before_sensitive_preview(confirmation_contract, arguments, expected_code, field_codes):
    tool = {
        'name': 'delete_record', 'description': 'Elimina el registro después de confirmarlo.',
        'requires_confirmation': True,
        'strict_arguments': True,
        'input_schema': {
            'type': 'object', 'properties': {'record_id': {'type': 'integer'}},
            'required': ['record_id'], 'additionalProperties': False,
        },
        'handler': _internal_failure,
    }

    with use_mcp_context(confirmation_contract):
        _, response = handle_message({
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': tool['name'], 'arguments': arguments},
        }, [tool], context=confirmation_contract)

    error = response['result']['structuredContent']['error']
    assert error['code'] == expected_code
    assert [(row['field'], row['code']) for row in error['details']['errors']] == field_codes
    assert not McpActionIntent.objects.filter(credential=confirmation_contract.credential).exists()


def test_missing_required_field_keeps_its_public_message():
    tool = {
        'name': 'echo', 'connector': 'documents', 'input_schema': {
            'type': 'object', 'properties': {'value': {}}, 'required': ['value'],
            'additionalProperties': False,
        }, 'handler': lambda args: args,
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'echo'},
    }, [tool])

    error = response['result']['structuredContent']['error']
    assert error['message'] == 'value es obligatorio.'
    assert error['details']['errors'] == [{'field': 'value', 'code': 'required', 'message': 'value es obligatorio.'}]


@pytest.mark.parametrize('extra_schema', [{}, {'additionalProperties': True}], ids=['implicit-open', 'explicit-open'])
def test_dispatcher_preserves_open_schema_handler_validation(extra_schema):
    received = []
    arguments = {'legacy_filter': True}

    def validate(args):
        received.append(args)
        raise ToolError('Falta el valor para ejecutar esta herramienta.', code='VALUE_REQUIRED', details={'origin': 'handler'})

    tool = {
        'name': 'open_validation', 'connector': 'projects', 'input_schema': {
            'type': 'object', 'properties': {'value': {}}, 'required': ['value'], **extra_schema,
        }, 'handler': validate,
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': arguments},
    }, [tool])

    assert received == [arguments]
    assert response['result']['structuredContent']['error'] == {
        'code': 'VALUE_REQUIRED', 'message': 'Falta el valor para ejecutar esta herramienta.',
        'details': {'origin': 'handler'},
    }


def test_dispatcher_leaves_types_to_the_handler():
    tool = {
        'name': 'echo', 'connector': 'documents', 'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'value': {'type': 'integer'}}, 'required': ['value'],
        }, 'handler': lambda args: {'seen': args['value']},
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'echo', 'arguments': {'value': 'handler decides'}},
    }, [tool])

    assert response['result']['isError'] is False
    assert response['result']['structuredContent'] == {'seen': 'handler decides'}


def test_dispatcher_accepts_a_private_legacy_argument():
    tool = {
        'name': 'legacy_echo', 'connector': 'documents',
        'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'value': {'type': 'string'}}, 'required': ['value'],
        },
        'accepted_arguments_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'value': {'type': 'string'}, 'legacy_value': {'type': 'string'}},
            'required': [],
        },
        'handler': lambda args: {'seen': args['legacy_value']},
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': {'legacy_value': 'Compatibility value'}},
    }, [tool])

    assert 'legacy_value' not in tool['input_schema']['properties']
    assert response['result']['isError'] is False
    assert response['result']['structuredContent'] == {'seen': 'Compatibility value'}


@pytest.mark.parametrize('scope', [
    {'connector': 'documents'}, {'connector': 'projects'},
    {'connector': 'communications', 'strict_arguments': True},
], ids=['documents-default', 'projects-default', 'other-connector-opt-in'])
def test_closed_tool_rejects_unknown_arguments_in_its_strict_scope(scope):
    received = []
    tool = {
        'name': 'scoped_echo', **scope,
        'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {}},
        'handler': lambda args: received.append(args),
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': {'legacy_value': 'Legacy'}},
    }, [tool])

    assert response['result']['structuredContent']['error']['code'] == 'unknown_field'
    assert response['result']['structuredContent']['error']['details']['errors'][0]['field'] == 'legacy_value'
    assert received == []


@pytest.mark.parametrize('scope', [
    {'connector': 'communications'}, {},
    {'connector': 'documents', 'strict_arguments': False},
    {'connector': 'projects', 'strict_arguments': False},
], ids=['other-connector-default', 'no-connector-default', 'documents-opt-out', 'projects-opt-out'])
def test_closed_tool_keeps_handler_validation_outside_its_strict_scope(scope):
    received = []
    arguments = {'legacy_value': 'Legacy'}

    def validate(args):
        received.append(args)
        raise ToolError('Falta el valor.', code='VALUE_REQUIRED', details={'origin': 'handler'})

    tool = {
        'name': 'scoped_validation', **scope,
        'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'value': {}}, 'required': ['value'],
        },
        'handler': validate,
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': arguments},
    }, [tool])

    assert received == [arguments]
    assert response['result']['structuredContent']['error'] == {
        'code': 'VALUE_REQUIRED', 'message': 'Falta el valor.', 'details': {'origin': 'handler'},
    }


def test_normalize_error_preserves_planner_details():
    structured = {
        'blockers': [{'code': 'pinned_folder', 'message': 'Carpeta fijada.'}],
        'blocker_counts': {'pinned_folder': 1}, 'planned': {'move': [4]},
        'impact_hash': 'impact', 'plan_hash': 'plan', 'can_apply': False,
        'guard_code': 'pinned_folder', 'resolution': 'choose_destination',
        'warnings': ['Advertencia.'], 'conflicts': [{'document_id': 9}],
    }
    payload = {'code': 'folder_blocked', 'message': 'Bloqueado.', **structured,
               'folder_id': [serializers.ErrorDetail('Destino inválido.', code='invalid')]}

    message, code, details = normalize_error(payload)

    assert (message, code) == ('Bloqueado.', 'FOLDER_BLOCKED')
    assert {name: details[name] for name in structured} == structured
    assert details['errors'] == [{'field': 'folder_id', 'code': 'invalid', 'message': 'Destino inválido.'}]


def test_registered_codes_extend_the_diagnostic_catalog(monkeypatch):
    monkeypatch.setattr(diagnostic_privacy, '_REGISTERED_MCP_DOMAIN_CODES', set())
    original = diagnostic_privacy._MCP_DOMAIN_CODES
    assert diagnostic_privacy.safe_mcp_error_code('registered_slice_code') == 'TOOL_ERROR'

    diagnostic_privacy.register_mcp_domain_codes('registered_slice_code', 'MixedCase_2', 'a' * 64)
    diagnostic_privacy.register_mcp_domain_codes('registered_slice_code')

    expected = {
        'registered_slice_code': 'registered_slice_code',
        'REGISTERED_SLICE_CODE': 'REGISTERED_SLICE_CODE',
        'MixedCase_2': 'MixedCase_2', 'MIXEDCASE_2': 'MIXEDCASE_2',
        'a' * 64: 'a' * 64, 'VALIDATION_ERROR': 'VALIDATION_ERROR',
        -32602: '-32602', 'arbitrary message': 'TOOL_ERROR',
    }
    assert {value: diagnostic_privacy.safe_mcp_error_code(value) for value in expected} == expected
    assert diagnostic_privacy._MCP_DOMAIN_CODES is original


@pytest.mark.parametrize('invalid_code', ['', 'a', '1code', '_code', 'two words', 'x\n', 'a' * 65, None])
def test_registration_rejects_invalid_identifiers(monkeypatch, invalid_code):
    monkeypatch.setattr(diagnostic_privacy, '_REGISTERED_MCP_DOMAIN_CODES', set())

    with pytest.raises(ValueError):
        diagnostic_privacy.register_mcp_domain_codes('atomic_valid_code', invalid_code)

    assert diagnostic_privacy.safe_mcp_error_code('atomic_valid_code') == 'TOOL_ERROR'
