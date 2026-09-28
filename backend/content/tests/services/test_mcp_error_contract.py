"""The shared error transport preserves machine-readable validation failures."""
import json

import pytest
from rest_framework import serializers

from content.mcp.panel_bridge import _error_message
from content.mcp.protocol import handle_message


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
    raise serializers.ValidationError({'amount': [serializers.ErrorDetail('Debe ser positivo.', code='min_value')]})


def _internal_failure(_arguments):
    raise RuntimeError('private-database-password')


def test_dispatcher_normalizes_uncaught_serializer_error():
    _, response = handle_message(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'validate'}},
        [{'name': 'validate', 'handler': _serializer_failure}],
    )

    error = json.loads(response['result']['content'][0]['text'])['error']
    assert error['details']['errors'] == [{'field': 'amount', 'code': 'min_value', 'message': 'Debe ser positivo.'}]
    assert 'amount' in error['message']


def test_internal_error_hides_exception_contents():
    _, response = handle_message(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'fail'}},
        [{'name': 'fail', 'handler': _internal_failure}],
    )

    error = json.loads(response['result']['content'][0]['text'])['error']
    assert error['code'] == 'INTERNAL_ERROR'
    assert 'private-database-password' not in json.dumps(response)
