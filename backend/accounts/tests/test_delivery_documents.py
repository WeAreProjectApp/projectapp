"""Publication and signed-contract evidence protect every client document route."""
import hashlib
import io
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from reportlab.pdfgen.canvas import Canvas
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import ContractSignatureEvidence, DeliveryDocumentLink, DeliveryDocumentSnapshot, Project
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish, version
from content.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


@pytest.fixture
def api(context):
    client = APIClient()
    client.force_authenticate(context.client)
    return client


def attach(context, doc, *, level='stage', target=None):
    result = delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': level,
        'target_id': target or context.stage.pk, 'document_id': doc.pk,
    })
    return result['result']['id']


def guide_document(context, **extra):
    fields = {'title': 'Guía original', 'project': context.project, 'client_user': context.client,
              'is_client_visible': True, 'content_markdown': '# Guía\nTexto original.',
              'include_portada': False, 'include_subportada': False, 'include_contraportada': False}
    fields.update(extra)
    return Document.objects.create(**fields)


def signed_pdf():
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(50, 700, 'Cliente: contrato firmado')
    canvas.save()
    return stream.getvalue()


@pytest.mark.parametrize('endpoint', ['list', 'detail', 'pdf', 'sign'])
def test_draft_attachment_is_hidden_from_global_portal(context, api, endpoint):
    doc = guide_document(context, requires_signature=True)
    attach(context, doc)
    paths = {'list': '/api/accounts/documents/', 'detail': f'/api/accounts/documents/{doc.uuid}/',
             'pdf': f'/api/accounts/documents/{doc.uuid}/pdf/', 'sign': f'/api/accounts/documents/{doc.uuid}/sign/'}
    method = {'list': api.get, 'detail': api.get, 'pdf': api.get, 'sign': api.post}

    response = method[endpoint](paths[endpoint])

    expected = {'list': 200, 'detail': 404, 'pdf': 404, 'sign': 404}
    assert response.status_code == expected[endpoint]
    assert str(doc.uuid) not in str(response.data)


def test_published_pdf_survives_source_edit(context, api):
    doc = guide_document(context)
    link_id = attach(context, doc)
    publish(context)
    original = delivery.document_pdf(context.project.pk, context.client, link_id)[0]
    doc.title = 'Borrador privado nuevo'
    doc.content_markdown = '# Contenido distinto'
    doc.save()

    response = api.get(f'/api/accounts/documents/{doc.uuid}/pdf/')
    detail = api.get(f'/api/accounts/documents/{doc.uuid}/')

    assert response.content == original
    assert detail.data['title'] == 'Guía original'


def test_admin_portal_reads_current_editorial_pdf(context, api):
    """Fails if the administrator portal replaces its current source PDF with client evidence."""
    doc = guide_document(context)
    attach(context, doc)
    publish(context)
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=doc)
    with snapshot.file.open('rb') as source:
        public_bytes = source.read()
    signature = ContractSignatureEvidence.objects.get()
    signed_hash = signature.sha256
    current_bytes = signed_pdf()
    doc.generated_file.save('editorial-current.pdf', ContentFile(current_bytes), save=True)
    admin = APIClient()
    admin.force_authenticate(context.admin)

    response = admin.get(f'/api/accounts/documents/{doc.uuid}/pdf/')
    snapshot.refresh_from_db()
    signature.refresh_from_db()
    with snapshot.file.open('rb') as source:
        frozen_bytes = source.read()

    assert response.status_code == 200
    assert response.content == current_bytes
    assert response['Cache-Control'] == 'private, no-store'
    assert frozen_bytes == public_bytes
    assert (snapshot.title, signature.sha256) == ('Guía original', signed_hash)


def test_archived_reply_source_keeps_admin_metadata(context):
    """Fails if archiving a reply source erases admin evidence or exposes it to the client."""
    doc = guide_document(context, title='Respuesta archivada')
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'archived-project-reply',
        'level': 'project', 'target_id': context.project.pk,
        'requirement_ids': [], 'message': 'La fuente sigue disponible para administración.', 'document_ids': [doc.pk],
    })
    doc.is_archived = True
    doc.save(update_fields=['is_archived'])

    admin_message = delivery.overview(context.project.pk, context.admin)['project']['messages'][0]
    client_message = delivery.overview(context.project.pk, context.client)['project']['messages'][0]

    assert admin_message['documents'] == [{'document_id': doc.pk, 'title': 'Respuesta archivada', 'uuid': str(doc.uuid)}]
    assert client_message['documents'] == []
    assert DeliveryDocumentSnapshot.objects.count() == 0
    assert version(context) == 1


@pytest.mark.parametrize('route', [
    lambda context, api, link_id: api.get(
        f'/api/accounts/projects/{context.project.pk}/delivery/documents/?level=phase&target_id={context.phase.pk}'
    ),
    lambda context, api, link_id: api.get(
        f'/api/accounts/projects/{context.project.pk}/delivery/documents/{link_id}/pdf/'
    ),
    lambda context, api, link_id: api.get(
        f'/api/accounts/projects/{context.project.pk}/delivery/contracts/{context.contract.pk}/pdf/'
    ),
], ids=['phase-list', 'linked-pdf', 'contract-pdf'])
def test_hidden_contract_blocks_inherited_document_reads(context, api, route):
    """Fails if a phase document survives the visibility guard after its contract is hidden."""
    doc = guide_document(context, title='Fase publicada')
    link_id = attach(context, doc, level='phase', target=context.phase.pk)
    publish(context)
    snapshot = DeliveryDocumentSnapshot.objects.get(link_id=link_id)
    frozen = (snapshot.link_id, snapshot.title, snapshot.sha256)
    context.contract.client_visible = False
    context.contract.save(update_fields=['client_visible'])

    response = route(context, api, link_id)

    snapshot.refresh_from_db()
    assert response.status_code == 404
    assert str(doc.uuid) not in response.content.decode()
    assert (snapshot.link_id, snapshot.title, snapshot.sha256) == frozen


def test_approved_requirement_document_cannot_be_unlinked(context):
    doc = guide_document(context)
    link_id = attach(context, doc, level='requirement', target=context.first.pk)
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(context, (context.first, 'approved')))

    with pytest.raises(ValidationError, match='evidencia'):
        delivery.unlink_document(context.project.pk, context.admin, link_id, {'expected_version': version(context)})

    assert DeliveryDocumentLink.objects.filter(pk=link_id).exists()


def test_approved_requirement_cannot_get_new_guide_document(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(context, (context.first, 'approved')))
    doc = guide_document(context)

    with pytest.raises(ValidationError, match='congelado'):
        attach(context, doc, level='requirement', target=context.first.pk)


def test_reply_document_is_available_as_captured_evidence(context):
    publish(context)
    doc = guide_document(context)
    result = delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'reply', 'level': 'stage', 'target_id': context.stage.pk,
        'requirement_ids': [context.second.pk], 'message': 'Prueba de nuevo con esta guía.', 'document_ids': [doc.pk],
    })
    link = DeliveryDocumentLink.objects.get(document=doc)

    pdf, title = delivery.document_pdf(context.project.pk, context.client, link.pk)

    assert pdf.startswith(b'%PDF-')
    assert title == 'Guía original'
    assert result['result']['kind'] == 'messages'
    assert DeliveryDocumentSnapshot.objects.filter(link=link).count() == 1


def test_contradictory_source_owner_is_hidden(context, api):
    other = User.objects.create_user('contradictory', 'other@example.test')
    doc = guide_document(context, client_user=other)

    response = api.get(f'/api/accounts/documents/{doc.uuid}/')

    assert response.status_code == 404


def test_unsigned_contract_is_available_before_publication(context, api):
    context.document.signed_at = None
    context.document.signed_by = None
    context.document.save(update_fields=['signed_at', 'signed_by'])

    response = api.get(f'/api/accounts/projects/{context.project.pk}/delivery/contracts/{context.contract.pk}/pdf/')

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert context.stage.publications.count() == 0


def test_portal_signature_captures_immutable_contract_pdf(context, api):
    context.document.signed_at = None
    context.document.signed_by = None
    context.document.save(update_fields=['signed_at', 'signed_by'])
    with patch('accounts.tasks.notify_team_document_signed_task'):
        response = api.post(f'/api/accounts/documents/{context.document.uuid}/sign/', {'accept': True, 'signature_name': 'Cliente'}, format='json')
    original = delivery.contract_pdf(context.project.pk, context.client, 'contracts', context.contract.pk)[0]
    context.document.content_markdown = '# Nueva redacción que no firmó el cliente'
    context.document.save(update_fields=['content_markdown', 'updated_at'])

    after = api.get(f'/api/accounts/documents/{context.document.uuid}/pdf/')

    assert response.status_code == 200
    assert after.content == original
    assert ContractSignatureEvidence.objects.get().method == 'portal'
    assert ContractSignatureEvidence.objects.get().sha256 == hashlib.sha256(original).hexdigest()


def test_external_signature_retains_original_pdf(context):
    original = signed_pdf()
    delivery.attest_signature(context.project.pk, context.admin, 'contracts', context.contract.pk, {
        'expected_version': 0, 'request_id': 'signature', 'signer_name': 'Cliente',
        'signed_at': '2026-09-30T12:00:00Z', 'attestation': 'Se verificó el PDF firmado por el cliente.',
    }, SimpleUploadedFile('signed.pdf', original, content_type='application/pdf'))
    context.document.content_markdown = '# Otro documento fuente'
    context.document.save(update_fields=['content_markdown', 'updated_at'])

    pdf, _ = delivery.contract_pdf(context.project.pk, context.client, 'contracts', context.contract.pk)

    assert pdf == original
    assert ContractSignatureEvidence.objects.get().method == 'external'


def test_foreign_project_document_cannot_be_attached(context):
    other_project = Project.objects.create(name='Otro proyecto', client=context.client)
    doc = guide_document(context, project=other_project)

    with pytest.raises(ValidationError, match='otro proyecto'):
        attach(context, doc)


def test_invalid_pdf_cannot_attest_a_signature(context):
    with pytest.raises(ValidationError, match='PDF válido'):
        delivery.attest_signature(context.project.pk, context.admin, 'contracts', context.contract.pk, {
            'expected_version': 0, 'request_id': 'invalid-pdf', 'signer_name': 'Cliente',
            'signed_at': '2026-09-30T12:00:00Z', 'attestation': 'Archivo verificado.',
        }, SimpleUploadedFile('signed.pdf', b'not a pdf', content_type='application/pdf'))
    assert ContractSignatureEvidence.objects.count() == 0


def test_failed_publication_removes_private_artifacts(context):
    valid = guide_document(context)
    invalid = guide_document(context, title='Documento vacío', content_markdown='')
    attach(context, valid)
    attach(context, invalid)
    before = set(Path(settings.PRIVATE_MEDIA_ROOT).rglob('*.pdf'))

    with pytest.raises(ValidationError, match='contenido válido'):
        publish(context)

    assert set(Path(settings.PRIVATE_MEDIA_ROOT).rglob('*.pdf')) == before
    assert ContractSignatureEvidence.objects.count() == 0
    assert DeliveryDocumentSnapshot.objects.count() == 0


def test_administrator_cannot_sign_for_the_client(context):
    api = APIClient()
    api.force_authenticate(context.admin)
    context.document.signed_at = None
    context.document.save(update_fields=['signed_at'])

    response = api.post(f'/api/accounts/documents/{context.document.uuid}/sign/', {'signature_name': 'Admin'}, format='json')

    assert response.status_code == 403
    context.document.refresh_from_db()
    assert context.document.signed_at is None


def test_signed_contract_source_cannot_be_replaced(context):
    publish(context)
    replacement = guide_document(context, requires_signature=True)

    with pytest.raises(ValidationError, match='fuente del contrato firmado'):
        delivery.mutate_node(context.project.pk, context.admin, 'contracts',
                             {'expected_version': version(context), 'document_id': replacement.pk}, context.contract.pk)


def test_legacy_portal_signature_gets_verified_capture_at_publication(context):
    publish(context)
    evidence = ContractSignatureEvidence.objects.get()

    assert evidence.method == 'portal'
    assert evidence.source_snapshot['signed_by_id'] == context.client.pk
    assert evidence.source_snapshot['document_id'] == context.document.pk
