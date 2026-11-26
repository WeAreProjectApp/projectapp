"""PA-296/298/299. Two panel entry points, one real receipt."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core import mail

from accounts.models import Payment
from accounts.services.hosting_context import reconcile_hosting
from content.models import Document, HostingCycle, HostingIncomePeriod, HostingReceiptAllocation, IncomeRecord, IncomeSettlement, PocketMovement
from content.services.hosting_periods import current_summary

pytestmark = pytest.mark.django_db


@pytest.fixture
def billing(api_client, admin_user, hosting_record, subscription):
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    api_client.force_authenticate(admin_user)
    reconcile_hosting(hosting_record.project_id, admin_user, {
        'expected_version': 0, 'reason': 'Fixture de cobros', 'subscription_id': subscription.pk,
        'hosting_record_ids': [hosting_record.pk], 'operational_record_id': hosting_record.pk,
    })
    payment = Payment.objects.create(subscription=subscription, amount=233280, status='pending',
                                     billing_period_start=date(2026, 4, 1), billing_period_end=date(2026, 6, 30),
                                     due_date=date(2026, 4, 5))
    income = IncomeRecord.objects.create(project=hosting_record.project, client=hosting_record.client, kind='expected',
                                         concept='Hosting de prueba', origin='hosting', period_start=payment.billing_period_start,
                                         period_end=payment.billing_period_end, period_cadence='quarterly',
                                         period_date=payment.due_date, total_amount=payment.amount)
    return api_client, hosting_record, income


def payment_inputs(billing, value='50000.00', folio='A', **cycle_options):
    client, record, income = billing
    identity = {'issuer': 'Recibos DEV', 'reference': folio,
                'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk}]}
    shared = {'destination': 'pocket', 'hosting_receipt': identity}
    cycle = {**shared, 'request_id': str(uuid4()), 'amount': value, 'income_id': income.pk,
             'paid_at': '2026-05-17', **cycle_options}
    settlement = {**shared, 'request_id': str(uuid4()), 'total_amount': value,
                  'income_ids': [income.pk], 'period_date': '2026-05-17'}
    return cycle, settlement


def from_hosting(billing, payload):
    client, record, _ = billing
    url = f'/api/accounting/hostings/{record.pk}/cycle-receipt/'
    preview = client.post(url + '?preview=1', payload, format='json')
    assert preview.status_code == 200, preview.data
    return client.post(url, {**payload, 'preview_hash': preview.data['preview_hash']}, format='json')


def from_incomes(billing, payload):
    client, _, _ = billing
    return client.post('/api/accounting/incomes/bulk-settle/', payload, format='json')


@pytest.mark.parametrize('amount', ['50000.00', '233280.00'])
def test_independent_income_attempt_reuses_hosting_cash(billing, amount):
    cycle, settlement = payment_inputs(billing, amount)
    first = from_hosting(billing, cycle)
    assert first.status_code == 201, first.data
    second = from_incomes(billing, settlement)
    assert second.status_code == 201, second.data
    assert second.data['settlement_id'] == first.data['settlement_id']
    assert IncomeSettlement.objects.count() == HostingReceiptAllocation.objects.count() == HostingCycle.objects.count() == 1
    assert PocketMovement.objects.count() == IncomeRecord.objects.filter(kind='liquid').count() == 1
    assert second.data['payment_confirmations'] == []


def test_independent_hosting_attempt_reuses_income_cash(billing):
    cycle, settlement = payment_inputs(billing, '233280.00')
    first = from_incomes(billing, settlement)
    assert first.status_code == 201, first.data
    second = from_hosting(billing, cycle)
    assert second.status_code == 200, second.data
    assert second.data['settlement_id'] == first.data['settlement_id']
    billing[1].refresh_from_db()
    assert billing[1].valid_to == date(2026, 3, 31)
    assert HostingCycle.objects.count() == 1


def test_equal_transfers_with_distinct_folios_both_credit_the_period(billing):
    cycle, _ = payment_inputs(billing)
    _, different = payment_inputs(billing, folio='B')
    assert from_hosting(billing, cycle).status_code == 201
    result = from_incomes(billing, different)
    assert result.status_code == 201, result.data
    period = current_summary(billing[1].project_id)
    assert Decimal(period['balance']) == Decimal('133280')
    assert HostingReceiptAllocation.objects.count() == 2


@pytest.mark.parametrize(('options', 'target'), [({}, date(2026, 6, 30)), ({'advance_validity': False}, date(2026, 3, 31))])
def test_partial_receipt_respects_validity_choice(billing, options, target):
    cycle, _ = payment_inputs(billing, **options)
    response = from_hosting(billing, cycle)
    assert response.status_code == 201, response.data
    billing[1].refresh_from_db()
    assert billing[1].valid_to == target
    assert billing[1].total_paid == Decimal('50000.00')


def test_missing_evidence_refuses_scoped_settlement(billing):
    _, payload = payment_inputs(billing)
    del payload['hosting_receipt']
    response = from_incomes(billing, payload)
    assert response.status_code == 400
    assert IncomeSettlement.objects.count() == 0


def test_incompatible_second_distribution_preserves_cash(billing):
    cycle, settlement = payment_inputs(billing)
    assert from_hosting(billing, cycle).status_code == 201
    response = from_incomes(billing, {**settlement, 'total_amount': '49999.00'})
    assert response.status_code in (400, 409)
    assert HostingCycle.objects.get().amount == Decimal('50000.00')


def test_reverse_removes_only_the_settlement_cash_projection(billing):
    client, record, _ = billing
    cycle, _ = payment_inputs(billing)
    result = from_hosting(billing, cycle)
    response = client.delete(f"/api/accounting/income-settlements/{result.data['settlement_id']}/",
                             {'revision': 1}, format='json')
    assert response.status_code == 200, response.data
    record.refresh_from_db()
    assert record.total_paid == 0
    assert record.valid_to == date(2026, 6, 30)
    assert HostingCycle.objects.count() == PocketMovement.objects.count() == 0


def test_next_expected_income_is_idempotent(billing):
    client, record, income = billing
    url = f'/api/accounting/hostings/{record.pk}/next-income/'
    proposal = client.get(url, {'reference_income_id': income.pk})
    assert proposal.status_code == 200, proposal.data
    assert proposal.json()['fields']['period_start'] == '2026-07-01'
    assert proposal.json()['fields']['period_end'] == '2026-09-30'
    payload = {'version': proposal.data['version'], 'reference_income_id': income.pk}
    first = client.post(url, payload, format='json')
    assert first.status_code == 201, first.data
    second = client.post(url, payload, format='json')
    assert second.status_code == 200, second.data
    assert first.data['existing_income_id'] == second.data['existing_income_id']
    assert HostingIncomePeriod.objects.get().income_id == first.data['existing_income_id']


def test_unlinked_overlapping_cycle_blocks_emission(billing):
    _, record, _ = billing
    HostingCycle.objects.create(hosting_record=record, amount=100000, paid_at=date(2026, 3, 31), modality='quarterly',
                                period_from=date(2026, 3, 28), period_to=date(2026, 6, 27))
    assert current_summary(record.project_id)['state'] == 'blocked'
    assert Document.objects.count() == 0


def test_paid_receipt_document_is_explicit(billing):
    client, record, _ = billing
    cycle, _ = payment_inputs(billing)
    recorded = from_hosting(billing, cycle)
    assert recorded.status_code == 201, recorded.data
    assert Document.objects.count() == 0
    period = recorded.data['period']
    payload = {'receipt_allocation_id': recorded.data['allocation_id'], 'period_version': period['version'],
               'hosting_payment_id': period['hosting_payment_id']}
    url = f'/api/accounting/hostings/{record.pk}/send-collection-account/'
    sent = client.post(url, payload, format='json')
    assert sent.status_code == 201, sent.data
    document = Document.objects.get()
    assert document.commercial_status == 'paid'
    assert document.total == Decimal('50000')
    assert client.post(url, payload, format='json').status_code == 400
    assert len([m for m in mail.outbox if m.to == [record.billing_email] and document.public_number in m.subject]) == 1
