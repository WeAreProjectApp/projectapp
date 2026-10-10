"""Both discovery routes publish the same authorized tool contracts."""

import pytest

from content.mcp.connectors import CONNECTORS
from content.mcp.context import McpExecutionContext
from content.mcp.protocol import handle_message
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import call_tool_inprocess
from content.views.mcp_blog import TOOLS_BY_SLUG

pytestmark = pytest.mark.django_db

RESTRICTED_TOOLS = {
    'documents': ['list_folders', 'read_document', 'delete_document'],
    'projects': ['list_projects', 'get_project', 'delete_project'],
}


def _discovery_contracts(tools, *, input_key, output_key):
    return {
        tool['name']: {
            **{key: tool[key] for key in ('title', 'description', 'annotations')},
            'inputSchema': tool[input_key], 'outputSchema': tool[output_key],
        }
        for tool in tools
    }


@pytest.mark.parametrize('slug', ['documents', 'projects'])
@pytest.mark.parametrize('restricted', [False, True])
def test_discovery_preserves_the_authorized_contract(slug, restricted, superuser):
    connector, _ = McpConnector.objects.get_or_create(slug=slug, defaults={'name': slug})
    allowed = RESTRICTED_TOOLS[slug] if restricted else []
    credential = McpCredential.objects.create(
        connector=connector, label='Discovery parity', actor=superuser,
        allowed_tools=allowed,
    )
    context = McpExecutionContext(connector=connector, credential=credential, request_id='discovery-parity')

    _, response = handle_message(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
        TOOLS_BY_SLUG[slug], context=context,
    )
    described = call_tool_inprocess(slug, 'describe_capabilities', {}, credential=credential)

    listed_contracts = _discovery_contracts(response['result']['tools'], input_key='inputSchema', output_key='outputSchema')
    described_contracts = _discovery_contracts(described['tools'], input_key='input_schema', output_key='output_schema')
    assert listed_contracts == described_contracts
    assert set(listed_contracts) == {
        tool['name'] for tool in TOOLS_BY_SLUG[slug] if credential.allows(tool['name'])
    }
    assert any(tool['requires_confirmation'] for tool in described['tools'])
    assert described['connector'] == slug
    assert described['version'] == CONNECTORS[slug].version
    assert all(tool['connector'] == slug for tool in TOOLS_BY_SLUG[slug])
    assert all(
        'accepted_arguments_schema' not in tool
        for tool in [*response['result']['tools'], *described['tools']]
    )
    explicit_names = {
        tool['name'] for tool in TOOLS_BY_SLUG[slug]
        if tool.get('_panel_operation', {}).get('payload_schema') is not None
        or tool.get('_panel_operation', {}).get('query_schema') is not None
    }
    explicit_properties = [
        contract['inputSchema']['properties']
        for name, contract in listed_contracts.items() if name in explicit_names
    ]
    assert all(
        not {'data', 'query'} & properties.keys()
        and all(field.get('type') != 'object' or field.get('additionalProperties') is False for field in properties.values())
        for properties in explicit_properties
    )
