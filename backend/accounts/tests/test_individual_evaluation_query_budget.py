"""Query-budget contracts for individual change-request and bug evaluations."""

from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
import re

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
    ChangeRequest,
    ChangeRequestComment,
    IssueEvent,
    IssueResponse,
    Project,
    ProjectPhase,
    Requirement,
    UserProfile,
)

User = get_user_model()
MAX_INDIVIDUAL_EVALUATION_QUERIES = 8


def _exact_table(sql, model):
    return re.search(rf'["`]{re.escape(model._meta.db_table)}["`]', sql) is not None


def _table_selects(queries, model):
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and _exact_table(query["sql"], model)
    ]


def _independent_selects(queries, related_model, owner_model):
    return [
        query["sql"]
        for query in _table_selects(queries, related_model)
        if not _exact_table(query, owner_model)
    ]


def _independent_author_reads(queries, owner_model, comment_model):
    return [
        query
        for query in _table_selects(queries, User)
        if not _exact_table(query, owner_model)
        and not _exact_table(query, comment_model)
        and not _exact_table(query, IssueResponse)
        and not _exact_table(query, IssueEvent)
    ]


def _comment_authors(count, *, start):
    return User.objects.bulk_create(
        [
            User(
                username=f"evaluation-author-{number}@example.com",
                email=f"evaluation-author-{number}@example.com",
                first_name=f"Author{number}",
            )
            for number in range(start, start + count)
        ]
    )


@pytest.fixture
def evaluation_context():
    """Create an admin JWT and project source chain for individual evaluations."""
    admin = User.objects.create_user(
        username="evaluation-admin@example.com", email="evaluation-admin@example.com"
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username="evaluation-client@example.com", email="evaluation-client@example.com"
    )
    UserProfile.objects.create(
        user=client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    project = Project.objects.create(name="Evaluation budget project", client=client)
    proposal = BusinessProposal.objects.create(
        title="Evaluation budget proposal", client_name="Evaluation budget client"
    )
    phase = make_delivery_stage(project, phase_title=proposal.title)
    requirement = make_requirement(phase, title="Evaluation source")
    return (
        APIClient(),
        {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(admin)}"},
        project,
        phase,
        requirement,
        client,
    )


def _change_request(project, phase, requirement, client, label):
    return ChangeRequest.objects.create(project=project, source_requirement=requirement, created_by=client, title=f"Change {label}")


def _bug_report(project, phase, requirement, client, label):
    return BugReport.objects.create(project=project, source_requirement=requirement, reported_by=client, title=f"Bug {label}")


def _comments(model, parent_field, parent, count, *, start):
    authors = _comment_authors(count, start=start)
    model.objects.bulk_create(
        [
            model(
                **{
                    parent_field: parent,
                    "user": author,
                    "content": f"Comment {number}",
                    "is_internal": number % 2 == 0,
                }
            )
            for number, author in zip(range(start, start + count), authors)
        ]
    )
    return authors


def _conversation_records(parent_field, ticket, authors):
    IssueResponse.objects.bulk_create([
        IssueResponse(
            **{parent_field: ticket}, actor=author, message=f'Response {author.pk}',
            status=ticket.status, is_internal=number % 2 == 0,
        )
        for number, author in enumerate(authors)
    ])
    IssueEvent.objects.bulk_create([
        IssueEvent(
            **{parent_field: ticket}, project=ticket.project, actor=author,
            action='comment', status=ticket.status, is_internal=number % 2 == 0,
        )
        for number, author in enumerate(authors)
    ])


def _evaluate_url(project, kind, item):
    return f"/api/accounts/projects/{project.pk}/{kind}/{item.pk}/evaluate/"


def _evaluate_conversation_pair(context, factory, kind, status, comment_model, parent_field):
    client, headers, project, phase, requirement, owner = context
    one = factory(project, phase, requirement, owner, 'one')
    fifty = factory(project, phase, requirement, owner, 'fifty')
    one_authors = _comments(comment_model, parent_field, one, 1, start=1)
    fifty_authors = _comments(comment_model, parent_field, fifty, 50, start=100)
    _conversation_records(parent_field, one, one_authors)
    _conversation_records(parent_field, fifty, fifty_authors)
    with CaptureQueriesContext(connection) as one_queries:
        one_response = client.post(
            _evaluate_url(project, kind, one), {'status': status}, format='json', **headers,
        )
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = client.post(
            _evaluate_url(project, kind, fifty), {'status': status}, format='json', **headers,
        )
    return one_response, fifty_response, one_queries, fifty_queries, fifty_authors


@pytest.mark.django_db
def test_admin_change_request_evaluation_keeps_comment_queries_constant(
    evaluation_context, record_property
):
    """Fails if evaluating change requests reloads source relations or comment authors per row."""
    one_response, fifty_response, one_queries, fifty_queries, fifty_authors = _evaluate_conversation_pair(
        evaluation_context, _change_request, 'change-requests', 'evaluating',
        ChangeRequestComment, 'change_request',
    )
    one_body, fifty_body = one_response.json(), fifty_response.json()
    record_property("query_count_change_request_one", len(one_queries))
    record_property("query_count_change_request_fifty", len(fifty_queries))
    assert (
        one_response.status_code,
        fifty_response.status_code,
        one_body["status"],
        fifty_body["status"],
    ) == (200, 200, "evaluating", "evaluating")
    assert (
        one_body["created_by_email"],
        one_body["source_requirement"]["title"],
        one_body["source_requirement"]["phase_title"],
        len(one_body["comments"]),
    ) == (evaluation_context[-1].email, "Evaluation source", "Evaluation budget proposal", 1)
    assert (
        fifty_body["created_by_email"],
        len(fifty_body["comments"]),
        [comment["user_email"] for comment in fifty_body["comments"]],
        [row['actor_name'] for row in fifty_body['responses']],
        [row['actor_name'] for row in fifty_body['history'][:-1]],
    ) == (
        evaluation_context[-1].email,
        50,
        [author.email for author in fifty_authors],
        [author.first_name for author in fifty_authors],
        [author.first_name for author in fifty_authors],
    )
    assert len(one_queries) == len(fifty_queries)
    assert tuple(
        (len(_table_selects(one_queries, model)), len(_table_selects(fifty_queries, model)))
        for model in (ChangeRequestComment, IssueResponse, IssueEvent)
    ) == ((1, 1), (1, 1), (1, 1))
    assert tuple(
        _independent_selects(fifty_queries, model, ChangeRequest)
        for model in (Requirement, ProjectPhase, BusinessProposal)
    ) == ([], [], [])
    assert (
        len(_independent_author_reads(fifty_queries, ChangeRequest, ChangeRequestComment))
        == 2
    )


@pytest.mark.django_db
def test_admin_bug_evaluation_keeps_comment_queries_constant(
    evaluation_context, record_property
):
    """Fails if evaluating bugs reloads source relations or comment authors per row."""
    one_response, fifty_response, one_queries, fifty_queries, fifty_authors = _evaluate_conversation_pair(
        evaluation_context, _bug_report, 'bug-reports', 'confirmed', BugComment, 'bug_report',
    )
    one_body, fifty_body = one_response.json(), fifty_response.json()
    record_property("query_count_bug_one", len(one_queries))
    record_property("query_count_bug_fifty", len(fifty_queries))
    assert (
        one_response.status_code,
        fifty_response.status_code,
        one_body["status"],
        fifty_body["status"],
    ) == (200, 200, "confirmed", "confirmed")
    assert (
        one_body["reported_by_email"],
        one_body["source_requirement"]["title"],
        one_body["source_requirement"]["phase_title"],
        len(one_body["comments"]),
    ) == (evaluation_context[-1].email, "Evaluation source", "Evaluation budget proposal", 1)
    assert (
        fifty_body["reported_by_email"],
        len(fifty_body["comments"]),
        [comment["user_email"] for comment in fifty_body["comments"]],
        [row['actor_name'] for row in fifty_body['responses']],
        [row['actor_name'] for row in fifty_body['history'][:-1]],
    ) == (
        evaluation_context[-1].email,
        50,
        [author.email for author in fifty_authors],
        [author.first_name for author in fifty_authors],
        [author.first_name for author in fifty_authors],
    )
    assert len(one_queries) == len(fifty_queries)
    assert tuple(
        (len(_table_selects(one_queries, model)), len(_table_selects(fifty_queries, model)))
        for model in (BugComment, IssueResponse, IssueEvent)
    ) == ((1, 1), (1, 1), (1, 1))
    assert tuple(
        _independent_selects(fifty_queries, model, BugReport)
        for model in (Requirement, ProjectPhase, BusinessProposal)
    ) == ([], [], [])
    assert len(_independent_author_reads(fifty_queries, BugReport, BugComment)) == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("factory", "kind", "status", "email_key", "owner_model", "comment_model"),
    [
        (
            _change_request,
            "change-requests",
            "evaluating",
            "created_by_email",
            ChangeRequest,
            ChangeRequestComment,
        ),
        (
            _bug_report,
            "bug-reports",
            "confirmed",
            "reported_by_email",
            BugReport,
            BugComment,
        ),
    ],
)
def test_admin_evaluation_serializes_null_source_requirement(
    evaluation_context,
    factory,
    kind,
    status,
    email_key,
    owner_model,
    comment_model,
    record_property,
):
    """Fails if evaluating an item without a source requirement traverses a null relation."""
    client, headers, project, phase, _, owner = evaluation_context
    item = factory(project, phase, None, owner, "without-source")

    with CaptureQueriesContext(connection) as queries:
        response = client.post(
            _evaluate_url(project, kind, item),
            {"status": status},
            format="json",
            **headers,
        )

    body = response.json()
    record_property(f"query_count_{kind}_without_source", len(queries))
    assert (
        response.status_code,
        body["source_requirement"],
        body[email_key],
        body["status"],
    ) == (200, None, owner.email, status)
    assert tuple(
        len(_independent_selects(queries, model, owner_model))
        for model in (Requirement, ProjectPhase, BusinessProposal)
    ) == (0, 0, 0)
    assert len(_independent_author_reads(queries, owner_model, comment_model)) == 2
