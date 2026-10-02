"""JWT client boundary, metadata projection and hostile input isolation."""

import json
import uuid

import pytest
from accounts.models import Project
from rest_framework.test import APIClient

from secure_links.models import SecureLink

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db


def base(project):
    """Return the owned secure-link collection URL for a project."""
    return f'/api/accounts/projects/{project.pk}/secure-links/'


def payload(**changes):
    """Build a valid client create payload with explicit caller overrides."""
    return {'request_id': str(uuid.uuid4()), 'title': 'Portal', 'secret_type': 'credentials', 'fields': CREDENTIALS, **changes}


def test_create_encrypts_the_payload(platform_client, project, client_profile):
    """Creating a managed link stores encrypted content and returns its first URL."""
    response = platform_client.post(base(project), payload(), format='json')

    link = SecureLink.objects.get(pk=response.data['link']['id'])
    assert response.status_code == 201
    assert (link.owner_id, link.client_id, link.project_id) == (client_profile.pk, client_profile.pk, project.pk)
    assert link.team_only is True
    assert token_from(response.data['url']) not in str(SecureLink.objects.values().get(pk=link.pk))
    assert CREDENTIALS['password'] not in str(SecureLink.objects.values().get(pk=link.pk))


def test_list_returns_only_metadata(platform_client, project, create_owned):
    """Listing links exposes metadata only and prevents cache retention."""
    link, url, _ = create_owned()

    response = platform_client.get(base(project))

    assert response.status_code == 200
    assert response.data['results'][0]['id'] == link.pk
    assert 'url' not in response.data['results'][0]
    assert 'fields' not in response.data['results'][0]
    assert token_from(url) not in json.dumps(response.data)
    assert CREDENTIALS['password'] not in json.dumps(response.data)
    assert response['Cache-Control'] == 'no-store, max-age=0'


def test_session_cookie_cannot_authenticate_platform(staff_client, project):
    """A Panel session cookie cannot authenticate a JWT Platform endpoint."""
    response = staff_client.get(base(project))

    assert response.status_code == 401
    assert response['Cache-Control'] == 'no-store, max-age=0'


def test_client_jwt_cannot_authenticate_panel(platform_client):
    """A Platform JWT cannot access the staff secure-link endpoint."""
    response = platform_client.get('/api/secure-links/')

    assert response.status_code == 403


def test_legacy_link_is_never_adopted(platform_client, project, client_profile, make_link):
    """A legacy link without an owner remains invisible to the client."""
    link, _ = make_link(project=project, client=client_profile)

    response = platform_client.get(f'{base(project)}{link.pk}/')

    assert response.status_code == 404
    assert platform_client.get(base(project)).data['count'] == 0


def test_wrong_project_cannot_read_own_link(platform_client, project, client_profile, create_owned):
    """A client cannot read a link through another one of its projects."""
    link, _, _ = create_owned()
    other = Project.objects.create(client=client_profile.user, name='Otro proyecto')

    response = platform_client.get(f'{base(other)}{link.pk}/')

    assert response.status_code == 404


@pytest.mark.parametrize('operation', ['', 'types/'])
def test_alien_project_is_hidden(platform_client, project, staff_user, operation):
    """A reassigned project is hidden for collection and catalog requests."""
    project.client = staff_user
    project.save(update_fields=['client'])

    response = platform_client.get(f'{base(project)}{operation}')

    assert response.status_code == 404


def test_history_omits_sensitive_details(platform_client, project, create_owned, staff_user):
    """History returns audited metadata without event secrets or tokens."""
    from secure_links import services
    from secure_links.models import SecureLinkEvent

    link, url, _ = create_owned()
    services.log_event(link, SecureLinkEvent.Kind.MCP_VIEWED, actor=staff_user, secret=CREDENTIALS['password'], token=url)

    response = platform_client.get(f'{base(project)}{link.pk}/events/')

    assert response.status_code == 200
    assert response.data['results'][0]['actor_kind'] == 'team'
    assert CREDENTIALS['password'] not in json.dumps(response.data)
    assert token_from(url) not in json.dumps(response.data)
    assert set(response.data['results'][0]) == {'id', 'kind', 'created_at', 'actor_kind', 'references'}


@pytest.mark.parametrize(('method', 'operation'), [('delete', ''), ('post', 'content/'), ('post', 'mark-sent/')])
def test_client_has_no_staff_operation(platform_client, project, create_owned, method, operation):
    """Client JWT routes cannot delete, alter content, or mark links sent."""
    link, _, _ = create_owned()

    response = getattr(platform_client, method)(f'{base(project)}{link.pk}/{operation}', {}, format='json')

    assert response.status_code in (404, 405)
    assert SecureLink.objects.filter(pk=link.pk).exists()


def test_unknown_input_is_not_echoed(platform_client, project):
    """Invalid client fields are rejected without echoing their secret names."""
    response = platform_client.post(base(project), payload(**{CREDENTIALS['password']: 'bad'}), format='json')

    assert response.status_code == 400
    assert CREDENTIALS['password'] not in json.dumps(response.data)
    assert not SecureLink.objects.exists()


def test_title_patch_cannot_replace_content(platform_client, project, create_owned):
    """A client title change cannot replace encrypted link content."""
    link, _, _ = create_owned()

    response = platform_client.patch(f'{base(project)}{link.pk}/', {
        'title': 'Otra etiqueta', 'expected_updated_at': link.updated_at.isoformat(), 'fields': {'password': 'different'},
    }, format='json')

    assert response.status_code == 400
    link.refresh_from_db()
    assert link.title == 'Acceso para el equipo'


def test_create_rate_limit_is_per_user(platform_client, project):
    """The eleventh create request for one client receives a rate limit."""
    for _ in range(10):
        platform_client.post(base(project), payload(), format='json')

    response = platform_client.post(base(project), payload(), format='json')

    assert response.status_code == 429
    assert response['Cache-Control'] == 'no-store, max-age=0'


def test_anonymous_jwt_endpoint_is_private(project):
    """An unauthenticated caller receives 401 and a non-cacheable response."""
    response = APIClient().get(base(project))

    assert response.status_code == 401
    assert response['Cache-Control'] == 'no-store, max-age=0'
