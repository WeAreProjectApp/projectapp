"""Evidence aliases that make a hosting receipt safe to adopt or reject."""
from datetime import date
from decimal import Decimal

import pytest

from accounts.models import HostingEvidence, HostingEvidenceGroup
from accounts.tests.billing.hosting_payment_fixtures import billing, from_hosting, from_incomes, payment_inputs
from content.models import (
    Document,
    DocumentType,
    HostingCycle,
    HostingIncomePeriod,
    HostingReceiptAllocation,
    IncomeRecord,
    IncomeSettlement,
)


pytestmark = pytest.mark.django_db


def receipt_without_folio(billing, *, value='50000.00'):
    cycle, _ = payment_inputs(billing, value=value)
    cycle['hosting_receipt'].pop('issuer')
    cycle['hosting_receipt'].pop('reference')
    return cycle


def test_reversed_adoption_keeps_the_preexisting_hosting_cycle(billing):
    """Falla si revertir una conciliación borra el ciclo legacy que sólo vinculó."""
    client, record, _ = billing
    cycle = HostingCycle.objects.create(
        hosting_record=record,
        modality='quarterly', amount=Decimal('50000.00'), paid_at=date(2026, 5, 17),
        period_from=date(2026, 4, 1), period_to=date(2026, 6, 30),
    )
    payload = receipt_without_folio(billing)
    payload['hosting_receipt']['entries'][0]['cycle_id'] = cycle.pk

    recorded = from_hosting(billing, payload)
    reversed_response = client.delete(
        f"/api/accounting/income-settlements/{recorded.data['settlement_id']}/",
        {'revision': 1}, format='json',
    )

    assert recorded.status_code == 201, recorded.data
    assert reversed_response.status_code == 200, reversed_response.data
    assert HostingCycle.objects.filter(pk=cycle.pk).exists()
    assert not HostingReceiptAllocation.objects.exists()
    assert not IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).exists()


def test_grouped_legacy_cycle_and_liquid_are_linked_without_new_money(billing):
    """Falla si una prueba documental común crea un segundo abono en vez de enlazar el existente."""
    client, record, income = billing
    cycle = HostingCycle.objects.create(
        hosting_record=record,
        modality='quarterly', amount=Decimal('50000.00'), paid_at=date(2026, 5, 17),
        period_from=date(2026, 4, 1), period_to=date(2026, 6, 30),
    )
    liquid = IncomeRecord.objects.create(
        concept='Abono legacy acreditado', kind=IncomeRecord.Kind.LIQUID,
        origin=IncomeRecord.Origin.HOSTING, project=income.project, client=income.client,
        expected_income=income, period_date=date(2026, 5, 17), total_amount=Decimal('50000.00'),
        destination=IncomeRecord.Destination.POCKET,
    )
    group = HostingEvidenceGroup.objects.create(
        hosting_id=record.project.billing_hosting.pk, label='Recibo legado comprobado',
    )
    document = Document.objects.create(
        title='Soporte del recibo legacy',
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        income_record=liquid, project=record.project, client_user=record.client.user,
    )
    HostingEvidence.objects.create(group=group, cycle=cycle)
    HostingEvidence.objects.create(group=group, document=document)
    payload = receipt_without_folio(billing)
    payload['hosting_receipt']['entries'][0].update(cycle_id=cycle.pk, liquid_id=liquid.pk)

    response = from_hosting(billing, payload)

    liquid.refresh_from_db()
    assert response.status_code == 200, response.data
    assert response.data['already_registered'] is True
    assert IncomeSettlement.objects.count() == 0
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).count() == 1
    assert liquid.hosting_allocation.cycle_id == cycle.pk


def test_selected_cycle_with_multiple_covered_periods_is_rejected(billing):
    """Falla si un ciclo consolidado se usa como identidad de una sola obligación."""
    client, record, _ = billing
    cycle = HostingCycle.objects.create(
        hosting_record=record,
        modality='quarterly', amount=Decimal('50000.00'), paid_at=date(2026, 5, 17),
        period_from=date(2026, 4, 1), period_to=date(2026, 6, 30), cycles_represented=2,
    )
    payload = receipt_without_folio(billing)
    payload['hosting_receipt']['entries'][0]['cycle_id'] = cycle.pk

    response = client.post(
        f'/api/accounting/hostings/{record.pk}/cycle-receipt/?preview=1', payload, format='json',
    )

    assert response.status_code in (400, 409)
    assert HostingCycle.objects.count() == 1
    assert not IncomeSettlement.objects.exists()


def test_selected_liquid_from_another_period_is_rejected(billing):
    """Falla si un abono de otra obligación se imputa al período abierto por coincidencia de importe."""
    client, record, income = billing
    other_income = IncomeRecord.objects.create(
        project=record.project, client=record.client, kind=IncomeRecord.Kind.EXPECTED,
        origin=IncomeRecord.Origin.HOSTING, concept='Hosting posterior',
        period_start=date(2026, 7, 1), period_end=date(2026, 9, 30), period_date=date(2026, 7, 5),
        period_cadence='quarterly', total_amount=Decimal('50000.00'),
    )
    HostingIncomePeriod.objects.create(
        hosting_id=record.project.billing_hosting.pk, income=other_income,
        start=other_income.period_start, end=other_income.period_end,
    )
    liquid = IncomeRecord.objects.create(
        concept='Abono de período posterior', kind=IncomeRecord.Kind.LIQUID,
        origin=IncomeRecord.Origin.HOSTING, project=record.project, client=record.client,
        expected_income=other_income, period_date=date(2026, 5, 17), total_amount=Decimal('50000.00'),
        destination=IncomeRecord.Destination.POCKET,
    )
    payload = receipt_without_folio(billing)
    payload['hosting_receipt']['entries'][0]['liquid_id'] = liquid.pk

    response = client.post(
        f'/api/accounting/hostings/{record.pk}/cycle-receipt/?preview=1', payload, format='json',
    )

    assert response.status_code == 409
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).count() == 1
    assert not HostingReceiptAllocation.objects.exists()


def test_request_id_cannot_be_reused_with_changed_receipt_payload(billing):
    """Falla si un reintento con el mismo UUID puede alterar el comprobante ya contabilizado."""
    client, record, _ = billing
    payload, _ = payment_inputs(billing)
    recorded = from_hosting(billing, payload)
    changed = {**payload, 'notes': 'Referencia corregida después de confirmar'}
    preview = client.post(
        f'/api/accounting/hostings/{record.pk}/cycle-receipt/?preview=1', changed, format='json',
    )
    response = client.post(
        f'/api/accounting/hostings/{record.pk}/cycle-receipt/',
        {**changed, 'preview_hash': preview.data['preview_hash']}, format='json',
    )

    assert recorded.status_code == 201, recorded.data
    assert preview.status_code == 200, preview.data
    assert response.status_code == 409
    assert IncomeSettlement.objects.count() == 1
    assert HostingCycle.objects.get().notes == ''


def test_other_screen_reuses_selected_liquid_alias_without_a_folio(billing):
    """Falla si el mismo pago exige un segundo folio al abrirse desde Ingresos."""
    _, record, income = billing
    cycle, settlement = payment_inputs(billing)
    recorded = from_hosting(billing, cycle)
    liquid = IncomeRecord.objects.get(kind=IncomeRecord.Kind.LIQUID)
    settlement['hosting_receipt'] = {
        'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk, 'liquid_id': liquid.pk}],
    }

    replayed = from_incomes(billing, settlement)

    assert recorded.status_code == 201, recorded.data
    assert replayed.status_code == 201, replayed.data
    assert replayed.data['settlement_id'] == recorded.data['settlement_id']
    assert IncomeSettlement.objects.count() == HostingReceiptAllocation.objects.count() == 1


def test_selected_alias_rejects_a_different_folio(billing):
    """Falla si un alias consumido puede adoptar una segunda referencia estable."""
    client, record, income = billing
    cycle, settlement = payment_inputs(billing)
    recorded = from_hosting(billing, cycle)
    liquid = IncomeRecord.objects.get(kind=IncomeRecord.Kind.LIQUID)
    changed = {
        **settlement,
        'hosting_receipt': {
            'issuer': 'Recibos DEV', 'reference': 'FOLIO-DISTINTO',
            'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk, 'liquid_id': liquid.pk}],
        },
    }

    response = client.post('/api/accounting/incomes/bulk-settle/', changed, format='json')

    assert recorded.status_code == 201, recorded.data
    assert response.status_code == 400
    assert 'referencia ya corresponde' in response.data['error']
    assert IncomeSettlement.objects.count() == 1
    assert HostingCycle.objects.get().amount == Decimal('50000.00')


def test_selected_alias_rejects_a_changed_destination(billing):
    """Falla si el comprobante ya consumido puede cambiar el destino del efectivo."""
    client, record, income = billing
    cycle, settlement = payment_inputs(billing)
    recorded = from_hosting(billing, cycle)
    liquid = IncomeRecord.objects.get(kind=IncomeRecord.Kind.LIQUID)
    changed = {**settlement, 'destination': 'partners', 'hosting_receipt': {
        'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk, 'liquid_id': liquid.pk}],
    }}

    response = client.post('/api/accounting/incomes/bulk-settle/', changed, format='json')

    assert recorded.status_code == 201, recorded.data
    assert response.status_code == 400
    assert 'referencia ya corresponde' in response.data['error']
    assert IncomeSettlement.objects.count() == 1
