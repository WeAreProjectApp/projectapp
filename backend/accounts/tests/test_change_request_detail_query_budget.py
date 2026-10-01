"""Response and query-budget contracts for change-request detail."""

from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from decimal import Decimal

import pytest
from content.models import BusinessProposal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import (
    ChangeRequest,
    ChangeRequestComment,
    Project,
    UserProfile,
)
from accounts.serializers import ChangeRequestDetailSerializer

User = get_user_model()
MAX_CHANGE_REQUEST_DETAIL_QUERIES = 5


def _detail_url(project_id, change_request_id):
    return f'/api/accounts/projects/{project_id}/change-requests/{change_request_id}/'


def _comment_authors(count, *, start=0):
    return User.objects.bulk_create([
        User(
            username=f'change-detail-author-{index}@example.com',
            email=f'change-detail-author-{index}@example.com',
            first_name=f'Author{index}',
            password='unused',
        )
        for index in range(start, start + count)
    ])


def _comments(change_request, authors, *, start=0):
    return ChangeRequestComment.objects.bulk_create([
        ChangeRequestComment(
            change_request=change_request,
            user=author,
            content=f'Comment {index}',
            is_internal=index % 2 == 0,
        )
        for index, author in enumerate(authors, start=start)
    ])


def _captured_sql(queries):
    return '\n'.join(query['sql'].lower() for query in queries)


@pytest.fixture
def api_client():
    """Provide an API client for JWT-authenticated detail requests."""
    return APIClient()


@pytest.fixture
def users_and_headers(api_client):
    """Create the administrator and owning client used by detail contracts."""
    admin = User.objects.create_user(
        username='change-detail-admin@example.com',
        email='change-detail-admin@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username='change-detail-client@example.com',
        email='change-detail-client@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    admin_login = api_client.post('/api/accounts/login/', {
        'email': admin.email,
        'password': 'pass12345',
    })
    client_login = api_client.post('/api/accounts/login/', {
        'email': client.email,
        'password': 'pass12345',
    })
    admin_headers = {'HTTP_AUTHORIZATION': f"Bearer {admin_login.json()['tokens']['access']}"}
    client_headers = {'HTTP_AUTHORIZATION': f"Bearer {client_login.json()['tokens']['access']}"}
    return admin, client, admin_headers, client_headers


@pytest.fixture
def change_request(users_and_headers):
    """Create a change request with the source relation detail must serialize."""
    _, client, _, _ = users_and_headers
    project = Project.objects.create(name='Change detail project', client=client)
    proposal = BusinessProposal.objects.create(
        title='Change detail proposal',
        client_name='Change detail client',
        total_investment=Decimal(12000000),
    )
    phase = make_delivery_stage(project, phase_title=proposal.title)
    requirement = make_requirement(phase, title='Source requirement')
    request = ChangeRequest.objects.create(project=project, source_requirement=requirement, created_by=client, title='Change request detail')
    return project, request


@pytest.mark.django_db
def test_admin_detail_keeps_comment_queries_constant_as_comments_grow(
    api_client, users_and_headers, change_request,
):
    """Fails if detail serialization reloads comment authors once per detail comment."""
    _, _, admin_headers, _ = users_and_headers
    project, request = change_request
    _comments(request, _comment_authors(1))

    with CaptureQueriesContext(connection) as one_comment_queries:
        one_response = api_client.get(_detail_url(project.id, request.id), **admin_headers)

    _comments(request, _comment_authors(49, start=1), start=1)
    with CaptureQueriesContext(connection) as fifty_comment_queries:
        fifty_response = api_client.get(_detail_url(project.id, request.id), **admin_headers)

    one_body = one_response.json()
    fifty_body = fifty_response.json()
    assert (one_response.status_code, fifty_response.status_code) == (200, 200)
    assert len(one_body['comments']) == 1
    assert len(fifty_body['comments']) == 50
    assert len(one_comment_queries) == len(fifty_comment_queries)
    assert len(fifty_comment_queries) <= MAX_CHANGE_REQUEST_DETAIL_QUERIES


@pytest.mark.django_db
def test_admin_detail_serializes_prefetched_related_values(
    api_client, users_and_headers, change_request,
):
    """Fails if optimized detail omits related data or serializes the wrong comment author."""
    _, _, admin_headers, _ = users_and_headers
    project, request = change_request
    _comments(request, _comment_authors(2))

    response = api_client.get(_detail_url(project.id, request.id), **admin_headers)

    body = response.json()
    assert response.status_code == 200
    assert body['created_by_email'] == 'change-detail-client@example.com'
    assert (
        body['source_requirement']['title'],
        body['source_requirement']['phase_title'],
    ) == ('Source requirement', 'Change detail proposal')
    assert [comment['content'] for comment in body['comments']] == ['Comment 0', 'Comment 1']
    assert [comment['user_email'] for comment in body['comments']] == [
        'change-detail-author-0@example.com',
        'change-detail-author-1@example.com',
    ]


@pytest.mark.django_db
def test_client_detail_excludes_internal_comments_from_prefetched_collection(
    api_client, users_and_headers, change_request,
):
    """Fails if client detail exposes internal comments after the optimized prefetch."""
    _, _, _, client_headers = users_and_headers
    project, request = change_request
    _comments(request, _comment_authors(2))

    response = api_client.get(_detail_url(project.id, request.id), **client_headers)

    body = response.json()
    assert response.status_code == 200
    assert [comment['content'] for comment in body['comments']] == ['Comment 1']
    assert [comment['is_internal'] for comment in body['comments']] == [False]
    assert [comment['user_email'] for comment in body['comments']] == ['change-detail-author-1@example.com']


@pytest.mark.django_db
def test_detail_serializer_fallback_hides_internal_comments_for_client(users_and_headers, change_request):
    """Fails if direct serializer consumers expose internal comments without the view prefetch."""
    _, client, _, _ = users_and_headers
    _, request = change_request
    _comments(request, _comment_authors(2))
    unprefetched_request = ChangeRequest.objects.get(pk=request.pk)

    body = ChangeRequestDetailSerializer(
        unprefetched_request,
        context={'request': type('RequestContext', (), {'user': client})()},
    ).data

    assert [comment['content'] for comment in body['comments']] == ['Comment 1']
    assert [comment['user_email'] for comment in body['comments']] == ['change-detail-author-1@example.com']


@pytest.mark.django_db
def test_detail_response_serializes_missing_source_requirement_as_null(
    api_client, users_and_headers, change_request,
):
    """Fails if change-request detail errors when its optional source requirement is absent."""
    _, _, _, client_headers = users_and_headers
    project, request = change_request
    request.source_requirement = None
    request.save(update_fields=['source_requirement'])

    response = api_client.get(_detail_url(project.id, request.id), **client_headers)

    assert response.status_code == 200
    assert response.json()['source_requirement'] is None


@pytest.mark.django_db
def test_client_detail_hides_archived_change_request(api_client, users_and_headers, change_request):
    """Fails if a client can read an archived change request through its detail route."""
    _, _, _, client_headers = users_and_headers
    project, request = change_request
    request.is_archived = True
    request.save(update_fields=['is_archived'])

    response = api_client.get(_detail_url(project.id, request.id), **client_headers)

    assert response.status_code == 404
    assert response.json() == {'detail': 'Solicitud de cambio no encontrada.'}


@pytest.mark.django_db
def test_admin_detail_returns_archived_change_request(api_client, users_and_headers, change_request):
    """Fails if the archived-detail visibility rule hides a request from administrators."""
    _, _, admin_headers, _ = users_and_headers
    project, request = change_request
    request.is_archived = True
    request.save(update_fields=['is_archived'])

    response = api_client.get(_detail_url(project.id, request.id), **admin_headers)

    assert response.status_code == 200
    assert (response.json()['id'], response.json()['title']) == (request.id, 'Change request detail')


@pytest.mark.django_db
def test_foreign_client_detail_request_returns_403(api_client, users_and_headers, change_request):
    """Fails if a client outside the project tenant can enumerate change-request detail."""
    admin, _, _, _ = users_and_headers
    project, request = change_request
    foreign_client = User.objects.create_user(
        username='foreign-change-detail@example.com',
        email='foreign-change-detail@example.com',
        password='pass12345',
    )
    UserProfile.objects.update_or_create(
        user=foreign_client,
        defaults={
            'role': UserProfile.ROLE_CLIENT,
            'is_onboarded': True,
            'profile_completed': True,
            'created_by': admin,
        },
    )
    login = api_client.post('/api/accounts/login/', {
        'email': foreign_client.email,
        'password': 'pass12345',
    })

    response = api_client.get(
        _detail_url(project.id, request.id),
        HTTP_AUTHORIZATION=f"Bearer {login.json()['tokens']['access']}",
    )

    assert response.status_code == 403
    assert response.json() == {'detail': 'No tienes acceso a este proyecto.'}


@pytest.mark.django_db
def test_change_request_delete_avoids_comment_queries(
    api_client, users_and_headers, change_request, record_property,
):
    """Fails if archiving a change request reloads its comment thread or authors."""
    _, client, admin_headers, _ = users_and_headers
    project, one_comment_request = change_request
    fifty_comment_request = ChangeRequest.objects.create(
        project=project,
        created_by=client,
        title='Change request with fifty comments',
    )
    _comments(one_comment_request, _comment_authors(1))
    _comments(fifty_comment_request, _comment_authors(50, start=100), start=100)

    with CaptureQueriesContext(connection) as one_comment_queries:
        one_comment_response = api_client.delete(
            _detail_url(project.id, one_comment_request.id),
            **admin_headers,
        )

    with CaptureQueriesContext(connection) as fifty_comment_queries:
        fifty_comment_response = api_client.delete(
            _detail_url(project.id, fifty_comment_request.id),
            **admin_headers,
        )

    one_comment_request.refresh_from_db()
    fifty_comment_request.refresh_from_db()
    fifty_comment_sql = _captured_sql(fifty_comment_queries)
    record_property('query_count_one', len(one_comment_queries))
    record_property('query_count_fifty', len(fifty_comment_queries))

    assert (one_comment_response.status_code, fifty_comment_response.status_code) == (200, 200)
    assert (one_comment_response.json(), fifty_comment_response.json()) == (
        {'detail': 'Solicitud de cambio archivada.'},
        {'detail': 'Solicitud de cambio archivada.'},
    )
    assert (one_comment_request.is_archived, fifty_comment_request.is_archived) == (True, True)
    assert len(one_comment_queries) == len(fifty_comment_queries)
    assert 'accounts_changerequestcomment' not in fifty_comment_sql
