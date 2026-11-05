"""Query and payload budgets for calculator administrative histories."""

import uuid
from copy import deepcopy

import pytest
from accounts.models import Project
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from content.models import (
    CalculatorActual,
    CalculatorEstimate,
    CalculatorRevision,
    Document,
    DocumentType,
    ProjectCalculatorVersion,
)
from content.services import calculator_calibration as calibration
from content.services import requirement_calculator as calculator

pytestmark = pytest.mark.django_db


def _definition():
    definition = calculator.seed_definition()
    definition["methodology"] = "Método interno documentado. " * 400
    definition["signals"] = [
        next(row for row in definition["signals"] if row["size"] == size)
        for size in ("XS", "S", "M", "L", "XL", "PROJECT")
    ]
    definition["families"] = definition["families"][:1]
    definition["modifiers"] = definition["modifiers"][:2]
    return calculator.normalized(definition)


@pytest.fixture
def history_rows(django_user_model):
    actor = django_user_model.objects.create_user(username="calculator-history-owner")
    owner = django_user_model.objects.create_user(username="calculator-history-client")
    doc_type, _ = DocumentType.objects.get_or_create(
        code="markdown", defaults={"name": "Markdown"}
    )
    first_definition = _definition()
    second_definition = deepcopy(first_definition)
    second_definition["sizes"][0]["points"] = "1.5"
    first = CalculatorRevision.objects.create(
        definition=first_definition,
        digest=calculator.digest(first_definition),
        note="First revision",
        author=actor,
    )
    second = CalculatorRevision.objects.create(
        definition=second_definition,
        digest=calculator.digest(second_definition),
        note="Second revision",
        author=actor,
    )
    project = Project.objects.create(name="History budget project", client=owner)
    first_document = Document.objects.create(
        title="First agreement",
        document_type=doc_type,
        project=project,
        client_user=owner,
    )
    second_document = Document.objects.create(
        title="Second agreement",
        document_type=doc_type,
        project=project,
        client_user=owner,
    )
    approved = ProjectCalculatorVersion.objects.create(
        project=project,
        base_revision=first,
        document=first_document,
        definition=first_definition,
        digest=calculator.digest(first_definition),
        note="First agreement",
        author=actor,
        status="approved",
        approved_by=actor,
        approved_at=timezone.now(),
        pdf_content=b"a" * 50000,
        pdf_digest="4" * 64,
    )
    project.calculator_document = first_document
    project.save(update_fields=["calculator_document", "updated_at"])
    draft = ProjectCalculatorVersion.objects.create(
        project=project,
        base_revision=second,
        document=second_document,
        definition=second_definition,
        digest=calculator.digest(second_definition),
        note="Second agreement",
        author=actor,
    )
    return {
        "project": project,
        "revisions": (first, second),
        "versions": (approved, draft),
        "actor": actor,
    }


def _estimate(revision, *, identifier, actor):
    estimate = CalculatorEstimate.objects.create(
        revision=revision,
        request_id=uuid.UUID(identifier),
        requirement="Requirement " + "r" * 500,
        size="XS",
        signal_ids=["signal-xs"],
        explanation="Explanation " + "e" * 500,
        expected_size="",
        snapshot={"rules": "snapshot-" + "z" * 50000},
        definition_digest=revision.digest,
        author=actor,
    )
    CalculatorActual.objects.create(
        estimate=estimate,
        actual_hours="2.00",
        hourly_cost_cop="30000.00",
        evidence="Evidence " + "v" * 200,
        cause="Cause " + "c" * 200,
        author=actor,
    )
    return estimate


def _measure_estimates():
    with CaptureQueriesContext(connection) as queries:
        payload = calibration.estimates(limit=20)
    return (
        len(queries),
        payload,
        [query["sql"].lower() for query in queries.captured_queries],
    )


def test_version_histories_omit_large_blobs_with_fixed_query_budget(history_rows):
    """Fails if a revision or agreement history loads its definition or frozen PDF per row."""
    with CaptureQueriesContext(connection) as revision_queries:
        revisions = calculator.list_revisions()
    with CaptureQueriesContext(connection) as project_queries:
        project = calculator.project_overview(history_rows["project"].pk)
    revision_sql = "\n".join(
        query["sql"].lower() for query in revision_queries.captured_queries
    )
    project_sql = "\n".join(
        query["sql"].lower() for query in project_queries.captured_queries
    )

    assert len(revision_queries) <= 2
    assert all("definition" not in row for row in revisions["results"])
    assert "definition" not in revision_sql
    assert len(project_queries) <= 3
    assert all(
        "definition" not in row and "pdf_content" not in row
        for row in project["versions"]
    )
    assert "definition" not in project_sql
    assert "pdf_content" not in project_sql


def test_estimate_history_keeps_flat_queries_without_snapshots(history_rows):
    """Fails if more estimates add queries or load stored rule snapshots."""
    _estimate(
        history_rows["revisions"][0],
        identifier="ad7154f8-2adf-4fb6-b054-d9e85c3648a6",
        actor=history_rows["actor"],
    )
    one_count, one, one_sql = _measure_estimates()
    _estimate(
        history_rows["revisions"][0],
        identifier="7cdc6afd-74c3-406a-bb4d-841fe3dd4213",
        actor=history_rows["actor"],
    )
    _estimate(
        history_rows["revisions"][1],
        identifier="d8b27753-658b-438a-94b4-4ebc2f46cc4a",
        actor=history_rows["actor"],
    )
    many_count, many, many_sql = _measure_estimates()

    assert one_count == many_count <= 3
    assert all("snapshot" not in row for row in [*one["results"], *many["results"]])
    assert "snapshot" not in "\n".join([*one_sql, *many_sql])


def test_estimate_summary_preserves_full_text_in_detail(history_rows):
    """Fails if a compact list loses the full requirement or closure evidence."""
    first = _estimate(
        history_rows["revisions"][0],
        identifier="ad7154f8-2adf-4fb6-b054-d9e85c3648a6",
        actor=history_rows["actor"],
    )
    summary = calibration.estimates(limit=20)["results"][0]

    assert (summary["is_summary"], len(summary["requirement"])) == (True, 320)
    assert (
        calibration.estimate_detail(first.pk)["requirement"],
        calibration.actual_history(first.pk)["results"][0]["evidence"],
    ) == (first.requirement, first.actuals.get().evidence)
