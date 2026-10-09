"""Shared seeded presentation, bilingual edits and credential-bound RPC calls."""
from copy import deepcopy

import pytest

from content.models import BuildingWithUsProgram, McpConnector
from content.services import building_with_us_program_service as service


@pytest.fixture
def building_with_us_program(db):
    """Use the real migration seed so tests fail if deployment leaves it absent."""
    return BuildingWithUsProgram.load()


@pytest.fixture
def building_with_us_mcp(superuser):
    connector = McpConnector.objects.get(slug='building-with-us')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = connector.credential_for_token(token)
    credential.actor = superuser
    credential.save(update_fields=['actor', 'updated_at'])
    return token, credential


@pytest.fixture
def changed_building_with_us_program(building_with_us_program, admin_user):
    original = service.read_program()
    service.apply_update(hero_update(original), actor=admin_user)
    return original


def hero_update(snapshot):
    sections = {'hero': {lang: deepcopy(snapshot['content'][lang]['hero']) for lang in ('es', 'en')}}
    sections['hero']['es']['title'] = 'Tu experiencia, un producto con propósito.'
    sections['hero']['en']['title'] = 'Your expertise, a product with purpose.'
    return {'sections': sections, 'if_match': snapshot['etag'], 'change_note': 'Aclara el propósito del producto.'}


def rpc_call(api_client, token, name, arguments, *, msg_id=1):
    response = api_client.post(
        f'/api/mcp/building-with-us/{token}/',
        {'jsonrpc': '2.0', 'id': msg_id, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}},
        format='json',
    )
    return response.data['result']


def confirm(api_client, token, preview):
    return rpc_call(api_client, token, 'confirm_action', {'confirmation_id': preview['confirmation_id']}, msg_id=2)
