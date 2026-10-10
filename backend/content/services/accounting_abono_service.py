"""Correct an existing transfer and its allocations as one financial write."""
from decimal import Decimal

from django.db import transaction

from accounts.services.billing_locks import current_income_paid_total, lock_billing_rows
from content.models import AccountingChangeLog, IncomeRecord, PocketMovement
from content.serializers.accounting import validate_project_client_match
from content.services import accounting_service
from content.services.accounting_settlement_service import (
    _abono_concept, _create_abono_child, _create_credit_child, _stamp_abono_ref,
    _sync_linked_collection_accounts,
)
from content.services.entity_history import historical_write
from content.services.income_completion_notice_service import schedule_completion_notice


def _lock_abono(movement_id, target_ids=()):
    discovered = list(IncomeRecord.objects.filter(
        pocket_movement_id=movement_id,
    ).values_list('pk', 'expected_income_id'))
    if not discovered:
        raise ValueError('Este movimiento no corresponde a un abono de ingresos.')
    parent_ids = {parent_id for _, parent_id in discovered if parent_id}
    locked = lock_billing_rows(
        income_ids=[*parent_ids, *target_ids, *(pk for pk, _ in discovered)],
        include_income_children=True, include_origin_documents=True,
    )
    movement = PocketMovement.objects.select_for_update().filter(pk=movement_id).first()
    if movement is None:
        raise ValueError('El movimiento ya no existe. Actualiza el bolsillo.')
    children = list(IncomeRecord.objects.select_for_update().filter(
        pocket_movement=movement,
    ).order_by('pk'))
    if [(row.pk, row.expected_income_id) for row in children] != sorted(discovered):
        raise ValueError('El reparto del abono cambió. Consulta el movimiento e inténtalo de nuevo.')
    if movement.direction != 'in' or any(
        child.kind != 'liquid' or child.destination != 'pocket' or child.ledger != 'company'
        for child in children
    ):
        raise ValueError('Solo se pueden corregir abonos de ingresos en el bolsillo de empresa.')
    if sum((child.total_amount for child in children), Decimal('0')) != movement.amount:
        raise ValueError('El abono y su reparto no coinciden. Revisa el movimiento antes de corregirlo.')
    return movement, children, locked


def _validate_replacement(data, parents, old_children):
    old_amounts = {}
    for child in old_children:
        if child.expected_income_id:
            old_amounts[child.expected_income_id] = old_amounts.get(child.expected_income_id, Decimal('0')) + child.total_amount
    for entry, income in zip(data['allocations'], parents):
        validate_project_client_match(income.project, income.client)
        if income.kind != 'expected' or income.ledger != 'company':
            raise ValueError('El reparto solo admite ingresos esperados de empresa.')
        available = income.total_amount - current_income_paid_total(income) + old_amounts.get(income.pk, Decimal('0'))
        if entry['amount'] > available:
            raise ValueError(f'La imputación a "{income.concept}" supera su saldo disponible (${available:,.2f}).')
    allocated = sum((entry['amount'] for entry in data['allocations']), Decimal('0'))
    excess = data['total_amount'] - allocated
    if excess > 0 and len({income.client_id for income in parents}) > 1:
        raise ValueError('Con clientes mezclados no se puede asignar el excedente como saldo a favor.')
    return excess


@historical_write
@transaction.atomic
def update_income_abono(movement_id, data, user):
    """Replace the distribution without changing the transfer's identity.

    Availability adds this transfer's old slices back before validating the
    replacement. All refusals precede the first deletion; other payments are
    never subtracted or changed.
    """
    ids = [entry['income_id'] for entry in data['allocations']]
    movement, old_children, locked = _lock_abono(movement_id, ids)
    parents = [locked.incomes[pk] for pk in ids]
    affected_ids = {child.expected_income_id for child in old_children if child.expected_income_id} | set(ids)
    was_paid = {
        pk: current_income_paid_total(locked.incomes[pk]) >= locked.incomes[pk].total_amount
        for pk in affected_ids
    }
    excess = _validate_replacement(data, parents, old_children)
    old_values = accounting_service.snapshot_values(movement, AccountingChangeLog.EntityType.POCKET)
    old_distribution = sorted(
        (child.expected_income_id or 0, str(child.total_amount)) for child in old_children
    )
    new_distribution = sorted(
        (entry['income_id'], str(entry['amount'])) for entry in data['allocations']
    )
    if excess > 0:
        new_distribution.append((0, str(excess)))
        new_distribution.sort()
    if (old_distribution == new_distribution and movement.amount == data['total_amount']
            and movement.movement_date == data['period_date'] and movement.notes == data.get('notes', '')):
        return {'movement': movement, 'incomes': [locked.incomes[pk] for pk in sorted(affected_ids)],
                'credit': next((child for child in old_children if child.expected_income_id is None), None)}
    for child in old_children:
        accounting_service.log_entity_removal(AccountingChangeLog.EntityType.INCOME, child, user)
        child.delete()
    movement.amount = data['total_amount']
    movement.movement_date = data['period_date']
    movement.notes = data.get('notes', '')
    movement.concept = _abono_concept(parents)
    movement.save(update_fields=['amount', 'movement_date', 'notes', 'concept', 'updated_at'])
    children = [
        _create_abono_child(income, entry['amount'], data, movement, user)
        for entry, income in zip(data['allocations'], parents)
    ]
    credit = None
    if excess > 0:
        credit = _create_credit_child(excess, parents[0].client, data, movement, user)
        children.append(credit)
    _stamp_abono_ref(movement, children)
    for pk in sorted(affected_ids):
        income = locked.incomes[pk]
        _sync_linked_collection_accounts(income, user)
        accounting_service.deselect_receivable_if_closed(income, user)
        schedule_completion_notice(income, was_paid=was_paid[pk])
    changes = accounting_service.compute_changes(
        AccountingChangeLog.EntityType.POCKET, old_values,
        accounting_service.snapshot_values(movement, AccountingChangeLog.EntityType.POCKET),
    )
    if old_distribution != new_distribution:
        changes.append({'field': 'allocations', 'label': 'Reparto del abono',
                        'old': old_distribution, 'new': new_distribution})
    change_log = accounting_service.log_accounting_change(
        entity_type=AccountingChangeLog.EntityType.POCKET, object_id=movement.pk,
        object_repr=movement.concept, action=AccountingChangeLog.Action.UPDATED,
        changes=changes, actor=user, movement_direction=movement.direction,
    )
    accounting_service._notify(change_log)
    return {'movement': movement, 'incomes': [locked.incomes[pk] for pk in sorted(affected_ids)], 'credit': credit}


@historical_write
@transaction.atomic
def delete_income_abono(movement_id, user):
    movement, _, _ = _lock_abono(movement_id)
    accounting_service.delete_record(AccountingChangeLog.EntityType.POCKET, movement, user)
