"""Reconcile one evidenced cash receipt through either accounting entry point."""
from dataclasses import dataclass
from decimal import Decimal

from accounts.models import ProjectHosting
from content.models import (
    HostingCycle, HostingIncomePeriod, HostingReceipt, HostingReceiptAllocation, HostingReceiptAttempt,
)
from content.services.hosting_cycle_service import register_cycle_payment
from content.services.hosting_periods import HostingPeriods, PeriodConflict, UNLINKED_CASH, Window, fingerprint
from content.services.income_settlement_allocation import money
from content.utils import add_months


REVIEW = 'La referencia ya corresponde a otra imputación. Consulta el pago registrado antes de continuar.'
NEEDS_REFERENCE = 'Selecciona el asiento acreditado o indica la fuente y el folio estable del pago.'


@dataclass
class ReceiptEntry:
    book: HostingPeriods
    window: Window
    cycle: object = None
    liquid: object = None

    def describe(self):
        def identity(obj, relation):
            allocation = getattr(obj, relation, None)
            if not allocation:
                return {}
            receipt = allocation.receipt
            return {'receipt_id': receipt.pk, 'issuer': receipt.issuer, 'reference': receipt.reference,
                    'allocation_id': allocation.pk, 'destination': allocation.liquid.destination}

        p = self.window
        return {
            **p.summary(self.book),
            'cycles': [{'id': c.pk, 'amount': str(c.amount), 'date': c.paid_at, **identity(c, 'receipt_allocation')} for c in p.cycles],
            'liquids': [{'id': i.pk, 'amount': str(i.total_amount), 'date': i.period_date, 'destination': i.destination, **identity(i, 'hosting_allocation')} for i in p.liquids],
        }


def settlement_entries(parents, data):
    requested = {e['income_id']: e for e in data.get('hosting_receipt', {}).get('entries', [])}
    managed = [p for p in parents if p.origin == 'hosting' and p.project_id and p.period_start and p.period_end]
    if not managed and not requested:
        return {}
    projects = set(ProjectHosting.objects.filter(project_id__in=[p.project_id for p in managed]).values_list('project_id', flat=True))
    books = {}
    entries = {}
    for p in managed:
        if p.project_id not in projects:
            continue   # Unmapped pre-PA-51 income: its accounting history remains available.
        if p.project_id not in books:
            books[p.project_id] = HostingPeriods(p.project_id)
        book = books[p.project_id]
        if not book.record:
            if p.pk in requested:
                raise PeriodConflict('Asocia el origen operativo para registrar el pago del ciclo.')
            continue
        window = book.settlement_window(p)
        source = requested.get(p.pk, {})
        if source and source['hosting_record_id'] != book.record.pk:
            raise PeriodConflict('El ingreso seleccionado pertenece a otro servicio.')
        entry = ReceiptEntry(book, window)
        if source.get('cycle_id'):
            entry.cycle = next((c for c in window.cycles if c.pk == source['cycle_id'] and
                                c.hosting_record_id == book.record.pk and c.cycles_represented == 1), None)
            if not entry.cycle:
                raise PeriodConflict('El ciclo no corresponde a esta obligación o es un histórico consolidado.')
        if source.get('liquid_id'):
            entry.liquid = next((i for i in window.liquids if i.pk == source['liquid_id'] and i.kind == 'liquid'
                                 and i.project_id == p.project_id and i.client_id == p.client_id), None)
            if not entry.liquid:
                raise PeriodConflict('El asiento no corresponde a este ingreso y servicio.')
        if entry.cycle and entry.liquid and not getattr(entry.liquid, 'hosting_allocation', None):
            evidence = getattr(entry.cycle, 'billing_evidence', None)
            if not evidence or not entry.liquid.collection_documents.filter(hosting_evidence__group_id=evidence.group_id).exists():
                raise PeriodConflict(UNLINKED_CASH)
        entries[p.pk] = entry
    if set(requested) - set(entries):
        raise PeriodConflict('El ingreso no tiene un período de hosting compatible con la selección.')
    return entries


def receipt_identity(data, entries):
    payload = data['hosting_receipt']
    aliases = set()
    for entry in entries.values():
        for obj, relation in ((entry.cycle, 'receipt_allocation'), (entry.liquid, 'hosting_allocation')):
            allocation = getattr(obj, relation, None)
            if allocation:
                aliases.add(allocation.receipt_id)
        if entry.liquid and entry.liquid.settlement_id:
            registered = getattr(entry.liquid.settlement, 'hosting_receipt', None)
            if registered:
                aliases.add(registered.pk)
    if len(aliases) > 1:
        raise PeriodConflict(REVIEW)
    issuer = payload.get('issuer', '').strip().casefold()
    reference = payload.get('reference', '').strip()
    if len(issuer) > 96 or len(reference) > 128:
        raise PeriodConflict('La referencia del pago excede la longitud permitida.')
    if aliases:
        existing = HostingReceipt.objects.select_for_update().get(pk=aliases.pop())
        if issuer and (issuer, reference) != (existing.issuer, existing.reference):
            raise PeriodConflict(REVIEW)
        return existing, existing.issuer, existing.reference
    if not issuer:
        existing_rows = [(e.liquid, '@liquid') if e.liquid else (e.cycle, '@cycle') for e in entries.values()]
        existing_rows = [(row, kind) for row, kind in existing_rows if row]
        if len(existing_rows) != 1:
            raise PeriodConflict(NEEDS_REFERENCE)
        row, issuer = existing_rows[0]
        reference = str(row.pk)
    qs = HostingReceipt.objects.select_for_update()
    return qs.filter(issuer=issuer, reference=reference).first(), issuer, reference


def attempt_hash(data):
    return fingerprint({k: v for k, v in data.items() if k not in ('preview_hash', 'request_id')})


def remember_attempt(data, receipt):
    if data.get('request_id'):
        attempt, _ = HostingReceiptAttempt.objects.get_or_create(
            pk=data['request_id'], defaults={'receipt': receipt, 'payload_hash': attempt_hash(data)},
        )
        if attempt.receipt_id != receipt.pk or attempt.payload_hash != attempt_hash(data):
            raise PeriodConflict('Este intento ya se usó con otros datos.')


def _check_distribution(liquids, data, parents, cash_total, originally_selected):
    amounts = {r.expected_income_id: r.total_amount for r in liquids if r.expected_income_id}
    if set(originally_selected) != {p.pk for p in parents} or money(data['total_amount']) != cash_total:
        raise PeriodConflict(REVIEW)
    if any(r.period_date != data['period_date'] or r.destination != data.get('destination', 'pocket') for r in liquids):
        raise PeriodConflict(REVIEW)
    explicit = data.get('allocations')
    if explicit is not None and amounts != {r['income_id']: money(r['amount']) for r in explicit if r['amount']}:
        raise PeriodConflict(REVIEW)


def existing_result(receipt, entries, parents, data):
    """Return the accounting facts before running allocation against a possibly zero balance."""
    from content.services.income_settlement_operation_service import _result

    selected = [entry.liquid for entry in entries.values() if entry.liquid]
    operation = receipt.settlement if receipt else None
    operations = {row.settlement_id for row in selected if row.settlement_id}
    if operations:
        if len(operations) != 1 or (operation and operation.pk not in operations):
            raise PeriodConflict(REVIEW)
        operation = next(row.settlement for row in selected if row.settlement_id)
    if operation:
        if operation.status != 'active':
            raise PeriodConflict('El pago fue revertido. Revisa su historial antes de continuar.')
        result = _result(operation)
        _check_distribution(result['liquids'], data, parents, money(operation.input_snapshot['total_amount']),
                            operation.effects['parent_ids'])
        for key in ('deductions', 'expected_incomes', 'vat_updates', 'periods', 'gustavo_amount', 'carlos_amount'):
            submitted = data.get(key)
            if submitted and fingerprint(submitted) != fingerprint(operation.input_snapshot.get(key)):
                # Some adapters spell the same decimal with a different precision.
                if key not in ('gustavo_amount', 'carlos_amount') or money(submitted) != sum(
                        (getattr(row, key) for row in result['liquids']), Decimal('0')):
                    raise PeriodConflict(REVIEW)
        return {**result, 'replayed': True}
    if receipt and receipt.allocations.exists():
        selected = [a.liquid for a in receipt.allocations.select_related('liquid').order_by('pk')]
    if not selected:
        return None
    _check_distribution(selected, data, parents, sum((i.total_amount for i in selected), Decimal('0')),
                        [i.expected_income_id for i in selected])
    if data.get('deductions') or data.get('expected_incomes') or data.get('vat_updates'):
        raise PeriodConflict(REVIEW)
    return {'settlement': None, 'settlement_id': None, 'incomes': parents, 'liquids': selected,
            'liquid': selected[0], 'income': parents[0], 'movement': selected[0].pocket_movement,
            'expenses': [], 'expected_incomes': [], 'credit': None, 'replayed': True}


def check_entry(entry, amount, data, *, recognized=False):
    w = entry.window
    if w.conflict and not (w.conflict == UNLINKED_CASH and (entry.cycle or entry.liquid or recognized)):
        raise PeriodConflict(w.conflict)
    if entry.cycle and (entry.cycle.amount != amount or entry.cycle.paid_at != data['period_date']):
        raise PeriodConflict('El importe o la fecha difiere del ciclo acreditado.')
    if not recognized:
        old_cycles = [c for c in w.cycles if not hasattr(c, 'receipt_allocation')]
        old_cash = [i for i in w.liquids if not hasattr(i, 'hosting_allocation')]
        if any(c != entry.cycle for c in old_cycles) or any(i != entry.liquid for i in old_cash):
            raise PeriodConflict(UNLINKED_CASH)
        if w.payment and w.payment.status in ('paid', 'processing') and not (entry.cycle or entry.liquid):
            raise PeriodConflict('La suscripción ya tiene un pago o un intento en curso. Concilia su asiento.')


def renewal_target(record, data):
    options = data.get('_hosting_cycle', {})
    if not options.get('advance_validity'):
        return None
    modality = options.get('modality') or record.payment_modality
    return options.get('period_to') or add_months(options.get('period_from') or record.valid_to or data['period_date'],
                                                 record.MODALITY_MONTHS[modality])


def attach_effects(receipt, entries, result, data, user):
    """Both the financial effects and their history links commit in the caller's transaction."""
    operation = result['settlement']
    if operation and not receipt.settlement_id:
        if HostingReceipt.objects.filter(settlement=operation).exclude(pk=receipt.pk).exists():
            raise PeriodConflict(REVIEW)
        receipt.settlement = operation
        receipt.save(update_fields=['settlement'])
    for liquid in result['liquids']:
        entry = entries.get(liquid.expected_income_id)
        if not entry:
            continue
        prior = getattr(liquid, 'hosting_allocation', None)
        if prior:
            if prior.receipt_id != receipt.pk or (entry.cycle and entry.cycle.pk != prior.cycle_id):
                raise PeriodConflict(REVIEW)
            continue
        if entry.cycle and hasattr(entry.cycle, 'receipt_allocation'):
            raise PeriodConflict(REVIEW)
        check_entry(entry, liquid.total_amount, data)
        w = entry.window
        period, _ = HostingIncomePeriod.objects.get_or_create(
            hosting=entry.book.hosting, start=w.start, end=w.end, defaults={'income_id': liquid.expected_income_id},
        )
        if period.income_id != liquid.expected_income_id:
            raise PeriodConflict(REVIEW)
        options = data.get('_hosting_cycle', {})
        cycle = entry.cycle or register_cycle_payment(entry.book.record, data={
            **options, 'amount': liquid.total_amount, 'paid_at': liquid.period_date,
            'period_from': w.start, 'period_to': w.end,
            'notes': data.get('notes', ''), 'advance_validity': options.get('advance_validity', False) and not result.get('replayed'),
        }, user=user, validity_target=renewal_target(entry.book.record, data), notify=False)
        HostingReceiptAllocation.objects.create(receipt=receipt, period=period, liquid=liquid, cycle=cycle,
                                               existing_cycle=bool(entry.cycle))
    remember_attempt(data, receipt)


def existing_preview(result, entries, data):
    from content.serializers.accounting import paid_total_for_income
    from content.services.income_payment_confirmation_service import confirmation_contexts

    parents = result['incomes']
    contexts = confirmation_contexts(parents)
    rows = []
    for parent in parents:
        entry = entries.get(parent.pk)
        cash = sum((i.total_amount for i in result['liquids'] if i.expected_income_id == parent.pk), Decimal('0'))
        deducted = sum((e.total_amount for e in result['expenses'] if e.source_income_id == parent.pk), Decimal('0'))
        follow_ups = sum((i.total_amount for i in result['expected_incomes']
                          if i.source_ref == f'income:{parent.pk}:settlement'), Decimal('0'))
        balance = entry.window.balance if entry else parent.total_amount - paid_total_for_income(parent)
        rows.append({
            'income_id': parent.pk, 'concept': parent.concept, 'amount': str(cash), 'vat_rate': parent.vat_rate,
            'hosting_period': entry.describe() if entry else None, 'deducted': str(deducted),
            'reexpected': str(follow_ups), 'pending_after': str(balance),
            'confirmation': {**contexts[parent.pk], 'can_send': False, 'blocked_reason': 'Pago acreditado.'},
        })
    return {'rows': rows, 'already_registered': True, 'total_amount': str(data['total_amount']),
            'pending_after': str(sum((Decimal(row['pending_after']) for row in rows), Decimal('0'))),
            'preview_hash': fingerprint([result['settlement_id'], rows])}


def undo_allocations(operation, user):
    from content.services.hosting_cycle_service import delete_cycle
    receipt = getattr(operation, 'hosting_receipt', None)
    if not receipt:
        return
    for allocation in receipt.allocations.select_related('cycle__hosting_record', 'liquid').order_by('pk'):
        if allocation.liquid.collection_documents.exclude(commercial_status='cancelled').exists():
            raise PeriodConflict('Hay una cuenta del pago. Resuelve su documentación antes de corregirlo.')
        cycle = allocation.cycle
        if not allocation.existing_cycle and hasattr(cycle, 'billing_evidence'):
            raise PeriodConflict('El ciclo tiene una conciliación posterior. Revísala antes de corregirlo.')
        allocation.delete()
        if not allocation.existing_cycle:
            delete_cycle(cycle.hosting_record, cycle, user=user, notify=False)
