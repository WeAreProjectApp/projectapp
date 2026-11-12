"""MCP catalog contract for human-managed requirement packages."""
import pytest

from content.models import McpConnector

pytestmark = pytest.mark.django_db


def tools_by_name(response):
    """Index MCP public tool declarations by their stable tool name."""
    return {row['name']: row for row in response.data['result']['tools']}


def capabilities_by_name(response):
    """Index detailed MCP capability metadata by tool name."""
    return {
        row['name']: row
        for row in response.data['result']['structuredContent']['tools']
    }


@pytest.fixture
def projects_token():
    """Create an active Projects MCP connector and return its one-use token."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Projects'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def test_projects_catalog_exposes_human_package_administration_without_client_consent(api_client, projects_token):
    """Fails if the administrative MCP can impersonate a client's allowance consent."""
    response = api_client.post(
        f'/api/mcp/projects/{projects_token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        format='json',
    )
    capabilities = api_client.post(
        f'/api/mcp/projects/{projects_token}/',
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
         'params': {'name': 'describe_capabilities', 'arguments': {}}},
        format='json',
    )

    tools = tools_by_name(response)
    capability_tools = capabilities_by_name(capabilities)
    assert response.status_code == 200
    assert {'get_project_requirement_packages', 'get_project_package_examples',
            'confirm_external_package_payment', 'begin_package_request_evaluation',
            'publish_package_size_proposal'} <= tools.keys()
    assert capability_tools['publish_package_size_proposal']['requires_confirmation'] is True
    assert 'decide_package_request' not in tools
