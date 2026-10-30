"""Uploaded PDFs keep their original bytes, identity and authorized history."""
import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from reportlab.pdfgen import canvas

from content.models import Document, DocumentFolder, EntityHistory
from content.services.uploaded_pdf_service import MAX_PDF_BYTES

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def pdf_type():
    from content.models import DocumentType
    return DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'})[0]



def pdf_bytes(text='Contenido buscable singular'):
    stream = io.BytesIO()
    page = canvas.Canvas(stream)
    page.drawString(50, 750, text)
    page.save()
    return stream.getvalue()


def upload(data=None, name='original.pdf'):
    return SimpleUploadedFile(name, data if data is not None else pdf_bytes(), content_type='application/pdf')


@pytest.fixture
def pdf_document(admin_client):
    response = admin_client.post('/api/documents/create-from-pdf/', {
        'title': 'Informe PDF', 'file': upload(),
    }, format='multipart')
    assert response.status_code == 201, response.data
    return Document.objects.get(pk=response.data['id'])


def test_creation_preserves_folder_association(admin_client):
    from accounts.models import Project, UserProfile
    user = get_user_model().objects.create_user(username='pdf-owner')
    UserProfile.objects.create(user=user, role='client')
    project = Project.objects.create(name='Proyecto PDF', client=user)
    folder = DocumentFolder.objects.create(name='Anexos PDF', client_user=user, project=project)
    original = pdf_bytes()

    response = admin_client.post('/api/documents/create-from-pdf/', {
        'title': 'Anexo', 'file': upload(original), 'folder_id': folder.pk,
        'client_custom_notes': '[{"title":"Privado","content":"Seguimiento"}]',
    }, format='multipart')

    assert response.status_code == 201, response.data
    document = Document.objects.get(pk=response.data['id'])
    assert (document.folder_id, document.client_user_id, document.project_id) == (folder.pk, user.pk, project.pk)
    assert document.uploaded_pdf.read() == original
    assert document.content_markdown == ''
    assert document.is_client_visible is False
    assert response.data['pdf']['version'] == 1
    assert 'uploaded_pdf' not in response.data
    assert 'singular' in document.pdf_search_text


@pytest.mark.parametrize(('content', 'name'), [(b'not pdf', 'fake.pdf'), (b'%PDF-1.7 broken', 'broken.pdf'), (b'', 'empty.pdf'), (b'text', 'word.docx')])
def test_invalid_upload_leaves_no_document(admin_client, content, name):
    before = Document.objects.count()
    response = admin_client.post('/api/documents/create-from-pdf/', {'title': 'Inválido', 'file': upload(content, name)}, format='multipart')
    assert response.status_code == 400
    assert Document.objects.count() == before


def test_rejects_oversized_pdf(admin_client):
    response = admin_client.post('/api/documents/create-from-pdf/', {
        'title': 'Grande', 'file': upload(b'%PDF-' + b' ' * MAX_PDF_BYTES),
    }, format='multipart')
    assert response.status_code == 413
    assert '25 MiB' in str(response.data)


def test_accepts_limit_exactly(admin_client):
    from pypdf import PdfWriter
    def padded_pdf(size):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_attachment('padding.bin', b'x' * size)
        stream = io.BytesIO()
        writer.write(stream)
        return stream.getvalue()
    padding = MAX_PDF_BYTES - len(padded_pdf(0))
    original = padded_pdf(padding)
    original = padded_pdf(padding + MAX_PDF_BYTES - len(original))
    assert len(original) == MAX_PDF_BYTES
    response = admin_client.post('/api/documents/create-from-pdf/', {
        'title': 'Límite', 'file': upload(original),
    }, format='multipart')
    assert response.status_code == 201, response.data
    assert response.data['pdf']['size'] == MAX_PDF_BYTES


def test_rejects_encrypted_pdf(admin_client):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt('password')
    stream = io.BytesIO()
    writer.write(stream)
    response = admin_client.post('/api/documents/create-from-pdf/', {
        'title': 'Protegido', 'file': upload(stream.getvalue()),
    }, format='multipart')
    assert response.status_code == 400
    assert 'cifrados' in str(response.data)


def test_preview_returns_original_bytes(admin_client, pdf_document):
    original = pdf_document.uploaded_pdf.read()
    response = admin_client.get(f'/api/documents/{pdf_document.pk}/pdf/?inline=1')
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == original
    assert response['Content-Disposition'].startswith('inline')
    assert response['Cache-Control'] == 'private, no-store'


def test_replacement_keeps_previous_file(admin_client, pdf_document):
    original = pdf_document.uploaded_pdf.read()
    history = EntityHistory.objects.get(entity_type='document', object_id=pdf_document.pk)
    version = history.entries.first()
    replacement = pdf_bytes('Versión nueva')
    response = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {
        'file': upload(replacement, 'nuevo.pdf'), 'expected_version': 1,
    }, format='multipart')
    assert response.status_code == 200, response.data
    assert response.data['pdf']['version'] == 2
    historical = admin_client.get(f'/api/entity-history/document/{pdf_document.pk}/versions/{version.pk}/file/')
    assert b''.join(historical.streaming_content) == original
    pdf_document.refresh_from_db()
    assert pdf_document.uploaded_pdf.read() == replacement
    assert history.entries.first().actor_label != 'Sistema'


def test_stale_replacement_preserves_current_file(admin_client, pdf_document):
    response = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {
        'file': upload(), 'expected_version': 2,
    }, format='multipart')
    assert response.status_code == 409
    pdf_document.refresh_from_db()
    assert pdf_document.pdf_version == 1


def test_pdf_metadata_remains_editable(admin_client, pdf_document):
    response = admin_client.patch(f'/api/documents/{pdf_document.pk}/update/', {
        'title': 'Identificación actualizada', 'is_client_visible': True,
    }, format='json')
    assert response.status_code == 200
    pdf_document.refresh_from_db()
    assert pdf_document.title == 'Identificación actualizada'
    assert pdf_document.is_client_visible is True


def test_pdf_rejects_text_edits(admin_client, pdf_document):
    response = admin_client.patch(f'/api/documents/{pdf_document.pk}/update/', {'content_markdown': '# Sustituido'}, format='json')
    assert response.status_code == 400
    pdf_document.refresh_from_db()
    assert pdf_document.content_markdown == ''


def test_pdf_text_is_searchable(admin_client, pdf_document):
    response = admin_client.get('/api/documents/?search=singular')
    assert response.status_code == 200
    assert pdf_document.pk in [row['id'] for row in response.data]


def test_unauthorized_user_cannot_download(api_client, pdf_document):
    api_client.force_authenticate(user=None)
    response = api_client.get(f'/api/documents/{pdf_document.pk}/pdf/')
    assert response.status_code in (401, 403)


def test_markdown_document_rejects_pdf_replacement(admin_client):
    doc = Document.objects.create(title='Markdown', content_markdown='# Editorial')
    response = admin_client.post(f'/api/documents/{doc.pk}/replace-pdf/', {
        'file': upload(), 'expected_version': 1,
    }, format='multipart')
    assert response.status_code == 400
    doc.refresh_from_db()
    assert doc.content_format == 'markdown'


def test_failed_replacement_preserves_version(admin_client, pdf_document):
    original_name = pdf_document.uploaded_pdf.name
    with patch('content.services.uploaded_pdf_service._assign_pdf', side_effect=OSError('storage offline')):
        with pytest.raises(OSError, match='storage offline'):
            admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {
                'file': upload(), 'expected_version': 1,
            }, format='multipart')
    pdf_document.refresh_from_db()
    assert pdf_document.pdf_version == 1
    assert pdf_document.uploaded_pdf.name == original_name
