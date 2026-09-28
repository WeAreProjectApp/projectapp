"""Public contracts consumed by MCP clients, including text-only clients."""
import json

import pytest

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
    return call


@pytest.mark.parametrize('nested', [False, True])
def test_unknown_folder_field_reaches_text_client(rpc, nested):
    folder = DocumentFolder.objects.create(name='Original')
    values = {'name': 'Changed', 'typo': 1}
    arguments = {'folder_id': folder.pk, **({'data': values} if nested else values)}

    result = rpc('tools/call', name='update_folder', arguments=arguments)

    payload = json.loads(result['content'][0]['text'])
    assert payload == result['structuredContent']
    assert payload['error']['code'] == 'unknown_field'
    assert payload['error']['details']['errors'] == [{'field': 'typo', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.'}]
    folder.refresh_from_db()
    assert folder.name == 'Original'


@pytest.mark.parametrize('self_parent', [False, True])
def test_folder_cycle_reaches_text_client(rpc, self_parent):
    parent = DocumentFolder.objects.create(name='Parent')
    child = DocumentFolder.objects.create(name='Child', parent=parent)
    destination = parent.pk if self_parent else child.pk

    result = rpc('tools/call', name='update_folder', arguments={'folder_id': parent.pk, 'parent_id': destination})

    error = json.loads(result['content'][0]['text'])['error']
    assert error['code'] == 'folder_cycle'
    assert error['details']['errors'][0]['field'] == 'parent'
    assert error['details']['errors'][0]['message'] in error['message']
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


@pytest.mark.parametrize('restricted', [False, True])
def test_discovery_input_schemas_match_capabilities(rpc, restricted):
    credential = rpc.connector.credentials.get(label='Default')
    credential.allowed_tools = ['list_folders', 'create_folder'] if restricted else []
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

    assert discovered == capabilities['version'] == '3.0.1'


def test_mcp_folder_provenance_is_read_only(rpc):
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
