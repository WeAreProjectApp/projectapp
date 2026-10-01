"""Public proposal interest list, separate from scope selection."""

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from content.models import BusinessProposal
from content.services.proposal_module_interests import (
    ModuleInterestsSerializer, interest_payload, save_module_interests,
)
from content.utils import is_staff_session
from content.throttles import TrackingAnonThrottle


@api_view(['GET', 'PUT'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TrackingAnonThrottle])
def proposal_module_interests(request, proposal_uuid):
    proposal = get_object_or_404(BusinessProposal, uuid=proposal_uuid, is_active=True)
    if proposal.is_expired:
        return Response({'error': 'Esta propuesta ha expirado.'}, status=410)
    if request.method == 'GET':
        response = Response(interest_payload(proposal))
        response['Cache-Control'] = 'private, no-store'
        return response
    if is_staff_session(request) or request.query_params.get('preview') == '1':
        return Response({**interest_payload(proposal), 'status': 'skipped'})
    serializer = ModuleInterestsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    proposal = save_module_interests(proposal.pk, serializer.validated_data['module_ids'])
    return Response(interest_payload(proposal))
