"""Fail-closed usage evidence and retirement checks for MCP compatibility."""
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from content.mcp.module_catalog import CANONICAL_FOR
from content.models import McpActionIntent, McpConnector, McpObservation, McpUsageDaily

COMPATIBILITY_DAYS = 30
QUIET_DAYS = 14
RETENTION_DAYS = 90
MAX_HEARTBEAT_GAP = timedelta(minutes=10)


def invalidate_observation():
    """A failed evidence write invalidates the window even between heartbeats."""
    now = timezone.now()
    McpObservation.objects.filter(key='migration').update(continuous_since=now)


@transaction.atomic
def observation_heartbeat():
    now = timezone.now()
    window, _ = McpObservation.objects.select_for_update().get_or_create(
        key='migration', defaults={'continuous_since': now, 'heartbeat_at': now},
    )
    if now - window.heartbeat_at > MAX_HEARTBEAT_GAP:
        window.continuous_since = now
    window.heartbeat_at = now
    window.save(update_fields=['continuous_since', 'heartbeat_at'])
    McpUsageDaily.objects.filter(day__lt=now.date() - timedelta(days=RETENTION_DAYS)).delete()


@transaction.atomic
def record_usage(connector, credential, message, *, legacy):
    """Called before dispatch; a failed evidence write prevents domain execution."""
    from content.mcp.protocol import ToolError
    locked = McpConnector.objects.select_for_update().get(pk=connector.pk)
    if locked.retired_at or (legacy and locked.aliases_retired_at):
        raise ToolError('Este acceso MCP está retirado.', code='CONNECTOR_RETIRED')
    params = message.get('params') if isinstance(message, dict) else None
    name = params.get('name', '') if isinstance(params, dict) else ''
    # Never persist arbitrary argument strings or client-supplied unknown names.
    from content.mcp.connectors import LEGACY_TOOLS_BY_SLUG, TOOLS_BY_SLUG
    known = {tool['name'] for tool in TOOLS_BY_SLUG[connector.slug] + LEGACY_TOOLS_BY_SLUG[connector.slug]}
    name = name if isinstance(name, str) and name in known else ''
    now = timezone.now()
    row, _ = McpUsageDaily.objects.get_or_create(
        connector=connector, credential=credential, day=now.date(),
        tool_name=name, legacy=legacy,
        defaults={'last_used_at': now},
    )
    McpUsageDaily.objects.filter(pk=row.pk).update(count=F('count') + 1, last_used_at=now)


def retirement_status(connector, *, credential=None):
    """The same evidence gates retiring a slug or an old credential catalog."""
    now = timezone.now()
    blockers = []
    started = connector.migration_started_at
    if started is None or now - started < timedelta(days=COMPATIBILITY_DAYS):
        blockers.append('compatibility_window')
    if connector.consumers_verified_at is None:
        blockers.append('consumer_inventory_unverified')
    from content.mcp.connectors import CONNECTORS
    credentials = connector.credentials.all()
    if not CONNECTORS[connector.slug].compatibility:
        credentials = credentials.filter(catalog='legacy')
    if credential is not None:
        credentials = credentials.filter(pk=credential.pk)
    if credentials.filter(migrated_at__isnull=True, revoked_at__isnull=True).exists():
        blockers.append('consumers_pending')
    observation = McpObservation.objects.filter(key='migration').first()
    if (observation is None or now - observation.heartbeat_at > MAX_HEARTBEAT_GAP
            or now - observation.continuous_since < timedelta(days=QUIET_DAYS)):
        blockers.append('observation_incomplete')
    usage = McpUsageDaily.objects.filter(connector=connector, legacy=True)
    if credential is not None:
        usage = usage.filter(credential=credential)
    last_used = usage.aggregate(last=Max('last_used_at'))['last']
    if last_used and now - last_used < timedelta(days=QUIET_DAYS):
        blockers.append('legacy_calls_recent')
    pending = McpActionIntent.objects.filter(
        connector=connector, status='pending', expires_at__gt=now,
    )
    if credential is not None:
        pending = pending.filter(credential=credential)
    if pending.exists():
        blockers.append('confirmations_pending')
    return {
        'eligible': not blockers, 'blockers': blockers,
        'replacement': CANONICAL_FOR[connector.slug],
        'earliest_retirement_at': (started + timedelta(days=COMPATIBILITY_DAYS)).isoformat() if started else None,
        'last_legacy_use_at': last_used.isoformat() if last_used else None,
        'continuous_observation_since': observation.continuous_since.isoformat() if observation else None,
    }
