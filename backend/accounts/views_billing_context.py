"""Thin billing context adapters, shared by JWT and session/CSRF routes."""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.serializers_billing_context import (
    BillingContextAssignmentSerializer, HostingEvidenceSerializer, HostingReconciliationSerializer,
)
from accounts.serializers_billing_read import BillingAccountDetailSerializer
from accounts.services.billing_access import require_billing_admin
from accounts.services.billing_context import associate_account, context_data
from accounts.services.billing_read import (
    account_for_actor, project_billing_options, project_hosting_list, project_hosting_read,
)
from accounts.services.hosting_context import hosting_inventory, reconcile_evidence, reconcile_hosting


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def billing_options_view(request, project_id):
    return Response(project_billing_options(project_id, request.user))


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def hosting_list_view(request):
    return Response(project_hosting_list(request.user))


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def hosting_read_view(request, project_id):
    return Response(project_hosting_read(project_id, request.user))


@api_view(['GET', 'PATCH'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def account_context_view(request, account_id):
    if request.method == 'GET':
        document = account_for_actor(account_id, request.user)
        return Response(context_data(getattr(document, 'billing_context', None)))
    require_billing_admin(request.user)
    serializer = BillingContextAssignmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(context_data(associate_account(account_id, request.user, serializer.validated_data)))


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def hosting_reconciliation_view(request, project_id):
    require_billing_admin(request.user)
    if request.method == 'GET':
        return Response(hosting_inventory(project_id, request.user))
    serializer = HostingReconciliationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(reconcile_hosting(project_id, request.user, serializer.validated_data,
                                      preview=request.query_params.get('preview') == '1'))


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def hosting_evidence_view(request, project_id):
    require_billing_admin(request.user)
    serializer = HostingEvidenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(reconcile_evidence(project_id, request.user, serializer.validated_data,
                                       preview=request.query_params.get('preview') == '1'))
