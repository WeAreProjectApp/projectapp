"""Credential-bound MCP operations use the same approved document identities."""
import hashlib

import pytest
from django.core.files.base import ContentFile

from content.mcp.upload_tools import store_artifact
from content.models import McpActionIntent, McpConnector, ProposalApprovalFile, ProposalDocument
from content.services.proposal_approval_service import load_proposal, source_hash
from content.tests.views.test_proposal_shared_documents import (
    confirmed_proposal, approval_client, reviewed_proposal,
)
from content.tests.views.test_mcp_proposal_approval import access, rpc, confirm

pytestmark = pytest.mark.django_db


@pytest.fixture
def document_access():
    connector, _ = McpConnector.objects.get_or_create(slug='documents')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return token, connector.credential_for_token(token)


def document_rpc(client, token, name, arguments):
    return client.post(f'/api/mcp/documents/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, format='json').data['result']


@pytest.fixture
def missing_annex_identity(reviewed_proposal, approval_client, admin_user):
    annex = ProposalDocument.objects.create(
        proposal=reviewed_proposal, document_type='legal_annex', title='MCP annex',
    )
    annex.file.save('mcp-annex.pdf', ContentFile(b'%PDF-1.4 mcp annex'))
    from content.tests.views.test_proposal_approval import confirm as confirm_proposal
    confirm_proposal(reviewed_proposal, approval_client, admin_user)
    proposal = load_proposal(reviewed_proposal.pk)
    binding = proposal.document_bindings.get(source_key=f'original-{annex.pk}')
    approved = binding.current_file
    document = binding.document
    details = (proposal, annex, approved.pk, approved.sha256, approved.file.read())
    ProposalApprovalFile.objects.filter(pk=approved.pk).update(binding=None)
    binding.delete()
    document.delete()
    return details


def test_document_connector_reads_the_shared_approved_identity(api_client, document_access, confirmed_proposal):
    token, _ = document_access
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')

    result = document_rpc(api_client, token, 'get_document_proposal_source', {'document_id': binding.document_id})

    assert result['isError'] is False
    assert result['structuredContent']['document']['document_id'] == binding.document_id
    assert result['structuredContent']['document']['current_file_id'] == binding.current_file_id
    assert confirmed_proposal.approval_packages.count() == 1


def test_binary_confirmation_preserves_the_approved_revision(api_client, document_access, confirmed_proposal):
    token, credential = document_access
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')
    approved_id = binding.current_file_id
    content = b'%PDF-1.4 revised through MCP'
    asset = store_artifact(connector=credential.connector, credential=credential,
        filename='new-contract.pdf', content_type='application/pdf', content=content, request=None)
    preview = document_rpc(api_client, token, 'replace_document_proposal_binary', {
        'document_id': binding.document_id, 'source_hash': source_hash(confirmed_proposal),
        'source_asset_id': asset['asset_id'],
    })

    result = document_rpc(api_client, token, 'confirm_action', {
        'confirmation_id': preview['structuredContent']['confirmation_id'],
    })

    binding.refresh_from_db()
    assert result['isError'] is False
    assert binding.current_file_id == approved_id
    assert binding.draft_sha256 == hashlib.sha256(content).hexdigest()
    assert result['structuredContent']['result']['document']['has_pending_changes'] is True


def test_binary_preview_requires_a_completed_upload(api_client, document_access, confirmed_proposal):
    token, _ = document_access
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')

    result = document_rpc(api_client, token, 'replace_document_proposal_binary', {
        'document_id': binding.document_id, 'source_hash': source_hash(confirmed_proposal),
    })

    assert result['isError'] is True
    assert 'source_asset_id' in str(result['structuredContent']['error'])
    assert McpActionIntent.objects.count() == 0


def test_revision_confirmation_retains_previous_contract_evidence(api_client, access, confirmed_proposal):
    token, _ = access
    binding = confirmed_proposal.document_bindings.get(source_key='custom-contract')
    approved = binding.current_file
    preview = rpc(api_client, token, 'confirm_proposal_document_revision', {
        'proposal_id': confirmed_proposal.pk, 'request_id': 'mcp-shared-revision',
        'source_hash': source_hash(load_proposal(confirmed_proposal.pk)),
    })

    result = confirm(api_client, token, preview)

    approved.refresh_from_db()
    assert result['isError'] is False
    assert result['structuredContent']['result']['confirmed_package'] == 2
    assert approved.package.number == 1
    assert approved.binding.document_id == binding.document_id
    assert confirmed_proposal.approval_packages.count() == 2


def test_document_mcp_reconciliation_requires_confirmation(
    api_client, document_access, missing_annex_identity,
):
    """Fails if the Documents MCP restores a missing identity before confirmation."""
    proposal, annex, approved_id, _approved_hash, _approved_bytes = missing_annex_identity
    token, _ = document_access

    preview = document_rpc(
        api_client, token, 'preview_proposal_document_reconciliation',
        {'proposal_id': proposal.pk},
    )
    expected_hash = preview['structuredContent']['expected_hash']
    prepared = document_rpc(
        api_client, token, 'reconcile_proposal_documents',
        {'proposal_id': proposal.pk, 'expected_hash': expected_hash},
    )

    assert preview['isError'] is False
    assert preview['structuredContent']['missing_documents'][0]['file_id'] == approved_id
    assert proposal.document_bindings.filter(source_key=f'original-{annex.pk}').count() == 0
    assert prepared['isError'] is False
    assert 'confirmation_id' in prepared['structuredContent']
    assert proposal.document_bindings.filter(source_key=f'original-{annex.pk}').count() == 0


def test_document_mcp_confirmation_restores_the_exact_approved_annex(
    api_client, document_access, missing_annex_identity,
):
    """Fails if confirmed MCP repair replaces an approved annex's immutable identity."""
    proposal, annex, approved_id, approved_hash, approved_bytes = missing_annex_identity
    token, _ = document_access
    preview = document_rpc(
        api_client, token, 'preview_proposal_document_reconciliation',
        {'proposal_id': proposal.pk},
    )
    prepared = document_rpc(
        api_client, token, 'reconcile_proposal_documents',
        {'proposal_id': proposal.pk, 'expected_hash': preview['structuredContent']['expected_hash']},
    )

    confirmed = document_rpc(
        api_client, token, 'confirm_action',
        {'confirmation_id': prepared['structuredContent']['confirmation_id']},
    )

    restored = proposal.document_bindings.get(source_key=f'original-{annex.pk}')
    assert confirmed['isError'] is False
    assert (restored.current_file_id, restored.current_file.sha256, restored.current_file.file.read()) == (
        approved_id, approved_hash, approved_bytes,
    )
    assert proposal.approval_packages.count() == 1
