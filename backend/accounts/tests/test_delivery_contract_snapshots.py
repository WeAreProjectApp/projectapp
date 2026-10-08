"""Published contractual sources preserve signatures without replacing annexes."""
import hashlib
from pathlib import Path

import pytest
from content.models import Document
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from accounts.models import DeliveryDocumentLink, DeliveryDocumentSnapshot, Requirement
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_documents import ensure_portal_signature_capture
from accounts.tests.delivery_authoring_helpers import pdf_bytes, signed_amendment
from accounts.tests.delivery_helpers import (
    build_delivery_context,
    decisions,
    publish,
    version,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    """Build the isolated delivery project used by snapshot regressions."""
    return build_delivery_context()


def portal_proof(context, node=None):
    """Retain the actual portal signature for the selected contractual node."""
    node = node or context.contract
    ensure_portal_signature_capture(node, context.client)
    return node.signature_evidence.get()


def external_proof(context):
    """Register the externally signed PDF through the delivery service."""
    signed = pdf_bytes('The signed agreement includes record validation.')
    delivery.attest_signature(context.project.pk, context.admin, 'contracts', context.contract.pk, {
        'expected_version': version(context), 'request_id': 'external-source-proof',
        'signer_name': 'Client', 'signed_at': '2026-09-30T12:00:00Z',
        'attestation': 'Verified signed original received externally.',
    }, SimpleUploadedFile('signed.pdf', signed, content_type='application/pdf'))
    DeliveryDocumentLink.objects.get_or_create(
        project=context.project, document=context.document, level='contract', contract=context.contract,
        defaults={'created_by': context.admin},
    )
    return context.contract.signature_evidence.get()


def source_link(context, node=None):
    """Resolve the canonical document link for the contract or amendment."""
    node = node or context.contract
    level = 'contract' if node is context.contract else 'amendment'
    return DeliveryDocumentLink.objects.get(project=context.project, document_id=node.document_id,
                                            level=level, **{level: node})


@pytest.mark.parametrize('proof_factory', [portal_proof, external_proof])
def test_published_source_matches_the_signed_contract(context, proof_factory):
    """Published contractual bytes come from the signature, not the live draft."""
    proof = proof_factory(context)
    link = source_link(context)
    context.document.content_markdown = '# Editable text the client did not sign'
    context.document.save(update_fields=['content_markdown'])

    publish(context)

    snapshot = DeliveryDocumentSnapshot.objects.get(link=link)
    assert snapshot.sha256 == proof.sha256
    pdf, _ = delivery.document_pdf(context.project.pk, context.client, link.pk)
    assert hashlib.sha256(pdf).hexdigest() == proof.sha256


def test_another_stage_uses_the_same_signed_source(context):
    """Another stage snapshots the same signed source after a live edit."""
    proof = portal_proof(context)
    publish(context)
    from accounts.models import DeliveryStage
    stage = DeliveryStage.objects.create(phase=context.phase, key='second', title='Second stage')
    Requirement.objects.create(stage=stage, key='new-case', title='Validate next case', guide=context.first.guide)
    context.document.content_markdown = '# Different administrative draft'
    context.document.save(update_fields=['content_markdown'])

    delivery.publish_stage(context.project.pk, context.admin, stage.pk, {
        'expected_version': version(context), 'request_id': 'publish-second-stage',
    })

    snapshots = DeliveryDocumentSnapshot.objects.filter(link=source_link(context))
    assert snapshots.count() == 2
    assert set(snapshots.values_list('sha256', flat=True)) == {proof.sha256}


def test_new_round_keeps_the_signed_source_hash(context):
    """Republication preserves the signed source after administrative edits."""
    proof = portal_proof(context)
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'objected')))
    context.document.content_markdown = '# Administrative changes after the first round'
    context.document.save(update_fields=['content_markdown'])

    publish(context, request_id='publish-second-round')

    snapshots = DeliveryDocumentSnapshot.objects.filter(link=source_link(context))
    assert snapshots.count() == 2
    assert set(snapshots.values_list('sha256', flat=True)) == {proof.sha256}


def test_amendment_source_uses_its_own_signed_pdf(context):
    """The amendment snapshot comes from its own retained signature."""
    amendment = signed_amendment(context)
    proof = portal_proof(context, amendment)
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])
    amendment.document.generated_file.save('edited-amendment.pdf', ContentFile(pdf_bytes('Unsigned amendment changes.')), save=True)

    publish(context)

    snapshot = DeliveryDocumentSnapshot.objects.get(link=source_link(context, amendment))
    assert snapshot.sha256 == proof.sha256


def test_independent_contract_annex_keeps_its_own_pdf(context):
    """An independent annex is not replaced by the contract signature."""
    proof = portal_proof(context)
    raw = pdf_bytes('A separate reference annex, not the signed contract.')
    document = Document.objects.create(project=context.project, client_user=context.client,
                                       title='Separate annex', generated_file=ContentFile(raw, name='annex.pdf'))
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'contract', 'target_id': context.contract.pk,
        'document_id': document.pk,
    })

    publish(context)

    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=document)
    assert snapshot.sha256 == hashlib.sha256(raw).hexdigest()
    assert snapshot.sha256 != proof.sha256


def test_approved_requirement_keeps_its_first_round_attachment(context):
    """The document approved by the client stays frozen in a later round."""
    raw = pdf_bytes('The exact guide document the client approved.')
    document = Document.objects.create(project=context.project, client_user=context.client,
                                       title='Approved guide attachment', generated_file=ContentFile(raw, name='guide.pdf'))
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'requirement', 'target_id': context.first.pk,
        'document_id': document.pk,
    })
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    document.generated_file.save('revised-guide.pdf', ContentFile(pdf_bytes('Later guide changes.')), save=True)

    publish(context, request_id='publish-pending-again')

    snapshots = DeliveryDocumentSnapshot.objects.filter(link__document=document)
    assert snapshots.count() == 2
    assert set(snapshots.values_list('sha256', flat=True)) == {hashlib.sha256(raw).hexdigest()}


def test_corrupt_contract_proof_rolls_back_the_whole_publication(context):
    """A corrupt signature cannot leave partial publication state or files."""
    annex = Document.objects.create(project=context.project, client_user=context.client,
                                     title='First captured annex', generated_file=ContentFile(pdf_bytes('Annex.'), name='annex.pdf'))
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'contract', 'target_id': context.contract.pk,
        'document_id': annex.pk,
    })
    proof = portal_proof(context)
    with proof.file.open('wb') as stream:
        stream.write(pdf_bytes('Tampered signature evidence.'))
    expected_version = version(context)
    snapshot_root = Path(settings.PRIVATE_MEDIA_ROOT) / 'delivery' / 'snapshots'
    before = set(snapshot_root.rglob('*.pdf'))

    with pytest.raises(ValidationError, match='huella conservada'):
        publish(context)

    context.stage.refresh_from_db()
    context.first.refresh_from_db()
    assert context.stage.editorial_status == 'draft'
    assert context.first.review_status == 'pending'
    assert not context.stage.publications.exists()
    assert not DeliveryDocumentSnapshot.objects.filter(publication__stage=context.stage).exists()
    assert version(context) == expected_version
    assert set(snapshot_root.rglob('*.pdf')) == before


def test_missing_signed_copy_does_not_use_live_document_text(context):
    """A missing signed copy cannot be reconstructed from editable text."""
    proof = portal_proof(context)
    proof.file.storage.delete(proof.file.name)
    context.document.content_markdown = '# Live text cannot reconstruct the missing signature'
    context.document.save(update_fields=['content_markdown'])

    with pytest.raises(ValidationError, match='no está disponible'):
        publish(context)

    assert not context.stage.publications.exists()


def test_corrupt_approved_attachment_cannot_be_recaptured(context):
    """A corrupt approved snapshot cannot become a new publication."""
    raw = pdf_bytes('The guide document actually approved by the client.')
    document = Document.objects.create(project=context.project, client_user=context.client,
                                       title='Approved attachment', generated_file=ContentFile(raw, name='guide.pdf'))
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'requirement', 'target_id': context.first.pk,
        'document_id': document.pk,
    })
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=document)
    with snapshot.file.open('wb') as stream:
        stream.write(pdf_bytes('A tampered approved copy.'))
    expected_version = version(context)
    snapshot_root = Path(settings.PRIVATE_MEDIA_ROOT) / 'delivery' / 'snapshots'
    before = set(snapshot_root.rglob('*.pdf'))

    with pytest.raises(ValidationError, match='huella conservada'):
        publish(context, request_id='second-round-invalid-evidence')

    assert context.stage.publications.count() == 1
    assert DeliveryDocumentSnapshot.objects.filter(link__document=document).count() == 1
    assert version(context) == expected_version
    assert set(snapshot_root.rglob('*.pdf')) == before
