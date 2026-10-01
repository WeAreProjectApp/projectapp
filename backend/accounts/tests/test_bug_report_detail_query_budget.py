"""Bug detail stays bounded with two history reads and batched comment evidence.

These three additive reads extend the original five-query detail contract.
"""

from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from types import SimpleNamespace

import pytest
from content.models import BusinessProposal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import (
    BugComment,
    BugReport,
    Project,
    UserProfile,
)
from accounts.serializers import BugReportDetailSerializer

User = get_user_model()
MAX_BUG_REPORT_DETAIL_QUERIES = 8


def _detail_url(project_id, bug_id):
    return f'/api/accounts/projects/{project_id}/bug-reports/{bug_id}/'


def _comment_authors(count, *, start=0):
    return User.objects.bulk_create([
        User(
            username=f'bug-detail-author-{index}@example.com',
            email=f'bug-detail-author-{index}@example.com',
            first_name=f'Author{index}',
            password='unused',
        )
        for index in range(start, start + count)
    ])


def _comments(bug, authors, *, start=0):
    return BugComment.objects.bulk_create([
        BugComment(
            bug_report=bug,
            user=author,
            content=f'Comment {index}',
            is_internal=index % 2 == 0,
        )
        for index, author in enumerate(authors, start=start)
    ])


@pytest.fixture
def api_client():
    """Provide an API client for JWT-authenticated detail requests."""
    return APIClient()


@pytest.fixture
def users_and_headers(api_client):
    """Create the administrator and owning client used by detail contracts."""
    admin = User.objects.create_user(
        username='bug-detail-admin@example.com',
        email='bug-detail-admin@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username='bug-detail-client@example.com',
        email='bug-detail-client@example.com',
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
def bug_report(users_and_headers):
    """Create a bug report with the nested source relationship detail must serialize."""
    _, client, _, _ = users_and_headers
    project = Project.objects.create(name='Bug detail project', client=client)
    proposal = BusinessProposal.objects.create(
        title='Bug detail proposal',
        client_name='Bug detail client',
    )
    phase = make_delivery_stage(project, phase_title=proposal.title)
    requirement = make_requirement(phase, title='Source requirement')
    bug = BugReport.objects.create(project=project, reported_by=client, source_requirement=requirement, title='Bug report detail')
    return project, bug


@pytest.mark.django_db
def test_admin_detail_keeps_comment_queries_constant_as_comments_grow(
    api_client, users_and_headers, bug_report, record_property,
):
    """Falla si el detalle vuelve a consultar autores de comentarios a medida que crecen."""
    _, _, admin_headers, _ = users_and_headers
    project, bug = bug_report
    _comments(bug, _comment_authors(1))

    with CaptureQueriesContext(connection) as one_comment_queries:
        one_response = api_client.get(_detail_url(project.id, bug.id), **admin_headers)

    _comments(bug, _comment_authors(49, start=1), start=1)
    with CaptureQueriesContext(connection) as fifty_comment_queries:
        fifty_response = api_client.get(_detail_url(project.id, bug.id), **admin_headers)

    one_body = one_response.json()
    fifty_body = fifty_response.json()
    record_property('query_count_bug_detail_one', len(one_comment_queries))
    record_property('query_count_bug_detail_fifty', len(fifty_comment_queries))

    assert (one_response.status_code, len(one_body['comments'])) == (200, 1)
    assert (fifty_response.status_code, len(fifty_body['comments'])) == (200, 50)
    assert (one_body['responses'], fifty_body['responses'], one_body['history'], fifty_body['history']) == ([], [], [], [])
    assert len(one_comment_queries) == len(fifty_comment_queries)
    assert len(fifty_comment_queries) <= MAX_BUG_REPORT_DETAIL_QUERIES


@pytest.mark.django_db
def test_admin_detail_serializes_prefetched_source_values(
    api_client, users_and_headers, bug_report,
):
    """Falla si el detalle optimizado omite el reportante o la relación de origen."""
    _, _, admin_headers, _ = users_and_headers
    project, bug = bug_report

    response = api_client.get(_detail_url(project.id, bug.id), **admin_headers)

    body = response.json()
    assert response.status_code == 200
    assert body['reported_by_email'] == 'bug-detail-client@example.com'
    assert body['source_requirement']['title'] == 'Source requirement'
    assert body['source_requirement']['phase_title'] == 'Bug detail proposal'


@pytest.mark.django_db
def test_client_detail_hides_internal_prefetched_comments(
    api_client, users_and_headers, bug_report,
):
    """Falla si el serializer expone comentarios internos desde la colección prefetched."""
    _, _, _, client_headers = users_and_headers
    project, bug = bug_report
    _comments(bug, _comment_authors(2))

    response = api_client.get(_detail_url(project.id, bug.id), **client_headers)

    assert response.status_code == 200
    assert [comment['content'] for comment in response.json()['comments']] == ['Comment 1']
    assert [comment['user_email'] for comment in response.json()['comments']] == [
        'bug-detail-author-1@example.com',
    ]


@pytest.mark.django_db
def test_client_detail_serializes_a_missing_source_requirement_as_null(
    api_client, users_and_headers, bug_report,
):
    """Falla si el detalle ya no tolera bugs sin requerimiento de origen."""
    _, _, _, client_headers = users_and_headers
    project, bug = bug_report
    bug.source_requirement = None
    bug.save(update_fields=['source_requirement'])

    response = api_client.get(_detail_url(project.id, bug.id), **client_headers)

    assert response.status_code == 200
    assert response.json()['source_requirement'] is None


@pytest.mark.django_db
def test_foreign_client_detail_request_returns_403(api_client, users_and_headers, bug_report):
    """Falla si un cliente ajeno puede enumerar el detalle de bugs de otro proyecto."""
    admin, _, _, _ = users_and_headers
    project, bug = bug_report
    foreign_client = User.objects.create_user(
        username='foreign-bug-detail@example.com',
        email='foreign-bug-detail@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=foreign_client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    login = api_client.post('/api/accounts/login/', {
        'email': foreign_client.email,
        'password': 'pass12345',
    })

    response = api_client.get(
        _detail_url(project.id, bug.id),
        HTTP_AUTHORIZATION=f"Bearer {login.json()['tokens']['access']}",
    )

    assert response.status_code == 403
    assert response.json() == {'detail': 'No tienes acceso a este proyecto.'}


@pytest.mark.django_db
def test_bug_detail_serializer_fallback_hides_internal_comments(users_and_headers, bug_report):
    """Falla si consumidores sin prefetch exponen comentarios internos al cliente."""
    _, client, _, _ = users_and_headers
    _, bug = bug_report
    _comments(bug, _comment_authors(2))
    unprefetched_bug = BugReport.objects.get(pk=bug.pk)

    body = BugReportDetailSerializer(
        unprefetched_bug,
        context={'request': SimpleNamespace(user=client)},
    ).data

    assert [comment['content'] for comment in body['comments']] == ['Comment 1']
    assert [comment['user_email'] for comment in body['comments']] == [
        'bug-detail-author-1@example.com',
    ]
