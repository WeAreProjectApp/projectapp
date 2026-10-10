"""Credential-aware HTTP parity for every registered MCP connector."""
import pytest

from content.mcp.connectors import (
    CONFIRMATION_NOTICE,
    CONNECTORS,
    DIRECT_EXECUTION_NOTICE,
    TOOLS_BY_SLUG,
)
from content.models import McpConnector, McpCredential


pytestmark = pytest.mark.django_db
CONTROL_TOOLS = {'describe_capabilities', 'confirm_action', 'cancel_action'}
SERVER_INFO_KEY = 'io.modelcontextprotocol/serverInfo'


def _message(method, params, modern):
    params = dict(params or {})
    headers = {}
    if modern:
        params['_meta'] = {
            'io.modelcontextprotocol/protocolVersion': '2026-07-28',
            'io.modelcontextprotocol/clientCapabilities': {},
            'io.modelcontextprotocol/clientInfo': {'name': 'parity-tests', 'version': '1.0.0'},
        }
        headers = {'HTTP_MCP_PROTOCOL_VERSION': '2026-07-28', 'HTTP_MCP_METHOD': method}
        if method == 'tools/call':
            headers['HTTP_MCP_NAME'] = params['name']
    return {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}, headers


@pytest.fixture
def rpc(api_client, slug):
    connector, _ = McpConnector.objects.get_or_create(slug=slug, defaults={'name': slug})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = connector.credentials.get(label='Default')
    credential.allowed_tools = [tool['name'] for tool in TOOLS_BY_SLUG[slug]]
    credential.save(update_fields=['allowed_tools'])

    def call(method, params=None, *, modern=False, bearer=False, credential_token=None):
        request_token = credential_token or token
        message, headers = _message(method, params, modern)
        url = f'/api/mcp/{slug}/{request_token}/'
        if bearer:
            url = f'/api/mcp/{slug}/'
            headers['HTTP_AUTHORIZATION'] = f'Bearer {request_token}'
        response = api_client.post(url, message, format='json', **headers)
        assert response.status_code == 200, response.json()
        assert 'error' not in response.json(), response.json()
        return response.json()['result']

    call.connector = connector
    return call


def _described_by_name(result):
    return {
        tool['name']: {
            'name': tool['name'], 'title': tool['title'], 'description': tool['description'],
            'inputSchema': tool['input_schema'], 'outputSchema': tool['output_schema'],
            'annotations': tool['annotations'],
        }
        for tool in result['structuredContent']['tools']
    }


def _server_infos(initialized, discovered, listed):
    infos = [initialized['serverInfo'], discovered['_meta'][SERVER_INFO_KEY]]
    list_info = listed.get('_meta', {}).get(SERVER_INFO_KEY)
    if list_info is not None:
        infos.append(list_info)
    return infos


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_full_scope_discovery_matches_capabilities(slug, rpc):
    """Both HTTP surfaces publish every public field for an unrestricted scope."""
    listed = rpc('tools/list', modern=True, bearer=True)['tools']
    described = rpc('tools/call', {'name': 'describe_capabilities', 'arguments': {}}, modern=True, bearer=True)

    assert {tool['name'] for tool in listed} == {tool['name'] for tool in TOOLS_BY_SLUG[slug]}
    assert {tool['name']: tool for tool in listed} == _described_by_name(described)


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_scoped_credential_discovery_matches_capabilities(slug, rpc):
    """A separate Bearer credential exposes precisely its scope plus controls."""
    available = [tool['name'] for tool in TOOLS_BY_SLUG[slug] if tool['name'] not in CONTROL_TOOLS]
    allowed = available[:2]
    credential = McpCredential.objects.create(connector=rpc.connector, label='Parity scope', allowed_tools=allowed)
    token = credential.generate_token()

    listed = rpc('tools/list', modern=True, bearer=True, credential_token=token)['tools']
    described = rpc('tools/call', {'name': 'describe_capabilities', 'arguments': {}}, modern=True, bearer=True, credential_token=token)

    assert len(listed) == min(2, len(available)) + len(CONTROL_TOOLS)
    assert {tool['name'] for tool in listed} == set(allowed) | CONTROL_TOOLS
    assert {tool['name']: tool for tool in listed} == _described_by_name(described)


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_handshakes_announce_registry_version(slug, rpc):
    """Legacy and modern handshakes agree with capabilities and the registry."""
    initialized = rpc('initialize', {'protocolVersion': '2025-11-25'})
    discovered = rpc('server/discover', modern=True, bearer=True)
    listed = rpc('tools/list', modern=True, bearer=True)
    described = rpc('tools/call', {'name': 'describe_capabilities', 'arguments': {}}, modern=True, bearer=True)
    infos = _server_infos(initialized, discovered, listed)

    assert {info['name'] for info in infos} == {f'projectapp-{slug}-mcp'}
    assert {info['version'] for info in infos} | {described['structuredContent']['version']} == {CONNECTORS[slug].version}


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_instructions_match_confirmation_contract(slug, rpc):
    """Confirmation and direct-execution promises follow the actual connector."""
    spec = CONNECTORS[slug]
    initialized = rpc('initialize', {'protocolVersion': '2025-11-25'})
    discovered = rpc('server/discover', modern=True, bearer=True)
    direct_notice = DIRECT_EXECUTION_NOTICE.format(canonical_area=spec.canonical_area)
    requires_confirmation = any(tool.get('requires_confirmation') for tool in TOOLS_BY_SLUG[slug])

    assert initialized['instructions'] == discovered['instructions'] == spec.instructions
    assert (CONFIRMATION_NOTICE in initialized['instructions']) == requires_confirmation
    assert (direct_notice in initialized['instructions']) == spec.compatibility
