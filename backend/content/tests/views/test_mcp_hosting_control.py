import pytest
from rest_framework.test import APIClient

from content.mcp.connectors import TOOLS_BY_SLUG
from content.models import McpConnector
from hosting_control.models import Control, Event
from monitoring.models import Resource

pytestmark = pytest.mark.django_db


def test_mcp_mode_change_requires_confirmation():
    tools = {tool['name']: tool for tool in TOOLS_BY_SLUG['projects']}
    assert tools['set_hosting_control_mode']['requires_confirmation'] is True
    assert tools['update_hosting_control_message']['requires_confirmation'] is True


def test_confirmed_mcp_edit_is_visible_in_canonical_data():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Proyectos'})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()
    credential = connector.credentials.get(label='Default')
    credential.catalog = 'canonical'
    credential.allowed_tools = [tool['name'] for tool in TOOLS_BY_SLUG['projects']]
    credential.save(update_fields=['catalog', 'allowed_tools'])
    resource = Resource.objects.create(key='mcp-site', name='MCP sitio', kind='project')
    control = Control.objects.create(resource=resource)
    client = APIClient()
    def rpc(name, arguments):
        response = client.post(f'/api/mcp/projects/{token}/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}}, format='json')
        return response.json()['result']
    preview = rpc('update_hosting_control_message', {'control_id': control.pk, 'expected_version': 0, 'message_mode': 'banner', 'title': 'Pago de prueba MCP', 'text': 'Texto MCP de prueba.'})
    assert not Event.objects.exists()
    result = rpc('confirm_action', {'confirmation_id': preview['structuredContent']['confirmation_id']})
    assert not result.get('isError', False)
    control.refresh_from_db()
    assert control.banner_title == 'Pago de prueba MCP'
    assert control.mode == 'normal'
    assert Event.objects.get().source.startswith('mcp:projects:credential:')
