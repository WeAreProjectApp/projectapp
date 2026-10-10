"""Safety boundaries for immutable signatures and review-document evidence."""
import hashlib

import pytest
from accounts.models import ContractSignatureEvidence, Project, RequirementReview
from accounts.tests.delivery_helpers import RECORDED_AT
from django.core.files.base import ContentFile

from content.models import McpActionIntent, McpUpload
from content.tests.views.test_mcp_delivery import (
    SIGNED_PDF,
    confirm,
    current_version,
    historical_arguments,
    sign_contract,
)
from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects,
)
from content.tests.views.test_mcp_delivery import (
    draft as draft,
)
from content.tests.views.test_mcp_delivery import (
    published as published,
)

pytestmark = pytest.mark.django_db


def test_mcp_signature_read_omits_internal_network_evidence(call_projects, draft, superuser):
    ContractSignatureEvidence.objects.create(
        contract=draft.contract, file=ContentFile(SIGNED_PDF, name='portal.pdf'),
        sha256=hashlib.sha256(SIGNED_PDF).hexdigest(), method='portal',
        source_sha256='a' * 64, signer_name='Cliente titular', signed_at=RECORDED_AT,
        attestation='Aceptación registrada en Platform.', attested_by=superuser,
        source_snapshot={'signature_ip': '192.0.2.1', 'signature_user_agent': 'private-browser'},
    )

    result = call_projects('get_delivery_contract', {
        'project_id': draft.project.pk, 'node_id': draft.contract.pk,
    })

    evidence = result['node']['signature_evidence'][0]
    assert evidence['method'] == 'portal'
    assert evidence['source_sha256'] == 'a' * 64
    assert 'source_snapshot' not in evidence


def test_mcp_cannot_rewrite_a_signed_contract_before_publication(call_projects, draft, superuser):
    """Reject a confirmed rewrite while preserving the signed contract evidence."""
    evidence = sign_contract(draft, superuser)
    signed_file_name = evidence.file.name
    contract_version = draft.contract.version
    workspace_version = current_version(call_projects, draft.project)

    error = confirm(call_projects, 'update_delivery_contract', {
        'project_id': draft.project.pk, 'node_id': draft.contract.pk,
        'expected_version': workspace_version,
        'title': 'Contrato reemplazado',
    }, expect_error=True)

    draft.contract.refresh_from_db()
    evidence.refresh_from_db()
    assert error['code'] == 'SIGNED_SOURCE_FROZEN'
    assert draft.contract.title == 'Contrato original'
    assert (
        draft.contract.key, draft.contract.version, draft.contract.document_id,
        draft.contract.proposal_document_id, draft.contract.approval_file_id,
    ) == ('contract', contract_version, draft.document.pk, None, None)
    assert current_version(call_projects, draft.project) == workspace_version
    assert (evidence.contract_id, evidence.sha256, evidence.file.name) == (
        draft.contract.pk, hashlib.sha256(SIGNED_PDF).hexdigest(), signed_file_name,
    )
    with evidence.file.open('rb') as signed_file:
        assert signed_file.read() == SIGNED_PDF


def test_mcp_external_attestation_cannot_claim_a_portal_signature(call_projects, draft):
    error = call_projects('attest_external_delivery_signature', {
        'project_id': draft.project.pk, 'kind': 'contracts', 'node_id': draft.contract.pk,
        'expected_version': current_version(call_projects, draft.project), 'request_id': 'fake-portal',
        'asset_id': '00000000-0000-0000-0000-000000000001',
        'signer_name': 'Cliente titular', 'signed_at': '2026-09-30T09:00:00Z',
        'attestation': 'PDF externo', 'method': 'portal',
    }, expect_error=True)

    assert error['code'] == 'unknown_field'
    assert 'method' in {row['field'] for row in error['details']['errors']}
    assert not McpActionIntent.objects.filter(tool_name='attest_external_delivery_signature').exists()


@pytest.fixture
def review_evidence(call_projects, published):
    confirm(call_projects, 'record_external_delivery_approval',
            historical_arguments(call_projects, published, 'immutable-review-document'))
    review = RequirementReview.objects.get(requirement=published.requirement)
    return review.document_evidence.get()


def test_mcp_download_preserves_the_review_document_after_source_rewrite(call_projects, published, review_evidence):
    original_title = published.document.title
    published.document.title = 'Documento editorial reemplazado'
    published.document.generated_file.save('changed.pdf', ContentFile(SIGNED_PDF + b'\n% changed source'), save=True)

    result = call_projects('download_delivery_document_pdf', {
        'project_id': published.project.pk, 'review_id': review_evidence.review_id,
        'evidence_id': review_evidence.pk,
    })

    artifact = McpUpload.objects.get(pk=result['asset_id'])
    with artifact.file.open('rb') as file:
        assert file.read() == SIGNED_PDF
    assert result['title'] == original_title
    assert 'file' not in result


def test_mcp_review_document_download_rejects_a_different_project(call_projects, published, review_evidence):
    other = Project.objects.create(name='Otro proyecto del cliente', client=published.client)

    error = call_projects('download_delivery_document_pdf', {
        'project_id': other.pk, 'review_id': review_evidence.review_id,
        'evidence_id': review_evidence.pk,
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'
    assert not McpUpload.objects.exists()


@pytest.mark.parametrize('source', [
    {}, {'review_id': 1}, {'evidence_id': 1},
    {'link_id': 1, 'review_id': 1, 'evidence_id': 1},
])
def test_mcp_document_download_rejects_an_ambiguous_source(call_projects, draft, source):
    error = call_projects('download_delivery_document_pdf', {
        'project_id': draft.project.pk, **source,
    }, expect_error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert not McpUpload.objects.exists()
