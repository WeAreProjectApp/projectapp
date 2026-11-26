"""Authorization and receipt-evidence boundaries for the hosting payment panel."""
from datetime import date
from uuid import uuid4

import pytest
from django.core import mail
from rest_framework.test import APIClient

from accounts.models import Project, ProjectHosting
from accounts.services.hosting_context import reconcile_hosting
from content.models import (
    Document,
    HostingCycle,
    HostingIncomePeriod,
    HostingRecord,
    IncomeRecord,
    IncomeSettlement,
    IssuerProfile,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def hosted_period(make_client_profile, superuser):
    client = make_client_profile('Contrato de prueba')
    project = Project.objects.create(name='Sitio de prueba', client=client.user)
    record = HostingRecord.objects.create(
        project=project,
        client=client,
        client_name='Contrato de prueba',
        monthly_value='50000.00',
        payment_per_cycle='50000.00',
        payment_modality='monthly',
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 1, 31),
    )
    reconciliation = reconcile_hosting(project.pk, superuser, {
        'expected_version': 0,
        'reason': 'Fixture del contrato de pago de hosting.',
        'hosting_record_ids': [record.pk],
        'operational_record_id': record.pk,
    })
    income = IncomeRecord.objects.create(
        project=project,
        client=client,
        kind=IncomeRecord.Kind.EXPECTED,
        origin=IncomeRecord.Origin.HOSTING,
        concept='Hosting enero',
        period_date=date(2026, 1, 1),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        period_cadence='monthly',
        total_amount='50000.00',
    )
    HostingIncomePeriod.objects.create(
        hosting=ProjectHosting.objects.get(pk=reconciliation['id']),
        income=income,
        start=income.period_start,
        end=income.period_end,
    )
    return record, income


def receipt_payload(record, income, **receipt):
    return {
        'income_id': income.pk,
        'amount': '50000.00',
        'paid_at': '2026-01-31',
        'request_id': str(uuid4()),
        'hosting_receipt': {
            'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk}],
            **receipt,
        },
    }


def record_receipt(super_client, record, payload):
    url = f'/api/accounting/hostings/{record.pk}/cycle-receipt/'
    preview = super_client.post(f'{url}?preview=1', payload, format='json')
    assert preview.status_code == 200, preview.data
    return super_client.post(url, {**payload, 'preview_hash': preview.data['preview_hash']}, format='json')


@pytest.mark.parametrize('suffix', ('cycle-receipt/', 'next-income/'))
def test_hosting_payment_endpoints_reject_anonymous_and_staff_users(
    api_client, admin_user, hosted_period, suffix,
):
    """Falla si alguien sin rol de superusuario puede consultar pagos o ingresos de hosting."""
    record, _ = hosted_period
    url = f'/api/accounting/hostings/{record.pk}/{suffix}'
    staff_client = APIClient()
    staff_client.force_authenticate(admin_user)

    anonymous = api_client.get(url)
    staff = staff_client.get(url)

    assert anonymous.status_code == 403
    assert staff.status_code == 403


def test_superuser_gets_the_same_period_from_each_hosting_payment_entry(
    super_client, hosted_period,
):
    """Falla si Hostings no expone el período vinculado que la confirmación siguiente necesita."""
    record, income = hosted_period

    receipt = super_client.get(f'/api/accounting/hostings/{record.pk}/cycle-receipt/')
    next_income = super_client.get(
        f'/api/accounting/hostings/{record.pk}/next-income/',
        {'reference_income_id': income.pk},
    )

    assert receipt.status_code == 200, receipt.data
    assert receipt.data['incomes'][0]['start'] == '2026-01-01'
    assert receipt.data['incomes'][0]['end'] == '2026-01-31'
    assert next_income.status_code == 200, next_income.data
    assert next_income.data['fields']['period_start'] == '2026-02-01'
    assert next_income.data['fields']['period_end'] == '2026-02-28'


def test_cycle_receipt_requires_stable_identity_before_creating_cash(
    super_client, hosted_period,
):
    """Falla si un abono manual sin folio ni asiento puede crear dinero imposible de conciliar."""
    record, income = hosted_period

    response = super_client.post(
        f'/api/accounting/hostings/{record.pk}/cycle-receipt/',
        {
            'income_id': income.pk,
            'amount': '50000.00',
            'paid_at': '2026-01-31',
            'request_id': str(uuid4()),
            'hosting_receipt': {
                'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk}],
            },
        },
        format='json',
    )

    assert response.status_code == 400
    assert 'hosting_receipt' in response.data
    assert HostingCycle.objects.count() == 0
    assert IncomeSettlement.objects.count() == 0


def test_paid_document_uses_reconciled_period_in_its_line_and_multipart_email(
    super_client, hosted_period,
):
    """Falla si documentar un pago acreditado cambia su período o pierde el detalle del correo."""
    record, income = hosted_period
    issuer = IssuerProfile.objects.create(
        name='ProjectApp pruebas', legal_name='ProjectApp pruebas SAS',
        identification_number='900123456', email='issuer@example.test',
        public_number_prefix='PA',
    )
    recorded = record_receipt(
        super_client, record, receipt_payload(record, income, issuer='Banco de prueba', reference='FOLIO-1'),
    )
    assert recorded.status_code == 201, recorded.data

    response = super_client.post(
        f'/api/accounting/hostings/{record.pk}/send-collection-account/',
        {
            'receipt_allocation_id': recorded.data['allocation_id'],
            'period_version': recorded.data['period']['version'],
            'hosting_payment_id': recorded.data['period']['hosting_payment_id'],
        },
        format='json',
    )

    assert response.status_code == 201, response.data
    document = Document.objects.get(pk=response.data['document']['id'])
    item = document.items.get()
    message = next(entry for entry in mail.outbox if entry.to == ['client1@example.com'])
    mime = message.message().as_bytes()
    assert issuer.pk == document.issuer_id
    assert document.commercial_status == Document.CommercialStatus.PAID
    assert (item.period_start, item.period_end) == (date(2026, 1, 1), date(2026, 1, 31))
    assert b'01/01/2026 a 31/01/2026' in mime
    assert any(attachment[0] == f'{document.public_number}.pdf' for attachment in message.attachments)


def test_legacy_cycle_can_supply_the_receipt_identity_without_a_new_cycle(
    super_client, hosted_period,
):
    """Falla si conciliar un ciclo legacy comprobable duplica su histórico de hosting."""
    record, income = hosted_period
    cycle = HostingCycle.objects.create(
        hosting_record=record,
        modality='monthly', amount='50000.00', paid_at=date(2026, 1, 31),
        period_from=date(2026, 1, 1), period_to=date(2026, 1, 31),
    )
    payload = receipt_payload(record, income)
    payload['hosting_receipt']['entries'][0]['cycle_id'] = cycle.pk

    response = record_receipt(super_client, record, payload)

    cycle.refresh_from_db()
    assert response.status_code == 201, response.data
    assert response.data['cycle']['id'] == cycle.pk
    assert HostingCycle.objects.count() == 1
    assert cycle.receipt_allocation.existing_cycle is True
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).count() == 1


def test_legacy_liquid_can_supply_the_receipt_identity_without_a_new_liquid(
    super_client, hosted_period,
):
    """Falla si conciliar un líquido legacy comprobable crea un segundo abono al mismo esperado."""
    record, income = hosted_period
    liquid = IncomeRecord.objects.create(
        concept='Abono legacy', kind=IncomeRecord.Kind.LIQUID,
        origin=IncomeRecord.Origin.HOSTING, project=income.project, client=income.client,
        expected_income=income, period_date=date(2026, 1, 31), total_amount='50000.00',
    )
    payload = receipt_payload(record, income)
    payload['hosting_receipt']['entries'][0]['liquid_id'] = liquid.pk

    response = record_receipt(super_client, record, payload)

    liquid.refresh_from_db()
    assert response.status_code == 200, response.data
    assert response.data['already_registered'] is True
    assert HostingCycle.objects.count() == 1
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).count() == 1
    assert liquid.hosting_allocation.cycle.hosting_record_id == record.pk


def test_unproven_legacy_cycle_and_liquid_are_not_linked_by_amount_or_dates(
    super_client, hosted_period,
):
    """Falla si dos filas legacy iguales se fusionan sin una evidencia común verificable."""
    record, income = hosted_period
    cycle = HostingCycle.objects.create(
        hosting_record=record,
        modality='monthly', amount='50000.00', paid_at=date(2026, 1, 31),
        period_from=date(2026, 1, 1), period_to=date(2026, 1, 31),
    )
    liquid = IncomeRecord.objects.create(
        concept='Abono legacy independiente', kind=IncomeRecord.Kind.LIQUID,
        origin=IncomeRecord.Origin.HOSTING, project=income.project, client=income.client,
        expected_income=income, period_date=date(2026, 1, 31), total_amount='50000.00',
    )
    payload = receipt_payload(record, income)
    payload['hosting_receipt']['entries'][0].update(cycle_id=cycle.pk, liquid_id=liquid.pk)

    response = super_client.post(
        f'/api/accounting/hostings/{record.pk}/cycle-receipt/?preview=1', payload, format='json',
    )

    assert response.status_code == 409
    assert HostingCycle.objects.count() == 1
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID).count() == 1
    assert IncomeSettlement.objects.count() == 0
