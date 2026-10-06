"""Panel billing context management: session authentication and CSRF."""
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from content.permissions import IsSuperUser
from accounts.serializers_billing_context import (
    BillingContextAssignmentSerializer, BillingContractLinkSerializer, HostingEvidenceSerializer, HostingReconciliationSerializer,
)
from accounts.services.billing_context import associate_account, context_data
from accounts.services.billing_read import account_for_actor, project_billing_options, project_hosting_read
from accounts.services.hosting_context import hosting_inventory, reconcile_evidence, reconcile_hosting


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def options(request, project_id):
    return Response(project_billing_options(project_id, request.user))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def link_contract(request, project_id):
    from accounts.services.billing_contracts import link_billing_contract
    serializer = BillingContractLinkSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(link_billing_contract(project_id, request.user, serializer.validated_data))


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def account_context(request, account_id):
    if request.method == 'GET':
        doc = account_for_actor(account_id, request.user)
        return Response(context_data(getattr(doc, 'billing_context', None)))
    serializer = BillingContextAssignmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(context_data(associate_account(account_id, request.user, serializer.validated_data)))


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def reconciliation(request, project_id):
    if request.method == 'GET':
        return Response({'inventory': hosting_inventory(project_id, request.user),
                         'overview': project_hosting_read(project_id, request.user)})
    serializer = HostingReconciliationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(reconcile_hosting(project_id, request.user, serializer.validated_data,
                                      preview=request.query_params.get('preview') == '1'))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperUser])
def evidence(request, project_id):
    serializer = HostingEvidenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(reconcile_evidence(project_id, request.user, serializer.validated_data,
                                       preview=request.query_params.get('preview') == '1'))
