"""Administrative MCP delivery actions exercise the live shared domain services."""
import base64
import hashlib
import io
from types import SimpleNamespace

import pytest
from accounts.models import (
    ContractAmendment,
    ContractSignatureEvidence,
    DeliveryDocumentLink,
    DeliveryMessage,
    DeliveryPhase,
    DeliveryPublication,
    DeliveryScope,
    DeliveryStage,
    Project,
    ProjectContract,
    Requirement,
    RequirementReview,
)
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import RECORDED_AT
from django.core.files.base import ContentFile
from pypdf import PdfWriter

from content.models import Document, DocumentType, McpConnector, McpUpload

pytestmark = pytest.mark.django_db

GUIDE = {
    'role': 'Responsable del cliente', 'environment': 'Staging',
    'preparation': 'Ingresar con la cuenta asignada.', 'data': 'Un registro de prueba.',
    'steps': ['Abrir el listado.', 'Crear un registro.'],
    'expected_result': 'El registro aparece en el listado.',
    'failure_signals': 'El registro no aparece o se muestra un error.',
}
def _signed_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


SIGNED_PDF = _signed_pdf()


@pytest.fixture
def call_projects(api_client, superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Proyectos'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()

    def call(name, arguments, *, expect_error=False):
        response = api_client.post(f'/api/mcp/projects/{token}/', {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }, format='json')
        assert response.status_code == 200, response.data
        result = response.data['result']
        assert result['isError'] is expect_error, result['content'][0]['text']
        return (result['structuredContent']['error'] if expect_error
                else result['structuredContent'])

    return call


@pytest.fixture
def draft(django_user_model, superuser):
    client = django_user_model.objects.create_user('delivery-mcp-client')
    project = Project.objects.create(name='Portal de validación', client=client)
    document_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    document = Document.objects.create(
        document_type=document_type, title='Contrato del portal',
        project=project, client_user=client, content_markdown='# Contrato\nAlcance acordado.',
        requires_signature=True, is_client_visible=True,
    )
    document.generated_file.save('contract.pdf', ContentFile(SIGNED_PDF), save=True)
    contract = ProjectContract.objects.create(
        project=project, key='contract', title='Contrato original',
        document=document, client_visible=True,
    )
    scope = DeliveryScope.objects.create(
        contract=contract, key='scope', title='Alcance aprobado',
    )
    phase = DeliveryPhase.objects.create(scope=scope, key='phase', title='Fase 1')
    stage = DeliveryStage.objects.create(phase=phase, key='stage', title='Etapa 1')
    requirement = Requirement.objects.create(
        stage=stage, key='requirement', title='Crear registro', guide=GUIDE,
    )
    return SimpleNamespace(
        project=project, client=client, document=document, contract=contract,
        scope=scope, phase=phase, stage=stage, requirement=requirement,
    )


def current_version(call, project):
    return call('get_delivery_overview', {'project_id': project.pk})['version']


def confirm(call, tool, arguments, *, expect_error=False):
    preview = call(tool, arguments)
    return call('confirm_action', {'confirmation_id': preview['confirmation_id']},
                expect_error=expect_error)


def sign_contract(draft, admin):
    return ContractSignatureEvidence.objects.create(
        contract=draft.contract, file=ContentFile(SIGNED_PDF, name='signed.pdf'),
        sha256=hashlib.sha256(SIGNED_PDF).hexdigest(), signer_name='Cliente titular',
        signed_at=RECORDED_AT, attestation='PDF firmado recibido del cliente.',
        attested_by=admin,
    )


@pytest.fixture
def published(draft, superuser):
    sign_contract(draft, superuser)
    delivery.publish_stage(draft.project.pk, superuser, draft.stage.pk, {
        'expected_version': delivery.overview(draft.project.pk, superuser)['version'],
        'request_id': 'fixture-publish',
    })
    draft.requirement.refresh_from_db()
    return draft


@pytest.mark.parametrize('kind', [
    'contract', 'amendment', 'scope', 'phase', 'stage', 'requirement',
])
def test_mcp_creates_a_node_in_the_project(call_projects, draft, kind):
    data = {
        'contract': {'document_id': draft.document.pk},
        'amendment': {'document_id': draft.document.pk, 'contract_id': draft.contract.pk},
        'scope': {'contract_id': draft.contract.pk},
        'phase': {'scope_id': draft.scope.pk},
        'stage': {'phase_id': draft.phase.pk},
        'requirement': {'stage_id': draft.stage.pk, 'guide': GUIDE},
    }[kind]
    model = {
        'contract': ProjectContract, 'amendment': ContractAmendment,
        'scope': DeliveryScope, 'phase': DeliveryPhase,
        'stage': DeliveryStage, 'requirement': Requirement,
    }[kind]

    call_projects(f'create_delivery_{kind}', {
        'project_id': draft.project.pk, 'expected_version': current_version(call_projects, draft.project),
        'key': 'new-node', 'title': 'Entrega legible', **data,
    })

    assert model.objects.get(key='new-node').title == 'Entrega legible'


def test_mcp_updates_a_pending_requirement_guide(call_projects, draft):
    call_projects('update_delivery_requirement', {
        'project_id': draft.project.pk, 'node_id': draft.requirement.pk,
        'expected_version': current_version(call_projects, draft.project),
        'guide': {**GUIDE, 'expected_result': 'Se confirma el guardado.'},
    })

    draft.requirement.refresh_from_db()
    assert draft.requirement.guide['expected_result'] == 'Se confirma el guardado.'


def test_mcp_rejects_a_stale_workspace_version(call_projects, draft):
    version = current_version(call_projects, draft.project)
    call_projects('update_delivery_requirement', {
        'project_id': draft.project.pk, 'node_id': draft.requirement.pk,
        'expected_version': version, 'title': 'Primera edición',
    })

    error = call_projects('update_delivery_requirement', {
        'project_id': draft.project.pk, 'node_id': draft.requirement.pk,
        'expected_version': version, 'title': 'Edición perdida',
    }, expect_error=True)

    draft.requirement.refresh_from_db()
    assert error['code'] == 'CONFLICT'
    assert draft.requirement.title == 'Primera edición'


def test_mcp_rejects_a_contract_from_another_project(call_projects, draft):
    other = Project.objects.create(name='Otro proyecto', client=draft.client)
    foreign = ProjectContract.objects.create(
        project=other, key='foreign', title='Contrato ajeno', document=draft.document,
    )

    error = call_projects('create_delivery_amendment', {
        'project_id': draft.project.pk, 'expected_version': current_version(call_projects, draft.project),
        'key': 'invalid', 'title': 'Otrosí inválido',
        'contract_id': foreign.pk, 'document_id': draft.document.pk,
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'
    assert not ContractAmendment.objects.filter(key='invalid').exists()


def import_json(draft):
    return {'schema_version': 1, 'scopes': [{
        'key': 'imported', 'title': 'Alcance importado', 'contract_id': draft.contract.pk,
        'phases': [{'key': 'phase', 'title': 'Primera fase',
                    'stages': [{'key': 'stage', 'title': 'Primera etapa',
                                'requirements': [{'key': 'req', 'title': 'Probar', 'guide': GUIDE}]}]}],
    }]}


def test_mcp_import_preview_keeps_the_workspace_unchanged(call_projects, draft):
    version = current_version(call_projects, draft.project)

    call_projects('preview_delivery_import', {
        'project_id': draft.project.pk, 'expected_version': version, 'payload': import_json(draft),
    })

    assert current_version(call_projects, draft.project) == version
    assert not DeliveryScope.objects.filter(key='imported').exists()


def test_mcp_import_writes_only_after_confirmation(call_projects, draft):
    preview = call_projects('apply_delivery_import', {
        'project_id': draft.project.pk, 'expected_version': current_version(call_projects, draft.project),
        'request_id': 'import-scope', 'payload': import_json(draft),
    })
    assert not DeliveryScope.objects.filter(key='imported').exists()

    call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert Requirement.objects.get(key='req').stage.phase.scope.key == 'imported'


def test_mcp_confirmation_rejects_a_changed_workspace(call_projects, draft):
    version = current_version(call_projects, draft.project)
    preview = call_projects('apply_delivery_import', {
        'project_id': draft.project.pk, 'expected_version': version,
        'request_id': 'import-stale', 'payload': import_json(draft),
    })
    call_projects('update_delivery_requirement', {
        'project_id': draft.project.pk, 'node_id': draft.requirement.pk,
        'expected_version': version, 'title': 'Guía revisada',
    })

    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)

    assert error['code'] == 'STALE_VERSION'
    assert not DeliveryScope.objects.filter(key='imported').exists()


def test_mcp_publication_requires_contract_signature(call_projects, draft):
    error = confirm(call_projects, 'publish_delivery_stage', {
        'project_id': draft.project.pk, 'stage_id': draft.stage.pk,
        'expected_version': current_version(call_projects, draft.project), 'request_id': 'publish-unsigned',
    }, expect_error=True)

    assert error['code'] != 'INTERNAL_ERROR'
    assert not DeliveryPublication.objects.filter(stage=draft.stage).exists()


def historical_arguments(call, draft, request_id):
    return {
        'project_id': draft.project.pk, 'stage_id': draft.stage.pk,
        'expected_version': current_version(call, draft.project), 'request_id': request_id,
        'decisions': [{'requirement_id': draft.requirement.pk,
                       'version': draft.requirement.version, 'decision': 'approved'}],
        'evidence_message': 'Mensaje entrante del cliente: confirmo la validación.',
        'client_statement': True,
        'original_reviewer': 'Cliente titular', 'occurred_at': '2026-09-30T10:00:00Z',
        'evidence_channel': 'document', 'external_reference': 'Guía de validación firmada del cliente',
        'evidence_document_ids': [draft.document.pk],
    }


def test_mcp_historical_approval_records_its_administrative_actor(call_projects, published):
    confirm(call_projects, 'record_external_delivery_approval',
            historical_arguments(call_projects, published, 'historical-evidence'))

    review = RequirementReview.objects.get(requirement=published.requirement)
    assert review.is_external is True
    assert review.actor.first_name == 'MCP'
    assert review.client_statement == 'Mensaje entrante del cliente: confirmo la validación.'


def test_mcp_rejects_editing_a_requirement_with_conformity(call_projects, published):
    confirm(call_projects, 'record_external_delivery_approval',
            historical_arguments(call_projects, published, 'approval-before-edit'))

    error = call_projects('update_delivery_requirement', {
        'project_id': published.project.pk, 'node_id': published.requirement.pk,
        'expected_version': current_version(call_projects, published.project),
        'title': 'Reemplazar evidencia aprobada',
    }, expect_error=True)

    published.requirement.refresh_from_db()
    assert error['code'] != 'INTERNAL_ERROR'
    assert published.requirement.title == 'Crear registro'


def test_mcp_historical_approval_requires_a_client_statement(call_projects, published):
    arguments = historical_arguments(call_projects, published, 'not-a-client-message')
    arguments['client_statement'] = False

    error = call_projects('record_external_delivery_approval', arguments, expect_error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert not RequirementReview.objects.filter(requirement=published.requirement).exists()


def test_mcp_reply_keeps_optional_document_evidence(call_projects, published):
    confirm(call_projects, 'add_delivery_message', {
        'project_id': published.project.pk, 'expected_version': current_version(call_projects, published.project),
        'request_id': 'reply-with-evidence', 'level': 'stage', 'target_id': published.stage.pk,
        'message': 'El ajuste está listo para otra revisión.',
        'requirement_ids': [published.requirement.pk], 'document_ids': [published.document.pk],
    })

    message = DeliveryMessage.objects.get(message='El ajuste está listo para otra revisión.')
    assert list(message.documents.values_list('pk', flat=True)) == [published.document.pk]
    assert list(message.requirements.values_list('pk', flat=True)) == [published.requirement.pk]


def test_mcp_document_association_rejects_another_project(call_projects, draft):
    other = Project.objects.create(name='Proyecto documental ajeno', client=draft.client)
    foreign = Document.objects.create(
        document_type=draft.document.document_type, title='Documento ajeno',
        project=other, client_user=draft.client,
    )

    error = call_projects('link_delivery_document', {
        'project_id': draft.project.pk, 'expected_version': current_version(call_projects, draft.project),
        'level': 'stage', 'target_id': draft.stage.pk, 'document_id': foreign.pk,
    }, expect_error=True)

    assert error['code'] != 'INTERNAL_ERROR'
    assert not DeliveryDocumentLink.objects.filter(document=foreign).exists()


def test_mcp_external_signature_consumes_a_credential_bound_pdf(call_projects, draft):
    digest = hashlib.sha256(SIGNED_PDF).hexdigest()
    asset = call_projects('begin_upload', {
        'filename': 'signed.pdf', 'content_type': 'application/pdf',
        'size': len(SIGNED_PDF), 'sha256': digest,
    })
    call_projects('upload_asset_chunk', {
        'asset_id': asset['asset_id'], 'index': 0,
        'base64': base64.b64encode(SIGNED_PDF).decode('ascii'), 'chunk_sha256': digest,
    })
    call_projects('complete_upload', {'asset_id': asset['asset_id']})

    confirm(call_projects, 'attest_external_delivery_signature', {
        'project_id': draft.project.pk, 'kind': 'contracts', 'node_id': draft.contract.pk,
        'expected_version': current_version(call_projects, draft.project), 'request_id': 'attest-pdf',
        'asset_id': asset['asset_id'], 'signer_name': 'Cliente titular',
        'signed_at': '2026-09-30T09:00:00Z', 'attestation': 'Firma constatada en el PDF entrante del cliente.',
    })

    evidence = ContractSignatureEvidence.objects.get(contract=draft.contract)
    assert evidence.sha256 == digest
    assert McpUpload.objects.get(pk=asset['asset_id']).status == McpUpload.STATUS_CONSUMED
