"""Exercise the actual monitoring MCP adapters against persistence and staff authorization."""
import pytest
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.monitoring_tools import MONITORING_TOOLS
from content.mcp.protocol import ToolError
from content.models import McpConnector, McpCredential
from django.contrib.auth import get_user_model

from monitoring.models import CapacityAllocation, CapacityChange, CaseActivity, Delivery
from monitoring.tests.dashboard_fixtures import create_cases

pytest_plugins = ('monitoring.tests.dashboard_fixtures',)


@pytest.fixture(name='dashboard_fixture')
def _dashboard_fixture(dashboard):
    return dashboard


def _tool(name):
    return next(item for item in MONITORING_TOOLS if item['name'] == name)['handler']


def test_case_mcp_uses_the_complete_filtered_set(dashboard_fixture):
    """Fails if MCP indicators ignore cases beyond the visible first page."""
    create_cases(dashboard_fixture['source'], 26)
    result = _tool('list_monitoring_cases')({'snapshot': 'new', 'resource': dashboard_fixture['project'].pk})
    assert result['count'] == 26
    assert result['summary']['active']['critical'] == 26


def test_capacity_mcp_updates_the_informational_record(dashboard_fixture):
    """Fails if MCP capacity updates do not persist the informational allocation."""
    result = _tool('update_monitoring_capacity')({'resource_id': dashboard_fixture['project'].pk, 'version': 0, 'cpu_mode': 'shared', 'ram_mode': 'assigned', 'ram_bytes': 1048576, 'storage_mode': 'unknown'})
    assert result['allocation']['ram_bytes'] == 1048576
    assert CapacityAllocation.objects.get().version == 1


def test_capacity_history_mcp_preserves_a_zero_bound(dashboard_fixture):
    """Fails if MCP loses the upper bound of an initially empty capacity history."""
    allocation = CapacityAllocation.objects.create(resource=dashboard_fixture['project'])
    first = _tool('list_monitoring_capacity_history')({'resource_id': dashboard_fixture['project'].pk})
    CapacityChange.objects.create(allocation=allocation, before={}, after={})

    frozen = _tool('list_monitoring_capacity_history')({
        'resource_id': dashboard_fixture['project'].pk,
        'changes_before': first['history_bounds']['changes'],
    })

    assert first['history_bounds'] == {'changes': 0}
    assert frozen['count'] == 0
    assert frozen['results'] == []


def test_note_mcp_preserves_real_authorship(dashboard_fixture):
    """Fails if an MCP note loses the actor who submitted it."""
    case = create_cases(dashboard_fixture['source'], 1)[0]
    _tool('add_monitoring_case_note')({'case_id': case.pk, 'text': 'Comprobación MCP'})
    assert CaseActivity.objects.get().actor == dashboard_fixture['actor']
    assert CaseActivity.objects.get().text == 'Comprobación MCP'


def test_case_mcp_returns_bounded_history_pages(dashboard_fixture):
    """Fails if the MCP case detail loses page controls or the captured history bounds."""
    case = create_cases(dashboard_fixture['source'], 1)[0]
    CaseActivity.objects.bulk_create([
        CaseActivity(case=case, kind='note', text=f'Nota MCP {number}')
        for number in range(26)
    ])
    Delivery.objects.bulk_create([
        Delivery(
            source=dashboard_fixture['source'], case=case, external_id=f'mcp-history-{number}',
            digest=f'{number:064x}', kind='detection', observed_at=case.last_seen_at,
        )
        for number in range(26)
    ])

    result = _tool('get_monitoring_case')({
        'case_id': case.pk,
        'history_snapshot': True,
        'activities_page': 2,
        'deliveries_page': 2,
    })

    assert result['activities']['count'] == result['deliveries']['count'] == 26
    assert result['activities']['page'] == result['deliveries']['page'] == 2
    assert len(result['activities']['results']) == len(result['deliveries']['results']) == 1
    assert result['history_bounds']['activities'] >= result['activities']['results'][0]['id']
    assert result['history_bounds']['deliveries'] >= result['deliveries']['results'][0]['id']


def test_case_mcp_rejects_a_missing_case_identifier(db):
    """Fails if the MCP adapter sends a case-detail request without its required identifier."""
    with pytest.raises(ToolError) as rejected:
        _tool('get_monitoring_case')({})

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.details['errors'] == [
        {'field': 'case_id', 'code': 'required', 'message': 'case_id es obligatorio.'},
    ]


def test_mcp_adapter_rejects_a_non_staff_actor(dashboard_fixture):
    """Fails if an MCP client without staff authority can consult capacity."""
    actor = get_user_model().objects.create_user(username='monitoring-client')
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects',
        defaults={'name': 'Projects'},
    )
    context = McpExecutionContext(
        connector=connector,
        credential=None,
        request_id='fixture',
        actor=actor,
    )
    with (
        use_mcp_context(context),
        pytest.raises(ToolError) as rejected,
    ):
        _tool('get_monitoring_capacity')({'resource_id': dashboard_fixture['project'].pk})
    assert rejected.value.code == 'FORBIDDEN'
    assert CapacityAllocation.objects.count() == 0


def test_restricted_mcp_credential_cannot_write_capacity(dashboard_fixture):
    """Fails if a read-only MCP credential can mutate capacity data."""
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save()
    credential = McpCredential.objects.create(connector=connector, label='Monitoring read only', actor=dashboard_fixture['actor'], allowed_tools=['get_monitoring_catalog'])
    token = credential.generate_token()
    response = dashboard_fixture['client'].post('/api/mcp/projects/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'update_monitoring_capacity', 'arguments': {'resource_id': dashboard_fixture['project'].pk, 'version': 0, 'cpu_mode': 'shared', 'ram_mode': 'shared', 'storage_mode': 'shared'}}}, format='json', HTTP_AUTHORIZATION=f'Bearer {token}')
    assert response.status_code == 200
    assert response.json()['result']['isError'] is True
    assert CapacityAllocation.objects.count() == 0
