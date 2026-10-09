"""Settling with the client's payment confirmation, through the panel API."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.db import connection

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentType,
    EmailLog,
    IncomeRecord,
)
from content.services import accounting_service
from content.services.income_payment_confirmation_service import TEMPLATE_KEY

User = get_user_model()


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


def billed_income(email='pagos@acme.co'):
    user = User.objects.create_user(
        username='ana@acme.co', email='ana@acme.co',
        first_name='Ana', last_name='Ruiz',
    )
    # update_or_create: under a committed transaction a signal may already
    # have created the profile.
    client, _ = UserProfile.objects.update_or_create(
        user=user, defaults={'role': UserProfile.ROLE_CLIENT},
    )
    project = Project.objects.create(name='Portal Acme', client=user)
    income = IncomeRecord.objects.create(
        concept='Portal Acme - Inicio 40%', kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 7, 1), total_amount=Decimal('1000000.00'),
        gustavo_amount=Decimal('500000.00'), carlos_amount=Decimal('500000.00'),
        client=client, project=project,
    )
    document = Document.objects.create(
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        title='Cuenta de cobro — Portal Acme',
        commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income, client_user=user, project=project,
        public_number='PA-ACME-001', total=income.total_amount,
    )
    DocumentCollectionAccount.objects.create(
        document=document, customer_name='Acme Soluciones',
        customer_email=email,
    )
    return income


def payload(**overrides):
    body = {
        'concept': 'Pago Portal Acme',
        'period_date': '2026-07-15',
        'destination': 'partners',
        'total_amount': '400000.00',
        'send_payment_confirmation': True,
    }
    body.update(overrides)
    return body


def settle(client, income, **overrides):
    return client.post(
        f'/api/accounting/incomes/{income.pk}/settle/',
        payload(**overrides), format='json',
    )


@pytest.mark.django_db
class TestPaymentConfirmationContext:
    def test_names_the_recipient_of_the_issued_account(self, super_client):
        income = billed_income()

        response = super_client.get(
            f'/api/accounting/incomes/{income.pk}/payment-confirmation/',
        )

        assert response.status_code == 200
        assert response.data['can_send'] is True
        assert response.data['recipient'] == 'pagos@acme.co'
        assert response.data['collection_account_number'] == 'PA-ACME-001'

    def test_unknown_income_is_404(self, super_client):
        response = super_client.get(
            '/api/accounting/incomes/99999/payment-confirmation/',
        )

        assert response.status_code == 404

    def test_is_superuser_only(self, admin_client):
        income = billed_income()

        response = admin_client.get(
            f'/api/accounting/incomes/{income.pk}/payment-confirmation/',
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestSettlingWithConfirmation:
    def test_sends_the_confirmation_to_the_account_address(
        self, super_client, mailoutbox,
    ):
        income = billed_income()

        response = settle(super_client, income)

        assert response.status_code == 201, response.data
        assert response.data['payment_confirmation'] == {
            'requested': True, 'status': 'sent',
            'recipient': 'pagos@acme.co', 'error': '',
        }
        assert mailoutbox[-1].to == ['pagos@acme.co']
        assert 'Saldo pendiente: $600.000 COP' in mailoutbox[-1].body

    def test_without_the_flag_nothing_goes_to_the_client(
        self, super_client, mailoutbox,
    ):
        income = billed_income()

        response = settle(super_client, income, send_payment_confirmation=False)

        assert response.status_code == 201
        assert response.data['payment_confirmation']['status'] == 'not_requested'
        assert not EmailLog.objects.filter(template_key=TEMPLATE_KEY).exists()

    def test_a_failed_send_keeps_the_settlement(self, super_client):
        income = billed_income()

        with patch(
            'content.services.email_delivery_service.EmailMessage.send',
            side_effect=OSError('SMTP caído'),
        ):
            response = settle(super_client, income)

        assert response.status_code == 201
        assert response.data['payment_confirmation']['status'] == 'failed'
        assert IncomeRecord.objects.filter(expected_income=income).exists()
        assert EmailLog.objects.get(template_key=TEMPLATE_KEY).status == (
            EmailLog.Status.FAILED
        )

    def test_an_unusable_address_skips_the_email_with_its_reason(
        self, super_client,
    ):
        income = billed_income(email='cliente_9@temp.example.com')

        response = settle(super_client, income)

        assert response.status_code == 201
        assert response.data['payment_confirmation']['status'] == 'skipped'
        assert 'provisional' in response.data['payment_confirmation']['error']
        assert not EmailLog.objects.filter(template_key=TEMPLATE_KEY).exists()

    def test_a_month_only_payment_reads_as_its_month(
        self, super_client, mailoutbox,
    ):
        income = billed_income()

        response = settle(super_client, income, period_date='2026-07')

        assert response.status_code == 201
        assert 'Fecha de pago: julio de 2026' in mailoutbox[-1].body


@pytest.mark.django_db(transaction=True)
def test_the_confirmation_leaves_after_the_settlement_committed(super_client):
    """SMTP must observe the settlement already durable, outside any atomic."""
    income = billed_income()
    observed = {}

    def transport_boundary(*args, **kwargs):
        observed['inside_transaction'] = connection.in_atomic_block
        observed['liquid_saved'] = IncomeRecord.objects.filter(
            expected_income=income, kind=IncomeRecord.Kind.LIQUID,
        ).exists()
        return 1

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=transport_boundary,
    ):
        response = settle(super_client, income)

    assert response.status_code == 201
    assert observed == {'inside_transaction': False, 'liquid_saved': True}
