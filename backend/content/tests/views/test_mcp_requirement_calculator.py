"""MCP confirmation and document-boundary tests for the requirement calculator."""

import pytest
from accounts.models import Project, UserProfile

from content.models import CalculatorRevision, Document, DocumentType, McpConnector
from content.services import requirement_calculator as calculator
from content.tests.mcp_confirmation_helpers import call_confirmed

pytestmark = pytest.mark.django_db


@pytest.fixture
def calculator_admin(django_user_model):
    return django_user_model.objects.create_user(
        username="calculator-mcp-admin", is_staff=True
    )


@pytest.fixture
def calculator_definition():
    DocumentType.objects.get_or_create(code="markdown", defaults={"name": "Markdown"})
    definition = calculator.seed_definition()
    definition["signals"] = [
        next(row for row in definition["signals"] if row["size"] == size)
        for size in ("XS", "S", "M", "L", "XL", "PROJECT")
    ]
    definition["families"] = definition["families"][:1]
    definition["modifiers"] = definition["modifiers"][:2]
    return definition


@pytest.fixture
def commercial_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug="commercial", defaults={"name": "Commercial"}
    )
    connector.is_active = True
    connector.save(update_fields=["is_active"])
    return connector.generate_token()


@pytest.fixture
def projects_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug="projects", defaults={"name": "Projects"}
    )
    connector.is_active = True
    connector.save(update_fields=["is_active"])
    return connector.generate_token()


@pytest.fixture
def documents_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug="documents", defaults={"name": "Documents"}
    )
    connector.is_active = True
    connector.save(update_fields=["is_active"])
    return connector.generate_token()


@pytest.fixture
def calculator_state(calculator_admin, calculator_definition):
    DocumentType.objects.get_or_create(code="markdown", defaults={"name": "Markdown"})
    return calculator.publish(
        calculator_definition,
        note="Initial definition",
        if_match="uninitialized",
        actor=calculator_admin,
    )


@pytest.fixture
def calculator_project(django_user_model):
    owner = django_user_model.objects.create_user(username="calculator-mcp-owner")
    UserProfile.objects.get_or_create(user=owner, defaults={"role": "client"})
    return Project.objects.create(name="Calculator MCP project", client=owner)


def _url(slug, token):
    return f"/api/mcp/{slug}/{token}/"


def _rpc(method, params=None, msg_id=1):
    payload = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _call(api_client, slug, token, name, arguments):
    return api_client.post(
        _url(slug, token),
        _rpc("tools/call", {"name": name, "arguments": arguments}),
        format="json",
    )


def _confirmed(api_client, slug, token, name, arguments):
    return call_confirmed(api_client, _url(slug, token), _rpc, name, arguments)


def test_capabilities_mark_calculator_publications_as_confirmed(
    api_client, commercial_token, projects_token
):
    """Fails if MCP advertises publishing or approval without a confirmation boundary."""
    commercial = _call(
        api_client, "commercial", commercial_token, "describe_capabilities", {}
    )
    projects = _call(
        api_client, "projects", projects_token, "describe_capabilities", {}
    )
    commercial_tools = {
        row["name"]: row
        for row in commercial.data["result"]["structuredContent"]["tools"]
    }
    project_tools = {
        row["name"]: row
        for row in projects.data["result"]["structuredContent"]["tools"]
    }

    assert (
        commercial_tools["publish_requirement_calculator"]["requires_confirmation"]
        is True
    )
    assert (
        project_tools["approve_project_requirement_calculator"]["requires_confirmation"]
        is True
    )


def test_mcp_publication_waits_for_confirmation(
    api_client, commercial_token, calculator_definition
):
    """Fails if an MCP publish call creates a revision before explicit confirmation."""
    arguments = {
        "definition": calculator_definition,
        "note": "MCP initial definition",
        "if_match": "uninitialized",
    }

    preview = _call(
        api_client,
        "commercial",
        commercial_token,
        "publish_requirement_calculator",
        arguments,
    )

    assert preview.data["result"]["isError"] is False
    assert "confirmation_id" in preview.data["result"]["structuredContent"]
    assert CalculatorRevision.objects.count() == 0
    confirmed = _confirmed(
        api_client,
        "commercial",
        commercial_token,
        "publish_requirement_calculator",
        arguments,
    )
    assert confirmed.data["result"]["isError"] is False
    assert CalculatorRevision.objects.count() == 1


def test_mcp_approval_waits_for_confirmation(
    api_client, projects_token, calculator_state, calculator_project, calculator_admin
):
    """Fails if an MCP approval assigns a document before explicit confirmation."""
    draft = calculator.create_project_draft(
        calculator_project.pk,
        base_revision_id=calculator_state["revision_id"],
        note="Negotiated version",
        if_match=calculator.project_overview(calculator_project.pk)["if_match"],
        actor=calculator_admin,
    )
    arguments = {
        "version_id": draft["id"],
        "note": "Approved from MCP",
        "if_match": draft["if_match"],
    }

    preview = _call(
        api_client,
        "projects",
        projects_token,
        "approve_project_requirement_calculator",
        arguments,
    )

    calculator_project.refresh_from_db()
    assert preview.data["result"]["isError"] is False
    assert calculator_project.calculator_document_id is None
    confirmed = _confirmed(
        api_client,
        "projects",
        projects_token,
        "approve_project_requirement_calculator",
        arguments,
    )
    calculator_project.refresh_from_db()
    assert confirmed.data["result"]["isError"] is False
    assert calculator_project.calculator_document_id == draft["document_id"]


def test_mcp_document_update_rejects_managed_calculator_body(
    api_client,
    documents_token,
    calculator_state,
):
    """Fails if the document MCP can overwrite calculator content outside its version flow."""
    document = Document.objects.get(pk=calculator_state["document_id"])

    response = _call(
        api_client,
        "documents",
        documents_token,
        "update_document",
        {
            "document_id": document.pk,
            "content_markdown": "Unauthorized rewrite",
        },
    )

    document.refresh_from_db()
    result = response.data["result"]
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "calculator_document_managed"
    assert document.content_markdown.startswith("# Calculadora de requerimientos")
