"""Registered MCP handlers retain their own validation and confirmation guards."""
import pytest

from content.mcp.building_with_us_tools import BUILDING_WITH_US_TOOLS
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.models import BuildingWithUsContractMirror, BuildingWithUsContractRevision, BuildingWithUsProgramRevision
from content.services import building_with_us_contract_service as contract_service

pytestmark = pytest.mark.django_db
WRITE_TOOLS = [
    'update_building_with_us_program', 'restore_building_with_us_program_version',
    'update_building_with_us_contract', 'restore_building_with_us_contract_version',
    'initialize_building_with_us_contract_mirror',
]


@pytest.fixture
def operations():
    return {tool['name']: tool for tool in BUILDING_WITH_US_TOOLS}


@pytest.mark.parametrize('name', ['get_building_with_us_program', 'get_building_with_us_contract'])
@pytest.mark.parametrize('arguments', [None, [], {'unexpected': True}])
def test_read_handler_rejects_unknown_arguments(operations, name, arguments):
    """Fails if registered read handlers rely entirely on transport argument validation."""
    with pytest.raises(ToolError) as error:
        operations[name]['handler'](arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert str(error.value) == 'Hay argumentos desconocidos.'
    assert error.value.details == {}


@pytest.mark.parametrize('name', WRITE_TOOLS)
@pytest.mark.parametrize('context_kind', ['missing', 'unconfirmed'])
def test_write_handler_requires_confirmation(operations, building_with_us_mcp, name, context_kind):
    """Fails if direct tool invocation can bypass durable confirmation."""
    _, credential = building_with_us_mcp
    unconfirmed = McpExecutionContext(connector=credential.connector, credential=credential,
                                     request_id='unconfirmed-write', actor=credential.actor)
    context = {'missing': None, 'unconfirmed': unconfirmed}[context_kind]

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        operations[name]['handler']({})

    assert error.value.code == 'CONFIRMATION_REQUIRED'
    assert str(error.value) == 'La operación requiere confirm_action.'
    assert BuildingWithUsProgramRevision.objects.count() == 1
    assert BuildingWithUsContractRevision.objects.count() == 1


@pytest.mark.parametrize('name', WRITE_TOOLS)
def test_confirmed_handler_requires_frozen_etags(operations, building_with_us_mcp, name):
    """Fails if a confirmed handler can apply an intent lacking preview dependencies."""
    _, credential = building_with_us_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='missing-preview-etags', actor=credential.actor, confirmation_bypass=True)

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        operations[name]['handler']({})

    assert error.value.code == 'STALE_VERSION'
    assert str(error.value) == 'La confirmación no conserva la versión previsualizada.'
    assert BuildingWithUsContractMirror.objects.count() == 0


@pytest.mark.parametrize('name', ['list_building_with_us_program_versions', 'list_building_with_us_contract_versions'])
def test_history_handler_preserves_service_errors(operations, name):
    """Fails if tool error translation loses the service's validation code or explanation."""
    with pytest.raises(ToolError) as error:
        operations[name]['handler']({'limit': 0})

    assert error.value.code == 'VALIDATION_ERROR'
    assert str(error.value) == 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.'
    assert error.value.details == {}


@pytest.mark.parametrize('entrypoint', ['prepare_arguments', 'handler'])
def test_initialization_rejects_unknown_arguments(operations, building_with_us_mcp, building_with_us_contract_folder, entrypoint):
    """Fails if initialization accepts undeclared inputs before or after confirmation."""
    _, credential = building_with_us_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='unknown-initialization-arguments', actor=credential.actor, confirmation_bypass=True)
    public = {'folder_id': building_with_us_contract_folder.pk, 'unexpected': True}
    arguments = {
        'prepare_arguments': public,
        'handler': {**public, '_expected_etags': contract_service.resource_etags(public)},
    }

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        operations['initialize_building_with_us_contract_mirror'][entrypoint](arguments[entrypoint])

    assert error.value.code == 'VALIDATION_ERROR'
    assert str(error.value) == 'Hay argumentos desconocidos.'
    assert BuildingWithUsContractMirror.objects.count() == 0
