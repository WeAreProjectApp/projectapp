"""Credential-bound MCP operations use the same approved document identities."""
import hashlib

import pytest

from content.mcp.upload_tools import store_artifact
from content.models import McpActionIntent, McpConnector
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
