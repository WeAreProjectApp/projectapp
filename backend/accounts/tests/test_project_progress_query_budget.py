"""Query-budget contracts for persisted project progress."""

import pytest
from content.models import BusinessProposal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.models import Project, ProjectPhase, Requirement
from accounts.views import _recalculate_project_progress

User = get_user_model()
MAX_PROJECT_PROGRESS_REQUIREMENT_QUERIES = 1


def _requirement_selects(queries):
    table = Requirement._meta.db_table.lower()
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and table in query["sql"].lower()
    ]


def _phase(project, label):
    proposal = BusinessProposal.objects.create(
        title=f"Progress budget proposal {label}",
        client_name="Progress budget client",
    )
    return ProjectPhase.objects.create(
        project=project, business_proposal=proposal, order=1
    )


@pytest.mark.django_db
def test_progress_recalculation_counts_only_active_requirements_for_its_project(
    record_property,
):
    """Falla si el progreso incluye archivados, otra fase de proyecto o repite el conteo de requisitos."""
    client = User.objects.create_user(username="progress-budget-client@example.com")
    project = Project.objects.create(name="Progress budget project", client=client)
    phase = _phase(project, "current")
    other_project = Project.objects.create(
        name="Other progress budget project", client=client
    )
    other_phase = _phase(other_project, "other")
    Requirement.objects.create(
        phase=phase, title="Done one", status=Requirement.STATUS_DONE
    )
    Requirement.objects.create(
        phase=phase, title="Done two", status=Requirement.STATUS_DONE
    )
    Requirement.objects.create(
        phase=phase, title="Pending", status=Requirement.STATUS_TODO
    )
    Requirement.objects.create(
        phase=phase,
        title="Archived done",
        status=Requirement.STATUS_DONE,
        is_archived=True,
    )
    Requirement.objects.create(
        phase=other_phase, title="Other done", status=Requirement.STATUS_DONE
    )

    with CaptureQueriesContext(connection) as queries:
        _recalculate_project_progress(project)

    project.refresh_from_db()
    record_property("query_count_progress", len(queries))
    assert project.progress == 67
    assert (
        len(_requirement_selects(queries)) == MAX_PROJECT_PROGRESS_REQUIREMENT_QUERIES
    )
    assert "COUNT(" in _requirement_selects(queries)[0].upper()


@pytest.mark.django_db
def test_progress_recalculation_persists_zero_without_requirements(record_property):
    """Falla si un proyecto vacío conserva progreso anterior o evita la agregación de requisitos."""
    client = User.objects.create_user(
        username="empty-progress-budget-client@example.com"
    )
    project = Project.objects.create(
        name="Empty progress budget project", client=client, progress=99
    )

    with CaptureQueriesContext(connection) as queries:
        _recalculate_project_progress(project)

    project.refresh_from_db()
    record_property("query_count_empty_progress", len(queries))
    assert project.progress == 0
    assert (
        len(_requirement_selects(queries)) == MAX_PROJECT_PROGRESS_REQUIREMENT_QUERIES
    )
    assert "COUNT(" in _requirement_selects(queries)[0].upper()
