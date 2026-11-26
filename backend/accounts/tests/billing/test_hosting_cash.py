"""PA-296/298/299. Two panel entry points, one real receipt."""
from datetime import date
from io import BytesIO
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core import mail
from django.db import IntegrityError
from pypdf import PdfReader

from accounts.models import Payment
from accounts.tests.billing.hosting_payment_fixtures import billing, from_hosting, from_incomes, payment_inputs
from content.models import (
    Document, HostingCycle, HostingIncomePeriod, HostingReceipt, HostingReceiptAllocation,
    IncomeRecord, IncomeSettlement, PocketMovement,
)
from content.services.collection_account_snapshot_service import stored_collection_account_pdf
from content.services.hosting_periods import current_summary

pytestmark = pytest.mark.django_db


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


def test_covered_period_exposes_the_existing_client_document(billing):
    client, record, _ = billing
    cycle, _ = payment_inputs(billing, value='233280.00')
    recorded = from_hosting(billing, cycle)
    period = recorded.data['period']
    response = client.post(f'/api/accounting/hostings/{record.pk}/send-collection-account/', {
        'receipt_allocation_id': recorded.data['allocation_id'], 'period_version': period['version'],
        'hosting_payment_id': period['hosting_payment_id'],
    }, format='json')
    assert response.status_code == 201, response.data
    summary = current_summary(record.project_id)
    assert summary['state'] == 'paid' and summary['blocker']
    assert summary['documents'][0]['id'] == response.data['document']['id']


def test_documenting_separate_partial_receipts_preserves_each_amount(billing):
    client, record, _ = billing
    for folio in ('AB7', 'ab7'):
        cycle, _ = payment_inputs(billing, value='50000.00', folio=folio)
        recorded = from_hosting(billing, cycle)
        assert recorded.status_code == 201, recorded.data
        period = recorded.data['period']
        response = client.post(f'/api/accounting/hostings/{record.pk}/send-collection-account/', {
            'receipt_allocation_id': recorded.data['allocation_id'], 'period_version': period['version'],
            'hosting_payment_id': period['hosting_payment_id'],
        }, format='json')
        assert response.status_code == 201, response.data
    assert list(Document.objects.values_list('total', flat=True)) == [Decimal('50000.00')] * 2
    assert current_summary(record.project_id)['balance'] == '133280.00'


def test_explicit_cycle_validity_target_is_independent_of_the_service_dates(billing):
    cycle, _ = payment_inputs(billing, period_from='2026-03-31', period_to='2026-07-08')
    response = from_hosting(billing, cycle)
    assert response.status_code == 201, response.data
    billing[1].refresh_from_db()
    assert billing[1].valid_to == date(2026, 7, 8)
    assert response.data['period']['period_end'] == '2026-06-30'


def test_next_expected_reopened_without_a_reference_uses_the_same_period(billing):
    client, record, _ = billing
    url = f'/api/accounting/hostings/{record.pk}/next-income/'
    review = client.get(url).json()
    response = client.post(url, {'version': review['version']}, format='json')
    assert response.status_code == 201, response.data
    assert client.get(url).json()['existing_income_id'] == response.data['existing_income_id']


def test_rescheduled_shortfall_preserves_contract_price_and_current_balance(billing):
    client, record, income = billing
    _, payment = payment_inputs(billing)
    payment['expected_incomes'] = [{'income_id': income.pk, 'concept': 'Saldo reprogramado',
                                    'period_date': '2026-07-20', 'amount': '50000.00'}]
    result = from_incomes(billing, payment)
    assert result.status_code == 201, result.data
    period = current_summary(record.project_id)
    assert Decimal(period['amount']) == Decimal('233280')
    assert Decimal(period['received']) == Decimal(period['rescheduled']) == Decimal('50000')
    assert Decimal(period['balance']) == Decimal('133280')
    proposal = client.get(f'/api/accounting/hostings/{record.pk}/next-income/').json()
    assert proposal['existing_income_id'] is None


def test_two_real_instalments_close_the_original_obligation(billing):
    client, record, income = billing
    first, _ = payment_inputs(billing, value='100000.00', folio='DEP-1', advance_validity=False)
    posted = from_hosting(billing, first)
    assert posted.status_code == 201, posted.data
    assert Decimal(posted.data['period']['balance']) == Decimal('133280.00')
    _, second = payment_inputs(billing, value='133280.00', folio='DEP-2')
    second['period_date'] = '2026-05-25'
    result = from_incomes(billing, second)
    assert result.status_code == 201, result.data
    record.refresh_from_db()
    assert record.total_paid == Decimal('233280') and record.cycles_count == 2
    assert current_summary(record.project_id)['state'] == 'paid'
    assert set(income.liquid_records.values_list('period_date', flat=True)) == {date(2026, 5, 17), date(2026, 5, 25)}


def test_november_obligation_is_shared_by_the_two_admin_reads(billing, monkeypatch):
    from content.services import hosting_periods
    monkeypatch.setattr(hosting_periods, 'today_bogota', lambda: date(2026, 11, 26))
    client, record, _ = billing
    subscription = record.project.hosting_subscription
    for start, end, state in [(date(2026, 8, 1), date(2026, 10, 31), 'paid'),
                              (date(2026, 11, 1), date(2027, 1, 31), 'pending')]:
        Payment.objects.create(subscription=subscription, amount=233280, status=state,
                               billing_period_start=start, billing_period_end=end, due_date=start)
    income = IncomeRecord.objects.create(project=record.project, client=record.client, kind='expected',
        origin='hosting', concept='Hosting trimestral', period_start=date(2026, 11, 1), period_end=date(2027, 1, 31),
        period_date=date(2026, 11, 8), period_cadence='quarterly', total_amount=233280)
    project = client.get(f'/api/admin/billing-context/projects/{record.project_id}/hosting/').json()['billing_period']
    options = client.get(f'/api/accounting/hostings/{record.pk}/cycle-receipt/').json()['incomes']
    cycle = next(row for row in options if row['income_id'] == income.pk)
    assert (project['period_start'], project['period_end']) == ('2026-11-01', '2027-01-31')
    assert project['version'] == cycle['version']
    assert Decimal(project['balance']) == Decimal('233280.00')


def two_period_distribution(billing):
    _, record, first = billing
    second = IncomeRecord.objects.create(
        project=record.project, client=record.client, kind='expected', origin='hosting',
        concept='Segundo trimestre facturado', period_start=date(2026, 7, 1),
        period_end=date(2026, 9, 30), period_date=date(2026, 7, 5),
        period_cadence='quarterly', total_amount=233280,
    )
    HostingIncomePeriod.objects.create(
        hosting_id=current_summary(record.project_id)['project_hosting_id'], income=second,
        start=second.period_start, end=second.period_end,
    )
    _, data = payment_inputs(billing, '100000.00', 'ABONO-DOS-PERIODOS')
    data['income_ids'].append(second.pk)
    data['allocations'] = [
        {'income_id': first.pk, 'amount': '65000.00'}, {'income_id': second.pk, 'amount': '35000.00'},
    ]
    data['hosting_receipt']['entries'].append({'income_id': second.pk, 'hosting_record_id': record.pk})
    return data


def test_one_transfer_keeps_its_two_allocations_on_an_independent_retry(billing):
    """Un segundo intento devuelve el reparto original de un único abono."""
    data = two_period_distribution(billing)
    first = from_incomes(billing, data)
    assert first.status_code == 201, first.data
    repeated = from_incomes(billing, {**data, 'request_id': str(uuid4())})
    assert repeated.status_code == 201, repeated.data
    assert first.data['settlement_id'] == repeated.data['settlement_id']
    assert PocketMovement.objects.get().amount == Decimal('100000.00')
    allocated = HostingReceiptAllocation.objects.values_list('period__income_id', 'liquid__total_amount')
    assert dict(allocated) == {row['income_id']: Decimal(row['amount']) for row in data['allocations']}
    assert HostingReceipt.objects.count() == 1 and HostingCycle.objects.count() == 2


def test_correcting_the_distribution_preserves_the_receipt_identity(billing):
    """Corregir un reparto entre períodos conserva el abono y su identidad original."""
    client, record, _ = billing
    data = two_period_distribution(billing)
    first = from_incomes(billing, data)
    assert first.status_code == 201, first.data
    identity = HostingReceipt.objects.get().pk
    amounts = ['60000.00', '40000.00']
    revised = [{**row, 'amount': amount} for row, amount in zip(data['allocations'], amounts)]
    response = client.patch(f"/api/accounting/income-settlements/{first.data['settlement_id']}/",
                            {**data, 'revision': 1, 'allocations': revised}, format='json')
    assert response.status_code == 200, response.data
    receipt = HostingReceipt.objects.get()
    assert receipt.pk == identity and receipt.allocations.count() == 2
    assert sorted(receipt.allocations.values_list('liquid__total_amount', flat=True)) == sorted(map(Decimal, amounts))
    record.refresh_from_db()
    assert record.total_paid == PocketMovement.objects.get().amount == Decimal('100000')
    assert record.valid_to == date(2026, 3, 31)


def test_failure_on_second_period_rolls_back_the_entire_transfer(billing, monkeypatch):
    """Un fallo de escritura deja ambos períodos y el bolsillo como estaban."""
    data = two_period_distribution(billing)
    manager = HostingReceiptAllocation.objects
    persist = manager.create
    second = data['income_ids'][1]

    def fail_second_allocation(**values):
        if values['liquid'].expected_income_id == second:
            raise IntegrityError('Synthetic second-period write failure')
        return persist(**values)

    monkeypatch.setattr(manager, 'create', fail_second_allocation)
    with pytest.raises(IntegrityError, match='Synthetic second-period write failure'):
        from_incomes(billing, data)
    assert not HostingReceipt.objects.exists()
    assert not HostingCycle.objects.exists()
    assert not PocketMovement.objects.exists()
    assert not IncomeRecord.objects.filter(kind='liquid').exists()
    billing[1].refresh_from_db()
    assert billing[1].total_paid == 0


def pdf_text(binary):
    return ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(binary)).pages).split())


def assert_customer_document(response, record, income):
    document = Document.objects.get(pk=response.data['document']['id'])
    line = document.items.get()
    assert (line.period_start, line.period_end) == (income.period_start, income.period_end)
    dates = f'{line.period_start:%d/%m/%Y} a {line.period_end:%d/%m/%Y}'
    pdf = stored_collection_account_pdf(document, allow_legacy=False)
    assert dates in pdf_text(pdf)
    message, = [m for m in mail.outbox if m.to == [record.billing_email] and document.public_number in m.subject]
    assert dates in message.body
    attachment, = [part for part in message.attachments if part.mimetype == 'application/pdf']
    assert attachment.content == pdf


def test_income_customer_pdf_matches_the_reviewed_service_dates(billing):
    """El PDF previsualizado en Ingresos conserva sus fechas al archivarse y enviarse."""
    client, record, income = billing
    period = current_summary(record.project_id)
    payload = {'period_version': period['version'], 'hosting_payment_id': period['hosting_payment_id'],
               'billing_nature': 'hosting', 'project_hosting_id': period['project_hosting_id'],
               'client_profile_id': income.client_id, 'income_record_id': income.pk,
               'items': [{'description': 'Servicio DEV', 'quantity': 1, 'unit_price': '233280.00'}]}
    preview = client.post('/api/accounting/collection-accounts/preview/', payload, format='json')
    assert preview.status_code == 200, preview.data
    assert '01/04/2026 a 30/06/2026' in pdf_text(client.get(preview.data['pdf_url']).content)
    assert not Document.objects.exists()
    issued = client.post('/api/accounting/collection-accounts/create/', payload, format='json')
    assert issued.status_code == 201, issued.data
    assert_customer_document(issued, record, income)


def test_hosting_customer_pdf_matches_the_reviewed_service_dates(billing):
    """Hostings envía al titular la copia archivada del período que acaba de revisar."""
    client, record, income = billing
    period = current_summary(record.project_id)
    context = {'period_version': period['version'], 'hosting_payment_id': period['hosting_payment_id']}
    result = client.post(f'/api/accounting/hostings/{record.pk}/send-collection-account/', context, format='json')
    assert result.status_code == 201, result.data
    assert_customer_document(result, record, income)


def test_stale_period_review_preserves_the_updated_balance(billing):
    """Un abono entre revisión y emisión invalida la cuenta por el total anterior."""
    client, record, _ = billing
    reviewed = current_summary(record.project_id)
    payment, _ = payment_inputs(billing)
    assert from_hosting(billing, payment).status_code == 201
    response = client.post(f'/api/accounting/hostings/{record.pk}/send-collection-account/', {
        'period_version': reviewed['version'], 'hosting_payment_id': reviewed['hosting_payment_id'],
    }, format='json')
    assert response.status_code == 400
    assert 'cambió' in str(response.data)
    assert not Document.objects.exists()
    assert Decimal(current_summary(record.project_id)['balance']) == Decimal('183280')


def test_next_quarter_starts_after_the_inclusive_january_end(billing):
    """El trimestre noviembre–enero prepara febrero–abril incluso con vigencia posterior."""
    client, record, income = billing
    subscription = record.project.hosting_subscription
    subscription.start_date = date(2026, 8, 1)
    subscription.save(update_fields=['start_date'])
    start, end = date(2026, 11, 1), date(2027, 1, 31)
    Payment.objects.filter(subscription=subscription).update(
        billing_period_start=start, billing_period_end=end, due_date=start,
    )
    IncomeRecord.objects.filter(pk=income.pk).update(period_start=start, period_end=end, period_date=start)
    record.valid_to = date(2027, 4, 18)
    record.save(update_fields=['valid_to'])
    response = client.get(f'/api/accounting/hostings/{record.pk}/next-income/', {'reference_income_id': income.pk})
    assert response.status_code == 200, response.data
    fields = response.json()['fields']
    assert (fields['period_start'], fields['period_end']) == ('2027-02-01', '2027-04-30')
    assert not HostingIncomePeriod.objects.exists()
