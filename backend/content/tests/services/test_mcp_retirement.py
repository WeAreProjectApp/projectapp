"""Durable evidence and fail-closed retirement gates for MCP compatibility."""
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

import pytest
from content.mcp.migration import observation_heartbeat, record_usage, retirement_status
from content.models import McpConnector, McpCredential, McpObservation, McpRequestLog, McpUsageDaily

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 19, tzinfo=datetime_timezone.utc)


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
