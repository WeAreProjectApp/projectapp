"""On-demand pocket detail, shared by the panel and MCP single-record read."""
from decimal import Decimal

from django.db.models import Prefetch, Q, Sum

from content.models import IncomeRecord, PocketMovement
from content.serializers.accounting import (
    IncomeRecordSerializer, PocketMovementSerializer, money_str,
)
from content.services import accounting_service


def pocket_detail_queryset():
    return PocketMovement.objects.select_related('expense_record').prefetch_related(
        Prefetch('income_records', queryset=IncomeRecord.objects.order_by('pk')),
    )


def balance_after(movement):
    """Unfiltered chronological balance, with a deterministic final tie-break."""
    preceding = (
        Q(movement_date__lt=movement.movement_date)
        | Q(movement_date=movement.movement_date, created_at__lt=movement.created_at)
        | Q(movement_date=movement.movement_date, created_at=movement.created_at,
            pk__lte=movement.pk)
    )
    totals = PocketMovement.objects.filter(preceding).aggregate(
        incoming=Sum('amount', filter=Q(direction=PocketMovement.Direction.IN)),
        outgoing=Sum('amount', filter=Q(direction=PocketMovement.Direction.OUT)),
    )
    return money_str((totals['incoming'] or Decimal('0'))
                     - (totals['outgoing'] or Decimal('0')))


def build_pocket_detail_payload(movement):
    """Keep the list serializer lean; enrich only an explicitly opened detail.

    Expected parents are annotated in one query, including all their payments
    and deductions. A later payment changes the *current* pending amount, not
    the amount this movement allocated. No historical pending is inferred.
    """
    payload = dict(PocketMovementSerializer(movement).data)
    children = movement.income_children
    parent_ids = {child.expected_income_id for child in children
                  if child.expected_income_id}
    parents = {
        parent.pk: parent for parent in IncomeRecord.objects.filter(pk__in=parent_ids)
        .annotate(paid_amount=accounting_service.paid_amount_subquery())
    }
    income_serializer = IncomeRecordSerializer()
    allocations = []
    for child in children:
        parent = parents.get(child.expected_income_id)
        allocations.append({
            'income_id': child.pk,
            'expected_income_id': child.expected_income_id,
            'concept': parent.concept if parent else child.concept,
            'amount': money_str(child.total_amount),
            'pending_amount': income_serializer.get_pending_amount(parent) if parent else None,
            'is_credit': parent is None and child.source_ref.startswith('abono:'),
        })
    expense = getattr(movement, 'expense_record', None)
    linked = None
    if expense is not None:
        linked = {'type': 'expense', 'id': expense.pk, 'concept': expense.concept,
                  'category_label': expense.get_category_display()}
    elif len(children) == 1:
        child = children[0]
        linked = {'type': 'income', 'id': child.pk, 'concept': child.concept}
    payload.update({
        'running_balance': balance_after(movement),
        'linked_record_detail': linked,
        'allocation_details': allocations,
    })
    return payload
