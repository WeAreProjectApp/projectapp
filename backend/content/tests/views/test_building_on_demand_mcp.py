"""Dedicated discovery and private read operations through real MCP credentials."""
import pytest

from content.tests.building_on_demand_fixtures import rpc_call

pytestmark = pytest.mark.django_db

READ_NAMES = {
    'get_building_on_demand_program', 'get_building_on_demand_economics',
    'list_building_on_demand_program_versions', 'preview_building_on_demand_program_update',
    'render_building_on_demand_program_pdf', 'get_building_on_demand_contract',
    'preview_building_on_demand_contract_update', 'list_building_on_demand_contract_versions',
    'render_building_on_demand_contract_pdf',
    'get_building_on_demand_video',
}
WRITE_NAMES = {
    'update_building_on_demand_program', 'restore_building_on_demand_program_version',
    'create_building_on_demand_tier', 'update_building_on_demand_tier', 'remove_building_on_demand_tier',
    'create_building_on_demand_term', 'update_building_on_demand_term', 'remove_building_on_demand_term',
    'create_building_on_demand_estimator_task', 'update_building_on_demand_estimator_task',
    'remove_building_on_demand_estimator_task',
    'create_building_on_demand_faq', 'update_building_on_demand_faq', 'remove_building_on_demand_faq',
    'create_building_on_demand_card', 'update_building_on_demand_card', 'remove_building_on_demand_card',
    'reorder_building_on_demand_items', 'update_building_on_demand_estimator_sizes',
    'update_building_on_demand_economics', 'update_building_on_demand_contract',
    'restore_building_on_demand_contract_version', 'sync_building_on_demand_contract_mirror',
    'set_building_on_demand_video', 'remove_building_on_demand_video',
    'restore_default_building_on_demand_video',
    'set_building_on_demand_video_visibility',
}
UPLOAD_NAMES = {
    'begin_upload', 'upload_asset_chunk', 'complete_upload', 'abort_upload',
}
DIRECT_WRITE_NAMES = {
    'set_building_on_demand_video', 'restore_default_building_on_demand_video',
    'set_building_on_demand_video_visibility',
}
CONTROL_NAMES = {'describe_capabilities', 'confirm_action', 'cancel_action'}


def test_connector_discovery_has_exact_tool_names(api_client, building_on_demand_mcp):
    """Fails if dedicated discovery gains unrelated actions or loses administration."""
    token, _ = building_on_demand_mcp

    response = api_client.post(f'/api/mcp/building-on-demand/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list',
    }, format='json')
    names = {tool['name'] for tool in response.data['result']['tools']}
    catalog = rpc_call(api_client, token, 'describe_capabilities', {})['structuredContent']

    assert names == READ_NAMES | WRITE_NAMES | UPLOAD_NAMES | CONTROL_NAMES
    assert len(response.data['result']['tools']) == 44
    assert catalog['connector'] == 'building-on-demand'
    schemas = {tool['name']: tool['input_schema'] for tool in catalog['tools']}
    assert schemas['set_building_on_demand_video']['required'] == ['revision', 'asset_id']
    assert schemas['remove_building_on_demand_video']['required'] == ['revision']
    assert schemas['restore_default_building_on_demand_video']['required'] == ['revision']
    assert schemas['set_building_on_demand_video_visibility']['required'] == ['visible']


def test_connector_discovery_pins_the_schema_version(api_client, building_on_demand_mcp):
    """Fails if capability discovery does not announce the schema revision that owns editorial metadata."""
    token, _ = building_on_demand_mcp

    catalog = rpc_call(api_client, token, 'describe_capabilities', {})['structuredContent']

    assert catalog['version'] == '4.1.1'


def test_catalog_writes_advertise_durable_confirmation(api_client, building_on_demand_mcp):
    """Fails if an advertised domain mutation can skip the confirmation circuit."""
    token, _ = building_on_demand_mcp

    catalog = rpc_call(api_client, token, 'describe_capabilities', {})['structuredContent']
    writes = {tool['name'] for tool in catalog['tools']
              if tool['risk'] == 'sensitive' and tool['requires_confirmation']}
    direct_writes = {tool['name'] for tool in catalog['tools']
                     if tool['risk'] == 'write' and not tool['requires_confirmation']
                     and tool['name'] in DIRECT_WRITE_NAMES}
    write_hints = {tool['name'] for tool in catalog['tools']
                   if not tool['annotations']['readOnlyHint'] and tool['name'] in WRITE_NAMES}
    reads = {tool['name'] for tool in catalog['tools']
             if tool['risk'] == 'read' and tool['annotations']['readOnlyHint']}

    assert writes == WRITE_NAMES - DIRECT_WRITE_NAMES
    assert direct_writes == DIRECT_WRITE_NAMES
    assert write_hints == WRITE_NAMES
    assert reads == READ_NAMES | {'describe_capabilities'}


def test_program_read_exposes_private_configuration(api_client, building_on_demand_mcp):
    """Fails if administrators cannot read the numeric inputs needed for edits."""
    token, _ = building_on_demand_mcp

    snapshot = rpc_call(api_client, token, 'get_building_on_demand_program', {})['structuredContent']

    assert snapshot['version'] == 1
    assert snapshot['author'] == 'Sistema'
    assert snapshot['content']['internal']['hour_cost'] == 55000
    assert snapshot['content']['offer']['tiers'][1]['recommended'] is True
    assert snapshot['derived']['tiers'][0]['bag_hours'] == 96
    assert snapshot['etag']


def test_economics_read_returns_backend_calculations(api_client, building_on_demand_mcp):
    """Fails if MCP economics drifts from the seeded hours and hosting costs."""
    token, _ = building_on_demand_mcp

    economics = rpc_call(api_client, token, 'get_building_on_demand_economics', {})['structuredContent']

    assert economics['currency'] == 'COP'
    assert economics['hour_cost'] == 55000
    assert economics['tiers'][0]['hosting_cost_monthly'] == 46291
    assert economics['rows'][0]['breakeven_hours'] == 31.9
    assert economics['rows'][0]['bag_share_percent'] == 33
