"""API tests for the accounting send log (tab Envíos).

This endpoint exists to answer "why didn't I get that notice", so what
matters is that it shows the recipient of every send, keeps the proposal
traffic that shares the EmailLog table out, and filters usefully.
"""
import pytest
from django.utils import timezone

from content.models import EmailLog
from content.serializers.accounting import EMAIL_TEMPLATE_LABELS

BASE = '/api/accounting/email-log/'


def make_log(template_key='accounting_change', **kwargs):
    defaults = {
        'recipient': 'ana@test.com',
        'subject': '[Contabilidad] Ingreso creado: Kore',
        'status': EmailLog.Status.SENT,
    }
    defaults.update(kwargs)
    return EmailLog.objects.create(template_key=template_key, **defaults)


@pytest.mark.django_db
class TestAccountingEmailLogList:
    def test_lists_one_row_per_recipient_with_its_state(self, super_client):
        make_log(recipient='ana@test.com')
        make_log(recipient='zoe@test.com', status=EmailLog.Status.FAILED,
                 error_message='SMTP timeout')

        response = super_client.get(BASE)

        assert response.status_code == 200
        results = response.data['results']
        assert {r['recipient'] for r in results} == {'ana@test.com', 'zoe@test.com'}
        failed = next(r for r in results if r['recipient'] == 'zoe@test.com')
        assert failed['status'] == 'failed'
        assert failed['error_message'] == 'SMTP timeout'

    def test_labels_the_notice_in_spanish(self, super_client):
        make_log(template_key='accounting_card_reminder')

        response = super_client.get(BASE)

        assert response.data['results'][0]['template_label'] == (
            'Recordatorio de deuda de tarjetas'
        )

    def test_excludes_emails_from_outside_the_module(self, super_client):
        make_log(template_key='accounting_change')
        make_log(template_key='proposal_sent', recipient='cliente@test.com')

        response = super_client.get(BASE)

        assert [r['template_key'] for r in response.data['results']] == [
            'accounting_change',
        ]

    def test_covers_every_notice_the_module_can_send(self, super_client):
        for key in EMAIL_TEMPLATE_LABELS:
            make_log(template_key=key)

        response = super_client.get(BASE)

        assert response.data['count'] == len(EMAIL_TEMPLATE_LABELS)

    def test_filters_by_recipient_substring(self, super_client):
        make_log(recipient='carlos18bp@gmail.com')
        make_log(recipient='team@projectapp.co')

        response = super_client.get(BASE, {'recipient': 'carlos18bp'})

        assert [r['recipient'] for r in response.data['results']] == [
            'carlos18bp@gmail.com',
        ]

    def test_filters_by_notice_and_by_status(self, super_client):
        make_log(template_key='accounting_change', status=EmailLog.Status.SENT)
        make_log(template_key='payment_status_team', status=EmailLog.Status.FAILED)

        by_key = super_client.get(BASE, {'template_key': 'payment_status_team'})
        by_status = super_client.get(BASE, {'status': 'failed'})

        assert by_key.data['count'] == 1
        assert by_status.data['count'] == 1
        assert by_status.data['results'][0]['template_key'] == 'payment_status_team'

    def test_filters_by_date_range(self, super_client):
        old = make_log()
        EmailLog.objects.filter(pk=old.pk).update(
            sent_at=timezone.now() - timezone.timedelta(days=10),
        )
        make_log(recipient='reciente@test.com')

        today = timezone.localdate().isoformat()
        response = super_client.get(BASE, {'date_from': today})

        assert [r['recipient'] for r in response.data['results']] == [
            'reciente@test.com',
        ]

    def test_rejects_a_malformed_date(self, super_client):
        response = super_client.get(BASE, {'date_from': 'ayer'})

        assert response.status_code == 400

    def test_paginates_at_twenty_per_page_newest_first(self, super_client):
        for index in range(25):
            make_log(recipient=f'r{index:02d}@test.com')

        first = super_client.get(BASE)
        second = super_client.get(BASE, {'page': 2})

        assert first.data['count'] == 25
        assert first.data['num_pages'] == 2
        assert len(first.data['results']) == 20
        assert len(second.data['results']) == 5
        # ordering = ['-sent_at'] on the model: the last write leads.
        assert first.data['results'][0]['recipient'] == 'r24@test.com'


def test_label_map_matches_the_keys_the_senders_actually_write():
    """The view filters by these keys, so a renamed TEMPLATE_KEY would drop
    that notice out of the log silently — pin them to the senders."""
    from accounts.services.payment_notifications import (
        TEMPLATE_KEY as PAYMENT_STATUS,
    )
    from content.services.accounting_card_reminder_service import (
        TEMPLATE_KEY as CARD_REMINDER,
    )
    from content.services.accounting_email_service import (
        TEMPLATE_KEY as CHANGE,
    )
    from content.services.accounting_payment_calendar_service import (
        TEMPLATE_KEY as CALENDAR,
    )
    from content.services.accounting_statement_reminder_service import (
        TEMPLATE_KEY as STATEMENT_REMINDER,
    )
    from content.services.collection_account_email_service import (
        TEMPLATE_KEY as COLLECTION,
    )
    from content.services.income_payment_confirmation_service import (
        TEMPLATE_KEY as PAYMENT_CONFIRMATION,
    )

    assert set(EMAIL_TEMPLATE_LABELS) == {
        CHANGE, CARD_REMINDER, STATEMENT_REMINDER, CALENDAR,
        COLLECTION, PAYMENT_CONFIRMATION, PAYMENT_STATUS,
    }


def test_frontend_template_options_mirror_the_label_map():
    """The history's template filter lists its options in the frontend; a
    key missing there leaves that notice unreachable from the filter."""
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[4]
        / 'frontend' / 'constants' / 'historyFilters.js'
    ).read_text()
    block = source.split('TEMPLATE_KEY_OPTIONS = [', 1)[1].split('];', 1)[0]
    options = dict(re.findall(r"value: '([a-z_]+)', label: '([^']+)'", block))

    assert options == EMAIL_TEMPLATE_LABELS


@pytest.mark.django_db
class TestAccountingEmailLogPermissions:
    def test_staff_without_superuser_is_forbidden(self, admin_client):
        assert admin_client.get(BASE).status_code == 403

    def test_anonymous_is_rejected(self, api_client):
        assert api_client.get(BASE).status_code in (401, 403)
