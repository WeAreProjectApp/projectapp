"""Panel boundary tests for requirement-calculator administration."""

from copy import deepcopy
import hashlib
import json

import pytest
from accounts.models import Project, UserProfile
from django.urls import reverse

from content.models import (
    CalculatorEstimate,
    CalculatorRevision,
    Document,
    DocumentType,
    ProjectCalculatorVersion,
    RequirementCalculator,
)
from content.services import requirement_calculator as calculator

pytestmark = pytest.mark.django_db


@pytest.fixture
def calculator_admin(django_user_model):
    return django_user_model.objects.create_user(
        username="calculator-view-admin", is_staff=True
    )


@pytest.fixture
def calculator_state(calculator_admin):
    DocumentType.objects.get_or_create(code="markdown", defaults={"name": "Markdown"})
    definition = calculator.seed_definition()
    definition["signals"] = [
        next(row for row in definition["signals"] if row["size"] == size)
        for size in ("XS", "S", "M", "L", "XL", "PROJECT")
    ]
    definition["families"] = definition["families"][:1]
    definition["modifiers"] = definition["modifiers"][:2]
    return calculator.publish(
        definition,
        note="Initial definition",
        if_match="uninitialized",
        actor=calculator_admin,
    )


@pytest.fixture
def calculator_project(django_user_model):
    owner = django_user_model.objects.create_user(username="calculator-view-owner")
    UserProfile.objects.get_or_create(user=owner, defaults={"role": "client"})
    return Project.objects.create(name="Calculator view project", client=owner)


@pytest.fixture
def project_draft(calculator_state, calculator_project, calculator_admin):
    return calculator.create_project_draft(
        calculator_project.pk,
        base_revision_id=calculator_state["revision_id"],
        note="Negotiated version",
        if_match=calculator.project_overview(calculator_project.pk)["if_match"],
        actor=calculator_admin,
    )


def _authenticate(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


def _estimate_payload(state):
    signal = next(row for row in state["definition"]["signals"] if row["size"] == "XS")
    return {
        "request_id": "e6e22d8c-e2a2-43f9-b89e-8d5e2785e0a5",
        "revision_id": state["revision_id"],
        "definition_digest": calculator.digest(state["definition"]),
        "requirement": "Adjust an existing field",
        "size": "XS",
        "signal_ids": [signal["id"]],
        "explanation": "Existing field adjustment.",
    }


def test_definition_read_returns_uninitialized_contract_without_revision(
    api_client, calculator_admin,
):
    """Fails if reading an empty calculator initializes or revises its catalog."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-definition")
    )

    assert response.status_code == 200
    assert response.json()["initialized"] is False
    assert response.json()["if_match"] == "uninitialized"
    assert response.json()["definition"]["schema_version"] == 1
    assert response.json()["definition"]["title"] == "Calculadora de requerimientos"
    assert [row["id"] for row in response.json()["definition"]["sizes"]] == [
        "XS",
        "S",
        "M",
        "L",
        "XL",
    ]
    assert CalculatorRevision.objects.count() == 0


def test_preview_returns_the_submitted_definition_without_creating_revision(
    api_client, calculator_admin, calculator_state,
):
    """Fails if a preview persists rules or hashes a definition other than the request."""
    before_count = CalculatorRevision.objects.count()
    # quality: allow-reimpl (validates the canonical SHA-256 contract independently of the service helper)
    expected_digest = hashlib.sha256(
        json.dumps(
            calculator_state["definition"],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    response = _authenticate(api_client, calculator_admin).post(
        reverse("calculator-preview"),
        {"definition": calculator_state["definition"]},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["definition"] == calculator_state["definition"]
    assert response.json()["digest"] == expected_digest
    assert response.json()["markdown"].startswith("# Calculadora de requerimientos")
    assert CalculatorRevision.objects.count() == before_count


def test_preview_rejects_metadata_outside_definition_without_revision(
    api_client, calculator_admin, calculator_state,
):
    """Fails if preview accepts publication metadata or mutates the revision catalog."""
    before_count = CalculatorRevision.objects.count()

    response = _authenticate(api_client, calculator_admin).post(
        reverse("calculator-preview"),
        {"definition": calculator_state["definition"], "note": "Do not persist"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json() == ["Envía únicamente definition."]
    assert CalculatorRevision.objects.count() == before_count


def test_revision_list_paginates_without_exposing_definition(
    api_client, calculator_admin, calculator_state,
):
    """Fails if the revision list ignores offset or exposes complete internal rules."""
    calculator.publish(
        calculator_state["definition"],
        note="Second definition",
        if_match=calculator_state["if_match"],
        actor=calculator_admin,
    )

    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-revisions"),
        {"limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 2
    result = response.json()["results"]
    assert len(result) == 1
    assert {
        "id": result[0]["id"],
        "digest": result[0]["digest"],
        "note": result[0]["note"],
        "author_id": result[0]["author_id"],
    } == {
        "id": calculator_state["revision_id"],
        "digest": calculator_state["digest"],
        "note": "Initial definition",
        "author_id": calculator_admin.pk,
    }
    assert set(result[0]) == {"id", "digest", "note", "author_id", "created_at"}


def test_revision_list_rejects_non_numeric_pagination_without_mutation(
    api_client, calculator_admin, calculator_state,
):
    """Fails if invalid pagination reaches revision storage instead of returning a client error."""
    before_count = CalculatorRevision.objects.count()

    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-revisions"), {"limit": "not-a-number"}
    )

    assert response.status_code == 400
    assert response.json() == ["La paginación necesita números enteros."]
    assert CalculatorRevision.objects.count() == before_count


@pytest.mark.parametrize(
    'query',
    (
        {'limit': 0},
        {'limit': 51},
        {'offset': -1},
    ),
)
def test_revision_list_rejects_out_of_contract_pagination(
    api_client, calculator_admin, calculator_state, query,
):
    """Fails if unbounded or negative revision pages reach the administrative history."""
    before_count = CalculatorRevision.objects.count()

    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-revisions"), query
    )

    assert response.status_code == 400
    assert response.json() == [
        "Usa limit entre 1 y 50 y offset no negativo."
    ]
    assert CalculatorRevision.objects.count() == before_count


def test_revision_detail_returns_the_published_definition(
    api_client, calculator_admin, calculator_state,
):
    """Fails if revision detail falls back to the summary payload without editable rules."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-revision", args=[calculator_state["revision_id"]])
    )

    assert response.status_code == 200
    assert response.json()["id"] == calculator_state["revision_id"]
    assert response.json()["definition"] == calculator_state["definition"]


def test_project_calculator_summary_hides_version_definition(
    api_client, calculator_admin, calculator_project, project_draft,
):
    """Fails if a project summary leaks the full rules stored in a negotiated version."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("project-calculator", args=[calculator_project.pk])
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == calculator_project.pk
    assert response.json()["versions"][0]["id"] == project_draft["id"]
    assert "definition" not in response.json()["versions"][0]


def test_project_calculator_draft_detail_returns_its_definition(
    api_client, calculator_admin, project_draft,
):
    """Fails if draft detail returns a project summary or another version's rules."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("project-calculator-draft", args=[project_draft["id"]])
    )

    assert response.status_code == 200
    assert response.json()["id"] == project_draft["id"]
    assert response.json()["definition"] == project_draft["definition"]


def test_project_draft_patch_rejects_document_reassignment(
    api_client, calculator_admin, project_draft,
):
    """Fails if a panel patch can point a negotiated calculator version at another document."""
    version = ProjectCalculatorVersion.objects.get(pk=project_draft["id"])
    before = (version.document_id, version.digest)
    payload = {
        "definition": project_draft["definition"],
        "note": "Attempted document reassignment",
        "if_match": project_draft["if_match"],
        "document_id": version.document_id,
    }

    response = _authenticate(api_client, calculator_admin).patch(
        reverse("project-calculator-draft", args=[project_draft["id"]]),
        payload,
        format="json",
    )

    version.refresh_from_db()
    assert response.status_code == 400
    assert response.json() == ["El documento particular ya está vinculado."]
    assert (version.document_id, version.digest) == before


@pytest.mark.parametrize("project_id", [0, "abc"])
def test_context_rejects_invalid_project_identifiers(
    api_client, calculator_admin, project_id,
):
    """Fails if malformed project identifiers reach an ambiguous calculator lookup."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-context"), {"project_id": project_id}
    )

    assert response.status_code == 400
    assert response.json() == {"project_id": ["Indica un identificador positivo."]}


def test_context_rejects_requirement_longer_than_limit_without_estimate(
    api_client, calculator_admin, calculator_state,
):
    """Fails if an unbounded requirement can pass through context and create work data."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-context"), {"requirement": "x" * 30001}
    )

    assert response.status_code == 400
    assert response.json() == ["El requerimiento supera 30000 caracteres."]
    assert CalculatorEstimate.objects.count() == 0


def test_context_requires_project_for_project_version(
    api_client, calculator_admin, project_draft,
):
    """Fails if a negotiated version can be read without checking its project relationship."""
    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-context"), {"project_version_id": project_draft["id"]}
    )

    assert response.status_code == 400
    assert response.json() == [
        "Indica el proyecto al consultar una versión particular."
    ]


def test_context_requires_a_published_calculator_without_writes(
    api_client, calculator_admin,
):
    """Fails if context returns empty rules before a general calculator has been published."""
    before_counts = (
        CalculatorRevision.objects.count(),
        Document.objects.count(),
        CalculatorEstimate.objects.count(),
    )

    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-context")
    )

    assert response.status_code == 400
    assert response.json() == [
        "Inicializa primero la calculadora desde el panel."
    ]
    assert RequirementCalculator.objects.count() == 0
    assert (
        CalculatorRevision.objects.count(),
        Document.objects.count(),
        CalculatorEstimate.objects.count(),
    ) == before_counts


def test_context_rejects_a_version_from_another_project(
    api_client,
    calculator_admin,
    calculator_project,
    calculator_state,
    django_user_model,
    project_draft,
):
    """Fails if a known version identifier can expose another project's negotiated rules."""
    second_owner = django_user_model.objects.create_user(
        username="calculator-second-owner"
    )
    UserProfile.objects.get_or_create(
        user=second_owner, defaults={"role": "client"}
    )
    second_project = Project.objects.create(
        name="Second calculator project", client=second_owner
    )
    second_draft = calculator.create_project_draft(
        second_project.pk,
        base_revision_id=calculator_state["revision_id"],
        note="Other negotiated version",
        if_match=calculator.project_overview(second_project.pk)["if_match"],
        actor=calculator_admin,
    )
    first_version = ProjectCalculatorVersion.objects.get(pk=project_draft["id"])
    other_version = ProjectCalculatorVersion.objects.get(pk=second_draft["id"])
    before_first = (
        first_version.pk,
        first_version.document_id,
        first_version.definition,
        first_version.status,
    )
    before_other = (
        other_version.pk,
        other_version.document_id,
        other_version.definition,
        other_version.status,
    )

    response = _authenticate(api_client, calculator_admin).get(
        reverse("calculator-context"),
        {
            "project_id": calculator_project.pk,
            "project_version_id": second_draft["id"],
        },
    )

    first_version.refresh_from_db()
    other_version.refresh_from_db()
    assert response.status_code == 404
    assert (
        first_version.pk,
        first_version.document_id,
        first_version.definition,
        first_version.status,
    ) == before_first
    assert (
        other_version.pk,
        other_version.document_id,
        other_version.definition,
        other_version.status,
    ) == before_other


def test_definition_endpoint_rejects_authenticated_non_staff(
    api_client, django_user_model
):
    """Fails if a signed-in client can read the internal calculator definition."""
    client_user = django_user_model.objects.create_user(username="calculator-client")

    response = _authenticate(api_client, client_user).get(
        reverse("calculator-definition")
    )

    assert response.status_code == 403


def test_estimate_endpoint_rejects_authenticated_non_staff(
    api_client, django_user_model, calculator_state
):
    """Fails if a signed-in client can add an internal execution estimate."""
    client_user = django_user_model.objects.create_user(
        username="calculator-estimate-client"
    )

    response = _authenticate(api_client, client_user).post(
        reverse("calculator-estimates"),
        _estimate_payload(calculator_state),
        format="json",
    )

    assert response.status_code == 403
    assert CalculatorEstimate.objects.count() == 0


def test_definition_write_rejects_conflicting_if_match_values(
    api_client, calculator_admin, calculator_state
):
    """Fails if contradictory concurrency preconditions can publish a revision."""
    payload = {
        "definition": calculator_state["definition"],
        "note": "Conflicting version",
        "if_match": calculator_state["if_match"],
    }

    response = _authenticate(api_client, calculator_admin).post(
        reverse("calculator-definition"),
        payload,
        format="json",
        HTTP_IF_MATCH="general:999:other",
    )

    assert response.status_code == 400
    assert CalculatorRevision.objects.count() == 1


def test_definition_write_returns_conflict_for_stale_if_match(
    api_client, calculator_admin, calculator_state
):
    """Fails if an obsolete uniform precondition can overwrite current rules."""
    calculator.publish(
        calculator_state["definition"],
        note="New current revision",
        if_match=calculator_state["if_match"],
        actor=calculator_admin,
    )
    payload = {
        "definition": calculator_state["definition"],
        "note": "Stale revision",
        "if_match": calculator_state["if_match"],
    }

    response = _authenticate(api_client, calculator_admin).post(
        reverse("calculator-definition"),
        payload,
        format="json",
        HTTP_IF_MATCH=calculator_state["if_match"],
    )

    assert response.status_code == 409
    assert CalculatorRevision.objects.count() == 2


def test_approved_project_version_rejects_panel_parameter_patch(
    api_client,
    calculator_admin,
    project_draft,
):
    """Fails if the panel can alter an approved agreement without another draft."""
    approved = calculator.approve_project_version(
        project_draft["id"],
        note="Approved agreement",
        if_match=project_draft["if_match"],
        actor=calculator_admin,
    )
    original = ProjectCalculatorVersion.objects.get(pk=approved["id"])
    before = (
        original.digest,
        deepcopy(original.definition),
        original.status,
        original.pdf_digest,
    )
    payload = {
        "definition": original.definition,
        "note": "Attempted rewrite",
        "if_match": approved["if_match"],
    }

    response = _authenticate(api_client, calculator_admin).patch(
        reverse("project-calculator-draft", args=[approved["id"]]),
        payload,
        format="json",
    )

    original.refresh_from_db()
    assert response.status_code == 400
    assert (
        original.digest,
        original.definition,
        original.status,
        original.pdf_digest,
    ) == before


def test_document_update_rejects_managed_calculator_body(
    api_client, calculator_admin, calculator_state
):
    """Fails if the generic document API can overwrite calculator content."""
    document = Document.objects.get(pk=calculator_state["document_id"])

    response = _authenticate(api_client, calculator_admin).patch(
        reverse("update-document", args=[document.pk]),
        {"content_markdown": "Unauthorized rewrite"},
        format="json",
    )

    document.refresh_from_db()
    assert response.status_code == 400
    assert document.content_markdown.startswith("# Calculadora de requerimientos")
