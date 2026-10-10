"""Data-integrity tools of the projects MCP connector: metadata, confirmation, replay and undo."""
import json

import pytest
from accounts.models import ProjectPhase

from content.mcp.contract_report import CONTRACTS_PATH
from content.mcp.registry import connector_version
from content.models import DataIntegrityOperation, McpActionIntent, McpConnector
from content.tests.data_integrity_helpers import (
    make_phase,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
)
from content.views.mcp_blog import TOOLS_BY_SLUG

pytestmark = pytest.mark.django_db
TOOL_NAMES = ('describe_integrity_rules', 'list_integrity_findings', 'preview_integrity_fixes',
              'apply_integrity_fixes', 'list_integrity_operations', 'preview_integrity_operation_undo',
              'undo_integrity_operation')


@pytest.fixture
def token():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


@pytest.fixture
def gap(make_client_profile):
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    make_phase(project, make_proposal(profile, 'Uno'), 1)
    make_phase(project, make_proposal(profile, 'Dos'), 4)
    [finding] = only(scan(), 'PJ7')
    return {'project': project, 'finding': finding,
            'batch': {'scope': {'kind': 'project', 'id': project.pk}, 'fixes': [selection(finding)]}}


def _call(api_client, token, name, arguments):
    response = api_client.post(f'/api/mcp/projects/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments},
    }, format='json')
    return json.loads(response.data['result']['content'][0]['text'])


def _orders():
    return sorted(ProjectPhase.objects.values_list('order', flat=True))


def _pending_apply(api_client, token, gap, request_id='mcp-1'):
    preview = _call(api_client, token, 'preview_integrity_fixes', gap['batch'])
    return _call(api_client, token, 'apply_integrity_fixes', {
        **gap['batch'], 'reason': 'Prueba MCP', 'request_id': request_id,
        'expected_impact_hash': preview['impact_hash'],
    })


def test_projects_connector_exposes_the_tools_with_the_right_risk():
    """Fails if a write tool is exposed without confirmation or a read tool is marked as a write."""
    tools = {tool['name']: tool for tool in TOOLS_BY_SLUG['projects']}

    assert set(TOOL_NAMES) <= set(tools)
    for name in ('apply_integrity_fixes', 'undo_integrity_operation'):
        assert (tools[name]['risk'], tools[name]['requires_confirmation']) == ('sensitive', True)
    for name in set(TOOL_NAMES) - {'apply_integrity_fixes', 'undo_integrity_operation'}:
        assert tools[name]['risk'] == 'read'
    assert connector_version('projects') == json.loads(CONTRACTS_PATH.read_text())['projects']['version']


def test_findings_are_listed_through_the_connector(api_client, token, gap):
    """Fails if the connector cannot scan a scope or loses the fingerprint the fixes need."""
    result = _call(api_client, token, 'list_integrity_findings', {
        'scope_kind': 'project', 'scope_id': gap['project'].pk, 'rule_ids': 'PJ7',
    })

    assert [row['fingerprint'] for row in result['results']] == [gap['finding'].fingerprint]


def test_apply_waits_for_confirmation_and_writes_nothing_before(api_client, token, gap):
    """Fails if MCP applies a fix without the confirmation step."""
    pending = _pending_apply(api_client, token, gap)

    assert pending['confirmation_required'] is True
    assert pending['impact']['steps'][0]['rule_id'] == 'PJ7'
    assert _orders() == [1, 4]
    assert not DataIntegrityOperation.objects.exists()


def test_confirmation_applies_once_and_replays_after(api_client, token, gap):
    """Fails if a confirmed fix is not applied, or a repeated confirmation applies it twice."""
    pending = _pending_apply(api_client, token, gap)

    first = _call(api_client, token, 'confirm_action', {'confirmation_id': pending['confirmation_id']})
    _call(api_client, token, 'confirm_action', {'confirmation_id': pending['confirmation_id']})

    assert _orders() == [1, 2]
    operation = DataIntegrityOperation.objects.get()
    assert operation.source == 'mcp:projects'
    assert operation.actor.username.startswith('mcp_')
    assert 'error' not in first


def test_a_stale_hash_is_refused_before_asking_for_confirmation(api_client, token, gap):
    """Fails if MCP asks to confirm a batch whose preview is outdated."""
    result = _call(api_client, token, 'apply_integrity_fixes', {
        **gap['batch'], 'reason': 'x', 'request_id': 'stale', 'expected_impact_hash': '0' * 64,
    })

    assert result['error']['code'] == 'STALE_VERSION'


def test_blocked_fixes_are_refused_before_asking_for_confirmation(api_client, token, gap):
    """Fails if MCP offers to confirm a batch the preview already blocks."""
    batch = {**gap['batch'], 'fixes': [selection(gap['finding'], 'report_only')]}
    preview = _call(api_client, token, 'preview_integrity_fixes', batch)

    result = _call(api_client, token, 'apply_integrity_fixes', {
        **batch, 'reason': 'x', 'request_id': 'blocked', 'expected_impact_hash': preview['impact_hash'],
    })

    assert result['error']['code'] == 'CONFLICT'
    assert result['error']['details']['blockers'][0]['code'] == 'report_only'


def test_cancelled_confirmation_never_applies(api_client, token, gap):
    """Fails if a cancelled intent can still be confirmed."""
    pending = _pending_apply(api_client, token, gap)
    _call(api_client, token, 'cancel_action', {'confirmation_id': pending['confirmation_id']})

    result = _call(api_client, token, 'confirm_action', {'confirmation_id': pending['confirmation_id']})

    assert 'error' in result
    assert _orders() == [1, 4]
    assert McpActionIntent.objects.get(pk=pending['confirmation_id']).status != 'executed'


def test_undo_goes_through_its_own_preview_and_confirmation(api_client, token, gap):
    """Fails if MCP cannot undo a fix, or undoes it without confirmation."""
    pending = _pending_apply(api_client, token, gap)
    _call(api_client, token, 'confirm_action', {'confirmation_id': pending['confirmation_id']})
    operation = DataIntegrityOperation.objects.get()
    preview = _call(api_client, token, 'preview_integrity_operation_undo', {'operation_id': operation.pk})

    undo = _call(api_client, token, 'undo_integrity_operation', {
        'operation_id': operation.pk, 'reason': 'Volver', 'request_id': 'mcp-undo',
        'expected_impact_hash': preview['impact_hash'],
    })
    assert undo['confirmation_required'] is True
    assert _orders() == [1, 2]

    _call(api_client, token, 'confirm_action', {'confirmation_id': undo['confirmation_id']})

    assert _orders() == [1, 4]
    log = _call(api_client, token, 'list_integrity_operations', {})
    assert [row['kind'] for row in log['results']] == ['undo', 'apply']


def test_the_catalog_is_described_through_the_connector(api_client, token):
    """Fails if the skill cannot read which rules exist and how they are fixed."""
    result = _call(api_client, token, 'describe_integrity_rules', {})

    rule = next(row for row in result['rules'] if row['id'] == 'PJ7')
    assert rule['fixable_kinds'] == ['reorder']
