"""Regression guards for the calendar-backed hosting income and receipt APIs."""
from datetime import date

import pytest

from accounts.models import Payment
from accounts.tests.billing.hosting_payment_fixtures import billing, payment_inputs
from content.models import HostingIncomePeriod, IncomeRecord, IncomeSettlement


pytestmark = pytest.mark.django_db


def test_next_income_requires_review_version_without_creating_an_income(billing):
    """Falla si confirmar sin la versión revisada crea un esperado nuevo."""
    client, record, income = billing

    response = client.post(
        f'/api/accounting/hostings/{record.pk}/next-income/',
        {'reference_income_id': income.pk}, format='json',
    )

    assert response.status_code == 400
    assert 'Revisa y confirma el ingreso esperado' in str(response.data)
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED).count() == 1
    assert not HostingIncomePeriod.objects.exists()


def test_next_income_rejects_a_stale_calendar_review_without_writing(billing):
    """Falla si una revisión vieja permite crear un esperado con datos contractuales nuevos."""
    client, record, income = billing
    url = f'/api/accounting/hostings/{record.pk}/next-income/'
    review = client.get(url, {'reference_income_id': income.pk})
    record.domain_url = 'hosting-cambiado.example'
    record.save(update_fields=['domain_url'])

    response = client.post(
        url, {'reference_income_id': income.pk, 'version': review.data['version']}, format='json',
    )

    assert review.status_code == 200, review.data
    assert response.status_code == 409
    assert 'El período cambió desde la revisión' in str(response.data)
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED).count() == 1
    assert not HostingIncomePeriod.objects.exists()


def test_next_income_blocks_a_subscription_with_a_conflicting_cadence(billing):
    """Falla si un calendario trimestral permite prever un ciclo semestral del registro."""
    client, record, income = billing
    record.payment_modality = 'semiannual'
    record.save(update_fields=['payment_modality'])

    response = client.get(
        f'/api/accounting/hostings/{record.pk}/next-income/', {'reference_income_id': income.pk},
    )

    assert response.status_code == 409
    assert 'Concilia el fin del período actual' in str(response.data)
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED).count() == 1
    assert not HostingIncomePeriod.objects.exists()


def test_next_income_blocks_a_future_processing_obligation_without_an_expected(billing):
    """Falla si un pago futuro en proceso sin esperado permite duplicar la obligación."""
    client, record, income = billing
    Payment.objects.create(
        subscription=record.project.hosting_subscription, amount=233280, status=Payment.STATUS_PROCESSING,
        billing_period_start=date(2026, 7, 1), billing_period_end=date(2026, 9, 30), due_date=date(2026, 7, 1),
    )

    response = client.get(
        f'/api/accounting/hostings/{record.pk}/next-income/', {'reference_income_id': income.pk},
    )

    assert response.status_code == 409
    assert 'El siguiente período ya tiene un pago o documento' in str(response.data)
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED).count() == 1
    assert not HostingIncomePeriod.objects.exists()


def test_next_income_blocks_an_overlapping_future_calendar_window(billing):
    """Falla si una obligación futura solapada deja crear otro esperado para el mismo hecho."""
    client, record, income = billing
    Payment.objects.create(
        subscription=record.project.hosting_subscription, amount=233280, status=Payment.STATUS_PENDING,
        billing_period_start=date(2026, 7, 2), billing_period_end=date(2026, 9, 30), due_date=date(2026, 7, 2),
    )

    response = client.get(
        f'/api/accounting/hostings/{record.pk}/next-income/', {'reference_income_id': income.pk},
    )

    assert response.status_code == 409
    assert 'Ya existe una ventana que se solapa' in str(response.data)
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED).count() == 1
    assert not HostingIncomePeriod.objects.exists()


def test_cycle_receipt_rejects_an_issuer_without_a_stable_reference(billing):
    """Falla si una fuente de pago sin folio estable se acepta como identidad del recibo."""
    client, record, _ = billing
    payload, _ = payment_inputs(billing)
    payload['hosting_receipt'].pop('reference')

    response = client.post(f'/api/accounting/hostings/{record.pk}/cycle-receipt/', payload, format='json')

    assert response.status_code == 400
    assert 'Indica tanto la fuente como el folio estable' in str(response.data)
    assert not IncomeSettlement.objects.exists()


def test_cycle_receipt_rejects_a_malformed_issuer_reference(billing):
    """Falla si un emisor reservado para referencias internas identifica un pago acreditado."""
    client, record, _ = billing
    payload, _ = payment_inputs(billing)
    payload['hosting_receipt']['issuer'] = '@interno'

    response = client.post(f'/api/accounting/hostings/{record.pk}/cycle-receipt/', payload, format='json')

    assert response.status_code == 400
    assert 'Elige la fuente que emitió el folio' in str(response.data)
    assert not IncomeSettlement.objects.exists()


def test_cycle_receipt_rejects_duplicate_income_evidence(billing):
    """Falla si un mismo ingreso se puede imputar dos veces dentro de un recibo."""
    client, record, income = billing
    payload, _ = payment_inputs(billing)
    payload['hosting_receipt']['entries'].append({'income_id': income.pk, 'hosting_record_id': record.pk})

    response = client.post(f'/api/accounting/hostings/{record.pk}/cycle-receipt/', payload, format='json')

    assert response.status_code == 400
    assert 'Indica una sola imputación de hosting por ingreso' in str(response.data)
    assert not IncomeSettlement.objects.exists()


def test_cycle_receipt_rejects_evidence_for_a_different_hosting_record(billing):
    """Falla si un recibo puede acreditar el ingreso desde otro servicio operativo."""
    client, record, income = billing
    payload, _ = payment_inputs(billing)
    payload['hosting_receipt']['entries'] = [{'income_id': income.pk, 'hosting_record_id': record.pk + 1000}]

    response = client.post(f'/api/accounting/hostings/{record.pk}/cycle-receipt/', payload, format='json')

    assert response.status_code == 400
    assert 'Completa el cliente y el proyecto' in str(response.data)
    assert not IncomeSettlement.objects.exists()


def test_cycle_receipt_requires_preview_confirmation_before_writing(billing):
    """Falla si un recibo válido puede registrar efectivo sin la revisión explícita."""
    client, record, _ = billing
    payload, _ = payment_inputs(billing)

    response = client.post(f'/api/accounting/hostings/{record.pk}/cycle-receipt/', payload, format='json')

    assert response.status_code == 400
    assert 'Revisa y confirma el pago antes de registrarlo' in str(response.data)
    assert not IncomeSettlement.objects.exists()


def test_cycle_receipt_lists_a_blocker_when_the_operating_owner_is_missing(billing):
    """Falla si una consulta sin proyecto operativo expone ingresos conciliables."""
    client, record, _ = billing
    record.project = None
    record.save(update_fields=['project'])

    response = client.get(f'/api/accounting/hostings/{record.pk}/cycle-receipt/')

    assert response.status_code == 200
    assert response.data['incomes'] == []
    assert 'Completa el cliente y el proyecto' in response.data['blocker']


def test_cycle_receipt_lists_an_overlapping_legacy_income_as_blocked(billing):
    """Falla si un esperado legacy solapado parece una opción cobrable sin advertencia."""
    client, record, _ = billing
    legacy = IncomeRecord.objects.create(
        project=record.project, client=record.client, kind=IncomeRecord.Kind.EXPECTED,
        origin=IncomeRecord.Origin.HOSTING, concept='Esperado legacy solapado',
        period_start=date(2026, 5, 1), period_end=date(2026, 7, 31), period_date=date(2026, 5, 1),
        period_cadence='quarterly', total_amount=233280,
    )

    response = client.get(f'/api/accounting/hostings/{record.pk}/cycle-receipt/')

    legacy_option = response.data['incomes'][0]
    assert response.status_code == 200
    assert legacy_option['income_id'] == legacy.pk
    assert legacy_option['state'] == 'blocked'
    assert 'Concilia el ingreso esperado con el período del mismo servicio' in legacy_option['blocker']


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('client', None, 'Completa el cliente y el proyecto'),
        ('project', None, 'Completa el cliente y el proyecto'),
        ('payment_per_cycle', 0, 'Configura la tarifa por ciclo del hosting'),
        ('payment_modality', 'unsupported', 'Completa la periodicidad del servicio'),
    ],
)
def test_next_income_blocks_incomplete_service_data_without_writing(billing, field, value, message):
    """Falla si un servicio sin dueño, tarifa o periodicidad crea un esperado nuevo."""
    client, record, income = billing
    setattr(record, field, value)
    record.save(update_fields=[field])

    response = client.get(
        f'/api/accounting/hostings/{record.pk}/next-income/', {'reference_income_id': income.pk},
    )

    assert response.status_code == 409
    assert message in str(response.data)
    assert IncomeRecord.objects.filter(kind=IncomeRecord.Kind.EXPECTED).count() == 1
    assert not HostingIncomePeriod.objects.exists()
