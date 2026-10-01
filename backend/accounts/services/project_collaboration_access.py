"""Role and project boundaries shared by ideas and explicit access grants."""
from django.core.paginator import Paginator
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from accounts.models import Project


class CollaborationConflict(APIException):
    status_code = 409
    default_detail = 'Los datos cambiaron. Actualiza antes de continuar.'
    default_code = 'project_collaboration_conflict'


def is_admin(actor, channel='platform'):
    if not actor or not actor.is_authenticated or not actor.is_active:
        return False
    if channel == 'panel':
        return bool(actor.is_staff)
    profile = getattr(actor, 'profile', None)
    return bool(profile and profile.is_admin)


def require_admin(actor, channel='platform'):
    if not is_admin(actor, channel):
        raise PermissionDenied('Solo un administrador puede realizar esta operación.')


def project_for_actor(project_id, actor, *, channel='platform', admin=False, lock=False):
    if not actor or not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('Se requiere una cuenta activa.')
    privileged = is_admin(actor, channel)
    if admin:
        require_admin(actor, channel)
    qs = Project.objects.select_related('client')
    if lock:
        qs = qs.select_for_update()
    if not privileged:
        profile = getattr(actor, 'profile', None)
        if not profile or not profile.is_client:
            raise PermissionDenied('Se requiere una cuenta de cliente.')
        qs = qs.filter(client_id=actor.pk)
    project = qs.filter(pk=project_id).first()
    if project is None:
        raise NotFound('Proyecto no encontrado.')
    return project


def actor_label(actor, *, team=False):
    return (actor.get_full_name().strip() or ('Equipo' if team else 'Cliente'))[:255]


def paginate(qs, page, serialize):
    try:
        value = int(page)
    except (TypeError, ValueError):
        raise ValidationError({'page': 'Página no válida.'})
    if isinstance(page, bool) or value < 1:
        raise ValidationError({'page': 'Página no válida.'})
    paginator = Paginator(qs, 20)
    return {'results': [serialize(item) for item in paginator.get_page(value)], 'count': paginator.count, 'page': min(value, paginator.num_pages)}


def check_version(instance, expected):
    if instance.version != expected:
        raise CollaborationConflict()
