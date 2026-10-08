"""Project-locked resource writes using the existing delivery version and receipts."""
import hashlib
import json

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models import DeliveryOperation, DeliveryWorkspace, Project
from accounts.permissions import IsAdminRole
from accounts.services.delivery_access import (
    DeliveryConflict,
    fail,
    is_admin,
)


def is_resource_admin(actor, request=None):
    """REST keeps its Platform role; trusted MCP calls use their service principal."""
    if not actor.is_authenticated or not actor.is_active:
        return False
    if request is not None:
        return actor.pk == request.user.pk and IsAdminRole().has_permission(request, None)
    profile = getattr(actor, 'profile', None)
    if profile and profile.is_admin:
        return True
    from content.mcp.context import current_mcp_context
    context = current_mcp_context()
    return bool(is_admin(actor) and context and context.connector.slug == 'projects'
        and context.actor and context.actor.pk == actor.pk and context.credential
        and context.credential.is_usable and context.credential.actor_id == actor.pk
        and context.credential.connector_id == context.connector.pk)


def require_resource_admin(actor, request=None):
    if not is_resource_admin(actor, request):
        raise PermissionDenied('Solo los administradores pueden modificar este recurso.')


def project_for_resource_actor(project_id, actor, *, request=None, lock=False):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('Se requiere una cuenta activa.')
    query = Project.objects.select_related('client')
    if lock:
        query = query.select_for_update()
    admin = is_resource_admin(actor, request)
    if request is None and not admin:
        query = query.filter(client_id=actor.pk)
    project = query.filter(pk=project_id).first()
    if project is None:
        raise NotFound('Proyecto no encontrado.')
    if request is not None and not admin and project.client_id != actor.pk:
        raise PermissionDenied('No tienes acceso a este proyecto.')
    return project


def _fingerprint(value):
    if hasattr(value, 'chunks'):
        position = value.tell()
        value.seek(0)
        digest = hashlib.sha256()
        for chunk in value.chunks():
            digest.update(chunk)
        value.seek(position)
        return {'filename': value.name, 'size': value.size, 'sha256': digest.hexdigest()}
    if isinstance(value, dict):
        return {name: _fingerprint(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_fingerprint(item) for item in value]
    return value


def workspace_version(project):
    return DeliveryWorkspace.objects.filter(project=project).values_list('version', flat=True).first() or 0


@transaction.atomic
def perform(project_id, actor, operation, payload, change, *, expected_version=None,
            request_id=None, credential=None, expected_client_id=None, request=None):
    project = project_for_resource_actor(project_id, actor, lock=True, request=request)
    if expected_client_id is not None and expected_client_id != project.client_id:
        raise DeliveryConflict('El destinatario del proyecto cambió. Revisa de nuevo la operación.')
    workspace, _ = DeliveryWorkspace.objects.get_or_create(project=project)
    if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()
                                   or len(request_id) > 100):
        fail('Usa un identificador de petición de hasta cien caracteres.')
    digest = hashlib.sha256(json.dumps({
        'operation': operation, 'payload': _fingerprint(payload),
        'client_id': project.client_id, 'credential_id': getattr(credential, 'pk', None),
    }, sort_keys=True, default=str).encode()).hexdigest()
    if request_id:
        receipt = DeliveryOperation.objects.filter(project=project, request_id=request_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.fingerprint != digest:
                raise DeliveryConflict('El identificador ya corresponde a otra operación.')
            return receipt.response
    if expected_version is not None and (
        type(expected_version) is not int or expected_version != workspace.version
    ):
        raise DeliveryConflict()
    response = change(project)
    workspace.version += 1
    workspace.save(update_fields=['version'])
    if request_id:
        DeliveryOperation.objects.create(project=project, request_id=request_id, actor=actor,
                                         fingerprint=digest, response=response)
    return response
