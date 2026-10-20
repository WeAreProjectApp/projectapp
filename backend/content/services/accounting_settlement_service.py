"""Settling an expected income that was collected short.

A client pays through Wompi, a bank or a withholding agent, and what lands is
4-10% below what was invoiced. That gap is not an unpaid balance — nobody will
ever collect it — yet the plain "Liquidar" action leaves it open forever,
because the pending amount is derived from the expected total minus its liquid
children.

This service closes the loop in one atomic operation: it registers what was
received and resolves the rest — deductions become linked expenses that count
as payment credit against the GROSS expected total, follow-ups move their
amount into their own expected record. The arithmetic that governs everything:

    pending = total - already_paid          # paid = liquid children + linked deductions
    received + deductions + follow_ups + unassigned = pending
    new parent total = total - follow_ups   # deductions keep the income gross

The income stays gross so the deduction can reduce utility as a real expense
without double-counting (the liquid total alone no longer carries the loss).
With no allocations the parent is untouched and the behaviour is identical to
today's liquidation. Whatever is left unassigned simply stays pending, so a
user who does not want to decide yet is never forced to.

``received`` may be zero when deductions and follow-ups cover the whole
pending: nothing was collected, so no liquid child is created and nobody is
notified — the settlement is pure bookkeeping that closes the residual.

The codebase already prescribed this workflow manually — see the error raised
when writing off a partially collected record in
``IncomeRecordCreateUpdateSerializer.validate``: *"Reduce su monto y registra la
diferencia como un ingreso perdido aparte"*.
"""
from decimal import ROUND_DOWN, Decimal

from django.db.models import Sum

from content.models import (
    AccountingChangeLog,
    Document,
    ExpenseRecord,
    IncomeRecord,
    Ledger,
    PocketMovement,
)
from content.serializers.accounting import (
    ExpenseRecordCreateUpdateSerializer,
    IncomeRecordCreateUpdateSerializer,
    payment_status_for,
    split_half,
)
from content.services import accounting_service

EntityType = AccountingChangeLog.EntityType

TWO_PLACES = Decimal('0.01')


def _paid_total(income):
    """Liquid children plus linked deductions fulfilling this expected record.

    The `kind=LIQUID` filter is load-bearing: `limit_choices_to` constrains the
    FK's target, not its source, so a lost record may point at an expected
    parent and must never count as payment. Deductions count as credit because
    the income keeps its gross total — the fee was applied at origin, so that
    part of the total will never arrive as a liquid child. The
    `deduction_type` exclude mirrors the LIQUID guard: only real deductions
    may credit the parent.
    """
    liquid = income.liquid_records.filter(
        kind=IncomeRecord.Kind.LIQUID,
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    deducted = income.deduction_records.exclude(
        deduction_type='',
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    return liquid + deducted


def income_payment_status(income):
    """Derived collection state ('pending'/'partial'/'paid') for an expected income.

    Single owner of the "is it fully paid" question outside serializers:
    the settle→cuenta sync below and the panel mark-paid guard both use it.
    """
    return payment_status_for(_paid_total(income), income.total_amount)


def _sync_linked_collection_accounts(income, user):
    """Reflect payment corrections in issued accounts inside the money write.

    Completing marks an issued account paid; reversing or reducing the payment
    reopens a paid account. Drafts and cancelled accounts retain their state.
    """
    paid = income_payment_status(income) == 'paid'
    from content.services.collection_account_service import (
        mark_collection_account_paid,
    )

    linked = income.collection_documents.filter(
        document_type__code='collection_account',
        project_id=income.project_id,
        commercial_status=(Document.CommercialStatus.ISSUED if paid
                           else Document.CommercialStatus.PAID),
    )
    if income.client_id:
        linked = linked.filter(client_user_id=income.client.user_id)
    for document in linked:
        if paid:
            mark_collection_account_paid(document, acting_user=user)
        else:
            from content.services.collection_account_service import _log_status_transition, _status_snapshot
            old_values = _status_snapshot(document)
            document.commercial_status = Document.CommercialStatus.ISSUED
            document.updated_by = user
            document.save(update_fields=['commercial_status', 'updated_by', 'updated_at'])
            _log_status_transition(document, old_values, user)


def _proportional_split(parent, amount):
    """Partner amounts keeping the parent's ratio, never exceeding `amount`.

    Both partners are rounded down independently so the unassigned residue
    (the company share) keeps its own proportion instead of being absorbed by
    whoever is computed last.
    """
    total = parent.total_amount or Decimal('0')
    if not total:
        return split_half(amount)
    gustavo = (amount * parent.gustavo_amount / total).quantize(
        TWO_PLACES, rounding=ROUND_DOWN,
    )
    carlos = (amount * parent.carlos_amount / total).quantize(
        TWO_PLACES, rounding=ROUND_DOWN,
    )
    return gustavo, carlos


def _deduction_label(deduction):
    """Free text wins for 'Otro'; otherwise the choice's Spanish label."""
    if deduction['type'] == ExpenseRecord.DeductionType.OTHER:
        return deduction.get('detail', '').strip() or 'Otro'
    return ExpenseRecord.DeductionType(deduction['type']).label


def _stamp_source_ref(records, income_id):
    """Trace every record back to the settlement that produced it.

    `source_ref` is not a serializer field, so it is written afterwards with a
    queryset update; the in-memory instances are patched too because they are
    what the view serializes back.
    """
    if not records:
        return
    source_ref = f'income:{income_id}:settlement'
    type(records[0]).objects.filter(
        pk__in=[record.pk for record in records],
    ).update(source_ref=source_ref)
    for record in records:
        record.source_ref = source_ref


def settle_expected_income(income, data, user):
    """Compatibility adapter to the same engine used for grouped payments."""
    from content.services.income_settlement_operation_service import settle_incomes, single_input
    return settle_incomes(single_input(income, data), user)


def _complete_parent_period(income, period, user):
    """Write the covered window the operator completed while settling.

    The window belongs here, on the expected income: it is the record that
    says which service was billed. Its children carry the payment instead, so
    they are exempt from the rule (see the covered-period block in
    ``IncomeRecordCreateUpdateSerializer.validate``) and this is the only
    place a settlement writes a period.

    It goes through the ordinary write serializer, without the `settlement`
    context, precisely because this IS someone describing the charge: the
    same rules the income form obeys apply — the end must come after the
    start, and the change lands in the accounting changelog like any other
    edit. The window says WHAT the charge covers; `period_date` says WHEN the
    money is expected. Completing a legacy window keeps the parent's date;
    moving an existing window follows its start only if the stored date
    already followed it. This parent edit skips the change email because the
    liquid child notifies for the settlement.
    """
    if income.origin != IncomeRecord.Origin.HOSTING:
        raise ValueError(
            'Solo un ingreso de hosting cubre un período; este no lo es.'
        )
    serializer = IncomeRecordCreateUpdateSerializer(
        instance=income,
        data={
            'period_start': period['period_start'],
            'period_end': period['period_end'],
            'period_cadence': period['period_cadence'],
        },
        partial=True, context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    return accounting_service.update_record(
        EntityType.INCOME, income, serializer, user, notify=False,
    )


def _create_liquid_child(income, data, user):
    """The payment itself — the only record that notifies, as it does today."""
    payload = {
        'concept': data['concept'],
        'kind': IncomeRecord.Kind.LIQUID,
        'period_date': data['period_date'],
        'destination': data['destination'],
        'ledger': income.ledger,
        'vat_rate': income.vat_rate,
        'total_amount': data['total_amount'],
        'expected_income': income.pk,
        # Inherited from the projection: without this the collected money
        # would drop out of its client's totals the moment it is settled.
        'client': income.client_id,
        # Same inheritance for the project — a liquid with no project would
        # split the deal across two per-project buckets (PA-51).
        'project': income.project_id,
        'origin': income.origin,
        'notes': data.get('notes', ''),
    }
    if data.get('gustavo_amount') is not None:
        payload['gustavo_amount'] = data['gustavo_amount']
    if data.get('carlos_amount') is not None:
        payload['carlos_amount'] = data['carlos_amount']
    # The child copies the parent's origin rather than classifying anything, so
    # it may be as blank as the parent — most of the book predates the field,
    # and refusing to settle those would be a far worse answer than a liquid
    # that is exactly as unclassified as what it collects.
    serializer = IncomeRecordCreateUpdateSerializer(
        data=payload, context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    return accounting_service.create_record(
        EntityType.INCOME, serializer, user,
    )


def _create_deduction(income, data, deduction, user):
    """The shortfall as an expense — never a pocket movement.

    `register_in_pocket=False` is load-bearing: this money never entered the
    pocket, it was discounted before the transfer ever arrived.
    """
    label = _deduction_label(deduction)
    gustavo, carlos = _proportional_split(income, deduction['amount'])
    serializer = ExpenseRecordCreateUpdateSerializer(
        data={
            'concept': f'{label} — {income.concept}'[:255],
            'period_date': data['period_date'],
            'category': ExpenseRecord.Category.BUSINESS,
            'ledger': income.ledger,
        'vat_rate': Decimal('0'),
            'total_amount': deduction['amount'],
            'gustavo_amount': gustavo,
            'carlos_amount': carlos,
            'deduction_type': deduction['type'],
            'register_in_pocket': False,
            'notes': data.get('notes', ''),
        },
        # The write serializer rejects deduction_type outside this flow.
        context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    expense = accounting_service.create_record(
        EntityType.EXPENSE, serializer, user, notify=False,
    )
    # Not serializer-writable — stamped afterwards like source_ref. This link
    # is what credits the deduction against the parent's gross total.
    ExpenseRecord.objects.filter(pk=expense.pk).update(source_income=income)
    expense.source_income = income
    return expense


def _create_follow_up(income, follow_up, user):
    """A balance that WILL be collected, rescheduled as its own expected."""
    gustavo, carlos = _proportional_split(income, follow_up['amount'])
    serializer = IncomeRecordCreateUpdateSerializer(
        data={
            'concept': follow_up['concept'],
            'kind': IncomeRecord.Kind.EXPECTED,
            'period_date': follow_up['period_date'],
            'destination': income.destination,
            'ledger': income.ledger,
            'vat_rate': income.vat_rate,
            'total_amount': follow_up['amount'],
            'gustavo_amount': gustavo,
            'carlos_amount': carlos,
            'client': income.client_id,
            'project': income.project_id,
            'origin': income.origin,
        },
        # Same as the liquid child: the rescheduled balance inherits the
        # parent's line of business, blank included.
        context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    return accounting_service.create_record(
        EntityType.INCOME, serializer, user, notify=False,
    )


def _reduce_parent(income, new_total, user):
    """Shrink the expected record by whatever was moved out of it.

    The split must be rescaled in the same call: `PartnerSplitMixin` rejects
    partner amounts adding up to more than the total, and the old split still
    reflects the old (larger) total.
    """
    gustavo, carlos = _proportional_split(income, new_total)
    serializer = IncomeRecordCreateUpdateSerializer(
        instance=income,
        data={
            'total_amount': new_total,
            'gustavo_amount': gustavo,
            'carlos_amount': carlos,
        },
        partial=True, context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    return accounting_service.update_record(
        EntityType.INCOME, income, serializer, user, notify=False,
    )


# ── Abono: one payment covering several expected incomes ──

def _abono_concept(parents):
    """'Abono <distinct clients in selection order>', or the count fallback.

    The movement is the only row the pocket ledger shows for the whole
    abono, so its concept has to say who paid without opening anything.
    """
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    seen = set()
    names = []
    for income in parents:
        if income.client_id and income.client_id not in seen:
            seen.add(income.client_id)
            names.append(build_client_display_name(income.client))
    if not names:
        suffix = 'ingreso' if len(parents) == 1 else 'ingresos'
        return f'Abono {len(parents)} {suffix}'[:255]
    return f'Abono {", ".join(names)}'[:255]


def _create_abono_child(income, amount, data, movement, user):
    """One allocation slice: a liquid child riding the shared movement.

    The child keeps the parent's concept so the incomes list reads naturally;
    the operator's note lives once, on the movement. No partner amounts on
    purpose: the write serializer applies split_half, exactly what settling
    to the pocket produces today.
    """
    serializer = IncomeRecordCreateUpdateSerializer(
        data={
            'concept': income.concept,
            'kind': IncomeRecord.Kind.LIQUID,
            'period_date': data['period_date'],
            'destination': IncomeRecord.Destination.POCKET,
            'ledger': income.ledger,
            'vat_rate': income.vat_rate,
            'total_amount': amount,
            'expected_income': income.pk,
            'client': income.client_id,
            'project': income.project_id,
            'origin': income.origin,
            'notes': '',
        },
        context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    return accounting_service.create_record(
        EntityType.INCOME, serializer, user,
        notify=False, shared_pocket_movement=movement,
    )


def _create_credit_child(excess, client, data, movement, user):
    """The client's saldo a favor: a parentless liquid child on the movement.

    Money that DID enter but covers no expected income yet. Keeping it as a
    child of the same movement preserves movement.amount == Σ children, and
    applying it later is just re-pointing its `expected_income` at the next
    expected record — the edit the shared-child guard leaves open on purpose.
    """
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    concept = 'Saldo a favor'
    if client is not None:
        concept = f'Saldo a favor {build_client_display_name(client)}'[:255]
    serializer = IncomeRecordCreateUpdateSerializer(
        data={
            'concept': concept,
            'kind': IncomeRecord.Kind.LIQUID,
            'period_date': data['period_date'],
            'destination': IncomeRecord.Destination.POCKET,
            'ledger': Ledger.COMPANY,
            'total_amount': excess,
            'client': client.pk if client is not None else None,
            'notes': '',
        },
        context={'settlement': True},
    )
    serializer.is_valid(raise_exception=True)
    return accounting_service.create_record(
        EntityType.INCOME, serializer, user,
        notify=False, shared_pocket_movement=movement,
    )


def _stamp_abono_ref(movement, children):
    """Trace the movement and every child back to the same abono."""
    source_ref = f'abono:{movement.pk}'
    PocketMovement.objects.filter(pk=movement.pk).update(source_ref=source_ref)
    movement.source_ref = source_ref
    IncomeRecord.objects.filter(
        pk__in=[child.pk for child in children],
    ).update(source_ref=source_ref)
    for child in children:
        child.source_ref = source_ref


def bulk_settle_expected_incomes(data, user):
    """One or several expected incomes, with the same financial rules."""
    from content.services.income_settlement_operation_service import settle_incomes
    return settle_incomes(data, user)
