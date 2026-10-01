"""Permanent revocation through real Django Admin project writes."""

import pytest
from content.admin import admin_site
from django.db import IntegrityError
from django.test import RequestFactory

from accounts.admin import ProjectAdmin
from accounts.models import Project
from accounts.models_project_client_access import ProjectClientAccessEvent
from accounts.services import project_client_access as access
from accounts.tests.project_collaboration_helpers import context, enable, sources

pytestmark = pytest.mark.django_db


def save_project(c, **changes):
    """Save a changed project through its actual registered Admin class."""
    project = Project.objects.get(pk=c.project.pk)
    for field, value in changes.items():
        setattr(project, field, value)
    request = RequestFactory().post('/admin/accounts/project/')
    request.user = c.admin
    ProjectAdmin(Project, admin_site).save_model(request, project, form=None, change=True)


def test_admin_owner_reversal_keeps_permissions_revoked():
    """Fails if moving ownership back restores previous access permission."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_password')
    save_project(c, client_id=c.other.pk)
    save_project(c, client_id=c.client.pk)
    assert access.client_access(c.project.pk, c.client)['environments'] == []


@pytest.mark.parametrize(('field', 'environment', 'original'), [
    ('production_url', 'production', 'https://client.example.test/'),
    ('staging_url', 'staging', 'https://qa.example.test/'),
])
def test_admin_url_reversal_keeps_its_permission_revoked(field, environment, original):
    """Fails if returning a product URL silently restores its approval."""
    c = context()
    sources(c)
    enable(c, f'{environment}.site_url')
    save_project(c, **{field: 'https://changed.example.test/'})
    save_project(c, **{field: original})
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_admin_url_change_preserves_unaffected_permissions():
    """Fails if a product URL change revokes a sibling credential grant."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_username')
    save_project(c, production_url='https://changed.example.test/')
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'credential_actions': ['admin_username']}]


def test_admin_rename_preserves_permissions():
    """Fails if renaming a project revokes unchanged access permission."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    save_project(c, name='Nombre corregido')
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'site_url': 'https://client.example.test/'}]


def test_admin_owner_change_audits_original_recipient():
    """Fails if an ownership revocation records the replacement recipient."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_password')
    save_project(c, client_id=c.other.pk)
    event = ProjectClientAccessEvent.objects.get(action='grants_revoked', project=c.project)
    assert event.recipient_id == c.client.pk
    assert event.actor_id == c.admin.pk
    assert event.fields == ['production.site_url', 'production.admin_password']


def test_admin_failed_save_preserves_permissions():
    """Fails if a rejected database write leaves access approval revoked."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    with pytest.raises(IntegrityError):
        save_project(c, name=None, production_url='https://rejected.example.test/')
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'site_url': 'https://client.example.test/'}]


def test_admin_failed_save_leaves_no_revocation_event():
    """Fails if a rolled-back admin write leaves a revocation audit row."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    with pytest.raises(IntegrityError):
        save_project(c, name=None, production_url='https://rejected.example.test/')
    assert not ProjectClientAccessEvent.objects.filter(action='grants_revoked', project=c.project).exists()
