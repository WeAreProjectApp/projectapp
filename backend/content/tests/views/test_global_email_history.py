import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    Document,
    DocumentType,
    EmailAttachmentSnapshot,
    EmailBody,
    EmailCopyRecipient,
    EmailDeliverySnapshot,
    EmailLog,
    IncomeRecord,
)
from content.services.email_snapshot_service import EmailSnapshotCaptureError
from content.services.email_retry_service import prepare_retry_sources, retry_payload


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def email_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    mail.outbox = []


def make_log(
    template_key,
    *,
    recipient='recipient@example.com',
    status=EmailLog.Status.SENT,
    audience=EmailLog.Audience.INTERNAL,
    body=None,
    delivery_id=None,
    delivery_role=EmailLog.DeliveryRole.PRIMARY,
    recipient_kind=EmailLog.RecipientKind.TO,
    metadata=None,
):
    return EmailLog.objects.create(
        template_key=template_key,
        recipient=recipient,
        subject=f'Asunto {template_key}',
        status=status,
        audience=audience,
        body=body,
        delivery_id=delivery_id,
        delivery_role=delivery_role,
        recipient_kind=recipient_kind,
        metadata=metadata or {},
    )


def global_history(admin_client, params=None):
    return admin_client.get(
        reverse('list-standalone-emails'),
        {'scope': 'all', **(params or {})},
    )


def make_snapshot_log(
    *,
    attachment_bytes=None,
    format_kind='pdf',
    business_kind='proposal',
    document=None,
):
    body = EmailBody.objects.create(
        text='Contenido exacto https://projectapp.co/proposal/abc',
        html='<p>Contenido exacto</p>',
    )
    delivery_id = uuid.uuid4()
    snapshot = EmailDeliverySnapshot.objects.create(
        delivery_id=delivery_id,
        template_key='proposal_sent_client',
        classification='client',
        family='proposals',
        subject='Propuesta exacta',
        from_email='team@projectapp.co',
        body=body,
        message_size_bytes=800,
        attachment_size_bytes=len(attachment_bytes or b''),
        attachment_count=1 if attachment_bytes is not None else 0,
    )
    if attachment_bytes is not None:
        attachment = EmailAttachmentSnapshot(
            snapshot=snapshot,
            filename='propuesta.pdf',
            mime_type='application/pdf',
            size_bytes=len(attachment_bytes),
            sha256='0' * 64,
            position=0,
            format_kind=format_kind,
            business_kind=business_kind,
            business_kind_label='Propuesta',
            source_document=document,
            source_document_type_code=(
                document.document_type.code if document and document.document_type else ''
            ),
            source_document_type_name=(
                document.document_type.name if document and document.document_type else ''
            ),
        )
        attachment.file.save('propuesta.pdf', ContentFile(attachment_bytes), save=False)
        attachment.save()
    return EmailLog.objects.create(
        template_key='proposal_sent_client',
        recipient='recipient@example.com',
        subject=snapshot.subject,
        status=EmailLog.Status.SENT,
        audience=EmailLog.Audience.CLIENT,
        body=body,
        snapshot=snapshot,
        delivery_id=delivery_id,
    )


def make_failed_payment_confirmation_logs(count):
    logs = []
    for number in range(1, count + 1):
        income = IncomeRecord.objects.create(
            concept=f'Pago archivado {number}',
            kind=IncomeRecord.Kind.EXPECTED,
            period_date=date(2026, 7, number),
            total_amount=Decimal('100.00'),
            gustavo_amount=Decimal('50.00'),
            carlos_amount=Decimal('50.00'),
        )
        liquid = IncomeRecord.objects.create(
            concept=f'Abono archivado {number}',
            kind=IncomeRecord.Kind.LIQUID,
            period_date=date(2026, 7, number),
            total_amount=Decimal('50.00'),
            gustavo_amount=Decimal('25.00'),
            carlos_amount=Decimal('25.00'),
            expected_income=income,
        )
        logs.append(make_log(
            'income_payment_received_client',
            recipient=f'client-{number}@example.com',
            status=EmailLog.Status.FAILED,
            audience=EmailLog.Audience.CLIENT,
            body=EmailBody.objects.create(text='Confirmación', html='<p>Confirmación</p>'),
            metadata={
                'income_id': income.pk,
                'liquid_id': liquid.pk,
                'document_id': None,
                'public_number': f'PA-{number:03d}',
                'greeting_name': 'Ana',
                'concept': liquid.concept,
                'project_name': '',
                'amount': '50.00',
                'payment_date': f'2026-07-{number:02d}',
                'payment_date_precision': 'day',
                'pending_after': '50.00',
            },
        ))
    return logs


def test_global_scope_includes_every_audience(admin_client):
    make_log('proposal_sent_client', audience=EmailLog.Audience.CLIENT)
    make_log('accounting_change', audience=EmailLog.Audience.INTERNAL)
    make_log('verification_code_onboarding', audience=EmailLog.Audience.SECURITY)

    response = global_history(admin_client)

    assert response.status_code == 200
    assert {row['audience'] for row in response.data['results']} == {
        'client', 'internal', 'security',
    }


def test_default_scope_preserves_standalone_history(admin_client):
    make_log('branded_email')
    make_log('accounting_change')

    response = admin_client.get(reverse('list-standalone-emails'))

    assert [row['template_key'] for row in response.data['results']] == [
        'branded_email',
    ]


def test_global_scope_nests_copy_attempt(admin_client):
    delivery_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
    primary = make_log('accounting_change', delivery_id=delivery_id)
    make_log(
        'accounting_change',
        recipient='audit@example.com',
        delivery_id=delivery_id,
        delivery_role=EmailLog.DeliveryRole.COPY,
    )

    response = global_history(admin_client)

    assert response.data['total'] == 1
    assert response.data['results'][0]['id'] == primary.pk
    assert response.data['results'][0]['copies'][0]['recipient'] == (
        'audit@example.com'
    )


def test_global_history_groups_visible_recipients_by_delivery(admin_client):
    delivery_id = uuid.UUID('00000000-0000-0000-0000-000000000002')
    primary = make_log(
        'branded_email',
        recipient='uno@example.com',
        delivery_id=delivery_id,
    )
    make_log(
        'branded_email',
        recipient='dos@example.com',
        delivery_id=delivery_id,
    )
    make_log(
        'branded_email',
        recipient='copia@example.com',
        delivery_id=delivery_id,
        recipient_kind=EmailLog.RecipientKind.CC,
    )

    response = global_history(admin_client)

    assert response.data['total'] == 1
    assert response.data['results'][0]['id'] == primary.pk
    assert [item['email'] for item in response.data['results'][0]['to_recipients']] == [
        'uno@example.com',
        'dos@example.com',
    ]
    assert [item['email'] for item in response.data['results'][0]['cc_recipients']] == [
        'copia@example.com',
    ]


def test_recipient_filter_matches_cc_sibling(admin_client):
    delivery_id = uuid.UUID('00000000-0000-0000-0000-000000000003')
    primary = make_log(
        'branded_email',
        recipient='principal@example.com',
        delivery_id=delivery_id,
    )
    make_log(
        'branded_email',
        recipient='copia-buscada@example.com',
        delivery_id=delivery_id,
        recipient_kind=EmailLog.RecipientKind.CC,
    )

    response = global_history(admin_client, {'recipient': 'copia-buscada'})

    assert [row['id'] for row in response.data['results']] == [primary.pk]


def test_email_id_filter_resolves_cc_sibling(admin_client):
    delivery_id = uuid.UUID('00000000-0000-0000-0000-000000000004')
    primary = make_log(
        'branded_email',
        recipient='principal@example.com',
        delivery_id=delivery_id,
    )
    cc_log = make_log(
        'branded_email',
        recipient='copia@example.com',
        delivery_id=delivery_id,
        recipient_kind=EmailLog.RecipientKind.CC,
    )

    response = global_history(admin_client, {'email_id': cc_log.pk})

    assert [row['id'] for row in response.data['results']] == [primary.pk]


def test_family_filter_returns_matching_channel(admin_client):
    make_log('proposal_sent_client')
    make_log('accounting_change')

    response = global_history(admin_client, {'family': 'accounting'})

    assert [row['template_key'] for row in response.data['results']] == [
        'accounting_change',
    ]


def test_recipient_filter_is_case_insensitive(admin_client):
    make_log('accounting_change', recipient='Carlos@example.com')
    make_log('accounting_change', recipient='other@example.com')

    response = global_history(admin_client, {'recipient': 'CARLOS'})

    assert [row['recipient'] for row in response.data['results']] == [
        'Carlos@example.com',
    ]


def test_status_filter_returns_failed_send(admin_client):
    make_log('accounting_change', status=EmailLog.Status.SENT)
    failed = make_log(
        'accounting_change',
        recipient='failed@example.com',
        status=EmailLog.Status.FAILED,
    )

    response = global_history(admin_client, {'status': 'failed'})

    assert [row['id'] for row in response.data['results']] == [failed.pk]


@freeze_time('2026-08-20 12:00:00')
def test_date_window_excludes_older_send(admin_client):
    """Falla si el filtro diario incluye un envío de una fecha anterior."""
    old = make_log('accounting_change', recipient='old@example.com')
    EmailLog.objects.filter(pk=old.pk).update(
        sent_at=timezone.now() - timedelta(days=10),
    )
    current = make_log('accounting_change', recipient='today@example.com')

    response = global_history(
        admin_client,
        {'date_from': '2026-08-20', 'date_to': '2026-08-20'},
    )

    assert [row['id'] for row in response.data['results']] == [current.pk]


def test_admin_can_read_security_email_body(admin_client):
    body = EmailBody.objects.create(
        text='Tu código es 123456',
        html='<p>Tu código es <strong>123456</strong></p>',
    )
    log = make_log(
        'verification_code_onboarding',
        audience=EmailLog.Audience.SECURITY,
        body=body,
    )

    response = admin_client.get(reverse(
        'standalone-email-body',
        kwargs={'log_id': log.pk},
    ))

    assert response.status_code == 200
    assert response.data['text'] == 'Tu código es 123456'
    assert '123456' in response.data['html']


def test_anonymous_user_cannot_read_email_body(api_client):
    log = make_log('verification_code_onboarding')

    response = api_client.get(reverse(
        'standalone-email-body',
        kwargs={'log_id': log.pk},
    ))

    assert response.status_code in (401, 403)


def test_history_exposes_exact_attachment_recognition_data(admin_client):
    log = make_snapshot_log(attachment_bytes=b'pdf-original')

    response = global_history(admin_client)

    row = response.data['results'][0]
    assert row['id'] == log.pk
    assert row['snapshot_state'] == 'captured'
    assert row['message_size_bytes'] == 800
    assert row['attachments'][0]['filename'] == 'propuesta.pdf'
    assert row['attachments'][0]['format_label'] == 'PDF'
    assert row['attachments'][0]['size_bytes'] == len(b'pdf-original')


def test_history_states_confirmed_no_attachments_explicitly(admin_client):
    make_snapshot_log()

    response = global_history(admin_client)

    row = response.data['results'][0]
    assert row['snapshot_state'] == 'captured'
    assert row['has_attachments'] is False
    assert row['attachment_count'] == 0


def test_history_marks_legacy_attachment_as_unavailable(admin_client):
    log = make_log('proposal_sent_client')
    log.metadata = {'attachment_names': ['contrato.pdf']}
    log.save(update_fields=['metadata'])

    response = global_history(admin_client)

    row = response.data['results'][0]
    assert row['snapshot_state'] == 'legacy_partial'
    assert row['attachments'][0]['exact_available'] is False
    assert row['can_resend'] is False


def test_attachment_filters_use_presence_and_format(admin_client):
    attached = make_snapshot_log(attachment_bytes=b'pdf')
    make_snapshot_log()

    response = global_history(
        admin_client,
        {'has_attachments': 'true', 'attachment_type': 'format:pdf'},
    )

    assert [row['id'] for row in response.data['results']] == [attached.pk]


def test_attachment_filter_excludes_legacy_email_from_confirmed_zero(admin_client):
    """Falla si un correo legado se muestra como confirmado sin adjuntos."""
    captured_without_attachments = make_snapshot_log()
    make_log('proposal_sent_client')

    response = global_history(admin_client, {'has_attachments': 'false'})

    assert response.status_code == 200
    assert [row['id'] for row in response.data['results']] == [
        captured_without_attachments.pk,
    ]


def test_attachment_filter_returns_only_requested_business_kind(admin_client):
    """Falla si buscar una cuenta de cobro devuelve adjuntos de otro tipo."""
    collection_account = make_snapshot_log(
        attachment_bytes=b'collection-account',
        business_kind='collection_account',
    )
    make_snapshot_log(attachment_bytes=b'proposal', business_kind='proposal')

    response = global_history(
        admin_client,
        {'attachment_type': 'business:collection_account'},
    )

    assert response.status_code == 200
    assert [row['id'] for row in response.data['results']] == [
        collection_account.pk,
    ]


def test_attachment_download_uses_retained_bytes_after_source_changes(admin_client):
    document_type, _ = DocumentType.objects.get_or_create(
        code='proposal', defaults={'name': 'Propuesta'},
    )
    document = Document.objects.create(
        title='Propuesta original',
        content_markdown='# Versión original',
        document_type=document_type,
    )
    log = make_snapshot_log(
        attachment_bytes=b'pdf-original',
        document=document,
    )
    attachment = log.snapshot.attachments.get()
    document.title = 'Propuesta modificada'
    document.content_markdown = '# Versión modificada'
    document.save(update_fields=['title', 'content_markdown', 'updated_at'])

    response = admin_client.get(reverse(
        'standalone-email-attachment',
        kwargs={'log_id': log.pk, 'attachment_id': attachment.pk},
    ))

    assert response.status_code == 200
    assert b''.join(response.streaming_content) == b'pdf-original'


def test_exact_resend_preserves_retained_delivery(admin_client):
    log = make_snapshot_log(attachment_bytes=b'pdf-original')
    EmailCopyRecipient.objects.create(email='carlos18bp@gmail.com')

    response = admin_client.post(
        reverse('resend-standalone-email', kwargs={'log_id': log.pk}),
        {'recipient': 'nuevo@example.com'},
        format='json',
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 2
    assert mail.outbox[0].to == ['nuevo@example.com']
    assert mail.outbox[0].attachments[0].content == b'pdf-original'
    assert mail.outbox[1].bcc == ['carlos18bp@gmail.com']
    resent = EmailLog.objects.get(pk=response.data['email_log_id'])
    assert resent.snapshot.resend_of_id == log.snapshot_id


def test_exact_resend_preserves_visible_header_groups(admin_client):
    log = make_snapshot_log(attachment_bytes=b'pdf-original')

    response = admin_client.post(
        reverse('resend-standalone-email', kwargs={'log_id': log.pk}),
        {
            'recipient_emails': ['uno@example.com', 'dos@example.com'],
            'cc_emails': ['copia@example.com'],
        },
        format='json',
    )

    assert response.status_code == 200
    assert mail.outbox[0].to == ['uno@example.com', 'dos@example.com']
    assert mail.outbox[0].cc == ['copia@example.com']
    resent_logs = EmailLog.objects.filter(
        delivery_id=response.data['delivery_id'],
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    )
    assert set(resent_logs.values_list('recipient', 'recipient_kind')) == {
        ('uno@example.com', EmailLog.RecipientKind.TO),
        ('dos@example.com', EmailLog.RecipientKind.TO),
        ('copia@example.com', EmailLog.RecipientKind.CC),
    }


def test_resend_returns_service_unavailable_when_snapshot_capture_fails(admin_client):
    log = make_snapshot_log(attachment_bytes=b'pdf-original')

    with patch(
        'content.services.email_delivery_service.EmailDeliveryGateway.send',
        side_effect=EmailSnapshotCaptureError('storage unavailable'),
    ):
        response = admin_client.post(
            reverse('resend-standalone-email', kwargs={'log_id': log.pk}),
            {'recipient': 'nuevo@example.com'},
            format='json',
        )

    assert response.status_code == 503
    assert response.data['code'] == 'email_snapshot_capture_failed'


def test_resend_records_failed_log_when_gateway_raises(admin_client):
    log = make_snapshot_log(attachment_bytes=b'pdf-original')
    marker = 'SYNTHETIC_PRIVATE_P5_20261001'

    with patch(
        'content.services.email_delivery_service.EmailDeliveryGateway.send',
        side_effect=RuntimeError(marker),
    ):
        response = admin_client.post(
            reverse('resend-standalone-email', kwargs={'log_id': log.pk}),
            {'recipient': 'nuevo@example.com'},
            format='json',
        )

    assert response.status_code == 502
    failed = EmailLog.objects.exclude(pk=log.pk).get(status=EmailLog.Status.FAILED)
    assert failed.error_message == 'No se pudo completar el envío de correo.'
    assert marker not in str(response.data)


def test_resend_records_failed_log_when_gateway_returns_zero(admin_client):
    log = make_snapshot_log(attachment_bytes=b'pdf-original')

    with patch(
        'content.services.email_delivery_service.EmailDeliveryGateway.send',
        return_value=0,
    ):
        response = admin_client.post(
            reverse('resend-standalone-email', kwargs={'log_id': log.pk}),
            {'recipient': 'nuevo@example.com'},
            format='json',
        )

    assert response.status_code == 502
    failed = EmailLog.objects.exclude(pk=log.pk).get(status=EmailLog.Status.FAILED)
    assert failed.error_message == 'El backend de correo no aceptó el reenvío.'


def test_retry_sends_only_the_failed_cc_recipient_from_its_snapshot(admin_client):
    """Falla si reintentar un CC fallido vuelve a enviar al destinatario que sí recibió."""
    representative = make_snapshot_log()
    failed_cc = EmailLog.objects.create(
        template_key=representative.template_key,
        recipient='failed-copy@example.com',
        subject=representative.subject,
        status=EmailLog.Status.FAILED,
        audience=representative.audience,
        body=representative.body,
        snapshot=representative.snapshot,
        delivery_id=representative.delivery_id,
        recipient_kind=EmailLog.RecipientKind.CC,
    )

    response = admin_client.post(reverse(
        'retry-standalone-email', kwargs={'log_id': failed_cc.pk},
    ), {}, format='json')

    retry = EmailLog.objects.get(pk=response.data['id'])
    assert response.status_code == 201
    assert response.data == {
        'id': retry.pk,
        'status': EmailLog.Status.SENT,
        'recipient': 'failed-copy@example.com',
        'retry_of': failed_cc.pk,
    }
    assert mail.outbox[0].to == ['failed-copy@example.com']
    assert len(mail.outbox) == 1
    assert mail.outbox[0].cc == []
    assert mail.outbox[0].bcc == []
    assert retry.retry_of_id == failed_cc.pk


def test_history_exposes_retry_state_for_each_visible_recipient(admin_client):
    """Falla si Historial oculta que sólo el CC fallido puede reintentarse."""
    representative = make_snapshot_log()
    failed_cc = EmailLog.objects.create(
        template_key=representative.template_key,
        recipient='failed-copy@example.com',
        subject=representative.subject,
        status=EmailLog.Status.FAILED,
        audience=representative.audience,
        body=representative.body,
        snapshot=representative.snapshot,
        delivery_id=representative.delivery_id,
        recipient_kind=EmailLog.RecipientKind.CC,
    )

    response = global_history(admin_client)

    row = response.data['results'][0]
    assert response.status_code == 200
    assert row['is_retryable'] is False
    assert row['retry_blocked_reason'] == 'Solo se reintentan los envíos que fallaron.'
    assert row['cc_recipients'] == [{
        'email': 'failed-copy@example.com',
        'status': EmailLog.Status.FAILED,
        'status_label': 'Failed',
        'error_message': '',
        'client_id': None,
        'client_name': '',
        'id': failed_cc.pk,
        'is_retryable': True,
        'retry_blocked_reason': '',
        'retry_of': None,
    }]


def test_retry_rejects_a_replacement_recipient_without_sending(admin_client):
    """Falla si el reintento permite cambiar el destinatario archivado."""
    log = make_snapshot_log()
    log.status = EmailLog.Status.FAILED
    log.save(update_fields=['status'])

    response = admin_client.post(reverse(
        'retry-standalone-email', kwargs={'log_id': log.pk},
    ), {'recipient': 'replacement@example.com'}, format='json')

    assert response.status_code == 400
    assert response.data['detail'] == (
        'El reintento usa el destinatario del fallo y no admite cambios.'
    )
    assert mail.outbox == []
    assert EmailLog.objects.count() == 1


@pytest.mark.parametrize('recipient_kind', (
    EmailLog.RecipientKind.TO, EmailLog.RecipientKind.CC,
))
def test_exact_retry_retains_original_client_for_unregistered_alias(
    admin_client, make_client_profile, recipient_kind,
):
    """Falla si un alias válido pierde la asociación del fallo original."""
    client = make_client_profile(email='registered@example.com')
    original = make_snapshot_log()
    original.recipient = 'client-alias@example.com'
    original.client = client
    original.status = EmailLog.Status.FAILED
    original.recipient_kind = recipient_kind
    original.save(update_fields=['recipient', 'client', 'status', 'recipient_kind'])

    response = admin_client.post(reverse(
        'retry-standalone-email', kwargs={'log_id': original.pk},
    ), {}, format='json')

    assert response.status_code == 201
    retry = EmailLog.objects.get(pk=response.data['id'])
    assert retry.client_id == client.pk
    assert retry.audience == EmailLog.Audience.CLIENT
    assert retry.recipient == original.recipient
    assert retry.retry_of_id == original.pk
    assert mail.outbox[0].to == [original.recipient]
    history = global_history(admin_client)
    assert history.data['results'][0]['to_recipients'][0]['client_id'] == client.pk
    assert history.data['results'][0]['audience'] == EmailLog.Audience.CLIENT


def test_failed_exact_retry_retains_original_client_for_unregistered_alias(
    admin_client, make_client_profile,
):
    """Falla si otro error de transporte desvincula el intento de su cliente."""
    client = make_client_profile(email='registered@example.com')
    original = make_snapshot_log()
    original.recipient = 'client-alias@example.com'
    original.client = client
    original.status = EmailLog.Status.FAILED
    original.save(update_fields=['recipient', 'client', 'status'])

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=OSError('SMTP unavailable'),
    ):
        response = admin_client.post(reverse(
            'retry-standalone-email', kwargs={'log_id': original.pk},
        ), {}, format='json')

    assert response.status_code == 502
    retry = EmailLog.objects.get(pk=response.data['id'])
    assert retry.status == EmailLog.Status.FAILED
    assert retry.client_id == client.pk
    assert retry.audience == EmailLog.Audience.CLIENT
    assert retry.recipient == original.recipient
    assert retry.retry_of_id == original.pk


def test_exact_resend_attributes_replacement_address_to_its_registered_client(
    admin_client, make_client_profile,
):
    """Falla si reenviar a otra dirección hereda un cliente que no le corresponde."""
    original_client = make_client_profile(email='registered@example.com')
    replacement_client = make_client_profile(email='replacement@example.com')
    original = make_snapshot_log()
    original.recipient = 'client-alias@example.com'
    original.client = original_client
    original.save(update_fields=['recipient', 'client'])

    response = admin_client.post(
        reverse('resend-standalone-email', kwargs={'log_id': original.pk}),
        {'recipient': replacement_client.user.email},
        format='json',
    )

    assert response.status_code == 200
    resent = EmailLog.objects.get(pk=response.data['email_log_id'])
    assert resent.client_id == replacement_client.pk
    assert resent.audience == EmailLog.Audience.CLIENT
    assert mail.outbox[0].to == [replacement_client.user.email]


def test_failed_snapshot_retry_keeps_a_linked_failed_history_attempt(admin_client):
    """Falla si un segundo fallo SMTP desaparece del historial o pierde su origen."""
    log = make_snapshot_log()
    log.status = EmailLog.Status.FAILED
    log.save(update_fields=['status'])

    with patch(
        'content.services.email_delivery_service.EmailMessage.send',
        side_effect=OSError('SMTP unavailable'),
    ):
        response = admin_client.post(reverse(
            'retry-standalone-email', kwargs={'log_id': log.pk},
        ), {}, format='json')

    retry = EmailLog.objects.get(retry_of=log)
    assert response.status_code == 502
    assert response.data['id'] == retry.pk
    assert retry.status == EmailLog.Status.FAILED
    assert retry.recipient == 'recipient@example.com'
    assert retry.error_message == 'No se pudo completar el envío de correo.'


def test_superuser_rebuilds_payment_confirmation_from_saved_facts(super_client):
    """Falla si un reintento legado consulta el destinatario o saldo actuales."""
    original = make_failed_payment_confirmation_logs(1)[0]
    original.recipient = 'original-address@example.com'
    original.save(update_fields=['recipient'])
    IncomeRecord.objects.filter(pk=original.metadata['income_id']).update(total_amount=Decimal('900.00'))

    response = super_client.post(reverse(
        'retry-standalone-email', kwargs={'log_id': original.pk},
    ), {}, format='json')

    retry = EmailLog.objects.get(pk=response.data['id'])
    assert response.status_code == 201
    assert response.data['recipient'] == 'original-address@example.com'
    assert retry.retry_of_id == original.pk
    assert mail.outbox[0].to == ['original-address@example.com']
    assert 'Saldo pendiente: $50 COP' in mail.outbox[0].body


def test_admin_cannot_rebuild_a_legacy_payment_confirmation(admin_client):
    """Falla si un administrador común puede reconstruir un cobro legado."""
    original = make_failed_payment_confirmation_logs(1)[0]

    response = admin_client.post(reverse(
        'retry-standalone-email', kwargs={'log_id': original.pk},
    ), {}, format='json')

    assert response.status_code == 403
    assert response.data['detail'] == (
        'Solo un superusuario puede reconstruir este envío contable.'
    )
    assert mail.outbox == []


def test_retry_blocks_payment_confirmation_with_incomplete_saved_facts(super_client):
    """Falla si un reintento inventa los datos que el correo legado no guardó."""
    original = make_failed_payment_confirmation_logs(1)[0]
    original.metadata = {'income_id': 1, 'liquid_id': 2}
    original.save(update_fields=['metadata'])

    response = super_client.post(reverse(
        'retry-standalone-email', kwargs={'log_id': original.pk},
    ), {}, format='json')

    assert response.status_code == 409
    assert response.data['detail'] == (
        'Este envío no conservó todos los datos del pago para reconstruir la confirmación.'
    )
    assert mail.outbox == []


@pytest.mark.parametrize('log_count', (2, 10))
def test_prepare_retry_sources_batches_payment_confirmation_pairs(
    django_assert_num_queries, log_count, superuser,
):
    """Falla si Historial vuelve a consultar un pago por cada confirmación fallida."""
    logs = make_failed_payment_confirmation_logs(log_count)

    with django_assert_num_queries(1):
        prepare_retry_sources(logs)
        payloads = [retry_payload(log, superuser) for log in logs]

    assert payloads[0] == {'is_retryable': True, 'retry_blocked_reason': '', 'retry_of': None}
    assert payloads[-1] == {'is_retryable': True, 'retry_blocked_reason': '', 'retry_of': None}


def _document_with_email_usage():
    document_type, _ = DocumentType.objects.get_or_create(
        code='proposal', defaults={'name': 'Propuesta'},
    )
    document = Document.objects.create(
        title='Propuesta histórica',
        document_type=document_type,
    )
    log = make_snapshot_log(
        attachment_bytes=b'pdf-original',
        document=document,
    )
    return document, log


def test_document_email_usage_returns_primary_delivery(admin_client):
    document, log = _document_with_email_usage()

    usage = admin_client.get(reverse(
        'document-email-usage',
        kwargs={'document_id': document.pk},
    ))

    assert usage.data['results'][0]['email_log_id'] == log.pk


def test_document_email_usage_blocks_destructive_delete(admin_client):
    document, _ = _document_with_email_usage()

    deleted = admin_client.delete(reverse(
        'delete-document',
        kwargs={'document_id': document.pk},
    ))

    assert deleted.status_code == 409
    assert deleted.data['code'] == 'document_used_in_email_history'
