"""Hardening checks for granular client access and permanent revocation."""

from unittest.mock import patch

import pytest
from django.core import signing

from accounts.services import project_client_access as access
from accounts.services.project_collaboration_access import CollaborationConflict
from accounts.tests.project_collaboration_helpers import context, enable, sources
from accounts.tests.test_project_collaboration_api import api, url

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(('environment', 'field'), [
    ('production', 'site_url'), ('production', 'admin_url'),
    ('production', 'admin_username'), ('production', 'admin_password'),
    ('staging', 'site_url'), ('staging', 'admin_url'),
    ('staging', 'admin_username'), ('staging', 'admin_password'),
])
def test_each_access_grant_exposes_only_its_selected_field(environment, field):
    """Fails if one grant discloses a sibling field or environment."""
    from accounts.models import ProjectAdminAccess
    from accounts.services.credential_cipher import encrypt_secret
    c = context()
    sources(c)
    ProjectAdminAccess.objects.create(project=c.project, environment='staging',
        admin_url='https://qa.example.test/admin/', admin_username='qa-user',
        admin_password_encrypted=encrypt_secret('qa-secret'))
    enable(c, f'{environment}.{field}')
    entry = access.client_access(c.project.pk, c.client)['environments'][0]
    expected_key = {'site_url': 'site_url', 'admin_url': 'admin_url',
                    'admin_username': 'credential_actions', 'admin_password': 'credential_actions'}[field]
    assert set(entry) == {'environment', expected_key}
    assert entry['environment'] == environment


@pytest.mark.parametrize('token_change', ['tampered', 'expired'])
def test_invalid_source_token_leaves_the_policy_hidden(token_change):
    """Fails if tampered or expired source approval changes visibility."""
    c = context()
    sources(c)
    policy = access.get_policy(c.project.pk, c.admin)
    tokens = {'tampered': policy['source_token'] + 'changed', 'expired': policy['source_token']}
    timestamps = {'tampered': signing.time.time(), 'expired': signing.time.time() + 1801}
    permissions = access.empty_matrix()
    permissions['production']['site_url'] = True
    with patch('django.core.signing.time.time', return_value=timestamps[token_change]):
        with pytest.raises(CollaborationConflict):
            access.update_policy(c.project.pk, c.admin, {
                'expected_version': 0, 'source_token': tokens[token_change], 'permissions': permissions})
    assert access.client_access(c.project.pk, c.client)['environments'] == []


@pytest.mark.parametrize(('role', 'status'), [('client', 403), ('other', 404)])
def test_denied_credential_responses_are_never_cached(role, status):
    """Fails if denied credential responses can be stored by a client."""
    c = context()
    response = api(getattr(c, role)).post(url(c, 'client-access/environments/production/credentials/admin_password/reveal/'), {}, format='json')
    assert response.status_code == status
    assert response['Cache-Control'] == 'no-store, max-age=0'


def test_moving_a_source_back_to_its_environment_requires_a_new_grant():
    """Fails if returning a source to its environment restores approval."""
    c = context()
    source = sources(c)
    enable(c, 'production.admin_username')
    source.environment = 'staging'
    source.save(update_fields=['environment'])
    source.environment = 'production'
    source.save(update_fields=['environment'])
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_moving_a_source_back_to_its_project_requires_a_new_grant():
    """Fails if returning a source to its project restores approval."""
    c = context()
    source = sources(c)
    enable(c, 'production.admin_username')
    source.project = c.other_project
    source.save(update_fields=['project'])
    source.project = c.project
    source.save(update_fields=['project'])
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_unpersisted_source_changes_do_not_revoke_a_grant():
    """Fails if an unrelated save revokes an unchanged access grant."""
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    c.project.production_url = 'https://unpersisted.example.test/'
    c.project.name = 'Actualización de nombre'
    c.project.save(update_fields=['name'])
    assert access.client_access(c.project.pk, c.client)['environments'] == [
        {'environment': 'production', 'site_url': 'https://client.example.test/'}]


def test_bulk_owner_reversal_does_not_restore_the_original_grant():
    """Fails if bulk owner reversal restores the original access grant."""
    from accounts.models import Project
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    Project.objects.filter(pk=c.project.pk).update(client=c.other)
    Project.objects.filter(pk=c.project.pk).update(client=c.client)
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_bulk_url_reversal_requires_a_new_grant():
    """Fails if bulk URL reversal restores access without a new grant."""
    from accounts.models import Project
    c = context()
    sources(c)
    enable(c, 'production.site_url')
    Project.objects.filter(pk=c.project.pk).update(production_url='https://changed.example.test/')
    Project.objects.filter(pk=c.project.pk).update(production_url='https://client.example.test/')
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_bulk_credential_reversal_requires_a_new_grant():
    """Fails if bulk password reversal restores reveal without a new grant."""
    from accounts.models import ProjectAdminAccess
    from accounts.services.credential_cipher import encrypt_secret
    c = context()
    source = sources(c)
    original = source.admin_password_encrypted
    enable(c, 'production.admin_password')
    ProjectAdminAccess.objects.filter(pk=source.pk).update(admin_password_encrypted=encrypt_secret('changed-secret'))
    ProjectAdminAccess.objects.filter(pk=source.pk).update(admin_password_encrypted=original)
    assert access.client_access(c.project.pk, c.client)['environments'] == []
