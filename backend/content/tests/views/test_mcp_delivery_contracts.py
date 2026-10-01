"""Read, permission, file and confirmation boundaries of delivery MCP tools."""
import hashlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile

from accounts.models import (
    ContractAmendment, ContractSignatureEvidence, DeliveryDocumentLink,
    DeliveryPublication, Project, ProjectContract, RequirementReview, UserProfile,
)
from accounts.tests.delivery_helpers import RECORDED_AT
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.models import (
    CommunicationMessage, CommunicationThread, McpConnector, McpCredential, McpUpload,
)
from content.tests.views.test_mcp_delivery import (
    SIGNED_PDF, call_projects as call_projects, confirm, current_version,
    draft as draft, historical_arguments, import_json, published as published,
)
from content.views.mcp_blog import TOOLS_BY_SLUG


pytestmark = pytest.mark.django_db


@pytest.fixture
def entity_ids(draft):
    amendment = ContractAmendment.objects.create(
        contract=draft.contract, key='amendment', title='Otrosí 1', document=draft.document,
    )
    return {
        'contract': draft.contract.pk, 'amendment': amendment.pk,
        'scope': draft.scope.pk, 'phase': draft.phase.pk,
        'stage': draft.stage.pk, 'requirement': draft.requirement.pk,
    }


@pytest.mark.parametrize('kind', [
    'contract', 'amendment', 'scope', 'phase', 'stage', 'requirement',
])
def test_mcp_reads_the_selected_delivery_entity(call_projects, draft, entity_ids, kind):
    result = call_projects(f'get_delivery_{kind}', {
        'project_id': draft.project.pk, 'node_id': entity_ids[kind],
    })

    assert result['node']['id'] == entity_ids[kind]


def test_mcp_detail_cannot_read_a_node_from_another_project(call_projects, draft):
    other = Project.objects.create(name='Seguimiento ajeno', client=draft.client)
    foreign = ProjectContract.objects.create(
        project=other, key='foreign', title='Contrato ajeno', document=draft.document,
    )

    error = call_projects('get_delivery_contract', {
        'project_id': draft.project.pk, 'node_id': foreign.pk,
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'


def test_administrative_handler_rejects_a_client_actor(draft):
    tool = next(tool for tool in TOOLS_BY_SLUG['projects'] if tool['name'] == 'get_delivery_overview')
    context = McpExecutionContext(
        connector=SimpleNamespace(slug='projects'), credential=None,
        request_id='read-client', actor=draft.client,
    )

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as rejected:
        tool['handler']({'project_id': draft.project.pk})

    assert rejected.value.code == 'FORBIDDEN'


def test_mcp_credential_scope_blocks_delivery_mutation(call_projects, draft):
    credential = McpCredential.objects.get(connector__slug='projects', label='Default')
    credential.allowed_tools = ['get_delivery_overview']
    credential.save(update_fields=['allowed_tools'])

    error = call_projects('create_delivery_scope', {
        'project_id': draft.project.pk, 'expected_version': 0,
        'data': {'key': 'scope-blocked', 'title': 'Alcance bloqueado', 'contract_id': draft.contract.pk},
    }, expect_error=True)

    assert error['code'] == 'FORBIDDEN'
    assert not draft.contract.scopes.filter(key='scope-blocked').exists()


def test_mcp_download_preserves_the_signed_pdf_as_a_private_artifact(call_projects, published):
    result = call_projects('download_delivery_contract_pdf', {
        'project_id': published.project.pk, 'kind': 'contracts', 'node_id': published.contract.pk,
    })

    artifact = McpUpload.objects.get(pk=result['asset_id'])
    with artifact.file.open('rb') as file:
        assert file.read() == SIGNED_PDF
    assert artifact.credential.connector.slug == 'projects'
    assert 'file' not in result


def test_mcp_pdf_download_rejects_a_foreign_document_link(call_projects, draft, superuser):
    other = Project.objects.create(name='Proyecto con documento ajeno', client=draft.client)
    link = DeliveryDocumentLink.objects.create(
        project=other, document=draft.document, level='project', created_by=superuser,
    )

    error = call_projects('download_delivery_document_pdf', {
        'project_id': draft.project.pk, 'link_id': link.pk,
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'


def test_mcp_document_unlink_removes_an_editable_association(call_projects, draft):
    linked = call_projects('link_delivery_document', {
        'project_id': draft.project.pk, 'level': 'stage', 'target_id': draft.stage.pk,
        'document_id': draft.document.pk, 'expected_version': current_version(call_projects, draft.project),
    })
    link_id = linked['result']['id']

    call_projects('unlink_delivery_document', {
        'project_id': draft.project.pk, 'link_id': link_id,
        'expected_version': current_version(call_projects, draft.project),
    })

    assert not DeliveryDocumentLink.objects.filter(pk=link_id).exists()


def test_mcp_signed_asset_is_bound_to_its_credential(call_projects, draft):
    connector = McpConnector.objects.get(slug='projects')
    foreign_credential = McpCredential.objects.create(
        connector=connector, label='Other', token_hash='a' * 64,
    )
    upload = McpUpload.objects.create(
        connector=connector, credential=foreign_credential,
        filename='signed.pdf', content_type='application/pdf',
        expected_size=len(SIGNED_PDF), received_size=len(SIGNED_PDF),
        expected_sha256=hashlib.sha256(SIGNED_PDF).hexdigest(),
        status=McpUpload.STATUS_COMPLETE, expires_at=RECORDED_AT + timedelta(days=3650),
    )
    upload.file.save('signed.pdf', ContentFile(SIGNED_PDF), save=True)

    error = confirm(call_projects, 'attest_external_delivery_signature', {
        'project_id': draft.project.pk, 'kind': 'contracts', 'node_id': draft.contract.pk,
        'expected_version': current_version(call_projects, draft.project),
        'request_id': 'foreign-pdf', 'asset_id': str(upload.pk), 'signer_name': 'Cliente titular',
        'signed_at': '2026-09-30T09:00:00Z', 'attestation': 'PDF del cliente.',
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'
    assert not ContractSignatureEvidence.objects.filter(contract=draft.contract).exists()


def test_mcp_publication_confirmation_is_replayed_without_another_round(call_projects, draft, superuser):
    from content.tests.views.test_mcp_delivery import sign_contract

    sign_contract(draft, superuser)
    preview = call_projects('publish_delivery_stage', {
        'project_id': draft.project.pk, 'stage_id': draft.stage.pk,
        'expected_version': current_version(call_projects, draft.project), 'request_id': 'one-round',
    })
    call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']})

    replay = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert replay['replayed'] is True
    assert DeliveryPublication.objects.filter(stage=draft.stage).count() == 1


def test_mcp_historical_approval_rejects_missing_external_provenance(call_projects, published):
    arguments = historical_arguments(call_projects, published, 'no-provenance')
    del arguments['evidence_document_ids']

    error = confirm(call_projects, 'record_external_delivery_approval', arguments, expect_error=True)

    assert error['code'] != 'INTERNAL_ERROR'
    assert not RequirementReview.objects.filter(requirement=published.requirement).exists()


def test_mcp_document_detail_preserves_its_delivery_level(call_projects, draft):
    linked = call_projects('link_delivery_document', {
        'project_id': draft.project.pk, 'level': 'requirement', 'target_id': draft.requirement.pk,
        'document_id': draft.document.pk, 'expected_version': current_version(call_projects, draft.project),
    })

    result = call_projects('get_delivery_document', {
        'project_id': draft.project.pk, 'link_id': linked['result']['id'],
    })

    assert result['document']['level'] == 'requirement'
    assert result['document']['target_id'] == draft.requirement.pk


def test_mcp_authoring_contract_exposes_a_structured_json_schema(call_projects, draft):
    result = call_projects('get_delivery_authoring_contract', {'project_id': draft.project.pk})

    assert result['schema']['required'] == ['schema_version', 'scopes']
    assert result['schema']['properties']['schema_version'] == {'const': 1}
    assert result['template']['scopes'][0]['contract_id'] == draft.contract.pk


def test_mcp_import_cannot_declare_approval(call_projects, draft):
    payload = import_json(draft)
    payload['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]['review_status'] = 'approved'

    error = call_projects('preview_delivery_import', {
        'project_id': draft.project.pk, 'expected_version': current_version(call_projects, draft.project),
        'payload': payload,
    }, expect_error=True)

    assert error['code'] != 'INTERNAL_ERROR'
    assert not draft.contract.scopes.filter(key='imported').exists()


def source_message(draft, *, direction, status):
    profile, _ = UserProfile.objects.get_or_create(user=draft.client, defaults={'role': 'client'})
    thread = CommunicationThread.objects.create(
        client=profile, project=draft.project, title='Validación de la etapa',
    )
    return CommunicationMessage.objects.create(
        thread=thread, channel='email', direction=direction, status=status,
        subject='Conformidad', content='Confirmo la validación de Crear registro.',
        occurred_at=RECORDED_AT,
    )


def test_mcp_historical_approval_rejects_an_outgoing_message(call_projects, published):
    outgoing = source_message(published, direction='outgoing', status='sent')
    arguments = historical_arguments(call_projects, published, 'outgoing-message')
    arguments.update({'source_message_id': outgoing.pk, 'evidence_message': outgoing.content})

    error = confirm(call_projects, 'record_external_delivery_approval', arguments, expect_error=True)

    assert error['code'] == 'CLIENT_EVIDENCE_REQUIRED'
    assert not RequirementReview.objects.filter(requirement=published.requirement).exists()


def test_mcp_historical_approval_preserves_the_incoming_source(call_projects, published):
    incoming = source_message(published, direction='incoming', status='received')
    evidence = call_projects('list_delivery_approval_evidence', {'project_id': published.project.pk})
    arguments = historical_arguments(call_projects, published, 'incoming-message')
    arguments.update({'source_message_id': evidence['messages'][0]['id'],
                      'evidence_message': incoming.content})

    confirm(call_projects, 'record_external_delivery_approval', arguments)

    review = RequirementReview.objects.get(requirement=published.requirement)
    assert review.source_message_id == incoming.pk
    assert review.reviewed_at == incoming.occurred_at
    assert review.source_snapshot['content'] == incoming.content
