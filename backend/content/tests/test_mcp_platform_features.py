"""MCP discovery, confirmation and persistence for PA-263."""
import pytest

from accounts.models_feature_flags import PlatformFeatureEvent, PlatformFeatureSettings
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import call_tool_inprocess

pytestmark = pytest.mark.django_db


@pytest.fixture
def credential(admin_user):
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    return McpCredential.objects.create(connector=connector, actor=admin_user,
                                       label='PA-263 contract', token_hash='0' * 64)


def test_mcp_catalog_exposes_effective_defaults(credential):
    result = call_tool_inprocess('projects', 'get_platform_feature_flags', {}, credential=credential)

    flags = {item['key']: item for item in result['features']}
    assert flags['platform.documents']['effective'] is True
    assert flags['platform.ai_chatbot']['effective'] is False


def test_mcp_change_requires_confirmation(credential):
    preview = call_tool_inprocess('projects', 'update_platform_feature_flags',
        {'expected_version': 0, 'values': {'platform.documents': False}}, credential=credential)

    assert preview['confirmation_required'] is True
    assert not PlatformFeatureSettings.objects.exists()


def test_mcp_confirmation_persists_shared_configuration(credential):
    preview = call_tool_inprocess('projects', 'update_platform_feature_flags',
        {'expected_version': 0, 'values': {'platform.documents': False}}, credential=credential)

    result = call_tool_inprocess('projects', 'confirm_action',
        {'confirmation_id': preview['confirmation_id']}, credential=credential)

    assert result['confirmed'] is True
    assert PlatformFeatureSettings.objects.get().values == {'platform.documents': False}
    assert PlatformFeatureEvent.objects.get().actor_id == credential.actor_id


def test_mcp_rejects_nonadministrative_actor(credential, client_user):
    credential.actor = client_user
    credential.save(update_fields=['actor'])

    result = call_tool_inprocess('projects', 'get_platform_feature_flags', {}, credential=credential)

    assert result['error']['code'] == 'ACCESS_REJECTED'


def test_mcp_client_override_can_return_to_inheritance(credential, client_user):
    from accounts.services import platform_features
    platform_features.update(credential.actor, {'expected_version': 0, 'values': {'platform.documents': False}})
    preview = call_tool_inprocess('projects', 'update_platform_client_feature_flags', {
        'user_id': client_user.pk, 'expected_version': 0, 'values': {'platform.documents': True},
    }, credential=credential)
    call_tool_inprocess('projects', 'confirm_action', {'confirmation_id': preview['confirmation_id']}, credential=credential)
    preview = call_tool_inprocess('projects', 'update_platform_client_feature_flags', {
        'user_id': client_user.pk, 'expected_version': 1, 'values': {'platform.documents': None},
    }, credential=credential)

    call_tool_inprocess('projects', 'confirm_action', {'confirmation_id': preview['confirmation_id']}, credential=credential)
    result = call_tool_inprocess('projects', 'get_platform_client_feature_flags', {'user_id': client_user.pk}, credential=credential)

    flag = next(item for item in result['features'] if item['key'] == 'platform.documents')
    assert flag['effective'] is False
    assert flag['override'] is None
    assert flag['source'] == 'global'
