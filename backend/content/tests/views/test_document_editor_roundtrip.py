"""Persistence contracts for the Document Manager rich-text editor."""
import pytest
from django.urls import reverse

from content.models import Document


pytestmark = pytest.mark.django_db


RICH_FORMAT = {'/content_markdown': 'markdown_html_v1'}
CLIENT_NOTES = [{'title': 'Entrega', 'content': 'Confirmar la recepción.'}]
EXTENDED_MARKDOWN = (
    '[TOC]\n\n# Alcance aprobado\n\n> [!NOTE]\n'
    '> Revisar el material antes de compartirlo.\n\n'
    '<p><span style="color: #ff0000"><mark '
    'style="background-color: #ffff00">Prioridad</mark></span> '
    '<u>vigente</u></p>\n\n'
    '<table><tbody><tr><th rowspan="2">Servicio</th><td colspan="2">Diseño</td>'
    '</tr><tr><td>UX</td><td>UI</td></tr></tbody></table>'
)
UPDATED_MARKDOWN = (
    '# Alcance actualizado\n\n<p><span style="color: #0000ff">Aprobado</span> '
    '<u>para publicación</u></p>\n\n<table><tbody><tr><th rowspan="2">Fase</th>'
    '<td colspan="2"><mark style="background-color: #ffff00">Entrega</mark>'
    '</td></tr><tr><td>Uno</td><td>Dos</td></tr></tbody></table>'
)


def _create_document(client, markdown, text_formats):
    return client.post(
        reverse('create-document-from-markdown'),
        {
            'title': 'Guía de entrega',
            'markdown': markdown,
            'text_formats': text_formats,
            'client_custom_notes': CLIENT_NOTES,
        },
        format='json',
    )


def test_create_from_markdown_reopens_extended_editorial_source(admin_client):
    """Falla si crear un documento rico cambia su fuente o metadatos al reabrirlo."""
    created = _create_document(admin_client, EXTENDED_MARKDOWN, RICH_FORMAT)
    document_id = created.json()['id']
    reopened = admin_client.get(reverse('retrieve-document', args=[document_id]))
    reopened_data = reopened.json()
    stored = Document.objects.get(pk=document_id)

    assert (created.status_code, reopened.status_code) == (201, 200)
    assert (stored.content_markdown, stored.text_formats, stored.client_custom_notes) == (
        EXTENDED_MARKDOWN, RICH_FORMAT, CLIENT_NOTES,
    )
    assert (
        reopened_data['content_markdown'], reopened_data['text_formats'],
        reopened_data['client_custom_notes'],
    ) == (EXTENDED_MARKDOWN, RICH_FORMAT, CLIENT_NOTES)


def test_patch_reopens_revised_rich_source_with_existing_private_notes(admin_client):
    """Falla si editar el cuerpo rico pierde las notas privadas que no formaban parte del cambio."""
    created = _create_document(admin_client, EXTENDED_MARKDOWN, RICH_FORMAT)
    document_id = created.json()['id']
    updated = admin_client.patch(
        reverse('update-document', args=[document_id]),
        {'content_markdown': UPDATED_MARKDOWN, 'text_formats': RICH_FORMAT},
        format='json',
    )
    reopened = admin_client.get(reverse('retrieve-document', args=[document_id]))

    assert (created.status_code, updated.status_code, reopened.status_code) == (201, 200, 200)
    assert (reopened.json()['content_markdown'], reopened.json()['text_formats']) == (
        UPDATED_MARKDOWN, RICH_FORMAT,
    )
    assert reopened.json()['client_custom_notes'] == CLIENT_NOTES


def test_detail_keeps_legacy_markdown_without_an_editorial_annotation(admin_client):
    """Falla si reabrir contenido legado inventa un perfil editorial que cambia su interpretación."""
    legacy_markdown = '# Archivo histórico\n\n**Texto existente**'
    created = _create_document(admin_client, legacy_markdown, {})
    document_id = created.json()['id']
    reopened = admin_client.get(reverse('retrieve-document', args=[document_id]))
    stored = Document.objects.get(pk=document_id)

    assert (created.status_code, reopened.status_code) == (201, 200)
    assert (stored.content_markdown, stored.text_formats) == (legacy_markdown, {})
    assert reopened.json().get('text_formats') is None
    assert reopened.json()['content_markdown'] == legacy_markdown


def test_patch_rejects_unsafe_rich_html_without_changing_document(admin_client):
    """Falla si un PATCH inseguro modifica la fuente segura que el editor ya había guardado."""
    created = _create_document(admin_client, EXTENDED_MARKDOWN, RICH_FORMAT)
    document_id = created.json()['id']
    original = Document.objects.get(pk=document_id)
    original_values = (
        original.content_markdown, original.text_formats, original.client_custom_notes,
    )
    rejected = admin_client.patch(
        reverse('update-document', args=[document_id]),
        {
            'content_markdown': '<script>alert(1)</script>',
            'text_formats': RICH_FORMAT,
        },
        format='json',
    )
    original.refresh_from_db()

    assert created.status_code == 201
    assert rejected.status_code == 400
    assert 'text_formats' in rejected.json()
    assert (
        original.content_markdown, original.text_formats, original.client_custom_notes,
    ) == original_values
