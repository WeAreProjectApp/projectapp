from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.exceptions import ValidationError

from content.email_copy_families import COLLECTIONS, PROPOSALS, SECURITY
from content.models import (
    ClientEmailCopyRecipient,
    Document,
    DocumentType,
    EmailBody,
    EmailDeliverySnapshot,
    EmailLog,
)
from content.services import email_log_service
from content.services.client_email_inventory import CLIENT_EMAIL_CHANNELS
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.services.email_snapshot_service import (
    _format_kind,
    _inferred_business_kind,
)
from content.services.outbound_email_inventory import OUTBOUND_EMAIL_CHANNELS
from content.serializers.accounting import EmailLogSerializer


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def locmem_email_backend(settings, tmp_path):
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    settings.MEDIA_ROOT = tmp_path
    mail.outbox = []


def build_message(recipient='client@example.com'):
    message = EmailMultiAlternatives(
        subject='Propuesta ProjectApp',
        body='Versión de texto',
        from_email='team@projectapp.co',
        to=[recipient],
    )
    message.attach_alternative('<p>Versión HTML</p>', 'text/html')
    message.attach('alcance.txt', b'contenido', 'text/plain')
    return message


def record_primary(recipient='client@example.com'):
    return email_log_service.record_send(
        template_key='proposal_sent_client',
        recipients=[recipient],
        subject='Propuesta ProjectApp',
        status=EmailLog.Status.SENT,
        html_body='<p>Versión HTML</p>',
        text_body='Versión de texto',
        audience=EmailLog.Audience.CLIENT,
    )[0]


def _exercise_outbound_inventory_bcc_matrix():
    """Deliver every inventory key with exactly its own family recipient."""
    recipient_by_family = {
        family: f'audit-{family}@example.com'
        for family in set(OUTBOUND_EMAIL_CHANNELS.values())
    }
    for family, recipient in recipient_by_family.items():
        ClientEmailCopyRecipient.objects.create(
            email=recipient,
            families=[family],
        )

    delivery_matrix = {}
    for template_key, family in OUTBOUND_EMAIL_CHANNELS.items():
        classification = None
        if template_key not in CLIENT_EMAIL_CHANNELS:
            classification = (
                DeliveryClassification.SECURITY
                if family == SECURITY
                else DeliveryClassification.INTERNAL
            )
        outbox_start = len(mail.outbox)
        result = EmailDeliveryGateway.send(
            build_message(),
            template_key=template_key,
            classification=classification,
        )
        primary, copy_message = mail.outbox[outbox_start:]
        delivery_matrix[template_key] = {
            'result': result,
            'primary_to': primary.to,
            'primary_cc': primary.cc,
            'primary_bcc': primary.bcc,
            'copy_to': copy_message.to,
            'copy_cc': copy_message.cc,
            'copy_bcc': copy_message.bcc,
            'expected_copy_bcc': [recipient_by_family[family]],
        }
    return delivery_matrix


def test_client_delivery_uses_hidden_copy_envelope():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    result = EmailDeliveryGateway.send(
        message, template_key='proposal_sent_client',
    )

    assert result == 1
    assert len(mail.outbox) == 2
    assert mail.outbox[0].to == ['client@example.com']
    assert mail.outbox[0].bcc == []
    assert mail.outbox[1].to == []
    assert mail.outbox[1].bcc == ['audit@example.com']


def test_multi_recipient_delivery_uses_one_visible_envelope():
    message = EmailMultiAlternatives(
        subject='Seguimiento',
        body='Contenido',
        from_email='team@projectapp.co',
        to=['uno@example.com', 'dos@example.com'],
        cc=['copia@example.com'],
    )

    result = EmailDeliveryGateway.send(
        message,
        template_key='branded_email',
        classification=DeliveryClassification.CLIENT,
    )

    assert result == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['uno@example.com', 'dos@example.com']
    assert mail.outbox[0].cc == ['copia@example.com']


def test_multi_recipient_delivery_archives_header_roles():
    message = EmailMultiAlternatives(
        subject='Seguimiento',
        body='Contenido',
        from_email='team@projectapp.co',
        to=['uno@example.com', 'dos@example.com'],
        cc=['copia@example.com'],
    )

    EmailDeliveryGateway.send(
        message,
        template_key='branded_email',
        classification=DeliveryClassification.CLIENT,
    )

    snapshot = EmailDeliverySnapshot.objects.get()
    roles = set(EmailLog.objects.values_list('recipient', 'recipient_kind'))
    assert snapshot.to_recipients == ['uno@example.com', 'dos@example.com']
    assert snapshot.cc_recipients == ['copia@example.com']
    assert roles == {
        ('uno@example.com', EmailLog.RecipientKind.TO),
        ('dos@example.com', EmailLog.RecipientKind.TO),
        ('copia@example.com', EmailLog.RecipientKind.CC),
    }


def test_every_registered_outbound_channel_uses_its_family_bcc_copy():
    """Falla si una clave inventariada deja de emitir su copia BCC única."""
    delivery_matrix = _exercise_outbound_inventory_bcc_matrix()

    assert set(delivery_matrix) == set(OUTBOUND_EMAIL_CHANNELS)
    assert len(delivery_matrix) == 58
    assert all(
        delivery == {
            'result': 1,
            'primary_to': ['client@example.com'],
            'primary_cc': [],
            'primary_bcc': [],
            'copy_to': [],
            'copy_cc': [],
            'copy_bcc': delivery['expected_copy_bcc'],
            'expected_copy_bcc': delivery['expected_copy_bcc'],
        }
        for delivery in delivery_matrix.values()
    )


def test_client_copy_preserves_rendered_content():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    primary, copy_message = mail.outbox
    assert copy_message.subject == primary.subject
    assert copy_message.body == primary.body
    assert copy_message.alternatives == primary.alternatives
    assert copy_message.attachments == primary.attachments


def test_primary_failure_records_primary_without_copy():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=SMTPException('primary unavailable'),
    ) as smtp_send:
        with pytest.raises(SMTPException, match='primary unavailable'):
            EmailDeliveryGateway.send(
                message, template_key='proposal_sent_client',
            )

    smtp_send.assert_called_once_with()
    primary = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.PRIMARY)
    assert primary.status == EmailLog.Status.FAILED
    assert primary.error_message == 'primary unavailable'
    assert not EmailLog.objects.filter(
        delivery_role=EmailLog.DeliveryRole.COPY,
    ).exists()


def test_primary_smtp_failure_is_suppressed_when_requested():
    message = build_message()

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=SMTPException('primary unavailable'),
    ) as smtp_send:
        result = EmailDeliveryGateway.send(
            message,
            template_key='proposal_sent_client',
            fail_silently=True,
        )

    smtp_send.assert_called_once_with()
    primary = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.PRIMARY)
    assert result == 0
    assert primary.status == EmailLog.Status.FAILED
    assert primary.error_message == 'primary unavailable'


def test_copy_failure_preserves_primary_status():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=[1, SMTPException('copy unavailable')],
    ):
        result = EmailDeliveryGateway.send(
            message, template_key='proposal_sent_client',
        )
    primary = record_primary()

    copy_log = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.COPY)
    assert result == 1
    assert primary.status == EmailLog.Status.SENT
    assert copy_log.status == EmailLog.Status.FAILED
    assert copy_log.error_message == 'copy unavailable'


def test_copy_failure_does_not_prevent_later_copy_recipient():
    """Falla si una copia fallida bloquea otra copia o degrada el envío principal."""
    ClientEmailCopyRecipient.objects.create(email='audit-a@example.com')
    ClientEmailCopyRecipient.objects.create(email='audit-b@example.com')
    message = build_message()

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=[1, SMTPException('audit-a unavailable'), 1],
    ) as smtp_send:
        result = EmailDeliveryGateway.send(
            message,
            template_key='proposal_sent_client',
        )

    primary = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.PRIMARY)
    copy_attempts = list(
        EmailLog.objects.filter(
            delivery_role=EmailLog.DeliveryRole.COPY,
        ).order_by('recipient').values_list('recipient', 'status', 'error_message')
    )
    assert result == 1
    assert primary.status == EmailLog.Status.SENT
    assert copy_attempts == [
        ('audit-a@example.com', EmailLog.Status.FAILED, 'audit-a unavailable'),
        ('audit-b@example.com', EmailLog.Status.SENT, ''),
    ]
    assert smtp_send.call_count == 3


def test_copy_history_shares_delivery_body():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')
    primary = record_primary()
    copy_log = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.COPY)

    assert primary.delivery_id == copy_log.delivery_id
    assert primary.body_id == copy_log.body_id
    assert primary.snapshot_id == copy_log.snapshot_id
    assert EmailBody.objects.count() == 1


def test_primary_serializer_exposes_copy_attempt():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')
    primary = record_primary()

    assert EmailLogSerializer(primary).data['copies'][0]['recipient'] == (
        'audit@example.com'
    )


def test_nonmatching_family_skips_copy():
    ClientEmailCopyRecipient.objects.create(
        email='billing@example.com', families=[COLLECTIONS],
    )
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    assert len(mail.outbox) == 1


def test_security_delivery_uses_hidden_copy():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(
        message,
        template_key='verification_code_onboarding',
        classification=DeliveryClassification.SECURITY,
    )

    assert len(mail.outbox) == 2
    assert mail.outbox[1].bcc == ['audit@example.com']
    primary = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.PRIMARY)
    assert primary.audience == EmailLog.Audience.SECURITY


def test_unregistered_delivery_requires_explicit_policy():
    message = build_message()

    with pytest.raises(ValueError, match='missing from the inventory'):
        EmailDeliveryGateway.send(message, template_key='future_email')


def test_unregistered_client_policy_is_rejected():
    message = build_message()

    with pytest.raises(ValueError, match='missing from the inventory'):
        EmailDeliveryGateway.send(
            message,
            template_key='future_email',
            classification=DeliveryClassification.CLIENT,
        )


def test_copy_recipient_lookup_failure_preserves_primary():
    message = build_message()

    with patch(
        'content.services.email_delivery_service._active_copy_recipients',
        side_effect=RuntimeError('configuration unavailable'),
    ):
        result = EmailDeliveryGateway.send(
            message, template_key='proposal_sent_client',
        )

    assert result == 1
    assert len(mail.outbox) == 1
    primary = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.PRIMARY)
    assert primary.metadata['outbound_delivery']['copy_error'] == (
        'No se pudo resolver la configuración de copias.'
    )


def test_inactive_recipient_is_not_copied():
    ClientEmailCopyRecipient.objects.create(
        email='paused@example.com', is_active=False,
    )
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    assert len(mail.outbox) == 1


def test_primary_recipient_is_not_copied_twice():
    ClientEmailCopyRecipient.objects.create(email='CLIENT@example.com')
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    assert len(mail.outbox) == 1
    copy_log = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.COPY)
    assert copy_log.status == EmailLog.Status.SKIPPED
    assert copy_log.error_message == 'Ya era destinatario del envío principal.'


def test_internal_delivery_uses_hidden_copy():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(
        message,
        template_key='accounting_change',
        classification=DeliveryClassification.INTERNAL,
    )

    assert len(mail.outbox) == 2
    assert mail.outbox[1].bcc == ['audit@example.com']


def test_gateway_persists_history_without_caller_logger():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(
        message,
        template_key='task_alert_notification',
        classification=DeliveryClassification.INTERNAL,
    )

    primary = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.PRIMARY)
    copy_log = EmailLog.objects.get(delivery_role=EmailLog.DeliveryRole.COPY)
    assert primary.delivery_id == copy_log.delivery_id
    assert primary.body_id == copy_log.body_id


def test_multiple_copy_recipients_create_independent_attempts():
    ClientEmailCopyRecipient.objects.create(email='audit-a@example.com')
    ClientEmailCopyRecipient.objects.create(email='audit-b@example.com')
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')
    record_primary()

    assert len(mail.outbox) == 3
    assert EmailLog.objects.filter(
        delivery_role=EmailLog.DeliveryRole.COPY,
    ).count() == 2


def test_multi_log_delivery_records_single_copy():
    ClientEmailCopyRecipient.objects.create(email='audit@example.com')
    message = build_message()

    EmailDeliveryGateway.send(
        message,
        template_key='proposal_multi_sent_client',
        primary_log_writes=2,
    )
    first = email_log_service.record_send(
        template_key='proposal_multi_sent_client',
        recipients=['client@example.com'],
        subject='Propuesta ProjectApp',
        status=EmailLog.Status.SENT,
        html_body='<p>Versión HTML</p>',
        text_body='Versión de texto',
        audience=EmailLog.Audience.CLIENT,
    )[0]
    second = email_log_service.record_send(
        template_key='proposal_multi_sent_client',
        recipients=['client@example.com'],
        subject='Propuesta ProjectApp',
        status=EmailLog.Status.SENT,
        audience=EmailLog.Audience.CLIENT,
    )[0]

    assert first.delivery_id == second.delivery_id
    assert EmailLog.objects.filter(
        delivery_role=EmailLog.DeliveryRole.COPY,
    ).count() == 1


def test_active_recipient_requires_selected_family():
    recipient = ClientEmailCopyRecipient(
        email='audit@example.com', is_active=True, families=[],
    )

    with pytest.raises(ValidationError, match='al menos una familia'):
        recipient.full_clean()


def test_model_normalizes_email_case():
    recipient = ClientEmailCopyRecipient.objects.create(
        email=' Audit@Example.COM ', families=[PROPOSALS],
    )

    assert recipient.email == 'audit@example.com'


def test_gateway_archives_exact_attachment_bytes_before_delivery():
    message = build_message()

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    snapshot = EmailDeliverySnapshot.objects.get()
    attachment = snapshot.attachments.get()
    with attachment.file.open('rb') as retained:
        # text/plain MIME canonicalization adds the newline the recipient
        # decodes; the archive follows the wire representation, not the input.
        assert retained.read() == b'contenido\n'
    assert attachment.filename == 'alcance.txt'
    assert attachment.size_bytes == len(b'contenido\n')
    assert snapshot.message_size_bytes > snapshot.attachment_size_bytes


def test_gateway_archives_document_provenance_with_attachment():
    """Falla si un adjunto enviado pierde su relación con el documento origen."""
    document_type = DocumentType.objects.create(
        code='proposal', name='Propuesta',
    )
    document = Document.objects.create(
        title='Propuesta para cliente',
        content_markdown='# Alcance',
        document_type=document_type,
    )

    EmailDeliveryGateway.send(
        build_message(),
        template_key='proposal_sent_client',
        attachment_sources=[{'document_id': document.pk}],
    )

    attachment = EmailDeliverySnapshot.objects.get().attachments.get()
    assert attachment.source_document_id == document.pk
    assert (
        attachment.source_document_type_code,
        attachment.source_document_type_name,
    ) == ('proposal', 'Propuesta')


def test_gateway_records_confirmed_zero_attachments():
    message = EmailMultiAlternatives(
        subject='Sin adjuntos',
        body='Contenido',
        from_email='team@projectapp.co',
        to=['client@example.com'],
    )

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    snapshot = EmailDeliverySnapshot.objects.get()
    assert snapshot.attachment_count == 0
    assert snapshot.attachment_size_bytes == 0


def test_gateway_archives_content_and_template_links_separately():
    message = EmailMultiAlternatives(
        subject='Enlaces',
        body='Propuesta https://projectapp.co/proposal/abc',
        from_email='team@projectapp.co',
        to=['client@example.com'],
    )
    message.attach_alternative(
        '<a href="https://projectapp.co">ProjectApp</a>',
        'text/html',
    )

    EmailDeliveryGateway.send(message, template_key='proposal_sent_client')

    links = set(EmailDeliverySnapshot.objects.get().links.values_list('url', 'group'))
    assert links == {
        ('https://projectapp.co', 'template'),
        ('https://projectapp.co/proposal/abc', 'content'),
    }


def test_snapshot_failure_blocks_smtp():
    message = build_message()

    with patch(
        'content.services.email_snapshot_service.capture_delivery_snapshot',
        side_effect=RuntimeError('storage unavailable'),
    ), patch(
        'content.services.email_delivery_service.EmailMessage.send',
    ) as smtp_send:
        with pytest.raises(RuntimeError, match='storage unavailable'):
            EmailDeliveryGateway.send(
                message,
                template_key='proposal_sent_client',
            )

    smtp_send.assert_not_called()


@pytest.mark.parametrize(
    ('filename', 'mime_type', 'expected'),
    [
        (
            'alcance.docx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'word',
        ),
        (
            'presupuesto.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'spreadsheet',
        ),
    ],
    ids=['word', 'spreadsheet'],
)
def test_attachment_format_classifies_office_file(filename, mime_type, expected):
    assert _format_kind(filename, mime_type) == expected


def test_business_kind_infers_platform_guide():
    result = _inferred_business_kind('platform_welcome', 'guia-plataforma.pdf')

    assert result == ('platform_guide', 'Guía de plataforma')
