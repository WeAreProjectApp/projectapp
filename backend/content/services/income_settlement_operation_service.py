"""One preview, writer and reversible unit for individual and grouped payments."""
import hashlib
import json
import uuid
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction

from accounts.services.billing_locks import lock_billing_rows
from content.models import AccountingChangeLog, Document, ExpenseRecord, IncomeRecord, IncomeSettlement, PocketMovement
from content.serializers.accounting import (
    IncomeRecordCreateUpdateSerializer, validate_project_client_match,
)
from content.services import accounting_service
from content.services.entity_history import historical_write
from content.services.income_settlement_allocation import allocation_plan, money
from content.services.accounting_vat import vat_breakdown

EntityType = AccountingChangeLog.EntityType


class SettlementConflict(ValueError):
    """The financial or email facts changed after the last preview."""


def json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _digest(value):
    return hashlib.sha256(json.dumps(json_safe(value), sort_keys=True).encode()).hexdigest()


def selected_ids(data):
    return data.get('income_ids') or [entry['income_id'] for entry in data.get('allocations', [])]


def _parents(data):
    ids = selected_ids(data)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Selecciona ingresos distintos para liquidar.')
    locked = lock_billing_rows(income_ids=ids, include_income_children=True, include_origin_documents=True)
    parents = sorted((locked.incomes[pk] for pk in ids), key=lambda row: (row.period_date, row.pk))
    for income in parents:
        validate_project_client_match(income.project, income.client)
        if income.kind != 'expected':
            raise ValueError(f'Solo se pueden liquidar ingresos esperados ("{income.concept}" no lo es).')
    if len({parent.ledger for parent in parents}) != 1 or (len(parents) > 1 and parents[0].ledger != 'company'):
        raise ValueError('La liquidación múltiple solo admite ingresos de empresa; liquida los personales individualmente.')
    return parents


def _financial_snapshot(instance):
    names = (
        'total_amount', 'gustavo_amount', 'carlos_amount', 'kind', 'client_id',
        'project_id', 'origin', 'vat_rate', 'destination', 'expected_income_id',
        'source_income_id', 'deduction_type', 'period_date', 'period_start',
        'period_end', 'period_cadence', 'pocket_movement_id',
    )
    return json_safe({name: getattr(instance, name) for name in names if hasattr(instance, name)})


def _prepare(parents, data):
    from content.services.income_payment_confirmation_service import confirmation_contexts

    paid = dict.fromkeys([parent.pk for parent in parents], Decimal('0'))
    for child in IncomeRecord.objects.select_for_update().filter(expected_income_id__in=paid, kind='liquid').order_by('pk'):
        paid[child.expected_income_id] += child.total_amount
    for expense in ExpenseRecord.objects.select_for_update().filter(source_income_id__in=paid).exclude(deduction_type='').order_by('pk'):
        paid[expense.source_income_id] += expense.total_amount
    pendings = {parent.pk: parent.total_amount - paid[parent.pk] for parent in parents}
    if any(value <= 0 for value in pendings.values()):
        raise ValueError('Alguno de los ingresos ya está completamente pagado. Actualiza la selección.')
    if data.get('_single') and money(data['total_amount']) > pendings[parents[0].pk]:
        raise ValueError('La suma del monto recibido, los gastos y los nuevos ingresos esperados no puede superar el saldo pendiente.')
    plan = allocation_plan(parents, pendings, data)
    if not (plan['total_amount'] or plan['deducted'] or data.get('expected_incomes')):
        raise ValueError('El monto recibido debe ser mayor a cero.')
    contexts = confirmation_contexts(parents)
    for parent, row in zip(parents, plan['rows']):
        base, vat, total = vat_breakdown(row['amount'], parent.vat_rate)
        row.update(
            concept=parent.concept, client_id=parent.client_id, project_id=parent.project_id,
            vat_rate=parent.vat_rate, base_amount=base, vat_amount=vat,
            total_amount=total, confirmation=contexts[parent.pk],
        )
    facts = {
        'parents': {parent.pk: _financial_snapshot(parent) for parent in parents},
        'plan': plan,
    }
    payload = {key: value for key, value in data.items() if key not in {'preview_hash', 'request_id'}}
    plan['preview_hash'] = _digest({'input': payload, 'facts': facts})
    return plan


@transaction.atomic
def preview_settlement(data):
    """Read current, consistent balances without creating any bookkeeping."""
    return json_safe(_prepare(_parents(data), data))


def single_input(income, data):
    return {
        **data, '_single': True, 'income_ids': [income.pk],
        'allocations': [{'income_id': income.pk, 'amount': data['total_amount']}],
        'expected_incomes': [{**entry, 'income_id': income.pk} for entry in data.get('expected_incomes', [])],
        'periods': [{**data['period'], 'income_id': income.pk}] if data.get('period') else [],
    }


def _create_payment(parent, row, data, movement, user):
    payload = {
        'concept': data.get('concept', parent.concept) if data.get('_single') else parent.concept,
        'kind': 'liquid', 'period_date': data['period_date'],
        'destination': data.get('destination', 'pocket'), 'ledger': parent.ledger,
        'vat_rate': parent.vat_rate, 'total_amount': row['amount'],
        'gustavo_amount': row['gustavo_amount'], 'carlos_amount': row['carlos_amount'],
        'expected_income': parent.pk, 'client': parent.client_id,
        'project': parent.project_id, 'origin': parent.origin,
        'notes': data.get('notes', '') if data.get('_single') else '',
    }
    serializer = IncomeRecordCreateUpdateSerializer(data=payload, context={'settlement': True})
    serializer.is_valid(raise_exception=True)
    return accounting_service.create_record(EntityType.INCOME, serializer, user, notify=False, shared_pocket_movement=movement)


def _create_movement(parents, data, user, existing=None):
    from content.services.accounting_settlement_service import _abono_concept
    if data.get('destination', 'pocket') != 'pocket' or not money(data['total_amount']) or parents[0].ledger != 'company':
        return None
    values = {
        'concept': _abono_concept(parents), 'movement_date': data['period_date'],
        'direction': PocketMovement.Direction.IN, 'amount': data['total_amount'],
        'notes': data.get('notes', ''),
    }
    if existing is not None:
        for name, value in values.items():
            setattr(existing, name, value)
        existing.save(update_fields=[*values, 'updated_at'])
        return existing
    return PocketMovement.objects.create(**values, created_by=user if getattr(user, 'is_authenticated', False) else None)


def _record_effects(operation, parents, plan, data, user, existing_movement=None, old_movement_values=None):
    from content.services import accounting_settlement_service as helpers

    before = {parent.pk: _financial_snapshot(parent) for parent in parents}
    periods = {entry['income_id']: entry for entry in data.get('periods', [])}
    movement = _create_movement(parents, data, user, existing_movement)
    liquids, expenses, follow_ups = [], [], []
    for parent, row in zip(parents, plan['rows']):
        if parent.pk in periods:
            helpers._complete_parent_period(parent, periods[parent.pk], user)
        if row['amount'] > 0:
            liquids.append(_create_payment(parent, row, data, movement, user))
        derived_expenses = [helpers._create_deduction(parent, data, line, user) for line in row['deductions']]
        derived_follow_ups = [helpers._create_follow_up(parent, line, user) for line in row['expected_incomes']]
        helpers._stamp_source_ref(derived_expenses, parent.pk)
        helpers._stamp_source_ref(derived_follow_ups, parent.pk)
        expenses.extend(derived_expenses)
        follow_ups.extend(derived_follow_ups)
        if row['reexpected']:
            helpers._reduce_parent(parent, parent.total_amount - row['reexpected'], user)
        parent.refresh_from_db()
    credit = None
    if plan['credit_amount']:
        # A credit shares the money event, including when the destination is
        # partners (where no pocket movement is created).
        serializer = IncomeRecordCreateUpdateSerializer(data={
            'concept': 'Saldo a favor', 'kind': 'liquid', 'ledger': 'company',
            'destination': data.get('destination', 'pocket'), 'period_date': data['period_date'],
            'total_amount': plan['credit_amount'], 'client': parents[0].client_id,
            'gustavo_amount': plan['credit_gustavo'], 'carlos_amount': plan['credit_carlos'],
        }, context={'settlement': True})
        serializer.is_valid(raise_exception=True)
        credit = accounting_service.create_record(EntityType.INCOME, serializer, user, notify=False, shared_pocket_movement=movement)
        liquids.append(credit)
    for instance in [*liquids, *follow_ups, *expenses]:
        type(instance).objects.filter(pk=instance.pk).update(settlement=operation)
        instance.settlement = operation
    if movement:
        helpers._stamp_abono_ref(movement, liquids)
    operation.pocket_movement = movement
    operation.input_snapshot = json_safe({key: value for key, value in data.items() if key != 'preview_hash'})
    operation.effects = {
        'parent_ids': [parent.pk for parent in parents],
        'parents_before': json_safe(before),
        'parents_after': {str(parent.pk): _financial_snapshot(parent) for parent in parents},
        'liquid_ids': [row.pk for row in liquids], 'expense_ids': [row.pk for row in expenses],
        'follow_up_ids': [row.pk for row in follow_ups], 'credit_id': credit.pk if credit else None,
        'income_snapshots': {str(row.pk): _financial_snapshot(row) for row in [*liquids, *follow_ups]},
        'expense_snapshots': {str(row.pk): _financial_snapshot(row) for row in expenses},
    }
    operation.save()
    _finish(parents, user)
    if movement:
        _log_movement(movement, user, old_movement_values)
    elif liquids:
        # create_record already recorded the facts; send one accounting notice
        # for the money event, including the personal-ledger path.
        log = AccountingChangeLog.objects.filter(entity_type=EntityType.INCOME, object_id=liquids[0].pk).order_by('-pk').first()
        if log:
            accounting_service._notify(log)
    return _result(operation)


def _finish(parents, user):
    from content.services.accounting_settlement_service import _sync_linked_collection_accounts
    from content.services.income_completion_notice_service import schedule_completion_notice
    for parent in parents:
        parent.refresh_from_db()
        _sync_linked_collection_accounts(parent, user)
        accounting_service.deselect_receivable_if_closed(parent, user)
        schedule_completion_notice(parent, was_paid=False)


def _log_movement(movement, user, old_values=None):
    changes = accounting_service.compute_changes(EntityType.POCKET, old_values or {}, accounting_service.snapshot_values(movement, EntityType.POCKET))
    if old_values and 'allocations' in old_values:
        current = sorted((row.expected_income_id or 0, str(row.total_amount)) for row in movement.income_records.all())
        if old_values['allocations'] != current:
            changes.append({'field': 'allocations', 'label': 'Reparto del abono', 'old': old_values['allocations'], 'new': current})
    log = accounting_service.log_accounting_change(
        entity_type=EntityType.POCKET, object_id=movement.pk, object_repr=movement.concept,
        action=AccountingChangeLog.Action.UPDATED if old_values else AccountingChangeLog.Action.CREATED,
        changes=changes, actor=user, movement_direction=movement.direction,
    )
    accounting_service._notify(log)


def _result(operation):
    effects = operation.effects
    parents = list(IncomeRecord.objects.filter(pk__in=effects['parent_ids']).order_by('period_date', 'pk'))
    liquids = list(operation.incomes.filter(kind='liquid').order_by('pk'))
    credit = next((row for row in liquids if row.pk == effects.get('credit_id')), None)
    return {
        'settlement': operation, 'settlement_id': str(operation.pk),
        'incomes': parents, 'liquids': liquids, 'movement': operation.pocket_movement,
        'credit': credit, 'expenses': list(operation.expenses.all().order_by('pk')),
        'expected_incomes': list(operation.incomes.filter(kind='expected').order_by('pk')),
        'income': parents[0] if len(parents) == 1 else None,
        'liquid': next((row for row in liquids if row.expected_income_id), None),
    }


@historical_write
@transaction.atomic
def settle_incomes(data, user):
    parents = _parents(data)
    request_id = data.get('request_id')
    if request_id:
        existing = IncomeSettlement.objects.select_for_update().filter(pk=request_id).first()
        if existing:
            return _replay(existing, data)
    plan = _prepare(parents, data)
    if data.get('preview_hash') and data['preview_hash'] != plan['preview_hash']:
        raise SettlementConflict('Los saldos o los datos del correo cambiaron. Revisa la liquidación de nuevo.')
    try:
        with transaction.atomic():
            operation = IncomeSettlement.objects.create(
                id=request_id or uuid.uuid4(), created_by=user if getattr(user, 'is_authenticated', False) else None,
            )
    except IntegrityError:
        if not request_id:
            raise
        return _replay(IncomeSettlement.objects.select_for_update().get(pk=request_id), data)
    return _record_effects(operation, parents, plan, data, user)


def _replay(operation, data):
    old = {key: value for key, value in operation.input_snapshot.items() if key not in {'request_id', 'preview_hash'}}
    new = json_safe({key: value for key, value in data.items() if key not in {'request_id', 'preview_hash'}})
    if operation.status != 'active' or old != new:
        raise SettlementConflict('Esta solicitud ya se utilizó con otros datos o fue revertida.')
    return {**_result(operation), 'replayed': True}


def settlement_payload(operation):
    """Public operation detail also works without a pocket movement."""
    from content.serializers.accounting import ExpenseRecordSerializer, IncomeRecordSerializer
    result = _result(operation)
    return {
        'id': str(operation.pk), 'status': operation.status, 'revision': operation.revision,
        'movement_id': operation.pocket_movement_id,
        'created_at': operation.created_at, 'updated_at': operation.updated_at,
        'effects': operation.effects,
        'input': {key: value for key, value in operation.input_snapshot.items() if not key.startswith('_')},
        'incomes': IncomeRecordSerializer(result['incomes'], many=True).data,
        'liquids': IncomeRecordSerializer(result['liquids'], many=True).data,
        'expenses': ExpenseRecordSerializer(result['expenses'], many=True).data,
        'expected_incomes': IncomeRecordSerializer(result['expected_incomes'], many=True).data,
    }


def _lock_operation(settlement_id, extra_ids=()):
    discovered = IncomeSettlement.objects.get(pk=settlement_id)
    ids = {*discovered.effects['parent_ids'], *discovered.effects['liquid_ids'],
           *discovered.effects['follow_up_ids'], *extra_ids}
    lock_billing_rows(income_ids=ids, include_income_children=True, include_origin_documents=True)
    operation = IncomeSettlement.objects.select_for_update().get(pk=settlement_id)
    if operation.revision != discovered.revision:
        raise SettlementConflict('La liquidación cambió mientras se consultaba. Revísala de nuevo.')
    if operation.pocket_movement_id:
        PocketMovement.objects.select_for_update().get(pk=operation.pocket_movement_id)
    list(operation.expenses.select_for_update().order_by('pk'))
    return operation


def _assert_reversible(operation, revision=None):
    if operation.status != 'active':
        raise ValueError('Esta liquidación ya fue revertida.')
    if revision is not None and revision != operation.revision:
        raise SettlementConflict('La liquidación cambió. Consulta su revisión actual.')
    expected_incomes = operation.effects['income_snapshots']
    expected_expenses = operation.effects['expense_snapshots']
    incomes = list(operation.incomes.select_for_update().order_by('pk'))
    expenses = list(operation.expenses.select_for_update().order_by('pk'))
    if {str(row.pk) for row in incomes} != set(expected_incomes) or {str(row.pk) for row in expenses} != set(expected_expenses):
        raise SettlementConflict('Faltan registros de esta liquidación. Revisa su historial antes de corregirla.')
    for record in [*incomes, *expenses]:
        expected = expected_expenses[str(record.pk)] if isinstance(record, ExpenseRecord) else expected_incomes[str(record.pk)]
        if _financial_snapshot(record) != expected:
            raise SettlementConflict(f'El registro "{record.concept}" cambió después de liquidar; impide revertir el conjunto.')
    for income in incomes:
        if income.kind == 'expected' and (
            income.liquid_records.exists() or income.deduction_records.exists()
            or income.collection_documents.exclude(commercial_status='cancelled').exists()
        ):
            raise ValueError(f'El saldo reprogramado "{income.concept}" tiene pagos, deducciones o documentos vigentes; impide revertir la liquidación.')
    for parent in IncomeRecord.objects.filter(pk__in=operation.effects['parent_ids']):
        before = operation.effects['parents_before'][str(parent.pk)]
        after = operation.effects['parents_after'][str(parent.pk)]
        current = _financial_snapshot(parent)
        if any(current[name] != value for name, value in after.items() if before[name] != value):
            raise SettlementConflict(f'Las condiciones de "{parent.concept}" cambiaron después de reprogramarlo; impiden revertirlo.')


def _undo_effects(operation, user, keep_movement=False):
    parents = list(IncomeRecord.objects.filter(pk__in=operation.effects['parent_ids']).order_by('period_date', 'pk'))
    for record in [*operation.expenses.all(), *operation.incomes.all()]:
        entity_type = EntityType.EXPENSE if isinstance(record, ExpenseRecord) else EntityType.INCOME
        accounting_service.log_entity_removal(entity_type, record, user)
        record.delete()
    for parent in parents:
        before = operation.effects['parents_before'][str(parent.pk)]
        after = operation.effects['parents_after'][str(parent.pk)]
        fields = {name: value for name, value in before.items() if value != after[name]}
        if fields:
            serializer = IncomeRecordCreateUpdateSerializer(instance=parent, data=fields, partial=True, context={'settlement': True})
            serializer.is_valid(raise_exception=True)
            accounting_service.update_record(EntityType.INCOME, parent, serializer, user, notify=False)
    if operation.pocket_movement_id and not keep_movement:
        movement = operation.pocket_movement
        accounting_service.log_entity_removal(EntityType.POCKET, movement, user)
        movement.delete()
        operation.pocket_movement = None
    return parents


@historical_write
@transaction.atomic
def update_settlement(settlement_id, data, user, revision=None):
    operation = _lock_operation(settlement_id, selected_ids(data))
    _assert_reversible(operation, revision)
    movement = operation.pocket_movement
    keep_movement = movement is not None and data.get('destination', 'pocket') == 'pocket' and money(data['total_amount']) > 0
    old_values = accounting_service.snapshot_values(movement, EntityType.POCKET) if keep_movement else None
    if old_values is not None:
        old_values['allocations'] = sorted((row.expected_income_id or 0, str(row.total_amount)) for row in operation.incomes.filter(kind='liquid'))
    old_parent_ids = operation.effects['parent_ids']
    operation.revisions.append({'revision': operation.revision, 'input': operation.input_snapshot, 'effects': operation.effects, 'action': 'updated'})
    _undo_effects(operation, user, keep_movement)
    parents = _parents(data)
    plan = _prepare(parents, data)
    if data.get('preview_hash') and data['preview_hash'] != plan['preview_hash']:
        raise SettlementConflict('La propuesta de corrección cambió. Revísala antes de guardar.')
    operation.revision += 1
    result = _record_effects(operation, parents, plan, data, user, movement if keep_movement else None, old_values)
    _finish(list(IncomeRecord.objects.filter(pk__in=set(old_parent_ids) - set(selected_ids(data)))), user)
    return result


@historical_write
@transaction.atomic
def reverse_settlement(settlement_id, user, revision=None):
    operation = _lock_operation(settlement_id)
    _assert_reversible(operation, revision)
    operation.revisions.append({'revision': operation.revision, 'input': operation.input_snapshot, 'effects': operation.effects, 'action': 'reversed'})
    parents = _undo_effects(operation, user)
    operation.status = 'reversed'
    operation.revision += 1
    operation.save()
    _finish(parents, user)
    return operation
