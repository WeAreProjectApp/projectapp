"""Payment confirmation: who receives it, what it says and how it is recorded."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model

from content.models import (
    Document,
    DocumentCollectionAccount,
    EmailLog,
    IncomeRecord,
)
from content.services import accounting_service, accounting_settlement_service
from content.services import income_payment_confirmation_service as service
from content.services.document_type_utils import (
    get_collection_account_document_type,
)
from content.services.income_settlement_policy import MISSING_ACCOUNT_REASON
from content.utils import format_bogota_date

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


def make_client(email='ana@acme.co'):
    user = User.objects.create_user(
        username=email, email=email, first_name='Ana', last_name='Ruiz',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


def make_income(client=None, project=None, total='1000000.00'):
    amount = Decimal(total)
    return IncomeRecord.objects.create(
        concept='Portal Acme - Inicio 40%',
        kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 7, 1),
        total_amount=amount,
        gustavo_amount=amount / 2,
        carlos_amount=amount / 2,
        client=client,
        project=project,
    )


def issue_account(income, *, email='pagos@acme.co', project=None,
                  status=Document.CommercialStatus.ISSUED):
    document = Document.objects.create(
        document_type=get_collection_account_document_type(),
        title='Cuenta de cobro — Portal Acme',
        commercial_status=status,
        income_record=income,
        client_user=income.client.user,
        project=income.project if project is None else project,
        public_number=f'PA-ACME-{Document.objects.count() + 1:03d}',
        total=income.total_amount,
    )
    DocumentCollectionAccount.objects.create(
        document=document,
        customer_name='Acme Soluciones',
        customer_contact_name='Ana Ruiz',
        customer_email=email,
        billing_concept='Portal Acme - Inicio 40%',
    )
    return document


@pytest.fixture
def billed_income():
    client = make_client()
    project = Project.objects.create(name='Portal Acme', client=client.user)
    income = make_income(client=client, project=project)
    issue_account(income)
    return income


def settle(income, user, **overrides):
    data = {
        'concept': 'Pago Portal Acme',
        'period_date': date(2026, 7, 15),
        'destination': IncomeRecord.Destination.PARTNERS,
        'total_amount': Decimal('400000.00'),
        'notes': '',
        'deductions': [],
        'expected_incomes': [],
        'send_payment_confirmation': True,
        'period_date_precision': 'day',
    }
    data.update(overrides)
    result = accounting_settlement_service.settle_expected_income(
        income, data, user,
    )
    return result, data


def values(**overrides):
    base = {
        'income_id': 1,
        'liquid_id': 2,
        'document_id': None,
        'public_number': 'PA-ACME-001',
        'greeting_name': 'Ana Ruiz',
        'concept': 'Pago Portal Acme',
        'project_name': 'Portal Acme',
        'amount': '400000.00',
        'payment_date': '2026-07-15',
        'payment_date_precision': 'day',
        'pending_after': '600000.00',
    }
    base.update(overrides)
    return base


def test_context_names_the_issued_account_address(billed_income):
    context = service.confirmation_context(billed_income)

    assert context['can_send'] is True
    assert context['recipient'] == 'pagos@acme.co'
    assert context['collection_account_number'] == 'PA-ACME-001'
    assert context['project_name'] == 'Portal Acme'
    assert context['greeting_name'] == 'Ana Ruiz'
    assert context['client_name'] == 'Ana Ruiz'


def test_context_without_client_explains_why():
    context = service.confirmation_context(make_income())

    assert context['can_send'] is False
    assert context['blocked_reason'] == service.NO_CLIENT_REASON


def test_context_ignores_cancelled_and_other_project_accounts():
    """Only an account that satisfies the settlement rule names a recipient."""
    client = make_client()
    project = Project.objects.create(name='Portal Acme', client=client.user)
    other = Project.objects.create(name='App Acme', client=client.user)
    income = make_income(client=client, project=project)
    issue_account(income, status=Document.CommercialStatus.CANCELLED)
    issue_account(income, project=other)

    context = service.confirmation_context(income)

    assert context['can_send'] is False
    assert context['blocked_reason'] == MISSING_ACCOUNT_REASON


def test_context_refuses_a_placeholder_address():
    client = make_client()
    income = make_income(client=client)
    issue_account(income, email='cliente_5@temp.example.com')

    context = service.confirmation_context(income)

    assert context['can_send'] is False
    assert 'provisional' in context['blocked_reason']


def test_email_states_the_payment_and_the_pending_balance():
    email = service.build_payment_confirmation_email(values())

    assert email['subject'] == 'Confirmación de pago — Cuenta de cobro PA-ACME-001'
    assert email['greeting'] == 'Hola Ana Ruiz'
    assert 'Valor recibido: $400.000 COP' in email['text_body']
    assert 'Proyecto: Portal Acme' in email['text_body']
    assert 'Saldo pendiente: $600.000 COP' in email['text_body']
    assert '**' not in email['text_body']


def test_email_without_project_and_balance_reads_al_dia():
    email = service.build_payment_confirmation_email(
        values(project_name='', pending_after='0.00'),
    )

    assert 'Proyecto:' not in email['text_body']
    assert 'Saldo pendiente' not in email['text_body']
    assert 'quedaste al día' in email['text_body']


def test_payment_date_keeps_the_precision_the_operator_chose():
    """A month-only period is stored as day 1, which is also an exact date."""
    first = date(2026, 7, 1)

    assert service.payment_date_label(first, 'month') == 'julio de 2026'
    assert service.payment_date_label(first, 'day') == format_bogota_date(first)
    month_email = service.build_payment_confirmation_email(
        values(payment_date='2026-07-01', payment_date_precision='month'),
    )
    assert 'Fecha de pago: julio de 2026' in month_email['text_body']


def test_send_records_a_client_row_with_targets(billed_income, superuser, mailoutbox):
    result, data = settle(billed_income, superuser)
    context = service.confirmation_context(billed_income)
    facts = service.settlement_values(billed_income, result['liquid'], data, context)

    assert service.send_payment_confirmation_email(
        facts, recipient='pagos@acme.co', client=billed_income.client,
    ) is True

    log = EmailLog.objects.get(template_key=service.TEMPLATE_KEY)
    assert (log.status, log.audience) == (EmailLog.Status.SENT, EmailLog.Audience.CLIENT)
    assert log.client_id == billed_income.client_id
    assert service.values_from_metadata(log.metadata) == facts
    assert set(log.targets.values_list('entity_type', 'object_id')) == {
        ('income', billed_income.pk), ('income', result['liquid'].pk),
        ('collection_account', context['collection_account_id']),
    }
    assert (mailoutbox[0].to, mailoutbox[0].attachments) == (['pagos@acme.co'], [])


def test_send_failure_records_a_failed_row(mailoutbox):
    with patch.object(
        service.EmailDeliveryGateway, 'send', side_effect=OSError('SMTP caído'),
    ):
        sent = service.send_payment_confirmation_email(
            values(), recipient='pagos@acme.co',
        )

    assert sent is False
    log = EmailLog.objects.get(template_key=service.TEMPLATE_KEY)
    assert log.status == EmailLog.Status.FAILED
    assert 'SMTP caído' in log.error_message
    assert mailoutbox == []


def test_confirm_settlement_sends_after_the_settlement(billed_income, superuser, mailoutbox):
    result, data = settle(billed_income, superuser)

    block = service.confirm_settlement(result, data)

    assert block == {
        'requested': True, 'status': 'sent',
        'recipient': 'pagos@acme.co', 'error': '',
    }
    assert 'Saldo pendiente: $600.000 COP' in mailoutbox[0].body


def test_confirm_settlement_without_the_flag_sends_nothing(billed_income, superuser):
    result, data = settle(billed_income, superuser, send_payment_confirmation=False)

    block = service.confirm_settlement(result, data)

    assert block['status'] == 'not_requested'
    assert block['requested'] is False
    assert not EmailLog.objects.filter(template_key=service.TEMPLATE_KEY).exists()


def test_residual_only_settlement_is_skipped(billed_income):
    block = service.confirm_settlement(
        {'income': billed_income, 'liquid': None},
        {'send_payment_confirmation': True},
    )

    assert block['status'] == 'skipped'
    assert block['error'] == service.NO_AMOUNT_REASON


def test_an_unexpected_error_is_reported_not_raised(billed_income, superuser):
    result, data = settle(billed_income, superuser)

    with patch.object(
        service, 'build_payment_confirmation_email', side_effect=KeyError('x'),
    ):
        block = service.confirm_settlement(result, data)

    assert block['status'] == 'skipped'
    assert block['error'] == service.UNEXPECTED_REASON
    assert IncomeRecord.objects.filter(expected_income=billed_income).exists()


def test_pending_after_still_counts_an_earlier_follow_up(billed_income, superuser):
    """A rescheduled installment is still owed, so the client is not 'al día'."""
    settle(
        billed_income, superuser,
        total_amount=Decimal('300000.00'),
        expected_incomes=[{
            'concept': 'Portal Acme - Saldo', 'period_date': date(2026, 9, 1),
            'amount': Decimal('300000.00'),
        }],
    )
    billed_income.refresh_from_db()
    result, data = settle(billed_income, superuser)
    context = service.confirmation_context(billed_income)

    facts = service.settlement_values(billed_income, result['liquid'], data, context)

    assert facts['pending_after'] == '300000.00'


def test_schedule_waits_for_the_commit(
    billed_income, superuser, mailoutbox, django_capture_on_commit_callbacks,
):
    result, data = settle(billed_income, superuser)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        block = service.schedule_confirmation(result, data)

    assert block['status'] == 'scheduled'
    assert mailoutbox == []
    callbacks[0]()
    assert len(mailoutbox) == 1


def test_preview_estimates_without_writing(billed_income):
    data = {
        'concept': 'Pago Portal Acme', 'period_date': date(2026, 7, 15),
        'total_amount': Decimal('400000.00'),
        'deductions': [{'type': 'gateway_fee', 'amount': Decimal('8000.00')}],
    }

    preview = service.preview_confirmation(billed_income, data)

    assert preview['recipient'] == 'pagos@acme.co'
    assert preview['pending_after'] == '592000.00'
    assert 'Saldo pendiente: $592.000 COP' in preview['text_body']
    assert not IncomeRecord.objects.filter(expected_income=billed_income).exists()
