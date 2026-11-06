"""Single writer for the log rows an automated send leaves behind.

Every notice of the accounting module reaches N recipients and produces N
``EmailLog`` rows, so each service used to repeat the same
``for recipient: EmailLog.objects.create(...)`` block twice — once for the
failure path and once for the success one. Worse, the record the notice was
about survived only inside a free-form ``metadata`` dict, which the history
could not query: asking "what went out for this hosting" meant reading JSON
by eye.

``record_send`` writes the rows, the shared body and the ``EmailLogTarget``
links in one place. The digest notices name several records at once, which
is why the links are their own rows instead of a column pair on the log.
"""

from django.db import transaction
from django.db.models import Case, IntegerField, OuterRef, Q, Subquery, Value, When


def client_for_entity(entity_type, object_id):
    """Client pk behind a target row, or None.

    The write-time twin of ``accounting_history_service._client_target_q``,
    which resolves the same three entities at query time. Keep both in step:
    incomes and hostings point at the ``UserProfile``, a cuenta de cobro at
    the ``User`` behind it.
    """
    from content.models import Document, HostingRecord, IncomeRecord

    if not object_id:
        return None
    if entity_type == 'income':
        return (
            IncomeRecord.objects.filter(pk=object_id)
            .values_list('client_id', flat=True).first()
        )
    if entity_type == 'hosting':
        return (
            HostingRecord.objects.filter(pk=object_id)
            .values_list('client_id', flat=True).first()
        )
    if entity_type == 'collection_account':
        return (
            Document.objects.filter(pk=object_id)
            .values_list('client_user__profile__id', flat=True).first()
        )
    return None


def client_for_payment(payment):
    """Client profile behind a platform payment, or None.

    Its own resolver because ``_client_target_q`` never learned to read
    ``payment`` targets: the hosting payment notice is the one accounting
    notice its client filter cannot reach today.
    """
    project = getattr(getattr(payment, 'subscription', None), 'project', None)
    return getattr(getattr(project, 'client', None), 'profile', None)


def _normalize_targets(targets):
    """Coerce the callers' shorthand into ``(entity_type, id, repr)`` rows.

    Accepts dicts or ``(entity_type, object_id[, object_repr])`` sequences,
    drops the incomplete ones and de-duplicates, so a service can hand over
    whatever its context already holds without pre-cleaning it.
    """
    seen = set()
    rows = []
    for item in targets or ():
        if isinstance(item, dict):
            entity_type = item.get('entity_type')
            object_id = item.get('object_id')
            object_repr = item.get('object_repr') or ''
        else:
            entity_type, object_id, *rest = item
            object_repr = rest[0] if rest else ''
        if not entity_type or not object_id:
            continue
        key = (entity_type, int(object_id))
        if key in seen:
            continue
        seen.add(key)
        rows.append((entity_type, int(object_id), str(object_repr)[:255]))
    return rows


@transaction.atomic
def record_send(
    *,
    template_key,
    recipients,
    subject,
    status,
    metadata=None,
    targets=(),
    origin_action='',
    error_message='',
    html_body='',
    text_body='',
    retry_of=None,
    proposal=None,
    client=None,
    audience=None,
    delivery_id=None,
    delivery_role=None,
    recipient_contexts=None,
):
    """Write one ``EmailLog`` per recipient and return them.

    The rendered message is stored once and shared by the sibling rows. The
    body is kept on the failure path too: diagnosing a bounce needs to show
    what could not be delivered.

    ``client`` accepts an instance or a bare pk, so a caller holding only
    ``proposal.client_id`` does not have to load the profile. ``audience``
    defaults to internal: a forgotten one leaves the row out of a client's
    contact count, which is the harmless direction to be wrong in.
    """
    from content.models import EmailBody, EmailLog, EmailLogTarget
    from content.services.email_delivery_service import (
        complete_delivery_log_write,
        matching_delivery_trace,
    )

    client_id = getattr(client, 'pk', client)
    audience = audience or EmailLog.Audience.INTERNAL
    delivery_role = delivery_role or EmailLog.DeliveryRole.PRIMARY
    trace = None
    if delivery_role == EmailLog.DeliveryRole.PRIMARY:
        trace = matching_delivery_trace(template_key, recipients)
    if trace is not None:
        delivery_id = delivery_id or trace.delivery_id

    body = trace.body if trace is not None else None
    if body is None and (html_body or text_body):
        body = EmailBody.objects.create(
            html=html_body or '', text=text_body or '',
        )
    if trace is not None and body is not None:
        trace.body = body

    logs = []
    can_enrich_gateway_rows = (
        trace is not None
        and delivery_role == EmailLog.DeliveryRole.PRIMARY
        and trace.enrichment_count == 0
        and trace.gateway_primary_log_ids
    )
    gateway_rows = {}
    if can_enrich_gateway_rows:
        for log in EmailLog.objects.filter(
            pk__in=trace.gateway_primary_log_ids,
        ):
            gateway_rows.setdefault(log.recipient.strip().lower(), []).append(log)

    contexts_by_email = {
        (item.get('email') or '').strip().lower(): item
        for item in (recipient_contexts or ())
    }
    for recipient in recipients:
        normalized = (recipient or '').strip().lower()
        recipient_context = contexts_by_email.get(normalized, {})
        candidates = gateway_rows.get(normalized, [])
        log = candidates.pop(0) if candidates else None
        if log is None:
            log = EmailLog(
                template_key=template_key,
                recipient=recipient,
                delivery_id=delivery_id,
                delivery_role=delivery_role,
            )
        merged_metadata = dict(log.metadata or {})
        merged_metadata.update(metadata or {})
        log.subject = subject
        log.status = status
        log.error_message = error_message or ''
        log.metadata = merged_metadata
        log.body = body
        if trace is not None:
            log.snapshot = trace.snapshot
        log.origin_action = origin_action or ''
        log.retry_of = retry_of
        log.proposal = proposal
        log.client_id = recipient_context.get('client_id', client_id)
        log.audience = recipient_context.get('audience', audience)
        log.recipient_kind = recipient_context.get(
            'recipient_kind', log.recipient_kind,
        )
        log.save()
        logs.append(log)

    rows = _normalize_targets(targets)
    if rows:
        EmailLogTarget.objects.bulk_create([
            EmailLogTarget(
                email_log=log,
                entity_type=entity_type,
                object_id=object_id,
                object_repr=object_repr,
            )
            for log in logs
            for entity_type, object_id, object_repr in rows
        ])

    # The gateway creates copy rows immediately, even for senders that have no
    # business-specific logger. Enrich those rows when a caller does provide
    # proposal/client/target context, without producing a second BCC record.
    if trace is not None and trace.gateway_copy_log_ids:
        copy_logs = list(EmailLog.objects.filter(pk__in=trace.gateway_copy_log_ids))
        if trace.enrichment_count == 0:
            for copy_log in copy_logs:
                copy_metadata = dict(copy_log.metadata or {})
                copy_metadata.update(metadata or {})
                copy_log.metadata = copy_metadata
                copy_log.subject = subject
                copy_log.body = body
                copy_log.snapshot = trace.snapshot
                copy_log.origin_action = origin_action or ''
                copy_log.proposal = proposal
                copy_log.client_id = client_id
                copy_log.save()
            if rows:
                EmailLogTarget.objects.bulk_create([
                    EmailLogTarget(
                        email_log=log,
                        entity_type=entity_type,
                        object_id=object_id,
                        object_repr=object_repr,
                    )
                    for log in copy_logs
                    for entity_type, object_id, object_repr in rows
                ])

    if trace is not None:
        trace.enrichment_count += 1
        complete_delivery_log_write(trace)

    return logs


def attach_delivery_copies(logs):
    """Batch-load copy attempts and attach them to primary log instances."""
    from content.models import EmailLog

    logs = list(logs)
    delivery_ids = {
        log.delivery_id for log in logs
        if log.delivery_id and log.delivery_role == EmailLog.DeliveryRole.PRIMARY
    }
    copies_by_delivery = {delivery_id: [] for delivery_id in delivery_ids}
    if delivery_ids:
        copies = EmailLog.objects.filter(
            delivery_id__in=delivery_ids,
            delivery_role=EmailLog.DeliveryRole.COPY,
        ).order_by('sent_at', 'id')
        for copy_log in copies:
            copies_by_delivery.setdefault(copy_log.delivery_id, []).append(copy_log)
    for log in logs:
        log._delivery_copies = copies_by_delivery.get(log.delivery_id, [])
    return logs


def representative_delivery_queryset(logs):
    """Collapse primary log rows to one stable row per SMTP delivery."""
    from content.models import EmailLog

    first_primary_id = (
        EmailLog.objects.filter(
            delivery_id=OuterRef('delivery_id'),
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
        )
        .annotate(
            _kind_order=Case(
                When(recipient_kind=EmailLog.RecipientKind.TO, then=Value(0)),
                When(recipient_kind=EmailLog.RecipientKind.CC, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ),
        )
        .order_by('_kind_order', 'id')
        .values('id')[:1]
    )
    return logs.filter(
        Q(delivery_id__isnull=True) | Q(pk=Subquery(first_primary_id)),
    )


def _retain_matching_deliveries(logs, matching_logs):
    """Expand matching rows back to all primary siblings of each delivery."""
    matching_delivery_ids = matching_logs.filter(
        delivery_id__isnull=False,
    ).order_by().values('delivery_id')
    matching_legacy_ids = matching_logs.filter(
        delivery_id__isnull=True,
    ).order_by().values('id')
    return logs.filter(
        Q(delivery_id__in=Subquery(matching_delivery_ids))
        | Q(pk__in=Subquery(matching_legacy_ids)),
    )


def filter_delivery_recipient(logs, search):
    """Match any To/CC sibling while retaining the complete delivery group."""
    search = (search or '').strip()
    if not search:
        return logs
    return _retain_matching_deliveries(
        logs,
        logs.filter(recipient__icontains=search),
    )


def filter_delivery_status(logs, status):
    """Match a per-address status without hiding the delivery representative."""
    if not status:
        return logs
    return _retain_matching_deliveries(logs, logs.filter(status=status))


def filter_delivery_log_id(logs, log_id):
    """Resolve a deep link from any sibling row to its grouped delivery."""
    if not log_id:
        return logs
    return _retain_matching_deliveries(logs, logs.filter(pk=log_id))


def attach_delivery_recipients(logs):
    """Batch-load every visible primary recipient for representative rows."""
    from content.models import EmailLog

    logs = list(logs)
    delivery_ids = {log.delivery_id for log in logs if log.delivery_id}
    recipients_by_delivery = {delivery_id: [] for delivery_id in delivery_ids}
    if delivery_ids:
        recipient_logs = (
            EmailLog.objects.filter(
                delivery_id__in=delivery_ids,
                delivery_role=EmailLog.DeliveryRole.PRIMARY,
            )
            .select_related('client__user', 'snapshot')
            .annotate(
                _kind_order=Case(
                    When(recipient_kind=EmailLog.RecipientKind.TO, then=Value(0)),
                    When(recipient_kind=EmailLog.RecipientKind.CC, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
            )
            .order_by('_kind_order', 'id')
        )
        for recipient_log in recipient_logs:
            recipients_by_delivery.setdefault(
                recipient_log.delivery_id, [],
            ).append(recipient_log)
    for log in logs:
        log._delivery_recipients = (
            recipients_by_delivery.get(log.delivery_id, [log])
            if log.delivery_id else [log]
        )
    return logs


def delivery_recipient_payloads(log, *, retry_actor=None):
    """Return separate To/CC payloads for one grouped history result."""
    from accounts.services.proposal_client_service import build_client_display_name
    from content.models import EmailLog

    recipient_logs = getattr(log, '_delivery_recipients', [log])
    groups = {'to_recipients': [], 'cc_recipients': []}
    for recipient_log in recipient_logs:
        if recipient_log.recipient_kind == EmailLog.RecipientKind.BCC:
            continue
        profile = recipient_log.client
        payload = {
            'email': recipient_log.recipient,
            'status': recipient_log.status,
            'status_label': recipient_log.get_status_display(),
            'error_message': recipient_log.error_message,
            'client_id': profile.pk if profile else None,
            'client_name': build_client_display_name(profile) if profile else '',
        }
        if retry_actor is not None:
            from content.services.email_retry_service import error_message, retry_payload

            payload.update({
                'id': recipient_log.pk, 'error_message': error_message(recipient_log),
                **retry_payload(recipient_log, retry_actor),
            })
        key = (
            'cc_recipients'
            if recipient_log.recipient_kind == EmailLog.RecipientKind.CC
            else 'to_recipients'
        )
        groups[key].append(payload)
    return groups


def delivery_copy_payloads(log):
    """Serialize the internal attempts belonging to one primary delivery."""
    from content.models import EmailLog

    copies = getattr(log, '_delivery_copies', None)
    if copies is None:
        if not log.delivery_id or log.delivery_role != EmailLog.DeliveryRole.PRIMARY:
            copies = []
        else:
            copies = EmailLog.objects.filter(
                delivery_id=log.delivery_id,
                delivery_role=EmailLog.DeliveryRole.COPY,
            ).order_by('sent_at', 'id')
    return [
        {
            'id': copy_log.pk,
            'recipient': copy_log.recipient,
            'status': copy_log.status,
            'status_label': copy_log.get_status_display(),
            'error_message': copy_log.error_message,
            'sent_at': copy_log.sent_at,
        }
        for copy_log in copies
    ]
