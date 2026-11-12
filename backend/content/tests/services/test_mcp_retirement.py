"""Durable evidence and fail-closed retirement gates for MCP compatibility."""
import copy
from datetime import datetime, timedelta, timezone as datetime_timezone
from functools import lru_cache
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from content.mcp.connectors import tools_for_credential
from content.mcp.coverage import build_matrix
from content.mcp.migration import observation_heartbeat, record_usage, retirement_status
from content.models import McpConnector, McpCredential, McpObservation, McpRequestLog, McpUsageDaily

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 19, tzinfo=datetime_timezone.utc)
EVIDENCE = ['docs/audits/PA-221/README.md']
PERMISSION_EVIDENCE = ['docs/audits/PA-221/README.md']
CONFIRMATION_EVIDENCE = ['docs/audits/PA-221/README.md']


@lru_cache
def _current_coverage_summary():
    matrix = build_matrix()
    return {
        'schema': 1,
        'report_sha256': 'a' * 64,
        'report_path': '/tmp/pa-221-functional-coverage.json',
        'revision': matrix['revision'],
        'matrix_fingerprint': matrix['matrix_fingerprint'],
        'contracts': matrix['contracts'],
        'operations': len(matrix['rows']),
        'surfaces': len(matrix['surfaces']),
    }


def _coverage_summary():
    return copy.deepcopy(_current_coverage_summary())


def _verified_report():
    report = build_matrix()
    for row in report['rows']:
        assert row['candidate_view_ids'], f"{row['id']} has no assigned surface"
        row.update({
            'result': 'mapped_verified',
            'tested_role': 'QA MCP functional actor',
            'view_ids': row['candidate_view_ids'],
            'evidence': EVIDENCE,
            'permission_evidence': PERMISSION_EVIDENCE,
        })
        if row['requires_confirmation']:
            row['confirmation_evidence'] = CONFIRMATION_EVIDENCE
    for surface in report['surfaces']:
        if surface['result'] == 'exempt':
            continue
        checks = [row['id'] for row in report['rows'] if surface['id'] in row['view_ids']]
        assert checks, f"{surface['id']} has no mapped tool"
        surface.update({'result': 'mapped_verified', 'evidence': EVIDENCE, 'checks': checks})
        for feature in surface['feature_checks']:
            assert feature['candidate_tools'], f"{feature['id']} has no assigned tool"
            feature.update({
                'result': 'mapped_verified',
                'evidence': EVIDENCE,
                'checks': [feature['candidate_tools'][0]],
            })
    return report


def _write_report(tmp_path, report):
    path = tmp_path / 'coverage.json'
    path.write_text(json.dumps(report, sort_keys=True))
    return path


def _retirement_clock():
    return patch('content.mcp.migration.timezone.now', return_value=NOW), patch(
        'content.management.commands.mcp_retirement.timezone.now', return_value=NOW,
    )


def _credential(connector, label='Legacy consumer', *, catalog='legacy', migrated_at=None):
    return McpCredential.objects.create(
        connector=connector,
        label=label,
        catalog=catalog,
        migrated_at=migrated_at,
        token_hash=McpCredential.hash_token(label),
    )


def _ready_connector(now):
    connector, _ = McpConnector.objects.update_or_create(
        slug='blog',
        defaults={
            'name': 'Blog compatibility', 'is_active': True,
            'migration_started_at': now - timedelta(days=31), 'consumers_verified_at': now,
            'retired_at': None, 'aliases_retired_at': None,
            'retirement_evidence': {'legacy': [_coverage_summary()]},
        },
    )
    connector.credentials.all().delete()
    credential = _credential(connector, migrated_at=now)
    McpObservation.objects.update_or_create(
        key='migration',
        defaults={'continuous_since': now - timedelta(days=15), 'heartbeat_at': now},
    )
    return connector, credential


def test_retirement_allows_migrated_consumers_after_the_quiet_observation_window():
    """Fails if a fully migrated compatibility connector cannot retire after its quiet window."""
    now = NOW
    connector, _ = _ready_connector(now)

    with patch('content.mcp.migration.timezone.now', return_value=now):
        eligible = retirement_status(connector)

    assert eligible['eligible'] is True


def test_retirement_blocks_a_recent_legacy_call():
    """Fails if a legacy call within 14 days does not block retirement."""
    connector, credential = _ready_connector(NOW)
    McpUsageDaily.objects.create(
        connector=connector, credential=credential, day=NOW.date(), tool_name='list_blog_posts',
        legacy=True, count=1, last_used_at=NOW - timedelta(days=13),
    )

    with patch('content.mcp.migration.timezone.now', return_value=NOW):
        status = retirement_status(connector)

    assert status['blockers'] == ['legacy_calls_recent']


def test_retirement_blocks_an_incomplete_observation_window():
    """Fails if fewer than 14 continuous observed days still permit retirement."""
    connector, _ = _ready_connector(NOW)
    McpObservation.objects.update(continuous_since=NOW - timedelta(days=13))

    with patch('content.mcp.migration.timezone.now', return_value=NOW):
        status = retirement_status(connector)

    assert status['blockers'] == ['observation_incomplete']


def test_retirement_blocks_an_unmigrated_legacy_consumer():
    """Fails if an identified consumer can be retired while its legacy credential remains unmigrated."""
    now = NOW
    connector, _ = _ready_connector(now)
    _credential(connector, 'Pending consumer')

    with patch('content.mcp.migration.timezone.now', return_value=now):
        status = retirement_status(connector)

    assert status['eligible'] is False
    assert status['blockers'] == ['consumers_pending']


def test_pre_split_retirement_ignores_legacy_alias_state_and_legacy_usage():
    """Fails if retiring segmented Commercial access is blocked by unrelated legacy aliases or calls."""
    connector, _ = McpConnector.objects.update_or_create(
        slug='commercial',
        defaults={
            'name': 'Commercial', 'is_active': True, 'retired_at': None,
            'aliases_retired_at': NOW, 'pre_split_started_at': NOW - timedelta(days=31),
            'pre_split_consumers_verified_at': NOW, 'pre_split_retired_at': None,
            'retirement_evidence': {'pre_split': [_coverage_summary()]},
        },
    )
    connector.credentials.all().delete()
    pre_split = _credential(
        connector, 'Pre-split consumer', catalog='pre_split', migrated_at=NOW,
    )
    legacy = _credential(connector, 'Legacy consumer', catalog='legacy')
    McpObservation.objects.update_or_create(
        key='migration',
        defaults={'continuous_since': NOW - timedelta(days=15), 'heartbeat_at': NOW},
    )
    McpUsageDaily.objects.create(
        connector=connector, credential=legacy, day=NOW.date(), tool_name='list_clients',
        legacy=True, count=1, last_used_at=NOW - timedelta(days=1),
    )

    with patch('content.mcp.migration.timezone.now', return_value=NOW):
        status = retirement_status(connector, catalog='pre_split')

    assert status['eligible'] is True
    assert status['blockers'] == []
    assert pre_split.catalog == 'pre_split'


def test_observation_heartbeat_restarts_quiet_window_after_a_gap():
    """Fails if a monitoring outage still counts toward the required 14 quiet retirement days."""
    McpObservation.objects.update_or_create(
        key='migration',
        defaults={
            'continuous_since': NOW - timedelta(days=15),
            'heartbeat_at': NOW - timedelta(minutes=11),
        },
    )

    with patch('content.mcp.migration.timezone.now', return_value=NOW):
        observation_heartbeat()

    observation = McpObservation.objects.get(key='migration')
    assert (observation.continuous_since, observation.heartbeat_at) == (NOW, NOW)


def test_usage_evidence_survives_pruning_the_panel_request_log():
    """Fails if retirement evidence is lost when the panel discards old request-log rows."""
    connector, credential = _ready_connector(NOW)

    record_usage(
        connector, credential,
        {'params': {'name': 'list_blog_posts'}}, legacy=True,
    )
    McpRequestLog.record(
        connector, 'tool_call', credential=credential, tool_name='list_blog_posts',
    )
    McpRequestLog.objects.filter(connector=connector).delete()

    usage = McpUsageDaily.objects.get(connector=connector, credential=credential)
    assert (usage.tool_name, usage.legacy, usage.count) == ('list_blog_posts', True, 1)
    assert McpRequestLog.objects.filter(connector=connector).count() == 0


def test_retirement_command_rejects_a_static_matrix_without_persisting_it(tmp_path):
    """Fails if an unverified generated matrix can retire a compatibility connector or replace its proof."""
    connector, _ = _ready_connector(NOW)
    prior_evidence = {'legacy': [{'preserved': 'prior-proof'}]}
    connector.retirement_evidence = prior_evidence
    connector.save(update_fields=['retirement_evidence'])
    report_path = _write_report(tmp_path, build_matrix())
    migration_clock, command_clock = _retirement_clock()

    with migration_clock, command_clock, pytest.raises(CommandError):
        call_command(
            'mcp_retirement', '--slug', 'blog', '--retire', '--apply',
            '--coverage-report', str(report_path),
        )

    connector.refresh_from_db()
    assert connector.retired_at is None
    assert connector.retirement_evidence == prior_evidence


@pytest.fixture
def retired_legacy_connector(tmp_path):
    """A connector retired through the command with schema-complete synthetic proof."""
    connector, credential = _ready_connector(NOW)
    prior_evidence = _coverage_summary()
    connector.retirement_evidence = {
        'legacy': [prior_evidence],
        'pre_split': [{'preserved': 'pre-split-proof'}],
    }
    connector.save(update_fields=['retirement_evidence'])
    report_path = _write_report(tmp_path, _verified_report())
    migration_clock, command_clock = _retirement_clock()

    with migration_clock, command_clock:
        call_command(
            'mcp_retirement', '--slug', 'blog', '--retire', '--apply',
            '--coverage-report', str(report_path),
        )

    connector.refresh_from_db()
    credential.connector = connector
    return SimpleNamespace(
        connector=connector,
        credential=credential,
        persisted=connector.retirement_evidence['legacy'][-1],
        report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
    )


def test_retirement_command_persists_the_verified_report_digest(retired_legacy_connector):
    """Fails if a successful retirement stores a digest unrelated to the approved report file."""
    persisted = retired_legacy_connector.persisted

    assert persisted['report_sha256'] == retired_legacy_connector.report_sha256
    assert persisted['revision'] == _current_coverage_summary()['revision']


def test_retirement_command_preserves_other_catalog_evidence(retired_legacy_connector):
    """Fails if retiring a legacy catalog overwrites the evidence retained for another catalog."""
    assert retired_legacy_connector.connector.retirement_evidence['pre_split'] == [
        {'preserved': 'pre-split-proof'},
    ]


def test_retirement_command_deactivates_a_retired_legacy_connector(retired_legacy_connector):
    """Fails if a retired compatibility connector remains active in the operating catalog."""
    assert retired_legacy_connector.connector.is_active is False


def test_retirement_command_records_when_the_legacy_connector_retired(retired_legacy_connector):
    """Fails if retirement deactivates a connector without recording its retirement instant."""
    assert retired_legacy_connector.connector.retired_at == NOW


def test_retired_connector_exposes_no_tools_to_its_credential(retired_legacy_connector):
    """Fails if a credential can still discover legacy tools after its connector retires."""
    assert tools_for_credential('blog', retired_legacy_connector.credential) == []


def test_retirement_command_keeps_evidence_when_a_gate_blocks_the_retirement(tmp_path):
    """Fails if a blocked retirement persists candidate coverage evidence or a retired timestamp."""
    connector, _ = _ready_connector(NOW)
    connector.consumers_verified_at = None
    connector.save(update_fields=['consumers_verified_at'])
    prior_evidence = copy.deepcopy(connector.retirement_evidence)
    report_path = _write_report(tmp_path, _verified_report())
    migration_clock, command_clock = _retirement_clock()

    with migration_clock, command_clock, pytest.raises(CommandError, match='consumer_inventory_unverified'):
        call_command(
            'mcp_retirement', '--slug', 'blog', '--retire', '--apply',
            '--coverage-report', str(report_path),
        )

    connector.refresh_from_db()
    assert connector.retired_at is None
    assert connector.retirement_evidence == prior_evidence


def test_retirement_command_dry_run_does_not_persist_candidate_evidence(tmp_path):
    """Fails if a retirement preview writes evidence or a retirement timestamp before --apply."""
    connector, _ = _ready_connector(NOW)
    prior_evidence = copy.deepcopy(connector.retirement_evidence)
    report_path = _write_report(tmp_path, _verified_report())
    migration_clock, command_clock = _retirement_clock()

    with migration_clock, command_clock:
        call_command(
            'mcp_retirement', '--slug', 'blog', '--retire', '--coverage-report', str(report_path),
        )

    connector.refresh_from_db()
    assert connector.retired_at is None
    assert connector.retirement_evidence == prior_evidence


@pytest.mark.parametrize(
    ('field', 'value'),
    [('revision', '0' * 40), ('contracts', [])],
)
def test_retirement_status_blocks_stale_or_corrupt_coverage_evidence(field, value):
    """Fails if stale or malformed stored coverage evidence is accepted after the original report is gone."""
    connector, _ = _ready_connector(NOW)
    stale_evidence = _coverage_summary()
    stale_evidence[field] = value
    connector.retirement_evidence = {'legacy': [stale_evidence]}
    connector.save(update_fields=['retirement_evidence'])

    with patch('content.mcp.migration.timezone.now', return_value=NOW):
        status = retirement_status(connector)

    assert (status['coverage_verified'], status['blockers']) == (
        False, ['replacement_coverage_unverified'],
    )
