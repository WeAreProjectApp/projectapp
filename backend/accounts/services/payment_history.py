"""Append-only payment status transition log."""

import logging

from accounts.models import Payment, PaymentHistory

logger = logging.getLogger(__name__)


def record_payment_status_change(payment, old_status, new_status, source='', metadata=None):
    """
    Persist a PaymentHistory row when status actually changes.
    Call after updating in-memory payment.status but typically before or after save;
    payment.pk must exist.
    """
    if old_status == new_status:
        return None
    history = PaymentHistory.objects.create(
        payment=payment,
        from_status=old_status,
        to_status=new_status,
        source=source or '',
        metadata=metadata if metadata is not None else {},
    )

    # Notify the team inbox on terminal outcomes (approved / failed). Async and
    # best-effort: never let an email problem break the payment flow.
    if new_status in (Payment.STATUS_PAID, Payment.STATUS_FAILED):
        try:
            from accounts.tasks import send_payment_status_team_email_task
            send_payment_status_team_email_task(payment.id, new_status, source or '')
        except Exception:
            logger.warning(
                'PAYMENT_STATUS_EMAIL_ENQUEUE_FAILED payment_id=%s status=%s',
                payment.id,
                new_status,
            )

    return history
