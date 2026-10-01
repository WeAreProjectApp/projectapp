"""Query-budget contracts for archived bug reports."""

from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
import pytest
from content.models import BusinessProposal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import (
    BugComment,
    BugReport,
    Project,
    UserProfile,
)

User = get_user_model()
MAX_BUG_REPORT_ARCHIVE_QUERIES = 8


def _detail_url(project_id, bug_id):
    return f'/api/accounts/projects/{project_id}/bug-reports/{bug_id}/'


def _comment_authors(count, *, start=0):
    return User.objects.bulk_create([
        User(
            username=f'bug-archive-author-{index}@example.com',
            email=f'bug-archive-author-{index}@example.com',
        )
        for index in range(start, start + count)
    ])


def _comments(bug_report, authors, *, start=0):
    BugComment.objects.bulk_create([
        BugComment(
            bug_report=bug_report,
            user=author,
            content=f'Archive budget comment {index}',
        )
        for index, author in enumerate(authors, start=start)
    ])


def _collection_selects(queries):
    table = BugComment._meta.db_table.lower()
    return [
        query['sql']
        for query in queries
        if query['sql'].lstrip().upper().startswith('SELECT') and table in query['sql'].lower()
    ]


@pytest.fixture
def api_client():
    """Provide an API client for JWT-authenticated archive requests."""
    return APIClient()


@pytest.fixture
def users_and_headers(api_client):
    """Create the administrator and client actors used by archive contracts."""
    admin = User.objects.create_user(
        username='bug-archive-admin@example.com',
        email='bug-archive-admin@example.com',
        password=None,
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username='bug-archive-client@example.com',
        email='bug-archive-client@example.com',
        password=None,
    )
    UserProfile.objects.create(
        user=client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    admin_headers = {'HTTP_AUTHORIZATION': f'Bearer {AccessToken.for_user(admin)}'}
    client_headers = {'HTTP_AUTHORIZATION': f'Bearer {AccessToken.for_user(client)}'}
    return admin_headers, client_headers, client


@pytest.fixture
def project_and_bug_reports(users_and_headers):
    """Create two equivalent bug reports for the one-to-fifty comparison."""
    _, _, client = users_and_headers
    project = Project.objects.create(name='Bug archive budget project', client=client)
    proposal = BusinessProposal.objects.create(
        title='Bug archive budget proposal',
        client_name='Bug archive budget client',
    )
    phase = make_delivery_stage(project, phase_title=proposal.title)
    requirement = make_requirement(phase, title='Bug archive source')
    one_comment_bug = BugReport.objects.create(project=project, reported_by=client, source_requirement=requirement, title='One comment bug')
    fifty_comment_bug = BugReport.objects.create(project=project, reported_by=client, source_requirement=requirement, title='Fifty comment bug')
    return project, one_comment_bug, fifty_comment_bug


@pytest.mark.django_db
def test_admin_archive_keeps_comment_reads_constant_as_comments_grow(
    api_client, users_and_headers, project_and_bug_reports, record_property,
):
    """Fails if bug archiving reloads comments that its response never returns."""
    admin_headers, _, _ = users_and_headers
    project, one_comment_bug, fifty_comment_bug = project_and_bug_reports
    _comments(one_comment_bug, _comment_authors(1))
    _comments(fifty_comment_bug, _comment_authors(50, start=1), start=1)

    with CaptureQueriesContext(connection) as one_comment_queries:
        one_comment_response = api_client.delete(
            _detail_url(project.id, one_comment_bug.id),
            **admin_headers,
        )
    with CaptureQueriesContext(connection) as fifty_comment_queries:
        fifty_comment_response = api_client.delete(
            _detail_url(project.id, fifty_comment_bug.id),
            **admin_headers,
        )

    one_comment_bug.refresh_from_db()
    fifty_comment_bug.refresh_from_db()
    record_property('query_count_one', len(one_comment_queries))
    record_property('query_count_fifty', len(fifty_comment_queries))

    assert (one_comment_response.status_code, fifty_comment_response.status_code) == (200, 200)
    assert (one_comment_response.json(), fifty_comment_response.json()) == (
        {'detail': 'Reporte de bug archivado.'},
        {'detail': 'Reporte de bug archivado.'},
    )
    assert (one_comment_bug.is_archived, fifty_comment_bug.is_archived) == (True, True)
    assert len(one_comment_queries) == len(fifty_comment_queries)
    assert len(fifty_comment_queries) <= MAX_BUG_REPORT_ARCHIVE_QUERIES
    assert _collection_selects(one_comment_queries) == []
    assert _collection_selects(fifty_comment_queries) == []


@pytest.mark.django_db
def test_client_archive_rejection_skips_bug_comment_reads(
    api_client, users_and_headers, project_and_bug_reports,
):
    """Fails if a rejected client archive loads bug comments before checking the role."""
    _, client_headers, _ = users_and_headers
    project, one_comment_bug, _ = project_and_bug_reports
    _comments(one_comment_bug, _comment_authors(1))

    with CaptureQueriesContext(connection) as queries:
        response = api_client.delete(_detail_url(project.id, one_comment_bug.id), **client_headers)

    one_comment_bug.refresh_from_db()
    assert response.status_code == 403
    assert response.json() == {'detail': 'Solo los administradores pueden eliminar reportes de bugs.'}
    assert one_comment_bug.is_archived is False
    assert _collection_selects(queries) == []
