"""Admin-only history; the durable identity also resolves deleted records."""

import difflib

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from content.models.entity_history import EntityHistory, EntityRevision
from content.services.entity_history import changes_between
from content.services.entity_history_registry import ENTITIES, canonical_type, entity_model, field_labels


def _scope(kind, object_id, request):
    if kind not in ('document', 'proposal', 'project', 'client') and not request.user.is_superuser:
        raise PermissionDenied('Este historial requiere acceso a Contabilidad.')
    kind = canonical_type(kind)
    if kind not in ENTITIES:
        raise ValidationError({'entity_type': 'Tipo de registro no válido.'})
    history = EntityHistory.objects.filter(entity_type=kind, object_id=object_id).first()
    if history is None:
        get_object_or_404(entity_model(kind), pk=object_id)
    return history


def _summary(row):
    return {
        'id': row.pk, 'number': row.number, 'occurred_at': row.occurred_at,
        'action': row.action, 'actor': row.actor_label, 'source': row.source,
        'complete': row.number is not None,
        'fields': row.changed_fields,
        'evidence': row.evidence,
    }


def _version(history, pk):
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        raise ValidationError({'version': 'Selecciona una versión válida.'})
    return get_object_or_404(EntityRevision.objects.exclude(action='prepared_version'), history=history, pk=pk)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def entity_history_list(request, entity_type, object_id):
    history = _scope(entity_type, object_id, request)
    try:
        page = int(request.query_params.get('page', 1))
        if page < 1:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError({'page': 'Página no válida.'})
    order = request.query_params.get('order', 'recent')
    if order not in ('recent', 'oldest'):
        raise ValidationError({'order': 'Orden no válido.'})
    qs = EntityRevision.objects.filter(history=history).exclude(action='prepared_version').defer('snapshot', 'secrets', 'changes')
    latest = qs.exclude(action='baseline').order_by('-occurred_at', '-id').first()
    ordering = ('occurred_at', 'id') if order == 'oldest' else ('-occurred_at', '-id')
    rows = qs.order_by(*ordering)[(page - 1) * 20:page * 20]
    count = qs.count()
    result = {
        'results': [_summary(row) for row in rows], 'count': count,
        'page': page, 'num_pages': max(1, (count + 19) // 20),
        'object_label': history.object_label if history else '',
        'latest_change': _summary(latest) if latest else None,
        'last_sent_version': None,
    }
    if canonical_type(entity_type) == 'proposal':
        # An exact sent snapshot is an explicit marker, not an inference from status.
        sent = qs.filter(action='sent_version').order_by('-occurred_at', '-id').first()
        result['last_sent_version'] = _summary(sent) if sent else None
    return Response(result)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def entity_history_version(request, entity_type, object_id, revision_id):
    row = _version(_scope(entity_type, object_id, request), revision_id)
    previous = EntityRevision.objects.filter(
        history=row.history, number__lt=row.number,
    ).order_by('-number').first() if row.number else None
    return Response({**_summary(row), 'snapshot': row.snapshot, 'changes': row.changes,
                     'labels': field_labels(),
                     'protected_fields': list(row.secrets),
                     'previous_id': previous.pk if previous else None})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def entity_history_compare(request, entity_type, object_id):
    history = _scope(entity_type, object_id, request)
    left = _version(history, request.query_params.get('from'))
    right = _version(history, request.query_params.get('to'))
    if left.snapshot is None or right.snapshot is None:
        raise ValidationError({'version': 'Este evento antiguo no contiene una versión completa.'})
    from content.services.entity_history import _secret_changes
    changes = changes_between(left.snapshot, right.snapshot)
    protected = _secret_changes(left.secrets, right.secrets)
    paths = {c['field'] for c in protected}
    changes = [c for c in changes if c['field'] not in paths] + protected
    for change in changes:
        if (isinstance(change['old'], str) and isinstance(change['new'], str)
                and len(change['old']) + len(change['new']) <= 200_000):
            change['lines'] = list(difflib.unified_diff(
                change['old'].splitlines(), change['new'].splitlines(),
                fromfile='Anterior', tofile='Posterior', lineterm='',
            ))
    return Response({'from': _summary(left), 'to': _summary(right), 'changes': changes})


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def entity_history_reveal(request, entity_type, object_id, revision_id):
    from accounts.services.credential_cipher import _get_cipher
    from cryptography.fernet import InvalidToken

    row = _version(_scope(entity_type, object_id, request), revision_id)
    field = request.data.get('field')
    if not isinstance(field, str) or field not in row.secrets:
        raise ValidationError({'field': 'Campo protegido no disponible en esta versión.'})
    token = row.secrets[field]
    try:
        secret = _get_cipher().decrypt(token.encode()).decode() if token else ''
    except (InvalidToken, ValueError):
        return Response({'detail': 'No se puede descifrar esta versión.'}, status=409,
                        headers={'Cache-Control': 'no-store'})
    return Response({'secret': secret}, headers={'Cache-Control': 'no-store, max-age=0',
                                                'Pragma': 'no-cache'})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def entity_history_file(request, entity_type, object_id, revision_id):
    kind = canonical_type(entity_type)
    row = _version(_scope(entity_type, object_id, request), revision_id)
    field_name = {'document': 'generated_file', 'statement': 'pdf_file', 'proposal': 'generated_file'}.get(kind)
    if (kind == 'document' and (row.snapshot or {}).get('uploaded_pdf')
            and not (row.snapshot or {}).get('generated_file')):
        field_name = 'uploaded_pdf'
    name = (row.snapshot or {}).get('archived_pdf' if kind == 'proposal' else field_name)
    if not name or not field_name:
        raise Http404('Esta versión no contiene un archivo guardado.')
    storage = entity_model('document' if kind == 'proposal' else kind)._meta.get_field(field_name).storage
    try:
        stream = storage.open(name, 'rb')
    except FileNotFoundError:
        raise Http404('El archivo histórico no está disponible.')
    response = FileResponse(stream, content_type='application/pdf')
    response['Cache-Control'] = 'no-store'
    return response
