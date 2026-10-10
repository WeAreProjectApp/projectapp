"""Tests for the minimal MCP JSON-RPC dispatcher."""
from content.mcp.protocol import ToolError, handle_message


def _echo_handler(arguments):
    return {'echo': arguments.get('value')}


def _failing_handler(arguments):
    raise ToolError('categoría inválida')


TOOLS = [
    {
        'name': 'echo',
        'description': 'Echo a value back.',
        'input_schema': {'type': 'object', 'properties': {'value': {'type': 'string'}}},
        'handler': _echo_handler,
    },
    {
        'name': 'always_fails',
        'description': 'Always raises a business error.',
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': _failing_handler,
    },
]


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


class TestInitialize:
    def test_initialize_returns_capabilities_and_server_info(self):
        status, resp = handle_message(
            _rpc('initialize', {'protocolVersion': '2025-06-18'}), TOOLS,
        )
        assert status == 200
        assert resp['id'] == 1
        assert resp['result']['protocolVersion'] == '2025-06-18'
        assert resp['result']['capabilities'] == {'tools': {}}
        assert 'name' in resp['result']['serverInfo']

    def test_initialize_uses_explicit_server_name(self):
        status, resp = handle_message(
            _rpc('initialize', {'protocolVersion': '2025-06-18'}), TOOLS,
            server_name='projectapp-documents-mcp',
        )
        assert status == 200
        assert resp['result']['serverInfo']['name'] == 'projectapp-documents-mcp'
        assert resp['result']['serverInfo']['version'] == '0.0.0'

    def test_initialize_without_server_name_uses_fallback(self):
        status, resp = handle_message(
            _rpc('initialize', {'protocolVersion': '2025-06-18'}), TOOLS,
        )
        assert status == 200
        assert resp['result']['serverInfo'] == {
            'name': 'projectapp-mcp', 'version': '0.0.0',
        }
        assert 'instructions' not in resp['result']

    def test_initialize_with_unknown_version_falls_back_to_supported(self):
        status, resp = handle_message(
            _rpc('initialize', {'protocolVersion': '1999-01-01'}), TOOLS,
        )
        assert status == 200
        assert resp['result']['protocolVersion'] == '2025-11-25'

    def test_initialize_does_not_negotiate_the_stateless_version(self):
        status, resp = handle_message(
            _rpc('initialize', {'protocolVersion': '2026-07-28'}), TOOLS,
        )

        assert status == 200
        assert resp['result']['protocolVersion'] == '2025-11-25'

    def test_initialized_notification_returns_202_no_body(self):
        status, resp = handle_message(
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, TOOLS,
        )
        assert status == 202
        assert resp is None


class TestToolsList:
    def test_lists_tools_with_schemas(self):
        status, resp = handle_message(_rpc('tools/list'), TOOLS)
        assert status == 200
        names = [t['name'] for t in resp['result']['tools']]
        assert names == ['echo', 'always_fails']
        assert resp['result']['tools'][0]['inputSchema']['type'] == 'object'


class TestToolsCall:
    def test_calls_handler_and_wraps_result_as_text_content(self):
        status, resp = handle_message(
            _rpc('tools/call', {'name': 'echo', 'arguments': {'value': 'hola'}}), TOOLS,
        )
        assert status == 200
        result = resp['result']
        assert result['isError'] is False
        assert result['content'][0]['type'] == 'text'
        assert 'hola' in result['content'][0]['text']

    def test_tool_error_becomes_is_error_result_not_protocol_error(self):
        status, resp = handle_message(
            _rpc('tools/call', {'name': 'always_fails', 'arguments': {}}), TOOLS,
        )
        assert status == 200
        assert resp['result']['isError'] is True
        assert 'categoría inválida' in resp['result']['content'][0]['text']

    def test_unknown_tool_returns_invalid_params_error(self):
        status, resp = handle_message(
            _rpc('tools/call', {'name': 'nope', 'arguments': {}}), TOOLS,
        )
        assert status == 200
        assert resp['error']['code'] == -32602


class TestProtocolErrors:
    def test_ping_returns_empty_result(self):
        status, resp = handle_message(_rpc('ping'), TOOLS)
        assert status == 200
        assert resp['result'] == {}

    def test_unknown_method_returns_method_not_found(self):
        status, resp = handle_message(_rpc('bogus/method'), TOOLS)
        assert status == 200
        assert resp['error']['code'] == -32601

    def test_non_dict_message_is_invalid_request(self):
        status, resp = handle_message(['not', 'a', 'dict'], TOOLS)
        assert status == 200
        assert resp['error']['code'] == -32600

    def test_array_params_return_invalid_params_not_crash(self):
        status, resp = handle_message(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': [1]}, TOOLS,
        )
        assert status == 200
        assert resp['error']['code'] == -32602
