"""Query-budget contracts for monitoring case state changes."""

import re
from datetime import datetime, timezone

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from monitoring.models import Case, CaseActivity, Resource, Source

User = get_user_model()
CASES_URL = "/api/monitoring/cases/"
MAX_CASE_STATE_QUERIES = 8


def _table_selects(queries, model):
    table = re.compile(rf'["`]{re.escape(model._meta.db_table)}["`]')
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and table.search(query["sql"])
    ]


def _exact_table(sql, model):
    return re.search(rf'["`]{re.escape(model._meta.db_table)}["`]', sql) is not None


def _independent_relation_reads(queries, related_model):
    return [
        query
        for query in _table_selects(queries, related_model)
        if not _exact_table(query, Case)
    ]


@pytest.fixture
def staff_client(db):
    """Authenticate a real staff session for the session-protected monitoring route."""
    staff = User.objects.create_user(
        username="case-state-budget", password="test-password", is_staff=True
    )
    client = APIClient()
    client.force_login(staff)
    return client, staff


@pytest.fixture
def monitoring_case():
    """Create a pending case with its source and project resource."""
    server = Resource.objects.create(
        key="srv1681495", name="Budget server", kind="server"
    )
    resource = Resource.objects.create(
        key="projectapp", name="ProjectApp", kind="project", server=server
    )
    source = Source.objects.create(resource=resource, key="integrity", name="Integrity")
    return Case.objects.create(
        source=source,
        fingerprint="case-state-budget",
        fingerprint_hash="a" * 64,
        title="Case state budget",
        severity="warning",
        first_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        version=2,
    )


@pytest.mark.django_db
def test_staff_state_change_serializes_preloaded_case_relations(
    staff_client, monitoring_case, record_property
):
    """Fails if a state change reloads source or resource after the locked case query."""
    client, staff = staff_client

    with CaptureQueriesContext(connection) as no_op_queries:
        client.post(
            f"{CASES_URL}{monitoring_case.pk}/state/",
            {"state": "pending", "version": monitoring_case.version},
            format="json",
        )
    with CaptureQueriesContext(connection) as queries:
        response = client.post(
            f"{CASES_URL}{monitoring_case.pk}/state/",
            {
                "state": "reviewing",
                "version": monitoring_case.version,
                "note": "Checked.",
            },
            format="json",
        )

    activity = CaseActivity.objects.get(case=monitoring_case, kind="state")
    body = response.json()
    record_property("query_count_changed_state", len(queries))
    record_property("query_count_noop_reference", len(no_op_queries))
    record_property("query_count_delta", len(queries) - len(no_op_queries))
    assert (response.status_code, body["state"], body["version"]) == (
        200,
        "reviewing",
        3,
    )
    assert (body["source_name"], body["resource"]["key"]) == ("Integrity", "projectapp")
    assert (activity.actor_id, activity.text) == (staff.pk, "Checked.")
    assert len(queries) - len(no_op_queries) == 2
    assert tuple(
        len(_table_selects(queries, model)) for model in (Case, Source, Resource)
    ) == (1, 1, 1)
    assert tuple(
        _independent_relation_reads(queries, model) for model in (Source, Resource)
    ) == ([], [])


@pytest.mark.django_db
def test_staff_same_state_keeps_case_history_unchanged_with_preloaded_relations(
    staff_client,
    monitoring_case,
    record_property,
):
    """Fails if a no-op state request creates audit history or reloads serialized relations."""
    client, _ = staff_client
    monitoring_case.closed_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    monitoring_case.save(update_fields=["closed_at"])

    with CaptureQueriesContext(connection) as queries:
        response = client.post(
            f"{CASES_URL}{monitoring_case.pk}/state/",
            {"state": "pending", "version": monitoring_case.version},
            format="json",
        )

    monitoring_case.refresh_from_db()
    body = response.json()
    record_property("query_count_same_state", len(queries))
    assert (response.status_code, body["version"], body["state"]) == (200, 2, "pending")
    assert (body["source_name"], body["resource"]["key"]) == ("Integrity", "projectapp")
    assert (
        CaseActivity.objects.filter(case=monitoring_case).count(),
        monitoring_case.closed_at is not None,
    ) == (0, True)
    assert len(queries) <= MAX_CASE_STATE_QUERIES
    assert tuple(
        len(_table_selects(queries, model)) for model in (Case, Source, Resource)
    ) == (1, 1, 1)
    assert tuple(
        _independent_relation_reads(queries, model) for model in (Source, Resource)
    ) == ([], [])
