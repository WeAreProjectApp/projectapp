"""Observable MCP approval behavior through credential-bound confirmations."""
from datetime import timedelta
import hashlib
import io
from uuid import uuid4
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.models import Project
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.proposal_approval_tools import PREVIEW_TOOL
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import store_artifact
from content.models import McpConnector, McpCredential, McpUpload, ProposalApprovalFile

pytestmark = pytest.mark.django_db


def rpc(client, token, name, arguments):
    return client.post(f'/api/mcp/proposals/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, format='json').data['result']


@pytest.fixture
def access():
    connector, _ = McpConnector.objects.get_or_create(slug='proposals')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return token, connector.credential_for_token(token)


@pytest.fixture
def assets(access):
    _, credential = access
    return [store_artifact(
        connector=credential.connector, credential=credential,
        filename=filename, content_type='application/pdf', content=content, request=None,
    )['asset_id'] for filename, content in (
        ('signed-contract.pdf', b'%PDF-1.4 signed contract'),
        ('signed-amendment.pdf', b'%PDF-1.4 signed amendment'),
    )]


@pytest.fixture
def approval_arguments(api_client, access, proposal, assets, monkeypatch):
    # Replace PDF rendering only; validation, linking and packet persistence stay real.
    monkeypatch.setattr('content.services.proposal_formalization_service.document_bytes',
                        lambda proposal, kind, **kwargs: b'%PDF-1.4 ' + kind.encode())
    token, _ = access
    preview = rpc(api_client, token, 'get_proposal_approval', {'proposal_id': proposal.pk})
    return {
        'proposal_id': proposal.pk, 'action': 'confirm',
        'source_hash': preview['structuredContent']['source_hash'], 'request_id': str(uuid4()),
        'new_client': {'name': 'Approval client', 'email': 'approval@example.com'},
        'new_project': {'name': 'Explicit project'}, 'use_proposal_contracts': False,
        'custom_asset_ids': assets,
        'custom_documents': [
            {'title': 'Signed contract', 'document_type': 'contract'},
            {'title': 'Signed amendment', 'document_type': 'amendment'},
        ],
    }


def confirm(client, token, preview):
    return rpc(client, token, 'confirm_action', {
        'confirmation_id': preview['structuredContent']['confirmation_id'],
    })


def test_review_preview_keeps_project_uncreated(api_client, access, proposal, approval_arguments):
    token, _ = access

    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)

    proposal.refresh_from_db()
    assert preview['structuredContent']['confirmation_required'] is True
    assert proposal.status == 'draft'
    assert proposal.deliverable_id is None
    assert Project.objects.count() == 0
    assert ProposalApprovalFile.objects.count() == 0


def test_custom_confirmation_preserves_exact_asset_contents(api_client, access, proposal, approval_arguments):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)

    result = confirm(api_client, token, preview)

    proposal.refresh_from_db()
    assert result['isError'] is False
    assert proposal.status == 'accepted'
    assert Project.objects.count() == 1
    assert list(proposal.approval_files.values_list('source_key', flat=True)) == [
        'custom-0', 'custom-1', 'commercial', 'technical',
    ]
    assert list(proposal.approval_files.filter(source_key__startswith='custom-').values_list('sha256', flat=True)) == [
        hashlib.sha256(b'%PDF-1.4 signed contract').hexdigest(),
        hashlib.sha256(b'%PDF-1.4 signed amendment').hexdigest(),
    ]


def test_repeat_confirmation_reuses_link(api_client, access, proposal, approval_arguments):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    confirm(api_client, token, preview)
    proposal.refresh_from_db()
    original_link = proposal.deliverable_id

    result = confirm(api_client, token, preview)

    proposal.refresh_from_db()
    assert result['structuredContent']['replayed'] is True
    assert proposal.deliverable_id == original_link
    assert Project.objects.count() == 1
    assert proposal.approval_files.count() == 4


def test_tampered_asset_blocks_confirmation(api_client, access, proposal, approval_arguments, assets):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    upload = McpUpload.objects.get(pk=assets[0])
    upload.file.save(upload.filename, ContentFile(b'%PDF-1.4 changed after preview'), save=True)

    result = confirm(api_client, token, preview)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'ATTACHMENT_CHANGED'
    assert Project.objects.count() == 0
    assert ProposalApprovalFile.objects.count() == 0


def test_expired_asset_blocks_confirmation(api_client, access, approval_arguments, assets):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    McpUpload.objects.filter(pk=assets[0]).update(expires_at=timezone.now() - timedelta(seconds=1))

    result = confirm(api_client, token, preview)

    assert result['isError'] is True
    assert Project.objects.count() == 0
    assert ProposalApprovalFile.objects.count() == 0


def test_changed_proposal_blocks_confirmation(api_client, access, proposal, approval_arguments):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    proposal.title = 'Concurrent edit'
    proposal.save(update_fields=['title'])

    result = confirm(api_client, token, preview)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert Project.objects.count() == 0


def test_other_credential_cannot_confirm_packet(api_client, access, approval_arguments):
    token, credential = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    other = McpCredential.objects.create(connector=credential.connector, label='Other',
                                        token_hash=McpCredential.hash_token('other-token'))
    other_token = other.generate_token()

    result = confirm(api_client, other_token, preview)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'FORBIDDEN'
    assert Project.objects.count() == 0


def test_defer_accepts_without_link(api_client, access, proposal):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', {
        'proposal_id': proposal.pk, 'action': 'defer',
    })

    result = confirm(api_client, token, preview)

    proposal.refresh_from_db()
    assert result['isError'] is False
    assert proposal.status == 'accepted'
    assert proposal.deliverable_id is None
    assert proposal.project_review_required is True
    assert Project.objects.count() == 0


def test_status_accepted_requires_review(api_client, access, proposal):
    token, _ = access
    preview = rpc(api_client, token, 'update_proposal_status', {'proposal_id': proposal.pk, 'status': 'accepted'})

    result = confirm(api_client, token, preview)

    proposal.refresh_from_db()
    assert result['isError'] is False
    assert proposal.status == 'accepted'
    assert proposal.deliverable_id is None
    assert Project.objects.count() == 0


@pytest.mark.parametrize('arguments', [{}, {'force': True}])
def test_implicit_launch_is_rejected(api_client, access, proposal, arguments):
    token, _ = access

    result = rpc(api_client, token, 'launch_proposal_to_platform', {'proposal_id': proposal.pk, **arguments})

    assert result['isError'] is True
    assert Project.objects.count() == 0


def test_private_storage_urls_are_absent(api_client, access, proposal, approval_arguments):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    confirm(api_client, token, preview)

    result = rpc(api_client, token, 'get_proposal_approval', {'proposal_id': proposal.pk})

    assert result['isError'] is False
    assert 'download_url' not in result['structuredContent']['confirmed_files'][0]
    assert 'file' not in result['structuredContent']['confirmed_files'][0]


def test_authorized_download_returns_exact_file(api_client, access, proposal, approval_arguments):
    token, credential = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    confirm(api_client, token, preview)
    packet_file = proposal.approval_files.get(source_key='custom-0')

    result = rpc(api_client, token, 'download_proposal_approval_file', {
        'proposal_id': proposal.pk, 'file_id': packet_file.pk,
    })

    assert result['isError'] is False
    artifact = McpUpload.objects.get(pk=result['structuredContent']['asset_id'], credential=credential)
    with artifact.file.open('rb') as source:
        assert source.read() == b'%PDF-1.4 signed contract'
    assert artifact.expected_sha256 == packet_file.sha256


def test_retry_reuses_same_packet(api_client, access, proposal, approval_arguments):
    token, _ = access
    preview = rpc(api_client, token, 'review_proposal_approval', approval_arguments)
    confirm(api_client, token, preview)
    proposal.refresh_from_db()
    original_link = proposal.deliverable_id
    retry = rpc(api_client, token, 'launch_proposal_to_platform', {'proposal_id': proposal.pk, 'action': 'retry'})

    result = confirm(api_client, token, retry)

    proposal.refresh_from_db()
    assert result['isError'] is False
    assert proposal.deliverable_id == original_link
    assert proposal.approval_files.count() == 4
    assert Project.objects.count() == 1


def test_nonadmin_cannot_read_approval(access, proposal):
    _, credential = access
    actor = get_user_model().objects.create_user(username='unprivileged', is_staff=False)
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='denied', actor=actor)

    with use_mcp_context(context), pytest.raises(ToolError):
        PREVIEW_TOOL['handler']({'proposal_id': proposal.pk})


@pytest.mark.parametrize(('filename', 'content_type', 'content'), [
    ('agreement.doc', 'application/msword', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1office'),
    ('appendix.xls', 'application/vnd.ms-excel', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1sheet'),
])
def test_office_asset_can_be_previewed(api_client, access, approval_arguments, filename, content_type, content):
    token, credential = access
    asset = store_artifact(connector=credential.connector, credential=credential,
                           filename=filename, content_type=content_type,
                           content=content, request=None)['asset_id']
    approval_arguments['custom_asset_ids'][0] = asset

    result = rpc(api_client, token, 'review_proposal_approval', approval_arguments)

    assert result['isError'] is False
    assert result['structuredContent']['impact']['custom_assets'][0]['filename'] == filename
    assert Project.objects.count() == 0


def test_xlsx_asset_can_be_previewed(api_client, access, approval_arguments):
    token, credential = access
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('xl/workbook.xml', '<workbook/>')
    asset = store_artifact(connector=credential.connector, credential=credential,
                           filename='appendix.xlsx',
                           content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                           content=buffer.getvalue(), request=None)['asset_id']
    approval_arguments['custom_asset_ids'][0] = asset

    result = rpc(api_client, token, 'review_proposal_approval', approval_arguments)

    assert result['isError'] is False
    assert result['structuredContent']['impact']['custom_assets'][0]['filename'] == 'appendix.xlsx'


def test_invalid_xlsx_asset_is_rejected(api_client, access, approval_arguments):
    token, credential = access
    asset = store_artifact(connector=credential.connector, credential=credential,
                           filename='forged.xlsx',
                           content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                           content=b'PK not an Excel workbook', request=None)['asset_id']
    approval_arguments['custom_asset_ids'][0] = asset

    result = rpc(api_client, token, 'review_proposal_approval', approval_arguments)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'INVALID_FILE_CONTENT'
    assert Project.objects.count() == 0
