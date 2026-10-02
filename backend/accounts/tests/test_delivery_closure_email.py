"""Manual closure-email evidence is frozen before its single SMTP attempt."""
import hashlib
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import (
    DeliveryDocumentSnapshot, DeliveryEvidenceEmail, DeliveryMessage,
    DeliveryPhase, DeliveryScope, DeliveryStage, ProjectContract, Requirement,
    UserProfile,
)
from accounts.services import delivery_closure_email as closure_email
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish, version
from content.models import Document, EmailDeliverySnapshot, EmailLog, McpConnector, McpCredential


pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


def _approved(context, *, with_attachment=False):
    document = None
    if with_attachment:
        document = Document.objects.create(
            title='Guía aprobada', project=context.project, client_user=context.client,
            is_client_visible=True, content_markdown='# Guía\nUsa datos de prueba.',
            include_portada=False, include_subportada=False, include_contraportada=False,
        )
        delivery.link_document(context.project.pk, context.admin, {
            'expected_version': version(context), 'level': 'stage',
            'target_id': context.stage.pk, 'document_id': document.pk,
        })
    publish(context)
    delivery.review_stage(
        context.project.pk, context.client, context.stage.pk,
        decisions(context, (context.first, 'approved'), (context.second, 'approved')),
    )
    return document


def _prepare(context, **overrides):
    data = {
        'expected_version': version(context), 'request_id': 'closure-prepare-1',
        'message': 'Validamos el cierre con el equipo.',
    }
    data.update(overrides)
    return closure_email.prepare_stage_email(
        context.project.pk, context.admin, context.stage.pk, data,
    )


def _send(context, preparation, **overrides):
    data = {
        'expected_version': version(context), 'request_id': 'closure-send-1',
        'preview_sha256': preparation['manifest_sha256'], 'human_reviewed': True,
    }
    data.update(overrides)
    return closure_email.send_stage_email(
        context.project.pk, context.admin, preparation['id'], data,
    )


def test_prepare_requires_every_requirement_to_be_approved(context):
    """Fails if a partially reviewed stage can generate a client closure email."""
    publish(context)
    delivery.review_stage(
        context.project.pk, context.client, context.stage.pk,
        decisions(context, (context.first, 'approved')),
    )

    with pytest.raises(ValidationError) as rejected:
        _prepare(context)

    assert rejected.value.detail['code'] == 'stage_not_approved'
    assert DeliveryEvidenceEmail.objects.count() == 0


def test_prepare_copies_the_approved_public_document(context):
    """Fails if a closure attachment follows source edits instead of its approved version."""
    document = _approved(context, with_attachment=True)
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=document)
    with snapshot.file.open('rb') as source:
        published_bytes = source.read()

    prepared = _prepare(context, document_snapshot_ids=[snapshot.pk])
    email = DeliveryEvidenceEmail.objects.get(pk=prepared['id'])
    file = email.attachments.get()
    document.content_markdown = '# Sustitución interna\nNo es el PDF aprobado.'
    document.save(update_fields=['content_markdown', 'updated_at'])
    with file.file.open('rb') as source:
        frozen_bytes = source.read()

    assert prepared['attachments'][0]['sha256'] == hashlib.sha256(published_bytes).hexdigest()
    assert frozen_bytes == published_bytes
    history = email.closure_history['requirements']
    assert [(row['requirement_title'], row['publication_round'], row['channel']) for row in history] == [
        ('Guardar registro', 1, 'platform'), ('Editar registro', 1, 'platform'),
    ]
    assert set(history[0]) == {
        'requirement_id', 'requirement_key', 'requirement_title', 'requirement_version',
        'publication_id', 'publication_round', 'reviewed_at', 'reviewer', 'channel',
    }


def test_prepare_rejects_another_contracts_public_snapshot(context):
    """Fails if a real public document from another contract can be attached to this closure."""
    _approved(context)
    other_document = Document.objects.create(
        title='Contrato de otra entrega', project=context.project,
        client_user=context.client, is_client_visible=True,
        requires_signature=True, signed_by=context.client,
        signed_at=context.document.signed_at, signature_name='Cliente',
        content_markdown='# Otro contrato\nUn alcance independiente.',
        include_portada=False, include_subportada=False, include_contraportada=False,
    )
    other_contract = ProjectContract.objects.create(
        project=context.project, key='otro-contrato', title='Otro contrato',
        document=other_document, client_visible=True,
    )
    other_scope = DeliveryScope.objects.create(
        contract=other_contract, key='otro-alcance', title='Otro alcance',
    )
    other_phase = DeliveryPhase.objects.create(
        scope=other_scope, key='otra-fase', title='Otra fase',
    )
    other_stage = DeliveryStage.objects.create(
        phase=other_phase, key='otra-etapa', title='Otra etapa',
    )
    Requirement.objects.create(
        stage=other_stage, key='otro-requerimiento', title='Otra validación',
        guide=context.first.guide,
    )
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'contract',
        'target_id': other_contract.pk, 'document_id': other_document.pk,
    })
    delivery.publish_stage(context.project.pk, context.admin, other_stage.pk, {
        'expected_version': version(context), 'request_id': 'publish-other-contract',
    })
    other_snapshot = DeliveryDocumentSnapshot.objects.get(link__document=other_document)

    with pytest.raises(NotFound, match='documento publicado'):
        _prepare(context, document_snapshot_ids=[other_snapshot.pk])

    assert DeliveryEvidenceEmail.objects.count() == 0


def test_prepare_requires_the_approved_stage_to_remain_visible_to_the_client(context):
    """Fails if an approved stage under a hidden contract can still email the client."""
    _approved(context)
    context.contract.client_visible = False
    context.contract.save(update_fields=['client_visible'])

    with pytest.raises(ValidationError) as rejected:
        _prepare(context)

    assert rejected.value.detail['code'] == 'stage_not_client_visible'
    assert DeliveryEvidenceEmail.objects.count() == 0


def _close_after_an_objected_round(context):
    publish(context, 'closure-round-one')
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'closure-public-before',
        'level': 'stage', 'target_id': context.stage.pk,
        'requirement_ids': [context.second.pk], 'message': 'Prueba la validación inicial.',
    })
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'closure-internal-before',
        'level': 'stage', 'target_id': context.stage.pk,
        'requirement_ids': [], 'message': 'Nota interna que nunca se comparte.', 'is_internal': True,
    })
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(
        context, (context.first, 'approved'), (context.second, 'objected'),
    ))
    delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
        'expected_version': version(context), 'title': 'Editar registro corregido',
    }, context.second.pk)
    context.second.refresh_from_db()
    publish(context, 'closure-round-two')
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'closure-public-round-two',
        'level': 'requirement', 'target_id': context.second.pk,
        'requirement_ids': [context.second.pk], 'message': 'Ahora valida el ajuste publicado.',
    })
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, decisions(
        context, (context.second, 'approved'), request_id='closure-review-round-two',
    ))
    sibling = DeliveryStage.objects.create(phase=context.phase, key='sibling', title='Etapa ajena')
    DeliveryMessage.objects.create(
        project=context.project, actor=context.admin, level='stage', target_id=sibling.pk,
        message='Conversación de otra etapa.', is_internal=False,
    )
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'closure-public-after',
        'level': 'stage', 'target_id': context.stage.pk,
        'requirement_ids': [], 'message': 'Mensaje posterior al cierre.',
    })


def test_prepare_freezes_the_public_closure_record(context):
    """Fails if closure history omits an earlier objection or leaks private and post-close messages."""
    _close_after_an_objected_round(context)

    prepared = _prepare(context)
    history = DeliveryEvidenceEmail.objects.get(pk=prepared['id']).closure_history

    assert [item['round'] for item in history['publications']] == [1, 2]
    assert [(item['decision'], item['requirement_id']) for item in history['reviews']] == [
        ('approved', context.first.pk), ('objected', context.second.pk), ('approved', context.second.pk),
    ]
    assert [item['message'] for item in history['messages']] == [
        'Prueba la validación inicial.', 'Ahora valida el ajuste publicado.',
    ]
    assert 'source_references' not in str(history)
    assert 'Nota interna que nunca se comparte.' not in str(history)
    assert 'Mensaje posterior al cierre.' not in str(history)
    assert 'Conversación de otra etapa.' not in str(history)


def test_send_requires_the_human_review_confirmation(context):
    """Fails if an administrator can dispatch a frozen preview without confirming review."""
    _approved(context)
    prepared = _prepare(context)

    with pytest.raises(ValidationError) as rejected:
        _send(context, prepared, human_reviewed=False)

    assert rejected.value.detail['human_reviewed'] == ['Confirma que revisaste el correo antes de enviarlo.']
    assert DeliveryEvidenceEmail.objects.get(pk=prepared['id']).attempts.count() == 0


def test_send_records_a_sent_attempt_after_one_private_gateway_delivery(context):
    """Fails if sending skips durable success evidence or exposes attachments in public history."""
    document = _approved(context, with_attachment=True)
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=document)
    prepared = _prepare(context, document_snapshot_ids=[snapshot.pk])

    with patch('content.services.email_delivery_service.EmailDeliveryGateway.send', return_value=1) as gateway:
        result = _send(context, prepared)

    assert result['status'] == 'sent'
    assert result['attempts'][0]['status'] == 'sent'
    assert gateway.call_count == 1
    assert gateway.call_args.kwargs['private_attachments'] is True


def test_send_with_a_new_request_id_returns_the_existing_attempt(context):
    """Fails if a double click with a new request id sends the same prepared email twice."""
    _approved(context)
    prepared = _prepare(context)

    with patch('content.services.email_delivery_service.EmailDeliveryGateway.send', return_value=1) as gateway:
        _send(context, prepared)
        replay = _send(context, prepared, request_id='closure-send-second-click')

    assert replay['status'] == 'sent'
    assert len(replay['attempts']) == 1
    assert gateway.call_count == 1


def test_failed_send_needs_an_explicit_resend_preparation(context):
    """Fails if a failed closure email silently retries from the original preparation."""
    _approved(context)
    prepared = _prepare(context)

    marker = 'SYNTHETIC_PRIVATE_P5_20261001'
    with patch('content.services.email_delivery_service.EmailDeliveryGateway.send', side_effect=RuntimeError(marker)) as gateway:
        failed = _send(context, prepared)
        replay = _send(context, prepared, request_id='closure-send-retry')

    attempt = DeliveryEvidenceEmail.objects.get(pk=prepared['id']).attempts.get()
    log = EmailLog.objects.get(template_key='delivery_stage_approved_client')
    assert (
        failed['status'], replay['status'], replay['error_message'],
        attempt.error_message, log.error_message,
        marker not in f'{failed}{replay}', gateway.call_count,
    ) == (
        'failed', 'failed', 'No se pudo completar el envío de correo.',
        'No se pudo completar el envío de correo.',
        'No se pudo completar el envío de correo.', True, 1,
    )


def test_post_smtp_audit_error_marks_delivery_unknown_without_resending(context):
    """Fails if a post-SMTP audit error rewrites an accepted send as failed or retries it."""
    _approved(context)
    prepared = _prepare(context)

    with patch('django.core.mail.message.EmailMessage.send', return_value=1) as smtp_send, patch(
        'accounts.services.delivery_closure_email._record_gateway_send', side_effect=RuntimeError('audit storage unavailable'),
    ):
        unknown = _send(context, prepared)
        replay = _send(context, prepared, request_id='closure-send-after-audit-error')

    assert unknown['status'] == 'unknown'
    assert 'Correo aceptado' in unknown['error_message']
    assert replay['status'] == 'unknown'
    assert smtp_send.call_count == 1
    assert EmailDeliverySnapshot.objects.get(template_key='delivery_stage_approved_client').to_recipients == [
        context.client.email,
    ]


def test_resend_preparation_clones_the_original_frozen_attachment_bytes(context):
    """Fails if an explicit resend regenerates its body or reads a changed source document."""
    document = _approved(context, with_attachment=True)
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=document)
    original = _prepare(context, document_snapshot_ids=[snapshot.pk])
    original_email = DeliveryEvidenceEmail.objects.get(pk=original['id'])
    with original_email.attachments.get().file.open('rb') as source:
        original_bytes = source.read()
    document.content_markdown = '# Documento nuevo\nNo pertenece al reenvío.'
    document.save(update_fields=['content_markdown', 'updated_at'])

    resent = closure_email.prepare_stage_email_resend(
        context.project.pk, context.admin, original['id'],
        {'expected_version': version(context), 'request_id': 'closure-resend-1'},
    )
    resent_email = DeliveryEvidenceEmail.objects.get(pk=resent['id'])
    with resent_email.attachments.get().file.open('rb') as source:
        resent_bytes = source.read()

    assert resent['manifest_sha256'] == original['manifest_sha256']
    assert resent_email.resend_of_id == original_email.pk
    assert resent_bytes == original_bytes


def test_mcp_credential_cannot_read_a_rest_preparation(context):
    """Fails if an MCP credential can disclose a preview prepared through the REST channel."""
    _approved(context)
    prepared = _prepare(context)
    connector = McpConnector.objects.create(slug='closure-email', name='Closure email')
    credential = McpCredential.objects.create(
        connector=connector, label='closure-key', token_hash='f' * 64,
        actor=context.admin,
    )

    with pytest.raises(NotFound):
        closure_email.get_preparation(
            context.project.pk, context.admin, prepared['id'], mcp_credential=credential,
        )

    assert DeliveryEvidenceEmail.objects.get(pk=prepared['id']).mcp_credential_id is None


def test_other_administrator_cannot_read_a_personal_preparation(context):
    """Fails if an administrator can send or download a colleague's reviewed closure email."""
    _approved(context)
    prepared = _prepare(context)
    other = User.objects.create_user('other-admin', 'other-admin@example.test', 'test-password')
    UserProfile.objects.create(user=other, role='admin', is_onboarded=True, email_verified=True)

    with pytest.raises(PermissionDenied, match='quien preparó'):
        closure_email.get_preparation(context.project.pk, other, prepared['id'])

    assert closure_email.list_stage_emails(context.project.pk, other, context.stage.pk)['emails'] == []
