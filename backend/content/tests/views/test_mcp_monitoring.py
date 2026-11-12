"""MCP contracts for Operations follow-up over monitoring records."""
import json
from types import SimpleNamespace

import pytest
from accounts.models import Project
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import handle_message
from content.models import McpActionIntent, McpConnector, McpCredential
from monitoring.models import Case, CaseActivity, Report, Resource, Source


pytestmark = pytest.mark.django_db

MONITORING_TOOL_NAMES = {
    'get_monitoring_catalog',
    'list_monitoring_cases',
    'get_monitoring_case',
    'update_monitoring_case_state',
    'create_monitoring_case_note',
    'list_monitoring_reports',
    'get_monitoring_report',
    'link_monitoring_resource_project',
}


def _rpc(method, params=None):
    message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _content(response):
    return json.loads(response.data['result']['content'][0]['text'])


def _structured(response):
    return response.data['result']['structuredContent']


def _call(api_client, token, name, arguments=None):
    return api_client.post(
        f'/api/mcp/operations/{token}/',
        _rpc('tools/call', {'name': name, 'arguments': arguments or {}}),
        format='json',
    )


def _credential(connector, token, allowed_tools=None):
    return McpCredential.objects.create(
        connector=connector,
        label='Monitoring contract',
        catalog='canonical',
        token_hash=McpCredential.hash_token(token),
        token_prefix=token[:8],
        allowed_tools=allowed_tools or [],
    )


@pytest.fixture
def monitoring_mcp_case(make_client_profile):
    profile = make_client_profile()
    project = Project.objects.create(name='Proyecto observado', client=profile.user)
    server = Resource.objects.create(key='server-monitoring', name='Servidor observado', kind='server')
    resource = Resource.objects.create(
        key='project-monitoring', name='Proyecto monitoreado', kind='project', server=server,
    )
    source = Source.objects.create(resource=resource, key='integrity', name='Integridad')
    observed_at = timezone.now()
    case = Case.objects.create(
        source=source,
        fingerprint='integrity:monitoring-contract',
        fingerprint_hash='b' * 64,
        title='Respaldo pendiente',
        severity='critical',
        evidence={'rule': 'backup_age', 'result': 'stale'},
        first_seen_at=observed_at,
        last_seen_at=observed_at,
        detections=1,
        version=2,
    )
    report = Report.objects.create(
        source=source,
        title='Reporte operativo',
        observed_at=observed_at,
        text='El respaldo requiere seguimiento.',
    )
    connector, _ = McpConnector.objects.update_or_create(
        slug='operations',
        defaults={'name': 'Gestor de operaciones', 'is_active': True, 'retired_at': None},
    )
    connector.credentials.all().delete()
    token = 'operations-monitoring-contract'
    credential = _credential(connector, token)
    return SimpleNamespace(
        project=project, resource=resource, source=source, case=case, report=report,
        connector=connector, credential=credential, token=token,
    )


def test_operations_discovery_publishes_monitoring_tools(api_client, monitoring_mcp_case):
    """Fails if Operations omits a monitoring follow-up operation or advertises the wrong public version."""
    discover = api_client.post(
        f'/api/mcp/operations/{monitoring_mcp_case.token}/', _rpc('server/discover'), format='json',
    )
    listed = api_client.post(
        f'/api/mcp/operations/{monitoring_mcp_case.token}/', _rpc('tools/list'), format='json',
    )

    tools = {tool['name'] for tool in listed.data['result']['tools']}
    server = discover.data['result']['_meta']['io.modelcontextprotocol/serverInfo']
    assert discover.status_code == 200
    assert server == {'name': 'projectapp-operations-mcp', 'version': '3.1.0'}
    assert MONITORING_TOOL_NAMES <= tools


def test_monitoring_catalog_returns_the_observed_inventory(api_client, monitoring_mcp_case):
    """Fails if Operations cannot discover the monitored resources and sources it can follow up."""
    response = _call(api_client, monitoring_mcp_case.token, 'get_monitoring_catalog')

    payload = _content(response)
    assert response.status_code == 200
    assert monitoring_mcp_case.resource.pk in {item['id'] for item in payload['resources']}
    assert payload['sources'][0]['resource'] == monitoring_mcp_case.resource.pk


def test_monitoring_case_list_returns_the_case(api_client, monitoring_mcp_case):
    """Fails if Operations cannot list a case that requires operational follow-up."""
    response = _call(api_client, monitoring_mcp_case.token, 'list_monitoring_cases')

    payload = _content(response)
    assert response.status_code == 200
    assert payload['results'][0]['id'] == monitoring_mcp_case.case.pk


def test_monitoring_case_detail_returns_evidence(api_client, monitoring_mcp_case):
    """Fails if Operations hides the received evidence needed to assess a monitoring case."""
    response = _call(
        api_client, monitoring_mcp_case.token, 'get_monitoring_case', {'pk': monitoring_mcp_case.case.pk},
    )

    payload = _content(response)
    assert response.status_code == 200
    assert (payload['id'], payload['evidence']) == (
        monitoring_mcp_case.case.pk, {'rule': 'backup_age', 'result': 'stale'},
    )


def test_monitoring_report_list_returns_the_report(api_client, monitoring_mcp_case):
    """Fails if Operations cannot list received reports without creating a new ingestion capability."""
    response = _call(api_client, monitoring_mcp_case.token, 'list_monitoring_reports')

    payload = _content(response)
    assert response.status_code == 200
    assert payload['results'][0]['id'] == monitoring_mcp_case.report.pk


def test_monitoring_report_detail_returns_received_text(api_client, monitoring_mcp_case):
    """Fails if Operations cannot read a received report's text for follow-up."""
    response = _call(
        api_client, monitoring_mcp_case.token, 'get_monitoring_report', {'pk': monitoring_mcp_case.report.pk},
    )

    payload = _content(response)
    assert response.status_code == 200
    assert (payload['id'], payload['text']) == (
        monitoring_mcp_case.report.pk, 'El respaldo requiere seguimiento.',
    )


def test_monitoring_state_confirmation_records_service_actor(api_client, monitoring_mcp_case):
    """Fails if confirming a state preview does not version the case and attribute its activity."""
    arguments = {
        'pk': monitoring_mcp_case.case.pk,
        'state': 'reviewing',
        'version': monitoring_mcp_case.case.version,
        'note': 'Se inicia la revisión.',
    }
    preview = _content(_call(
        api_client, monitoring_mcp_case.token, 'update_monitoring_case_state', arguments,
    ))

    monitoring_mcp_case.case.refresh_from_db()
    monitoring_mcp_case.credential.refresh_from_db()
    assert (monitoring_mcp_case.case.state, monitoring_mcp_case.case.version) == ('pending', 2)
    assert not CaseActivity.objects.filter(case=monitoring_mcp_case.case).exists()
    confirmed = _content(_call(
        api_client, monitoring_mcp_case.token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    ))
    activity = CaseActivity.objects.get(case=monitoring_mcp_case.case, kind='state')

    monitoring_mcp_case.case.refresh_from_db()
    assert preview['impact']['resources']['monitoring_case_id'] == monitoring_mcp_case.case.pk
    assert monitoring_mcp_case.case.state == 'reviewing'
    assert monitoring_mcp_case.case.version == 3
    assert (confirmed['confirmed'], activity.actor_id, activity.text) == (
        True, monitoring_mcp_case.credential.actor_id, 'Se inicia la revisión.',
    )


def test_monitoring_state_conflict_leaves_case_unchanged(api_client, monitoring_mcp_case):
    """Fails if confirming a stale state version overwrites a newer monitoring case."""
    preview = _content(_call(
        api_client, monitoring_mcp_case.token, 'update_monitoring_case_state', {
            'pk': monitoring_mcp_case.case.pk,
            'state': 'reviewing',
            'version': monitoring_mcp_case.case.version,
        },
    ))
    Case.objects.filter(pk=monitoring_mcp_case.case.pk).update(version=3)

    rejected = _structured(_call(
        api_client, monitoring_mcp_case.token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    ))

    monitoring_mcp_case.case.refresh_from_db()
    assert rejected['error']['code'] == 'CONFLICT'
    assert (monitoring_mcp_case.case.state, monitoring_mcp_case.case.version) == ('pending', 3)
    assert not CaseActivity.objects.filter(case=monitoring_mcp_case.case).exists()


def test_monitoring_note_uses_the_credential_actor(api_client, monitoring_mcp_case):
    """Fails if a monitoring note loses the technical actor that created it."""
    response = _call(
        api_client, monitoring_mcp_case.token, 'create_monitoring_case_note', {
            'pk': monitoring_mcp_case.case.pk,
            'text': 'La evidencia fue revisada.',
        },
    )

    monitoring_mcp_case.credential.refresh_from_db()
    activity = CaseActivity.objects.get(case=monitoring_mcp_case.case, kind='note')
    assert response.status_code == 200
    assert (activity.actor_id, activity.actor_name, activity.text) == (
        monitoring_mcp_case.credential.actor_id,
        monitoring_mcp_case.credential.actor.username,
        'La evidencia fue revisada.',
    )


def test_monitoring_resource_link_changes_only_its_project(api_client, monitoring_mcp_case):
    """Fails if confirming a resource link mutates monitoring evidence or fields beyond its project relation."""
    before = (
        monitoring_mcp_case.resource.key,
        monitoring_mcp_case.resource.name,
        monitoring_mcp_case.resource.kind,
        monitoring_mcp_case.resource.server_id,
        monitoring_mcp_case.resource.enabled,
    )
    preview = _content(_call(
        api_client, monitoring_mcp_case.token, 'link_monitoring_resource_project', {
            'pk': monitoring_mcp_case.resource.pk,
            'project': monitoring_mcp_case.project.pk,
        },
    ))

    monitoring_mcp_case.resource.refresh_from_db()
    _content(_call(
        api_client, monitoring_mcp_case.token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    ))

    monitoring_mcp_case.resource.refresh_from_db()
    assert preview['impact']['resources']['monitoring_resource_id'] == monitoring_mcp_case.resource.pk
    assert monitoring_mcp_case.resource.project_id == monitoring_mcp_case.project.pk
    assert (
        monitoring_mcp_case.resource.key,
        monitoring_mcp_case.resource.name,
        monitoring_mcp_case.resource.kind,
        monitoring_mcp_case.resource.server_id,
        monitoring_mcp_case.resource.enabled,
    ) == before


def test_monitoring_adapter_rejects_a_non_staff_actor(django_user_model, monitoring_mcp_case):
    """Fails if the MCP bridge bypasses the Panel's staff requirement for internal case notes."""
    actor = django_user_model.objects.create_user(username='monitoring-non-staff', is_staff=False)
    credential = _credential(
        monitoring_mcp_case.connector,
        'operations-non-staff',
        allowed_tools=['create_monitoring_case_note'],
    )
    context = McpExecutionContext(
        connector=monitoring_mcp_case.connector,
        credential=credential,
        request_id='monitoring-non-staff-request',
        actor=actor,
        request=APIRequestFactory().post('/api/mcp/operations/', HTTP_HOST='testserver'),
    )

    with use_mcp_context(context):
        _, response = handle_message(
            _rpc('tools/call', {
                'name': 'create_monitoring_case_note',
                'arguments': {'pk': monitoring_mcp_case.case.pk, 'text': 'Intento no autorizado.'},
            }),
            TOOLS_BY_SLUG['operations'], connector=CONNECTORS['operations'], context=context,
        )

    result = response['result']['structuredContent']
    assert result['error']['code'] == 'FORBIDDEN'
    assert not CaseActivity.objects.filter(case=monitoring_mcp_case.case).exists()
