"""Private retention through the common capture, history and resend paths."""
import hashlib
import logging
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from django.core import mail
from django.core.files.storage import FileSystemStorage
from django.urls import reverse

from content.email_copy_families import PLATFORM
from content.models import EmailAttachmentSnapshot, EmailDeliverySnapshot, EmailLog
from content.services.email_delivery_service import EmailDeliveryGateway, EmailMultiAlternatives
from content.services.email_snapshot_service import (
    EmailSnapshotCaptureError,
    capture_delivery_snapshot,
    resend_email_log,
)


pytestmark = pytest.mark.django_db
TEMPLATE_KEY = 'document_signed_client'
ATTACHMENT_BYTES = b'%PDF-1.7\nApproved version\n\x00\xff\n%%EOF'


@pytest.fixture(autouse=True)
def isolated_email_files(settings, tmp_path):
    settings.MAILERS = {
        'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'},
    }
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    settings.PRIVATE_MEDIA_ROOT = str(tmp_path / 'private')
    settings.STORAGES = {
        **settings.STORAGES,
        'private': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
            'OPTIONS': {'location': settings.PRIVATE_MEDIA_ROOT, 'base_url': None},
        },
    }
    mail.outbox = []


def evidence_message():
    message = EmailMultiAlternatives(
        subject='Etapa aprobada', body='La etapa fue aprobada.',
        from_email='team@projectapp.co', to=['client@example.com'],
    )
    message.attach_alternative('<p>La etapa fue aprobada.</p>', 'text/html')
    message.attach('evidence.pdf', ATTACHMENT_BYTES, 'application/pdf')
    return message


def captured_evidence(*, private=True):
    return capture_delivery_snapshot(
        evidence_message(),
        delivery_id=UUID('10000000-0000-4000-8000-000000000001'),
        template_key=TEMPLATE_KEY, classification='client', family=PLATFORM,
        private_attachments=private,
    )


def delivered_evidence(*, private=True):
    EmailDeliveryGateway.send(
        evidence_message(), template_key=TEMPLATE_KEY,
        private_attachments=private,
    )
    return EmailLog.objects.select_related('snapshot__body').get(
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    )


def attachment_download_url(log, attachment):
    return reverse('standalone-email-attachment', kwargs={
        'log_id': log.pk, 'attachment_id': attachment.pk,
    })


def test_capture_retains_attachment_outside_public_media(settings):
    snapshot = captured_evidence()

    attachment = snapshot.attachments.get()

    assert Path(attachment.file.path).is_relative_to(Path(settings.PRIVATE_MEDIA_ROOT))
    assert Path(attachment.file.path).read_bytes() == ATTACHMENT_BYTES
    assert attachment.sha256 == hashlib.sha256(ATTACHMENT_BYTES).hexdigest()
    assert list(Path(settings.MEDIA_ROOT).rglob('*')) == []


def test_reloaded_private_attachment_reads_exact_bytes():
    snapshot = captured_evidence()
    attachment_id = snapshot.attachments.get().pk

    reloaded = EmailAttachmentSnapshot.objects.get(pk=attachment_id)
    with reloaded.file.open('rb') as retained:
        actual_bytes = retained.read()

    assert actual_bytes == ATTACHMENT_BYTES
    assert reloaded.file.name.startswith('private-email-history/')
    assert reloaded.sha256 == hashlib.sha256(actual_bytes).hexdigest()


def test_history_download_streams_private_attachment(admin_client):
    log = delivered_evidence()
    attachment = log.snapshot.attachments.get()

    response = admin_client.get(attachment_download_url(log, attachment))

    assert response.status_code == 200
    assert b''.join(response.streaming_content) == ATTACHMENT_BYTES
    assert response['Content-Type'] == 'application/pdf'
    assert response['Cache-Control'] == 'private, no-store'


def test_history_download_rejects_anonymous_private_attachment(api_client):
    log = delivered_evidence()
    attachment = log.snapshot.attachments.get()

    response = api_client.get(attachment_download_url(log, attachment))

    assert response.status_code == 401
    assert not response.streaming


def test_resend_keeps_private_attachment_without_opt_in(settings):
    original = delivered_evidence()
    original_attachment = original.snapshot.attachments.get()

    resent = resend_email_log(original, ['client@example.com'])
    attachment = resent.snapshot.attachments.get()

    assert attachment.file.name.startswith('private-email-history/')
    assert attachment.sha256 == original_attachment.sha256
    assert Path(attachment.file.path).read_bytes() == ATTACHMENT_BYTES
    assert resent.snapshot.resend_of_id == original.snapshot_id
    assert list(Path(settings.MEDIA_ROOT).rglob('*')) == []


def test_gateway_resend_inherits_private_storage(settings):
    original = captured_evidence()

    accepted = EmailDeliveryGateway.send(
        evidence_message(), template_key=TEMPLATE_KEY, resend_of=original,
    )
    attachment = EmailDeliverySnapshot.objects.get(resend_of=original).attachments.get()

    assert accepted == 1
    assert attachment.file.name.startswith('private-email-history/')
    assert Path(attachment.file.path).is_relative_to(Path(settings.PRIVATE_MEDIA_ROOT))
    assert mail.outbox[0].attachments[0].content == ATTACHMENT_BYTES


def test_default_capture_keeps_historical_public_storage(settings):
    log = delivered_evidence(private=False)

    reloaded = EmailAttachmentSnapshot.objects.get(snapshot=log.snapshot)

    assert reloaded.file.name.startswith('email-history/')
    assert Path(reloaded.file.path).is_relative_to(Path(settings.MEDIA_ROOT))
    assert Path(reloaded.file.path).read_bytes() == ATTACHMENT_BYTES
    assert list(Path(settings.PRIVATE_MEDIA_ROOT).rglob('*')) == []


def test_public_resend_keeps_historical_storage(settings):
    original = delivered_evidence(private=False)

    resent = resend_email_log(original, ['client@example.com'])
    attachment = resent.snapshot.attachments.get()

    assert attachment.file.name.startswith('email-history/')
    assert Path(attachment.file.path).is_relative_to(Path(settings.MEDIA_ROOT))
    assert attachment.sha256 == original.snapshot.attachments.get().sha256
    assert list(Path(settings.PRIVATE_MEDIA_ROOT).rglob('*')) == []


def test_snapshot_failure_blocks_private_delivery(settings):
    """An invalid second source rolls back retained files before transport runs."""
    message = evidence_message()
    message.attach('second.pdf', ATTACHMENT_BYTES, 'application/pdf')

    with pytest.raises(EmailSnapshotCaptureError, match='archivar el correo exacto'):
        EmailDeliveryGateway.send(
            message, template_key=TEMPLATE_KEY, private_attachments=True,
            attachment_sources=[{}, {'document_id': 987654321}],
        )

    assert mail.outbox == []
    assert EmailDeliverySnapshot.objects.count() == 0
    assert EmailAttachmentSnapshot.objects.count() == 0
    assert list(Path(settings.PRIVATE_MEDIA_ROOT).rglob('*.pdf')) == []
    assert list(Path(settings.MEDIA_ROOT).rglob('*')) == []


def test_snapshot_capture_failure_hides_storage_exception(settings, caplog):
    """Fails if a storage exception leaks into frozen evidence or the gateway log."""
    marker = 'SYNTHETIC_PRIVATE_P5_20261001'

    with caplog.at_level(logging.ERROR, logger='content.services.email_delivery_service'):
        with patch.object(
            FileSystemStorage, '_save', side_effect=RuntimeError(marker),
        ):
            with pytest.raises(EmailSnapshotCaptureError, match='archivar el correo exacto'):
                EmailDeliveryGateway.send(
                    evidence_message(), template_key=TEMPLATE_KEY,
                    private_attachments=True,
                )

    assert marker not in caplog.text
    assert mail.outbox == []
    assert EmailDeliverySnapshot.objects.count() == 0
    assert EmailAttachmentSnapshot.objects.count() == 0
    assert list(Path(settings.PRIVATE_MEDIA_ROOT).rglob('*')) == []


def test_missing_private_attachment_never_reads_public_file(settings):
    snapshot = captured_evidence()
    attachment = snapshot.attachments.get()
    Path(attachment.file.path).unlink()
    public_decoy = Path(settings.MEDIA_ROOT) / attachment.file.name
    public_decoy.parent.mkdir(parents=True)
    public_decoy.write_bytes(b'public replacement')

    reloaded = EmailAttachmentSnapshot.objects.get(pk=attachment.pk)
    with pytest.raises(FileNotFoundError):
        reloaded.file.open('rb')

    assert public_decoy.read_bytes() == b'public replacement'
    assert reloaded.sha256 == hashlib.sha256(ATTACHMENT_BYTES).hexdigest()
