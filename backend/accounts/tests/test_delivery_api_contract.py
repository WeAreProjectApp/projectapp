"""The JWT delivery routes preserve their real authoring/review contracts."""
import hashlib

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun import freeze_time
from rest_framework.test import APIClient

from accounts.models import ContractSignatureEvidence, DeliveryDocumentLink, DeliveryWorkspace, Requirement, RequirementReview
from accounts.services.delivery_documents import _raw_pdf
from accounts.services.tokens import get_tokens_for_user
from accounts.tests.delivery_helpers import GUIDE, RECORDED_AT, build_delivery_context, decisions, version
from content.models import CommunicationMessage, CommunicationThread, Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


def api_for(actor):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(actor)["access"]}')
    return api


def endpoint(context, suffix=''):
    return f'/api/accounts/projects/{context.project.pk}/delivery/{suffix}'


def draft_tree(context):
    return {'schema_version': 1, 'scopes': [{
        'key': 'http-scope', 'title': 'Alcance HTTP', 'contract_id': context.contract.pk,
        'phases': [{'key': 'http-phase', 'title': 'Fase HTTP', 'stages': [{
            'key': 'http-stage', 'title': 'Etapa HTTP', 'requirements': [{
                'key': 'http-guide', 'title': 'Consultar solicitudes', 'guide': GUIDE,
            }],
        }]}],
    }]}


def create_payload(context, kind):
    parents = {
        'contracts': {'document_id': context.document.pk, 'client_visible': False},
        'scopes': {'contract_id': context.contract.pk},
        'stages': {'phase_id': context.phase.pk},
        'requirements': {'stage_id': context.stage.pk, 'guide': GUIDE},
    }
    return {'expected_version': version(context), 'key': 'http-created',
            'title': 'Contenido creado por HTTP', **parents[kind]}


def publish_http(context, api):
    response = api.post(endpoint(context, f'stages/{context.stage.pk}/publish/'), {
        'expected_version': version(context), 'request_id': 'http-publish',
    }, format='json')
    assert response.status_code == 200
    return response


def attachment(context):
    return Document.objects.create(
        project=context.project, client_user=context.client, title='Guía HTTP',
        content_markdown='# Guía\nUsar un registro de prueba.',
        include_portada=False, include_subportada=False, include_contraportada=False,
    )


@pytest.mark.parametrize('kind', ['contracts', 'scopes', 'stages', 'requirements'])
def test_admin_can_create_authoring_nodes_through_jwt(context, kind):
    """Fails if the authoring collection route loses its admin write contract."""
    api = api_for(context.admin)

    response = api.post(endpoint(context, f'{kind}/'), create_payload(context, kind), format='json')

    assert response.status_code == 201
    assert response.data['result']['kind'] == kind
    assert response.data['version'] == 1


def test_authoring_route_rejects_a_json_array(context):
    """Fails if a malformed authoring body becomes a 500 or creates a row."""
    api = api_for(context.admin)

    response = api.post(endpoint(context, 'stages/'), [{'expected_version': 0}], format='json')

    assert response.status_code == 400
    assert response.data['non_field_errors'] == ['Se esperaba un objeto JSON.']
    assert version(context) == 0


def test_authoring_route_rejects_publication_state_injection(context):
    """Fails if authoring can publish a guide by injecting a workflow field."""
    api = api_for(context.admin)
    payload = {**create_payload(context, 'stages'), 'editorial_status': 'published'}

    response = api.post(endpoint(context, 'stages/'), payload, format='json')

    assert response.status_code == 400
    assert response.data['editorial_status'] == 'Campo no permitido.'
    assert version(context) == 0


def test_client_cannot_write_authoring_nodes(context):
    """Fails if a valid client JWT acquires the administrator's authoring power."""
    api = api_for(context.client)

    response = api.post(endpoint(context, 'stages/'), create_payload(context, 'stages'), format='json')

    assert response.status_code == 403
    assert version(context) == 0


def test_unknown_node_is_reported_as_not_found(context):
    """Fails if an unknown node silently creates or edits another draft."""
    api = api_for(context.admin)

    response = api.patch(endpoint(context, 'stages/999999/'),
                         {'expected_version': 0, 'title': 'No existe'}, format='json')

    assert response.status_code == 404
    assert response.data['detail'] == 'Elemento de seguimiento no encontrado.'
    assert version(context) == 0


def test_stale_authoring_version_cannot_create_a_node(context):
    """Fails if an outdated browser can insert content over a newer workspace."""
    api = api_for(context.admin)
    payload = {**create_payload(context, 'requirements'), 'expected_version': 1}

    response = api.post(endpoint(context, 'requirements/'), payload, format='json')

    assert response.status_code == 409
    assert Requirement.objects.filter(key='http-created').count() == 0
    assert version(context) == 0


def test_prompt_route_returns_the_actual_contract_schema(context):
    """Fails if the HTTP authoring prompt loses contract context or becomes a write."""
    api = api_for(context.admin)

    response = api.get(endpoint(context, 'prompt/'))

    assert response.status_code == 200
    assert 'Alcance acordado.' in response.data['prompt']
    assert response.data['schema']['properties']['schema_version']['const'] == 1
    assert DeliveryWorkspace.objects.count() == 0


def test_import_preview_route_keeps_the_database_unchanged(context):
    """Fails if the preview URL accidentally invokes the applying operation."""
    api = api_for(context.admin)

    response = api.post(endpoint(context, 'import/preview/'),
                        {'expected_version': 0, 'payload': draft_tree(context)}, format='json')

    assert response.status_code == 200
    assert response.data['valid'] is True
    assert response.data['summary']['requirements'] == 1
    assert Requirement.objects.filter(key='http-guide').count() == 0


def test_import_apply_route_keeps_new_guides_private(context):
    """Fails if applying draft JSON exposes its guides to the customer."""
    api = api_for(context.admin)

    response = api.post(endpoint(context, 'import/apply/'), {
        'expected_version': 0, 'request_id': 'http-import', 'payload': draft_tree(context),
    }, format='json')

    client_response = api_for(context.client).get(endpoint(context))
    assert response.status_code == 200
    assert Requirement.objects.get(key='http-guide').review_status == 'pending'
    assert client_response.data['scopes'] == []


@pytest.mark.parametrize('mode', ['preview', 'apply'])
def test_import_envelope_rejects_unknown_workflow_fields(context, mode):
    """Fails if the HTTP envelope bypasses strict draft-only JSON authoring."""
    api = api_for(context.admin)

    response = api.post(endpoint(context, f'import/{mode}/'), {
        'expected_version': 0, 'request_id': 'bad-envelope',
        'payload': draft_tree(context), 'approved': True,
    }, format='json')

    assert response.status_code == 400
    assert response.data['detail'] == 'La importación contiene campos no permitidos.'
    assert Requirement.objects.filter(key='http-guide').count() == 0


def test_customer_jwt_records_only_the_selected_requirement(context):
    """Fails if the review URL rejects a genuine owner or approves the whole stage."""
    publish_http(context, api_for(context.admin))
    api = api_for(context.client)

    response = api.post(endpoint(context, f'stages/{context.stage.pk}/review/'),
                        decisions(context, (context.first, 'approved')), format='json')

    context.first.refresh_from_db()
    context.second.refresh_from_db()
    assert response.status_code == 200
    assert context.first.review_status == 'approved'
    assert context.second.review_status == 'in_review'
    assert RequirementReview.objects.get().actor_id == context.client.pk


def test_customer_reply_route_preserves_requirement_references(context):
    """Fails if the message URL drops the requirements explaining the reply."""
    publish_http(context, api_for(context.admin))
    api = api_for(context.client)

    response = api.post(endpoint(context, 'messages/'), {
        'expected_version': version(context), 'request_id': 'http-message',
        'level': 'stage', 'target_id': context.stage.pk,
        'requirement_ids': [context.first.pk], 'message': 'Necesito confirmar los datos de prueba.',
    }, format='json')

    message = response.data['scopes'][0]['phases'][0]['stages'][0]['messages'][0]
    assert response.status_code == 201
    assert message['message'] == 'Necesito confirmar los datos de prueba.'
    assert message['requirement_ids'] == [context.first.pk]


def test_admin_document_picker_can_remove_a_draft_attachment(context):
    """Fails if a selected draft attachment is unreadable or cannot be removed."""
    api = api_for(context.admin)
    doc = attachment(context)
    options = api.get(endpoint(context, 'documents/options/'))
    linked = api.post(endpoint(context, 'documents/'), {
        'expected_version': 0, 'level': 'stage', 'target_id': context.stage.pk, 'document_id': doc.pk,
    }, format='json')
    link_id = linked.data['result']['id']
    downloaded = api.get(endpoint(context, f'documents/{link_id}/pdf/'))

    response = api.delete(endpoint(context, f'documents/{link_id}/'),
                          {'expected_version': version(context)}, format='json')

    listed = api.get(endpoint(context, f'documents/?level=stage&target_id={context.stage.pk}'))
    assert next(row for row in options.data['documents'] if row['id'] == doc.pk)['title'] == 'Guía HTTP'
    assert downloaded.status_code == 200
    assert downloaded['Cache-Control'] == 'private, no-store'
    assert response.status_code == 200
    assert listed.data['documents'] == []
    assert DeliveryDocumentLink.objects.filter(pk=link_id).count() == 0


def test_document_filter_rejects_an_invalid_target_identifier(context):
    """Fails if a malformed query identifier becomes a 500 or a broad document list."""
    api = api_for(context.admin)

    response = api.get(endpoint(context, 'documents/?level=stage&target_id=no-es-un-id'))

    assert response.status_code == 400
    assert response.data['detail'] == 'El identificador documental debe ser un entero.'


def test_external_signature_route_preserves_the_uploaded_pdf(context):
    """Fails if multipart parsing drops the signed file or exposes a regenerated PDF."""
    api = api_for(context.admin)
    context.document.signed_at = None
    context.document.signed_by = None
    context.document.save(update_fields=['signed_at', 'signed_by'])
    pdf = _raw_pdf(context.document)

    response = api.post(endpoint(context, f'contracts/{context.contract.pk}/signature-external/'), {
        'expected_version': 0, 'request_id': 'http-signature', 'signer_name': 'Cliente',
        'signed_at': RECORDED_AT.isoformat(), 'attestation': 'PDF firmado recibido del cliente.',
        'file': SimpleUploadedFile('contrato-firmado.pdf', pdf, content_type='application/pdf'),
    }, format='multipart')

    downloaded = api_for(context.client).get(endpoint(context, f'contracts/{context.contract.pk}/pdf/'))
    assert response.status_code == 200
    assert response.data['contracts'][0]['signature_status'] == 'external'
    assert downloaded.status_code == 200
    assert downloaded.content == pdf
    assert response.data['contracts'][0]['signature_evidence'][0]['sha256'] == hashlib.sha256(pdf).hexdigest()


def test_historical_evidence_catalogue_roundtrips_received_client_proof(context):
    """Fails if incoming proof selection loses its private recorded document link."""
    api = api_for(context.admin)
    publish_http(context, api)
    doc = attachment(context)
    thread = CommunicationThread.objects.create(client=context.client.profile, project=context.project, title='Validación')
    source = CommunicationMessage.objects.create(thread=thread, direction='incoming', status='received',
                                                  channel='email', content='Apruebo guardar registro.', occurred_at=RECORDED_AT)
    options = api.get(endpoint(context, 'evidence-options/'))
    data = {**decisions(context, (context.first, 'approved')), 'client_statement': True,
            'source_message_id': source.pk, 'evidence_message': source.content, 'evidence_document_ids': [doc.pk]}

    response = api.post(endpoint(context, f'stages/{context.stage.pk}/historical-approvals/'), data, format='json')

    review = RequirementReview.objects.get()
    proof = api_for(context.client).get(endpoint(context, f'reviews/{review.pk}/evidence/'))
    assert response.status_code == 200
    assert options.data['messages'][0]['id'] == source.pk
    assert proof.status_code == 200
    assert proof.data['documents'][0]['document_id'] == doc.pk
    assert proof.data['documents'][0]['title'] == 'Guía HTTP'


@freeze_time('2026-09-30T12:00:00Z')
def test_client_jwt_can_download_the_signed_amendment_pdf(context):
    """Fails if portal signing captures only contracts or loses the amendment PDF."""
    source = attachment(context)
    source.requires_signature = True
    source.save(update_fields=['requires_signature'])
    original_pdf = _raw_pdf(source)
    source.generated_file.save('amendment.pdf', ContentFile(original_pdf), save=True)
    created = api_for(context.admin).post(endpoint(context, 'amendments/'), {
        'expected_version': 0, 'key': 'http-amendment', 'title': 'Otrosí firmado',
        'contract_id': context.contract.pk, 'document_id': source.pk, 'client_visible': True,
    }, format='json')
    amendment_id = created.data['result']['id']
    api = api_for(context.client)

    signed = api.post(f'/api/accounts/documents/{source.uuid}/sign/',
                      {'accept': True, 'signature_name': 'Cliente titular'}, format='json')
    response = api.get(endpoint(context, f'amendments/{amendment_id}/pdf/'))

    assert created.status_code == 201
    assert signed.status_code == 200
    assert response.status_code == 200
    assert response.content == original_pdf
    assert response['Cache-Control'] == 'private, no-store'
    assert response['Content-Disposition'] == 'attachment; filename="otrosi-firmado.pdf"'
    assert ContractSignatureEvidence.objects.get(amendment_id=amendment_id).method == 'portal'
