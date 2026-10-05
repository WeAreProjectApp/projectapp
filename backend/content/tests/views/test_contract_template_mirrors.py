"""New mirror bindings share the locked UI and native MCP discovery."""
import pytest
from django.urls import reverse

from content.models import DocumentFolder, McpConnector
from content.services.contract_template_service import read_template
from content.tests.contract_template_fixtures import rpc_call

pytestmark = pytest.mark.django_db


def _documents_call(api_client, name, arguments):
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documentos'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    response = api_client.post(f'/api/mcp/documents/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, format='json')
    return response.data['result']['structuredContent']


@pytest.mark.parametrize('variant', ['combined', 'product', 'service'])
def test_new_mirror_binding_rejects_content_edits(admin_client, initialized_contract_mirrors, variant):
    mirror = initialized_contract_mirrors.mirrors.get(variant=variant)
    original_pointer = mirror.document.content_markdown

    response = admin_client.patch(reverse('update-document', args=[mirror.document_id]),
        {'content_markdown': '# No permitido'}, format='json')

    assert response.status_code == 409
    assert response.json()['code'] == 'contract_mirror_read_only'
    mirror.document.refresh_from_db()
    assert mirror.document.content_markdown == original_pointer


def test_documents_mcp_lists_the_three_current_mirrors(api_client, initialized_contract_mirrors):
    result = _documents_call(api_client, 'list_contract_mirrors', {})

    assert {row['variant'] for row in result['mirrors']} == {'combined', 'product', 'service'}
    assert [row['version'] for row in result['mirrors']] == [1, 1, 1]
    assert [row['synchronized'] for row in result['mirrors']] == [True, True, True]
    assert [bool(row['last_synced_at']) for row in result['mirrors']] == [True, True, True]
    assert {row['folder_id'] for row in result['mirrors']} == {initialized_contract_mirrors.mirrors.get(variant='combined').document.folder_id}
    assert [row['document_id'] for row in result['mirrors']] == [initialized_contract_mirrors.mirrors.get(variant=key).document_id for key in ('combined', 'product', 'service')]
    assert [row['title'] for row in result['mirrors']] == [
        'Contrato unificado de producto y servicio',
        'Contrato de producto — desarrollo e implementación de software',
        'Contrato de servicio — hosting, mantenimiento y soporte',
    ]


def test_documents_capabilities_describe_mirror_discovery(api_client, coherent_template):
    result = _documents_call(api_client, 'describe_capabilities', {'tools': ['list_contract_mirrors']})

    assert result['tools'][0]['name'] == 'list_contract_mirrors'
    assert 'last_synced_at' in result['tools'][0]['output_schema']['properties']['mirrors']['items']['properties']


def test_contract_folder_cannot_be_reparented(admin_client, initialized_contract_mirrors):
    folder = initialized_contract_mirrors.mirrors.get(variant='product').document.folder
    another = DocumentFolder.objects.create(name='Destino')

    response = admin_client.patch(reverse('update-document-folder', args=[folder.pk]),
        {'parent_id': another.pk}, format='json')

    assert response.status_code == 400
    folder.refresh_from_db()
    assert folder.parent_id is None


def test_confirmation_detects_a_changed_mirror_binding(api_client, initialized_contract_mirrors, proposals_mcp):
    token, _ = proposals_mcp
    before = read_template('combined')
    preview = rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': before['markdown'] + '\n',
        'if_match': before['etag'], 'change_note': 'La confirmación debe detectar cambios de espejo.',
    })['structuredContent']
    mirror = initialized_contract_mirrors.mirrors.get(variant='product')
    mirror.document.title = 'Nombre cambiado desde consola'
    mirror.document.save(update_fields=['title', 'updated_at'])

    result = rpc_call(api_client, token, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert read_template('combined')['version'] == 1
