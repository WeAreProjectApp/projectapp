"""Financial invariants of the unified settlement and its complete reversal."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from content.models import ExpenseRecord, IncomeRecord, IncomeSettlement, PocketMovement
from content.services import accounting_service
from content.services.income_settlement_operation_service import (
    SettlementConflict, preview_settlement, reverse_settlement, settle_incomes,
    update_settlement,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def mute_transport():
    with patch.object(accounting_service, '_notify'):
        yield


def expected(label='Primero', **overrides):
    data = {
        'concept': label, 'kind': 'expected', 'ledger': 'company',
        'period_date': date(2026, 10, 1), 'total_amount': Decimal('100.00'),
        'gustavo_amount': Decimal('50.00'), 'carlos_amount': Decimal('50.00'),
    }
    return IncomeRecord.objects.create(**{**data, **overrides})


def payment(*incomes, **overrides):
    return {
        'income_ids': [row.pk for row in incomes],
        'total_amount': Decimal('180.00'), 'period_date': date(2026, 10, 19),
        'destination': 'pocket', 'notes': '', **overrides,
    }


def fee(amount='20.00'):
    return {'type': 'bank_fee', 'amount': Decimal(amount), 'detail': ''}


def test_fee_proportionally_closes_two_expected_incomes(superuser):
    """Falla si la comisión se imputa al último ingreso o sobregira el primero."""
    first, second = expected(), expected('Segundo')

    result = settle_incomes(payment(first, second, deductions=[fee()]), superuser)

    assert [row.total_amount for row in result['liquids']] == [Decimal('90.00')] * 2
    assert [(row.source_income_id, row.total_amount) for row in result['expenses']] == [(first.pk, Decimal('10.00')), (second.pk, Decimal('10.00'))]
    assert result['movement'].amount == Decimal('180.00')
    assert PocketMovement.objects.count() == 1
    assert [row.pocket_movement_id for row in result['expenses']] == [None, None]


def test_reversal_removes_the_deductions_with_the_money(superuser):
    """Falla si deshacer el abono deja una deducción que mantiene el ingreso pagado."""
    first, second = expected(), expected('Segundo')
    result = settle_incomes(payment(first, second, deductions=[fee()]), superuser)

    operation = reverse_settlement(result['settlement_id'], superuser)

    assert operation.status == 'reversed'
    assert PocketMovement.objects.count() == 0
    assert ExpenseRecord.objects.count() == 0
    assert IncomeRecord.objects.filter(kind='liquid').count() == 0


def test_reversal_restores_the_reprogrammed_amount(superuser):
    """Falla si el saldo derivado desaparece sin volver al ingreso original."""
    income = expected()
    result = settle_incomes(payment(income, total_amount=Decimal('60.00'), expected_incomes=[{
        'income_id': income.pk, 'concept': 'Saldo', 'amount': Decimal('40.00'),
        'period_date': date(2026, 11, 1),
    }]), superuser)

    reverse_settlement(result['settlement_id'], superuser)

    income.refresh_from_db()
    assert (income.total_amount, income.gustavo_amount, income.carlos_amount) == (Decimal('100.00'), Decimal('50.00'), Decimal('50.00'))
    assert IncomeRecord.objects.count() == 1


def test_reversal_refuses_a_reprogrammed_balance_with_a_later_payment(superuser):
    """Falla si una reversa borra dinero cobrado posteriormente al saldo derivado."""
    income = expected()
    original = settle_incomes(payment(income, total_amount=Decimal('60.00'), expected_incomes=[{
        'income_id': income.pk, 'concept': 'Saldo', 'amount': Decimal('40.00'),
        'period_date': date(2026, 11, 1),
    }]), superuser)
    settle_incomes(payment(original['expected_incomes'][0], total_amount=Decimal('10.00')), superuser)

    with pytest.raises(ValueError, match='tiene pagos'):
        reverse_settlement(original['settlement_id'], superuser)

    assert PocketMovement.objects.count() == 2


def test_request_retry_does_not_duplicate_the_payment(superuser):
    """Falla si repetir una solicitud tras un timeout registra dinero dos veces."""
    income = expected()
    data = payment(income, total_amount=Decimal('20.00'), request_id=uuid4())
    first = settle_incomes(data, superuser)

    retry = settle_incomes(data, superuser)

    assert retry['settlement_id'] == first['settlement_id']
    assert retry['replayed'] is True
    assert PocketMovement.objects.count() == 1
    assert IncomeSettlement.objects.count() == 1


def test_global_partner_amounts_are_conserved_across_incomes(superuser):
    """Falla si el reparto se vuelve a calcular por separado para cada ingreso."""
    first, second = expected(), expected('Segundo')

    result = settle_incomes(payment(first, second, total_amount=Decimal('101.03'),
        gustavo_amount=Decimal('70.01'), carlos_amount=Decimal('31.02')), superuser)

    assert sum(row.gustavo_amount for row in result['liquids']) == Decimal('70.01')
    assert sum(row.carlos_amount for row in result['liquids']) == Decimal('31.02')
    assert [row.company_amount for row in result['liquids']] == [Decimal('0.00')] * 2


def test_partner_destination_does_not_create_a_pocket_movement(superuser):
    """Falla si elegir Socios registra también una entrada ficticia al bolsillo."""
    income = expected()

    result = settle_incomes(payment(income, total_amount=Decimal('100.00'), destination='partners'), superuser)

    assert result['movement'] is None
    assert PocketMovement.objects.count() == 0
    assert result['liquid'].destination == 'partners'


def test_residual_only_settlement_has_no_money_event(superuser):
    """Falla si resolver un saldo enteramente deducido crea un abono de cero pesos."""
    income = expected()

    result = settle_incomes(payment(income, total_amount=Decimal('0.00'), deductions=[fee('100.00')]), superuser)

    assert result['liquid'] is None
    assert result['movement'] is None
    assert result['expenses'][0].total_amount == Decimal('100.00')


def test_preview_does_not_write_financial_records():
    """Falla si revisar la propuesta crea registros antes de confirmarla."""
    first, second = expected(), expected('Segundo')

    result = preview_settlement(payment(first, second, deductions=[fee()]))

    assert [row['amount'] for row in result['rows']] == ['90.00', '90.00']
    assert IncomeSettlement.objects.count() == 0
    assert PocketMovement.objects.count() == 0
    assert ExpenseRecord.objects.count() == 0


def test_stale_preview_refuses_changed_balances(superuser):
    """Falla si se confirma una distribución calculada antes de otro abono."""
    income = expected()
    data = payment(income, total_amount=Decimal('20.00'))
    preview = preview_settlement(data)
    settle_incomes(payment(income, total_amount=Decimal('10.00')), superuser)

    with pytest.raises(SettlementConflict, match='cambiaron'):
        settle_incomes({**data, 'preview_hash': preview['preview_hash']}, superuser)

    assert PocketMovement.objects.count() == 1


def test_generic_deduction_deletion_cannot_break_the_settlement(superuser):
    """Falla si el CRUD de gastos permite borrar solo la comisión del abono."""
    income = expected()
    result = settle_incomes(payment(income, total_amount=Decimal('80.00'), deductions=[fee()]), superuser)

    with pytest.raises(ValueError, match='liquidación completa'):
        accounting_service.delete_record('expense', result['expenses'][0], superuser)

    assert ExpenseRecord.objects.count() == 1


def test_correction_replaces_deductions_with_the_payment(superuser):
    """Falla si corregir el abono conserva la comisión anterior."""
    income = expected()
    original = settle_incomes(payment(income, total_amount=Decimal('80.00'), deductions=[fee()]), superuser)

    result = update_settlement(original['settlement_id'], payment(income,
        total_amount=Decimal('90.00'), deductions=[fee('10.00')]), superuser, revision=1)

    assert result['movement'].pk == original['movement'].pk
    assert result['movement'].amount == Decimal('90.00')
    assert ExpenseRecord.objects.get().total_amount == Decimal('10.00')
    assert result['settlement'].revision == 2
