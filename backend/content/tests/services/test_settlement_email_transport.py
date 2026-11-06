"""PA-215: real SMTP backends must survive gateway cloning and mail retries."""

from datetime import date
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from smtplib import SMTPException
from threading import RLock
from unittest.mock import patch

import pytest

from content.models import (
    AccountingSettings,
    Document,
    DocumentCollectionAccount,
    EmailCopyRecipient,
    EmailDeliverySnapshot,
    EmailLog,
    IncomeCompletionNotice,
    IncomeRecord,
    NotificationRecipient,
    PocketMovement,
)
from content.services.accounting_email_retry_service import retry_send
from content.services.document_type_utils import get_collection_account_document_type
from content.services.email_delivery_service import (
    EmailDeliveryGateway,
    EmailMultiAlternatives,
    matching_delivery_trace,
)
from content.services.income_completion_notice_service import send_completion_notice
from content.services.income_settlement_confirmation_service import confirm_operation
from content.services.income_settlement_operation_service import settle_incomes

pytestmark = pytest.mark.django_db


@pytest.fixture
def smtp_transport(settings):
    accounting_settings = AccountingSettings.load()
    accounting_settings.notifications_enabled = False
    accounting_settings.save(update_fields=['notifications_enabled'])
    NotificationRecipient.objects.all().delete()
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'OPTIONS': {
                'host': 'smtp.example.test', 'port': 2525,
                'username': '', 'password': '', 'timeout': 60,
            },
        },
    }
    with patch('django.core.mail.backends.smtp.smtplib.SMTP', autospec=True) as smtp:
        smtp.return_value.sendmail.return_value = {}
        yield smtp


def message_with_connection():
    message = EmailMultiAlternatives(
        subject='Liquidación de prueba', body='Texto del pago',
        from_email='team@example.test', to=['cliente@example.test'],
        connection=EmailDeliveryGateway.bounded_connection(timeout_seconds=20),
    )
    message.attach_alternative('<p>Texto del pago</p>', 'text/html')
    message.attach('recibo.txt', b'Pago registrado', 'text/plain')
    return message


def parsed_messages(smtp):
    return [
        BytesParser(policy=policy.default).parsebytes(call.args[2])
        for call in smtp.return_value.sendmail.call_args_list
    ]


def test_smtp_delivery_preserves_hidden_copy_content(smtp_transport):
    EmailCopyRecipient.objects.create(email='auditoria@example.test')
    message = message_with_connection()

    sent = EmailDeliveryGateway.send(message, template_key='income_payment_received_client')

    primary, copied = parsed_messages(smtp_transport)
    assert sent == 1
    assert primary['To'] == 'cliente@example.test'
    assert copied['To'] is None
    assert copied['Cc'] is None
    assert copied['Bcc'] is None
    assert smtp_transport.return_value.sendmail.call_args_list[1].args[1] == ['auditoria@example.test']
    assert primary.get_body(preferencelist=('html',)).get_content() == copied.get_body(preferencelist=('html',)).get_content()
    assert next(primary.iter_attachments()).get_payload(decode=True) == next(copied.iter_attachments()).get_payload(decode=True)
    assert message.to == ['cliente@example.test']
    assert message.bcc == []
    assert EmailDeliverySnapshot.objects.count() == 1
    assert set(EmailLog.objects.values_list('status', flat=True)) == {'sent'}
    assert len(smtp_transport.call_args_list) == 2
    assert smtp_transport.call_args_list[0].kwargs['timeout'] == 20
    assert smtp_transport.call_args_list[1].kwargs['timeout'] == 20


def test_smtp_copy_failure_keeps_other_deliveries_sent(smtp_transport):
    EmailCopyRecipient.objects.create(email='audit-a@example.test')
    EmailCopyRecipient.objects.create(email='audit-b@example.test')
    smtp_transport.return_value.sendmail.side_effect = [{}, SMTPException('Unavailable'), {}]

    sent = EmailDeliveryGateway.send(message_with_connection(), template_key='income_payment_received_client')

    assert sent == 1
    assert list(EmailLog.objects.order_by('recipient').values_list('recipient', 'status')) == [
        ('audit-a@example.test', 'failed'),
        ('audit-b@example.test', 'sent'),
        ('cliente@example.test', 'sent'),
    ]


def test_smtp_copy_keeps_content_from_before_transport(smtp_transport):
    EmailCopyRecipient.objects.create(email='auditoria@example.test')
    message = message_with_connection()

    def mutate_original(*args):
        message.body = 'Contenido alterado por el transporte'
        message.alternatives.clear()
        message.attachments.clear()
        return {}

    smtp_transport.return_value.sendmail.side_effect = mutate_original
    EmailDeliveryGateway.send(message, template_key='income_payment_received_client')

    primary, copied = parsed_messages(smtp_transport)
    assert copied.get_body(preferencelist=('plain',)).get_content() == primary.get_body(preferencelist=('plain',)).get_content()
    assert copied.get_body(preferencelist=('html',)).get_content() == primary.get_body(preferencelist=('html',)).get_content()
    assert next(copied.iter_attachments()).get_payload(decode=True).splitlines() == [b'Pago registrado']
    snapshot = EmailDeliverySnapshot.objects.get()
    assert snapshot.body.text == 'Texto del pago'
    with snapshot.attachments.get().file.open('rb') as retained:
        assert retained.read() == b'Pago registrado\n'


def test_preparation_failure_clears_the_delivery_context(smtp_transport):
    message = message_with_connection()
    message.extra_headers['X-Uncopyable'] = RLock()

    with pytest.raises(TypeError, match='RLock'):
        EmailDeliveryGateway.send(message, template_key='income_payment_received_client')

    assert matching_delivery_trace('income_payment_received_client', message.to) is None
    assert EmailDeliverySnapshot.objects.count() == 0
    smtp_transport.assert_not_called()


def expected_income(**overrides):
    return IncomeRecord.objects.create(**{
        'concept': 'Ingreso PA-215', 'kind': 'expected', 'ledger': 'company',
        'period_date': date(2026, 11, 1), 'total_amount': Decimal('100.00'),
        'gustavo_amount': Decimal('50.00'), 'carlos_amount': Decimal('50.00'),
        **overrides,
    })


def payment(*incomes):
    return {
        'income_ids': [income.pk for income in incomes],
        'total_amount': Decimal('100.00') * len(incomes),
        'period_date': date(2026, 11, 6), 'destination': 'pocket',
    }


def test_completion_notice_retry_preserves_the_payment(smtp_transport, superuser):
    settings = AccountingSettings.load()
    settings.notifications_enabled = True
    settings.save(update_fields=['notifications_enabled'])
    NotificationRecipient.objects.create(email='contabilidad@example.test')
    income = expected_income()
    settle_incomes(payment(income), superuser)
    notice = IncomeCompletionNotice.objects.get(income=income)
    smtp_transport.return_value.sendmail.side_effect = SMTPException('Unavailable')
    assert send_completion_notice(notice.pk) is False
    failed = EmailLog.objects.get(template_key='income_completed_account_pending')

    smtp_transport.return_value.sendmail.side_effect = None
    attempt = retry_send(failed)

    notice.refresh_from_db()
    assert attempt.status == 'sent'
    assert attempt.retry_of_id == failed.pk
    assert notice.status == 'sent'
    assert IncomeCompletionNotice.objects.filter(income=income).count() == 1
    assert IncomeRecord.objects.filter(expected_income=income).count() == 1
    assert PocketMovement.objects.count() == 1
    assert send_completion_notice(notice.pk) is False
    assert smtp_transport.return_value.sendmail.call_count == 2


@pytest.fixture(params=[1, 2], ids=['individual', 'multiple'])
def billed_settlement(request, superuser, make_client_profile):
    client = make_client_profile()
    incomes = [expected_income(client=client) for _ in range(request.param)]
    for income in incomes:
        document = Document.objects.create(
            title='Cuenta PA-215', document_type=get_collection_account_document_type(),
            income_record=income, client_user=client.user,
            commercial_status=Document.CommercialStatus.ISSUED,
            public_number=f'PA-QA-{income.pk}', total=income.total_amount,
        )
        DocumentCollectionAccount.objects.create(
            document=document, customer_name='Cliente QA',
            customer_contact_name='Cliente QA', customer_email='pagos@example.test',
            billing_concept=income.concept,
        )
    data = payment(*incomes)
    data['send_payment_confirmation'] = True
    result = settle_incomes(data, superuser)
    return result, data, request.param


def retry_failed_confirmations():
    return [
        retry_send(log) for log in EmailLog.objects.filter(
            template_key='income_payment_received_client', status='failed',
        ).order_by('pk')
    ]


def test_confirmation_delivers_each_selected_income(smtp_transport, billed_settlement):
    result, data, income_count = billed_settlement

    confirm_operation(result, data)

    assert EmailLog.objects.filter(template_key='income_payment_received_client', status='sent').count() == income_count
    assert smtp_transport.return_value.sendmail.call_count == income_count
    assert IncomeRecord.objects.filter(kind='liquid').count() == income_count
    assert PocketMovement.objects.count() == 1
    assert IncomeCompletionNotice.objects.count() == 0


def test_confirmation_retry_preserves_settlement(smtp_transport, billed_settlement):
    result, data, income_count = billed_settlement
    smtp_transport.return_value.sendmail.side_effect = SMTPException('Unavailable')
    confirm_operation(result, data)

    smtp_transport.return_value.sendmail.side_effect = None
    attempts = retry_failed_confirmations()

    assert len(attempts) == income_count
    assert EmailLog.objects.filter(template_key='income_payment_received_client', status='sent', retry_of__status='failed').count() == income_count
    assert IncomeRecord.objects.filter(kind='liquid').count() == income_count
    assert PocketMovement.objects.count() == 1
    assert IncomeCompletionNotice.objects.count() == 0
    assert smtp_transport.return_value.sendmail.call_count == income_count * 2
