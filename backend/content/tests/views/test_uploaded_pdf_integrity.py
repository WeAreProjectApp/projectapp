"""PDF rollback, private evidence and resource failures are observable contracts."""
import hashlib
import io
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from accounts.models import ContractSignatureEvidence, ProjectContract, UserProfile
from django.core.files.storage import storages
from rest_framework.test import APIClient

from content.models import Document, DocumentType, EntityHistory
from content.services.entity_history import history_operation
from content.services.uploaded_pdf_service import inspect_upload
from content.tests.views.test_uploaded_pdf_documents import (
    pdf_bytes,
    upload,
)
from content.tests.views.test_uploaded_pdf_documents import (
    pdf_document as pdf_document,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def pdf_type():
    return DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})[0]


def private_files():
    return set(Path(storages['private'].location).rglob('*.pdf'))


def test_failed_outer_history_flush_removes_new_file(admin_client):
    before = private_files()
    with patch('content.services.entity_history._flush', side_effect=RuntimeError('history unavailable')):
        with pytest.raises(RuntimeError, match='history unavailable'):
            admin_client.post('/api/documents/create-from-pdf/', {'title': 'Rollback', 'file': upload()}, format='multipart')
    assert private_files() == before
    assert Document.objects.filter(title='Rollback').exists() is False
    assert EntityHistory.objects.filter(object_label='Rollback').exists() is False


def test_replacement_outer_rollback_preserves_original(admin_client, pdf_document):
    original = pdf_document.uploaded_pdf.name
    before = private_files()
    with patch('content.services.entity_history._flush', side_effect=RuntimeError('history unavailable')):
        with pytest.raises(RuntimeError, match='history unavailable'):
            admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {'file': upload(), 'expected_version': 1}, format='multipart')
    pdf_document.refresh_from_db()
    assert pdf_document.uploaded_pdf.name == original
    assert pdf_document.pdf_version == 1
    assert private_files() == before


def test_marked_outer_rollback_removes_new_file(admin_user, pdf_type):
    from django.db import transaction

    from content.serializers.document import DocumentCreateUpdateSerializer
    from content.services.uploaded_pdf_service import create_pdf_document
    before = private_files()
    serializer = DocumentCreateUpdateSerializer(data={'title': 'Marked rollback'})
    serializer.is_valid(raise_exception=True)
    with history_operation(actor=admin_user):
        create_pdf_document(serializer, upload(), actor=admin_user)
        transaction.set_rollback(True)
    assert Document.objects.filter(title='Marked rollback').exists() is False
    assert private_files() == before


def test_extraction_timeout_retains_validated_pdf():
    with patch('content.services.uploaded_pdf_service._probe', side_effect=[{'valid': True}, subprocess.TimeoutExpired('extract', 5)]):
        data, metadata = inspect_upload(upload())
    assert data.startswith(b'%PDF-')
    assert metadata == {'text': '', 'status': 'unavailable'}


def test_structural_timeout_rejects_file():
    from rest_framework.exceptions import ValidationError
    with patch('content.services.uploaded_pdf_service._probe', side_effect=subprocess.TimeoutExpired('validate', 5)):
        with pytest.raises(ValidationError, match='validar'):
            inspect_upload(upload())


def test_blank_pdf_is_accepted_without_search_text(admin_client):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    data = io.BytesIO()
    writer.write(data)
    response = admin_client.post('/api/documents/create-from-pdf/', {'title': 'Escaneado', 'file': upload(data.getvalue())}, format='multipart')
    assert response.status_code == 201, response.data
    assert response.data['pdf']['text_status'] == 'empty'
    assert Document.objects.get(pk=response.data['id']).pdf_search_text == ''


def test_replacement_removes_old_search_text(admin_client, pdf_document):
    response = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {'file': upload(pdf_bytes('Texto renovado')), 'expected_version': 1}, format='multipart')
    assert response.status_code == 200, response.data
    assert pdf_document.pk not in [row['id'] for row in admin_client.get('/api/documents/?search=singular').data]
    assert pdf_document.pk in [row['id'] for row in admin_client.get('/api/documents/?search=renovado').data]


def test_private_pdf_has_no_public_media_url(pdf_document):
    from django.conf import settings
    assert Path(pdf_document.uploaded_pdf.path).is_relative_to(Path(settings.PRIVATE_MEDIA_ROOT))
    assert not Path(settings.MEDIA_ROOT, pdf_document.uploaded_pdf.name).exists()


def test_deleted_document_keeps_historical_bytes(admin_client, pdf_document):
    history = EntityHistory.objects.get(entity_type='document', object_id=pdf_document.pk)
    version = history.entries.first()
    response = admin_client.delete(f'/api/documents/{pdf_document.pk}/delete/')
    assert response.status_code == 204
    result = admin_client.get(f'/api/entity-history/document/{pdf_document.pk}/versions/{version.pk}/file/')
    assert result.status_code == 200
    assert b''.join(result.streaming_content).startswith(b'%PDF-')


def test_published_pdf_is_only_visible_to_its_client(admin_client, admin_user, pdf_document):
    from django.contrib.auth import get_user_model
    owner = get_user_model().objects.create_user(username='pdf-client')
    UserProfile.objects.get_or_create(user=owner, defaults={'role': 'client'})
    pdf_document.client_user = owner
    pdf_document.is_client_visible = True
    pdf_document.save()
    client = APIClient()
    client.force_authenticate(owner)
    response = client.get(f'/api/accounts/documents/{pdf_document.uuid}/pdf/')
    assert response.status_code == 200
    assert response.content == pdf_document.uploaded_pdf.read()
    other = get_user_model().objects.create_user(username='other-pdf-client')
    UserProfile.objects.get_or_create(user=other, defaults={'role': 'client'})
    client.force_authenticate(other)
    hidden = client.get(f'/api/accounts/documents/{pdf_document.uuid}/pdf/')
    assert hidden.status_code == 404


def test_draft_contract_keeps_pdf_replaceable(admin_client, pdf_document):
    ProjectContract.objects.create(document=pdf_document, title='Borrador', key='draft')
    result = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {'file': upload(), 'expected_version': 1}, format='multipart')
    assert result.status_code == 200, result.data
    assert result.data['pdf']['version'] == 2


def test_signed_evidence_blocks_replacement(admin_client, admin_user, pdf_document):
    contract = ProjectContract.objects.create(document=pdf_document, title='Firmado', key='signed')
    original = pdf_document.uploaded_pdf.read()
    evidence = ContractSignatureEvidence.objects.create(contract=contract, method='uploaded', signer_name='Cliente', signed_at=datetime(2026, 10, 29, tzinfo=UTC), attested_by=admin_user, sha256=hashlib.sha256(original).hexdigest())
    from django.core.files.base import ContentFile
    evidence.file.save('signed.pdf', ContentFile(original), save=True)
    before = private_files()
    result = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {'file': upload(), 'expected_version': 1}, format='multipart')
    assert result.status_code == 409
    assert private_files() == before
    assert evidence.file.read() == original
    assert admin_client.get(f'/api/documents/{pdf_document.pk}/detail/').data['pdf_replaceable'] is False


def test_delivery_publication_blocks_replacement(admin_client, pdf_document):
    from accounts.models import DeliveryDocumentSnapshot
    from accounts.services import delivery_workflow as delivery
    from accounts.tests.delivery_helpers import build_delivery_context, publish, version
    context = build_delivery_context()
    pdf_document.project = context.project
    pdf_document.client_user = context.client
    pdf_document.save()
    delivery.link_document(context.project.pk, context.admin, {'expected_version': version(context), 'level': 'stage', 'target_id': context.stage.pk, 'document_id': pdf_document.pk})
    publish(context)
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=pdf_document)
    original = snapshot.file.read()
    result = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/', {'file': upload(), 'expected_version': 1}, format='multipart')
    assert result.status_code == 409
    snapshot.refresh_from_db()
    assert snapshot.file.read() == original
    assert snapshot.sha256 == hashlib.sha256(original).hexdigest()


def test_delivery_keeps_its_ten_mib_limit(pdf_document):
    from accounts.services.delivery_documents import _raw_pdf
    from django.core.files.base import ContentFile
    from rest_framework.exceptions import ValidationError
    pdf_document.uploaded_pdf.save('over-delivery-limit.pdf', ContentFile(b'%PDF-' + b'x' * (10 * 1024 * 1024)), save=False)
    with pytest.raises(ValidationError, match='10 MB'):
        _raw_pdf(pdf_document)


def test_stale_metadata_save_preserves_latest_pdf(admin_client, admin_user, pdf_document):
    from content.serializers.document import DocumentCreateUpdateSerializer
    serializer = DocumentCreateUpdateSerializer(pdf_document, data={'title': 'Metadata edit'}, partial=True)
    serializer.is_valid(raise_exception=True)
    replacement = pdf_bytes('Latest PDF bytes')
    response = admin_client.post(f'/api/documents/{pdf_document.pk}/replace-pdf/',
                                 {'file': upload(replacement), 'expected_version': 1}, format='multipart')
    assert response.status_code == 200
    updated = serializer.save(updated_by=admin_user)
    assert updated.pdf_version == 2
    assert updated.title == 'Metadata edit'
    assert updated.uploaded_pdf.read() == replacement


@pytest.mark.django_db(transaction=True)
def test_post_commit_callback_failure_preserves_committed_file(admin_user, pdf_type):
    from django.db import transaction

    from content.serializers.document import DocumentCreateUpdateSerializer
    from content.services import uploaded_pdf_service as service
    assign = service._assign_pdf
    def callback():
        raise RuntimeError('post commit failure')
    def assign_with_callback(*args, **kwargs):
        assign(*args, **kwargs)
        transaction.on_commit(callback)
    serializer = DocumentCreateUpdateSerializer(data={'title': 'Committed PDF'})
    serializer.is_valid(raise_exception=True)
    with patch.object(service, '_assign_pdf', side_effect=assign_with_callback):
        with pytest.raises(RuntimeError, match='post commit failure'):
            service.create_pdf_document(serializer, upload(), actor=admin_user)
    committed = Document.objects.get(title='Committed PDF')
    assert committed.uploaded_pdf.storage.exists(committed.uploaded_pdf.name)
    assert committed.uploaded_pdf.read().startswith(b'%PDF-')


def test_generated_evidence_has_priority_over_uploaded_source(admin_client, pdf_document):
    from django.core.files.base import ContentFile

    from content.services.document_pdf_service import DocumentPdfService
    generated = pdf_bytes('Generated evidence')
    pdf_document.generated_file.save('generated.pdf', ContentFile(generated), save=True)
    response = admin_client.get(f'/api/documents/{pdf_document.pk}/pdf/')
    assert response.status_code == 200
    assert response.content == generated
    assert DocumentPdfService.generate(pdf_document) == generated
    version = EntityHistory.objects.get(entity_type='document', object_id=pdf_document.pk).entries.first()
    historical = admin_client.get(f'/api/entity-history/document/{pdf_document.pk}/versions/{version.pk}/file/')
    assert b''.join(historical.streaming_content) == generated
