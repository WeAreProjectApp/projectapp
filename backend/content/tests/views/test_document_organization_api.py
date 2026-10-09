"""Real REST/MCP boundaries for document organization."""
import json

import pytest
from django.urls import reverse

from content.models import (
    ContractTemplate,
    Document,
    DocumentFolder,
    DocumentType,
    McpConnector,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def doc():
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    return Document.objects.create(title='Large', document_type=kind, content_markdown='# Large\n' + 'x' * 72000)


@pytest.fixture
def mirror(doc):
    template = ContractTemplate.get_default() or ContractTemplate.objects.create(name='Contract', is_default=True)
    template.mirror_document = doc
    template.save(update_fields=['mirror_document'])
    return Document.objects.get(pk=doc.pk)


@pytest.fixture
def rpc(api_client, superuser):
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documents'})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()

    def call(name, arguments):
        response = api_client.post(f'/api/mcp/documents/{token}/', {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }, format='json')
        return response.json()['result']
    return call


def test_mcp_update_folder_accepts_parent_id(rpc):
    folder = DocumentFolder.objects.create(name='Original')
    parent = DocumentFolder.objects.create(name='Parent')
    result = rpc('update_folder', {'folder_id': folder.pk, 'data': {'name': 'Changed', 'parent_id': parent.pk}})
    assert result['isError'] is False
    folder.refresh_from_db()
    assert folder.parent_id == parent.pk
    assert folder.name == 'Changed'


def test_mcp_update_folder_rejects_unknown_without_partial_save(rpc):
    folder = DocumentFolder.objects.create(name='Original')
    result = rpc('update_folder', {'folder_id': folder.pk, 'data': {'name': 'Changed', 'typo': 1}})
    assert result['isError'] is True
    folder.refresh_from_db()
    assert folder.name == 'Original'


def test_panel_folder_creation_stamps_actor(admin_client, admin_user):
    response = admin_client.post(reverse('create-document-folder'), {'name': 'Audited'}, format='json')
    assert response.status_code == 201
    assert response.data['creation_source'] == 'panel'
    assert response.data['created_by']['id'] == admin_user.pk


def test_mcp_folder_creation_stamps_source(rpc):
    result = rpc('create_folder', {'name': 'Audited'})
    assert result['isError'] is False
    assert result['structuredContent']['created_by'] == 'mcp'
    assert DocumentFolder.objects.get(pk=result['structuredContent']['id']).created_by_id is not None


def test_mcp_folder_filter_reports_archive_counts(rpc, doc):
    parent = DocumentFolder.objects.create(name='Parent')
    folder = DocumentFolder.objects.create(name='Littigio', parent=parent)
    DocumentFolder.objects.create(name='Littigio')
    DocumentFolder.objects.create(name='Archived child', parent=folder, is_archived=True)
    doc.folder = folder
    doc.is_archived = True
    doc.save()
    result = rpc('list_folders', {'parent_id': parent.pk, 'name': 'littigio'})
    row, = result['structuredContent']['folders']
    assert row['id'] == folder.pk
    assert row['archived_document_count'] == 1
    assert row['archived_children_count'] == 1
    assert row['created_at']
    assert row['updated_at']


def test_mcp_default_write_has_bounded_payload(rpc, doc):
    result = rpc('update_document', {'document_id': doc.pk, 'title': 'Renamed'})
    assert result['isError'] is False
    assert len(json.dumps(result)) < 3000
    assert 'markdown' not in result['structuredContent']
    assert 'content_markdown' not in result['structuredContent']
    assert result['structuredContent']['title'] == 'Renamed'


def test_mcp_content_opt_in_has_only_canonical_field(rpc, doc):
    result = rpc('update_document', {'document_id': doc.pk, 'title': 'Renamed', 'include_content': True})
    assert result['structuredContent']['markdown'] == doc.content_markdown
    assert 'content_markdown' not in result['structuredContent']


def test_rest_default_write_omits_content(admin_client, doc):
    response = admin_client.patch(reverse('update-document', args=[doc.pk]), {'title': 'Renamed'}, format='json')
    assert response.status_code == 200
    assert response.data['title'] == 'Renamed'
    assert set(response.data) >= {'etag', 'folder_id', 'folder_name', 'editable', 'updated_at'}
    assert 'content_markdown' not in response.data
    assert 'content_json' not in response.data


def test_rest_opt_in_returns_markdown(admin_client, doc):
    response = admin_client.patch(reverse('update-document', args=[doc.pk]), {'title': 'Renamed', 'include_content': True}, format='json')
    assert response.status_code == 200
    assert response.data['markdown'] == doc.content_markdown
    assert 'content_markdown' not in response.data


def test_invalid_content_control_does_not_write(admin_client, doc):
    response = admin_client.patch(reverse('update-document', args=[doc.pk]), {'title': 'Renamed', 'include_content': 'yes'}, format='json')
    assert response.status_code == 400
    doc.refresh_from_db()
    assert doc.title == 'Large'


def test_mirror_folder_move_is_rejected(admin_client, mirror):
    folder = DocumentFolder.objects.create(name='Destination')
    response = admin_client.patch(reverse('update-document', args=[mirror.pk]), {'folder_id': folder.pk}, format='json')
    assert response.status_code == 409
    mirror.refresh_from_db()
    assert mirror.folder_id is None
    assert mirror.content_markdown.endswith('x' * 72000)
    assert response.data['code'] == 'contract_mirror_read_only'


def test_mcp_mirror_folder_move_is_rejected(rpc, mirror):
    folder = DocumentFolder.objects.create(name='Destination')
    result = rpc('update_document', {'document_id': mirror.pk, 'folder_id': folder.pk})
    assert result['isError'] is True
    mirror.refresh_from_db()
    assert mirror.folder_id is None


def test_mcp_move_rejects_generated_markdown(rpc, doc):
    doc.generated_file = 'snapshots/retained.pdf'
    doc.save(update_fields=['generated_file'])
    folder = DocumentFolder.objects.create(name='Destination')

    result = rpc('update_document', {'document_id': doc.pk, 'folder_id': folder.pk})

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'NOT_EDITABLE'
    doc.refresh_from_db()
    assert doc.folder_id is None


def test_mirror_mixed_update_is_atomic(admin_client, mirror):
    folder = DocumentFolder.objects.create(name='Destination')
    response = admin_client.patch(reverse('update-document', args=[mirror.pk]), {'folder_id': folder.pk, 'title': 'Bad'}, format='json')
    assert response.status_code == 409
    mirror.refresh_from_db()
    assert mirror.folder_id is None
    assert mirror.title == 'Large'


def test_capabilities_can_filter_and_summarize(rpc):
    result = rpc('describe_capabilities', {'tools': ['update_folder', 'move_documents'], 'summary': True})
    data = result['structuredContent']
    assert data['version'] == '3.1.0'
    assert {tool['name'] for tool in data['tools']} == {'update_folder', 'move_documents'}
    assert set(data['tools'][0]) == {'name', 'title', 'risk', 'requires_confirmation'}


def test_capabilities_document_folder_schema(rpc):
    result = rpc('describe_capabilities', {'tools': ['update_folder']})
    tool, = result['structuredContent']['tools']
    schema = tool['input_schema']
    assert schema['additionalProperties'] is False
    assert set(schema['properties']) == {'folder_id', 'name', 'parent_id', 'parent', 'order', 'client', 'project', 'if_match'}


def test_capabilities_describe_atomic_move_contract(rpc):
    result = rpc('describe_capabilities', {'tools': ['move_documents']})
    tool, = result['structuredContent']['tools']
    assert tool['input_schema']['required'] == ['document_ids', 'folder_id']
    assert tool['input_schema']['properties']['include_content']['default'] is False
    result_schema = tool['output_schema']['properties']['results']['items']
    assert result_schema['properties']['status']['enum'] == ['moved', 'unchanged', 'failed', 'aborted']


def test_folder_writes_require_staff(api_client):
    response = api_client.post(reverse('create-document-folder'), {'name': 'Forbidden'}, format='json')
    assert response.status_code in (401, 403)
    assert not DocumentFolder.objects.filter(name='Forbidden').exists()
