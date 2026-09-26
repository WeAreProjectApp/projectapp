"""The Document-manager window onto the one contract: live, read-only, no copy."""

import io
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.urls import reverse
from pypdf import PdfReader

from content.models import (
    ContractTemplate,
    Document,
    DocumentFolder,
    DocumentType,
    McpConnector,
)

pytestmark = pytest.mark.django_db
link_migration = import_module('content.migrations.0261_link_contract_mirror_document')


@pytest.fixture
def markdown_type(db):
    doc_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    return doc_type


@pytest.fixture
def templates_folder(db):
    return DocumentFolder.objects.create(name='Templates')


@pytest.fixture
def mirror(markdown_type, templates_folder):
    """The migrated default contract linked to a document holding a pointer."""
    document = Document.objects.create(
        title='Contrato — borrador vigente', document_type=markdown_type,
        folder=templates_folder, content_markdown='Puntero, no contrato.',
    )
    template = ContractTemplate.get_default()
    template.mirror_document = document
    template.save(update_fields=['mirror_document'])
    return document


def _pdf_text(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return ' '.join(' '.join(page.extract_text() for page in reader.pages).split())


def test_detail_serves_the_complete_live_draft(admin_client, mirror):
    data = admin_client.get(reverse('retrieve-document', args=[mirror.pk])).json()

    assert data['is_contract_mirror'] is True
    markdown = data['content_markdown']
    assert markdown.startswith('# CONTRATO DE PRESTACIÓN DE SERVICIOS')
    assert '## CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN' in markdown
    assert '## EN CONSTANCIA DE LO ANTERIOR,' in markdown
    assert 'XXX-XXX-XXX' in markdown
    assert 'Puntero, no contrato.' not in markdown


def test_pdf_is_the_draft_the_client_downloads(admin_client, mirror):
    response = admin_client.get(reverse('download-document-pdf', args=[mirror.pk]))

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    text = _pdf_text(response.content)
    assert 'CONTRATO DE PRESTACIÓN' in text
    assert 'CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN' in text
    assert 'XXX-XXX-XXX' in text


@pytest.mark.parametrize('method,route,payload', [
    ('patch', 'update-document', {'content_markdown': '# Otra cosa'}),
    ('delete', 'delete-document', None),
    ('patch', 'archive-document', None),
    ('post', 'duplicate-document', None),
])
def test_panel_writes_are_refused(admin_client, mirror, method, route, payload):
    response = getattr(admin_client, method)(
        reverse(route, args=[mirror.pk]), payload, format='json',
    )

    assert response.status_code == 409
    assert response.json()['code'] == 'contract_mirror_read_only'
    mirror.refresh_from_db()
    assert mirror.content_markdown == 'Puntero, no contrato.'
    assert mirror.is_archived is False
    assert Document.objects.filter(title__endswith='(copia)').count() == 0


def test_folder_archive_is_refused_while_it_holds_the_window(admin_client, mirror, templates_folder):
    response = admin_client.patch(reverse('archive-document-folder', args=[templates_folder.pk]))

    assert response.status_code == 409
    mirror.refresh_from_db()
    templates_folder.refresh_from_db()
    assert mirror.is_archived is False
    assert templates_folder.is_archived is False


@pytest.fixture
def documents_token(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Gestor Documental'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def _mcp(client, token, name, arguments):
    response = client.post(
        f'/api/mcp/documents/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
         'params': {'name': name, 'arguments': arguments}},
        format='json',
    )
    return response.data['result']


def test_mcp_read_returns_the_live_contract_as_read_only(api_client, superuser, documents_token, mirror):
    result = _mcp(api_client, documents_token, 'read_document', {'document_id': mirror.pk})

    content = result['structuredContent']
    assert content['is_contract_mirror'] is True
    assert content['editable'] is False
    assert content['edit_blockers'] == ['contract_mirror']
    assert '## EN CONSTANCIA DE LO ANTERIOR,' in content['markdown']


@pytest.mark.parametrize('tool,arguments', [
    ('update_document', {'markdown': '# Otra cosa'}),
    ('append_document', {'markdown': 'Más texto'}),
])
def test_mcp_writes_are_refused(api_client, superuser, documents_token, mirror, tool, arguments):
    result = _mcp(api_client, documents_token, tool, {'document_id': mirror.pk, **arguments})

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'NOT_EDITABLE'
    assert result['structuredContent']['error']['details']['edit_blockers'] == ['contract_mirror']
    mirror.refresh_from_db()
    assert mirror.content_markdown == 'Puntero, no contrato.'


def test_link_command_dry_run_then_apply(markdown_type):
    document = Document.objects.create(
        title='Copia vieja', document_type=markdown_type, content_markdown='Texto v6',
    )

    call_command('link_contract_document', '--document-id', str(document.pk))
    assert ContractTemplate.get_default().mirror_document_id is None

    call_command('link_contract_document', '--document-id', str(document.pk), '--apply')
    document.refresh_from_db()
    assert ContractTemplate.get_default().mirror_document_id == document.pk
    assert document.title == 'Contrato de prestación de servicios — borrador vigente'
    assert 'Texto v6' not in document.content_markdown


@pytest.mark.parametrize('copies,linked', [(1, True), (2, False)])
def test_link_migration_needs_a_single_exact_match(markdown_type, templates_folder, copies, linked):
    for _ in range(copies):
        Document.objects.create(
            title=link_migration.LEGACY_TITLE, document_type=markdown_type,
            folder=templates_folder, content_markdown='Texto v6',
        )

    link_migration.link_mirror(apps, SimpleNamespace(connection=connection))

    template = ContractTemplate.get_default()
    assert (template.mirror_document_id is not None) is linked
    if linked:
        assert template.mirror_document.title == link_migration.MIRROR_TITLE
        assert 'Texto v6' not in template.mirror_document.content_markdown


def test_admin_cannot_rewrite_the_contract_text(client, superuser):
    template = ContractTemplate.get_default()
    before = template.content_markdown
    client.force_login(superuser)

    response = client.post(
        f'/admin/content/contracttemplate/{template.pk}/change/',
        {'name': template.name, 'is_default': 'on', 'content_markdown': '# Editado a mano'},
    )

    assert response.status_code == 302
    template.refresh_from_db()
    assert template.content_markdown == before
