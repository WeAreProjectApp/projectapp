"""Observable field-level policy validation for client project access."""

import pytest
from rest_framework.exceptions import ValidationError

from accounts.services import project_client_access as access
from accounts.services.project_collaboration_access import CollaborationConflict
from accounts.tests.project_collaboration_helpers import context, enable, sources

pytestmark = pytest.mark.django_db


def test_default_projection_contains_no_access():
    """Fails if a project exposes access data without an explicit grant."""
    c = context()
    sources(c)
    assert access.client_access(c.project.pk, c.client) == {'project_id': c.project.pk, 'environments': []}


def test_granted_url_does_not_grant_django_fields():
    """Fails if granting a URL also exposes Django credentials."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'site_url': 'https://client.example.test/'}]


def test_credential_grants_emit_actions_without_values():
    """Fails if credential grants expose values instead of reveal actions."""
    c = context()
    sources(c)
    enable(c, 'production.admin_username', 'production.admin_password')
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'credential_actions': ['admin_username', 'admin_password']}]


def test_qa_grant_is_independent_of_production():
    """Fails if a QA grant also enables production access."""
    c = context()
    sources(c)
    enable(c, 'staging.site_url')
    assert access.preview_access(c.project.pk, c.admin)['environments'] == [
        {'environment': 'staging', 'site_url': 'https://qa.example.test/'}]


@pytest.mark.parametrize('url', ['https://user:secret@host.test/', 'https://host.test/?token=secret', 'https://host.test/#secret'])
def test_url_containing_credentials_is_unavailable(url):
    """Fails if URLs with embedded secrets can be granted."""
    c = context()
    c.project.production_url = url
    c.project.save()
    with pytest.raises(ValidationError):
        enable(c, 'production.site_url')


def test_unavailable_password_cannot_be_granted():
    """Fails if a missing password can appear as client access."""
    c = context()
    with pytest.raises(ValidationError):
        enable(c, 'production.admin_password')


def test_stale_source_token_rejects_new_grant():
    """Fails if a changed source accepts an old approval token."""
    c = context()
    sources(c)
    original = access.get_policy(c.project.pk, c.admin)
    c.project.production_url = 'https://different.example.test/'
    c.project.save()
    permissions = access.empty_matrix()
    permissions['production']['site_url'] = True
    with pytest.raises(CollaborationConflict):
        access.update_policy(c.project.pk, c.admin, {'source_token': original['source_token'], 'expected_version': 0, 'permissions': permissions})


def test_stale_policy_version_cannot_overwrite_grant():
    """Fails if a stale policy version overwrites a current grant."""
    c = context()
    sources(c)
    original = access.get_policy(c.project.pk, c.admin)
    enable(c, 'production.site_url')
    with pytest.raises(CollaborationConflict):
        access.update_policy(c.project.pk, c.admin, {
            'source_token': original['source_token'], 'expected_version': 0, 'permissions': access.empty_matrix()})


@pytest.mark.parametrize('value', ['false', 1, None])
def test_non_boolean_permissions_are_rejected(value):
    """Fails if a non-boolean field permission changes the policy."""
    c = context()
    original = access.get_policy(c.project.pk, c.admin)
    permissions = access.empty_matrix()
    permissions['production']['site_url'] = value
    with pytest.raises(ValidationError):
        access.update_policy(c.project.pk, c.admin, {'source_token': original['source_token'], 'expected_version': 0, 'permissions': permissions})
