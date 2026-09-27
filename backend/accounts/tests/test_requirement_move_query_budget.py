"""Query-budget contracts for requirement moves."""

import re

import pytest
from content.models import BusinessProposal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import (
    Project,
    ProjectPhase,
    ProjectScopeItem,
    Requirement,
    RequirementComment,
    RequirementHistory,
    UserProfile,
)

User = get_user_model()
MAX_REQUIREMENT_MOVE_QUERIES = 8


def _move_url(project, requirement):
    return f"/api/accounts/projects/{project.pk}/requirements/{requirement.pk}/move/"


def _exact_table(sql, model):
    return re.search(rf'["`]{re.escape(model._meta.db_table)}["`]', sql) is not None


def _independent_reads(queries, related_model, owner_model):
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and _exact_table(query["sql"], related_model)
        and not _exact_table(query["sql"], owner_model)
    ]


def _owner_reads(queries):
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and _exact_table(query["sql"], Requirement)
    ]


def _principal_move_reads(queries):
    return [
        query
        for query in _owner_reads(queries)
        if _exact_table(query, RequirementComment)
        and _exact_table(query, ProjectPhase)
        and _exact_table(query, ProjectScopeItem)
    ]


def _comment_authors(count, *, start):
    return User.objects.bulk_create(
        [
            User(
                username=f"move-budget-author-{number}@example.com",
                email=f"move-budget-author-{number}@example.com",
            )
            for number in range(start, start + count)
        ]
    )


def _comments(requirement, count, *, start):
    return RequirementComment.objects.bulk_create(
        [
            RequirementComment(
                requirement=requirement,
                user=author,
                content=f"Comment {number}",
                is_internal=number % 2 == 0,
            )
            for number, author in zip(
                range(start, start + count), _comment_authors(count, start=start)
            )
        ]
    )


@pytest.fixture
def move_context():
    """Create the authenticated actors and project relations required by requirement moves."""
    admin = User.objects.create_user(
        username="move-budget-admin@example.com", email="move-budget-admin@example.com"
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username="move-budget-client@example.com",
        email="move-budget-client@example.com",
    )
    UserProfile.objects.create(
        user=client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    project = Project.objects.create(name="Move budget project", client=client)
    proposal = BusinessProposal.objects.create(
        title="Move budget proposal", client_name="Move budget client"
    )
    phase = ProjectPhase.objects.create(
        project=project, business_proposal=proposal, order=1
    )
    return (
        APIClient(),
        {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(admin)}"},
        project,
        phase,
    )


def _requirement(phase, label):
    scope = ProjectScopeItem.objects.create(
        phase=phase,
        source_item_id=f"{label}-scope",
        name=f"{label} scope",
        group_id=f"{label}-group",
        group_title=f"{label} group",
    )
    return Requirement.objects.create(
        phase=phase,
        scope_item=scope,
        title=f"{label} requirement",
        status=Requirement.STATUS_TODO,
    )


@pytest.mark.django_db
def test_admin_move_keeps_requirement_comment_budget_constant(
    move_context, record_property
):
    """Fails if moving a requirement reloads its phase, scope, or comments as they grow."""
    client, headers, project, phase = move_context
    one_requirement = _requirement(phase, "one")
    fifty_requirement = _requirement(phase, "fifty")
    _comments(one_requirement, 1, start=1)
    _comments(fifty_requirement, 50, start=100)

    with CaptureQueriesContext(connection) as one_queries:
        one_response = client.post(
            _move_url(project, one_requirement),
            {"status": "done", "order": 2},
            format="json",
            **headers,
        )
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = client.post(
            _move_url(project, fifty_requirement),
            {"status": "done", "order": 3},
            format="json",
            **headers,
        )

    project.refresh_from_db()
    one_body, fifty_body = one_response.json(), fifty_response.json()
    record_property("query_count_one", len(one_queries))
    record_property("query_count_fifty", len(fifty_queries))
    assert (one_response.status_code, fifty_response.status_code) == (200, 200)
    assert (
        one_body["phase_title"],
        one_body["scope_item_name"],
        one_body["scope_item_group_id"],
        one_body["comments_count"],
        one_body["status"],
        one_body["order"],
    ) == ("Move budget proposal", "one scope", "one-group", 1, "done", 2)
    assert (
        fifty_body["phase_title"],
        fifty_body["scope_item_name"],
        fifty_body["scope_item_group_id"],
        fifty_body["comments_count"],
        fifty_body["status"],
        fifty_body["order"],
    ) == ("Move budget proposal", "fifty scope", "fifty-group", 50, "done", 3)
    assert (
        RequirementHistory.objects.filter(requirement=one_requirement).count(),
        RequirementHistory.objects.filter(requirement=fifty_requirement).count(),
        project.progress,
    ) == (1, 1, 100)
    assert len(one_queries) == len(fifty_queries)
    assert tuple(
        len(_principal_move_reads(queries)) for queries in (one_queries, fifty_queries)
    ) == (1, 1)
    assert "COUNT(" in _principal_move_reads(one_queries)[0].upper()
    assert tuple(
        _independent_reads(one_queries, model, Requirement)
        for model in (
            RequirementComment,
            ProjectPhase,
            BusinessProposal,
            ProjectScopeItem,
        )
    ) == ([], [], [], [])


@pytest.mark.django_db
def test_admin_same_status_move_updates_order_without_requirement_history(
    move_context, record_property
):
    """Fails if a same-status move loses relation data or creates transition history."""
    client, headers, project, phase = move_context
    requirement = _requirement(phase, "same")
    _comments(requirement, 2, start=1)

    with CaptureQueriesContext(connection) as queries:
        response = client.post(
            _move_url(project, requirement),
            {"status": "todo", "order": 9},
            format="json",
            **headers,
        )

    requirement.refresh_from_db()
    body = response.json()
    record_property("query_count_same_status", len(queries))
    assert (response.status_code, requirement.status, requirement.order) == (
        200,
        "todo",
        9,
    )
    assert (
        body["phase_title"],
        body["scope_item_name"],
        body["scope_item_group_id"],
        body["comments_count"],
    ) == ("Move budget proposal", "same scope", "same-group", 2)
    assert RequirementHistory.objects.filter(requirement=requirement).count() == 0
    assert len(_principal_move_reads(queries)) == 1
    assert tuple(
        _independent_reads(queries, model, Requirement)
        for model in (
            RequirementComment,
            ProjectPhase,
            BusinessProposal,
            ProjectScopeItem,
        )
    ) == ([], [], [], [])
