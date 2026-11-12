"""Payment-confirmation delivery through the collection account workflow."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

from accounts.models import UserProfile
from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentType,
    EmailLog,
    IncomeRecord,
)
from content.services import accounting_service


pytestmark = pytest.mark.django_db

User = get_user_model()
BULK_SETTLE_URL = '/api/accounting/incomes/bulk-settle/'


@pytest.fixture(autouse=True)
def mute_accounting_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


def issued_income(*, suffix, amount, recipient):
    user = User.objects.create_user(
        username=f'client-{suffix}@example.com',
        email=f'client-{suffix}@example.com',
        first_name='Ana',
        last_name=f'Cliente {suffix}',
    )
    client, _ = UserProfile.objects.update_or_create(user=user, defaults={'role': UserProfile.ROLE_CLIENT})
    income = IncomeRecord.objects.create(
        concept=f'Servicio {suffix}',
        kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 7, suffix),
        total_amount=amount,
        gustavo_amount=amount / 2,
        carlos_amount=amount / 2,
        client=client,
    )
    document = Document.objects.create(
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        title=f'Cuenta {suffix}',
        commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income,
        client_user=user,
        public_number=f'PA-EMAIL-{suffix:03d}',
        total=amount,
    )
    DocumentCollectionAccount.objects.create(
        document=document,
        customer_name='Cliente',
        customer_email=recipient,
    )
    return income


def test_bulk_settlement_delivers_each_confirmation_to_its_issued_account(
    super_client, settings,
):
    """Falla si dos liquidaciones confirman sólo una cuenta o cruzan sus direcciones."""
    first = issued_income(
        suffix=1, amount=Decimal('100.00'), recipient='billing-one@example.com',
    )
    second = issued_income(
        suffix=2, amount=Decimal('200.00'), recipient='billing-two@example.com',
    )

    settings.MAILERS = {'default': {
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'OPTIONS': {'host': 'smtp.example.test', 'port': 2525},
    }}
    with patch.object(SmtpBackend, 'send_messages', autospec=True, return_value=1) as transport:
        settlement = super_client.post(BULK_SETTLE_URL, {
            'income_ids': [first.pk, second.pk],
            'allocations': [
                {'income_id': first.pk, 'amount': '100.00'},
                {'income_id': second.pk, 'amount': '200.00'},
            ],
            'total_amount': '300.00',
            'period_date': '2026-07-15',
            'destination': 'pocket',
            'send_payment_confirmation': True,
            'confirmation_income_ids': [first.pk, second.pk],
        }, format='json')
    history = super_client.get('/api/emails/history/', {'scope': 'all'})

    confirmations = settlement.data['payment_confirmations']
    by_recipient = {row['recipient']: row for row in history.data['results']}
    assert settlement.status_code == 201
    assert [(row['income_id'], row['status'], row['recipient']) for row in confirmations] == [
        (first.pk, 'sent', 'billing-one@example.com'),
        (second.pk, 'sent', 'billing-two@example.com'),
    ]
    assert [call.args[1][0].to for call in transport.call_args_list] == [
        ['billing-one@example.com'], ['billing-two@example.com'],
    ]
    assert by_recipient['billing-one@example.com']['status'] == EmailLog.Status.SENT
    assert by_recipient['billing-two@example.com']['status'] == EmailLog.Status.SENT
