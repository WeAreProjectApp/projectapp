"""
Minimal MCP (Model Context Protocol) JSON-RPC 2.0 dispatcher.

Implements the stateless subset of the Streamable HTTP transport that
claude.ai custom connectors need: initialize, notifications/*, tools/list,
tools/call, ping. Every response is plain JSON (the SSE mode of the
transport is optional per spec and deliberately unsupported — this must
run under gunicorn WSGI).
"""
import json
import logging
import traceback

from rest_framework.exceptions import APIException, ValidationError

from content.mcp.errors import normalize_error
from content.mcp.registry import public_tool
from content.mcp.registry import server_info as build_server_info
from content.services.diagnostic_privacy import safe_mcp_error_code

logger = logging.getLogger(__name__)
TRACE_FRAMES = 12


def _safe_trace(exc):
    """Exception type and code frames only: messages may carry client data."""
    frames = traceback.StackSummary.extract(traceback.walk_tb(exc.__traceback__), lookup_lines=False)
    trace = ' > '.join(
        f'{frame.filename.rsplit("/backend/", 1)[-1]}:{frame.lineno}:{frame.name}'
        for frame in list(frames)[-TRACE_FRAMES:]
    )
    cause = exc.__cause__ or exc.__context__
    return f'{type(exc).__name__} at {trace}' + (f' (from {type(cause).__name__})' if cause else '')

MODERN_PROTOCOL_VERSION = '2026-07-28'
LEGACY_PROTOCOL_VERSIONS = (
    '2025-11-25',
    '2025-06-18',
    '2025-03-26',
    '2024-11-05',
)
SUPPORTED_PROTOCOL_VERSIONS = (
    MODERN_PROTOCOL_VERSION,
    *LEGACY_PROTOCOL_VERSIONS,
)
DEFAULT_PROTOCOL_VERSION = LEGACY_PROTOCOL_VERSIONS[0]
LIST_CACHE_TTL_MS = 300_000
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ToolError(Exception):
    """Business/validation error inside a tool handler.

    Surfaces as result.isError=true with a readable message so the calling
    model can fix its arguments and retry.
    """

    def __init__(self, message, *, code='VALIDATION_ERROR', details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _error(msg_id, code, message):
    return 200, {'jsonrpc': '2.0', 'id': msg_id, 'error': {'code': code, 'message': message}}


def _result(msg_id, result):
    return 200, {'jsonrpc': '2.0', 'id': msg_id, 'result': result}


def _text_result(msg_id, payload, is_error=False, *, error=None, meta=None):
    structured = payload if isinstance(payload, dict) else {'items': payload} if isinstance(payload, list) else {'message': str(payload)}
    if error:
        structured = {'ok': False, 'error': error}
        results = error.get('details', {}).get('results')
        if isinstance(results, list):
            structured['results'] = results
    text_payload = structured if error else payload
    text = text_payload if isinstance(text_payload, str) else json.dumps(
        text_payload, ensure_ascii=False, default=str,
    )
    result = {
        'content': [{'type': 'text', 'text': text}],
        'isError': is_error,
        'structuredContent': structured,
    }
    if meta:
        result['_meta'] = meta
    return _result(msg_id, result)


def handle_message(message, tools, server_name=None, context=None):
    """
    Handle one JSON-RPC message. Returns (http_status, response_dict|None).
    Notifications (no 'id') return (202, None) per Streamable HTTP transport.
    server_name overrides the serverInfo name so each connector (blog,
    documents, proposals, ...) identifies itself instead of a shared default.
    """
    if not isinstance(message, dict):
        return _error(None, INVALID_REQUEST, 'Expected a single JSON-RPC request object.')

    method = message.get('method', '')
    msg_id = message.get('id')
    params = message.get('params') or {}

    if isinstance(method, str) and method.startswith('notifications/'):
        return 202, None

    if message.get('jsonrpc') != '2.0' or not method:
        return _error(msg_id, INVALID_REQUEST, 'Malformed JSON-RPC 2.0 request.')

    # JSON-RPC allows positional (array) params, but every MCP method here
    # takes named params — reject anything that is not an object.
    if not isinstance(params, dict):
        return _error(msg_id, INVALID_PARAMS, 'params must be a JSON object.')

    if method == 'server/discover':
        server_info = build_server_info(server_name)
        return _result(msg_id, {
            'resultType': 'complete',
            'supportedVersions': [MODERN_PROTOCOL_VERSION],
            'capabilities': {'tools': {}},
            '_meta': {
                'io.modelcontextprotocol/serverInfo': server_info,
            },
            'instructions': (
                'Usa tools/list para descubrir acciones. Las operaciones sensibles '
                'devuelven una vista previa que se ejecuta con confirm_action.'
            ),
            'ttlMs': LIST_CACHE_TTL_MS,
            'cacheScope': 'private',
        })

    if method == 'initialize':
        requested = params.get('protocolVersion', '')
        version = (
            requested if requested in LEGACY_PROTOCOL_VERSIONS
            else DEFAULT_PROTOCOL_VERSION
        )
        server_info = build_server_info(server_name)
        return _result(msg_id, {
            'protocolVersion': version,
            'capabilities': {'tools': {}},
            'serverInfo': server_info,
        })

    if method == 'ping':
        return _result(msg_id, {})

    if method == 'tools/list':
        visible_tools = [
            tool for tool in tools
            if not context
            or not context.credential
            or context.credential.allows(tool['name'])
        ]
        return _result(msg_id, {
            'tools': [public_tool(tool) for tool in visible_tools],
        })

    if method == 'tools/call':
        name = params.get('name', '')
        arguments = params.get('arguments', {})
        tool = next((t for t in tools if t['name'] == name), None)
        if tool is None:
            return _error(msg_id, INVALID_PARAMS, f'Unknown tool: {name}')
        if context and context.credential and not context.credential.allows(name):
            return _text_result(
                msg_id,
                'La credencial no permite esta herramienta.',
                is_error=True,
                error={
                    'code': 'FORBIDDEN',
                    'message': 'La credencial no permite esta herramienta.',
                    'details': {},
                },
                meta={'requestId': context.request_id, 'risk': tool.get('risk')},
            )
        try:
            if not isinstance(arguments, dict):
                raise ToolError('Los argumentos deben ser un objeto JSON.')
            if (
                tool.get('requires_confirmation')
                and (not tool.get('confirmation_predicate') or tool['confirmation_predicate'](arguments))
                and not (context and context.confirmation_bypass)
            ):
                from content.mcp.confirmation import preview_sensitive_action
                payload = preview_sensitive_action(tool, arguments)
            else:
                payload = tool['handler'](arguments)
        except (ToolError, APIException) as exc:
            if isinstance(exc, ValidationError):
                detail, code, fields = normalize_error(exc.detail)
                exc = ToolError(detail, code=code, details=fields)
            elif isinstance(exc, APIException):
                # Domain tools call services directly: a model guard or service
                # PermissionDenied/NotFound keeps its meaning instead of INTERNAL_ERROR.
                detail, code, fields = normalize_error(exc.detail, exc.status_code)
                exc = ToolError(detail, code=code, details=fields)
            logger.info(
                '[MCP] tool %s rejected code=%s requestId=%s',
                name, safe_mcp_error_code(exc.code),
                context.request_id if context else '',
            )
            return _text_result(
                msg_id,
                str(exc),
                is_error=True,
                error={
                    'code': exc.code,
                    'message': str(exc),
                    'details': exc.details,
                },
                meta={
                    'requestId': context.request_id if context else '',
                    'risk': tool.get('risk'),
                },
            )
        except Exception as exc:
            logger.error(
                '[MCP] tool %s crashed code=INTERNAL_ERROR requestId=%s trace=%s',
                name, context.request_id if context else '', _safe_trace(exc),
            )
            return _text_result(
                msg_id,
                'Error interno ejecutando la herramienta. Revisa los logs del servidor.',
                is_error=True,
                error={
                    'code': 'INTERNAL_ERROR',
                    'message': 'Error interno ejecutando la herramienta.',
                    'details': {},
                },
                meta={
                    'requestId': context.request_id if context else '',
                    'risk': tool.get('risk'),
                },
            )
        logger.info('[MCP] tool %s executed ok', name)
        return _text_result(
            msg_id,
            payload,
            meta={
                'requestId': context.request_id if context else '',
                'risk': tool.get('risk'),
            },
        )

    return _error(msg_id, METHOD_NOT_FOUND, f'Method not supported: {method}')
