"""In-process assertions for MCP previews and their corresponding mutations."""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from accounts.document_views import _visible_docs_qs
from accounts.models import Project
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory

from content.mcp.confirmation import requires_durable_confirmation
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.principal import service_actor_for_connector
from content.mcp.protocol import DEFAULT_PROTOCOL_VERSION, ToolError, handle_message
from content.models import Document, DocumentFolder

_WRITE_PREFIX = re.compile(r'^(INSERT|UPDATE|DELETE)\b', re.IGNORECASE)
_WRITE_TABLE = re.compile(
    r'^(?:INSERT(?:\s+OR\s+\w+|\s+IGNORE)?\s+INTO|UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM)'
    r'\s+([\w.`"\[\]]+)', re.IGNORECASE,
)


def assert_no_writes(fn, *args, allow_tables=(), **kwargs):
    """Reject writes made by a preview, including writes that are rolled back."""
    allowed = {name.lower() for name in allow_tables}
    with CaptureQueriesContext(connection) as captured:
        try:
            result = fn(*args, **kwargs)
        finally:
            writes = []
            for query in captured.captured_queries:
                sql = query['sql'].strip()
                if not _WRITE_PREFIX.match(sql):
                    continue
                match = _WRITE_TABLE.match(sql)
                table = match.group(1).translate(str.maketrans('', '', '`"[]')).rsplit('.', 1)[-1] if match else None
                if table is None or table.lower() not in allowed:
                    writes.append(sql)
            assert not writes, 'Unexpected SQL writes:\n' + '\n'.join(writes)
    return result


def ownership_state():
    """Snapshot ownership and the real portal audience in a stable JSON shape."""
    folders = list(DocumentFolder.objects.order_by('pk').values(
        'id', 'name', 'parent_id', 'order', 'project_id', 'client_user_id',
        'managed_project_id', 'managed_client_id', 'is_archived', 'archived_via_folder_id',
    ))
    documents = list(Document.objects.order_by('pk').values(
        'id', 'folder_id', 'project_id', 'client_user_id', 'is_client_visible',
        'is_archived', 'archived_via_folder_id',
    ))
    user_ids = (
        {row['client_user_id'] for row in documents}
        | {row['client_user_id'] for row in folders}
        | set(Project.objects.values_list('client_id', flat=True))
    ) - {None}
    portal = {
        str(user.pk): list(_visible_docs_qs(SimpleNamespace(user=user)).order_by('pk').values_list('pk', flat=True))
        for user in get_user_model().objects.filter(pk__in=user_ids).order_by('pk')
    }
    admin_request = SimpleNamespace(user=SimpleNamespace(profile=SimpleNamespace(is_admin=True)))
    return {
        'folders': folders, 'documents': documents, 'portal': portal,
        'admin': list(_visible_docs_qs(admin_request).order_by('pk').values_list('pk', flat=True)),
    }


def _unpredicted(preview, before_state):
    return None


@dataclass
class PreviewApplyPair:
    name: str
    preview: Callable[[dict], dict]
    apply: Callable[[dict, dict], Any]
    observe: Callable[[], Any] = ownership_state
    predicted: Callable[[dict, Any], Any | None] = _unpredicted


def check_pair(pair, args, *, preview_allow_tables=()):
    before = pair.observe()
    preview = assert_no_writes(pair.preview, args, allow_tables=preview_allow_tables)
    if preview['can_apply'] is False:
        try:
            pair.apply(args, preview)
        except ToolError as exc:
            result = exc
        else:
            raise AssertionError(f'{pair.name}: a blocked preview was applied.')
        blockers = result.details.get('blockers')
        assert isinstance(blockers, list), f'{pair.name}: apply did not return structured blockers.'
        assert sorted(row['code'] for row in blockers) == sorted(row['code'] for row in preview['blockers']), pair.name
        assert pair.observe() == before, f'{pair.name}: a blocked apply changed ownership.'
    else:
        expected = pair.predicted(preview, before)
        result = pair.apply(args, preview)
        if expected is not None:
            assert pair.observe() == expected, f'{pair.name}: apply differs from its prediction.'
    return preview, result


def call_tool_inprocess(slug, name, arguments, *, credential):
    """Use the endpoint's tools and history boundaries without throttling.

    Initialize credential.actor before asserting a call is read-only; its first
    resolution persists the same service actor binding as the HTTP endpoint.
    """
    from content.views.mcp_blog import TOOLS_BY_SLUG

    connector = credential.connector
    if connector.slug != slug:
        raise ValueError('The credential must belong to the requested connector.')
    tools = TOOLS_BY_SLUG[slug]
    message = {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }
    actor = credential.actor or service_actor_for_connector(connector)
    if credential.actor_id != actor.pk:
        credential.actor = actor
        credential.save(update_fields=['actor', 'updated_at'])
    context = McpExecutionContext(
        connector=connector, credential=credential, request_id=str(uuid.uuid4()),
        actor=actor, protocol_version=DEFAULT_PROTOCOL_VERSION,
        request=APIRequestFactory().post(f'/api/mcp/{slug}/', message, format='json', HTTP_HOST='testserver'),
    )
    durable = name == 'confirm_action' and requires_durable_confirmation(arguments, tools, context)
    with use_mcp_context(context, atomic_history=not durable):
        _status, response = handle_message(message, tools, server_name=f'projectapp-{slug}-mcp', context=context)
    return response['result']['structuredContent']
