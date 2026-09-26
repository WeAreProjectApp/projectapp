"""
Blog Publisher MCP: public JSON-RPC endpoint (token-authenticated) and
the panel management endpoints backing /panel/mcps.
"""
import logging
import time
import uuid
from copy import deepcopy
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone as tz
from django.utils.dateparse import parse_datetime
from rest_framework import exceptions, serializers, status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from content.mcp.protocol import (
    DEFAULT_PROTOCOL_VERSION,
    LEGACY_PROTOCOL_VERSIONS,
    LIST_CACHE_TTL_MS,
    MODERN_PROTOCOL_VERSION,
    SERVER_INFO,
    SUPPORTED_PROTOCOL_VERSIONS,
    handle_message,
)
from content.mcp.common_tools import build_common_tools
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.operation_catalogs import (
    BILLING_PARITY_TOOLS,
    CARD_PARITY_TOOLS,
    COMMERCIAL_PARITY_TOOLS,
    COMMUNICATION_EMAIL_TOOLS,
    CONTENT_PARITY_TOOLS,
    DOCUMENT_PARITY_TOOLS,
    LEDGER_PARITY_TOOLS,
    OPERATIONS_TOOLS,
    PROJECT_TOOLS,
)
from content.mcp.principal import service_actor_for_connector
from content.mcp.registry import infer_risk, normalize_tools
from content.mcp.accounting_tools import ACCOUNTING_TOOLS
from content.mcp.client_tools import CLIENT_TOOLS
from content.mcp.communication_tools import COMMUNICATION_TOOLS
from content.mcp.secure_link_tools import SECURE_LINK_TOOLS
from content.mcp.diagnostic_tools import DIAGNOSTIC_TOOLS
from content.mcp.document_thread_tools import DOCUMENT_THREAD_TOOLS
from content.mcp.document_tools import DOCUMENT_TOOLS
from content.mcp.linkedin_tools import LINKEDIN_TOOLS
from content.mcp.linktree_template_tools import LINKTREE_TEMPLATE_TOOLS
from content.mcp.proposal_tools import PROPOSAL_TOOLS
from content.mcp.task_tools import TASK_TOOLS
from content.mcp.tools import BLOG_TOOLS
from content.models import (
    McpActionIntent,
    McpConnector,
    McpCredential,
    McpRequestLog,
)
from content.permissions import IsSuperUser

logger = logging.getLogger(__name__)

LAST_USED_TOUCH_SECONDS = 60

# Existing connector registries are compatibility surfaces. Canonical area
# connectors below compose them with the Panel parity adapters.
LEGACY_TOOLS_BY_SLUG = {
    'blog': BLOG_TOOLS,
    # Los hilos viven en su propio registro: son una relación entre documentos,
    # no una operación sobre uno, y así el catálogo base queda legible.
    'documents': DOCUMENT_TOOLS + DOCUMENT_THREAD_TOOLS,
    'clients': CLIENT_TOOLS,
    'communications': COMMUNICATION_TOOLS,
    'tasks': TASK_TOOLS,
    'accounting': ACCOUNTING_TOOLS,
    'diagnostics': DIAGNOSTIC_TOOLS,
    'proposals': PROPOSAL_TOOLS,
    'linkedin-personal': LINKEDIN_TOOLS,
}


def _canonical_tools(tools):
    result = []
    for source in tools:
        tool = deepcopy(source)
        risk = tool.get('risk', infer_risk(tool['name']))
        tool['risk'] = risk
        if risk == 'sensitive':
            tool['requires_confirmation'] = True
        result.append(tool)
    return result


def _accounting_tools(*prefixes, exact=()):
    return [
        tool for tool in ACCOUNTING_TOOLS
        if tool['name'] in exact or tool['name'].startswith(prefixes)
    ]


RAW_TOOLS_BY_SLUG = {
    **LEGACY_TOOLS_BY_SLUG,
    'documents': _canonical_tools(
        DOCUMENT_TOOLS + DOCUMENT_THREAD_TOOLS + DOCUMENT_PARITY_TOOLS
    ),
    'communications': _canonical_tools(
        COMMUNICATION_TOOLS + COMMUNICATION_EMAIL_TOOLS + SECURE_LINK_TOOLS
    ),
    'tasks': _canonical_tools(TASK_TOOLS),
    'operations': OPERATIONS_TOOLS,
    'commercial': _canonical_tools(
        CLIENT_TOOLS + PROPOSAL_TOOLS + DIAGNOSTIC_TOOLS + COMMERCIAL_PARITY_TOOLS
    ),
    'projects': PROJECT_TOOLS,
    'content': _canonical_tools(
        BLOG_TOOLS + LINKEDIN_TOOLS + CONTENT_PARITY_TOOLS + LINKTREE_TEMPLATE_TOOLS
    ),
    'accounting-ledger': _canonical_tools(
        _accounting_tools(
            'list_income', 'get_income', 'create_income', 'update_income', 'delete_income',
            'list_expense', 'get_expense', 'create_expense', 'update_expense', 'delete_expense',
            'list_pocket', 'get_pocket', 'create_pocket', 'update_pocket', 'delete_pocket',
            'list_recurring', 'get_recurring', 'create_recurring', 'update_recurring', 'delete_recurring',
            'list_ads', 'get_ads', 'create_ads', 'update_ads', 'delete_ads',
            'settle_', 'bulk_settle_', 'mute_income', 'set_recurring_',
            'archive_recurring', 'restore_recurring', 'mute_recurring',
            'bulk_action_recurring',
            exact=(
                'get_dashboard', 'get_receivables', 'get_income_detail',
                'list_change_logs',
            ),
        ) + LEDGER_PARITY_TOOLS
    ),
    'accounting-billing': _canonical_tools(
        _accounting_tools(
            'list_hosting', 'get_hosting', 'create_hosting', 'update_hosting', 'delete_hosting',
            'list_notification_recipient', 'get_notification_recipient',
            'create_notification_recipient', 'update_notification_recipient',
            'delete_notification_recipient',
            exact=('get_settings', 'update_settings'),
        ) + BILLING_PARITY_TOOLS
    ),
    'accounting-cards': _canonical_tools(
        _accounting_tools(
            'list_card_snapshot', 'get_card_snapshot', 'create_card_snapshot',
            'update_card_snapshot', 'delete_card_snapshot',
            'get_statement_', 'create_statement', 'resolve_merchants',
            'save_merchant_aliases', 'update_statement', 'finalize_statement',
            'reopen_statement', 'list_statements', 'delete_statement',
            'list_merchant_aliases', 'update_merchant_alias', 'delete_merchant_alias',
        ) + CARD_PARITY_TOOLS
    ),
}


COMMON_TOOL_SLUGS = {
    'operations', 'commercial', 'projects', 'documents', 'communications',
    'content', 'tasks', 'accounting-ledger', 'accounting-billing',
    'accounting-cards',
}
UPLOAD_TOOL_SLUGS = {
    'commercial', 'documents', 'communications', 'content', 'accounting-cards',
}

TOOLS_BY_SLUG = {
    slug: normalize_tools(tools, slug)
    for slug, tools in RAW_TOOLS_BY_SLUG.items()
}
for _slug in COMMON_TOOL_SLUGS:
    _common = build_common_tools(
        _slug,
        lambda slug=_slug: TOOLS_BY_SLUG[slug],
        include_uploads=_slug in UPLOAD_TOOL_SLUGS,
    )
    TOOLS_BY_SLUG[_slug] = normalize_tools(
        [*TOOLS_BY_SLUG[_slug], *_common],
        _slug,
    )


class McpEndpointThrottle(AnonRateThrottle):
    scope = 'mcp'

    def get_cache_key(self, request, view):
        """Rate-limit each registered connector independently per client IP.

        Codex initializes every configured connector concurrently. Sharing one
        IP-only bucket made five legitimate connectors consume each other's
        allowance. Unknown slugs deliberately share one bucket so callers
        cannot evade the throttle by inventing paths.
        """
        slug = getattr(view, 'kwargs', {}).get('slug', '')
        connector_scope = slug if slug in TOOLS_BY_SLUG else 'unknown'
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': f'{self.scope}:{connector_scope}',
            'ident': ident,
        }


class McpContentNegotiation(DefaultContentNegotiation):
    """
    MCP clients probe with Accept: text/event-stream (SSE detection). DRF's
    default negotiation raises 406 before the view runs, but the Streamable
    HTTP spec requires a plain 405 for that probe. Fall back to the first
    renderer (JSON) instead of erroring so the view controls the response.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        try:
            return super().select_renderer(request, renderers, format_suffix)
        except exceptions.NotAcceptable:
            return (renderers[0], renderers[0].media_type)


def _origin_is_foreign(request):
    """
    Streamable HTTP spec: servers MUST validate the Origin header (DNS
    rebinding defense). claude.ai's MCP client DOES send
    Origin: https://claude.ai, so known MCP client origins are allowed
    alongside our own host; anything else is rejected.
    """
    origin = request.headers.get('Origin')
    if not origin:
        return False
    if origin in getattr(settings, 'MCP_ALLOWED_ORIGINS', []):
        return False
    if urlparse(origin).netloc != request.get_host():
        # Record the exact rejected value: MCP clients' headers are not
        # documented anywhere, so this log is how we learn what they send.
        logger.warning('[MCP] rejected foreign Origin: %s', origin)
        return True
    return False


def _touch_last_used(connector, credential=None):
    now = tz.now()
    connector_is_stale = (
        connector.last_used_at is None
        or (now - connector.last_used_at).total_seconds() >= LAST_USED_TOUCH_SECONDS
    )
    credential_is_stale = (
        credential is not None
        and (
            credential.last_used_at is None
            or (now - credential.last_used_at).total_seconds() >= LAST_USED_TOUCH_SECONDS
        )
    )
    if connector_is_stale:
        McpConnector.objects.filter(pk=connector.pk).update(last_used_at=now)
    if credential_is_stale:
        McpCredential.objects.filter(pk=credential.pk).update(last_used_at=now)


def _record_event(connector, event, ok=True, detail='', **metadata):
    """Best-effort activity logging — must never break the MCP response."""
    if connector is None:
        return
    try:
        McpRequestLog.record(
            connector, event, ok=ok, detail=detail, **metadata,
        )
    except Exception:
        logger.exception('[MCP] failed to record %s event for %s', event, connector.slug)


def _argument_object_refs(arguments, *, prefix='', limit=25):
    """Extract stable resource identifiers without retaining request payloads."""
    refs = []
    if not isinstance(arguments, dict):
        return refs
    for key, value in arguments.items():
        field = f'{prefix}.{key}' if prefix else key
        if key.endswith(('_id', '_ids')):
            safe_value = value[:20] if isinstance(value, list) else value
            if isinstance(safe_value, (str, int, float, bool, list)):
                refs.append({'field': field, 'value': safe_value})
        elif isinstance(value, dict):
            refs.extend(
                _argument_object_refs(
                    value,
                    prefix=field,
                    limit=max(0, limit - len(refs)),
                )
            )
        if len(refs) >= limit:
            break
    return refs[:limit]


def _tool_call_object_refs(connector, credential, tool_name, params):
    if not isinstance(params, dict):
        return []
    arguments = params.get('arguments') or {}
    refs = _argument_object_refs(arguments)
    if tool_name not in {'confirm_action', 'cancel_action'}:
        return refs
    confirmation_id = arguments.get('confirmation_id')
    if not confirmation_id:
        return refs
    try:
        intent = McpActionIntent.objects.filter(
            pk=confirmation_id,
            connector=connector,
            credential=credential,
        ).only('tool_name', 'arguments').first()
    except (DjangoValidationError, TypeError, ValueError):
        intent = None
    if intent is None:
        return refs
    refs.append({'field': 'confirmed_tool', 'value': intent.tool_name})
    refs.extend(_argument_object_refs(intent.arguments))
    return refs[:25]


def _record_tools_call(
    connector, credential, request_id, message, payload, duration_ms,
):
    params = message.get('params') or {}
    tool_name = params.get('name', '?') if isinstance(params, dict) else '?'
    result = (payload or {}).get('result') or {}
    error = (payload or {}).get('error')
    tool = next(
        (candidate for candidate in TOOLS_BY_SLUG.get(connector.slug, [])
         if candidate['name'] == tool_name),
        {},
    )
    structured_error = result.get('structuredContent', {}).get('error', {})
    metadata = {
        'credential': credential,
        'request_id': request_id,
        'tool_name': tool_name,
        'risk_level': tool.get('risk', ''),
        'duration_ms': duration_ms,
        'object_refs': _tool_call_object_refs(
            connector, credential, tool_name, params,
        ),
    }
    if error:
        _record_event(
            connector,
            'tool_call',
            ok=False,
            detail=f'{tool_name}: {error.get("message", "")}',
            error_code=str(error.get('code', '')),
            **metadata,
        )
    elif result.get('isError'):
        text = (result.get('content') or [{}])[0].get('text', '')
        _record_event(
            connector,
            'tool_call',
            ok=False,
            detail=f'{tool_name}: {text[:150]}',
            error_code=structured_error.get('code', ''),
            **metadata,
        )
    else:
        _record_event(connector, 'tool_call', detail=tool_name, **metadata)


def _request_token(request, path_token):
    authorization = request.headers.get('Authorization', '')
    bearer = (
        authorization[7:].strip()
        if authorization.lower().startswith('bearer ') else ''
    )
    if bearer and path_token and bearer != path_token:
        return ''
    return bearer or path_token or ''


HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022


def _jsonrpc_error(message, code, detail, *, data=None):
    msg_id = message.get('id') if isinstance(message, dict) else None
    error = {'code': code, 'message': detail}
    if data:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': msg_id, 'error': error}


def _message_meta(message):
    if not isinstance(message, dict):
        return {}
    params = message.get('params')
    if not isinstance(params, dict):
        return {}
    meta = params.get('_meta')
    return meta if isinstance(meta, dict) else {}


def _is_modern_request(request, message):
    return (
        request.headers.get('MCP-Protocol-Version', '').strip()
        == MODERN_PROTOCOL_VERSION
        or _message_meta(message).get('io.modelcontextprotocol/protocolVersion')
        == MODERN_PROTOCOL_VERSION
    )


def _request_protocol(request, message):
    """Validate the self-contained envelope for the modern MCP era."""
    header_version = request.headers.get('MCP-Protocol-Version', '').strip()
    meta = _message_meta(message)
    meta_version = str(
        meta.get('io.modelcontextprotocol/protocolVersion') or ''
    ).strip()
    for version in (header_version, meta_version):
        if version and version not in SUPPORTED_PROTOCOL_VERSIONS:
            return '', False, _jsonrpc_error(
                message,
                UNSUPPORTED_PROTOCOL_VERSION,
                f'Versión MCP no soportada: {version}.',
                data={'supportedVersions': list(SUPPORTED_PROTOCOL_VERSIONS)},
            )

    modern = (
        header_version == MODERN_PROTOCOL_VERSION
        or meta_version == MODERN_PROTOCOL_VERSION
    )
    if not modern:
        version = header_version or meta_version or DEFAULT_PROTOCOL_VERSION
        if version not in LEGACY_PROTOCOL_VERSIONS:
            version = DEFAULT_PROTOCOL_VERSION
        return version, False, None

    body_method = message.get('method', '') if isinstance(message, dict) else ''
    header_method = request.headers.get('Mcp-Method', '').strip()
    if (
        header_version != MODERN_PROTOCOL_VERSION
        or meta_version != MODERN_PROTOCOL_VERSION
        or not body_method
        or header_method != body_method
    ):
        return MODERN_PROTOCOL_VERSION, True, _jsonrpc_error(
            message,
            HEADER_MISMATCH,
            'Los headers MCP no coinciden con el cuerpo de la petición.',
        )

    client_capabilities = meta.get(
        'io.modelcontextprotocol/clientCapabilities'
    )
    if not isinstance(client_capabilities, dict):
        return MODERN_PROTOCOL_VERSION, True, _jsonrpc_error(
            message,
            -32602,
            'params._meta debe incluir clientCapabilities como objeto.',
        )
    client_info = meta.get('io.modelcontextprotocol/clientInfo')
    if client_info is not None and not isinstance(client_info, dict):
        return MODERN_PROTOCOL_VERSION, True, _jsonrpc_error(
            message,
            -32602,
            'clientInfo debe ser un objeto cuando se envía.',
        )

    if body_method == 'tools/call':
        params = message.get('params') or {}
        body_name = params.get('name', '') if isinstance(params, dict) else ''
        if request.headers.get('Mcp-Name', '').strip() != body_name:
            return MODERN_PROTOCOL_VERSION, True, _jsonrpc_error(
                message,
                HEADER_MISMATCH,
                'Mcp-Name no coincide con params.name.',
            )
    return MODERN_PROTOCOL_VERSION, True, None


def _decorate_modern_result(payload, server_name, method):
    if not isinstance(payload, dict) or not isinstance(payload.get('result'), dict):
        return
    result = payload['result']
    result.setdefault('resultType', 'complete')
    meta = result.setdefault('_meta', {})
    if not isinstance(meta, dict):
        meta = {}
        result['_meta'] = meta
    meta.setdefault(
        'io.modelcontextprotocol/serverInfo',
        {**SERVER_INFO, 'name': server_name},
    )
    if method in {'server/discover', 'tools/list'}:
        result.setdefault('ttlMs', LIST_CACHE_TTL_MS)
        result.setdefault('cacheScope', 'private')


def _credential_for_request(connector, token):
    credential = connector.credential_for_token(token)
    if credential is not None:
        return credential
    # Expand/contract fallback for the brief deploy window before the data
    # migration has copied an old connector token into McpCredential.
    if connector.credentials.exists() or not connector.check_token(token):
        return None
    credential, _ = McpCredential.objects.get_or_create(
        connector=connector,
        label='Default',
        defaults={
            'token_hash': connector.token_hash,
            'token_prefix': connector.token_prefix,
        },
    )
    return credential


@api_view(['POST'])
@authentication_classes([])  # token in URL is the credential; no session ⇒ no CSRF
@permission_classes([AllowAny])
@throttle_classes([McpEndpointThrottle])
def mcp_endpoint(request, slug, token=None):
    """
    MCP Streamable HTTP endpoint for a connector (e.g. blog).
    Plain-JSON responses only (no SSE) — WSGI-compatible by design. DRF
    answers GET (SSE probe) and DELETE (session termination) with the
    spec-mandated 405; McpContentNegotiation keeps an SSE-only Accept
    header from short-circuiting into a 406.
    """
    connector_for_log = McpConnector.objects.filter(slug=slug).first()

    if _origin_is_foreign(request):
        _record_event(
            connector_for_log, 'origin_rejected', ok=False,
            detail=request.headers.get('Origin', ''),
        )
        return HttpResponse(status=403)

    tools = TOOLS_BY_SLUG.get(slug)
    connector = connector_for_log if (connector_for_log and connector_for_log.is_active) else None
    request_token = _request_token(request, token)
    credential = (
        _credential_for_request(connector, request_token)
        if connector is not None and tools is not None else None
    )
    if tools is None or connector is None or credential is None:
        if connector_for_log and not connector_for_log.is_active:
            detail = 'Conector inactivo — actívalo en el panel'
        else:
            detail = 'Token inválido (¿fue regenerado?)'
        _record_event(connector_for_log, 'auth_error', ok=False, detail=detail)
        raise Http404

    raw_message = request.data
    modern_hint = _is_modern_request(request, raw_message)
    message = raw_message
    header_method = request.headers.get('Mcp-Method')
    if (
        not modern_hint
        and header_method
        and (not isinstance(message, dict) or not message.get('method'))
    ):
        params = {}
        if header_method == 'tools/call':
            params = {
                'name': request.headers.get('Mcp-Name', ''),
                'arguments': message if isinstance(message, dict) else {},
            }
        message = {
            'jsonrpc': '2.0',
            'id': request.headers.get('Mcp-Request-Id', str(uuid.uuid4())),
            'method': header_method,
            'params': params,
        }
    protocol_version, is_modern, protocol_error = _request_protocol(
        request, message,
    )
    request_id = str(uuid.uuid4())
    if protocol_error:
        response = Response(protocol_error, status=status.HTTP_400_BAD_REQUEST)
        response['Mcp-Protocol-Version'] = (
            protocol_version or MODERN_PROTOCOL_VERSION
        )
        response['Mcp-Request-Id'] = request_id
        return response

    actor = credential.actor or service_actor_for_connector(connector)
    if credential.actor_id != actor.id:
        credential.actor = actor
        credential.save(update_fields=['actor', 'updated_at'])
    context = McpExecutionContext(
        connector=connector,
        credential=credential,
        request_id=request_id,
        actor=actor,
        request=request,
        protocol_version=protocol_version,
    )
    started = time.monotonic()
    with use_mcp_context(context):
        http_status, payload = handle_message(
            message,
            tools,
            server_name=f'projectapp-{slug}-mcp',
            context=context,
        )
    method = message.get('method') if isinstance(message, dict) else ''
    server_name = f'projectapp-{slug}-mcp'
    if is_modern:
        _decorate_modern_result(payload, server_name, method)
    duration_ms = max(0, round((time.monotonic() - started) * 1000))

    if isinstance(message, dict):
        if method in ('initialize', 'server/discover'):
            _record_event(
                connector,
                'handshake' if method == 'initialize' else 'discovery',
                detail=f'{method} OK',
                credential=credential,
                request_id=request_id,
                duration_ms=duration_ms,
            )
        elif method == 'tools/call':
            _touch_last_used(connector, credential)
            _record_tools_call(
                connector, credential, request_id, message, payload, duration_ms,
            )

    if payload is None:
        response = Response(status=http_status)
        response['Mcp-Protocol-Version'] = protocol_version
        response['Mcp-Request-Id'] = request_id
        return response
    response = Response(payload, status=http_status)
    if method == 'initialize' and isinstance(payload, dict):
        protocol_version = (
            payload.get('result', {}).get('protocolVersion')
            or protocol_version
        )
    response['Mcp-Protocol-Version'] = protocol_version
    response['Mcp-Request-Id'] = request_id
    return response


# api_view exposes the wrapped APIView class as .cls; override negotiation so
# an SSE-only Accept header reaches the view instead of 406ing in initial().
mcp_endpoint.cls.content_negotiation_class = McpContentNegotiation


# ---------------------------------------------------------------------------
# Panel management endpoints (/panel/mcps) — session + CSRF, superuser only
# ---------------------------------------------------------------------------

def _connector_payload(connector):
    tools = TOOLS_BY_SLUG.get(connector.slug, [])
    recent = [
        {
            'event': e.event,
            'ok': e.ok,
            'detail': e.detail,
            'request_id': e.request_id,
            'tool_name': e.tool_name,
            'risk': e.risk_level,
            'error_code': e.error_code,
            'duration_ms': e.duration_ms,
            'object_refs': e.object_refs,
            'credential_prefix': (
                e.credential.token_prefix if e.credential_id else ''
            ),
            'created_at': e.created_at.isoformat(),
        }
        for e in connector.request_logs.all()[:10]
    ]
    if not recent:
        connection_status = 'none'
    elif recent[0]['ok']:
        connection_status = 'connected'
    else:
        connection_status = 'error'
    risk_counts = {'read': 0, 'write': 0, 'sensitive': 0}
    for tool in tools:
        risk_counts[tool.get('risk', infer_risk(tool['name']))] += 1
    credentials = [
        {
            'id': credential.id,
            'label': credential.label,
            'token_prefix': credential.token_prefix,
            'allowed_tools': credential.allowed_tools,
            'actor': credential.actor.username if credential.actor_id else None,
            'is_usable': credential.is_usable,
            'expires_at': (
                credential.expires_at.isoformat() if credential.expires_at else None
            ),
            'revoked_at': (
                credential.revoked_at.isoformat() if credential.revoked_at else None
            ),
            'last_used_at': (
                credential.last_used_at.isoformat()
                if credential.last_used_at else None
            ),
        }
        for credential in connector.credentials.select_related('actor').all()
    ]
    return {
        'slug': connector.slug,
        'name': connector.name,
        'description': connector.description,
        'is_active': connector.is_active,
        'has_token': bool(connector.token_hash),
        'token_prefix': connector.token_prefix,
        'last_used_at': connector.last_used_at.isoformat() if connector.last_used_at else None,
        'connection_status': connection_status,
        'tool_count': len(tools),
        'risk_counts': risk_counts,
        'is_legacy': connector.slug in {
            'accounting', 'blog', 'clients', 'diagnostics',
            'linkedin-personal', 'proposals',
        },
        'credentials': credentials,
        'recent_events': recent,
        'tools': [
            {
                'name': tool['name'],
                'title': tool.get('title'),
                'description': tool['description'],
                'risk': tool.get('risk'),
                'requires_confirmation': bool(tool.get('requires_confirmation')),
                'annotations': tool.get('annotations', {}),
            }
            for tool in tools
        ],
    }


@api_view(['GET'])
@permission_classes([IsSuperUser])
def list_mcp_connectors(request):
    """List MCP connectors for /panel/mcps."""
    connectors = (
        McpConnector.objects
        .prefetch_related('request_logs__credential', 'credentials__actor')
        .all()
        .order_by('slug')
    )
    return Response([_connector_payload(c) for c in connectors], status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def generate_mcp_connector_token(request, slug):
    """Create/rotate the connector token. The full URL is returned ONCE."""
    connector = get_object_or_404(McpConnector, slug=slug)
    token = connector.generate_token()
    credential = connector.credentials.get(label='Default')
    credential.actor = service_actor_for_connector(connector)
    credential.save(update_fields=['actor', 'updated_at'])
    logger.info('[MCP] token rotated for connector %s by %s', slug, request.user.username)
    # Build from the request host so staging/local instances hand out URLs
    # that actually point at themselves (the token only exists in their DB).
    connector_url = request.build_absolute_uri(f'/api/mcp/{connector.slug}/{token}/')
    return Response({
        'connector_url': connector_url,
        'bearer_endpoint': request.build_absolute_uri(f'/api/mcp/{connector.slug}/'),
        'credential': token,
        'token_prefix': connector.token_prefix,
    }, status=status.HTTP_200_OK)


def _credential_expiry(raw_value):
    if raw_value in (None, ''):
        return None
    value = parse_datetime(str(raw_value))
    if value is not None and tz.is_naive(value):
        value = tz.make_aware(value, tz.get_current_timezone())
    if value is None or value <= tz.now():
        raise serializers.ValidationError('expires_at debe ser una fecha futura ISO 8601.')
    return value


def _allowed_tools(connector, raw_tools):
    if raw_tools in (None, []):
        return []
    if not isinstance(raw_tools, list) or not all(isinstance(item, str) for item in raw_tools):
        raise serializers.ValidationError('allowed_tools debe ser una lista de nombres.')
    available = {tool['name'] for tool in TOOLS_BY_SLUG.get(connector.slug, [])}
    unknown = sorted(set(raw_tools) - available)
    if unknown:
        raise serializers.ValidationError(
            f'Herramientas desconocidas: {", ".join(unknown)}.'
        )
    return sorted(set(raw_tools))


@api_view(['POST'])
@permission_classes([IsSuperUser])
def create_mcp_credential(request, slug):
    connector = get_object_or_404(McpConnector, slug=slug)
    label = str(request.data.get('label') or '').strip()
    if not label:
        return Response({'label': 'La etiqueta es obligatoria.'}, status=400)
    if len(label) > McpCredential._meta.get_field('label').max_length:
        return Response(
            {'label': 'La etiqueta no puede superar 100 caracteres.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        allowed_tools = _allowed_tools(connector, request.data.get('allowed_tools'))
        expires_at = _credential_expiry(request.data.get('expires_at'))
    except serializers.ValidationError as exc:
        return Response({'detail': exc.detail}, status=400)
    credential = McpCredential(
        connector=connector,
        label=label,
        token_hash='pending',
        actor=service_actor_for_connector(connector),
        allowed_tools=allowed_tools,
        expires_at=expires_at,
    )
    try:
        with transaction.atomic():
            token = credential.generate_token()
    except IntegrityError:
        return Response(
            {'label': 'Ya existe una credencial con esa etiqueta.'},
            status=status.HTTP_409_CONFLICT,
        )
    return Response({
        'id': credential.id,
        'label': credential.label,
        'credential': token,
        'token_prefix': credential.token_prefix,
        'bearer_endpoint': request.build_absolute_uri(f'/api/mcp/{connector.slug}/'),
        'connector_url': request.build_absolute_uri(
            f'/api/mcp/{connector.slug}/{token}/'
        ),
        'allowed_tools': credential.allowed_tools,
        'expires_at': credential.expires_at.isoformat() if credential.expires_at else None,
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsSuperUser])
def mcp_credential_detail(request, slug, credential_id):
    connector = get_object_or_404(McpConnector, slug=slug)
    credential = get_object_or_404(
        McpCredential, pk=credential_id, connector=connector,
    )
    if request.method == 'DELETE':
        credential.revoked_at = tz.now()
        credential.save(update_fields=['revoked_at', 'updated_at'])
        if credential.label == 'Default':
            connector.token_hash = ''
            connector.token_prefix = ''
            connector.save(update_fields=['token_hash', 'token_prefix', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
    try:
        if 'allowed_tools' in request.data:
            credential.allowed_tools = _allowed_tools(
                connector, request.data.get('allowed_tools'),
            )
        if 'expires_at' in request.data:
            credential.expires_at = _credential_expiry(request.data.get('expires_at'))
    except serializers.ValidationError as exc:
        return Response({'detail': exc.detail}, status=400)
    credential.save(update_fields=['allowed_tools', 'expires_at', 'updated_at'])
    return Response(_connector_payload(connector), status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def rotate_mcp_credential(request, slug, credential_id):
    """Rotate one credential and reveal the replacement secret exactly once."""
    connector = get_object_or_404(McpConnector, slug=slug)
    credential = get_object_or_404(
        McpCredential, pk=credential_id, connector=connector,
    )
    token = credential.generate_token()
    if credential.label == 'Default':
        connector.token_hash = credential.token_hash
        connector.token_prefix = credential.token_prefix
        connector.save(update_fields=['token_hash', 'token_prefix', 'updated_at'])
    logger.info(
        '[MCP] credential %s rotated for connector %s by %s',
        credential.id, slug, request.user.username,
    )
    return Response({
        'id': credential.id,
        'label': credential.label,
        'credential': token,
        'token_prefix': credential.token_prefix,
        'bearer_endpoint': request.build_absolute_uri(f'/api/mcp/{connector.slug}/'),
        'connector_url': request.build_absolute_uri(
            f'/api/mcp/{connector.slug}/{token}/'
        ),
        'allowed_tools': credential.allowed_tools,
        'expires_at': credential.expires_at.isoformat() if credential.expires_at else None,
    }, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsSuperUser])
def update_mcp_connector(request, slug):
    """Toggle is_active."""
    connector = get_object_or_404(McpConnector, slug=slug)
    if 'is_active' in request.data:
        try:
            is_active = serializers.BooleanField().to_internal_value(request.data['is_active'])
        except serializers.ValidationError:
            return Response(
                {'is_active': 'Valor booleano inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        connector.is_active = is_active
        connector.save(update_fields=['is_active', 'updated_at'])
        logger.info(
            '[MCP] connector %s %s by %s',
            slug, 'activated' if connector.is_active else 'deactivated',
            request.user.username,
        )
    return Response(_connector_payload(connector), status=status.HTTP_200_OK)
