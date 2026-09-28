"""Bounded response contracts shared by panel and Documents MCP writes."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from content.models import Document, DocumentType, McpConnector

pytestmark = pytest.mark.django_db


@pytest.fixture
def markdown_type():
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    return document_type


@pytest.fixture
def document(markdown_type):
    return Document.objects.create(
        title='Original', document_type=markdown_type,
        content_markdown='# Original markdown',
    )


@pytest.fixture
def rpc(api_client, superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documents'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()

    def call(name, arguments):
        response = api_client.post(
            f'/api/mcp/documents/{token}/',
            {
                'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': name, 'arguments': arguments},
            },
            format='json',
        )
        return response.data['result']

    return call


def _panel_create(client, document, include_content):
    payload = {'title': 'Panel create', 'content_markdown': '# Panel create'}
    if include_content:
        payload['include_content'] = True
    return client.post(reverse('create-document'), payload, format='json')


def _panel_markdown_create(client, document, include_content):
    payload = {'title': 'Markdown create', 'markdown': '# Markdown create'}
    if include_content:
        payload['include_content'] = True
    return client.post(reverse('create-document-from-markdown'), payload, format='json')


def _panel_upload(client, document, include_content):
    payload = {'file': SimpleUploadedFile('upload.md', b'# Uploaded markdown')}
    if include_content:
        payload['include_content'] = 'true'
    return client.post(reverse('upload-document-markdown'), payload, format='multipart')


def _panel_duplicate(client, document, include_content):
    payload = {'include_content': True} if include_content else {}
    return client.post(reverse('duplicate-document', args=[document.pk]), payload, format='json')


def _panel_archive(client, document, include_content):
    payload = {'include_content': True} if include_content else {}
    return client.patch(reverse('archive-document', args=[document.pk]), payload, format='json')


def _panel_unarchive(client, document, include_content):
    document.is_archived = True
    document.save(update_fields=['is_archived'])
    payload = {'include_content': True} if include_content else {}
    return client.patch(reverse('unarchive-document', args=[document.pk]), payload, format='json')


@pytest.mark.parametrize(
    ('operation', 'include_content'),
    (
        (_panel_create, False), (_panel_create, True),
        (_panel_markdown_create, False), (_panel_markdown_create, True),
        (_panel_upload, False), (_panel_upload, True),
        (_panel_duplicate, False), (_panel_duplicate, True),
        (_panel_archive, False), (_panel_archive, True),
        (_panel_unarchive, False), (_panel_unarchive, True),
    ),
)
def test_panel_write_response_bounds_markdown(
    admin_client, document, operation, include_content,
):
    """Falla si una escritura del panel filtra markdown sin pedirlo o lo omite al pedirlo."""
    response = operation(admin_client, document, include_content)

    assert response.status_code in (200, 201)
    assert 'content_markdown' not in response.data
    assert 'content_json' not in response.data
    assert ('markdown' in response.data) is include_content


def _mcp_create(rpc, document, include_content):
    return rpc('create_document', {
        'title': 'MCP create', 'markdown': '# MCP create',
        'include_content': include_content,
    })


def _mcp_append(rpc, document, include_content):
    return rpc('append_document', {
        'document_id': document.pk, 'markdown': 'Appended',
        'include_content': include_content,
    })


def _mcp_duplicate(rpc, document, include_content):
    return rpc('duplicate_document', {
        'document_id': document.pk, 'include_content': include_content,
    })


def _mcp_archive(rpc, document, include_content):
    return rpc('archive_document', {
        'document_id': document.pk, 'include_content': include_content,
    })


def _mcp_unarchive(rpc, document, include_content):
    document.is_archived = True
    document.save(update_fields=['is_archived'])
    return rpc('unarchive_document', {
        'document_id': document.pk, 'include_content': include_content,
    })


@pytest.mark.parametrize(
    ('operation', 'include_content'),
    (
        (_mcp_create, False), (_mcp_create, True),
        (_mcp_append, False), (_mcp_append, True),
        (_mcp_duplicate, False), (_mcp_duplicate, True),
        (_mcp_archive, False), (_mcp_archive, True),
        (_mcp_unarchive, False), (_mcp_unarchive, True),
    ),
)
def test_mcp_write_response_bounds_markdown(rpc, document, operation, include_content):
    """Falla si structuredContent no conserva el mismo control compacto que el panel."""
    result = operation(rpc, document, include_content)
    payload = result['structuredContent']

    assert result['isError'] is False
    assert 'content_markdown' not in payload
    assert 'content_json' not in payload
    assert ('markdown' in payload) is include_content


def _invalid_panel_create(client):
    return client.post(
        reverse('create-document'),
        {'title': 'Rejected', 'content_markdown': '# Rejected', 'include_content': 'yes'},
        format='json',
    )


def _invalid_panel_upload(client):
    return client.post(
        reverse('upload-document-markdown'),
        {
            'file': SimpleUploadedFile('rejected.md', b'# Rejected'),
            'include_content': 'yes',
        },
        format='multipart',
    )


@pytest.mark.parametrize('operation', (_invalid_panel_create, _invalid_panel_upload))
def test_panel_rejects_non_boolean_content_control_before_creation(
    admin_client, operation,
):
    """Falla si include_content inválido permite crear un documento antes de responder 400."""
    before = Document.objects.count()
    response = operation(admin_client)

    assert response.status_code == 400
    assert response.data['include_content'] == 'Debe ser true o false.'
    assert Document.objects.count() == before
