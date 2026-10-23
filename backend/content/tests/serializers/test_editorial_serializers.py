"""Serializer contracts for editorial-format metadata."""

import pytest

from content.models import Document
from content.serializers.communication import CommunicationMessageCreateSerializer
from content.serializers.document import (
    DocumentCreateUpdateSerializer,
    DocumentDetailSerializer,
)


pytestmark = pytest.mark.django_db


def test_document_serializer_persists_format_profile_for_existing_content():
    """Falla si guardar el perfil editorial no persiste el formato del cuerpo ya existente."""
    document = Document.objects.create(
        title='Propuesta de diseño',
        content_markdown='**Alcance aprobado**',
    )
    serializer = DocumentCreateUpdateSerializer(
        document,
        data={'text_formats': {'/content_markdown': 'markdown'}},
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    document.refresh_from_db()

    assert document.text_formats == {'/content_markdown': 'markdown'}


def test_document_detail_serializer_returns_persisted_format_profile():
    """Falla si el panel no recibe el perfil que necesita para reabrir un documento formateado."""
    document = Document.objects.create(
        title='Acta de entrega',
        content_markdown='**Aceptado**',
        text_formats={'/content_markdown': 'markdown'},
    )

    payload = DocumentDetailSerializer(document).data

    assert payload['text_formats'] == {'/content_markdown': 'markdown'}


def test_document_serializer_rejects_unsafe_rich_html_without_writing_profile():
    """Falla si un perfil editorial con HTML ejecutable se guarda en un documento."""
    document = Document.objects.create(title='Documento seguro', content_markdown='Texto inicial')
    serializer = DocumentCreateUpdateSerializer(
        document,
        data={
            'content_markdown': '<script>alert(1)</script>',
            'text_formats': {'/content_markdown': 'markdown_html_v1'},
        },
        partial=True,
    )

    assert not serializer.is_valid()
    assert 'text_formats' in serializer.errors
    document.refresh_from_db()

    assert document.text_formats == {}


def test_communication_serializer_accepts_whatsapp_profile_for_its_content():
    """Falla si un borrador de WhatsApp no puede declarar el perfil de su propio contenido."""
    serializer = CommunicationMessageCreateSerializer(data={
        'channel': 'whatsapp',
        'direction': 'outgoing',
        'content': '*Confirmado*',
        'text_formats': {'/content': 'whatsapp_v1'},
    })

    assert serializer.is_valid(), serializer.errors

    assert serializer.validated_data['text_formats'] == {
        '/content': 'whatsapp_v1',
    }


def test_communication_serializer_rejects_unrelated_format_profile():
    """Falla si un mensaje puede declarar formato para su asunto no editorial."""
    serializer = CommunicationMessageCreateSerializer(data={
        'channel': 'email',
        'direction': 'outgoing',
        'subject': 'Entrega',
        'content': 'Cuerpo',
        'text_formats': {'/subject': 'markdown'},
    })

    assert not serializer.is_valid()

    assert str(serializer.errors['text_formats']) == (
        'Campo o formato no permitido: /subject.'
    )
