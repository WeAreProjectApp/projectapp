"""Retry a single failed recipient from exact evidence or its accounting origin."""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from content.models import EmailLog
from content.services import accounting_email_retry_service as accounting
from content.services.diagnostic_privacy import safe_email_diagnostic


def requires_superuser(log):
    return not log.snapshot_id and log.template_key in accounting.RETRY_HANDLERS


def _source_for(log):
    from accounts.models import Payment
    from content.models import AccountingChangeLog, Document, IncomeCompletionNotice

    sources = {
        'accounting_change': (AccountingChangeLog, 'change_log_id'),
        'collection_account_sent': (Document, 'document_id'),
        'payment_status_team': (Payment, 'payment_id'),
        'income_completed_account_pending': (IncomeCompletionNotice, 'completion_notice_id'),
    }
    model, key = sources[log.template_key]
    metadata = log.metadata if isinstance(log.metadata, dict) else {}
    return model, metadata.get(key)


def prepare_retry_sources(logs):
    """Resolve history-page origins by family, rather than querying per address."""
    from content.models import IncomeRecord

    pending = [log for log in logs if log.status == EmailLog.Status.FAILED]
    confirmations = [log for log in pending if log.template_key == 'income_payment_received_client']
    ids = {
        str((log.metadata or {}).get('liquid_id'))
        for log in confirmations if isinstance(log.metadata, dict)
    }
    pairs = set(IncomeRecord.objects.filter(
        pk__in=[int(value) for value in ids if value.isdigit()],
        kind=IncomeRecord.Kind.LIQUID,
    ).values_list('pk', 'expected_income_id')) if confirmations else set()
    for log in confirmations:
        metadata = log.metadata if isinstance(log.metadata, dict) else {}
        try:
            pair = (int(metadata.get('liquid_id')), int(metadata.get('income_id')))
        except (TypeError, ValueError):
            pair = (None, None)
        log._retry_payment_exists = pair in pairs

    groups = {}
    for log in pending:
        if log.snapshot_id or log.template_key == 'income_payment_received_client' or log.template_key not in accounting.RETRY_HANDLERS:
            continue
        model, source_id = _source_for(log)
        groups.setdefault(model, []).append((log, source_id))
    for model, rows in groups.items():
        existing = set(model.objects.filter(
            pk__in={int(str(source_id)) for _, source_id in rows if str(source_id).isdigit()},
        ).values_list('pk', flat=True))
        for log, source_id in rows:
            log._retry_source_exists = str(source_id).isdigit() and int(source_id) in existing


def retry_blocked_reason(log, actor):
    if log.delivery_role != EmailLog.DeliveryRole.PRIMARY:
        return 'Las copias internas no se reintentan.'
    if log.status != EmailLog.Status.FAILED:
        return 'Solo se reintentan los envíos que fallaron.'
    if requires_superuser(log) and not actor.is_superuser:
        return 'Solo un superusuario puede reconstruir este envío contable.'
    try:
        validate_email(log.recipient)
    except ValidationError:
        return 'El registro no conservó un destinatario válido para reintentar.'
    if log.template_key == 'income_payment_received_client':
        try:
            accounting.payment_confirmation_values(log, payment_exists=getattr(log, '_retry_payment_exists', None))
        except accounting.RetryError as exc:
            return str(exc)
    if log.snapshot_id:
        return ''
    if log.template_key not in accounting.RETRY_HANDLERS:
        if log.template_key in accounting.DIGEST_TEMPLATE_KEYS:
            return accounting.retry_blocked_reason(log.template_key)
        return 'Este envío no conserva una copia exacta ni un origen compatible para reconstruirlo.'
    if log.template_key == 'income_payment_received_client':
        return ''

    model, source_id = _source_for(log)
    source_exists = getattr(log, '_retry_source_exists', None)
    if source_exists is None:
        source_exists = str(source_id).isdigit() and model.objects.filter(pk=source_id).exists()
    if not source_exists:
        return 'Este envío no conservó un origen disponible para reconstruirlo.'
    return ''


def retry_payload(log, actor):
    reason = retry_blocked_reason(log, actor)
    return {
        'is_retryable': not reason,
        'retry_blocked_reason': reason,
        'retry_of': log.retry_of_id,
    }


def retry_send(log, actor):
    reason = retry_blocked_reason(log, actor)
    if reason:
        raise accounting.RetryError(reason)
    if log.snapshot_id:
        from content.services.email_snapshot_service import resend_email_log

        return resend_email_log(log, [log.recipient])
    return accounting.retry_send(log)


def error_message(log):
    return safe_email_diagnostic(log.error_message)
