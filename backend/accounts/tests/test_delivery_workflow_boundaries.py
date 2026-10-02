"""Business boundaries that protect published delivery evidence."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun import freeze_time
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import (
    ContractAmendment, DeliveryMessage, DeliveryScope, DeliveryStage,
    Notification, Requirement, RequirementReview,
)
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_documents import _raw_pdf
from accounts.tests.delivery_helpers import (
    RECORDED_AT, build_delivery_context, decisions, publish, stage_data, version,
)
from content.models import CommunicationMessage, CommunicationThread, Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


def test_deleting_a_draft_requirement_invalidates_stage_version(context):
    """A removed draft guide must invalidate an editor's saved stage version."""
    old_version = context.stage.version

    delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                         {'expected_version': version(context)}, context.second.pk, delete=True)

    context.stage.refresh_from_db()
    assert not Requirement.objects.filter(pk=context.second.pk).exists()
    assert context.stage.version == old_version + 1
    assert context.stage.editorial_status == 'draft'


def test_signed_contract_evidence_cannot_be_deleted_before_publication(context):
    """A signed original remains evidence even before its first delivery round."""
    delivery.mutate_node(context.project.pk, context.admin, 'contracts',
                         {'expected_version': version(context)}, context.contract.pk)
    evidence_id = context.contract.signature_evidence.get().pk

    with pytest.raises(ValidationError, match='eliminar evidencia de firma'):
        delivery.mutate_node(context.project.pk, context.admin, 'contracts',
                             {'expected_version': version(context)}, context.contract.pk, delete=True)

    assert context.contract.signature_evidence.get().pk == evidence_id
    assert context.project.delivery_contracts.filter(pk=context.contract.pk).exists()


def test_published_scope_cannot_be_deleted(context):
    """Deleting a published ancestor would erase the client's review history."""
    publish(context)

    with pytest.raises(ValidationError, match='eliminar evidencia publicada'):
        delivery.mutate_node(context.project.pk, context.admin, 'scopes',
                             {'expected_version': version(context)}, context.scope.pk, delete=True)

    assert context.stage.publications.count() == 1
    assert DeliveryScope.objects.filter(pk=context.scope.pk).exists()


def test_published_scope_description_cannot_be_rewritten(context):
    """The agreed scope stays intact while its published guides are reviewed."""
    publish(context)

    with pytest.raises(ValidationError, match='contexto contractual publicado'):
        delivery.mutate_node(context.project.pk, context.admin, 'scopes',
                             {'expected_version': version(context), 'description': 'Otro alcance'}, context.scope.pk)

    context.scope.refresh_from_db()
    assert context.scope.description == ''


def test_published_requirement_cannot_move_to_another_stage(context):
    """Moving a guide must not change the stage attached to its evidence."""
    destination = DeliveryStage.objects.create(phase=context.phase, key='destino', title='Destino')
    publish(context)

    with pytest.raises(ValidationError, match='referencias publicadas'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                             {'expected_version': version(context), 'stage_id': destination.pk}, context.first.pk)

    context.first.refresh_from_db()
    assert context.first.stage_id == context.stage.pk
    assert destination.requirements.count() == 0


def test_approved_phase_cannot_receive_another_stage(context):
    """An extension cannot silently reopen a phase the client already closed."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'approved')))

    with pytest.raises(ValidationError, match='fase aprobada está congelada'):
        delivery.mutate_node(context.project.pk, context.admin, 'stages',
                             {'expected_version': version(context), 'phase_id': context.phase.pk,
                              'key': 'ampliacion', 'title': 'Ampliación'})

    assert context.phase.stages.count() == 1


def test_approved_stage_title_cannot_be_rewritten(context):
    """A stage the client closed must preserve its agreed identity."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'approved')))

    with pytest.raises(ValidationError, match='etapa aprobada está congelada'):
        delivery.mutate_node(context.project.pk, context.admin, 'stages',
                             {'expected_version': version(context), 'title': 'Nombre posterior'}, context.stage.pk)

    context.stage.refresh_from_db()
    assert context.stage.title == 'Etapa'


def test_new_current_scope_replaces_previous_current_scope(context):
    """The same contract must not expose two competing current scopes."""
    result = delivery.mutate_node(context.project.pk, context.admin, 'scopes',
                                  {'expected_version': version(context), 'contract_id': context.contract.pk,
                                   'key': 'nuevo', 'title': 'Nuevo alcance', 'is_current': True})

    assert list(context.contract.scopes.filter(is_current=True).values_list('pk', flat=True)) == [result['result']['id']]
    context.scope.refresh_from_db()
    assert context.scope.is_current is False


def test_unsigned_applicable_amendment_blocks_publication(context):
    """The original signature cannot stand in for an unsigned amendment."""
    document = Document.objects.create(title='Otrosí pendiente', project=context.project,
                                       client_user=context.client, requires_signature=True)
    amendment = ContractAmendment.objects.create(contract=context.contract, key='ampliacion',
                                                  title='Otrosí', document=document, client_visible=True)
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])

    with pytest.raises(ValidationError, match='otrosí aplicable debe estar firmado'):
        publish(context)

    assert context.stage.publications.count() == 0


def test_signed_applicable_amendment_is_captured_in_publication(context):
    """The published round must identify the amendment's actual client signature."""
    document = Document.objects.create(title='Otrosí firmado', project=context.project,
                                       client_user=context.client, requires_signature=True,
                                       signed_by=context.client, signed_at=RECORDED_AT, signature_name='Cliente',
                                       content_markdown='Ampliación firmada', include_portada=False,
                                       include_subportada=False, include_contraportada=False)
    amendment = ContractAmendment.objects.create(contract=context.contract, key='ampliacion',
                                                  title='Otrosí', document=document, client_visible=True)
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])

    publish(context)

    assert context.stage.publications.get().payload['amendment_signature'] == {
        'signature_status': 'portal', 'signed_at': RECORDED_AT.isoformat(), 'signer_name': 'Cliente',
    }
    assert amendment.signature_evidence.get().attested_by_id == context.client.pk


def test_hidden_contract_blocks_publication(context):
    """A client must be able to consult the contract behind a delivery request."""
    context.contract.client_visible = False
    context.contract.save(update_fields=['client_visible'])

    with pytest.raises(ValidationError, match='consultar el contrato'):
        publish(context)

    assert context.stage.publications.count() == 0
    assert not Notification.objects.filter(user=context.client).exists()


def test_stage_edit_requires_a_new_publication(context):
    """Changing a stage explanation must remain an internal draft until published."""
    publish(context)

    delivery.mutate_node(context.project.pk, context.admin, 'stages',
                         {'expected_version': version(context), 'description': 'Explicación corregida'}, context.stage.pk)

    context.stage.refresh_from_db()
    assert context.stage.editorial_status == 'draft'
    assert stage_data(delivery.overview(context.project.pk, context.client))['description'] == ''
    assert context.stage.description == 'Explicación corregida'


def test_duplicate_decisions_cannot_create_two_approvals(context):
    """One request cannot submit competing decisions for the same guide."""
    publish(context)
    data = decisions(context, (context.first, 'approved'), (context.first, 'rejected'))

    with pytest.raises(ValidationError, match='No repitas un requerimiento'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)

    assert not RequirementReview.objects.exists()
    context.first.refresh_from_db()
    assert context.first.review_status == 'in_review'


def test_objection_cannot_be_replaced_without_a_new_round(context):
    """A closed response remains evidence until the team opens another round."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'objected')))

    with pytest.raises(ValidationError, match='nueva publicación'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                              decisions(context, (context.first, 'approved'), request_id='second-response'))

    assert list(RequirementReview.objects.values_list('decision', flat=True)) == ['objected']


def test_approved_requirement_cannot_receive_a_later_rejection(context):
    """A later request cannot overwrite the client's recorded approval."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved')))

    with pytest.raises(ValidationError, match='aprobación previa se conserva'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                              decisions(context, (context.first, 'rejected'), request_id='later-rejection'))

    assert list(RequirementReview.objects.values_list('decision', flat=True)) == ['approved']


def test_client_cannot_inject_historical_approval_metadata(context):
    """A portal response must record its real actor rather than a supplied identity."""
    publish(context)
    data = {**decisions(context, (context.first, 'approved')), 'original_reviewer': 'Otro firmante'}

    with pytest.raises(ValidationError, match='evidencia histórica'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)

    assert not RequirementReview.objects.exists()


def test_historical_register_cannot_turn_an_objection_into_approval(context):
    """The administrative history path accepts only explicit client approvals."""
    publish(context)
    data = {**decisions(context, (context.first, 'objected')), 'client_statement': True,
            'evidence_message': 'El cliente objetó esta entrega'}

    with pytest.raises(ValidationError, match='solo admite aprobaciones expresas'):
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk, data, historical=True)

    assert not RequirementReview.objects.exists()


def test_historical_quote_must_exist_in_the_incoming_message(context):
    """An incoming email cannot support an approval the client never wrote."""
    publish(context)
    thread = CommunicationThread.objects.create(client=context.client.profile, project=context.project, title='Pruebas')
    source = CommunicationMessage.objects.create(thread=thread, direction='incoming', status='received',
                                                  channel='email', content='Todavía estoy probando.', occurred_at=RECORDED_AT)
    data = {**decisions(context, (context.first, 'approved')), 'client_statement': True,
            'source_message_id': source.pk, 'evidence_message': 'Apruebo todo.'}

    with pytest.raises(ValidationError, match='citar el contenido recibido'):
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk, data, historical=True)

    assert not RequirementReview.objects.exists()


def test_client_cannot_write_an_internal_note(context):
    """A client must not hide a response from the public delivery conversation."""
    data = {'expected_version': version(context), 'request_id': 'internal-client', 'level': 'project',
            'target_id': context.project.pk, 'message': 'Nota oculta', 'is_internal': True}

    with pytest.raises(PermissionDenied, match='notas internas'):
        delivery.add_message(context.project.pk, context.client, data)

    assert not DeliveryMessage.objects.exists()


def test_response_cannot_reference_a_requirement_from_another_stage(context):
    """A stage conversation cannot attach a guide from a different stage."""
    destination = DeliveryStage.objects.create(phase=context.phase, key='destino', title='Destino')
    data = {'expected_version': version(context), 'request_id': 'wrong-stage', 'level': 'stage',
            'target_id': destination.pk, 'message': 'Observación', 'is_internal': True,
            'requirement_ids': [context.first.pk]}

    with pytest.raises(ValidationError, match='nivel seleccionado'):
        delivery.add_message(context.project.pk, context.admin, data)

    assert not DeliveryMessage.objects.exists()


def test_response_cannot_attach_a_document_twice(context):
    """Duplicate attachments must fail before storing or notifying a response."""
    data = {'expected_version': version(context), 'request_id': 'duplicate-documents', 'level': 'project',
            'target_id': context.project.pk, 'message': 'Evidencia',
            'document_ids': [context.document.pk, context.document.pk]}

    with pytest.raises(ValidationError, match='No repitas documentos'):
        delivery.add_message(context.project.pk, context.client, data)

    assert not DeliveryMessage.objects.exists()
    assert not Notification.objects.exists()


@freeze_time(RECORDED_AT)
def test_external_signature_cannot_claim_a_future_signing_date(context):
    """A future-dated upload cannot establish a signed contractual agreement."""
    context.document.signed_at = None
    context.document.signed_by = None
    context.document.save(update_fields=['signed_at', 'signed_by'])
    signed_file = SimpleUploadedFile('signed.pdf', _raw_pdf(context.document), content_type='application/pdf')
    data = {'expected_version': version(context), 'request_id': 'future-signature',
            'signer_name': 'Cliente', 'signed_at': (RECORDED_AT + timedelta(days=1)).isoformat(),
            'attestation': 'Acuerdo recibido del cliente.'}

    with pytest.raises(ValidationError, match='firma no puede estar en el futuro'):
        delivery.attest_signature(context.project.pk, context.admin, 'contracts', context.contract.pk, data, signed_file)

    assert context.contract.signature_evidence.count() == 0
    assert version(context) == 0


@freeze_time(RECORDED_AT)
def test_historical_approval_cannot_claim_a_future_review_date(context):
    """The team cannot close a guide using a client approval dated in the future."""
    publish(context)
    before = version(context)
    data = {**decisions(context, (context.first, 'approved')), 'client_statement': True,
            'evidence_message': 'Apruebo guardar el registro.', 'original_reviewer': 'Cliente',
            'occurred_at': (RECORDED_AT + timedelta(days=1)).isoformat(),
            'evidence_channel': 'document', 'external_reference': 'constancia-del-cliente',
            'evidence_document_ids': [context.document.pk]}

    with pytest.raises(ValidationError, match='aprobación no puede estar en el futuro'):
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk, data, historical=True)

    assert RequirementReview.objects.count() == 0
    assert version(context) == before
