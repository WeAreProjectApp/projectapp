"""Panel deletion preserves originals used by retained delivery authoring proof."""
import json

import pytest
from django.urls import reverse
from freezegun import freeze_time

from accounts.models import DeliveryPromptSource
from accounts.tests.delivery_authoring_helpers import (
    build_authoring_context, pdf_bytes, proposal_source, reference, source_document,
)
from accounts.tests.delivery_helpers import RECORDED_AT, prepare_prompt
from content.models import Document, ProposalDocument


pytestmark = pytest.mark.django_db
SOURCE_PDF = pdf_bytes('Selected original reference for the validation guide.')
RETAINED_MESSAGE = (
    'Este documento forma parte de una fuente o evidencia contractual '
    'retenida y no se puede eliminar.'
)


@pytest.fixture
def authoring_context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


def proposal_selection(document, role):
    return [{'proposal_document_id': document.pk, 'role': role,
             'applicability_note': 'Fuente seleccionada explícitamente para esta guía.'}]


@pytest.mark.parametrize('role', ['reference', 'contractual_annex'])
def test_panel_keeps_a_retained_proposal_source(admin_client, authoring_context, role):
    """Falla si eliminar un anexo retenido borra el original antes de detectar su protección."""
    document = proposal_source(authoring_context, SOURCE_PDF, 'selected-reference.pdf')
    prepare_prompt(authoring_context, sources=proposal_selection(document, role))
    storage, filename, document_id = document.file.storage, document.file.name, document.pk

    response = admin_client.delete(reverse('delete-proposal-document', args=[document.proposal_id, document_id]))

    assert response.status_code == 409
    assert response.data['code'] == 'document_used_in_delivery'
    assert response.data['error'] == RETAINED_MESSAGE
    assert ProposalDocument.objects.get(pk=document_id).file.name == filename
    with storage.open(filename, 'rb') as original:
        assert original.read() == SOURCE_PDF
    assert DeliveryPromptSource.objects.get(proposal_document_id=document_id).role == role


@pytest.mark.parametrize('role', ['reference', 'contractual_annex'])
def test_panel_reports_immutable_proof_for_a_retained_document(admin_client, authoring_context, role):
    """Falla si eliminar una fuente retenida pide retirar un contexto que es inmutable."""
    document = source_document(authoring_context, 'Texto del original elegido.')
    prepare_prompt(authoring_context, sources=[reference(document, role=role)])
    captured_source = DeliveryPromptSource.objects.get(document=document)

    response = admin_client.delete(reverse('delete-document', args=[document.pk]))

    assert response.status_code == 409
    assert response.data['code'] == 'document_used_in_delivery'
    assert response.data['error'] == RETAINED_MESSAGE
    assert response.data['hint'] == (
        'Puedes archivarlo. Las copias usadas en guías, respuestas '
        'y conformidades deben conservarse.'
    )
    assert Document.objects.get(pk=document.pk).content_markdown == 'Texto del original elegido.'
    with captured_source.file.open('rb') as retained:
        assert json.loads(retained.read())['markdown'] == 'Texto del original elegido.'
    assert DeliveryPromptSource.objects.get(document=document).role == role


def test_panel_deletes_an_unretained_uploaded_source(admin_client, authoring_context):
    """Falla si proteger las capturas impide limpiar un archivo sin fuentes ni evidencia."""
    document = proposal_source(authoring_context, SOURCE_PDF, 'unused-reference.pdf')
    storage, filename, document_id = document.file.storage, document.file.name, document.pk

    response = admin_client.delete(reverse('delete-proposal-document', args=[document.proposal_id, document_id]))

    assert response.status_code == 204
    assert ProposalDocument.objects.filter(pk=document_id).count() == 0
    assert storage.exists(filename) is False
