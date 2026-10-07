"""Session-only, read-only client consultation of explicitly retained records."""
from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import UserProfile
from accounts.services.credential_cipher import decrypt_secret
from content.models import ProjectRetentionContext
from content.services.project_deletion_catalog import CATEGORIES
from content.services.project_retention_service import retained_record_payload
from content.services.retention_audit import audit_payload

PAGE_SIZE = 50


def _page(request):
    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        raise ValidationError({'page': 'Indica un número de página.'})
    if page < 1:
        raise ValidationError({'page': 'La página debe ser mayor que cero.'})
    return page


def _private_response(data):
    response = Response(data)
    response['Cache-Control'] = 'no-store'
    return response


def _categories(context):
    return [{**CATEGORIES[label], 'count': count}
            for label, count in context.category_counts.items() if label in CATEGORIES]


def _context(client_id, context_id):
    profile = get_object_or_404(UserProfile.objects.clients(), pk=client_id)
    return get_object_or_404(ProjectRetentionContext, pk=context_id, client_id=profile.user_id)


def _record(context, category_key, record_id):
    label = next((label for label, category in CATEGORIES.items() if category['key'] == category_key), None)
    if label is None or str(record_id) not in context.retained_records.get(label, []):
        raise NotFound('Ese dato no pertenece a esta consulta.')
    model = apps.get_model(label)
    try:
        return get_object_or_404(model._base_manager, pk=record_id)
    except (ValueError, DjangoValidationError):
        raise NotFound('Ese dato no existe.')


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def client_retained_project_data(request, client_id):
    profile = get_object_or_404(UserProfile.objects.clients(), pk=client_id)
    contexts = ProjectRetentionContext.objects.filter(client_id=profile.user_id)
    context_id = request.query_params.get('context')
    page = _page(request)
    if not context_id:
        total = contexts.count()
        contexts = contexts.defer('retained_records')[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        return _private_response({'contexts': [{
            'id': ctx.pk, 'project_name': ctx.project_name, 'created_at': ctx.created_at,
            'categories': _categories(ctx),
        } for ctx in contexts], 'count': total, 'page': page})
    try:
        context = get_object_or_404(contexts, pk=int(context_id))
    except (ValueError, TypeError):
        raise NotFound('Esa consulta no existe.')
    key = request.query_params.get('category', '')
    label = next((label for label, category in CATEGORIES.items() if category['key'] == key), None)
    if label is None:
        raise ValidationError({'category': 'Elige una categoría válida.'})
    rows = apps.get_model(label)._base_manager.filter(pk__in=context.retained_records.get(label, [])).order_by('pk')
    return _private_response({'count': rows.count(), 'page': page,
                             'results': [retained_record_payload(row) for row in rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]]})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def retained_project_file(request, client_id, context_id, category, record_id, field_name):
    row = _record(_context(client_id, context_id), category, record_id)
    field = next((field for field in row._meta.concrete_fields
                  if field.name == field_name and isinstance(field, models.FileField)), None)
    if field is None or not getattr(row, field.name):
        raise NotFound('Ese archivo no existe.')
    value = getattr(row, field.name)
    try:
        response = FileResponse(value.open('rb'), as_attachment=True, filename=value.name.rsplit('/', 1)[-1])
    except FileNotFoundError:
        raise NotFound('El archivo ya no está disponible.')
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def reveal_retained_project_secret(request, client_id, context_id, category, record_id):
    row = _record(_context(client_id, context_id), category, record_id)
    field = {'accounts.projectadminaccess': 'admin_password_encrypted',
             'accounts.projectaccessnote': 'content_encrypted'}.get(row._meta.label_lower)
    if field is None:
        raise PermissionDenied('Este dato no admite revelar credenciales.')
    response = Response({'value': decrypt_secret(getattr(row, field))})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def retained_project_data_audit(request):
    """Every retention context with live counts per category, for all clients."""
    client_profile_id = request.query_params.get('client_profile_id')
    if client_profile_id not in (None, ''):
        try:
            client_profile_id = int(client_profile_id)
        except (TypeError, ValueError):
            raise ValidationError({'client_profile_id': 'Indica el número del perfil de cliente.'})
    else:
        client_profile_id = None
    integrity = request.query_params.get('integrity', '').lower() in ('1', 'true')
    return _private_response(audit_payload(
        page=_page(request), client_profile_id=client_profile_id, integrity=integrity,
    ))
