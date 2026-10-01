"""Public closure evidence survives historical dates and storage failures."""
import io
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from pypdf import PdfReader

from accounts.models import (
    DeliveryDocumentSnapshot,
    DeliveryEvidenceEmail,
    DeliveryEvidenceEmailFile,
    DeliveryOperation,
)
from accounts.services import delivery_closure_email as closure_email
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_authoring_helpers import pdf_bytes
from accounts.tests.delivery_helpers import (
    RECORDED_AT,
    build_delivery_context,
    decisions,
    publish,
    version,
)
from content.models import CommunicationMessage, CommunicationThread, Document


pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT) as clock:
        result = build_delivery_context()
        result.clock = clock
        yield result


def prepare_email(context, **overrides):
    values = {
        'expected_version': version(context),
        'request_id': 'prepare-closure',
        'message': 'Conservamos la aprobación de esta etapa.',
    }
    values.update(overrides)
    return closure_email.prepare_stage_email(
        context.project.pk, context.admin, context.stage.pk, values,
    )


def approve_stage(context):
    publish(context)
    delivery.review_stage(
        context.project.pk, context.client, context.stage.pk,
        decisions(context, (context.first, 'approved'), (context.second, 'approved')),
    )


@pytest.fixture
def approved_attachment(context):
    document = Document.objects.create(
        title='Guía publicada', project=context.project, client_user=context.client,
        is_client_visible=True, content_markdown='# Guía\nDocumento compartido.',
        include_portada=False, include_subportada=False, include_contraportada=False,
    )
    document.generated_file.save('published-guide.pdf', ContentFile(pdf_bytes()))
    delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': 'stage',
        'target_id': context.stage.pk, 'document_id': document.pk,
    })
    approve_stage(context)
    return DeliveryDocumentSnapshot.objects.get(link__document=document)


def private_storage_state(storage):
    root = Path(storage.location)
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob('*') if path.is_file()
    }


class SecondStorageWriteFailure:
    """Exercise the real first write before a private-storage boundary failure."""

    def __init__(self, real_save):
        self.real_save = real_save
        self.writes = 0

    def __call__(self, *args, **kwargs):
        self.writes += 1
        if self.writes == 2:
            raise OSError('Private storage second write failed.')
        return self.real_save(*args, **kwargs)


def history_messages(history):
    return [message['message'] for message in history['messages']]


def review_provenance(history):
    return [
        (review['author'], review['reviewer'], review['channel'], review['is_external'],
         review['reviewed_at'], review['created_at'])
        for review in history['reviews']
    ]


def publication_ids(history):
    return [publication['id'] for publication in history['publications']]


def add_preparations(context, snapshot, count):
    for index in range(1, count + 1):
        prepare_email(
            context, request_id=f'query-prepare-{index}',
            document_snapshot_ids=[snapshot.pk], include_record_pdf=True,
        )


def attachment_count(result):
    return sum(len(email['attachments']) for email in result['emails'])


def normalized_pdf_text(content):
    reader = PdfReader(io.BytesIO(content))
    return ' '.join(' '.join(page.extract_text() for page in reader.pages).split())


def close_with_public_history(context, *, objection='No puedo editar el registro.', closing='Apruebo la etapa completa.'):
    context.client.first_name = 'Wilson'
    context.client.last_name = 'Rojas'
    context.client.save(update_fields=['first_name', 'last_name'])
    context.admin.first_name = 'Elena'
    context.admin.last_name = 'Equipo'
    context.admin.save(update_fields=['first_name', 'last_name'])
    publish(context)
    context.clock.move_to(RECORDED_AT + timedelta(minutes=1))
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'public-before-review',
        'level': 'stage', 'target_id': context.stage.pk,
        'message': 'Revisa el registro publicado.',
    })
    delivery.add_message(context.project.pk, context.admin, {
        'expected_version': version(context), 'request_id': 'private-before-review',
        'level': 'stage', 'target_id': context.stage.pk,
        'message': 'PRIVATE_TEAM_NOTE', 'is_internal': True,
    })
    context.clock.move_to(RECORDED_AT + timedelta(minutes=2))
    response = decisions(context, (context.first, 'approved'), (context.second, 'objected'))
    response['decisions'][1]['message'] = objection
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, response)
    context.clock.move_to(RECORDED_AT + timedelta(minutes=3))
    delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
        'expected_version': version(context), 'title': 'Editar registro corregido',
    }, context.second.pk)
    context.second.refresh_from_db()
    publish(context, 'corrected-round')
    context.clock.move_to(RECORDED_AT + timedelta(minutes=4))
    response = decisions(context, (context.second, 'approved'), request_id='closing-review')
    response['message'] = closing
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, response)
    context.clock.move_to(RECORDED_AT + timedelta(minutes=5))
    delivery.add_message(context.project.pk, context.client, {
        'expected_version': version(context), 'request_id': 'after-closing-review',
        'level': 'stage', 'target_id': context.stage.pk, 'message': 'POST_CLOSURE_MESSAGE',
    })


def send_email(context, preparation, request_id='send-public-record'):
    return closure_email.send_stage_email(context.project.pk, context.admin, preparation['id'], {
        'expected_version': version(context), 'request_id': request_id,
        'preview_sha256': preparation['manifest_sha256'], 'human_reviewed': True,
    })


def test_delivered_email_contains_the_public_closure_record(context, mailoutbox):
    """Fails if a message without attachments delivers a summary instead of public evidence."""
    close_with_public_history(context)
    prepared = prepare_email(context, message='')
    reloaded = closure_email.get_preparation(context.project.pk, context.admin, prepared['id'])

    result = send_email(context, reloaded)

    assert result['status'] == 'sent'
    assert prepared['attachments'] == []
    assert len(mailoutbox) == 1
    assert mailoutbox[0].body == prepared['text_body'] == reloaded['text_body']
    assert mailoutbox[0].alternatives[0].content == prepared['html_body'] == reloaded['html_body']
    assert 'No puedo editar el registro.' in mailoutbox[0].body
    assert 'Apruebo la etapa completa.' in mailoutbox[0].body
    assert 'No puedo editar el registro.' in mailoutbox[0].alternatives[0].content
    assert 'Apruebo la etapa completa.' in mailoutbox[0].alternatives[0].content
    assert 'Wilson Rojas' in mailoutbox[0].body
    assert 'Elena Equipo' in mailoutbox[0].body
    assert (RECORDED_AT + timedelta(minutes=2)).isoformat() in mailoutbox[0].body
    assert (RECORDED_AT + timedelta(minutes=4)).isoformat() in mailoutbox[0].body
    assert 'Editar registro (v1, ronda 1)' in mailoutbox[0].body
    assert 'Editar registro corregido (v2, ronda 2)' in mailoutbox[0].body
    assert mailoutbox[0].body.index('Revisa el registro publicado.') < mailoutbox[0].body.index('No puedo editar el registro.')
    assert 'PRIVATE_TEAM_NOTE' not in mailoutbox[0].body + mailoutbox[0].alternatives[0].content
    assert 'POST_CLOSURE_MESSAGE' not in mailoutbox[0].body + mailoutbox[0].alternatives[0].content


def test_closure_html_escapes_public_conversation_text(context):
    """Fails if client-authored markup becomes executable HTML in the prepared message."""
    close_with_public_history(context, objection='<script>alert("objeción")</script>', closing='<b>Apruebo</b>')

    prepared = prepare_email(context)

    assert '<script>alert("objeción")</script>' in prepared['text_body']
    assert '<b>Apruebo</b>' in prepared['text_body']
    assert '&lt;script&gt;alert(&quot;objeción&quot;)&lt;/script&gt;' in prepared['html_body']
    assert '&lt;b&gt;Apruebo&lt;/b&gt;' in prepared['html_body']
    assert '<script>alert(' not in prepared['html_body']
    assert '<b>Apruebo</b>' not in prepared['html_body']


def test_resent_email_keeps_the_original_conversation_record(context, mailoutbox):
    """Fails if a resend rebuilds the record from a renamed author instead of the frozen preview."""
    close_with_public_history(context)
    prepared = prepare_email(context)
    send_email(context, prepared)
    context.client.first_name = 'NEW_AUTHOR_NAME'
    context.client.save(update_fields=['first_name'])
    resent = closure_email.prepare_stage_email_resend(context.project.pk, context.admin, prepared['id'], {
        'expected_version': version(context), 'request_id': 'resend-public-record',
    })

    result = send_email(context, resent, 'send-frozen-resend')

    assert result['status'] == 'sent'
    assert len(mailoutbox) == 2
    assert mailoutbox[1].body == mailoutbox[0].body == prepared['text_body']
    assert mailoutbox[1].alternatives[0].content == mailoutbox[0].alternatives[0].content == prepared['html_body']
    assert resent['closure_history'] == prepared['closure_history']
    assert resent['manifest_sha256'] == prepared['manifest_sha256']
    assert 'No puedo editar el registro.' in mailoutbox[1].body
    assert 'Apruebo la etapa completa.' in mailoutbox[1].body
    assert 'NEW_AUTHOR_NAME' not in mailoutbox[1].body


def test_closure_record_shows_an_equivalent_decision_message_once(context):
    """Fails if the same client's simultaneous review repeats its shared message."""
    publish(context)
    context.clock.move_to(RECORDED_AT + timedelta(minutes=1))
    request = decisions(context, (context.first, 'approved'), (context.second, 'approved'))
    request['decisions'][0]['message'] = 'Conforme con los dos casos.'
    request['decisions'][1]['message'] = 'Conforme con los dos casos.'
    request['message'] = 'Conforme con los dos casos.'
    delivery.review_stage(context.project.pk, context.client, context.stage.pk, request)

    prepared = prepare_email(context)

    assert prepared['text_body'].count('Conforme con los dos casos.') == 1
    assert prepared['html_body'].count('Conforme con los dos casos.') == 1
    assert 'Guardar registro (v1, ronda 1)' in prepared['text_body']
    assert 'Editar registro (v1, ronda 1)' in prepared['text_body']


def test_closure_includes_the_final_review_message(context):
    """Fails if the closing operation loses its message or includes later discussion."""
    publish(context)
    request = decisions(
        context, (context.first, 'approved'), (context.second, 'approved'),
        request_id='final-review-with-message',
    )
    request['message'] = 'Aprobamos la etapa completa.'
    with freeze_time(RECORDED_AT + timedelta(minutes=10), auto_tick_seconds=1):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, request)
    operation = DeliveryOperation.objects.get(
        project=context.project, request_id='final-review-with-message',
    )
    context.clock.move_to(operation.created_at + timedelta(minutes=1))
    delivery.add_message(context.project.pk, context.client, {
        'expected_version': version(context), 'request_id': 'post-close-message',
        'level': 'stage', 'target_id': context.stage.pk,
        'message': 'Comentario recibido después del cierre.',
    })

    prepared = prepare_email(context)

    assert history_messages(prepared['closure_history']) == ['Aprobamos la etapa completa.']
    assert prepared['closure_history']['closed_at'] == operation.created_at.isoformat()


def test_historical_closure_preserves_the_original_reviewer(context):
    """Fails if backdated approval loses the shared round or exposes private source data."""
    context.client.first_name = 'Wilson'
    context.client.last_name = 'Rojas'
    context.client.save(update_fields=['first_name', 'last_name'])
    publish(context)
    publication = context.stage.publications.get()
    occurred_at = RECORDED_AT - timedelta(days=15)
    thread = CommunicationThread.objects.create(
        client=context.client.profile, project=context.project, title='Aprobación recibida',
    )
    source = CommunicationMessage.objects.create(
        thread=thread, direction='incoming', status='received', channel='email',
        content='Apruebo ambos requerimientos.\nPRIVATE_ARCHIVE_TEXT',
        subject='PRIVATE_ARCHIVE_SUBJECT', occurred_at=occurred_at,
    )
    request = decisions(context, (context.first, 'approved'), (context.second, 'approved'))
    request.update({
        'client_statement': True, 'source_message_id': source.pk,
        'evidence_message': 'Apruebo ambos requerimientos.',
    })
    delivery.review_stage(
        context.project.pk, context.admin, context.stage.pk, request, historical=True,
    )

    prepared = prepare_email(context)
    history = prepared['closure_history']

    assert publication_ids(history) == [publication.pk]
    assert review_provenance(history) == [
        ('admin@example.test', 'Wilson Rojas', 'email', True,
         occurred_at.isoformat(), RECORDED_AT.isoformat()),
        ('admin@example.test', 'Wilson Rojas', 'email', True,
         occurred_at.isoformat(), RECORDED_AT.isoformat()),
    ]
    serialized = json.dumps(history)
    assert 'source_snapshot' not in serialized
    assert 'source_message' not in serialized
    assert 'PRIVATE_ARCHIVE_TEXT' not in serialized
    assert 'PRIVATE_ARCHIVE_SUBJECT' not in serialized
    assert 'Wilson Rojas' in prepared['text_body']
    assert occurred_at.isoformat() in prepared['text_body']
    assert 'PRIVATE_ARCHIVE_TEXT' not in prepared['text_body'] + prepared['html_body']
    assert 'PRIVATE_ARCHIVE_SUBJECT' not in prepared['text_body'] + prepared['html_body']


def test_preparation_cleans_files_after_the_second_storage_write_fails(context, approved_attachment):
    """Fails if a later attachment failure leaves a preparation or an orphaned PDF."""
    storage = DeliveryEvidenceEmailFile._meta.get_field('file').storage
    before = private_storage_state(storage)
    failure = SecondStorageWriteFailure(storage.save)

    with patch.object(storage, 'save', side_effect=failure):
        with pytest.raises(OSError, match='second write failed'):
            prepare_email(
                context, document_snapshot_ids=[approved_attachment.pk], include_record_pdf=True,
            )

    assert DeliveryEvidenceEmail.objects.count() == 0
    assert DeliveryEvidenceEmailFile.objects.count() == 0
    assert private_storage_state(storage) == before


def test_resend_cleans_new_files_after_the_second_storage_write_fails(context, approved_attachment):
    """Fails if a failed resend leaks copies or damages the original approved evidence."""
    original = prepare_email(
        context, document_snapshot_ids=[approved_attachment.pk], include_record_pdf=True,
    )
    storage = DeliveryEvidenceEmailFile._meta.get_field('file').storage
    before = private_storage_state(storage)
    original_rows = list(DeliveryEvidenceEmail.objects.values())
    original_files = list(DeliveryEvidenceEmailFile.objects.order_by('id').values())
    failure = SecondStorageWriteFailure(storage.save)

    with patch.object(storage, 'save', side_effect=failure):
        with pytest.raises(OSError, match='second write failed'):
            closure_email.prepare_stage_email_resend(
                context.project.pk, context.admin, original['id'], {
                    'expected_version': version(context), 'request_id': 'failed-resend',
                },
            )

    assert list(DeliveryEvidenceEmail.objects.values()) == original_rows
    assert list(DeliveryEvidenceEmailFile.objects.order_by('id').values()) == original_files
    assert private_storage_state(storage) == before


def test_listing_preparations_has_constant_query_cost(context, approved_attachment):
    """Fails if each prepared email adds attachment, attempt or workspace queries."""
    prepare_email(
        context, request_id='query-prepare-0',
        document_snapshot_ids=[approved_attachment.pk], include_record_pdf=True,
    )
    with CaptureQueriesContext(connection) as single_queries:
        single = closure_email.list_stage_emails(context.project.pk, context.admin, context.stage.pk)
    add_preparations(context, approved_attachment, 9)

    with CaptureQueriesContext(connection) as ten_queries:
        ten = closure_email.list_stage_emails(context.project.pk, context.admin, context.stage.pk)

    assert len(single['emails']) == 1
    assert len(ten['emails']) == 10
    assert attachment_count(ten) == 20
    assert len(ten_queries) == len(single_queries)


def test_record_pdf_preserves_the_complete_public_closure_trace(context):
    """Fails if the PDF omits a public objection, closing message or contractual trace."""
    context.stage.title = (
        'Validacion de registros para el cliente '
        + 'recorrido de acceso y revision ' * 5
        + 'FIN_DEL_TITULO_COMPLETO'
    )
    context.stage.save(update_fields=['title'])
    context.client.first_name = 'Wilson'
    context.client.last_name = 'Rojas'
    context.client.save(update_fields=['first_name', 'last_name'])
    close_with_public_history(context)
    prepared = prepare_email(context, include_record_pdf=True)

    content, filename, content_type = closure_email.download_attachment(
        context.project.pk, context.admin, prepared['id'], prepared['attachments'][0]['id'],
    )
    text = normalized_pdf_text(content)

    assert context.stage.title in text
    assert 'Contrato original / Alcance / Fase' in text
    assert 'Wilson Rojas' in text
    assert RECORDED_AT.isoformat() in text
    assert 'v1, ronda 1' in text
    assert 'No puedo editar el registro.' in text
    assert 'Apruebo la etapa completa.' in text
    assert 'Editar registro corregido (v2, ronda 2)' in text
    assert 'PRIVATE_TEAM_NOTE' not in text
    assert 'POST_CLOSURE_MESSAGE' not in text
    assert filename == 'constancia-cierre-etapa.pdf'
    assert content_type == 'application/pdf'
