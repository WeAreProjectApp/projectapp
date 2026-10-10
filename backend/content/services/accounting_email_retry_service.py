"""Retry one failed send, from its own row in Historial.

Only the notices tied to a single record can be retried. The other three are
digests assembled from whatever was due that morning: re-running one would
build today's summary and send it under the guise of the message that
failed, which is worse than not retrying at all.

The retry goes to the address on the row and to no one else. The rest of the
recipients already received their copy — the failure was per-address, and so
is the fix.
"""

import logging

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised with a user-facing Spanish message when a retry cannot run."""


def _retry_accounting_change(log):
    from content.models import AccountingChangeLog
    from content.services.accounting_email_service import (
        send_accounting_change_email,
    )

    change_log_id = (log.metadata or {}).get('change_log_id')
    if not change_log_id:
        raise RetryError(
            'Este envío no guardó a qué cambio correspondía, así que no se '
            'puede reconstruir.',
        )
    if not AccountingChangeLog.objects.filter(id=change_log_id).exists():
        raise RetryError('El cambio que originó este aviso ya no existe.')
    return send_accounting_change_email(
        change_log_id, recipients=[log.recipient], retry_of=log,
    )


def _retry_collection_account(log):
    from content.models import Document
    from content.services.collection_account_email_service import (
        send_collection_account_email,
    )

    document_id = (log.metadata or {}).get('document_id')
    document = Document.objects.filter(id=document_id).first()
    if document is None:
        raise RetryError('La cuenta de cobro de este envío ya no existe.')
    return send_collection_account_email(
        document, resend=True, retry_of=log,
    )


def _retry_payment_status(log):
    from accounts.models import Payment
    from accounts.services.payment_notifications import (
        send_payment_status_team_email,
    )

    metadata = log.metadata or {}
    payment_id = metadata.get('payment_id')
    if not Payment.objects.filter(id=payment_id).exists():
        raise RetryError('El pago que originó este aviso ya no existe.')
    return send_payment_status_team_email(
        payment_id,
        metadata.get('to_status', ''),
        metadata.get('source', ''),
        recipients=[log.recipient],
        retry_of=log,
    )


def _retry_payment_confirmation(log):
    """Re-send the same confirmation from the facts stored on the row.

    Re-reading the income would state today's balance, not the one the
    client was told about. The payment must still exist, though: confirming
    a settlement that was undone would tell the client something false.
    """
    from content.models import IncomeRecord
    from content.services.income_payment_confirmation_service import (
        send_payment_confirmation_email,
        values_from_metadata,
    )

    values = values_from_metadata(log.metadata)
    if not values.get('liquid_id'):
        raise RetryError(
            'Este envío no guardó qué pago confirmaba, así que no se puede '
            'reconstruir.',
        )
    if not IncomeRecord.objects.filter(
        id=values['liquid_id'],
        kind=IncomeRecord.Kind.LIQUID,
        expected_income_id=values.get('income_id'),
    ).exists():
        raise RetryError('El pago que confirmaba este correo ya no existe.')
    return send_payment_confirmation_email(
        values, recipient=log.recipient, client=log.client_id, retry_of=log,
    )


# One entry per notice that names a single record. `is_retryable` on the
# serializer reads the same set, so the row and the endpoint cannot disagree
# about what the button is allowed to do.
RETRY_HANDLERS = {
    'accounting_change': _retry_accounting_change,
    'collection_account_sent': _retry_collection_account,
    'income_payment_received_client': _retry_payment_confirmation,
    'payment_status_team': _retry_payment_status,
}

# The three digests. Named here rather than imported from the serializers so
# this module keeps no import edge back into them.
DIGEST_TEMPLATE_KEYS = frozenset({
    'accounting_card_reminder',
    'accounting_statement_reminder',
    'accounting_payment_calendar',
})

# Everything else with no handler: proposal and diagnostic traffic, which the
# client's email view lists alongside the accounting notices. Telling those
# rows they "resume varios registros del día" would be nonsense, so they get
# the sentence that actually helps.
UNSUPPORTED_RETRY_REASON = (
    'Los correos de propuestas y diagnósticos no se reenvían desde aquí; '
    'vuelve a enviarlo desde la propuesta o el diagnóstico.'
)


def retry_blocked_reason(template_key):
    """Why this notice cannot be retried, or '' when it can.

    One source of truth for three families, read by both the endpoint and
    the serializer field the button's tooltip renders.
    """
    from content.serializers.accounting import RETRY_BLOCKED_REASON

    if template_key in RETRY_HANDLERS:
        return ''
    if template_key in DIGEST_TEMPLATE_KEYS:
        return RETRY_BLOCKED_REASON
    return UNSUPPORTED_RETRY_REASON


def retry_send(log):
    """Re-send the notice this row failed to deliver, to its recipient only.

    Returns the new ``EmailLog`` row, which is linked back to this one by
    ``retry_of``. Raises ``RetryError`` with a message for the panel when the
    retry cannot be attempted at all.
    """
    from content.models import EmailLog

    if log.delivery_role == EmailLog.DeliveryRole.COPY:
        raise RetryError('Las copias internas no se reintentan.')
    if log.status != EmailLog.Status.FAILED:
        raise RetryError('Solo se reintentan los envíos que fallaron.')

    handler = RETRY_HANDLERS.get(log.template_key)
    if handler is None:
        raise RetryError(retry_blocked_reason(log.template_key))

    sent = handler(log)
    attempt = EmailLog.objects.filter(retry_of=log).order_by('-sent_at').first()
    if not sent:
        detail = attempt.error_message if attempt else ''
        logger.warning(
            'Retry of email log %s failed: %s', log.id, detail or 'no detail',
        )
        raise RetryError(
            f'El reintento tampoco salió: {detail}' if detail
            else 'El reintento tampoco salió; revisa los logs.',
        )
    return attempt
