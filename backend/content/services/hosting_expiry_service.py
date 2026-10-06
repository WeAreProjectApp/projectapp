"""Hosting expiry notices for the accounting module.

Business rule: active hostings with a `valid_to` (vigencia) alert the
internal recipients 15 days before expiry, again when crossing 7 days,
and then every 5 days (continuing past expiry) until the cuenta de cobro
is sent to the client (`billing_requested_at`, set by
hosting_billing_service) or the hosting is deactivated.

Cadence state lives on each HostingRecord. `expiry_notice_target`
snapshots the valid_to the cadence is armed against: any change of
valid_to (renewal or correction) re-arms the cadence automatically on
the next daily run.

The rule above is unchanged; what changed is the envelope. These notices
used to be one email per hosting and are now a section of the daily
payment calendar (`accounting_payment_calendar_service`), which owns the
sending. This module contributes the due records and stamps their state,
so the cadence keeps living next to the hosting domain it belongs to.
"""
import logging

from django.db.models import F, Q

from content.services.accounting_notice_cadence import is_notice_due

logger = logging.getLogger(__name__)

FIRST_NOTICE_DAYS = 15
SECOND_NOTICE_DAYS = 7
REPEAT_EVERY_DAYS = 5


def collect_hosting_notices(today):
    """Hostings due for an expiry notice today, as calendar items.

    Re-arms renewed or corrected records first, so a renewal that moved
    `valid_to` starts a clean cadence instead of inheriting the old one.
    """
    from content.models import HostingRecord

    HostingRecord.objects.filter(
        Q(retention_context__isnull=True) & Q(expiry_notice_target__isnull=False) & ~Q(expiry_notice_target=F('valid_to')),
    ).update(
        expiry_notice_target=F('valid_to'),
        expiry_notice_last_sent_at=None,
        expiry_notice_count=0,
        billing_requested_at=None,
    )

    candidates = HostingRecord.objects.filter(
        retention_context__isnull=True,
        is_active=True,
        valid_to__isnull=False,
        billing_requested_at__isnull=True,
    ).exclude(
        project__current_state__operational_effect__in=(
            'suspended', 'completed', 'decommissioned',
        ),
    ).exclude(
        project__current_state__isnull=True,
        project__state_review_required=True,
    )
    items = []
    for record in candidates:
        try:
            if not _is_due(record, today):
                continue
            items.append(_item(record, today))
        except Exception:
            logger.exception(
                'Skipping hosting %s while building the payment calendar', record.pk,
            )
    return items


def mark_hosting_notices_sent(items, today):
    """Advance the cadence state of the hostings included in a sent digest."""
    from content.models import HostingRecord

    for item in items:
        # System state, not a user change: update directly (no audit trail).
        HostingRecord.objects.filter(pk=item['id']).update(
            expiry_notice_target=item['due_date'],
            expiry_notice_last_sent_at=today,
            expiry_notice_count=F('expiry_notice_count') + 1,
        )


def _is_due(record, today):
    """Single notice at 15 days, another crossing 7, then every 5 days.

    Delegates to the shared cadence rule, which the accounting calendar uses
    for expected incomes and recurring payments too. The milestones and the
    repeat interval below are what make it behave exactly as it always has.
    """
    return is_notice_due(
        target_date=record.valid_to,
        last_sent_at=record.expiry_notice_last_sent_at,
        today=today,
        milestones=(FIRST_NOTICE_DAYS, SECOND_NOTICE_DAYS),
        repeat_every_days=REPEAT_EVERY_DAYS,
    )


def _item(record, today):
    days_left = (record.valid_to - today).days
    return {
        'kind': 'hosting',
        'id': record.pk,
        # Client and project rejoined: the notice has to be recognisable at
        # a glance, and the client half alone drops the brand it renews.
        'title': record.display_label or record.domain_url,
        'subtitle': record.domain_url,
        'client_name': record.client_name,
        'due_date': record.valid_to,
        'days_left': days_left,
        'amount': record.payment_per_cycle,
        'total': None,
        'notice_number': record.expiry_notice_count + 1,
        'detail': record.payment_modality_label,
    }
