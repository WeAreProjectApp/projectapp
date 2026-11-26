"""Cycle-payment history for accounting hostings.

`total_paid` used to be a hand-maintained number that broke whenever a
client switched modality. Cycles are now the source of truth: every paid
period is one HostingCycle row (modality + amount snapshotted) and the
hosting's `total_paid` / `cycles_count` become denormalized sums, kept in
sync here so the dashboard's Sum('total_paid') and table sorting keep
working unchanged.

Registering a cycle payment optionally advances `valid_to` by the paid
period (payment = renewal), which also re-arms the expiry notice cadence
via hosting_expiry_service's target snapshot.
"""
from content.services.entity_history import historical_write
import logging

from django.db.models import Sum

from content.models import AccountingChangeLog, HostingCycle, HostingRecord
from content.services.accounting_service import (
    _notify,
    compute_changes,
    log_accounting_change,
    object_repr,
    snapshot_values,
)
from content.utils import add_months, today_bogota

logger = logging.getLogger(__name__)

EntityType = AccountingChangeLog.EntityType
Action = AccountingChangeLog.Action


def recalculate_hosting_totals(hosting):
    totals = hosting.cycles.aggregate(
        total=Sum('amount'), count=Sum('cycles_represented'),
    )
    HostingRecord.objects.filter(pk=hosting.pk).update(
        total_paid=totals['total'] or 0,
        cycles_count=totals['count'] or 0,
    )


@historical_write
def register_cycle_payment(hosting, *, data, user=None, validity_target=None, notify=True):
    """Append a paid cycle, recalc totals and (optionally) extend valid_to.

    ``data`` (already validated by the serializer): amount, modality?,
    paid_at?, period_from?, period_to?, notes?, advance_validity (default
    True). Defaults derive from the hosting's current contract values.
    """
    modality = data.get('modality') or hosting.payment_modality
    amount = data.get('amount') or hosting.payment_per_cycle
    paid_at = data.get('paid_at') or today_bogota()
    period_from = data.get('period_from') or hosting.valid_to or paid_at
    months = HostingRecord.MODALITY_MONTHS.get(modality, 1)
    period_to = data.get('period_to') or add_months(period_from, months)
    advance_validity = data.get('advance_validity', True)

    old_values = snapshot_values(hosting, EntityType.HOSTING)

    cycle = HostingCycle.objects.create(
        hosting_record=hosting,
        modality=modality,
        amount=amount,
        paid_at=paid_at,
        period_from=period_from,
        period_to=period_to,
        notes=data.get('notes', ''),
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    if advance_validity:
        HostingRecord.objects.filter(pk=hosting.pk).update(valid_to=validity_target or period_to)
    recalculate_hosting_totals(hosting)
    hosting.refresh_from_db()

    _audit(hosting, old_values, user, notify=notify)
    logger.info(
        'Registered hosting cycle %s for %s (%s, %s)',
        cycle.pk, hosting.client_name, modality, amount,
    )
    return cycle


@historical_write
def delete_cycle(hosting, cycle, *, user=None, notify=True):
    """Remove a cycle and recalc. Does NOT roll back valid_to."""
    old_values = snapshot_values(hosting, EntityType.HOSTING)
    cycle.delete()
    recalculate_hosting_totals(hosting)
    hosting.refresh_from_db()
    _audit(hosting, old_values, user, notify=notify)


def _audit(hosting, old_values, user, *, notify):
    changes = compute_changes(
        EntityType.HOSTING, old_values,
        snapshot_values(hosting, EntityType.HOSTING),
    )
    if not changes:
        return
    change_log = log_accounting_change(
        entity_type=EntityType.HOSTING,
        object_id=hosting.pk,
        object_repr=object_repr(EntityType.HOSTING, hosting),
        action=Action.UPDATED,
        changes=changes,
        actor=user,
    )
    if notify:
        _notify(change_log)
