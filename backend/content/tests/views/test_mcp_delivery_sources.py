"""MCP transports exact retained sources without inferring a signature."""
import pytest
from accounts.models import ProjectContract
from accounts.tests.delivery_authoring_helpers import docx_bytes
from accounts.tests.delivery_helpers import build_delivery_context
from accounts.tests.test_delivery_approval_sources import confirmed_file, create_source

from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects,  # noqa: PLC0414
)
from content.tests.views.test_mcp_delivery import (
    draft as draft,  # noqa: PLC0414
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def source_context():
    return build_delivery_context()


def test_mcp_creates_an_unsigned_contract_from_an_approval_file(call_projects, source_context):
    source = confirmed_file(source_context)
    response = call_projects('create_delivery_contract', {'project_id': source_context.project.pk,
        'expected_version': 0, 'request_id': 'mcp-approval-source',
        'data': {'key': 'mcp-approved-source', 'title': 'Confirmed agreement', 'approval_file_id': source.pk}})
    contract = ProjectContract.objects.get(pk=response['result']['id'])
    assert contract.approval_file_id == source.pk
    assert contract.client_visible is False
    assert not contract.signature_evidence.exists()


def test_mcp_downloads_the_exact_original_docx(call_projects, source_context, api_client):
    body = docx_bytes()
    node = create_source(source_context, confirmed_file(source_context, raw=body, filename='agreement.docx'))
    artifact = call_projects('download_delivery_contract_source', {
        'project_id': source_context.project.pk, 'kind': 'contracts', 'node_id': node.pk})
    response = api_client.get(artifact['download_url'])
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == body
    assert artifact['filename'] == 'agreement.docx'
    response.close()


def test_mcp_contract_source_rejects_a_foreign_project(call_projects, source_context, draft):
    node = create_source(source_context, confirmed_file(source_context))
    error = call_projects('download_delivery_contract_source', {
        'project_id': draft.project.pk, 'kind': 'contracts', 'node_id': node.pk}, expect_error=True)
    assert error['code'] == 'NOT_FOUND'


def test_mcp_contract_source_rejects_changed_retained_bytes(call_projects, source_context):
    source = confirmed_file(source_context)
    node = create_source(source_context, source)
    with source.file.open('wb') as target:
        target.write(b'changed bytes')
    error = call_projects('download_delivery_contract_source', {
        'project_id': source_context.project.pk, 'kind': 'contracts', 'node_id': node.pk}, expect_error=True)
    assert error['code'] == 'CONTRACT_SOURCE_INTEGRITY'
