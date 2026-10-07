"""Explicit administrative project corrections, separate from approval review."""
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from content.services.proposal_project_reassignment import preview_reassignment, reassign_proposal


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def proposal_project_reassignment(request, proposal_id):
    if request.method == 'POST':
        return Response(reassign_proposal(proposal_id, request.data, actor=request.user))
    try:
        target = int(request.query_params.get('target_project_id'))
        if target < 1:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValidationError({'target_project_id': 'Selecciona un proyecto de destino válido.'}) from exc
    return Response(preview_reassignment(proposal_id, target))
