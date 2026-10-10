"""Factories for the client and project data-integrity rule tests."""
from decimal import Decimal

from django.contrib.auth import get_user_model

from accounts.models import Project, UserProfile
from content.models import (
    CommunicationThread, Document, DocumentFolder, DocumentState, HostingRecord, ProjectRetentionContext,
)


def set_state(project, system_key):
    """Move a project onto a seeded lifecycle state, mirror included, without transition side effects."""
    state = DocumentState.objects.get(catalog='projects', system_key=system_key)
    Project.objects.filter(pk=project.pk).update(current_state=state, status=system_key)
    project.refresh_from_db()
    return project


def drop_roots(project):
    """A historical project: its root folder and thread lose the managed link."""
    DocumentFolder.objects.filter(managed_project=project).update(managed_project=None)
    CommunicationThread.objects.filter(managed_project=project).update(managed_project=None)


def make_hosting(profile, **fields):
    values = {'client': profile, 'client_name': 'Ana - Kore', 'domain_url': 'kore.co',
              'monthly_value': Decimal('120000.00')}
    values.update(fields)
    return HostingRecord.objects.create(**values)


def make_document(user, title='Acta de inicio', **fields):
    return Document.objects.create(title=title, client_user=user, **fields)


def make_retention_context(profile, actor, name='Kore anterior', original_project_id=9001):
    return ProjectRetentionContext.objects.create(
        client=profile.user, original_project_id=original_project_id, project_name=name, created_by=actor,
    )


def make_user(username, role=None):
    """A user that is not a client: no profile at all, or a profile with another role."""
    user = get_user_model().objects.create_user(username=username, email=f'{username}@example.com')
    if role:
        UserProfile.objects.create(user=user, role=role)
    return user
