"""Explicit administrative project corrections, separate from approval review."""
from datetime import date

from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from content.services.proposal_project_reassignment import preview_reassignment, reassign_proposal


def _hosting_options(params):
    """Optional hosting decision for a due phase joining an active subscription."""
    raw = params.get('hosting_start_date')
    try:
        start = date.fromisoformat(raw) if raw else None
    except (TypeError, ValueError) as exc:
        raise ValidationError({'hosting_start_date': 'Usa una fecha AAAA-MM-DD.'}) from exc
    accept = str(params.get('accept_hosting_start', '')).lower() in ('1', 'true')
    return {'hosting_start_date': start, 'accept_hosting_start': accept}


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
    return Response(preview_reassignment(proposal_id, target, **_hosting_options(request.query_params)))
