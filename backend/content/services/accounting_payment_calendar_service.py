"""Daily payment calendar: one email with everything about to come due.

Three sections in one message — expected incomes, the next charge of the
recurring payments, and the hostings about to expire. Each is announced 15
days ahead, 7 days ahead and on the date itself; an expected income that
passes its date keeps being reminded every week or fortnight
(`AccountingSettings.overdue_reminder_frequency`) until it is collected,
written off or muted.

One email and not one per record on purpose: with several hostings and
recurring payments live, individual messages become noise and stop being
read, which is the failure this whole calendar exists to prevent. For the
same reason an empty day sends nothing at all — a daily "todo al día" mail
would train the reader to ignore the sender.

Cadence state lives on each record and is only advanced after a confirmed
send, so a delivery failure or a missing recipient list rebuilds the same
digest tomorrow instead of losing the notice.
"""
import logging

from django.conf import settings
from django.db.models import F, Q
from django.template.loader import render_to_string

from content.services import accounting_service, email_log_service
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.services.accounting_notice_cadence import is_notice_due
from content.services.hosting_expiry_service import (
    collect_hosting_notices,
    mark_hosting_notices_sent,
)
from content.services.notification_recipient_service import (
    active_recipient_emails,
)
from content.services.recurring_schedule import next_charge_date
from content.utils import today_bogota

logger = logging.getLogger(__name__)

TEMPLATE_KEY = 'accounting_payment_calendar'
FIRST_NOTICE_DAYS = 15
SECOND_NOTICE_DAYS = 7
MILESTONES = (FIRST_NOTICE_DAYS, SECOND_NOTICE_DAYS, 0)
OVERDUE_FREQUENCY_DAYS = {'weekly': 7, 'biweekly': 14}


def run_payment_calendar(today=None):
    """Send today's calendar. Returns how many records it announced.

    Never raises: a record that cannot be read is logged and skipped rather
    than taking the whole digest down with it.
    """
    from content.models import AccountingSettings

    today = today or today_bogota()
    config = AccountingSettings.load()
    if not config.notifications_enabled:
        return 0

    calendar_on = config.payment_calendar_enabled
    incomes = collect_income_notices(today, config) if calendar_on else []
    recurring = collect_recurring_notices(today) if calendar_on else []
    hostings = (
        collect_hosting_notices(today)
        if config.hosting_expiry_reminder_enabled else []
    )
    if not (incomes or recurring or hostings):
        return 0

    recipients = active_recipient_emails()
    if not recipients:
        # Do not advance any state: retry daily until recipients exist.
        logger.warning(
            'Payment calendar ready (%s ingresos, %s recurrentes, %s hostings) '
            'but no recipients configured.',
            len(incomes), len(recurring), len(hostings),
        )
        return 0

    if not _send_digest(today, incomes, recurring, hostings, recipients, config):
        return 0

    mark_income_notices_sent(incomes, today)
    mark_recurring_notices_sent(recurring, today)
    mark_hosting_notices_sent(hostings, today)
    return len(incomes) + len(recurring) + len(hostings)


# ── Expected incomes ─────────────────────────────────────────────────────────

def collect_income_notices(today, config):
    """Expected incomes due for a notice today, as calendar items."""
    from content.models import IncomeRecord

    _resume_expired_mutes(today)
    _rearm_moved_incomes()

    overdue_every = OVERDUE_FREQUENCY_DAYS.get(
        config.overdue_reminder_frequency, 14,
    )
    candidates = (
        IncomeRecord.objects
        .filter(
            retention_context__isnull=True,
            kind=IncomeRecord.Kind.EXPECTED,
            reminders_muted=False,
            period_date__lte=today + _days(FIRST_NOTICE_DAYS),
        )
        .exclude(
            project__current_state__operational_effect__in=(
                'suspended', 'completed', 'decommissioned',
            ),
        )
        .exclude(
            project__current_state__isnull=True,
            project__state_review_required=True,
        )
        .annotate(paid_amount=accounting_service.paid_amount_subquery())
        # Mirrors the 'paid' branch of the income list filter in
        # views/accounting.py, which mirrors payment_status_for: keep the three
        # in sync. A partial payment deliberately keeps notifying — the balance
        # is still owed — and the digest shows what is left, not the gross.
        .exclude(paid_amount__gte=F('total_amount'))
        .select_related('client__user', 'project__current_state')
    )

    items = []
    for record in candidates:
        try:
            if not is_notice_due(
                target_date=record.period_date,
                last_sent_at=record.reminder_last_sent_at,
                today=today,
                milestones=MILESTONES,
                repeat_every_days=overdue_every,
            ):
                continue
            items.append(_income_item(record, today))
        except Exception:
            logger.exception(
                'Skipping income %s while building the payment calendar', record.pk,
            )
    return items


def _resume_expired_mutes(today):
    """Un-mute the incomes whose "silenciar hasta" date has arrived.

    Doing it here rather than lazily keeps the stored data honest, so the panel
    badge and the calendar can never disagree about whether a record is muted.
    """
    from content.models import IncomeRecord

    IncomeRecord.objects.filter(
        retention_context__isnull=True,
        reminders_muted=True,
        reminders_muted_until__isnull=False,
        reminders_muted_until__lte=today,
    ).update(reminders_muted=False, reminders_muted_until=None)


def _rearm_moved_incomes():
    """Restart the cadence of incomes whose expected date was edited."""
    from content.models import IncomeRecord

    IncomeRecord.objects.filter(
        Q(retention_context__isnull=True) & Q(reminder_target_date__isnull=False)
        & ~Q(reminder_target_date=F('period_date')),
    ).update(
        reminder_target_date=F('period_date'),
        reminder_last_sent_at=None,
        reminder_count=0,
    )


def mark_income_notices_sent(items, today):
    from content.models import IncomeRecord

    for item in items:
        # System state, not a user change: update directly (no audit trail).
        IncomeRecord.objects.filter(pk=item['id']).update(
            reminder_target_date=item['due_date'],
            reminder_last_sent_at=today,
            reminder_count=F('reminder_count') + 1,
        )


def _income_item(record, today):
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    paid = getattr(record, 'paid_amount', None) or 0
    pending = record.total_amount - paid
    client = record.client
    return {
        'kind': 'income',
        'id': record.pk,
        'title': record.concept,
        'subtitle': '',
        'client_name': build_client_display_name(client) if client else '',
        'due_date': record.period_date,
        'days_left': (record.period_date - today).days,
        'amount': pending,
        # Only carried when it differs, so the template can say "de $X" for a
        # partial payment and stay quiet for an untouched receivable.
        'total': record.total_amount if paid else None,
        'notice_number': record.reminder_count + 1,
        'detail': '',
    }


# ── Recurring payments ───────────────────────────────────────────────────────

def collect_recurring_notices(today):
    """Recurring payments whose next charge is due for a notice today.

    No overdue branch: `next_charge_date` always returns an occurrence on or
    after today, so the day after the charge the projection rolls to the next
    cycle and the record goes quiet by itself. An unpaid cycle does not nag.
    """
    from content.models import RecurringPayment

    RecurringPayment.objects.filter(
        reminders_muted=True,
        reminders_muted_until__isnull=False,
        reminders_muted_until__lte=today,
    ).update(reminders_muted=False, reminders_muted_until=None)

    items = []
    rearmed, without_schedule = [], 0
    for payment in RecurringPayment.objects.filter(
        is_active=True,
        is_archived=False,
        reminders_muted=False,
    ):
        try:
            target = next_charge_date(payment, today)
            if target is None:
                without_schedule += 1
                continue

            # The target is computed, not stored, so the re-arm comparison
            # happens here instead of in bulk SQL. A rolled-over cycle and an
            # edited anchor are the same event: the target moved.
            last_sent = payment.reminder_last_sent_at
            if payment.reminder_target_date != target:
                last_sent = None
                if payment.reminder_target_date is not None:
                    rearmed.append(payment.pk)

            if not is_notice_due(
                target_date=target,
                last_sent_at=last_sent,
                today=today,
                milestones=MILESTONES,
                repeat_every_days=None,
            ):
                continue
            items.append(_recurring_item(payment, target, today))
        except Exception:
            logger.exception(
                'Skipping recurring payment %s while building the payment calendar',
                payment.pk,
            )

    if rearmed:
        RecurringPayment.objects.filter(pk__in=rearmed).update(
            reminder_target_date=None, reminder_last_sent_at=None,
        )
    if without_schedule:
        logger.info(
            '%s recurring payments have no computable next charge '
            '(no reference date and not monthly).',
            without_schedule,
        )
    return items


def mark_recurring_notices_sent(items, today):
    from content.models import RecurringPayment

    for item in items:
        # System state, not a user change: update directly (no audit trail).
        RecurringPayment.objects.filter(pk=item['id']).update(
            reminder_target_date=item['due_date'],
            reminder_last_sent_at=today,
        )


def _recurring_item(payment, target, today):
    return {
        'kind': 'recurring',
        'id': payment.pk,
        'title': payment.name,
        'subtitle': '',
        'client_name': '',
        'due_date': target,
        'days_left': (target - today).days,
        'amount': payment.price,
        'total': None,
        'notice_number': None,
        'detail': payment.frequency_display,
        'currency': payment.currency,
    }


# ── Delivery ─────────────────────────────────────────────────────────────────

def _days(count):
    from datetime import timedelta

    return timedelta(days=count)


def status_label(item):
    """"En 7 días" / "Vence hoy" / "Vencido hace 3 días", plus the notice number.

    Built in Python so the text and the html bodies cannot drift apart, and so
    the plural agreement is not a template's problem.
    """
    days_left = item['days_left']
    if days_left > 0:
        label = f'En {days_left} día' + ('s' if days_left > 1 else '')
    elif days_left == 0:
        label = 'Vence hoy'
    else:
        overdue = abs(days_left)
        label = f'Vencido hace {overdue} día' + ('s' if overdue > 1 else '')
    number = item.get('notice_number')
    if number and number > 1:
        label += f' · aviso #{number}'
    return label


def _sorted(items):
    """Most overdue first, then the closest; amount and id break ties."""
    return sorted(items, key=lambda i: (i['days_left'], -(i['amount'] or 0), i['id']))


def _counts(items):
    return {
        'overdue': sum(1 for i in items if i['days_left'] < 0),
        'due_today': sum(1 for i in items if i['days_left'] == 0),
        'upcoming': sum(1 for i in items if i['days_left'] > 0),
    }


def _subject(counts):
    parts = []
    if counts['overdue']:
        n = counts['overdue']
        parts.append(f'{n} vencido' + ('s' if n > 1 else ''))
    if counts['due_today']:
        n = counts['due_today']
        parts.append(f'{n} vence' + ('n' if n > 1 else '') + ' hoy')
    if counts['upcoming']:
        n = counts['upcoming']
        parts.append(f'{n} próximo' + ('s' if n > 1 else ''))
    return '[Contabilidad] Calendario de cobros y pagos: ' + ', '.join(parts)


def _send_digest(today, incomes, recurring, hostings, recipients, config):
    from content.models import EmailLog

    incomes, recurring, hostings = _sorted(incomes), _sorted(recurring), _sorted(hostings)
    everything = incomes + recurring + hostings
    for item in everything:
        # Stamped per item rather than looked up by id: ids repeat across
        # sections, so a shared lookup would cross the wires between an income
        # and a recurring payment that happen to share a pk.
        item['status'] = status_label(item)
    counts = _counts(everything)
    subject = _subject(counts)
    base_url = getattr(settings, 'FRONTEND_BASE_URL', '').rstrip('/')
    context = {
        'incomes': incomes,
        'recurring': recurring,
        'hostings': hostings,
        'has_overdue': counts['overdue'] > 0,
        'overdue_frequency_label': config.get_overdue_reminder_frequency_display(),
        'panel_url': f'{base_url}/panel/accounting/incomes',
        'hostings_url': f'{base_url}/panel/accounting/hostings',
    }
    metadata = _metadata(today, incomes, recurring, hostings, counts, config)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co')
    # One digest names many records; linking each of them is what lets the
    # history answer "what went out for this hosting" from the hosting's row.
    # And why it passes no client=: it names several at once, so filing it
    # under whichever came first would be a lie the clients list would count.
    targets = (
        [('income', item['id'], item.get('title', '')) for item in incomes]
        + [('recurring', item['id'], item.get('title', '')) for item in recurring]
        + [('hosting', item['id'], item.get('title', '')) for item in hostings]
    )
    text_body = html_body = ''

    try:
        text_body = render_to_string('emails/accounting_payment_calendar.txt', context)
        html_body = render_to_string('emails/accounting_payment_calendar.html', context)
        email = EmailMultiAlternatives(
            subject=subject, body=text_body, from_email=from_email, to=recipients,
        )
        email.attach_alternative(html_body, 'text/html')
        EmailDeliveryGateway.send(
            email,
            template_key=TEMPLATE_KEY,
            classification=DeliveryClassification.INTERNAL,
        )
    except Exception as exc:
        logger.warning('Failed to send the payment calendar: %s', exc)
        email_log_service.record_send(
            template_key=TEMPLATE_KEY,
            recipients=recipients,
            subject=subject,
            status=EmailLog.Status.FAILED,
            error_message=str(exc),
            metadata=metadata,
            targets=targets,
            html_body=html_body,
            text_body=text_body,
        )
        return False

    email_log_service.record_send(
        template_key=TEMPLATE_KEY,
        recipients=recipients,
        subject=subject,
        status=EmailLog.Status.SENT,
        metadata=metadata,
        targets=targets,
        html_body=html_body,
        text_body=text_body,
    )
    logger.info(
        'Sent the payment calendar: %s ingresos, %s recurrentes, %s hostings',
        len(incomes), len(recurring), len(hostings),
    )
    return True


def _metadata(today, incomes, recurring, hostings, counts, config):
    """Everything needed to answer "why didn't the notice for X arrive?".

    Naming each record that went out means an absence is an answer too: the
    income is paid, lost or muted.
    """
    def line(item):
        return {
            'id': item['id'],
            'title': item['title'],
            'due_date': item['due_date'].isoformat(),
            'days_left': item['days_left'],
            'notice_number': item.get('notice_number'),
        }

    return {
        'date': today.isoformat(),
        'counts': {
            'incomes': len(incomes),
            'recurring': len(recurring),
            'hostings': len(hostings),
            **counts,
        },
        'overdue_every_days': OVERDUE_FREQUENCY_DAYS.get(
            config.overdue_reminder_frequency, 14,
        ),
        'incomes': [line(i) for i in incomes],
        'recurring': [line(i) for i in recurring],
        'hostings': [line(i) for i in hostings],
    }
