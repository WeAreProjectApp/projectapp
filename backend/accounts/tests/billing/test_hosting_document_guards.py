"""The reviewed hosting period remains authoritative until the customer document is issued."""
from datetime import date
from decimal import Decimal

import pytest
from django.core import mail

from accounts.models import HostingEvidence, HostingEvidenceGroup
from accounts.tests.billing.hosting_payment_fixtures import billing, from_hosting, payment_inputs
from content.models import Document, HostingCycle, HostingReceiptAllocation, IncomeRecord, IncomeSettlement
from content.services import hosting_billing_service
from content.services.collection_account_service import (
    CollectionAccountError, get_default_issuer, issue_collection_account,
)
from content.services.collection_account_snapshot_service import CollectionAccountSnapshotError
from content.services.hosting_periods import current_summary

pytestmark = pytest.mark.django_db


def review(record):
    period = current_summary(record.project_id)
    return {'period_version': period['version'], 'hosting_payment_id': period['hosting_payment_id']}


def invoice_payload(record, income):
    period = current_summary(record.project_id)
    return {
        'client_profile_id': income.client_id, 'income_record_id': income.pk,
        'billing_nature': 'hosting', 'project_hosting_id': period['project_hosting_id'],
        'period_version': period['version'], 'hosting_payment_id': period['hosting_payment_id'],
        'items': [{'description': 'Servicio de hosting', 'unit_price': period['balance']}],
    }


def post_income_invoice(client, data):
    return client.post('/api/accounting/collection-accounts/create/', data, format='json')


@pytest.mark.parametrize('details', [
    {'billing_nature': 'contract'}, {'document_pending': True},
])
def test_managed_income_requires_the_reviewed_hosting_before_issue(billing, details):
    """Un ingreso de hosting conciliado impide emitir sin revisar su obligación."""
    client, record, income = billing
    response = post_income_invoice(client, {**invoice_payload(record, income), **details})
    assert response.status_code == 400
    assert 'revisa su período' in str(response.data)
    assert not Document.objects.exists()


def test_income_invoice_rejects_another_operating_service(billing):
    """El identificador de servicio integra el consentimiento para emitir."""
    client, record, income = billing
    data = invoice_payload(record, income)
    data['project_hosting_id'] += 100
    response = post_income_invoice(client, data)
    assert response.status_code == 400
    assert 'otro cliente o proyecto' in str(response.data)
    assert not Document.objects.exists()


def test_income_invoice_requires_the_specific_expected_income(billing):
    """Compartir proyecto y cliente no autoriza documentar el ingreso de otro período."""
    client, record, current = billing
    old = IncomeRecord.objects.create(
        project=record.project, client=record.client, kind='expected', origin='hosting',
        concept='Otro período', period_date=date(2025, 11, 1), period_start=date(2025, 11, 1),
        period_end=date(2025, 11, 30), total_amount=current.total_amount,
    )
    response = post_income_invoice(client, {**invoice_payload(record, current), 'income_record_id': old.pk})
    assert response.status_code == 400
    assert 'ingreso esperado que corresponde' in str(response.data)
    assert not Document.objects.exists()


@pytest.mark.parametrize('change', [
    {'currency': 'USD'}, {'vat_rate': '0.00'},
    {'items': [{'description': 'Valor modificado', 'unit_price': '233000.00'}]},
])
def test_income_invoice_preserves_reviewed_financial_terms(billing, change):
    """La cuenta no puede cambiar el saldo, el IVA ni la moneda del ingreso revisado."""
    client, record, income = billing
    response = post_income_invoice(client, {**invoice_payload(record, income), **change})
    assert response.status_code == 400
    assert 'importe, IVA y moneda' in str(response.data)
    income.refresh_from_db()
    assert income.total_amount == Decimal('233280') and income.vat_rate is None
    assert not Document.objects.exists()


@pytest.mark.parametrize('line_edit', [
    {'period_end': date(2026, 7, 1)}, {'line_total': Decimal('210000')}, {'item_type': 'service'},
])
def test_an_edited_draft_line_cannot_receive_a_number(billing, admin_user, line_edit):
    """Se vuelve a revisar una línea cuyo cambio alteraría el importe o el período visible en el PDF."""
    _, record, _ = billing
    draft = hosting_billing_service.create_hosting_collection_account(record, acting_user=admin_user, **review(record))
    draft.items.update(**line_edit)
    with pytest.raises(CollectionAccountError, match='cambió'):
        issue_collection_account(draft, issuer=get_default_issuer(), acting_user=admin_user)
    draft.refresh_from_db()
    assert draft.commercial_status == 'draft' and not draft.public_number
    assert not mail.outbox


def test_a_changed_draft_vat_rate_requires_a_new_review(billing, admin_user):
    """La tasa que verá el cliente en la cuenta coincide con la revisión del esperado."""
    _, record, _ = billing
    draft = hosting_billing_service.create_hosting_collection_account(record, acting_user=admin_user, **review(record))
    extension = draft.collection_account
    extension.vat_rate = Decimal('19.00')
    extension.save(update_fields=['vat_rate'])
    with pytest.raises(CollectionAccountError, match='cambió'):
        issue_collection_account(draft, issuer=get_default_issuer(), acting_user=admin_user)
    draft.refresh_from_db()
    assert draft.commercial_status == 'draft' and not draft.public_number


def test_a_reversed_receipt_cannot_be_documented_from_an_old_review(billing):
    """La confirmación anterior a una reversión no emite una cuenta de dinero retirado."""
    client, record, _ = billing
    payment, _ = payment_inputs(billing)
    result = from_hosting(billing, payment)
    assert result.status_code == 201, result.data
    undone = client.delete(f"/api/accounting/income-settlements/{result.data['settlement_id']}/",
                           {'revision': 1}, format='json')
    assert undone.status_code == 200, undone.data
    data = {'receipt_allocation_id': result.data['allocation_id'], 'period_version': result.data['period']['version'],
            'hosting_payment_id': result.data['period']['hosting_payment_id']}
    response = client.post(f'/api/accounting/hostings/{record.pk}/send-collection-account/', data, format='json')
    assert response.status_code == 400
    assert 'pago acreditado no corresponde' in str(response.data)
    assert not Document.objects.exists()


def test_an_archiving_failure_leaves_the_review_available_for_retry(billing, monkeypatch):
    """Un PDF que no pudo archivarse libera la cuenta y su numeración para el reintento."""
    client, record, _ = billing
    url = f'/api/accounting/hostings/{record.pk}/send-collection-account/'
    data = review(record)

    def unavailable(_document):
        raise CollectionAccountSnapshotError('Archivo de prueba temporalmente indisponible.')

    with monkeypatch.context() as patch:
        patch.setattr(hosting_billing_service, 'persist_collection_account_pdf', unavailable)
        failed = client.post(url, data, format='json')
    assert failed.status_code == 400
    assert not Document.objects.exists()
    assert not mail.outbox
    retry = client.post(url, data, format='json')
    assert retry.status_code == 201, retry.data
    assert retry.data['document']['public_number'].endswith('001')
    assert Document.objects.count() == 1


def test_a_reconciled_cycle_requires_reversal_of_its_financial_operation(billing):
    """La eliminación aislada del histórico no puede separar el dinero de su ciclo."""
    client, record, _ = billing
    payment, _ = payment_inputs(billing)
    posted = from_hosting(billing, payment)
    assert posted.status_code == 201, posted.data
    cycle = HostingCycle.objects.get(hosting_record=record)
    response = client.delete(f'/api/accounting/hostings/{record.pk}/cycles/{cycle.pk}/delete/')
    assert response.status_code == 409, response.data
    assert HostingCycle.objects.get(pk=cycle.pk).amount == Decimal('50000')
    assert IncomeRecord.objects.filter(kind='liquid').count() == 1


def test_a_draft_for_a_paid_receipt_protects_its_supporting_cash(billing, admin_user):
    """El movimiento que respalda un borrador debe seguir disponible hasta resolver la cuenta."""
    client, record, income = billing
    payment, _ = payment_inputs(billing)
    recorded = from_hosting(billing, payment)
    assert recorded.status_code == 201, recorded.data
    period = recorded.data['period']
    draft = hosting_billing_service.create_hosting_collection_account(
        record, acting_user=admin_user, period_version=period['version'],
        hosting_payment_id=period['hosting_payment_id'], receipt_allocation_id=recorded.data['allocation_id'],
    )

    response = client.delete(f"/api/accounting/income-settlements/{recorded.data['settlement_id']}/",
                             {'revision': 1}, format='json')

    assert response.status_code == 400, response.data
    assert 'Hay una cuenta del pago' in str(response.data)
    assert IncomeSettlement.objects.get().status == IncomeSettlement.Status.ACTIVE
    assert income.liquid_records.get().pk == draft.income_record_id
    assert HostingReceiptAllocation.objects.get().pk == recorded.data['allocation_id']


def test_a_subsequent_reconciliation_protects_its_cycle_from_reversal(billing):
    """Una conciliación agregada después de cobrar conserva su soporte y explica cómo revisarlo."""
    client, _, _ = billing
    payment, _ = payment_inputs(billing)
    recorded = from_hosting(billing, payment)
    assert recorded.status_code == 201, recorded.data
    group = HostingEvidenceGroup.objects.create(
        hosting_id=recorded.data['period']['project_hosting_id'], label='Conciliación posterior al abono',
    )
    evidence = HostingEvidence.objects.create(group=group, cycle_id=recorded.data['cycle']['id'])

    response = client.delete(f"/api/accounting/income-settlements/{recorded.data['settlement_id']}/",
                             {'revision': 1}, format='json')

    assert response.status_code == 400, response.data
    assert 'conciliación posterior' in str(response.data)
    assert IncomeSettlement.objects.get().status == IncomeSettlement.Status.ACTIVE
    assert HostingReceiptAllocation.objects.get().cycle_id == evidence.cycle_id


def test_a_reversed_folio_cannot_reactivate_cash_with_a_new_request(billing):
    """Un intento separado con el folio revertido muestra su historia y conserva el saldo."""
    client, record, _ = billing
    payment, _ = payment_inputs(billing, folio='Revertido-102')
    recorded = from_hosting(billing, payment)
    assert recorded.status_code == 201, recorded.data
    reversal = client.delete(f"/api/accounting/income-settlements/{recorded.data['settlement_id']}/",
                             {'revision': 1}, format='json')
    assert reversal.status_code == 200, reversal.data
    retry, _ = payment_inputs(billing, folio='Revertido-102')

    response = client.post(f'/api/accounting/hostings/{record.pk}/cycle-receipt/?preview=1', retry, format='json')

    assert response.status_code == 409, response.data
    assert 'pago fue revertido' in str(response.data)
    assert not HostingReceiptAllocation.objects.exists()
    assert current_summary(record.project_id)['balance'] == '233280.00'


@pytest.mark.parametrize(('archived', 'subscription_status'), [(True, 'active'), (False, 'cancelled')])
def test_ending_the_subscription_invalidates_an_existing_billing_review(billing, archived, subscription_status):
    """Una revisión anterior al archivo o cancelación de la suscripción no puede convertirse en cuenta."""
    client, record, _ = billing
    original = review(record)
    subscription = record.project.hosting_subscription
    subscription.is_archived = archived
    subscription.status = subscription_status
    subscription.save(update_fields=['is_archived', 'status'])

    with pytest.raises(hosting_billing_service.HostingBillingError, match='archivada o cancelada'):
        hosting_billing_service.create_hosting_collection_account(record, **original)

    context = client.get(f'/api/admin/billing-context/projects/{record.project_id}/hosting/')
    assert context.status_code == 200, context.data
    assert context.data['billing_period']['state'] == 'blocked'
    assert not Document.objects.exists()


def test_an_inactive_hosting_record_cannot_issue_from_an_open_review(billing):
    """Dar de baja el servicio entre la lectura y la emisión deja intacto el ingreso pendiente."""
    _, record, income = billing
    original = review(record)
    record.is_active = False
    record.save(update_fields=['is_active'])

    with pytest.raises(hosting_billing_service.HostingBillingError, match='hosting está inactivo'):
        hosting_billing_service.create_hosting_collection_account(record, **original)

    assert current_summary(record.project_id)['state'] == 'blocked'
    assert not income.liquid_records.exists()
    assert not Document.objects.exists()
