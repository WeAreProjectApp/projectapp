"""The shared error transport preserves machine-readable validation failures."""
import json
import logging

import pytest
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, Throttled

from content.mcp.errors import transport_exception_handler
from content.mcp.context import McpExecutionContext
from content.mcp.panel_bridge import _error_message
from content.mcp.protocol import handle_message


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
