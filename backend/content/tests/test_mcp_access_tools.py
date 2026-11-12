"""MCP access tools must retain the panel's authority and secrecy boundaries."""

import pytest
from accounts.access_models import AccessEvent
from accounts.models import UserProfile
from django.contrib.auth import get_user_model

from content.mcp.contracts import MCP_MODEL_CONTRACTS
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import call_tool_inprocess

pytestmark = pytest.mark.django_db
User = get_user_model()


def make_user(*, email, staff=False):
    user = User.objects.create_user(
        username=email,
        email=email,
        password="Initial-pass-123",
        is_staff=staff,
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN if staff else UserProfile.ROLE_CLIENT,
        is_onboarded=True,
    )
    return user


@pytest.fixture
def staff_projects_credential():
    actor = make_user(email="mcp-staff@example.com", staff=True)
    connector, _ = McpConnector.objects.get_or_create(
        slug="projects",
        defaults={"name": "Projects"},
    )
    return McpCredential.objects.create(
        connector=connector,
        label="Access boundary",
        actor=actor,
        token_hash="0" * 64,
    )


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("list_accesses", {"group": "team"}),
        ("get_access", {"user_id": 0}),
    ],
)
def test_mcp_staff_cannot_read_team_access(
    staff_projects_credential, tool_name, arguments
):
    """Fails if MCP lets a regular panel operator inspect accounts belonging to the team."""
    teammate = make_user(email="mcp-team@example.com", staff=True)
    arguments = (
        {**arguments, "user_id": teammate.pk}
        if tool_name == "get_access"
        else arguments
    )

    response = call_tool_inprocess(
        "projects", tool_name, arguments, credential=staff_projects_credential
    )

    assert response["error"]["code"] == "ACCESS_REJECTED"


def test_mcp_access_change_requires_confirmation(staff_projects_credential):
    """Fails if a sensitive MCP access mutation applies before confirmation."""
    client = make_user(email="mcp-client@example.com")

    preview = call_tool_inprocess(
        "projects",
        "change_access",
        {"user_id": client.pk, "enabled": False},
        credential=staff_projects_credential,
    )

    client.refresh_from_db()
    assert preview["confirmation_required"] is True
    assert isinstance(preview["confirmation_id"], str)
    assert client.is_active is True


def test_mcp_confirmed_access_change_records_credential_actor(
    staff_projects_credential,
):
    """Fails if confirming an MCP disable leaves the client active or omits its credential actor."""
    client = make_user(email="mcp-confirmed-client@example.com")
    preview = call_tool_inprocess(
        "projects",
        "change_access",
        {"user_id": client.pk, "enabled": False},
        credential=staff_projects_credential,
    )

    confirmed = call_tool_inprocess(
        "projects",
        "confirm_action",
        {"confirmation_id": preview["confirmation_id"]},
        credential=staff_projects_credential,
    )

    client.refresh_from_db()
    event = AccessEvent.objects.get(user=client, action="disabled")
    assert confirmed["confirmed"] is True
    assert confirmed["result"]["enabled"] is False
    assert client.is_active is False
    assert event.actor_id == staff_projects_credential.actor_id


def test_mcp_access_contract_excludes_login_challenge_fields():
    """Fails if an MCP contract starts exposing challenge identifiers or credential digests."""
    contract = next(
        item
        for item in MCP_MODEL_CONTRACTS["projects"]
        if item.model_label == "accounts.LoginChallenge"
    )

    assert set(contract.excluded) == {
        "id",
        "user",
        "surface",
        "browser_digest",
        "identity_digest",
        "code_digest",
        "access_version",
        "expires_at",
        "attempts",
        "closed",
        "device",
        "created_at",
    }
