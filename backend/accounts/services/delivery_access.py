"""Shared ownership and conflict boundaries for REST and MCP delivery actions."""
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from accounts.models import Project
from accounts.services._platform_authority import platform_role_authority


class DeliveryConflict(APIException):
    status_code = 409
    default_detail = 'El seguimiento cambió. Actualiza antes de continuar.'
    default_code = 'delivery_conflict'


def fail(message, code='delivery_invalid'):
    raise ValidationError({'detail': message, 'code': code})


def is_admin(actor):
    profile = getattr(actor, 'profile', None)
    authority = platform_role_authority(actor)
    administrative = authority if authority is not None else (
        actor.is_staff or actor.is_superuser or (profile and profile.is_admin)
    )
    return bool(actor.is_authenticated and actor.is_active and administrative)


def require_admin(actor):
    if not is_admin(actor):
        raise PermissionDenied('Solo un administrador puede preparar o publicar el seguimiento.')


def project_for_actor(project_id, actor, *, lock=False):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('Se requiere una cuenta activa.')
    qs = Project.objects.select_related('client')
    if lock:
        qs = qs.select_for_update()
    if not is_admin(actor):
        qs = qs.filter(client=actor)
    project = qs.filter(pk=project_id).first()
    if project is None:
        raise NotFound('Proyecto no encontrado.')
    return project
