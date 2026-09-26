"""Secure-link tools on the communications MCP connector."""

import json

import pytest
from content.models import McpActionIntent, McpConnector, McpRequestLog

from secure_links.models import SecureLink

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db


@pytest.fixture
def mcp_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug='communications', defaults={'name': 'Gestor de Comunicaciones'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def call_tool(api_client, token, name, arguments):
    return api_client.post(
        f'/api/mcp/communications/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}},
        format='json',
    )


def result(response):
    return response.data['result']


def text(response):
    return result(response)['content'][0]['text']


def test_create_returns_url_once_and_reads_never_expose_it(api_client, mcp_token, client_profile, project):
    """Falla si el MCP puede recuperar la URL o el contenido después de crear."""
    created = call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'credentials', 'title': 'Admin portal', 'fields': CREDENTIALS,
        'client_id': client_profile.pk, 'project_id': project.pk,
    })
    data = json.loads(text(created))
    listed = call_tool(api_client, mcp_token, 'list_secure_links', {'client_id': client_profile.pk})
    detail = call_tool(api_client, mcp_token, 'get_secure_link', {'link_id': data['id']})

    token = token_from(data['url'])
    link = SecureLink.objects.get(pk=data['id'])
    assert link.origin == SecureLink.Origin.MCP and link.project == project
    for response in (listed, detail):
        assert token not in text(response) and CREDENTIALS['password'] not in text(response)
    assert json.loads(text(listed))['count'] == 1


def test_create_requires_content(api_client, mcp_token):
    """Falla si el asistente puede crear un enlace sin el secreto."""
    response = call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'credentials', 'title': 'Sin contenido', 'fields': {},
    })

    assert result(response)['isError'] is True
    assert 'pídeselo al operador' in text(response)
    assert not SecureLink.objects.exists()


def test_secret_values_are_not_copied_to_request_logs(api_client, mcp_token):
    """Falla si la contraseña queda registrada en la bitácora del conector."""
    call_tool(api_client, mcp_token, 'create_secure_link', {
        'secret_type': 'credentials', 'title': 'Log check', 'fields': CREDENTIALS,
    })

    assert CREDENTIALS['password'] not in str(list(McpRequestLog.objects.values()))
    assert not McpActionIntent.objects.exists()


def test_reactivation_requires_confirmation_and_hides_url(api_client, mcp_token, make_link):
    """Falla si el asistente reactiva sin confirmación o si la URL queda persistida."""
    from secure_links import services

    link, url = make_link()
    services.reveal(token_from(url))

    preview = call_tool(api_client, mcp_token, 'reactivate_secure_link', {'link_id': link.pk})
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    link.refresh_from_db()
    assert link.status == 'consumed'

    confirmed = call_tool(api_client, mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})

    link.refresh_from_db()
    assert link.status == 'active'
    assert token_from(url) not in text(confirmed)
    assert token_from(url) not in str(list(McpActionIntent.objects.values()))


def test_revoke_tool_blocks_link(api_client, mcp_token, make_link):
    """Falla si revocar desde el asistente deja el enlace abrible."""
    link, _url = make_link()

    response = call_tool(api_client, mcp_token, 'revoke_secure_link', {'link_id': link.pk})

    assert json.loads(text(response))['status'] == 'revoked'
