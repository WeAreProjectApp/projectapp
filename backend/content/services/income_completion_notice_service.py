"""A completed income can be paid before its cuenta de cobro is issued.

The event is unique per income and committed with the payment. Queue failures
leave it pending for recovery; delivery failures are retried from EmailLog,
never by creating another financial event.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string

from content.models import AccountingSettings, EmailLog, IncomeCompletionNotice, IncomeRecord
from content.services import email_log_service
from content.services.email_delivery_service import (
    DeliveryClassification, EmailDeliveryGateway, EmailMultiAlternatives,
)
from content.services.income_settlement_policy import issued_collection_account
from content.services.notification_recipient_service import active_recipient_emails

logger = logging.getLogger(__name__)
TEMPLATE_KEY = 'income_completed_account_pending'


def needs_collection_account(income):
    from content.services.accounting_settlement_service import income_payment_status

    return (
        income is not None and income.kind == IncomeRecord.Kind.EXPECTED
        and income.ledger == 'company' and income.total_amount > 0
        and income_payment_status(income) == 'paid'
        and issued_collection_account(income) is None
    )


def _enqueue(notice_id):
    try:
        from content.tasks import send_income_completion_notice
        send_income_completion_notice(notice_id)
    except Exception:
        logger.exception('Completion notice %s remains pending after enqueue failure.', notice_id)


def schedule_completion_notice(income, *, was_paid):
    """Called inside the financial transaction, after its final balances exist."""
    if was_paid or not needs_collection_account(income):
        return None
    from accounts.services.proposal_client_service import build_client_display_name

    notice, created = IncomeCompletionNotice.objects.get_or_create(
        income=income,
        defaults={'values': {
            'income_id': income.pk,
            'concept': income.concept,
            'client_name': build_client_display_name(income.client) if income.client_id else 'Sin cliente',
            'project_name': income.project.name if income.project_id else '',
            'total_amount': str(income.total_amount),
        }},
    )
    if created:
        transaction.on_commit(lambda: _enqueue(notice.pk), robust=True)
    return notice


def build_completion_email(values):
    from content.services.collection_account_email_service import format_cop_email

    base_url = getattr(settings, 'FRONTEND_BASE_URL', '').rstrip('/')
    context = {
        **values,
        'formatted_total': format_cop_email(Decimal(values['total_amount'])),
        'income_url': f'{base_url}/panel/accounting/incomes?income={values["income_id"]}',
    }
    return {
        'subject': f'[Contabilidad] Ingreso completo: {values["concept"]} — cuenta pendiente',
        'text_body': render_to_string('emails/income_completion_notice.txt', context),
        'html_body': render_to_string('emails/income_completion_notice.html', context),
    }


def _claim_notice(notice_id, *, retry_recipient=None):
    """Serialize consumers in the same Project -> Income -> Document order."""
    from accounts.services.billing_locks import lock_billing_rows

    income_id = IncomeCompletionNotice.objects.filter(pk=notice_id).values_list('income_id', flat=True).first()
    with transaction.atomic():
        income = None
        if income_id and IncomeRecord.objects.filter(pk=income_id).exists():
            locked = lock_billing_rows(
                income_ids=[income_id], include_income_children=True,
                include_origin_documents=True,
            )
            income = locked.incomes[income_id]
        notice = IncomeCompletionNotice.objects.select_for_update().filter(pk=notice_id).first()
        if notice is None or notice.status == IncomeCompletionNotice.Status.PROCESSING:
            return None
        if retry_recipient is None and notice.status != IncomeCompletionNotice.Status.PENDING:
            return None
        if retry_recipient and EmailLog.objects.filter(
            template_key=TEMPLATE_KEY, recipient__iexact=retry_recipient,
            status=EmailLog.Status.SENT, metadata__completion_notice_id=notice.pk,
        ).exists():
            return None
        if not needs_collection_account(income):
            notice.status = IncomeCompletionNotice.Status.SKIPPED
            notice.save(update_fields=['status'])
            return None
        notice.status = IncomeCompletionNotice.Status.PROCESSING
        notice.save(update_fields=['status'])
        return notice, income.client_id


def send_completion_notice(notice_id, *, recipients=None, retry_of=None):
    """Send after commit; financial writes never depend on SMTP success."""
    if not AccountingSettings.load().notifications_enabled:
        return False
    recipients = recipients or active_recipient_emails()
    if not recipients:
        logger.warning('No internal recipients for completion notice %s.', notice_id)
        return False
    claimed = _claim_notice(
        notice_id, retry_recipient=retry_of.recipient if retry_of is not None else None,
    )
    if claimed is None:
        return False
    notice, client_id = claimed
    parts = {'subject': '', 'text_body': '', 'html_body': ''}
    error = ''
    sent = False
    try:
        parts = build_completion_email(notice.values)
        email = EmailMultiAlternatives(
            subject=parts['subject'], body=parts['text_body'],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co'),
            to=recipients,
            connection=EmailDeliveryGateway.bounded_connection(timeout_seconds=20),
        )
        email.attach_alternative(parts['html_body'], 'text/html')
        sent = bool(EmailDeliveryGateway.send(
            email, template_key=TEMPLATE_KEY, classification=DeliveryClassification.INTERNAL,
        ))
        if not sent:
            error = 'El servidor de correo no aceptó el aviso.'
    except Exception as exc:
        error = str(exc)
        logger.exception('Completion notice %s failed.', notice_id)
    status = EmailLog.Status.SENT if sent else EmailLog.Status.FAILED
    email_log_service.record_send(
        template_key=TEMPLATE_KEY, recipients=recipients, subject=parts['subject'],
        status=status, error_message=error,
        metadata={**notice.values, 'completion_notice_id': notice.pk},
        targets=[('income', notice.values['income_id'], notice.values['concept'])],
        html_body=parts['html_body'], text_body=parts['text_body'],
        audience=EmailLog.Audience.INTERNAL, client=client_id, retry_of=retry_of,
    )
    IncomeCompletionNotice.objects.filter(pk=notice.pk).update(
        status=IncomeCompletionNotice.Status.SENT if sent else IncomeCompletionNotice.Status.FAILED,
    )
    return sent


def recover_pending_notices():
    if not AccountingSettings.load().notifications_enabled or not active_recipient_emails():
        return 0
    ids = list(IncomeCompletionNotice.objects.filter(
        status=IncomeCompletionNotice.Status.PENDING,
    ).order_by('created_at', 'pk').values_list('pk', flat=True)[:100])
    for notice_id in ids:
        _enqueue(notice_id)
    return len(ids)
