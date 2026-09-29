"""Keep the original annex validation across download, review, and delivery."""
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from freezegun import freeze_time

from content.models import EmailTemplateConfig, ProposalFormalization, ProposalFormalizationFile
from content.services.formalization_content import FormalizationError
from content.services.proposal_formalization_service import (
    MAX_ATTACHMENT_BYTES,
    document_bytes,
    prepare,
    send_preparation,
)
from content.tests.services import test_proposal_formalization_service as service_fixtures

pytestmark = pytest.mark.django_db
formalization_proposal = service_fixtures.formalization_proposal
formalization_payload = service_fixtures.formalization_payload
formalization_attachment = service_fixtures.formalization_attachment


@pytest.mark.parametrize(('size', 'expected_code'), [
    pytest.param(0, 'document_empty', id='empty'),
    pytest.param(MAX_ATTACHMENT_BYTES + 1, 'attachments_too_large', id='oversized'),
])
def test_prepare_rejects_an_unusable_source_attachment(
    formalization_proposal, formalization_attachment, admin_user,
    formalization_payload, size, expected_code,
):
    formalization_attachment.file.save('unusable.pdf', ContentFile(b'x' * size))
    payload = {**formalization_payload, 'additional_doc_ids': [formalization_attachment.pk]}

    with pytest.raises(FormalizationError) as error:
        prepare(formalization_proposal, admin_user, payload)

    assert error.value.code == expected_code
    assert not ProposalFormalization.objects.filter(proposal=formalization_proposal).exists()


def test_prepare_rejects_a_missing_source_attachment(
    formalization_proposal, formalization_attachment, admin_user, formalization_payload,
):
    formalization_attachment.file.storage.delete(formalization_attachment.file.name)
    payload = {**formalization_payload, 'additional_doc_ids': [formalization_attachment.pk]}

    with pytest.raises(FormalizationError) as error:
        prepare(formalization_proposal, admin_user, payload)

    assert error.value.code == 'document_unavailable'
    assert not ProposalFormalization.objects.filter(proposal=formalization_proposal).exists()


def test_send_rejects_an_expired_review(
    mailoutbox, formalization_proposal, admin_user, formalization_payload,
):
    with freeze_time('2026-09-29 12:00:00'):
        preparation = prepare(formalization_proposal, admin_user, formalization_payload)

    with freeze_time('2026-09-30 12:00:00'), pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    preparation.refresh_from_db()
    assert error.value.code == 'expired_preparation'
    assert error.value.status == 410
    assert preparation.status == ProposalFormalization.Status.PREPARED
    assert len(mailoutbox) == 0


def test_send_rejects_a_template_disabled_after_review(
    mailoutbox, formalization_proposal, admin_user, formalization_payload,
):
    """A previously reviewed package still respects the current send policy."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)
    EmailTemplateConfig.objects.update_or_create(
        template_key='proposal_formalization', defaults={'is_active': False},
    )

    with pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    preparation.refresh_from_db()
    assert error.value.code == 'template_disabled'
    assert preparation.status == ProposalFormalization.Status.PREPARED
    assert len(mailoutbox) == 0


def test_send_rejects_a_source_attachment_lost_after_review(
    mailoutbox, formalization_proposal, formalization_attachment,
    admin_user, formalization_payload,
):
    """The frozen copy cannot bypass validation of a missing source document."""
    payload = {**formalization_payload, 'additional_doc_ids': [formalization_attachment.pk]}
    preparation = prepare(formalization_proposal, admin_user, payload)
    formalization_attachment.file.storage.delete(formalization_attachment.file.name)

    with pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    preparation.refresh_from_db()
    assert error.value.code == 'document_unavailable'
    assert preparation.status == ProposalFormalization.Status.PREPARED
    assert len(mailoutbox) == 0


def test_send_rejects_a_modified_reviewed_pdf(
    mailoutbox, formalization_proposal, admin_user, formalization_payload,
):
    """Only the exact PDF bytes approved during review may reach the recipient."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)
    attachment = preparation.files.get(key='commercial')
    with attachment.file.storage.open(attachment.file.name, 'wb') as stored:
        stored.write(b'%PDF-content-not-reviewed-by-the-user')

    with pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    preparation.refresh_from_db()
    assert error.value.code == 'attachment_changed'
    assert error.value.status == 409
    assert preparation.status == ProposalFormalization.Status.PREPARED
    assert len(mailoutbox) == 0


@pytest.fixture
def failing_private_storage(monkeypatch):
    storage = ProposalFormalizationFile._meta.get_field('file').storage
    original_save = storage._save
    saved_paths = []

    def fail_after_first_file(name, content):
        if saved_paths:
            raise OSError('Private storage unavailable')
        saved_path = original_save(name, content)
        saved_paths.append(saved_path)
        return saved_path

    monkeypatch.setattr(storage, '_save', fail_after_first_file)
    return storage, saved_paths


def test_prepare_rolls_back_a_partially_written_package(
    formalization_proposal, admin_user, formalization_payload, failing_private_storage,
):
    storage, saved_paths = failing_private_storage

    with pytest.raises(OSError, match='Private storage unavailable'):
        prepare(formalization_proposal, admin_user, formalization_payload)

    assert len(saved_paths) == 1
    assert not storage.exists(saved_paths[0])
    assert not ProposalFormalization.objects.filter(proposal=formalization_proposal).exists()
    assert not ProposalFormalizationFile.objects.exists()


@pytest.mark.parametrize('kind', ['commercial', 'technical'])
def test_download_reports_a_pdf_output_failure(formalization_proposal, kind):
    with patch('reportlab.pdfgen.canvas.Canvas.save', side_effect=OSError('PDF output unavailable')):
        with pytest.raises(FormalizationError) as error:
            document_bytes(formalization_proposal, kind)

    assert error.value.code == 'pdf_generation_failed'
    assert error.value.status == 500
