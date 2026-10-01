"""Observable revocation guarantees for client access grants."""

import pytest
from rest_framework.exceptions import PermissionDenied

from accounts.models import Project, ProjectAdminAccess
from accounts.services import project_access
from accounts.services import project_client_access as access
from accounts.services.credential_cipher import encrypt_secret
from accounts.tests.project_collaboration_helpers import context, enable, sources

pytestmark = pytest.mark.django_db


def test_owner_change_clears_all_grants():
    """Fails if transferring a project leaves any grant for the new owner."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_password')
    c.project.client = c.other
    c.project.save(update_fields=['client'])
    assert access.client_access(c.project.pk, c.other)['environments'] == []


def test_original_owner_cannot_reveal_after_transfer():
    """Fails if the former owner can reveal a credential after transfer."""
    c = context()
    sources(c)
    enable(c, 'production.admin_password')
    c.project.client = c.other
    c.project.save()
    from rest_framework.exceptions import NotFound
    with pytest.raises(NotFound):
        access.reveal_credential(c.project.pk, c.client, 'production', 'admin_password', {})


def test_reverting_owner_does_not_restore_grants():
    """Fails if moving ownership back silently restores old grants."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    c.project.client = c.other
    c.project.save()
    c.project.client = c.client
    c.project.save()
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_panel_field_edit_revokes_only_changed_field():
    """Fails if changing one source revokes unrelated approved access."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_username')
    project_access.update_access_field(c.project, {'field': 'admin_username', 'environment': 'production', 'admin_username': 'new-user'}, c.admin)
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'site_url': 'https://client.example.test/'}]


def test_password_rotation_denies_old_grant():
    """Fails if rotating a password leaves its old grant usable."""
    c = context()
    source = sources(c)
    enable(c, 'production.admin_password')
    source.admin_password_encrypted = encrypt_secret('rotated-secret')
    source.save()
    with pytest.raises(PermissionDenied):
        access.reveal_credential(c.project.pk, c.client, 'production', 'admin_password', {})


def test_source_deletion_requires_new_grant():
    """Fails if recreating a deleted source restores its old grant."""
    c = context()
    source = sources(c)
    enable(c, 'production.admin_username')
    source.delete()
    ProjectAdminAccess.objects.create(project=c.project, environment='production', admin_username='production-user')
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_bulk_source_update_cannot_expose_new_value():
    """Fails if a bulk source edit exposes an unapproved URL."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    Project.objects.filter(pk=c.project.pk).update(production_url='https://unapproved.example.test/')
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_revoked_password_is_not_revealed():
    """Fails if removing a password grant still permits reveal."""
    c = context()
    sources(c)
    enable(c, 'production.admin_password')
    enable(c)
    with pytest.raises(PermissionDenied):
        access.reveal_credential(c.project.pk, c.client, 'production', 'admin_password', {})
