"""Real seeded Consulting presentation and commercial MCP helpers."""
from copy import deepcopy

import pytest

from content.models import ConsultingProgram, McpConnector
from content.services import consulting_program_service as service


@pytest.fixture
def consulting_program(db):
    """Load the migration seed so missing deployment data fails the tests."""
    return ConsultingProgram.load()


@pytest.fixture
def consulting_mcp(superuser):
    """Activate the real Commercial connector with an actor-bound credential."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='commercial', defaults={'name': 'Comercial'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = connector.credential_for_token(token)
    credential.actor = superuser
    credential.save(update_fields=['actor', 'updated_at'])
    return token, credential


@pytest.fixture
def changed_consulting_program(consulting_program, admin_user):
    """Publish one real revision and return the immutable seed snapshot."""
    original = service.read_program()
    service.apply_update(hero_update(original), actor=admin_user)
    return original


def hero_update(snapshot):
    """Return a bilingual, minimal editorial change against a real snapshot."""
    sections = {'hero': {lang: deepcopy(snapshot['content'][lang]['hero']) for lang in ('es', 'en')}}
    sections['hero']['es']['title'] = 'Una operación más clara. Decisiones mejor informadas.'
    sections['hero']['en']['title'] = 'A clearer operation. Better informed decisions.'
    return {
        'sections': sections,
        'if_match': snapshot['etag'],
        'change_note': 'Aclara el resultado del análisis empresarial.',
    }


def rpc_call(api_client, token, name, arguments, *, msg_id=1):
    """Call a real Commercial MCP tool through its JSON-RPC endpoint."""
    response = api_client.post(
        f'/api/mcp/commercial/{token}/',
        {'jsonrpc': '2.0', 'id': msg_id, 'method': 'tools/call',
         'params': {'name': name, 'arguments': arguments}},
        format='json',
    )
    return response.data['result']
