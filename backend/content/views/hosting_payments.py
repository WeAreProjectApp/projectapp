"""Panel reads and confirmations scoped to the operating record of the project."""

from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from content.api_errors import error_response
from content.models import HostingRecord
from content.permissions import IsSuperUser
from content.serializers.accounting import HostingCycleSerializer, IncomeBulkSettlementSerializer
from content.serializers.hosting_payments import CycleReceiptInput, NextIncomeInput
from content.services import hosting_next_income
from content.services.accounting_expected_income_service import ExpectedIncomeError
from content.services.hosting_periods import HostingPeriods, MISSING_OWNER, PeriodConflict
from content.services.hosting_receipts import ReceiptEntry
from content.services.income_settlement_operation_service import preview_settlement, settle_incomes


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def next_income(request, record_id):
    record = get_object_or_404(HostingRecord, pk=record_id)
    query = NextIncomeInput(data=request.query_params if request.method == 'GET' else request.data)
    query.is_valid(raise_exception=True)
    data = query.validated_data
    try:
        if request.method == 'GET':
            return Response(hosting_next_income.next_income_plan(record, reference_income_id=data.get('reference_income_id')))
        if not data.get('version'):
            return error_response('Revisa y confirma el ingreso esperado antes de crearlo.')
        proposal, created = hosting_next_income.confirm_next_income(record.pk, data, actor=request.user)
        return Response(proposal, status=201 if created else 200)
    except (PeriodConflict, ExpectedIncomeError) as exc:
        return error_response(str(exc), status=409)


def _options(record):
    book = HostingPeriods(record.project_id, record_id=record.pk)
    candidates = [w.income for w in book.windows.values() if w.income] + book.unlinked_incomes
    result = []
    for income in sorted(candidates, key=lambda i: (i.period_start, i.pk), reverse=True):
        try:
            entry = ReceiptEntry(book, book.settlement_window(income))
            result.append({**entry.describe(), 'concept': income.concept})
        except PeriodConflict as exc:
            result.append({'income_id': income.pk, 'concept': income.concept, 'blocker': str(exc), 'state': 'blocked'})
    return result


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def cycle_receipt(request, record_id):
    record = get_object_or_404(HostingRecord, pk=record_id)
    if request.method == 'GET':
        try:
            return Response({'incomes': _options(record)})
        except PeriodConflict as exc:
            return Response({'incomes': [], 'blocker': str(exc)})
    form = CycleReceiptInput(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    entries = data['hosting_receipt']['entries']
    if len(entries) != 1 or entries[0]['hosting_record_id'] != record.pk or entries[0]['income_id'] != data['income_id']:
        return error_response(MISSING_OWNER)
    payload = {key: data[key] for key in ('hosting_receipt', 'request_id', 'destination', 'notes', 'preview_hash') if key in data}
    payload.update(income_ids=[data['income_id']], total_amount=data['amount'], period_date=data['paid_at'].isoformat(),
                   allocations=[{'income_id': data['income_id'], 'amount': data['amount']}])
    # Validate the exact same wire representation as the Ingresos adapter.
    payload['request_id'] = str(payload['request_id'])
    settlement = IncomeBulkSettlementSerializer(data=payload)
    settlement.is_valid(raise_exception=True)
    validated = dict(settlement.validated_data)
    validated['_hosting_cycle'] = {key: data[key] for key in ('modality', 'advance_validity', 'period_from', 'period_to') if key in data}
    try:
        if request.query_params.get('preview') == '1':
            return Response(preview_settlement(validated))
        if not data.get('preview_hash'):
            return error_response('Revisa y confirma el pago antes de registrarlo.')
        result = settle_incomes(validated, request.user)
        allocation = result['liquid'].hosting_allocation
        book = HostingPeriods(record.project_id, record_id=record.pk)
        window = book.for_income(allocation.period.income)
        return Response({'cycle': HostingCycleSerializer(allocation.cycle).data,
                         'allocation_id': allocation.pk, 'receipt_id': allocation.receipt_id, 'settlement_id': result['settlement_id'],
                         'already_registered': result.get('replayed', False),
                         'period': window.summary(book, paid_allocation=allocation)}, status=200 if result.get('replayed') else 201)
    except ValueError as exc:
        return error_response(str(exc), status=409)
