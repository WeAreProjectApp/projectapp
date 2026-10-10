"""Diagnosing a send from its own row: what went out, and sending it again.

The history exists to answer "no me llegó". These cover the two things that
turn it from a receipt into a diagnosis — reading the message that was
delivered, and retrying the one that was not — plus the boundaries that keep
a retry from doing more than it claims.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.models import (
    AccountingChangeLog,
    EmailBody,
    EmailLog,
    EmailLogTarget,
    HostingRecord,
    NotificationRecipient,
)

pytestmark = pytest.mark.django_db


def make_log(**kwargs):
    fields = {
        'template_key': 'accounting_change',
        'recipient': 'ana@test.com',
        'subject': '[Contabilidad] Hosting creado: Kore',
        'status': EmailLog.Status.FAILED,
        'error_message': 'SMTP timeout',
    }
    fields.update(kwargs)
    return EmailLog.objects.create(**fields)


class TestReadingTheMessage:
    def test_returns_the_html_that_was_delivered(self, super_client):
        body = EmailBody.objects.create(
            html='<p>Hosting creado</p>', text='Hosting creado',
        )
        log = make_log(status=EmailLog.Status.SENT, body=body)

        response = super_client.get(f'/api/accounting/email-log/{log.id}/body/')

        assert response.status_code == 200
        assert response.data['html'] == '<p>Hosting creado</p>'
        assert response.data['text'] == 'Hosting creado'
        assert response.data['recipient'] == 'ana@test.com'

    def test_says_so_instead_of_showing_an_empty_modal(self, super_client):
        """Sends predating the feature have no body; that is an answer."""
        log = make_log(status=EmailLog.Status.SENT)

        response = super_client.get(f'/api/accounting/email-log/{log.id}/body/')

        assert response.status_code == 404
        assert response.data['code'] == 'body_not_stored'

    def test_is_not_a_reader_for_the_proposal_traffic(self, super_client):
        """EmailLog is shared; this endpoint is scoped to the module."""
        body = EmailBody.objects.create(html='<p>Propuesta</p>')
        log = make_log(template_key='proposal_sent', body=body)

        response = super_client.get(f'/api/accounting/email-log/{log.id}/body/')

        assert response.status_code == 404

    def test_is_superuser_only(self, admin_client):
        log = make_log()
        assert admin_client.get(
            f'/api/accounting/email-log/{log.id}/body/',
        ).status_code == 403


class TestRetryingTheSend:
    @pytest.fixture
    def change_log(self):
        return AccountingChangeLog.objects.create(
            entity_type='hosting', object_id=1, object_repr='Kore',
            action='created',
        )

    def test_resends_only_to_the_address_that_failed(
        self, super_client, change_log, mailoutbox,
    ):
        NotificationRecipient.objects.create(email='ana@test.com')
        NotificationRecipient.objects.create(email='zoe@test.com')
        log = make_log(metadata={'change_log_id': change_log.id})

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.status_code == 201
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['ana@test.com']

    def test_the_retry_is_a_new_row_linked_to_the_original(
        self, super_client, change_log,
    ):
        NotificationRecipient.objects.create(email='ana@test.com')
        log = make_log(metadata={'change_log_id': change_log.id})

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.data['retry_of'] == log.id
        assert response.data['status'] == 'sent'
        log.refresh_from_db()
        assert log.status == EmailLog.Status.FAILED

    def test_the_retry_keeps_the_record_the_notice_was_about(
        self, super_client, change_log,
    ):
        NotificationRecipient.objects.create(email='ana@test.com')
        log = make_log(metadata={'change_log_id': change_log.id})

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        targets = EmailLogTarget.objects.filter(email_log_id=response.data['id'])
        assert list(targets.values_list('entity_type', 'object_id')) == [
            ('hosting', 1),
        ]

    def test_a_digest_is_refused_with_its_reason(self, super_client):
        log = make_log(template_key='accounting_payment_calendar')

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.status_code == 400
        assert 'resumen' in response.data['error']

    def test_a_send_that_worked_is_not_retried(self, super_client, change_log):
        log = make_log(
            status=EmailLog.Status.SENT,
            metadata={'change_log_id': change_log.id},
        )

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.status_code == 400
        assert 'fallaron' in response.data['error']

    def test_says_so_when_the_record_behind_it_is_gone(self, super_client):
        log = make_log(metadata={'change_log_id': 9999})

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.status_code == 400
        assert 'ya no existe' in response.data['error']

    def test_a_retry_that_fails_again_reports_why(
        self, super_client, change_log,
    ):
        NotificationRecipient.objects.create(email='ana@test.com')
        log = make_log(metadata={'change_log_id': change_log.id})

        with patch(
            'content.services.accounting_email_service.EmailMultiAlternatives.send',
            side_effect=Exception('SMTP down'),
        ):
            response = super_client.post(
                f'/api/accounting/email-log/{log.id}/retry/',
            )

        assert response.status_code == 400
        assert 'SMTP down' in response.data['error']
        # The failed attempt is still recorded, linked to what it retried.
        assert EmailLog.objects.filter(
            retry_of=log, status=EmailLog.Status.FAILED,
        ).exists()

    def test_a_collection_account_retry_goes_to_its_client(
        self, super_client, mailoutbox,
    ):
        """This notice's recipient is the client, not the internal list.

        Which is why the retry re-sends the document rather than overriding
        the address: the row's recipient IS the client's.
        """
        from content.models import Document, DocumentCollectionAccount

        NotificationRecipient.objects.create(email='ana@test.com')
        hosting = HostingRecord.objects.create(
            client_name='Kore', monthly_value=Decimal('77760.00'),
        )
        document = Document.objects.create(
            title='Cuenta de cobro Kore', hosting_record=hosting,
        )
        DocumentCollectionAccount.objects.create(
            document=document, customer_email='cliente@test.com',
        )
        log = make_log(
            template_key='collection_account_sent',
            recipient='cliente@test.com',
            metadata={'document_id': document.id},
        )

        with patch(
            'content.services.collection_account_email_service'
            '.stored_collection_account_pdf',
            return_value=b'%PDF-1.4 fake',
        ):
            response = super_client.post(
                f'/api/accounting/email-log/{log.id}/retry/',
            )

        assert response.status_code == 201
        assert mailoutbox[-1].to == ['cliente@test.com']
        assert response.data['retry_of'] == log.id

    def _payment_confirmation_log(self, liquid_id, income_id):
        return make_log(
            template_key='income_payment_received_client',
            recipient='cliente@test.com',
            subject='Confirmación de pago — Cuenta de cobro PA-KORE-001',
            metadata={
                'income_id': income_id, 'liquid_id': liquid_id,
                'document_id': None, 'public_number': 'PA-KORE-001',
                'greeting_name': 'Ana', 'concept': 'Pago Kore',
                'project_name': '', 'amount': '400000.00',
                'payment_date': '2026-07-15', 'payment_date_precision': 'day',
                'pending_after': '600000.00',
            },
        )

    def test_a_payment_confirmation_retry_rebuilds_the_same_email(
        self, super_client, mailoutbox,
    ):
        """The retry states the balance the client was told, not today's."""
        from datetime import date

        from content.models import IncomeRecord

        expected = IncomeRecord.objects.create(
            concept='Kore', kind=IncomeRecord.Kind.EXPECTED,
            period_date=date(2026, 7, 1), total_amount=Decimal('1000000.00'),
        )
        liquid = IncomeRecord.objects.create(
            concept='Pago Kore', kind=IncomeRecord.Kind.LIQUID,
            period_date=date(2026, 7, 15), total_amount=Decimal('400000.00'),
            expected_income=expected,
        )
        log = self._payment_confirmation_log(liquid.id, expected.id)

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.status_code == 201
        assert response.data['retry_of'] == log.id
        assert mailoutbox[-1].to == ['cliente@test.com']
        assert mailoutbox[-1].subject == log.subject
        assert 'Saldo pendiente: $600.000 COP' in mailoutbox[-1].body

    def test_a_payment_confirmation_for_an_undone_payment_is_refused(
        self, super_client, mailoutbox,
    ):
        log = self._payment_confirmation_log(liquid_id=9999, income_id=9998)

        response = super_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        )

        assert response.status_code == 400
        assert 'ya no existe' in response.data['error']
        assert mailoutbox == []

    def test_every_retryable_notice_has_a_handler(self):
        from content.serializers.accounting import RETRYABLE_TEMPLATE_KEYS
        from content.services.accounting_email_retry_service import (
            RETRY_HANDLERS,
        )

        assert RETRYABLE_TEMPLATE_KEYS == frozenset(RETRY_HANDLERS)

    def test_is_superuser_only(self, admin_client):
        log = make_log()
        assert admin_client.post(
            f'/api/accounting/email-log/{log.id}/retry/',
        ).status_code == 403
