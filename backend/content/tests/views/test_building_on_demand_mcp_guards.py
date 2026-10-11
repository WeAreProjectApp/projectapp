"""Fail-closed transport and published schema guards for the dedicated connector."""
import pytest

from content.mcp.building_on_demand_contract_tools import BUILDING_ON_DEMAND_CONTRACT_TOOLS
from content.mcp.building_on_demand_tools import BUILDING_ON_DEMAND_TOOLS
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import schema_problems
from content.models import (
    BuildingOnDemandContractRevision, BuildingOnDemandProgramRevision, McpActionIntent, McpConnector, McpUpload,
)
from content.tests.building_on_demand_fixtures import rpc_call

pytestmark = pytest.mark.django_db
TOOLS = {tool['name']: tool for tool in [*BUILDING_ON_DEMAND_TOOLS, *BUILDING_ON_DEMAND_CONTRACT_TOOLS]}
READ_NAMES = sorted(name for name, tool in TOOLS.items() if tool['risk'] == 'read')


@pytest.fixture
def unknown_arguments(name):
    """Satisfy root presence checks while isolating an undeclared input."""
    return {**dict.fromkeys(TOOLS[name]['input_schema'].get('required', [])), 'unexpected': True}


def test_inactive_connector_refuses_rpc(api_client, building_on_demand_mcp):
    """Fails if a valid credential can access an administratively disabled connector."""
    token, credential = building_on_demand_mcp
    McpConnector.objects.filter(pk=credential.connector_id).update(is_active=False)

    response = api_client.post(f'/api/mcp/building-on-demand/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'get_building_on_demand_program', 'arguments': {}},
    }, format='json')

    assert response.status_code == 404
    assert not McpActionIntent.objects.filter(credential=credential).exists()


@pytest.mark.parametrize('name', sorted(TOOLS))
def test_rpc_rejects_unknown_arguments_before_execution(api_client, building_on_demand_mcp, name, unknown_arguments):
    """Fails if a dedicated tool accepts undeclared inputs before preparing its action."""
    token, credential = building_on_demand_mcp

    result = rpc_call(api_client, token, name, unknown_arguments)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'unknown_field'
    assert result['structuredContent']['error']['details']['errors'] == [{
        'field': 'unexpected', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.',
    }]
    assert not McpActionIntent.objects.filter(credential=credential).exists()
    assert BuildingOnDemandProgramRevision.objects.count() == 1
    assert BuildingOnDemandContractRevision.objects.count() == 1


@pytest.mark.parametrize('name', READ_NAMES)
def test_read_handler_rejects_undeclared_inputs(name):
    """Fails if direct read handlers admit inputs hidden from their published schemas."""
    with pytest.raises(ToolError) as error:
        TOOLS[name]['handler']({'unexpected': True})

    assert (error.value.code, str(error.value)) == ('VALIDATION_ERROR', 'Hay argumentos desconocidos.')


@pytest.mark.parametrize('name', [
    'update_building_on_demand_program', 'update_building_on_demand_contract',
    'sync_building_on_demand_contract_mirror',
])
def test_write_without_mcp_context_is_refused(name):
    """Fails if absent MCP context authorizes a program, contract or sync write."""
    with use_mcp_context(None, atomic_history=False), pytest.raises(ToolError) as error:
        TOOLS[name]['handler']({})

    assert error.value.code == 'CONFIRMATION_REQUIRED'
    assert BuildingOnDemandProgramRevision.objects.count() == 1
    assert BuildingOnDemandContractRevision.objects.count() == 1


def test_discovery_publishes_closed_described_schemas(api_client, building_on_demand_mcp):
    """Fails if discovery hides the explicit input contract needed to administer cells."""
    token, _ = building_on_demand_mcp

    catalog = rpc_call(api_client, token, 'describe_capabilities', {})['structuredContent']
    violations = [problem for tool in catalog['tools'] for problem in schema_problems(tool)]
    short_descriptions = [tool['name'] for tool in catalog['tools'] if len(tool['description'].strip()) < 40]
    open_roots = [tool['name'] for tool in catalog['tools'] if tool['input_schema'].get('additionalProperties') is not False]

    assert len(catalog['tools']) == 35
    assert violations == []
    assert short_descriptions == []
    assert open_roots == []


@pytest.mark.parametrize('language', ['fr', ['es'], None, True])
def test_program_pdf_rejects_invalid_language(api_client, building_on_demand_mcp, language):
    """Fails if PDF transport coerces an invalid language into an artifact request."""
    token, credential = building_on_demand_mcp

    result = rpc_call(api_client, token, 'render_building_on_demand_program_pdf', {'lang': language})

    assert result['isError'] is True
    assert result['structuredContent']['error'] == {
        'code': 'INVALID_LANGUAGE', 'message': 'Usa es o en.', 'details': {'path': 'lang'},
    }
    assert not McpUpload.objects.filter(credential=credential).exists()


@pytest.mark.parametrize('entrypoint', ['prepare_arguments', 'handler'])
def test_sync_rejects_undeclared_inputs(building_on_demand_mcp, entrypoint):
    """Fails if sync preparation or confirmed execution accepts hidden arguments."""
    _, credential = building_on_demand_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='unknown-sync-input', actor=credential.actor, confirmation_bypass=True)
    arguments = {'unexpected': True}
    calls = {'prepare_arguments': arguments, 'handler': {**arguments, '_expected_etags': {}}}

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        TOOLS['sync_building_on_demand_contract_mirror'][entrypoint](calls[entrypoint])

    assert error.value.code == 'VALIDATION_ERROR'
    assert str(error.value) == 'Hay argumentos desconocidos.'
