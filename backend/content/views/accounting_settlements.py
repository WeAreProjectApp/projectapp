"""Session/CSRF endpoints for settlement preview and complete corrections."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from content.api_errors import error_response_from_exc
from content.models import IncomeSettlement
from content.permissions import IsSuperUser
from content.serializers.accounting import IncomeBulkSettlementSerializer
from content.services import income_settlement_operation_service as service
from content.services.entity_history import history_operation


def settlement_error(exc):
    return error_response_from_exc(exc, status=409 if isinstance(exc, service.SettlementConflict) else 400)


@api_view(['POST'])
@permission_classes([IsSuperUser])
def preview_income_settlement(request):
    serializer = IncomeBulkSettlementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        return Response(service.preview_settlement(serializer.validated_data))
    except ValueError as exc:
        return settlement_error(exc)


class SettlementRevisionSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1)


@transaction.non_atomic_requests
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsSuperUser])
def income_settlement_detail(request, settlement_id):
    operation = get_object_or_404(IncomeSettlement, pk=settlement_id)
    if request.method == 'GET':
        return Response(service.settlement_payload(operation))
    revision_serializer = SettlementRevisionSerializer(data=request.data)
    revision_serializer.is_valid(raise_exception=True)
    revision = revision_serializer.validated_data['revision']
    serializer = IncomeBulkSettlementSerializer(data=request.data) if request.method == 'PATCH' else None
    if serializer:
        serializer.is_valid(raise_exception=True)
    try:
        with history_operation(actor=request.user, source='http'):
            if request.method == 'DELETE':
                operation = service.reverse_settlement(operation.pk, request.user, revision)
            else:
                operation = service.update_settlement(operation.pk, serializer.validated_data, request.user, revision)['settlement']
    except ValueError as exc:
        return settlement_error(exc)
    return Response(service.settlement_payload(operation))
