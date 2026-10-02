"""Approvals are per requirement and bound to an immutable publication."""
import pytest
from django.contrib.auth.models import User
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from accounts.models import ContractAmendment, DeliveryStage, Notification, ProjectContract, RequirementReview, UserProfile
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_helpers import RECORDED_AT, build_delivery_context, decisions, publish, stage_data, version
from content.models import CommunicationMessage, CommunicationThread

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


def test_partial_approval_keeps_stage_in_review(context):
    publish(context)
    result = delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                                   decisions(context, (context.first, 'approved')))
    assert stage_data(result)['status'] == 'in_review'
    assert RequirementReview.objects.get().requirement_id == context.first.pk


def test_approved_guide_cannot_be_edited(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(context, (context.first, 'approved')))
    with pytest.raises(ValidationError, match='congelado'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                             {'expected_version': version(context), 'title': 'Distinto'}, context.first.pk)
    context.first.refresh_from_db()
    assert context.first.title == 'Guardar registro'


def test_correcting_pending_work_preserves_previous_approval(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                         {'expected_version': version(context), 'title': 'Editar corregido'}, context.second.pk)
    result = publish(context, 'publish-2')
    requirements = stage_data(result)['requirements']
    assert requirements[0]['review_status'] == 'approved'
    assert requirements[1]['review_status'] == 'in_review'
    assert RequirementReview.objects.filter(requirement=context.first, decision='approved').count() == 1


def test_draft_stage_prevents_phase_approval(context):
    DeliveryStage.objects.create(phase=context.phase, key='sin-publicar', title='Pendiente')
    publish(context)
    result = delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                                   decisions(context, (context.first, 'approved'), (context.second, 'approved')))
    assert result['scopes'][0]['phases'][0]['status'] != 'approved'


def test_approved_stage_cannot_grow(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'approved')))
    with pytest.raises(ValidationError, match='congelada'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                             {'expected_version': version(context), 'stage_id': context.stage.pk, 'key': 'nuevo', 'title': 'Nuevo'})
    assert context.stage.requirements.count() == 2


def test_amendment_must_belong_to_scope_contract(context):
    other = ProjectContract.objects.create(project=context.project, key='otro', title='Otro', document=context.document)
    amendment = ContractAmendment.objects.create(contract=other, key='otrosi', title='Otrosí', document=context.document)
    with pytest.raises(ValidationError, match='contrato de este alcance'):
        delivery.mutate_node(context.project.pk, context.admin, 'scopes',
                             {'expected_version': 0, 'contract_id': context.contract.pk,
                              'amendment_id': amendment.pk, 'key': 'nuevo', 'title': 'Ampliación'})


def test_administrator_signature_cannot_authorize_publication(context):
    context.document.signed_by = context.admin
    context.document.save(update_fields=['signed_by'])
    with pytest.raises(ValidationError, match='firmado'):
        publish(context)
    assert context.stage.publications.count() == 0


def test_empty_stage_cannot_be_published(context):
    context.stage.requirements.all().delete()
    with pytest.raises(ValidationError, match='al menos un requerimiento'):
        publish(context)
    assert context.stage.publications.count() == 0


def test_incomplete_guide_cannot_be_published(context):
    context.first.guide = {}
    context.first.save(update_fields=['guide'])
    with pytest.raises(ValidationError, match='antes de publicar'):
        publish(context)
    assert context.stage.publications.count() == 0


def test_administrator_cannot_review_as_client(context):
    publish(context)
    with pytest.raises(PermissionDenied, match='cliente propietario'):
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk, decisions(context, (context.first, 'approved')))


def test_client_cannot_publish(context):
    with pytest.raises(PermissionDenied):
        delivery.publish_stage(context.project.pk, context.client, context.stage.pk, {'expected_version': 0, 'request_id': 'no'})


def test_other_client_cannot_read_project(context):
    outsider = User.objects.create_user('outsider', 'other@example.test')
    UserProfile.objects.create(user=outsider, role='client')
    with pytest.raises(NotFound):
        delivery.overview(context.project.pk, outsider)


def test_invalid_decision_rolls_back_review(context):
    publish(context)
    data = decisions(context, (context.first, 'approved'), (context.second, 'objected'))
    data['decisions'][1]['message'] = ''
    with pytest.raises(ValidationError, match='motivo'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)
    assert RequirementReview.objects.count() == 0
    context.first.refresh_from_db()
    assert context.first.review_status == 'in_review'


def test_client_cannot_approve_edited_unpublished_version(context):
    publish(context)
    stale = decisions(context, (context.first, 'approved'))
    delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                         {'expected_version': version(context), 'title': 'Borrador'}, context.first.pk)
    stale['expected_version'] = version(context)
    with pytest.raises(DeliveryConflict, match='guía cambió'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, stale)
    assert RequirementReview.objects.count() == 0


def test_repeated_review_does_not_duplicate_evidence(context):
    publish(context)
    data = decisions(context, (context.first, 'approved'))
    initial = delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)
    count = Notification.objects.count()
    repeated = delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)
    assert repeated == initial
    assert RequirementReview.objects.count() == 1
    assert Notification.objects.count() == count


def test_reused_request_identifier_rejects_different_content(context):
    publish(context)
    data = decisions(context, (context.first, 'approved'))
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)
    data['decisions'][0]['message'] = 'Otra respuesta'
    with pytest.raises(DeliveryConflict, match='otra operación'):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, data)


def test_historical_approval_captures_original_client_evidence(context):
    publish(context)
    thread = CommunicationThread.objects.create(client=context.client.profile, project=context.project, title='Validación')
    message = CommunicationMessage.objects.create(thread=thread, direction='incoming', status='received',
                                                  channel='email', content='Apruebo guardar registro.', occurred_at=RECORDED_AT)
    data = {**decisions(context, (context.first, 'approved')), 'client_statement': True,
            'source_message_id': message.pk, 'evidence_message': 'Apruebo guardar registro.'}
    delivery.review_stage(context.project.pk, context.admin, context.stage.pk, data, historical=True)
    review = RequirementReview.objects.get()
    assert review.actor_id == context.admin.pk
    assert review.original_reviewer == 'Cliente'
    assert review.reviewed_at == RECORDED_AT
    assert review.source_snapshot['direction'] == 'incoming'


def test_outgoing_constance_is_not_client_approval(context):
    publish(context)
    thread = CommunicationThread.objects.create(client=context.client.profile, project=context.project, title='Cierre')
    message = CommunicationMessage.objects.create(thread=thread, direction='outgoing', status='sent',
                                                  channel='email', content='Confirmamos el cierre.', occurred_at=RECORDED_AT)
    data = {**decisions(context, (context.first, 'approved')), 'client_statement': True,
            'source_message_id': message.pk, 'evidence_message': 'Confirmamos el cierre.'}
    with pytest.raises(ValidationError, match='mensaje entrante'):
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk, data, historical=True)
    assert RequirementReview.objects.count() == 0


def test_unsubstantiated_historical_approval_is_rejected(context):
    publish(context)
    data = {**decisions(context, (context.first, 'approved')), 'client_statement': True,
            'evidence_message': 'El equipo cree que el cliente aprobó.'}
    with pytest.raises(ValidationError, match='autor, fecha y fuente'):
        delivery.review_stage(context.project.pk, context.admin, context.stage.pk, data, historical=True)


def test_published_guide_remains_visible_during_draft_edit(context):
    publish(context)
    delivery.mutate_node(context.project.pk, context.admin, 'requirements',
                         {'expected_version': version(context), 'title': 'Borrador privado'}, context.second.pk)
    result = delivery.overview(context.project.pk, context.client)
    assert stage_data(result)['requirements'][1]['title'] == 'Editar registro'
    assert stage_data(result)['requirements'][1]['version'] == 1
