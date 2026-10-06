"""Team-facing email notifications for hosting payment outcomes.

Whenever a Payment transitions to PAID or FAILED, the active recipients of
the accounting module receive a summary so payment status can be tracked
outside the in-app notifications. The destinations come from the same
administrable list as every other notification of the module — this used to
be a single inbox hardcoded in settings — and each send leaves one EmailLog
row per recipient so the panel can answer "why didn't I get this one".
Best-effort: never raises.
"""

import logging

from django.conf import settings
from django.template.loader import render_to_string

from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)

logger = logging.getLogger(__name__)

TEMPLATE_KEY = 'payment_status_team'

# Human-readable labels per payment status (keys are Payment.STATUS_* values).
_STATUS_LABELS = {
    'paid': 'Pago aprobado',
    'failed': 'Pago fallido',
    'overdue': 'Pago vencido',
    'pending': 'Pago pendiente',
    'processing': 'Pago en proceso',
}


def build_payment_status_context(payment, to_status, source=''):
    """Build the template context for a payment-status team email."""
    sub = payment.subscription
    project = sub.project
    client = getattr(project, 'client', None)
    client_name = ''
    client_email = ''
    if client is not None:
        client_name = (
            f'{client.first_name} {client.last_name}'.strip()
            or client.email
            or ''
        )
        client_email = client.email or ''

    return {
        'status_label': _STATUS_LABELS.get(to_status, to_status),
        'is_paid': to_status == 'paid',
        'is_failed': to_status == 'failed',
        'client_name': client_name,
        'client_email': client_email,
        'project_name': project.name,
        'project_id': project.id,
        'amount': payment.amount,
        'currency': 'COP',
        'billing_period_start': payment.billing_period_start,
        'billing_period_end': payment.billing_period_end,
        'due_date': payment.due_date,
        'transaction_id': payment.wompi_transaction_id or '',
        'source': source or '',
        'payment_id': payment.id,
        'last_charge_error': payment.last_charge_error or '',
    }


def send_payment_status_team_email(
    payment_id, to_status, source='', *, recipients=None, retry_of=None,
):
    """
    Render and send the team notification for a payment outcome.
    Returns True if the email was sent, False otherwise. Never raises.

    `recipients` overrides the configured list — a manual retry re-sends to
    the one address that failed, not to everybody who already got it.
    """
    from accounts.models import Payment
    from content.models import AccountingSettings, EmailLog
    from content.services import email_log_service
    from content.services.notification_recipient_service import (
        active_recipient_emails,
    )

    if not AccountingSettings.load().notifications_enabled:
        logger.info(
            'Accounting notifications disabled; skipping payment email for %s',
            payment_id,
        )
        return False

    recipients = recipients or active_recipient_emails()
    if not recipients:
        logger.warning(
            'No active notification recipients; skipping payment email for %s',
            payment_id,
        )
        return False

    try:
        payment = Payment.objects.select_related(
            'subscription__project__client__profile',
        ).get(id=payment_id)
    except Payment.DoesNotExist:
        logger.warning('Payment %s not found for team status email', payment_id)
        return False

    if payment.subscription.retention_context_id or not payment.subscription.project_id:
        return False

    from content.utils import format_cop_email

    context = build_payment_status_context(payment, to_status, source)
    subject = (
        f'{context["status_label"]} · {context["project_name"]} · '
        f'${format_cop_email(context["amount"])} COP'
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co')
    metadata = {
        'payment_id': payment_id,
        'to_status': to_status,
        'source': source or '',
    }
    targets = [('payment', payment_id, context['project_name'])]
    # Internal: this one tells the team a hosting payment moved. Filed under
    # the client anyway, and through its own resolver because `payment`
    # targets are exactly what the query-time mapping never learned to read.
    client = email_log_service.client_for_payment(payment)
    text_body = html_body = ''

    try:
        text_body = render_to_string('emails/payment_status_team.txt', context)
        html_body = render_to_string('emails/payment_status_team.html', context)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=recipients,
        )
        email.attach_alternative(html_body, 'text/html')
        EmailDeliveryGateway.send(
            email,
            template_key=TEMPLATE_KEY,
            classification=DeliveryClassification.INTERNAL,
        )
    except Exception as exc:
        logger.warning(
            'Failed to send payment status email for payment %s: %s',
            payment_id, exc,
        )
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
            retry_of=retry_of,
            client=client,
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
        retry_of=retry_of,
        client=client,
    )
    logger.info(
        'Sent payment status email (%s) for payment %s to %s',
        to_status, payment_id, ', '.join(recipients),
    )
    return True
