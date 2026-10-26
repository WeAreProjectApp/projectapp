"""One eligibility source for radar totals, pages and current record details."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q

from content.models import BusinessProposal, Document, EmailDeliverySnapshot, EmailLog, RecurringPayment, Task
from content.services.diagnostic_privacy import safe_email_diagnostic
from content.services.recurring_schedule import next_charge_date

TYPES = ('documents_overdue', 'emails_failed', 'tasks_overdue', 'proposals_stale', 'recurring_due')
FAILED = (EmailLog.Status.FAILED, EmailLog.Status.BOUNCED)


def failed_email_incidents(now):
    """Collapse recipient rows and linked retries; the latest attempt owns state.

    Read only slim rows in the seven-day window. Snapshot ancestry is loaded
    in sets (also across the window boundary), never one query per message.
    Copy envelopes cannot resolve a primary delivery or expose BCC recipients.
    """
    rows = list(EmailLog.objects.filter(
        sent_at__gte=now - timedelta(days=7),
        status__in=(*FAILED, EmailLog.Status.SENT, EmailLog.Status.DELIVERED),
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    ).order_by('sent_at', 'id').values(
        'id', 'delivery_id', 'snapshot_id', 'sent_at', 'status', 'retry_of_id',
    ))
    parents = {}
    pending = {row['snapshot_id'] for row in rows if row['snapshot_id']}
    while pending:
        found = dict(EmailDeliverySnapshot.objects.filter(pk__in=pending).values_list('id', 'resend_of_id'))
        parents.update(found)
        pending = {parent for parent in found.values() if parent and parent not in parents}

    def root(snapshot_id):
        seen = set()
        while parents.get(snapshot_id) and snapshot_id not in seen:
            seen.add(snapshot_id)
            snapshot_id = parents[snapshot_id]
        return snapshot_id

    deliveries = {}
    log_keys = {}
    for row in rows:
        key = ('snapshot', root(row['snapshot_id'])) if row['snapshot_id'] else (
            'delivery', str(row['delivery_id']) if row['delivery_id'] else row['id'],
        )
        key = log_keys.get(row['retry_of_id'], key)
        log_keys[row['id']] = key
        attempt = str(row['delivery_id']) if row['delivery_id'] else row['id']
        incident = deliveries.setdefault(key, {})
        incident.setdefault(attempt, []).append(row)

    result = []
    for attempts in deliveries.values():
        latest = max(attempts.values(), key=lambda group: max((row['sent_at'], row['id']) for row in group))
        failures = [row for row in latest if row['status'] in FAILED]
        if failures:
            # A stable visible primary representative; a CC bounce still surfaces.
            result.append(min(failures, key=lambda row: row['id']))
    return sorted(result, key=lambda row: (row['sent_at'], row['id']), reverse=True)


def attention_records(kind, today, now):
    if kind == 'emails_failed':
        return failed_email_incidents(now)
    if kind == 'documents_overdue':
        return Document.objects.filter(
            commercial_status=Document.CommercialStatus.ISSUED, due_date__lt=today,
        ).only('id', 'title', 'client_name', 'total', 'currency', 'due_date').order_by('due_date', 'id')
    if kind == 'tasks_overdue':
        return Task.objects.filter(is_archived=False, due_date__lt=today).exclude(
            status=Task.Status.DONE,
        ).select_related('assignee').order_by('due_date', 'id')
    if kind == 'proposals_stale':
        return BusinessProposal.objects.filter(
            status='sent', is_active=True, first_viewed_at__isnull=True,
            sent_at__lt=now - timedelta(days=7),
        ).only('id', 'title', 'client_name', 'sent_at').order_by('sent_at', 'id')
    payments = RecurringPayment.objects.filter(
        is_active=True, is_archived=False, frequency=RecurringPayment.Frequency.MONTHLY,
    ).filter(Q(reminders_muted=False) | Q(reminders_muted_until__isnull=False, reminders_muted_until__lte=today))
    due = []
    for payment in payments:
        target = next_charge_date(payment, today)
        if target and 0 <= (target - today).days <= 7:
            payment.radar_charge_date = target
            due.append(payment)
    return sorted(due, key=lambda payment: (payment.radar_charge_date, payment.pk))


def record_count(records):
    return len(records) if isinstance(records, list) else records.count()


def record_model(kind):
    return {
        'emails_failed': EmailLog, 'recurring_due': RecurringPayment,
        'tasks_overdue': Task, 'documents_overdue': Document,
        'proposals_stale': BusinessProposal,
    }[kind]


def record_payload(kind, obj, today):
    """Small identification payload, with local destinations only."""
    data = {'id': obj.pk, 'type': kind}
    if kind == 'emails_failed':
        from content.services.email_log_service import attach_delivery_recipients, delivery_recipient_payloads
        if not hasattr(obj, '_delivery_recipients'):
            attach_delivery_recipients([obj])
        recipients = delivery_recipient_payloads(obj)
        for group in recipients.values():
            for recipient in group:
                recipient['error_message'] = safe_email_diagnostic(recipient['error_message'])
        data.update(
            title=obj.subject or 'Sin asunto', sent_at=obj.sent_at.isoformat(),
            error_message=safe_email_diagnostic(obj.error_message),
            recipient=obj.recipient if obj.recipient_kind != EmailLog.RecipientKind.BCC else '',
            **recipients, can_resend=bool(obj.snapshot_id),
            destination=f'/panel/emails?tab=history&email={obj.pk}&radar=1',
        )
    elif kind == 'recurring_due':
        target = getattr(obj, 'radar_charge_date', None) or next_charge_date(obj, today)
        data.update(
            title=obj.name, amount=str(obj.price), currency=obj.currency,
            due_date=target.isoformat() if target else None,
            payment_method=obj.get_payment_method_display(),
            destination=f'/panel/accounting/recurring?recurring={obj.pk}&radar=1',
        )
    elif kind == 'tasks_overdue':
        data.update(
            title=obj.title, assignee=(obj.assignee.get_full_name() or obj.assignee.username) if obj.assignee else '',
            due_date=obj.due_date.isoformat() if obj.due_date else None,
            priority={'high': 'Alta', 'medium': 'Media', 'low': 'Baja'}.get(obj.priority, obj.priority),
            description=obj.description, is_archived=obj.is_archived,
            board_type=obj.board_type,
            destination=f'/panel/tasks?task={obj.pk}&radar=1',
        )
    elif kind == 'documents_overdue':
        data.update(
            title=obj.title, client=obj.client_name, amount=str(obj.total) if obj.total is not None else None,
            currency=obj.currency, due_date=obj.due_date.isoformat() if obj.due_date else None,
            destination=f'/panel/documents/{obj.pk}/edit?radar=1',
        )
    else:
        data.update(
            title=obj.title, client=obj.client_name,
            sent_at=obj.sent_at.isoformat() if obj.sent_at else None,
            days_unopened=(today - obj.sent_at.astimezone(ZoneInfo('America/Bogota')).date()).days if obj.sent_at else None,
            destination=f'/panel/proposals/{obj.pk}/edit?radar=1',
        )
    return data
