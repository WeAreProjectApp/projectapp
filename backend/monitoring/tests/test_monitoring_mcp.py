"""Exercise the actual monitoring MCP adapters against persistence and staff authorization."""
import pytest
from django.contrib.auth import get_user_model

from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.monitoring_tools import MONITORING_TOOLS
from content.mcp.protocol import ToolError
from content.models import McpConnector, McpCredential
from monitoring.models import CapacityAllocation, CaseActivity
from monitoring.tests.dashboard_fixtures import dashboard, create_cases


def tool(name):
    return next(item for item in MONITORING_TOOLS if item['name'] == name)['handler']


def test_case_mcp_uses_the_complete_filtered_set(dashboard):
    create_cases(dashboard['source'], 26)
    result = tool('list_monitoring_cases')({'snapshot': 'new', 'resource': dashboard['project'].pk})
    assert result['count'] == 26
    assert result['summary']['active']['critical'] == 26


def test_capacity_mcp_updates_the_informational_record(dashboard):
    result = tool('update_monitoring_capacity')({'resource_id': dashboard['project'].pk, 'version': 0, 'cpu_mode': 'shared', 'ram_mode': 'assigned', 'ram_bytes': 1048576, 'storage_mode': 'unknown'})
    assert result['allocation']['ram_bytes'] == 1048576
    assert CapacityAllocation.objects.get().version == 1


def test_note_mcp_preserves_real_authorship(dashboard):
    case = create_cases(dashboard['source'], 1)[0]
    tool('add_monitoring_case_note')({'case_id': case.pk, 'text': 'Comprobación MCP'})
    assert CaseActivity.objects.get().actor == dashboard['actor']
    assert CaseActivity.objects.get().text == 'Comprobación MCP'


def test_mcp_adapter_rejects_a_non_staff_actor(dashboard):
    actor = get_user_model().objects.create_user(username='monitoring-client')
    with use_mcp_context(McpExecutionContext(connector=None, credential=None, request_id='fixture', actor=actor)):
        with pytest.raises(ToolError):
            tool('get_monitoring_capacity')({'resource_id': dashboard['project'].pk})
    assert CapacityAllocation.objects.count() == 0


def test_restricted_mcp_credential_cannot_write_capacity(dashboard):
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save()
    credential = McpCredential.objects.create(connector=connector, label='Monitoring read only', actor=dashboard['actor'], allowed_tools=['get_monitoring_catalog'])
    token = credential.generate_token()
    response = dashboard['client'].post('/api/mcp/projects/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'update_monitoring_capacity', 'arguments': {'resource_id': dashboard['project'].pk, 'version': 0, 'cpu_mode': 'shared', 'ram_mode': 'shared', 'storage_mode': 'shared'}}}, format='json', HTTP_AUTHORIZATION=f'Bearer {token}')
    assert response.status_code == 200
    assert response.json()['result']['isError'] is True
    assert CapacityAllocation.objects.count() == 0
