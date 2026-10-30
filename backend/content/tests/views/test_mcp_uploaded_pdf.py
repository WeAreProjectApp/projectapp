"""Documents MCP manages uploaded PDFs through the Panel write boundary."""
import base64
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.files.storage import storages

from content.mcp.upload_tools import store_artifact
from content.models import (
    Document,
    DocumentType,
    EntityHistory,
    McpConnector,
    McpUpload,
)
from content.tests.views.test_uploaded_pdf_documents import pdf_bytes

pytestmark = pytest.mark.django_db


@pytest.fixture
def access(superuser):
    DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'})
    connector, _ = McpConnector.objects.get_or_create(slug='documents')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return token, connector.credential_for_token(token)


def rpc(client, access, name, arguments):
    return client.post(f'/api/mcp/documents/{access[0]}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, format='json').data['result']


def artifact(access, *, content=None, content_type='application/pdf', filename='source.pdf'):
    _, credential = access
    return store_artifact(connector=credential.connector, credential=credential, filename=filename,
                          content_type=content_type, content=content or pdf_bytes(), request=None)['asset_id']


def create(client, access, asset=None):
    result = rpc(client, access, 'create_document_from_pdf', {'title': 'MCP PDF', 'source_asset_id': asset or artifact(access)})
    assert result['isError'] is False, result
    return result['structuredContent']


def test_chunks_create_a_searchable_private_pdf(api_client, access):
    content = pdf_bytes()
    begun = rpc(api_client, access, 'begin_upload', {'filename': 'chunked.pdf', 'content_type': 'application/pdf', 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    asset_id = begun['structuredContent']['asset_id']
    sent = rpc(api_client, access, 'upload_asset_chunk', {'asset_id': asset_id, 'index': 0, 'base64': base64.b64encode(content).decode(), 'chunk_sha256': hashlib.sha256(content).hexdigest()})
    assert sent['isError'] is False, sent
    completed = rpc(api_client, access, 'complete_upload', {'asset_id': asset_id})
    assert completed['isError'] is False, completed
    created = create(api_client, access, asset_id)
    assert created['content_format'] == 'pdf'
    assert McpUpload.objects.get(pk=asset_id).status == McpUpload.STATUS_CONSUMED
    listed = rpc(api_client, access, 'list_documents', {'search': 'singular'})
    assert created['id'] in [row['id'] for row in listed['structuredContent']['results']]
    assert McpUpload.objects.get(pk=asset_id).file.name.startswith('mcp-document-uploads/')


def test_read_returns_file_metadata_without_storage_path(api_client, access):
    doc = create(api_client, access)
    result = rpc(api_client, access, 'read_document', {'document_id': doc['id']})
    assert result['structuredContent']['pdf']['version'] == 1
    assert result['structuredContent']['content_editable'] is False
    assert 'documents/uploaded' not in str(result)


def test_download_asset_matches_original(api_client, access):
    doc = create(api_client, access)
    result = rpc(api_client, access, 'render_document_pdf', {'document_id': doc['id']})
    assert result['isError'] is False, result
    output = McpUpload.objects.get(pk=result['structuredContent']['asset_id'])
    assert output.file.read() == Document.objects.get(pk=doc['id']).uploaded_pdf.read()
    assert output.file.name.startswith('mcp-document-uploads/')
    with pytest.raises(ValueError, match='authenticated access'):
        _ = output.file.url


def test_replacement_preserves_history_download(api_client, access):
    doc = create(api_client, access)
    revision = EntityHistory.objects.get(entity_type='document', object_id=doc['id']).entries.first()
    replacement = artifact(access, content=pdf_bytes('Actualizado'))
    changed = rpc(api_client, access, 'replace_document_pdf', {'document_id': doc['id'], 'source_asset_id': replacement, 'expected_version': 1})
    assert changed['isError'] is False, changed
    assert changed['structuredContent']['pdf']['version'] == 2
    historical = rpc(api_client, access, 'download_document_history_file', {'object_id': doc['id'], 'revision_id': revision.pk})
    assert historical['isError'] is False, historical
    historical_file = McpUpload.objects.get(pk=historical['structuredContent']['asset_id'])
    historical_bytes = historical_file.file.read()
    assert historical_bytes != Document.objects.get(pk=doc['id']).uploaded_pdf.read()
    assert hashlib.sha256(historical_bytes).hexdigest() == doc['pdf']['sha256']


def test_metadata_update_reuses_panel_serializer(api_client, access):
    doc = create(api_client, access)
    result = rpc(api_client, access, 'update_pdf_document', {'document_id': doc['id'], 'title': 'Renombrado', 'is_client_visible': True})
    assert result['isError'] is False, result
    row = Document.objects.get(pk=doc['id'])
    assert row.title == 'Renombrado'
    assert row.is_client_visible is True
    assert row.pdf_version == 1


@pytest.mark.parametrize(('tool', 'field'), [('append_document', 'markdown'), ('update_document', 'markdown'), ('update_pdf_document', 'content_markdown')])
def test_text_writes_cannot_change_pdf(api_client, access, tool, field):
    doc = create(api_client, access)
    result = rpc(api_client, access, tool, {'document_id': doc['id'], field: '# Reescrito'})
    assert result['isError'] is True
    assert Document.objects.get(pk=doc['id']).content_markdown == ''


def test_stale_replacement_leaves_asset_reusable(api_client, access):
    doc = create(api_client, access)
    asset = artifact(access)
    result = rpc(api_client, access, 'replace_document_pdf', {'document_id': doc['id'], 'source_asset_id': asset, 'expected_version': 2})
    assert result['isError'] is True
    assert McpUpload.objects.get(pk=asset).status == McpUpload.STATUS_COMPLETE
    assert Document.objects.get(pk=doc['id']).pdf_version == 1


def test_rejects_asset_from_another_credential(api_client, access):
    credential = access[1]
    asset = artifact(access)
    from content.models import McpCredential
    other = McpCredential.objects.create(connector=credential.connector, label='Other PDF', actor=credential.actor)
    other_token = other.generate_token()
    result = rpc(api_client, (other_token, other), 'create_document_from_pdf', {'title': 'Ajeno', 'source_asset_id': asset})
    assert result['isError'] is True
    assert Document.objects.filter(title='Ajeno').exists() is False


def test_rejects_incomplete_asset(api_client, access):
    asset = artifact(access)
    McpUpload.objects.filter(pk=asset).update(status=McpUpload.STATUS_PENDING)
    result = rpc(api_client, access, 'create_document_from_pdf', {'title': 'Incompleto', 'source_asset_id': asset})
    assert result['isError'] is True
    assert Document.objects.filter(title='Incompleto').exists() is False


def test_rejects_non_pdf_asset(api_client, access):
    asset = artifact(access, content=b'plain text', content_type='text/plain', filename='source.txt')
    result = rpc(api_client, access, 'create_document_from_pdf', {'title': 'Texto', 'source_asset_id': asset})
    assert result['isError'] is True
    assert Document.objects.filter(title='Texto').exists() is False


def test_consumption_failure_compensates_saved_pdf(api_client, access):
    asset = artifact(access)
    before = set(Path(storages['private'].location).rglob('*.pdf'))
    with patch.object(McpUpload, 'save', side_effect=RuntimeError('consume failed')):
        result = rpc(api_client, access, 'create_document_from_pdf', {'title': 'Rollback MCP', 'source_asset_id': asset})
    assert result['isError'] is True
    assert Document.objects.filter(title='Rollback MCP').exists() is False
    assert McpUpload.objects.get(pk=asset).status == McpUpload.STATUS_COMPLETE
    assert set(Path(storages['private'].location).rglob('*.pdf')) == before


def test_history_metadata_never_exposes_private_path(api_client, access):
    doc = create(api_client, access)
    history = EntityHistory.objects.get(entity_type='document', object_id=doc['id']).entries.first()
    result = rpc(api_client, access, 'get_document_history_version', {'object_id': doc['id'], 'revision_id': history.pk})
    assert result['isError'] is False, result
    assert 'uploaded_pdf' not in result['structuredContent']['snapshot']
    assert 'documents/uploaded' not in str(result)
