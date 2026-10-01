"""Contractual provenance cannot be changed through selection or draft writes."""
import pytest
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from accounts.models import ContractSignatureEvidence, DeliveryMessage, DeliveryPromptContext, Notification, Project, ProjectContract, Requirement
from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_authoring_helpers import (
    api_for, build_authoring_context, citation, endpoint, guides_payload,
    other_contract, pdf_bytes, reply_payload, signed_amendment, source_document,
)
from accounts.tests.delivery_helpers import RECORDED_AT, prepare_prompt, publish, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


@pytest.mark.parametrize('selection', ['missing_contract', 'stage_selected'])
def test_guide_selection_rejects_an_invalid_contract_boundary(context, selection):
    """Fails if guides can be prepared without selecting only their contractual root."""
    values = {'expected_version': 0, 'request_id': 'invalid-guide-selection', 'mode': 'guides'}
    selections = {
        'missing_contract': {},
        'stage_selected': {'contract_id': context.contract.pk, 'stage_id': context.stage.pk},
    }

    with pytest.raises(ValidationError, match='seleccionar un contrato'):
        authoring.create_prompt_context(context.project.pk, context.admin, values | selections[selection])

    assert DeliveryPromptContext.objects.count() == 0
    assert ContractSignatureEvidence.objects.count() == 0
    assert version(context) == 0


def test_guide_selection_rejects_a_scope_from_another_contract(context):
    """Fails if a selected scope supplies the contractual ancestry of another agreement."""
    other = other_contract(context)

    with pytest.raises(ValidationError, match='no pertenece al contrato'):
        prepare_prompt(context, contract_id=other.pk, scope_id=context.scope.pk)

    assert DeliveryPromptContext.objects.count() == 0
    assert ContractSignatureEvidence.objects.count() == 0
    assert version(context) == 0


def test_repeated_amendments_are_rejected_before_capture(context):
    """Fails if selecting an amendment twice creates ambiguous duplicate evidence."""
    amendment = signed_amendment(context)

    with pytest.raises(ValidationError, match='No repitas otrosíes'):
        prepare_prompt(context, amendment_ids=[amendment.pk, amendment.pk])

    assert DeliveryPromptContext.objects.count() == 0
    assert ContractSignatureEvidence.objects.count() == 0


def test_tampered_contract_proof_cannot_supply_contractual_text(context):
    """Fails if a modified signed contractual root falls back to live document text."""
    prepare_prompt(context)
    evidence = context.contract.signature_evidence.get()
    with evidence.file.open('wb') as stream:
        stream.write(pdf_bytes('An invented replacement contractual scope.'))

    prepared = prepare_prompt(context, request_id='capture-tampered-contract')

    source = prepared['sources'][0]
    assert source['status'] == 'unreadable'
    assert source['fragments'] == []
    assert (source['sha256'], source['download_url']) == (None, None)
    assert prepared['complete'] is False
    assert 'no coincide con su hash' in ' '.join(source['warnings'])
    assert 'invented replacement' not in prepared['prompt']
    assert 'Alcance acordado.' not in prepared['prompt']


def test_a_different_signer_cannot_establish_client_contractual_evidence(context):
    """Fails if another person's recorded signature is treated as the client's assent."""
    context.document.signed_by = context.admin
    context.document.save(update_fields=['signed_by'])

    prepared = prepare_prompt(context)

    source = prepared['sources'][0]
    assert source['status'] == 'unreadable'
    assert source['fragments'] == []
    assert prepared['complete'] is False
    assert 'no corresponde al cliente propietario' in ' '.join(source['warnings'])
    assert ContractSignatureEvidence.objects.count() == 0


def test_cited_import_rejects_a_contract_replacement(context):
    """Fails if draft JSON substitutes an agreement absent from its captured selection."""
    other = other_contract(context)
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    payload['scopes'][0]['contract_id'] = other.pk

    response = api_for(context.admin).post(endpoint(context, 'import/apply/'), {
        'expected_version': 0, 'request_id': 'replace-captured-contract', 'payload': payload,
    }, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'context_scope'
    assert Requirement.objects.count() == 2
    assert version(context) == 0


def test_cited_import_rejects_an_unselected_amendment(context):
    """Fails if draft JSON adds an amendment the administrator did not select."""
    amendment = signed_amendment(context)
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    payload['scopes'][0]['amendment_id'] = amendment.pk

    response = api_for(context.admin).post(endpoint(context, 'import/apply/'), {
        'expected_version': 0, 'request_id': 'add-unselected-amendment', 'payload': payload,
    }, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'context_scope'
    assert Requirement.objects.count() == 2
    assert version(context) == 0


def test_cited_import_rejects_a_selected_scope_replacement(context):
    """Fails if JSON prepared for one existing scope creates a different scope."""
    prepared = prepare_prompt(context, scope_id=context.scope.pk)
    payload = guides_payload(prepared)
    payload['scopes'][0]['key'] = 'replacement-scope'

    response = api_for(context.admin).post(endpoint(context, 'import/apply/'), {
        'expected_version': 0, 'request_id': 'replace-selected-scope', 'payload': payload,
    }, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'context_scope'
    assert context.contract.scopes.count() == 1
    assert version(context) == 0


def test_manual_requirement_citations_need_a_captured_context(context):
    """Fails if direct editing attaches citations without their retained source context."""
    prepared = prepare_prompt(context)

    response = api_for(context.admin).patch(endpoint(context, f'requirements/{context.first.pk}/'), {
        'expected_version': 0, 'source_references': [citation(prepared)],
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 400
    assert response.data['code'] == 'context_required'
    assert context.first.context_id is None
    assert context.first.source_references == []
    assert version(context) == 0


def test_manual_requirement_rejects_another_projects_captured_context(context):
    """Fails if a real context captured for another project supplies guide provenance."""
    other = Project.objects.create(name='Other contractual project', client=context.client)
    document = source_document(context, 'Contract includes creating records.', project=other)
    contract = ProjectContract.objects.create(project=other, key='other-project-contract',
                                              title='Other project contract', document=document)
    prepared = authoring.create_prompt_context(other.pk, context.admin, {
        'expected_version': 0, 'request_id': 'foreign-project-context',
        'mode': 'guides', 'contract_id': contract.pk,
    })

    response = api_for(context.admin).patch(endpoint(context, f'requirements/{context.first.pk}/'), {
        'expected_version': 0, 'context_id': prepared['id'], 'source_references': [citation(prepared)],
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 404
    assert context.first.context_id is None
    assert context.first.source_references == []
    assert version(context) == 0


def test_reply_preview_rejects_a_stale_workspace_version(context):
    """Fails if a stale response preview succeeds after the client updates the review."""
    publish(context)
    prepared = prepare_prompt(context, mode='reply', stage_id=context.stage.pk)
    prepared_version = version(context)
    delivery.add_message(context.project.pk, context.client, {
        'expected_version': prepared_version, 'request_id': 'new-client-observation',
        'level': 'stage', 'target_id': context.stage.pk, 'message': 'Please review the new observation.',
    })
    notifications = Notification.objects.count()

    response = api_for(context.admin).post(endpoint(context, 'reply/preview/'), {
        'expected_version': prepared_version, 'payload': reply_payload(prepared),
    }, format='json')

    assert response.status_code == 409
    assert DeliveryMessage.objects.count() == 1
    assert Notification.objects.count() == notifications
    assert version(context) == prepared_version + 1
