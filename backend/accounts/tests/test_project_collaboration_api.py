"""Observable JWT and Panel boundaries for project collaboration APIs."""

from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models_project_ideas import ProjectIdea
from accounts.tests.project_collaboration_helpers import context, enable, sources

pytestmark = pytest.mark.django_db


def api(actor=None, *, impersonated_by=None):
    """Return a JWT API client for the requested test actor."""
    client = APIClient()
    if actor:
        token = RefreshToken.for_user(actor).access_token
        if impersonated_by:
            token['impersonated_by'] = impersonated_by
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


def url(c, suffix):
    """Return a project-scoped platform API URL for the test context."""
    return f'/api/accounts/projects/{c.project.pk}/{suffix}'


def test_unauthenticated_access_is_not_cached():
    """Fails if an anonymous access denial can be cached."""
    c = context()
    response = api().get(url(c, 'client-access/'))
    assert response.status_code == 401
    assert response['Cache-Control'] == 'no-store, max-age=0'


def test_cross_project_read_is_not_found():
    """Fails if a client can read collaboration data in another project."""
    c = context()
    response = api(c.other).get(url(c, 'ideas/'))
    assert response.status_code == 404


def test_cross_project_write_creates_no_idea():
    """Fails if a foreign project write persists a suggestion."""
    c = context()
    response = api(c.other).post(url(c, 'ideas/'), {'text': 'Forbidden', 'request_id': str(uuid4())}, format='json')
    assert response.status_code == 404
    assert ProjectIdea.objects.count() == 0


def test_client_cannot_modify_policy():
    """Fails if a client can change its own visibility policy."""
    c = context()
    response = api(c.client).patch(url(c, 'access/client-policy/'), {}, format='json')
    assert response.status_code == 403


def test_jwt_does_not_authenticate_panel():
    """Fails if a platform JWT authenticates a Panel session endpoint."""
    c = context()
    response = api(c.admin).get(f'/api/projects/{c.project.pk}/ideas/')
    assert response.status_code == 403


def test_panel_write_requires_csrf():
    """Fails if a Panel mutation accepts a request without CSRF."""
    c = context()
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(c.admin)
    response = client.post(f'/api/projects/{c.project.pk}/ideas/', {'text': 'Panel', 'request_id': str(uuid4())}, format='json')
    assert response.status_code == 403
    assert ProjectIdea.objects.count() == 0


def test_impersonated_client_cannot_create_idea():
    """Fails if an impersonated token can create a client suggestion."""
    c = context()
    response = api(c.client, impersonated_by=c.admin.pk).post(url(c, 'ideas/'), {'text': 'Impersonated', 'request_id': str(uuid4())}, format='json')
    assert response.status_code == 403
    assert ProjectIdea.objects.count() == 0


def test_impersonated_client_cannot_reveal_password():
    """Fails if an impersonated token can reveal a client credential."""
    c = context()
    sources(c)
    enable(c, 'production.admin_password')
    response = api(c.client, impersonated_by=c.admin.pk).post(url(c, 'client-access/environments/production/credentials/admin_password/reveal/'), {}, format='json')
    assert response.status_code == 403
    assert 'production-secret' not in response.content.decode()


def test_explicit_reveal_returns_only_selected_credential():
    """Fails if a credential reveal returns extra fields or is cacheable."""
    c = context()
    sources(c)
    enable(c, 'production.admin_password')
    response = api(c.client).post(url(c, 'client-access/environments/production/credentials/admin_password/reveal/'), {}, format='json')
    assert response.status_code == 200
    assert response.json() == {'secret': 'production-secret'}
    assert response['Cache-Control'] == 'no-store, max-age=0'


def test_client_list_contains_no_internal_data():
    """Fails if a client access listing exposes internal source data."""
    c = context()
    sources(c)
    enable(c, 'production.site_url', 'production.admin_password')
    response = api(c.client).get(url(c, 'client-access/'))
    assert response.json() == {'project_id': c.project.pk, 'environments': [
        {'environment': 'production', 'site_url': 'https://client.example.test/', 'credential_actions': ['admin_password']}]}


def test_project_detail_preserves_access_redaction():
    """Fails if project detail reveals internal access values to a client."""
    c = context()
    sources(c)
    enable(c, 'production.admin_password')
    response = api(c.client).get(url(c, ''))
    assert response.status_code == 200
    assert response.json()['can_view_client_access'] is True
    assert response.json()['production_url'] == ''
    assert 'Internal operations message' not in response.content.decode()
    assert 'production-user' not in response.content.decode()
    assert 'production-secret' not in response.content.decode()


def test_administrator_detail_does_not_load_client_grants():
    """Fails if the admin's detail reads grants for someone else's account."""
    c = context()
    sources(c)
    enable(c, 'production.admin_password')
    client = api(c.admin)
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url(c, ''))
    assert response.status_code == 200
    assert response.json()['can_view_client_access'] is False
    assert len(queries) <= 4


def test_client_cannot_read_access_events():
    """Fails if a client can read administrative access audit events."""
    c = context()
    response = api(c.client).get(url(c, 'access/client-policy/events/'))
    assert response.status_code == 403


def test_access_audit_contains_no_credential_values():
    """Fails if an audit event stores a revealed credential value."""
    c = context()
    sources(c)
    enable(c, 'production.admin_username')
    api(c.client).post(url(c, 'client-access/environments/production/credentials/admin_username/reveal/'), {}, format='json')
    response = api(c.admin).get(url(c, 'access/client-policy/events/'))
    assert response.status_code == 200
    assert response.json()['results'][0]['fields'] == ['production.admin_username']
    assert 'production-user' not in response.content.decode()
