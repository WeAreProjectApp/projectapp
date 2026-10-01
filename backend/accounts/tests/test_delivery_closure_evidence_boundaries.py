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

    history = prepare_email(context)['closure_history']

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


def test_summary_pdf_preserves_the_complete_approval_trace(context):
    """Fails if the optional PDF truncates the title or omits the approver and contractual trace."""
    context.stage.title = (
        'Validacion de registros para el cliente '
        + 'recorrido de acceso y revision ' * 5
        + 'FIN_DEL_TITULO_COMPLETO'
    )
    context.stage.save(update_fields=['title'])
    context.client.first_name = 'Wilson'
    context.client.last_name = 'Rojas'
    context.client.save(update_fields=['first_name', 'last_name'])
    approve_stage(context)
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
    assert filename == 'constancia-cierre-etapa.pdf'
    assert content_type == 'application/pdf'
