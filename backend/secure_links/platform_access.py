"""Fail-closed ownership boundary; legacy links are never adopted implicitly."""

from accounts.models import Project, UserProfile
from rest_framework.permissions import BasePermission

from .models import SecureLink
from .services import SecureLinkError


class IsActiveSecureLinkClient(BasePermission):
    message = 'Esta cuenta no puede administrar enlaces seguros.'

    def has_permission(self, request, view):
        profile = getattr(request.user, 'profile', None)
        return bool(
            request.user.is_authenticated and request.user.is_active and profile
            and profile.is_client and profile.is_onboarded and profile.archived_at is None
        )


def not_found():
    return SecureLinkError('Este recurso no está disponible.', code='not_found', status=404)


def owned_project(owner_id, project_id, *, lock=False):
    """Lock the project before links on writes, including administrative MCP writes."""
    profiles = UserProfile.objects.select_related('user')
    owner = profiles.filter(
        pk=owner_id, role=UserProfile.ROLE_CLIENT, archived_at__isnull=True,
        user__is_active=True, is_onboarded=True,
    ).first()
    if owner is None:
        raise not_found()
    projects = Project.objects.all()
    if lock:
        projects = projects.select_for_update()
    project = projects.filter(pk=project_id, client_id=owner.user_id).first()
    if project is None:
        raise not_found()
    return owner, project


def owned_links(owner, project):
    return SecureLink.objects.filter(
        owner=owner, client=owner, project=project,
        audience=SecureLink.Audience.TEAM, origin=SecureLink.Origin.PLATFORM,
    ).select_related('replaced_by')


def owned_link(owner, project, link_id, *, lock=False):
    query = owned_links(owner, project)
    # Do not lock the nullable reverse OneToOne join (unsupported by PostgreSQL).
    if lock:
        query = query.select_related(None).select_for_update()
    link = query.filter(pk=link_id).first()
    if link is None:
        raise not_found()
    return link
