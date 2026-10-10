"""Correcting one real pocket transfer without changing its identity."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import (
    AccountingChangeLog, Document, DocumentType, IncomeCompletionNotice,
    IncomeRecord, PocketMovement,
)
from content.services.accounting_abono_service import update_income_abono
from content.services.accounting_settlement_service import (
    bulk_settle_expected_incomes,
    income_payment_status,
)

pytestmark = pytest.mark.django_db


def _expected(concept, **overrides):
    fields = {
        'concept': concept, 'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': date(2026, 10, 1), 'total_amount': Decimal('100.00'),
        'gustavo_amount': Decimal('50.00'), 'carlos_amount': Decimal('50.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def _abono(first, second, user):
    return bulk_settle_expected_incomes({
        'allocations': [
            {'income_id': first.pk, 'amount': Decimal('60.00')},
            {'income_id': second.pk, 'amount': Decimal('40.00')},
        ],
        'total_amount': Decimal('100.00'),
        'period_date': date(2026, 10, 10),
        'notes': 'Transferencia original',
    }, user)


def test_update_abono_replaces_distribution_on_existing_movement(superuser):
    """Falla si corregir un reparto duplica el movimiento o conserva imputaciones reemplazadas."""
    first = _expected('Fase dos')
    second = _expected('Fase tres')
    original = _abono(first, second, superuser)

    result = update_income_abono(original['movement'].pk, {
        'allocations': [
            {'income_id': first.pk, 'amount': Decimal('20.00')},
            {'income_id': second.pk, 'amount': Decimal('100.00')},
        ],
        'total_amount': Decimal('120.00'),
        'period_date': date(2026, 10, 20),
        'notes': 'Reparto corregido',
    }, superuser)

    movement = result['movement']
    allocations = sorted(
        movement.income_records.values_list('expected_income_id', 'total_amount'),
    )
    change = AccountingChangeLog.objects.get(
        entity_type=AccountingChangeLog.EntityType.POCKET,
        object_id=movement.pk,
        action=AccountingChangeLog.Action.UPDATED,
    )
    assert (movement.pk, movement.amount, movement.movement_date, movement.notes) == (
        original['movement'].pk, Decimal('120.00'), date(2026, 10, 20), 'Reparto corregido',
    )
    assert PocketMovement.objects.count() == 1
    assert allocations == [(first.pk, Decimal('20.00')), (second.pk, Decimal('100.00'))]
    assert {first.pk: income_payment_status(first), second.pk: income_payment_status(second)} == {
        first.pk: 'partial', second.pk: 'paid',
    }
    assert IncomeCompletionNotice.objects.filter(income=second).count() == 1
    assert next(item for item in change.changes if item['field'] == 'allocations')['new'] == [
        [first.pk, '20.00'], [second.pk, '100.00'],
    ]


def test_invalid_abono_replacement_preserves_accounting_state(superuser):
    """Falla si rechazar una imputación sobregirada borra el reparto que ya estaba contabilizado."""
    first = _expected('Fase dos')
    second = _expected('Fase tres')
    original = _abono(first, second, superuser)
    before_allocations = sorted(
        original['movement'].income_records.values_list('expected_income_id', 'total_amount'),
    )

    with pytest.raises(ValueError, match='supera su saldo disponible'):
        update_income_abono(original['movement'].pk, {
            'allocations': [
                {'income_id': first.pk, 'amount': Decimal('101.00')},
            ],
            'total_amount': Decimal('101.00'),
            'period_date': date(2026, 10, 20),
            'notes': 'No debe guardarse',
        }, superuser)

    original['movement'].refresh_from_db()
    assert original['movement'].amount == Decimal('100.00')
    assert sorted(
        original['movement'].income_records.values_list('expected_income_id', 'total_amount'),
    ) == before_allocations
    assert original['movement'].income_records.count() == 2


def test_mixed_client_excess_replacement_preserves_accounting_state(
    superuser, make_client_profile,
):
    """Falla si un excedente sin cliente único borra el reparto antes de ser rechazado."""
    first = _expected('Fase dos', client=make_client_profile(company='Kore SAS'))
    second = _expected('Fase tres', client=make_client_profile(company='Globex SAS'))
    original = _abono(first, second, superuser)
    before_allocations = sorted(
        original['movement'].income_records.values_list('expected_income_id', 'total_amount'),
    )

    with pytest.raises(ValueError, match='clientes mezclados'):
        update_income_abono(original['movement'].pk, {
            'allocations': [
                {'income_id': first.pk, 'amount': Decimal('60.00')},
                {'income_id': second.pk, 'amount': Decimal('40.00')},
            ],
            'total_amount': Decimal('110.00'),
            'period_date': date(2026, 10, 20), 'notes': 'No debe guardarse',
        }, superuser)

    original['movement'].refresh_from_db()
    assert original['movement'].amount == Decimal('100.00')
    assert original['movement'].income_records.count() == 2
    assert sorted(
        original['movement'].income_records.values_list('expected_income_id', 'total_amount'),
    ) == before_allocations


def test_correcting_a_paid_abono_reopens_its_issued_collection_account(superuser):
    """Falla si reducir un pago completo deja como pagada una cuenta que vuelve a tener saldo pendiente."""
    first = _expected('Fase dos')
    second = _expected('Fase tres')
    collection_type = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )[0]
    account = Document.objects.create(
        title='Cuenta fase dos', document_type=collection_type,
        commercial_status=Document.CommercialStatus.ISSUED, income_record=first,
    )
    original = bulk_settle_expected_incomes({
        'allocations': [
            {'income_id': first.pk, 'amount': Decimal('100.00')},
            {'income_id': second.pk, 'amount': Decimal('40.00')},
        ],
        'total_amount': Decimal('140.00'),
        'period_date': date(2026, 10, 10), 'notes': '',
    }, superuser)
    account.refresh_from_db()
    assert account.commercial_status == Document.CommercialStatus.PAID

    update_income_abono(original['movement'].pk, {
        'allocations': [
            {'income_id': first.pk, 'amount': Decimal('20.00')},
            {'income_id': second.pk, 'amount': Decimal('70.00')},
        ],
        'total_amount': Decimal('90.00'),
        'period_date': date(2026, 10, 20), 'notes': 'Corrección',
    }, superuser)

    account.refresh_from_db()
    assert account.commercial_status == Document.CommercialStatus.ISSUED
