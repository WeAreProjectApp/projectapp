"""Administrative parity never persists creation inputs or explicit URL results."""

import json
import uuid

import pytest
from content.models import McpActionIntent, McpConnector, McpRequestLog

from secure_links.models import SecureLink

from .conftest import CREDENTIALS, token_from
from .test_mcp_tools import call_tool, error_code, list_tools, result, text

pytestmark = pytest.mark.django_db


@pytest.fixture
def platform_mcp_token():
    connector, _ = McpConnector.objects.get_or_create(slug='communications', defaults={'name': 'Comunicaciones'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def test_mcp_create_enforces_the_owner_project(api_client, platform_mcp_token, project, client_profile, platform_client):
    response = call_tool(api_client, platform_mcp_token, 'create_platform_secure_link', {
        'owner_id': client_profile.pk, 'project_id': project.pk, 'request_id': str(uuid.uuid4()),
        'secret_type': 'credentials', 'title': 'Portal', 'fields': CREDENTIALS,
    })

    data = json.loads(text(response))
    link = SecureLink.objects.get(pk=data['id'])
    assert (link.owner_id, link.project_id, link.origin, link.audience) == (client_profile.pk, project.pk, 'platform', 'team')
    assert CREDENTIALS['password'] not in str(list(McpRequestLog.objects.values()))
    assert token_from(data['url']) not in str(list(McpRequestLog.objects.values()))
    assert not McpActionIntent.objects.exists()


def test_mcp_reused_request_with_other_input_conflicts(api_client, platform_mcp_token, project, client_profile, platform_client):
    arguments = {
        'owner_id': client_profile.pk, 'project_id': project.pk, 'request_id': str(uuid.uuid4()),
        'secret_type': 'credentials', 'title': 'Portal', 'fields': CREDENTIALS,
    }
    call_tool(api_client, platform_mcp_token, 'create_platform_secure_link', arguments)

    response = call_tool(api_client, platform_mcp_token, 'create_platform_secure_link', {**arguments, 'fields': {'password': 'different'}})

    assert error_code(response) == 'request_id_conflict'
    assert SecureLink.objects.count() == 1


def test_general_grant_does_not_include_url(api_client, platform_mcp_token):
    response = list_tools(api_client, platform_mcp_token)

    names = {tool['name'] for tool in result(response)['tools']}
    assert 'create_platform_secure_link' in names
    assert 'list_secure_link_events' in names
    assert 'get_secure_link_url' not in names


def test_url_result_is_ephemeral(api_client, platform_mcp_token, create_owned):
    link, url, _ = create_owned()
    credential = McpConnector.objects.get(slug='communications').credentials.get(label='Default')
    credential.allowed_tools = ['get_secure_link_url']
    credential.save(update_fields=['allowed_tools'])
    preview = call_tool(api_client, platform_mcp_token, 'get_secure_link_url', {'link_id': link.pk})
    confirmation_id = result(preview)['structuredContent']['confirmation_id']

    confirmed = call_tool(api_client, platform_mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})
    repeated = call_tool(api_client, platform_mcp_token, 'confirm_action', {'confirmation_id': confirmation_id})

    assert json.loads(text(confirmed))['result']['url'] == url
    assert token_from(url) not in str(list(McpActionIntent.objects.values()))
    assert token_from(url) not in str(list(McpRequestLog.objects.values()))
    assert token_from(url) not in text(repeated)
    assert json.loads(text(repeated))['result']['content_available'] is False


def test_mcp_owner_filter_omits_unowned_legacy_links(api_client, platform_mcp_token, create_owned, client_profile, make_link):
    owned, _, _ = create_owned()
    make_link(client=client_profile)

    response = call_tool(api_client, platform_mcp_token, 'list_secure_links', {'owner_id': client_profile.pk})

    data = json.loads(text(response))
    assert [link['id'] for link in data['results']] == [owned.pk]
    assert 'url' not in data['results'][0]


def test_mcp_url_history_contains_no_token(api_client, platform_mcp_token, create_owned, client_profile):
    link, url, _ = create_owned()
    from secure_links import services

    services.audited_link_url(link, actor=client_profile.user)

    response = call_tool(api_client, platform_mcp_token, 'list_secure_link_events', {'link_id': link.pk})

    data = json.loads(text(response))
    assert data['results'][0]['kind'] == 'url_accessed'
    assert token_from(url) not in text(response)
    assert CREDENTIALS['password'] not in text(response)


def test_creation_field_names_cannot_leak_into_mcp_logs(api_client, platform_mcp_token, project, client_profile, platform_client):
    response = call_tool(api_client, platform_mcp_token, 'create_platform_secure_link', {
        'owner_id': client_profile.pk, 'project_id': project.pk, 'request_id': str(uuid.uuid4()),
        'secret_type': 'credentials', 'title': 'Portal', 'fields': {CREDENTIALS['password']: 'bad'},
    })

    assert result(response)['isError'] is True
    assert CREDENTIALS['password'] not in text(response)
    assert CREDENTIALS['password'] not in str(list(McpRequestLog.objects.values()))
