"""Calculator rules and client agreements retain their effective definitions."""

import json
import uuid
from copy import deepcopy
from decimal import Decimal

import pytest
from accounts.models import Project, UserProfile
from django.core.management import call_command
from rest_framework.exceptions import ValidationError

from content.models import (
    CalculatorActual,
    CalculatorEstimate,
    CalculatorRevision,
    Document,
    DocumentType,
    HourPackageSettings,
    ProjectCalculatorVersion,
    RequirementCalculator,
)
from content.serializers.requirement_calculator import DefinitionSerializer
from content.services import calculator_calibration as calibration
from content.services import requirement_calculator as calculator
from content.services.document_pdf_service import DocumentPdfService

pytestmark = pytest.mark.django_db

_PRIVATE_CLIENT_MARKERS = (
    "87654",
    "87655",
    "7654321",
    "654.321",
    "543.210",
    "543.211",
    "432.123",
    "6789012",
    "hours_min",
    "hours_max",
    "standard_value_cop",
    "surcharge_percent",
    "hourly_cost_cop",
    "banda interna de horas",
    "valor estándar cop",
    "calibración interna",
)


@pytest.fixture
def calculator_admin(django_user_model):
    return django_user_model.objects.create_user(
        username="calculator-admin", is_staff=True
    )


@pytest.fixture
def calculator_state(calculator_admin):
    DocumentType.objects.get_or_create(code="markdown", defaults={"name": "Markdown"})
    return calculator.publish(
        _reduced_definition(),
        note="Initial definition",
        if_match="uninitialized",
        actor=calculator_admin,
    )


def _reduced_definition():
    config = calculator.seed_definition()
    config["signals"] = [
        next(row for row in config["signals"] if row["size"] == size)
        for size in ("XS", "S", "M", "L", "XL", "PROJECT")
    ]
    config["families"] = config["families"][:1]
    config["modifiers"] = config["modifiers"][:2]
    return config


@pytest.fixture
def calculator_project(django_user_model):
    owner = django_user_model.objects.create_user(username="calculator-owner")
    UserProfile.objects.get_or_create(user=owner, defaults={"role": "client"})
    return Project.objects.create(name="Calculator project", client=owner)


@pytest.fixture
def project_draft(calculator_state, calculator_project, calculator_admin):
    return calculator.create_project_draft(
        calculator_project.pk,
        base_revision_id=calculator_state["revision_id"],
        note="Negotiated version",
        if_match=calculator.project_overview(calculator_project.pk)["if_match"],
        actor=calculator_admin,
    )


@pytest.fixture
def adopted_general_document(calculator_admin):
    document_type, _ = DocumentType.objects.get_or_create(
        code="markdown", defaults={"name": "Markdown"}
    )
    document = Document.objects.create(
        title="Adoptable calculator", document_type=document_type
    )
    stale_copy = Document.objects.get(pk=document.pk)
    calculator.publish(
        _reduced_definition(),
        note="Adopt existing document",
        if_match="uninitialized",
        actor=calculator_admin,
        document_id=document.pk,
    )
    document.refresh_from_db()
    return document, stale_copy


def test_publishing_updates_shared_size_price(calculator_state, calculator_admin):
    config = deepcopy(calculator_state["definition"])
    config["sizes"][0]["standard_value_cop"] = "62000"

    calculator.publish(
        config,
        note="Adjust XS",
        if_match=calculator_state["if_match"],
        actor=calculator_admin,
    )

    assert HourPackageSettings.load().xs_price_cop == Decimal(62000)


def test_publishing_rejects_stale_definition(calculator_state, calculator_admin):
    """Fails if an obsolete editor can overwrite the currently published rules."""
    calculator.publish(
        calculator_state["definition"],
        note="New revision",
        if_match=calculator_state["if_match"],
        actor=calculator_admin,
    )

    with pytest.raises(calculator.CalculatorConflict):
        calculator.publish(
            calculator_state["definition"],
            note="Stale edit",
            if_match=calculator_state["if_match"],
            actor=calculator_admin,
        )

    assert CalculatorRevision.objects.count() == 2


def test_project_draft_rejects_body_changes(project_draft, calculator_admin):
    """Fails if a project draft can alter agreed classification text or formulas."""
    config = deepcopy(project_draft["definition"])
    config["methodology"] = "Replace the agreed methodology"

    with pytest.raises(ValidationError, match="parámetros"):
        calculator.update_project_draft(
            project_draft["id"],
            definition=config,
            note="Attempt body edit",
            if_match=project_draft["if_match"],
            actor=calculator_admin,
        )

    assert (
        ProjectCalculatorVersion.objects.get(pk=project_draft["id"]).digest
        == project_draft["digest"]
    )


def test_project_draft_preserves_original_base(
    calculator_state, project_draft, calculator_admin
):
    """Fails if a later global revision retroactively changes a negotiated draft."""
    config = deepcopy(calculator_state["definition"])
    config["sizes"][0]["definition"] = "A new general definition"

    calculator.publish(
        config,
        note="New explanation",
        if_match=calculator_state["if_match"],
        actor=calculator_admin,
    )

    version = ProjectCalculatorVersion.objects.get(pk=project_draft["id"])
    assert (
        version.definition["sizes"][0]["definition"]
        == project_draft["definition"]["sizes"][0]["definition"]
    )


def test_approval_preserves_pdf_after_general_change(
    calculator_state, project_draft, calculator_admin
):
    """The real renderer must retain the exact client PDF across global changes."""
    approved = calculator.approve_project_version(
        project_draft["id"],
        note="Agreed",
        if_match=project_draft["if_match"],
        actor=calculator_admin,
    )
    document = Document.objects.get(pk=approved["document_id"])
    original = DocumentPdfService.generate(document)
    config = deepcopy(calculator_state["definition"])
    config["sizes"][0]["points"] = "1.5"

    calculator.publish(
        config,
        note="New points",
        if_match=calculator_state["if_match"],
        actor=calculator_admin,
    )

    document.refresh_from_db()
    assert DocumentPdfService.generate(document) == original
    assert original.startswith(b"%PDF-")


def _private_project_parameters(definition):
    config = deepcopy(definition)
    config["sizes"][0].update(
        hours_min="87654", hours_max="87655", standard_value_cop="7654321"
    )
    config["signals"][0]["surcharge_percent"] = "654.321"
    config["modifiers"][0].update(minimum="543.210", maximum="543.211")
    config["calibration"].update(deviation_percent="432.123", hourly_cost_cop="6789012")
    return config


def _client_document_copy(document):
    return "\n".join(
        (
            document.content_markdown,
            json.dumps(document.content_json, ensure_ascii=False),
        )
    ).casefold()


def _seed_project_lifecycle_catalog():
    from importlib import import_module
    from content.models import DocumentState, DocumentStateGroup

    group, _ = DocumentStateGroup.objects.get_or_create(
        catalog="projects", name="Ciclo del proyecto",
        defaults={"selection_mode": "exclusive", "order": 0},
    )
    states = import_module("content.migrations.0214_seed_project_lifecycle_states").PROJECT_STATES
    for name, key, color, effect, order in states:
        DocumentState.objects.get_or_create(
            catalog="projects", system_key=key,
            defaults={"name": name, "normalized_name": name.casefold(),
                      "slug": key.replace("_", "-"), "color": color,
                      "group": group, "order": order, "operational_effect": effect},
        )
    DocumentState.objects.get_or_create(
        catalog="projects", system_key="evolving",
        defaults={"name": "En evolución", "normalized_name": "en evolucion",
                  "slug": "evolving", "color": "blue", "group": group,
                  "order": 2, "operational_effect": "operating"},
    )


def test_project_document_excludes_internal_calibration_values(
    project_draft, calculator_admin
):
    """Fails if a client agreement exposes internal effort bands or calibration values."""
    updated = calculator.update_project_draft(
        project_draft["id"],
        definition=_private_project_parameters(project_draft["definition"]),
        note="Private calibration values",
        if_match=project_draft["if_match"],
        actor=calculator_admin,
    )
    document = Document.objects.get(pk=updated["document_id"])
    client_copy = _client_document_copy(document)

    assert all(marker not in client_copy for marker in _PRIVATE_CLIENT_MARKERS)
    assert (
        f"**versión:** {updated['base_revision_id']}/{updated['id']}".casefold()
        in client_copy
    )
    assert "## xs —" in client_copy
    assert "## señales de clasificación" in client_copy


def test_save_rejects_document_loaded_before_calculator_adoption(
    adopted_general_document,
):
    """Fails if a stale generic document object can rewrite content after calculator adoption."""
    document, stale_copy = adopted_general_document
    stale_copy.content_markdown = "Stale rewrite after adoption"

    with pytest.raises(ValidationError, match="Calculadora"):
        stale_copy.save()

    document.refresh_from_db()
    assert document.content_markdown.startswith("# Calculadora de requerimientos")


def test_bulk_update_rejects_adopted_calculator_content(adopted_general_document):
    """Fails if an untracked bulk field can bypass the calculator document write guard."""
    document, _ = adopted_general_document
    original_json = deepcopy(document.content_json)

    with pytest.raises(ValidationError, match="Calculadora"):
        Document.objects.filter(pk=document.pk).update(
            content_json={"blocks": ["Unauthorized rewrite"]}
        )

    document.refresh_from_db()
    assert document.content_json == original_json


def test_fake_refresh_preserves_general_calculator_definition(calculator_state):
    """Fails if a fake-data refresh treats the published calculator catalog as business data."""
    general = RequirementCalculator.objects.get()
    document_id, revision_id = general.document_id, general.current_revision_id

    call_command("delete_fake_data", "--confirm", verbosity=0)
    _seed_project_lifecycle_catalog()
    call_command(
        "create_fake_data",
        "--count",
        "1",
        "--skip-contacts",
        "--skip-proposals",
        "--skip-blog",
        "--skip-portfolio",
        "--skip-tasks",
        "--skip-diagnostics",
        "--skip-financing",
        "--skip-accounting",
        "--skip-documents",
        "--skip-communications",
        "--skip-auxiliary",
        verbosity=0,
    )

    preserved = RequirementCalculator.objects.get()
    assert (preserved.document_id, preserved.current_revision_id) == (
        document_id,
        revision_id,
    )
    assert (
        Document.objects.get(pk=document_id).metadata["requirement_calculator"]["kind"]
        == "general"
    )


def test_fake_reset_releases_project_calculator_graph(
    calculator_state, calculator_project, project_draft, calculator_admin
):
    """Fails if a confirmed fake reset leaves protected negotiated calibration records behind."""
    estimate = calibration.record_estimate(
        _estimate_data(
            calculator_state,
            request_id="180756a1-92ee-4fe1-b86e-b855a892621b",
            project_id=calculator_project.pk,
            project_version_id=project_draft["id"],
        ),
        actor=calculator_admin,
    )
    closure = calibration.record_actual(
        {
            "estimate_id": estimate["id"],
            "actual_hours": Decimal(3),
            "hourly_cost_cop": Decimal(30000),
            "evidence": "Initial close",
            "cause": "Delivered scope",
        },
        actor=calculator_admin,
    )
    correction = calibration.record_actual(
        {
            "estimate_id": estimate["id"],
            "supersedes_id": closure["id"],
            "actual_hours": Decimal(4),
            "hourly_cost_cop": Decimal(30000),
            "evidence": "Corrected close",
            "cause": "Measured again",
        },
        actor=calculator_admin,
    )

    call_command("delete_fake_data", "--confirm", verbosity=0)

    assert not Project.objects.filter(pk=calculator_project.pk).exists()
    assert not ProjectCalculatorVersion.objects.filter(pk=project_draft["id"]).exists()
    assert not Document.objects.filter(pk=project_draft["document_id"]).exists()
    assert not CalculatorEstimate.objects.filter(pk=estimate["id"]).exists()
    assert not CalculatorActual.objects.filter(
        pk__in=(closure["id"], correction["id"])
    ).exists()


def test_generic_document_save_rejects_calculator_body(calculator_state):
    document = Document.objects.get(pk=calculator_state["document_id"])
    document.content_markdown = "Changed outside calculator"

    with pytest.raises(ValidationError, match="Calculadora"):
        document.save()

    document.refresh_from_db()
    assert document.content_markdown.startswith("# Calculadora de requerimientos")


def test_unassigned_project_context_warns(calculator_state, calculator_project):
    context = calculator.calculator_context(project_id=calculator_project.pk)

    assert context["revision_id"] == calculator_state["revision_id"]
    assert "no tiene calculadora aprobada" in context["warning"]


def test_explicit_project_draft_context_identifies_unapproved_rules(
    calculator_project, project_draft,
):
    """Fails if context treats an explicit unapproved agreement as the general calculator."""
    context = calculator.calculator_context(
        project_id=calculator_project.pk,
        project_version_id=project_draft["id"],
    )

    assert context["project_version_id"] == project_draft["id"]
    assert context["definition"] == project_draft["definition"]
    assert context["warning"] == (
        "Borrador explícito: sus condiciones todavía no están aprobadas."
    )


def test_recorded_closure_uses_actual_cost(calculator_state, calculator_admin):
    """Fails if an accepted closure stops contributing its measured execution cost."""
    config = calculator_state["definition"]
    signal = next(row for row in config["signals"] if row["size"] == "XS")
    estimate = calibration.record_estimate(
        {
            "request_id": uuid.UUID("ae391ea0-b14f-43fb-9aa6-5dc533b57181"),
            "revision_id": calculator_state["revision_id"],
            "definition_digest": calculator.digest(config),
            "requirement": "Adjust an existing field",
            "size": "XS",
            "signal_ids": [signal["id"]],
            "explanation": "Existing field adjustment.",
        },
        actor=calculator_admin,
    )

    calibration.record_actual(
        {
            "estimate_id": estimate["id"],
            "actual_hours": Decimal(2),
            "hourly_cost_cop": Decimal(30000),
            "evidence": "Confirmed execution log",
            "cause": "Delivered scope",
        },
        actor=calculator_admin,
    )

    cohort = calibration.report()["cohorts"][0]
    assert cohort["median_cost_cop"] == "60000.0000"
    assert cohort["covers_median_cost"] is False
    assert cohort["status"] == "insufficient_data"


def _estimate_data(
    state, *, request_id, size="XS", project_id=None, project_version_id=None
):
    signal = next(row for row in state["definition"]["signals"] if row["size"] == "XS")
    return {
        "request_id": uuid.UUID(request_id),
        "revision_id": state["revision_id"],
        "project_id": project_id,
        "project_version_id": project_version_id,
        "definition_digest": calculator.digest(state["definition"]),
        "requirement": "Adjust an existing field",
        "size": size,
        "signal_ids": [signal["id"]],
        "explanation": "Existing field adjustment.",
    }


def _closed_estimate(state, *, request_id, actor, evidence):
    estimate = calibration.record_estimate(
        _estimate_data(state, request_id=request_id), actor=actor
    )
    calibration.record_actual(
        {
            "estimate_id": estimate["id"],
            "actual_hours": Decimal(20),
            "hourly_cost_cop": Decimal(30000),
            "evidence": evidence,
            "cause": "Delivered scope",
        },
        actor=actor,
    )


def test_record_estimate_replays_same_request_without_duplicate(
    calculator_state, calculator_admin
):
    """Fails if a chat retry writes a second estimate for the same request."""
    data = _estimate_data(
        calculator_state, request_id="58e55390-6d17-4fa9-ae0e-e451c36e2b14"
    )

    first = calibration.record_estimate(data, actor=calculator_admin)
    replay = calibration.record_estimate(data, actor=calculator_admin)

    assert replay["id"] == first["id"]
    assert CalculatorEstimate.objects.filter(request_id=data["request_id"]).count() == 1


def test_record_estimate_rejects_reused_request_with_other_size(
    calculator_state, calculator_admin
):
    """Fails if a retry can replace the size recorded for the original request."""
    request_id = "c555ce47-8da5-4bc1-9d36-bf47f5c5e552"
    calibration.record_estimate(
        _estimate_data(calculator_state, request_id=request_id), actor=calculator_admin
    )

    with pytest.raises(ValidationError, match="ya corresponde"):
        calibration.record_estimate(
            _estimate_data(calculator_state, request_id=request_id, size="S"),
            actor=calculator_admin,
        )

    assert CalculatorEstimate.objects.get(request_id=request_id).size == "XS"


def test_record_estimate_rejects_reused_request_with_other_project(
    calculator_state,
    calculator_admin,
    calculator_project,
):
    """Fails if a retry can move a recorded estimate to another project."""
    request_id = "9a541ca3-9e18-48a1-b8f0-5bbb562812d2"
    calibration.record_estimate(
        _estimate_data(calculator_state, request_id=request_id), actor=calculator_admin
    )

    with pytest.raises(ValidationError, match="ya corresponde"):
        calibration.record_estimate(
            _estimate_data(
                calculator_state,
                request_id=request_id,
                project_id=calculator_project.pk,
            ),
            actor=calculator_admin,
        )

    assert CalculatorEstimate.objects.get(request_id=request_id).project_id is None


def test_record_estimate_rejects_reused_request_with_other_project_version(
    calculator_state,
    calculator_admin,
    calculator_project,
    project_draft,
):
    """Fails if a retry can replace the negotiated definition used by a request."""
    request_id = "a8db324b-4dbf-42f9-954a-4f22c9ccab7d"
    calibration.record_estimate(
        _estimate_data(
            calculator_state,
            request_id=request_id,
            project_id=calculator_project.pk,
        ),
        actor=calculator_admin,
    )

    with pytest.raises(ValidationError, match="ya corresponde"):
        calibration.record_estimate(
            _estimate_data(
                calculator_state,
                request_id=request_id,
                project_id=calculator_project.pk,
                project_version_id=project_draft["id"],
            ),
            actor=calculator_admin,
        )

    assert (
        CalculatorEstimate.objects.get(request_id=request_id).project_version_id is None
    )


def test_calibration_proposes_review_without_repricing(
    calculator_state, calculator_admin
):
    """Fails if three out-of-band closures automatically change prices or revisions."""
    _closed_estimate(
        calculator_state,
        request_id="4acd9de8-bad5-476a-b886-cece390cb73a",
        actor=calculator_admin,
        evidence="Log one",
    )
    _closed_estimate(
        calculator_state,
        request_id="0ea1de4a-b485-4540-9c5f-bdc329636f5d",
        actor=calculator_admin,
        evidence="Log two",
    )
    _closed_estimate(
        calculator_state,
        request_id="4b2b1420-e4e7-475b-a6f7-57629fd84307",
        actor=calculator_admin,
        evidence="Log three",
    )
    settings = HourPackageSettings.load()
    before = (settings.xs_price_cop, CalculatorRevision.objects.count())

    report = calibration.report()
    settings.refresh_from_db()

    cohort = next(row for row in report["cohorts"] if row["size"] == "XS")
    assert cohort["propose_review"] is True
    assert (settings.xs_price_cop, CalculatorRevision.objects.count()) == before


def test_definition_accepts_separate_modifier_without_numeric_bounds():
    """Fails if a contractual separate item makes the canonical seed unpublishable."""
    definition = calculator.seed_definition()
    separate = next(row for row in definition["modifiers"] if row["kind"] == "separate")
    serializer = DefinitionSerializer(data=definition)

    assert serializer.is_valid(), serializer.errors
    assert (
        serializer.validated_data["modifiers"][definition["modifiers"].index(separate)][
            "minimum"
        ],
        serializer.validated_data["modifiers"][definition["modifiers"].index(separate)][
            "maximum"
        ],
    ) == (None, None)
