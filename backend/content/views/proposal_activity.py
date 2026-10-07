"""Bounded administrative activity reads independent of the editor payload."""
from django.core import signing
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from content.models import BusinessProposal, ProposalChangeLog

CURSOR_SALT = 'proposal-activity-v1'


def activity_page(proposal_id, params):
    get_object_or_404(BusinessProposal, pk=proposal_id)
    try:
        size = int(params.get('page_size', 20))
        if not 1 <= size <= 50:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValidationError({'page_size': 'Usa un tamaño de página entre 1 y 50.'}) from exc
    logs = ProposalChangeLog.objects.filter(proposal_id=proposal_id)
    cursor = params.get('cursor')
    if cursor:
        try:
            value = signing.loads(cursor, salt=CURSOR_SALT)
            timestamp = parse_datetime(value['created_at'])
            if value['proposal_id'] != proposal_id or timestamp is None:
                raise ValueError
            logs = logs.filter(Q(created_at__lt=timestamp) | Q(created_at=timestamp, pk__lt=int(value['id'])))
        except (signing.BadSignature, ValueError, TypeError, KeyError) as exc:
            raise ValidationError({'cursor': 'El cursor de actividad no es válido para esta propuesta.'}) from exc
    entries = list(logs.order_by('-created_at', '-pk')[:size + 1])
    more = len(entries) > size
    entries = entries[:size]
    next_cursor = signing.dumps({'proposal_id': proposal_id, 'id': entries[-1].pk, 'created_at': entries[-1].created_at.isoformat()}, salt=CURSOR_SALT) if more else None
    fields = ('id', 'change_type', 'description', 'field_name', 'old_value', 'new_value', 'actor_type', 'created_at')
    return {'results': [{field: getattr(log, field) for field in fields} for log in entries], 'next_cursor': next_cursor, 'has_more': more}


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def list_proposal_activity(request, proposal_id):
    return Response(activity_page(proposal_id, request.query_params))
