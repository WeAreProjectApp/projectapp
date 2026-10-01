"""Recorded approval documents are immutable evidence with tenant ownership."""
import hashlib

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import DeliveryReviewDocumentEvidence, DeliveryStage, RequirementReview, UserProfile
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_documents import _raw_pdf
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish, version
from content.models import Document

pytestmark = pytest.mark.django_db


def evidence_document(context):
    return Document.objects.create(
        project=context.project, client_user=context.client, title='Aprobación del cliente',
        content_markdown='# Aprobación\nApruebo guardar el registro.',
        include_portada=False, include_subportada=False, include_contraportada=False,
    )


def historical_decision(context, doc):
    result = decisions(context, (context.first, 'approved'), request_id='external-proof')
    result.update({
        'client_statement': True, 'evidence_message': 'Apruebo guardar el registro.',
        'evidence_document_ids': [doc.pk], 'original_reviewer': 'Cliente',
        'occurred_at': '2026-09-30T12:00:00Z', 'evidence_channel': 'document',
        'external_reference': 'Documento recibido del cliente el 30 de septiembre.',
    })
    return result


def recorded_evidence(context):
    publish(context)
    doc = evidence_document(context)
    original_pdf = _raw_pdf(doc)
    doc.generated_file.save('external-approval.pdf', ContentFile(original_pdf), save=True)
    delivery.review_stage(context.project.pk, context.admin, context.stage.pk,
                          historical_decision(context, doc), historical=True)
    return doc, original_pdf, DeliveryReviewDocumentEvidence.objects.get(document=doc)


def test_review_evidence_pdf_survives_source_edit():
    """Fails if editing the source rewrites the file proving a past approval."""
    context = build_delivery_context()
    doc, original_pdf, evidence = recorded_evidence(context)
    doc.title = 'Texto posterior'
    doc.content_markdown = '# Otro contenido\nNo corresponde a la aprobación.'
    doc.generated_file = None
    doc.save(update_fields=['title', 'content_markdown', 'generated_file'])
    api = APIClient()
    api.force_authenticate(context.client)

    response = api.get(f'/api/accounts/projects/{context.project.pk}/delivery/reviews/'
                       f'{evidence.review_id}/evidence/{evidence.pk}/pdf/')

    assert response.status_code == 200
    assert response.content == original_pdf
    assert evidence.sha256 == hashlib.sha256(original_pdf).hexdigest()
    assert 'aprobacion-del-cliente.pdf' in response['Content-Disposition']


def test_foreign_client_cannot_download_review_evidence():
    """Fails if a proof identifier bypasses the project owner's boundary."""
    context = build_delivery_context()
    _, _, evidence = recorded_evidence(context)
    outsider = User.objects.create_user('outside-evidence', 'outside@example.test', 'test-password')
    UserProfile.objects.create(user=outsider, role='client')
    api = APIClient()
    api.force_authenticate(outsider)

    response = api.get(f'/api/accounts/projects/{context.project.pk}/delivery/reviews/'
                       f'{evidence.review_id}/evidence/{evidence.pk}/pdf/')

    assert response.status_code == 404
    assert response.data['detail'] == 'Proyecto no encontrado.'


def test_draft_linked_document_cannot_back_a_public_approval():
    """Fails if attaching historical proof leaks a guide awaiting publication."""
    context = build_delivery_context()
    publish(context)
    doc = evidence_document(context)
    private_stage = DeliveryStage.objects.create(phase=context.phase, key='privada', title='Etapa privada')
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'stage', 'target_id': private_stage.pk, 'document_id': doc.pk,
    })

    with pytest.raises(ValidationError) as caught:
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk,
                              historical_decision(context, doc), historical=True)

    context.first.refresh_from_db()
    assert caught.value.detail['code'] == 'document_not_published'
    assert RequirementReview.objects.count() == 0
    assert DeliveryReviewDocumentEvidence.objects.count() == 0
    assert context.first.review_status == 'in_review'
