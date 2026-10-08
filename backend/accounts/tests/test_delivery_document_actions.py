"""Document policies protect the agreement and the evidence a client approved."""
import io

import pytest
from content.models import BusinessProposal, Document, DocumentType, ProposalDocument
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
from reportlab.pdfgen.canvas import Canvas
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import (
    ContractSignatureEvidence,
    DeliveryDocumentSnapshot,
    Project,
    ProjectContract,
    ProjectPhase,
)
from accounts.services import delivery_documents as documents
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import (
    RECORDED_AT,
    build_delivery_context,
    decisions,
    prepare_prompt,
    publish,
    version,
)

pytestmark = pytest.mark.django_db


def pdf_bytes(*texts):
    """Build a deterministic PDF containing the supplied text pages."""
    output = io.BytesIO()
    canvas = Canvas(output, invariant=1)
    for text in texts:
        canvas.drawString(30, 700, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


AGREEMENT_PDF = pdf_bytes('Client agreed to validate invoice totals.')


@pytest.fixture
def context():
    """Provide an owned delivery graph with its original agreement PDF."""
    value = build_delivery_context()
    value.document.generated_file.save('agreement.pdf', ContentFile(AGREEMENT_PDF), save=True)
    return value


def guide_document(context, **overrides):
    """Create a visible guide document with a retained PDF for the project."""
    fields = {
        'title': 'Guía documental acordada', 'project': context.project,
        'client_user': context.client, 'content_markdown': '# Guía\nPasos del cliente.',
        'include_portada': False, 'include_subportada': False, 'include_contraportada': False,
        'is_client_visible': True,
    }
    fields.update(overrides)
    document = Document.objects.create(**fields)
    document.generated_file.save('guide.pdf', ContentFile(AGREEMENT_PDF), save=True)
    return document


def attach(context, document, *, level='stage', target_id=None):
    """Link a document to the requested delivery level through the service."""
    response = delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': level,
        'target_id': target_id or context.stage.pk, 'document_id': document.pk,
    })
    return response['result']['id']


def attest(context, body):
    """Record the client's external signature evidence for the contract."""
    delivery.attest_signature(context.project.pk, context.admin, 'contracts', context.contract.pk, {
        'expected_version': version(context), 'request_id': 'document-action-signature',
        'signer_name': 'Cliente titular', 'signed_at': RECORDED_AT.isoformat(),
        'attestation': 'Se recibió y verificó el acuerdo firmado por el cliente.',
    }, SimpleUploadedFile('signed.pdf', body, content_type='application/pdf'))
    return ContractSignatureEvidence.objects.get(contract=context.contract)


def invalid_pdf(kind):
    """Build an unreadable PDF fixture for the selected validation failure."""
    if kind == 'malformed':
        return b'%PDF-1.7\nNot a readable PDF.'
    writer = PdfWriter()
    page_counts = {'encrypted': 1, 'empty': 0, 'too_many_pages': 501}
    for _ in range(page_counts[kind]):
        writer.add_blank_page(width=595, height=842)
    if kind == 'encrypted':
        writer.encrypt('unavailable-client-password')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize('kind', ['encrypted', 'empty', 'too_many_pages', 'malformed'])
def test_external_signature_rejects_a_pdf_the_client_cannot_read(context, kind):
    """Reject external signature evidence that the client cannot read."""
    with pytest.raises(ValidationError) as rejected:
        attest(context, invalid_pdf(kind))

    assert rejected.value.detail['code'] == 'pdf_invalid'
    assert not ContractSignatureEvidence.objects.filter(contract=context.contract).exists()
    assert version(context) == 0


@pytest.mark.parametrize('stream_factory', [
    lambda body: SimpleUploadedFile('large.pdf', body, content_type='application/pdf'),
    io.BytesIO,
], ids=['upload-size', 'stream-size'])
def test_pdf_input_enforces_the_ten_megabyte_limit(stream_factory):
    """Reject PDF input that exceeds the ten megabyte limit."""
    body = AGREEMENT_PDF + b'\n%' + b'x' * documents.MAX_PDF_BYTES

    with pytest.raises(ValidationError) as rejected:
        documents.validated_pdf_bytes(stream_factory(body))

    assert rejected.value.detail['code'] == 'pdf_too_large'


def test_authoring_prompt_uses_the_exact_external_agreement(context):
    """Use the externally signed agreement when preparing an authoring prompt."""
    attest(context, AGREEMENT_PDF)
    context.document.content_markdown = '# Borrador privado que no firmó el cliente'
    context.document.save(update_fields=['content_markdown'])

    response = prepare_prompt(context)

    assert 'Client agreed to validate invoice totals.' in response['prompt']
    assert 'Borrador privado que no firmó el cliente' not in response['prompt']


@pytest.mark.parametrize(('texts', 'prefix', 'excluded'), [
    (('A' * 60_000 + 'EXCLUDED-AFTER-TEXT-LIMIT',), 'A' * 20, 'EXCLUDED-AFTER-TEXT-LIMIT'),
    (tuple(f'Agreed page {number}' for number in range(1, 101)) + ('EXCLUDED-PAGE-101',), 'Agreed page 1', 'EXCLUDED-PAGE-101'),
], ids=['text-limit', 'page-limit'])
def test_external_agreement_context_limits_untrusted_pdf_content(context, texts, prefix, excluded):
    """Limit untrusted signed PDF text included in the authoring context."""
    attest(context, pdf_bytes(*texts))

    response = prepare_prompt(context)

    source = response['sources'][0]
    assert source['status'] == 'partial'
    assert source['fragments'][0]['text'].startswith(prefix)
    assert excluded not in response['prompt']
    assert response['complete'] is False


def test_authoring_prompt_reports_a_missing_signed_pdf(context):
    """Report an unreadable authoring source when its signed PDF is missing."""
    evidence = attest(context, AGREEMENT_PDF)
    evidence.file.storage.delete(evidence.file.name)

    response = prepare_prompt(context)

    assert response['sources'][0]['status'] == 'unreadable'
    assert response['sources'][0]['fragments'] == []
    assert response['complete'] is False


@pytest.fixture
def proposal_contract(context):
    """Provide a historical commercial contract with its original PDF."""
    proposal = BusinessProposal.objects.create(title='Acuerdo comercial', client_name='Cliente titular')
    ProjectPhase.objects.create(project=context.project, business_proposal=proposal, order=1)
    source = ProposalDocument.objects.create(
        proposal=proposal, title='PDF comercial acordado', document_type='contract',
        file=ContentFile(AGREEMENT_PDF, name='commercial.pdf'),
    )
    return ProjectContract.objects.create(
        project=context.project, key='commercial-contract', title='Contrato comercial',
        proposal_document=source, client_visible=True,
    )


def test_client_reads_the_uploaded_proposal_contract_before_publication(context, proposal_contract):
    """Let the client read the original proposal contract before publication."""
    body, title = documents.contract_pdf(context.project.pk, context.client, 'contracts', proposal_contract.pk)

    assert body == AGREEMENT_PDF
    assert title == 'Contrato comercial'
    assert not context.stage.publications.exists()


def test_proposal_contract_reports_a_missing_original_pdf(context, proposal_contract):
    """Reject an original proposal contract whose PDF is missing."""
    source = proposal_contract.proposal_document
    source.file.storage.delete(source.file.name)

    with pytest.raises(ValidationError) as rejected:
        documents.contract_pdf(context.project.pk, context.client, 'contracts', proposal_contract.pk)

    assert rejected.value.detail['code'] == 'pdf_unavailable'


def test_proposal_contract_download_enforces_the_document_size_limit(context, proposal_contract):
    """Reject a proposal contract download that exceeds the PDF size limit."""
    source = proposal_contract.proposal_document
    source.file.save('large-commercial.pdf', ContentFile(AGREEMENT_PDF + b'\n%' + b'x' * documents.MAX_PDF_BYTES), save=True)

    with pytest.raises(ValidationError) as rejected:
        documents.contract_pdf(context.project.pk, context.client, 'contracts', proposal_contract.pk)

    assert rejected.value.detail['code'] == 'pdf_too_large'


def test_document_catalog_excludes_sources_outside_the_contractual_context(context, proposal_contract, django_user_model):
    """Only this client's editorial sources belong in the contractual picker."""
    client_source = guide_document(context, project=None)
    project_source = guide_document(context, client_user=None)
    other_client = django_user_model.objects.create_user('other-document-owner')
    other_project = Project.objects.create(name='Proyecto ajeno', client=other_client)
    guide_document(context, project=other_project, client_user=other_client)
    guide_document(context, client_user=other_client)
    guide_document(context, is_archived=True)
    financial_type, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Cuenta de cobro'})
    guide_document(context, document_type=financial_type)

    response = documents.document_options(context.project.pk, context.admin)

    assert {item['id'] for item in response['documents']} == {context.document.pk, client_source.pk, project_source.pk}
    assert response['proposal_documents'] == [{
        'id': proposal_contract.proposal_document_id, 'title': 'PDF comercial acordado', 'document_type': 'contract',
    }]


def test_client_cannot_read_the_administrative_document_catalog(context):
    """Deny client access to the administrative document catalog."""
    with pytest.raises(PermissionDenied):
        documents.document_options(context.project.pk, context.client)


def test_approved_guide_document_keeps_its_copy_in_the_next_round(context):
    """Reopening another requirement must preserve the document already approved."""
    source = guide_document(context)
    link_id = attach(context, source, level='requirement', target_id=context.first.pk)
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    source.title = 'Redacción documental posterior'
    source.generated_file.save('later.pdf', ContentFile(pdf_bytes('Not the document the client approved.')), save=True)

    publish(context, 'reopen-with-approved-document')

    snapshot = DeliveryDocumentSnapshot.objects.filter(link_id=link_id).order_by('-publication__round').first()
    with snapshot.file.open('rb') as captured:
        assert captured.read() == AGREEMENT_PDF
    assert snapshot.title == 'Guía documental acordada'


def test_document_read_reports_a_missing_editorial_pdf(context):
    """Reject an editorial document whose generated PDF is missing."""
    source = guide_document(context)
    link_id = attach(context, source)
    source.generated_file.storage.delete(source.generated_file.name)

    with pytest.raises(ValidationError) as rejected:
        documents.document_pdf(context.project.pk, context.admin, link_id)

    assert rejected.value.detail['code'] == 'pdf_unavailable'


def test_document_read_reports_a_missing_published_pdf(context):
    """Reject a published document whose captured PDF is missing."""
    source = guide_document(context)
    link_id = attach(context, source)
    publish(context)
    snapshot = DeliveryDocumentSnapshot.objects.get(link_id=link_id)
    snapshot.file.storage.delete(snapshot.file.name)

    with pytest.raises(ValidationError) as rejected:
        documents.document_pdf(context.project.pk, context.client, link_id)

    assert rejected.value.detail['code'] == 'pdf_unavailable'


def test_contract_read_reports_a_missing_signature_pdf(context):
    """Reject a missing signed contract PDF without altering retained evidence."""
    evidence = attest(context, AGREEMENT_PDF)
    expected_version = version(context)
    expected_evidence = (evidence.file.name, evidence.sha256, evidence.source_snapshot)
    evidence.file.storage.delete(evidence.file.name)

    with pytest.raises(ValidationError) as rejected:
        documents.contract_pdf(context.project.pk, context.client, 'contracts', context.contract.pk)

    assert rejected.value.detail['code'] == 'contract_source_unavailable'
    evidence.refresh_from_db()
    assert (evidence.file.name, evidence.sha256, evidence.source_snapshot) == expected_evidence
    assert version(context) == expected_version
    assert not evidence.file.storage.exists(evidence.file.name)
    with context.document.generated_file.open('rb') as original:
        assert original.read() == AGREEMENT_PDF


def test_document_filter_requires_the_target_level_identifier(context):
    """Require the target identifier when filtering documents by delivery level."""
    with pytest.raises(ValidationError, match='elemento'):
        documents.list_documents(context.project.pk, context.admin, level='scope')
