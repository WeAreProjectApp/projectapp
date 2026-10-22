"""Fiscal changes are part of the same reversible payment operation."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from content.models import Document, DocumentType, ExpenseRecord, IncomeRecord, IncomeSettlement, PocketMovement
from content.services import accounting_service
from content.services.income_settlement_operation_service import (
    SettlementConflict, preview_settlement, reverse_settlement, settle_incomes,
    update_settlement,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def mute_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


def source(**overrides):
    return IncomeRecord.objects.create(**{
        'concept': 'Servicio', 'kind': 'expected', 'ledger': 'company',
        'period_date': date(2026, 10, 1), 'total_amount': Decimal('238000.00'),
        'gustavo_amount': Decimal('119000.00'), 'carlos_amount': Decimal('119000.00'),
        'vat_rate': None, **overrides,
    })


def payment(*parents, **overrides):
    return {
        'income_ids': [row.pk for row in parents], 'total_amount': Decimal('119000.00'),
        'period_date': date(2026, 10, 21), 'destination': 'pocket', **overrides,
    }


def tax(parent, rate='19.00', **capture):
    return {'income_id': parent.pk, 'vat_rate': Decimal(rate) if rate is not None else None, **capture}


def issue(parent):
    kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Cuenta'})
    return Document.objects.create(title='Cuenta emitida', document_type=kind,
                                   income_record=parent, commercial_status='issued', total=parent.total_amount)


def test_preview_uses_draft_rate_without_saving_the_source():
    """Falla si la vista previa guarda IVA antes de confirmar el pago."""
    parent = source()
    result = preview_settlement(payment(parent, vat_updates=[tax(parent)]))

    parent.refresh_from_db()
    assert parent.vat_rate is None
    assert (result['rows'][0]['base_amount'], result['rows'][0]['vat_amount']) == ('100000.00', '19000.00')
    assert IncomeSettlement.objects.count() == 0
    assert PocketMovement.objects.count() == 0


def test_payment_inherits_the_confirmed_source_rate(superuser):
    """Falla si el pago conserva la tasa anterior o cambia el importe esperado."""
    parent = source()
    result = settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)

    parent.refresh_from_db()
    assert (parent.vat_rate, parent.total_amount) == (Decimal('19'), Decimal('238000'))
    assert (result['liquid'].vat_rate, result['liquid'].vat_amount) == (Decimal('19'), Decimal('19000'))
    assert result['movement'].amount == Decimal('119000')


@pytest.mark.parametrize(('amount', 'mode'), [('100000.00', 'before_vat'), ('119000.00', 'vat_included')])
def test_both_capture_modes_book_the_same_money(superuser, amount, mode):
    """Falla si introducir la base y el total genera pagos de distinto valor."""
    parent = source()
    data = payment(parent, vat_updates=[tax(parent, amount=Decimal(amount), amount_mode=mode)])
    result = settle_incomes(data, superuser)

    assert result['liquid'].total_amount == Decimal('119000')
    assert result['liquid'].base_amount == Decimal('100000')


def test_zero_rate_explicitly_removes_vat(superuser):
    """Falla si apagar el IVA sólo esconde el desglose sin guardar cero."""
    parent = source(vat_rate=Decimal('19'))
    result = settle_incomes(payment(parent, vat_updates=[tax(parent, '0')]), superuser)

    parent.refresh_from_db()
    assert parent.vat_rate == Decimal('0')
    assert result['liquid'].vat_amount == Decimal('0')
    assert result['liquid'].base_amount == result['liquid'].total_amount


def test_omitted_configuration_keeps_unknown_vat(superuser):
    """Falla si abrir o liquidar un ingreso histórico infiere una tasa."""
    parent = source()
    result = settle_incomes(payment(parent), superuser)

    parent.refresh_from_db()
    assert parent.vat_rate is None
    assert result['liquid'].vat_amount is None


def test_each_source_keeps_its_selected_rate(superuser):
    """Falla si una liquidación colectiva aplana todas las tasas al primer IVA."""
    first, second = source(), source(concept='Otro')
    data = payment(first, second, total_amount=Decimal('238000'), allocations=[
        {'income_id': first.pk, 'amount': Decimal('119000')},
        {'income_id': second.pk, 'amount': Decimal('119000')},
    ], vat_updates=[tax(first), tax(second, '5')])
    result = settle_incomes(data, superuser)

    assert [row.vat_rate for row in result['liquids']] == [Decimal('19'), Decimal('5')]
    assert result['movement'].amount == Decimal('238000')


def test_reprogrammed_balance_inherits_the_selected_rate(superuser):
    """Falla si el saldo futuro pierde el IVA confirmado en su origen."""
    parent = source()
    data = payment(parent, vat_updates=[tax(parent)], expected_incomes=[{
        'income_id': parent.pk, 'concept': 'Saldo', 'amount': Decimal('119000'),
        'period_date': date(2026, 11, 1),
    }])
    result = settle_incomes(data, superuser)

    assert result['expected_incomes'][0].vat_rate == Decimal('19')
    assert result['expected_incomes'][0].total_amount == Decimal('119000')


def test_issued_account_blocks_a_source_rate_change(superuser):
    """Falla si liquidar permite corregir una cuenta que ya se emitió."""
    parent = source()
    issue(parent)
    with pytest.raises(ValueError, match='Anula la cuenta'):
        settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)

    assert PocketMovement.objects.count() == 0


def test_prior_payment_blocks_a_source_rate_change(superuser):
    """Falla si un nuevo abono cambia las condiciones de los pagos previos."""
    parent = source()
    settle_incomes(payment(parent, total_amount=Decimal('100')), superuser)
    with pytest.raises(ValueError, match='pagos o deducciones'):
        settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)

    assert PocketMovement.objects.count() == 1


def test_prior_deduction_blocks_a_source_rate_change():
    """Falla si una retención anterior permite cambiar la tasa de su ingreso."""
    parent = source()
    ExpenseRecord.objects.create(concept='Retención', period_date=date(2026, 10, 1),
                                 total_amount=Decimal('100'), source_income=parent, deduction_type='withholding')
    result = preview_settlement(payment(parent))

    assert result['rows'][0]['vat_editable'] is False
    assert 'pagos o deducciones' in result['rows'][0]['vat_blocked_reason']


def test_locked_income_can_still_receive_a_payment(superuser):
    """Falla si el bloqueo del porcentaje impide liquidar sin cambio fiscal."""
    parent = source(vat_rate=Decimal('19'))
    issue(parent)
    result = settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)

    assert result['liquid'].total_amount == Decimal('119000')


def test_capture_mismatch_rolls_back_the_operation(superuser):
    """Falla si una base incompatible se guarda con otro importe de pago."""
    parent = source()
    with pytest.raises(ValueError, match='no coincide'):
        settle_incomes(payment(parent, vat_updates=[tax(parent, amount=Decimal('1'), amount_mode='before_vat')]), superuser)

    parent.refresh_from_db()
    assert parent.vat_rate is None
    assert IncomeSettlement.objects.count() == 0


def test_reversal_restores_the_original_unknown_rate(superuser):
    """Falla si deshacer la operación deja parte de su cambio fiscal guardado."""
    parent = source()
    result = settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)
    reverse_settlement(result['settlement_id'], superuser)

    parent.refresh_from_db()
    assert parent.vat_rate is None
    assert IncomeRecord.objects.filter(kind='liquid').count() == 0


def test_later_payment_prevents_restoring_the_old_rate(superuser):
    """Falla si revertir cambia el IVA de un ingreso usado por un abono posterior."""
    parent = source()
    first = settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)
    settle_incomes(payment(parent, total_amount=Decimal('100')), superuser)
    with pytest.raises(SettlementConflict, match='posteriores'):
        reverse_settlement(first['settlement_id'], superuser)

    assert PocketMovement.objects.count() == 2


def test_correction_replaces_the_operation_rate(superuser):
    """Falla si corregir no puede sustituir su propio cambio fiscal reversible."""
    parent = source()
    original = settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)
    result = update_settlement(original['settlement_id'], payment(parent, vat_updates=[tax(parent, '0')]), superuser, revision=1)

    parent.refresh_from_db()
    assert parent.vat_rate == Decimal('0')
    assert result['liquid'].vat_amount == Decimal('0')
    assert result['settlement'].revision == 2


def test_rate_change_invalidates_an_earlier_preview(superuser):
    """Falla si una revisión anterior confirma después de cambiar el IVA original."""
    parent = source()
    data = payment(parent, vat_updates=[tax(parent)])
    preview = preview_settlement(data)
    IncomeRecord.objects.filter(pk=parent.pk).update(vat_rate=Decimal('5'))
    with pytest.raises(SettlementConflict, match='cambiaron'):
        settle_incomes({**data, 'preview_hash': preview['preview_hash']}, superuser)

    assert PocketMovement.objects.count() == 0


def test_retry_preserves_the_single_fiscal_operation(superuser):
    """Falla si reenviar la configuración duplica el pago después de un timeout."""
    parent = source()
    data = payment(parent, vat_updates=[tax(parent)], request_id=uuid4())
    first = settle_incomes(data, superuser)
    retry = settle_incomes(data, superuser)

    assert retry['settlement_id'] == first['settlement_id']
    assert PocketMovement.objects.count() == 1


def test_historical_abono_rejects_unsupported_vat_configuration(superuser):
    """Falla si el adaptador histórico acepta IVA pero descarta la configuración."""
    from content.services.accounting_abono_service import update_income_abono

    parent = source()
    movement = PocketMovement.objects.create(concept='Abono histórico', amount=Decimal('100'),
        direction='in', movement_date=date(2026, 10, 1))
    IncomeRecord.objects.create(concept='Pago histórico', kind='liquid', ledger='company',
        destination='pocket', expected_income=parent, pocket_movement=movement,
        period_date=date(2026, 10, 1), total_amount=Decimal('100'), vat_rate=None)

    with pytest.raises(ValueError, match='históricos conservan su IVA'):
        update_income_abono(movement.pk, payment(parent, total_amount=Decimal('100'),
            allocations=[{'income_id': parent.pk, 'amount': Decimal('100')}], vat_updates=[tax(parent)]), superuser)

    parent.refresh_from_db()
    movement.refresh_from_db()
    assert parent.vat_rate is None
    assert movement.amount == Decimal('100')


def test_abono_alias_configures_vat_for_a_registered_operation(superuser):
    """Falla si proteger los históricos bloquea también el adaptador de operaciones nuevas."""
    from content.services.accounting_abono_service import update_income_abono

    parent = source()
    original = settle_incomes(payment(parent, vat_updates=[tax(parent)]), superuser)
    result = update_income_abono(original['movement'].pk, payment(parent,
        allocations=[{'income_id': parent.pk, 'amount': Decimal('119000')}],
        vat_updates=[tax(parent, '0')]), superuser)

    parent.refresh_from_db()
    assert parent.vat_rate == Decimal('0')
    assert result['liquid'].vat_amount == Decimal('0')
