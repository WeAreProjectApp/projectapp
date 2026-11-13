"""PA-259: reading an income exposes its account state without issuing it."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import Document, DocumentType, IncomeRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def collection_income():
    return IncomeRecord.objects.create(
        concept='Servicio ficticio PA-259', kind=IncomeRecord.Kind.EXPECTED,
        period_date=date(2026, 11, 8), total_amount=Decimal('119000.00'),
        gustavo_amount=Decimal('59500.00'), carlos_amount=Decimal('59500.00'),
    )


@pytest.mark.parametrize(('status', 'number'), [
    ('draft', ''), ('issued', 'PA-FICT-259'), ('paid', 'PA-FICT-260'),
])
def test_detail_exposes_commercial_status_without_changing_the_account(
    super_client, collection_income, status, number,
):
    document_type, _ = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )
    account = Document.objects.create(
        title='Cuenta ficticia PA-259', document_type=document_type,
        income_record=collection_income, commercial_status=status,
        public_number=number, issue_date=date(2026, 11, 8), total=Decimal('119000.00'),
    )
    baseline = (account.commercial_status, account.public_number, account.issue_date, account.updated_at)

    response = super_client.get(f'/api/accounting/incomes/{collection_income.pk}/detail/')

    assert response.status_code == 200
    assert response.data['collection_account']['id'] == account.pk
    assert response.data['collection_account']['commercial_status'] == status
    assert response.data['collection_account']['public_number'] == number
    assert str(response.data['collection_account']['issue_date']) == '2026-11-08'
    account.refresh_from_db()
    assert (account.commercial_status, account.public_number, account.issue_date, account.updated_at) == baseline


def test_detail_returns_no_account_for_an_income_without_one(super_client, collection_income):
    response = super_client.get(f'/api/accounting/incomes/{collection_income.pk}/detail/')

    assert response.status_code == 200
    assert response.data['collection_account'] is None
