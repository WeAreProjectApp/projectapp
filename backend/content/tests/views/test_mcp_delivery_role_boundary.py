"""The delivery facade accepts only its bound usable MCP authority."""
from types import SimpleNamespace

import pytest
from accounts.models import UserProfile
from accounts.tests.delivery_authoring_helpers import build_authoring_context
from accounts.tests.delivery_helpers import version
from django.utils import timezone

from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.models import McpConnector, McpCredential
from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects,  # noqa: PLC0414 - pytest discovers this shared fixture.
)
from content.views.mcp_blog import TOOLS_BY_SLUG

pytestmark = pytest.mark.django_db


@pytest.fixture
def authority(call_projects):
    """Bootstrap the real non-interactive principal through the MCP HTTP route."""
    context = build_authoring_context()
    call_projects('get_delivery_overview', {'project_id': context.project.pk})
    credential = McpCredential.objects.select_related('connector', 'actor').get(connector__slug='projects', label='Default')
    return SimpleNamespace(delivery=context, credential=credential, actor=credential.actor)


def _execution(authority, **overrides):
    return McpExecutionContext(**{
        'connector': authority.credential.connector, 'credential': authority.credential,
        'actor': authority.actor, 'request_id': 'delivery-role-binding', **overrides,
    })


def _update_tool():
    return next(tool for tool in TOOLS_BY_SLUG['projects'] if tool['name'] == 'update_delivery_requirement')


def _arguments(authority):
    context = authority.delivery
    return {'project_id': context.project.pk, 'node_id': context.first.pk,
        'expected_version': version(context), 'title': 'Bound technical principal edit'}


def test_bound_mcp_principal_can_edit_without_creating_a_profile(authority):
    """Fails if the trusted technical channel requires a fabricated Platform role."""
    actor = authority.actor
    assert actor.has_usable_password() is False
    assert UserProfile.objects.filter(user=actor).exists() is False
    context = _execution(authority)

    with use_mcp_context(context, atomic_history=False):
        result = _update_tool()['handler'](_arguments(authority))

    authority.delivery.first.refresh_from_db()
    assert result['result']['id'] == authority.delivery.first.pk
    assert authority.delivery.first.title == 'Bound technical principal edit'
    assert UserProfile.objects.filter(user=actor).exists() is False
    authority.credential.refresh_from_db()
    assert authority.credential.actor_id == actor.pk


def _different_actor(authority):
    return _execution(authority, actor=authority.delivery.admin)


def _different_connector(authority):
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Other connector'})
    return _execution(authority, connector=connector)


def _revoked_credential(authority):
    authority.credential.revoked_at = timezone.now()
    authority.credential.save(update_fields=['revoked_at'])
    return _execution(authority)


@pytest.mark.parametrize('execution', [_different_actor, _different_connector, _revoked_credential])
def test_mcp_delivery_facade_rejects_an_invalid_authority_binding(authority, execution):
    """Fails if an invalid server context can write using an administrative actor."""
    original_title = authority.delivery.first.title
    expected = version(authority.delivery)
    context = execution(authority)

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as rejected:
        _update_tool()['handler'](_arguments(authority))

    authority.delivery.first.refresh_from_db()
    assert rejected.value.code == 'FORBIDDEN'
    assert authority.delivery.first.title == original_title
    assert version(authority.delivery) == expected
