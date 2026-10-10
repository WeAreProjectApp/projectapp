"""Durable internal notices for incomes paid before their collection account."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.models import (
    AccountingSettings,
    Document,
    DocumentType,
    EmailLog,
    IncomeCompletionNotice,
    IncomeRecord,
    NotificationRecipient,
)
from content.services.accounting_email_retry_service import retry_send
from content.services.income_completion_notice_service import (
    recover_pending_notices,
    schedule_completion_notice,
    send_completion_notice,
)

pytestmark = pytest.mark.django_db


def _paid_income(**overrides):
    fields = {
        'concept': 'Entrega fase dos', 'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': date(2026, 10, 1), 'total_amount': Decimal('100.00'),
        'gustavo_amount': Decimal('50.00'), 'carlos_amount': Decimal('50.00'),
    }
    fields.update(overrides)
    income = IncomeRecord.objects.create(
        **fields,
    )
    IncomeRecord.objects.create(
        concept='Pago recibido', kind=IncomeRecord.Kind.LIQUID,
        period_date=date(2026, 10, 2), total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
        expected_income=income,
    )
    return income


@pytest.fixture
def liquid_income():
    return IncomeRecord.objects.create(
        concept='Pago no elegible', kind=IncomeRecord.Kind.LIQUID,
        period_date=date(2026, 10, 1), total_amount=Decimal('100.00'),
    )


@pytest.fixture
def personal_paid_income():
    return _paid_income(ledger='gustavo')


@pytest.fixture
def zero_total_income():
    return IncomeRecord.objects.create(
        concept='Saldo cero', kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 10, 1), total_amount=Decimal('0.00'),
    )


@pytest.fixture
def partially_paid_income():
    income = _paid_income()
    income.liquid_records.update(total_amount=Decimal('50.00'))
    return income


@pytest.fixture
def paid_income_with_issued_account(make_client_profile):
    client = make_client_profile()
    income = _paid_income(client=client)
    account_type = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )[0]
    Document.objects.create(
        title='Cuenta ya emitida', document_type=account_type,
        commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income, client_user=client.user,
    )
    return income


def _pending_notice(income):
    notice = schedule_completion_notice(income, was_paid=False)
    assert notice is not None
    return notice


def _enable_notifications():
    settings = AccountingSettings.load()
    settings.notifications_enabled = True
    settings.save(update_fields=['notifications_enabled'])


@pytest.mark.parametrize('income_fixture', [
    'liquid_income', 'personal_paid_income', 'zero_total_income',
    'partially_paid_income', 'paid_income_with_issued_account',
])
def test_ineligible_income_does_not_create_a_completion_notice(request, income_fixture):
    """Falla si un ingreso fuera de la elegibilidad crea avisos internos de cuenta pendiente."""
    income = request.getfixturevalue(income_fixture)

    notice = schedule_completion_notice(income, was_paid=False)

    assert notice is None
    assert IncomeCompletionNotice.objects.filter(income=income).count() == 0


def test_failed_notice_retries_one_recipient():
    """Falla si un aviso fallido pierde su historial o el reintento vuelve a escribirle a todo el equipo."""
    _enable_notifications()
    NotificationRecipient.objects.create(email='contabilidad@example.test')
    NotificationRecipient.objects.create(email='equipo@example.test')
    notice = _pending_notice(_paid_income())

    with patch(
        'content.services.income_completion_notice_service.EmailDeliveryGateway.send',
        return_value=False,
    ):
        sent = send_completion_notice(notice.pk, recipients=['contabilidad@example.test'])

    failed = EmailLog.objects.get(
        template_key='income_completed_account_pending',
        recipient='contabilidad@example.test', status=EmailLog.Status.FAILED,
    )
    assert sent is False
    assert failed.metadata['completion_notice_id'] == notice.pk
    assert failed.body.text.startswith('Ingreso completo: Entrega fase dos')

    with patch(
        'content.services.income_completion_notice_service.EmailDeliveryGateway.send',
        return_value=True,
    ):
        retry = retry_send(failed)

    assert retry.retry_of_id == failed.pk
    assert retry.recipient == 'contabilidad@example.test'
    assert EmailLog.objects.filter(
        retry_of=failed, recipient='equipo@example.test',
    ).count() == 0
    assert EmailLog.objects.filter(retry_of=failed).count() == 1


def test_successful_notice_records_single_delivery(mailoutbox):
    """Falla si el aviso no atraviesa el gateway inventariado, no guarda su cuerpo o se repite tras enviarse."""
    _enable_notifications()
    NotificationRecipient.objects.create(email='contabilidad@example.test')
    notice = _pending_notice(_paid_income())

    sent = send_completion_notice(notice.pk)
    sent_again = send_completion_notice(notice.pk)

    notice.refresh_from_db()
    log = EmailLog.objects.get(
        template_key='income_completed_account_pending',
        recipient='contabilidad@example.test',
    )
    assert sent is True
    assert sent_again is False
    assert notice.status == notice.Status.SENT
    assert log.status == EmailLog.Status.SENT
    assert log.body.html.lower().startswith('<!doctype html>')
    assert 'Este ingreso quedó pagado al 100%. Se debe crear y emitir su cuenta de cobro' in log.body.text
    assert [message.to for message in mailoutbox] == [['contabilidad@example.test']]


def test_disabled_notifications_keep_a_pending_notice_for_recovery():
    """Falla si apagar los avisos consume el evento y ya no permite recuperarlo después."""
    notice = _pending_notice(_paid_income())

    sent = send_completion_notice(notice.pk)

    notice.refresh_from_db()
    assert sent is False
    assert notice.status == notice.Status.PENDING
    assert EmailLog.objects.filter(template_key='income_completed_account_pending').count() == 0


def test_missing_recipients_keep_a_pending_notice_for_recovery():
    """Falla si no tener destinatarios internos marca como enviado un aviso que nadie recibió."""
    _enable_notifications()
    notice = _pending_notice(_paid_income())

    sent = send_completion_notice(notice.pk)

    notice.refresh_from_db()
    assert sent is False
    assert notice.status == notice.Status.PENDING
    assert EmailLog.objects.filter(template_key='income_completed_account_pending').count() == 0


def test_recovery_enqueues_a_pending_notice_after_notifications_are_enabled(mailoutbox):
    """Falla si un aviso pendiente queda varado después de habilitar el interruptor y sus destinatarios."""
    notice = _pending_notice(_paid_income())
    _enable_notifications()
    NotificationRecipient.objects.create(email='contabilidad@example.test')

    recovered = recover_pending_notices()

    notice.refresh_from_db()
    assert recovered == 1
    assert notice.status == notice.Status.SENT
    assert [message.to for message in mailoutbox] == [['contabilidad@example.test']]
