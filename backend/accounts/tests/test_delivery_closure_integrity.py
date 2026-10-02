"""Closure evidence fails closed when private files or reviewed requests change."""
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from accounts.models import DeliveryDocumentSnapshot, DeliveryEvidenceEmail
from accounts.services import delivery_closure_email as closure_email
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_workflow import DeliveryConflict
from accounts.tests.delivery_authoring_helpers import pdf_bytes
from accounts.tests.delivery_helpers import (
    RECORDED_AT, build_delivery_context, decisions, publish, version,
)
from content.models import Document, EmailDeliverySnapshot


pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_delivery_context()


@pytest.fixture
def approved_document(context):
    document = Document.objects.create(
        title='Guía aprobada', project=context.project, client_user=context.client,
        is_client_visible=True, content_markdown='# Guía\nDocumento compartido.',
        include_portada=False, include_subportada=False, include_contraportada=False,
    )
    document.generated_file.save('approved-guide.pdf', ContentFile(pdf_bytes()))
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'stage',
        'target_id': context.stage.pk, 'document_id': document.pk,
    })
    publish(context)
    delivery.review_stage(
        context.project.pk, context.client, context.stage.pk,
        decisions(context, (context.first, 'approved'), (context.second, 'approved')),
    )
    return DeliveryDocumentSnapshot.objects.get(link__document=document)


def prepare(context, snapshot, **overrides):
    values = {
        'expected_version': version(context), 'request_id': 'prepare-integrity',
        'document_snapshot_ids': [snapshot.pk], 'message': 'Aprobación conservada.',
    }
    values.update(overrides)
    return closure_email.prepare_stage_email(
        context.project.pk, context.admin, context.stage.pk, values,
    )


def send(context, prepared, **overrides):
    values = {
        'expected_version': version(context), 'request_id': 'send-integrity',
        'preview_sha256': prepared['manifest_sha256'], 'human_reviewed': True,
    }
    values.update(overrides)
    return closure_email.send_stage_email(
        context.project.pk, context.admin, prepared['id'], values,
    )


def resend(context, prepared, request_id='resend-integrity'):
    return closure_email.prepare_stage_email_resend(
        context.project.pk, context.admin, prepared['id'], {
            'expected_version': version(context), 'request_id': request_id,
        },
    )


def remove_file(field):
    field.storage.delete(field.name)


def replace_file(field):
    with field.open('wb') as stream:
        stream.write(b'Un archivo que no pertenece a la evidencia aprobada.')


@pytest.fixture(params=[
    pytest.param((remove_file, 'attachment_unavailable'), id='missing'),
    pytest.param((replace_file, 'attachment_integrity'), id='modified'),
])
def damaged_file(request):
    return request.param


def stored_files(storage):
    return {
        str(path.relative_to(storage.location)): path.read_bytes()
        for path in Path(storage.location).rglob('*') if path.is_file()
    }


def test_prepare_rejects_damaged_public_evidence(context, approved_document, damaged_file, mailoutbox):
    """A public snapshot cannot seed a closure after its exact bytes disappear or change."""
    damage, error_code = damaged_file
    damage(approved_document.file)
    before = stored_files(approved_document.file.storage)

    with pytest.raises(ValidationError) as rejected:
        prepare(context, approved_document)

    assert rejected.value.detail['code'] == error_code
    assert DeliveryEvidenceEmail.objects.count() == 0
    assert stored_files(approved_document.file.storage) == before
    assert mailoutbox == []


def test_send_records_damaged_attachment_failure(context, approved_document, damaged_file, mailoutbox):
    """A damaged frozen attachment produces a visible failed receipt before mail transport."""
    prepared = prepare(context, approved_document)
    email = DeliveryEvidenceEmail.objects.get(pk=prepared['id'])
    attachment = email.attachments.get()
    damage, error_code = damaged_file
    damage(attachment.file)

    result = send(context, prepared)

    assert result['status'] == 'failed'
    assert result['attempts'][0]['status'] == 'failed'
    assert error_code in result['error_message']
    assert email.attempts.count() == 1
    assert EmailDeliverySnapshot.objects.filter(template_key=closure_email.TEMPLATE_KEY).count() == 0
    assert mailoutbox == []


def test_resend_rejects_damaged_original_attachment(context, approved_document, damaged_file, mailoutbox):
    """A failed clone leaves the original evidence and storage intact without mailing it."""
    prepared = prepare(context, approved_document)
    email = DeliveryEvidenceEmail.objects.get(pk=prepared['id'])
    attachment = email.attachments.get()
    damage, error_code = damaged_file
    damage(attachment.file)
    before = stored_files(attachment.file.storage)

    with pytest.raises(ValidationError) as rejected:
        resend(context, prepared)

    assert rejected.value.detail['code'] == error_code
    assert DeliveryEvidenceEmail.objects.count() == 1
    assert email.resend_preparations.count() == 0
    assert stored_files(attachment.file.storage) == before
    assert mailoutbox == []


def test_download_rejects_damaged_closure_attachment(context, approved_document, damaged_file):
    """The authorized download refuses bytes that no longer match the reviewed evidence."""
    prepared = prepare(context, approved_document)
    attachment = DeliveryEvidenceEmail.objects.get(pk=prepared['id']).attachments.get()
    damage, error_code = damaged_file
    damage(attachment.file)

    with pytest.raises(ValidationError) as rejected:
        closure_email.download_attachment(
            context.project.pk, context.admin, prepared['id'], attachment.pk,
        )

    assert rejected.value.detail['code'] == error_code


def test_repeated_preparation_returns_original_evidence(context, approved_document, mailoutbox):
    """Repeating an identical preparation keeps one immutable copy and its private files."""
    prepared = prepare(context, approved_document, include_record_pdf=True)
    email = DeliveryEvidenceEmail.objects.get(pk=prepared['id'])
    storage = email.attachments.first().file.storage
    before = stored_files(storage)

    replay = prepare(context, approved_document, include_record_pdf=True)

    assert replay['id'] == prepared['id']
    assert replay['manifest_sha256'] == prepared['manifest_sha256']
    assert DeliveryEvidenceEmail.objects.count() == 1
    assert stored_files(storage) == before
    assert mailoutbox == []


def test_preparation_request_cannot_replace_reviewed_message(context, approved_document, mailoutbox):
    """Reusing the request identifier with another message cannot overwrite frozen evidence."""
    prepared = prepare(context, approved_document)

    with pytest.raises(DeliveryConflict):
        prepare(context, approved_document, message='Un cierre diferente.')

    email = DeliveryEvidenceEmail.objects.get(pk=prepared['id'])
    assert email.text_body == prepared['text_body']
    assert email.manifest_sha256 == prepared['manifest_sha256']
    assert DeliveryEvidenceEmail.objects.count() == 1
    assert mailoutbox == []


def test_repeated_resend_preparation_returns_original_clone(context, approved_document, mailoutbox):
    """A repeated explicit resend request preserves one clone without duplicate files or mail."""
    prepared = prepare(context, approved_document)
    cloned = resend(context, prepared)
    email = DeliveryEvidenceEmail.objects.get(pk=cloned['id'])
    storage = email.attachments.get().file.storage
    before = stored_files(storage)

    replay = resend(context, prepared)

    assert replay['id'] == cloned['id']
    assert replay['manifest_sha256'] == prepared['manifest_sha256']
    assert DeliveryEvidenceEmail.objects.count() == 2
    assert stored_files(storage) == before
    assert mailoutbox == []


def test_resend_request_cannot_reuse_another_preparation(context, approved_document, mailoutbox):
    """A resend request cannot claim the identity of an unrelated prepared email."""
    prepared = prepare(context, approved_document)
    other = prepare(context, approved_document, request_id='other-preparation')

    with pytest.raises(DeliveryConflict):
        resend(context, prepared, request_id='other-preparation')

    assert DeliveryEvidenceEmail.objects.count() == 2
    assert DeliveryEvidenceEmail.objects.get(pk=other['id']).resend_of_id is None
    assert mailoutbox == []


def test_repeated_send_returns_original_receipt(context, approved_document, mailoutbox):
    """Repeating the same reviewed send request delivers one exact private email."""
    prepared = prepare(context, approved_document)
    sent = send(context, prepared)

    replay = send(context, prepared)

    assert sent['status'] == replay['status'] == 'sent'
    assert replay['attempts'] == sent['attempts']
    assert DeliveryEvidenceEmail.objects.get(pk=prepared['id']).attempts.count() == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].body == prepared['text_body']
    assert mailoutbox[0].alternatives[0].content == prepared['html_body']


@pytest.mark.parametrize('overrides', [
    pytest.param({'expected_version': 0}, id='stale-workspace'),
    pytest.param({'preview_sha256': '0' * 64}, id='different-preview'),
])
def test_send_rejects_a_changed_reviewed_context(context, approved_document, overrides, mailoutbox):
    """A stale workspace or different preview blocks dispatch before claiming any attempt."""
    prepared = prepare(context, approved_document)

    with pytest.raises(DeliveryConflict):
        send(context, prepared, **overrides)

    assert DeliveryEvidenceEmail.objects.get(pk=prepared['id']).attempts.count() == 0
    assert mailoutbox == []
