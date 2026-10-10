"""Public contracts consumed by MCP clients, including text-only clients."""
import json

import pytest

from content.mcp.connectors import CONNECTORS
from content.models import Document, DocumentFolder, DocumentType, McpConnector

pytestmark = pytest.mark.django_db


@pytest.fixture
def rpc(api_client, superuser):
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documents'})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()

    def call(method, **params):
        return api_client.post(f'/api/mcp/documents/{token}/', {
            'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params,
        }, format='json').json()['result']
    call.connector = connector
    call.url = f'/api/mcp/documents/{token}/'
    return call


def test_unknown_folder_field_reaches_text_client(rpc):
    folder = DocumentFolder.objects.create(name='Original')
    arguments = {'folder_id': folder.pk, 'name': 'Changed', 'typo': 1}

    result = rpc('tools/call', name='update_folder', arguments=arguments)

    payload = json.loads(result['content'][0]['text'])
    assert payload == result['structuredContent']
    assert payload['error']['code'] == 'unknown_field'
    assert payload['error']['details']['errors'] == [{'field': 'typo', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.'}]
    folder.refresh_from_db()
    assert folder.name == 'Original'


@pytest.mark.parametrize('destination_kind', ['self', 'descendant'])
def test_folder_cycle_reaches_text_client(rpc, destination_kind):
    parent = DocumentFolder.objects.create(name='Parent')
    child = DocumentFolder.objects.create(name='Child', parent=parent)
    destination = {'self': parent.pk, 'descendant': child.pk}[destination_kind]

    result = rpc('tools/call', name='update_folder', arguments={'folder_id': parent.pk, 'parent_id': destination})

    payload = json.loads(result['content'][0]['text'])
    assert payload == result['structuredContent']
    error = payload['error']
    assert error['code'] == 'OWNERSHIP_PLAN_BLOCKED'
    blocker, = error['details']['blockers']
    assert (blocker['code'], blocker['resource_type'], blocker['resource_id']) == ('folder_cycle', 'folder', parent.pk)
    parent.refresh_from_db()
    assert parent.parent_id is None


def test_native_create_folder_uses_shared_error_contract(rpc):
    result = rpc('tools/call', name='create_folder', arguments={'name': 'New', 'typo': True})

    payload = json.loads(result['content'][0]['text'])
    assert payload['error']['code'] == 'unknown_field'
    assert payload['error']['details']['errors'][0]['field'] == 'typo'
    assert not DocumentFolder.objects.filter(name='New').exists()


def test_rejected_move_exposes_every_id_at_root(rpc):
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    document = Document.objects.create(title='Valid', document_type=kind)
    target = DocumentFolder.objects.create(name='Target')

    result = rpc('tools/call', name='move_documents', arguments={'document_ids': [document.pk, 999999], 'folder_id': target.pk})

    payload = json.loads(result['content'][0]['text'])
    assert payload == result['structuredContent']
    assert [(row['id'], row['status'], row['code']) for row in payload['results']] == [(document.pk, 'aborted', 'batch_aborted'), (999999, 'failed', 'not_found')]
    assert payload['results'] == payload['error']['details']['results']
    document.refresh_from_db()
    assert document.folder_id is None


@pytest.mark.parametrize('allowed_tools', [[], ['list_folders', 'create_folder']])
def test_discovery_input_schemas_match_capabilities(rpc, allowed_tools):
    credential = rpc.connector.credentials.get(label='Default')
    credential.allowed_tools = allowed_tools
    credential.save()

    listed = rpc('tools/list')['tools']
    described = rpc('tools/call', name='describe_capabilities', arguments={})['structuredContent']['tools']

    assert {tool['name']: tool['inputSchema'] for tool in listed} == {tool['name']: tool['input_schema'] for tool in described}


def test_discovery_publishes_document_organization_fields(rpc):
    listed = rpc('tools/list')['tools']
    fields = {tool['name']: set(tool['inputSchema']['properties']) for tool in listed}

    assert fields['list_folders'] == {'parent_id', 'name'}
    assert fields['describe_capabilities'] == {'tools', 'summary'}
    assert {'name', 'parent_id', 'parent', 'order', 'client', 'project'} <= fields['update_folder']
    assert {'parent', 'order', 'client', 'project'} <= fields['create_folder']
    assert 'include_content' in fields['create_document'] & fields['update_document']


def test_discovery_uses_connector_version(rpc):
    discovered = rpc('initialize')['serverInfo']['version']
    capabilities = rpc('tools/call', name='describe_capabilities', arguments={'summary': True})['structuredContent']

    assert discovered == capabilities['version'] == CONNECTORS['documents'].version


def test_mcp_folder_creation_records_provenance(rpc):
    result = rpc('tools/call', name='create_folder', arguments={'name': 'Audited'})
    folder = DocumentFolder.objects.get(pk=result['structuredContent']['id'])

    assert folder.creation_source == 'mcp'
    assert folder.creation_operation == 'create_folder'
    assert folder.created_by_id == rpc.connector.credentials.get(label='Default').actor_id


def test_credential_denial_reaches_text_client(rpc):
    credential = rpc.connector.credentials.get(label='Default')
    credential.allowed_tools = ['list_folders']
    credential.save()

    result = rpc('tools/call', name='create_folder', arguments={'name': 'Denied'})

    error = json.loads(result['content'][0]['text'])['error']
    assert error['code'] == 'FORBIDDEN'
    assert error['message'] == 'La credencial no permite esta herramienta.'
    assert not DocumentFolder.objects.filter(name='Denied').exists()


def test_invalid_transport_token_returns_machine_code(api_client):
    response = api_client.post('/api/mcp/documents/invalid-token/', {}, format='json')

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'
    assert isinstance(response.json()['error']['message'], str)
    assert len(response.json()['error']['message']) > 0


def test_foreign_origin_returns_machine_code(api_client, rpc):
    response = api_client.post(rpc.url, {}, format='json', HTTP_ORIGIN='https://foreign.example')

    assert response.status_code == 403
    assert response.json()['error'] == {
        'code': 'FORBIDDEN', 'message': 'El origen de la solicitud no está permitido.',
    }


def test_malformed_transport_json_returns_machine_code(api_client, rpc):
    response = api_client.post(rpc.url, '{broken', content_type='application/json')

    assert response.status_code == 400
    assert response.json()['error']['code'] == 'PARSE_ERROR'
    assert 'JSON parse error' in response.json()['error']['message']


def test_unsupported_transport_method_returns_machine_code(api_client, rpc):
    response = api_client.get(rpc.url)

    assert response.status_code == 405
    assert response.json()['error']['code'] == 'METHOD_NOT_ALLOWED'
    assert 'GET' in response.json()['error']['message']
