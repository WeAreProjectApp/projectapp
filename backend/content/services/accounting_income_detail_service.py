"""Shared read payload for one income and its complete payment history."""
from content.models import Document, IncomeRecord
from content.serializers.accounting import (
    ExpenseRecordSerializer,
    IncomeRecordSerializer,
    LiquidSettlementSerializer,
)
from content.services import accounting_service


def income_detail_queryset():
    """Efficient queryset for a payment-aware expected-income detail."""
    return (
        IncomeRecord.objects
        .select_related('client', 'client__user', 'project')
        .annotate(paid_amount=accounting_service.paid_amount_subquery())
    )


def build_income_detail_payload(income):
    """Serialize an income with payments, deductions and collection account."""
    children = (
        income.liquid_records
        .filter(kind=IncomeRecord.Kind.LIQUID)
        .select_related('client', 'client__user', 'project', 'pocket_movement')
        .prefetch_related('pocket_movement__income_records')
        .order_by('period_date', 'id')
    )
    deductions = (
        income.deduction_records
        .exclude(deduction_type='')
        .order_by('period_date', 'id')
    )
    collection_account = (
        income.collection_documents
        .select_related('collection_account')
        .exclude(commercial_status=Document.CommercialStatus.CANCELLED)
        .order_by('-created_at')
        .first()
    )
    return {
        'income': IncomeRecordSerializer(income).data,
        'liquid': LiquidSettlementSerializer(children, many=True).data,
        'expenses': ExpenseRecordSerializer(deductions, many=True).data,
        'collection_account': {
            'id': collection_account.pk,
            'public_number': collection_account.public_number,
            'commercial_status': collection_account.commercial_status,
            'total': collection_account.total,
            'tax_total': collection_account.tax_total,
            'subtotal': collection_account.subtotal,
            'vat_rate': getattr(getattr(collection_account, 'collection_account', None), 'vat_rate', None),
            'issue_date': collection_account.issue_date,
            'due_date': collection_account.due_date,
        } if collection_account else None,
    }
