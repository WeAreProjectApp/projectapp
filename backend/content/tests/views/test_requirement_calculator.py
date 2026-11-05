"""Panel boundary tests for requirement-calculator administration."""

from copy import deepcopy

import pytest
from accounts.models import Project, UserProfile
from django.urls import reverse

from content.models import (
    CalculatorEstimate,
    CalculatorRevision,
    Document,
    DocumentType,
    ProjectCalculatorVersion,
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
