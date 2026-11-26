"""Account issued from a Hosting row, using the same decision shown in the panel."""
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.core import mail
from freezegun import freeze_time
from pypdf import PdfReader

from accounts.models import Payment
from accounts.services.hosting_context import reconcile_hosting
from content.models import Document, IncomeRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def row_billing(api_client, admin_user, hosting_record, subscription, payment):
    """A paid first quarter, a different price for the next one and a local recipient."""
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    api_client.force_authenticate(admin_user)
    hosting_record.client_email = 'alfa@example.invalid'
    hosting_record.domain_url = 'https://alfa.example.invalid'
    hosting_record.save(update_fields=['client_email', 'domain_url'])
    reconcile_hosting(hosting_record.project_id, admin_user, {
        'expected_version': 0, 'reason': 'Servicio ficticio Alfa',
        'subscription_id': subscription.pk, 'hosting_record_ids': [hosting_record.pk],
        'operational_record_id': hosting_record.pk,
    })
    current = Payment.objects.create(
        subscription=subscription, status='pending', amount=Decimal('236500.00'),
        billing_period_start=date(2026, 4, 1), billing_period_end=date(2026, 6, 30),
        due_date=date(2026, 4, 10),
    )
    return api_client, hosting_record, current


def read_period(client, row):
    response = client.get(f'/api/admin/billing-context/projects/{row.project_id}/hosting/')
    assert response.status_code == 200
    return response.data['billing_period']


def confirm(client, row, period):
    return client.post(f'/api/accounting/hostings/{row.pk}/send-collection-account/', {
        'hosting_payment_id': period['hosting_payment_id'], 'period_version': period['version'],
    }, format='json')


def pdf_text(pdf):
    return ' '.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


@freeze_time('2026-05-18')
def test_opening_the_row_preserves_reminders_and_billing_history(row_billing):
    client, row, current = row_billing
    before = (row.billing_requested_at, row.expiry_notice_target, row.cycles.count())

    period = read_period(client, row)

    assert period['hosting_record_id'] == row.pk
    assert period['client_id'] == row.client_id
    assert period['hosting_payment_id'] == current.pk
    row.refresh_from_db()
    assert (row.billing_requested_at, row.expiry_notice_target, row.cycles.count()) == before
    assert not row.collection_documents.exists()
    assert not mail.outbox


@freeze_time('2026-05-18')
def test_document_delivered_to_the_row_matches_its_reviewed_period(row_billing):
    client, row, _ = row_billing
    period = read_period(client, row)

    response = confirm(client, row, period)

    assert response.status_code == 201, response.data
    document = Document.objects.get(pk=response.data['document']['id'])
    item = document.items.get()
    assert (item.period_start.isoformat(), item.period_end.isoformat()) == (
        period['period_start'], period['period_end'],
    ) == ('2026-04-01', '2026-06-30')
    assert Decimal(period['balance']) == item.line_total == document.total == Decimal('236500')
    message, = mail.outbox
    assert message.to == ['alfa@example.invalid']
    attachment, = message.attachments
    assert (attachment.filename, attachment.mimetype) == (f'{document.public_number}.pdf', 'application/pdf')
    for text in (message.body, pdf_text(attachment.content)):
        assert '01/04/2026' in text
        assert '30/06/2026' in text
        assert '236.500' in text
    row.refresh_from_db()
    assert row.billing_requested_at is not None


@freeze_time('2026-05-18')
def test_income_preview_without_due_date_preserves_the_period_billed_from_hostings(row_billing):
    client, row, current = row_billing
    income = IncomeRecord.objects.create(
        project=row.project, client=row.client, kind='expected', origin='hosting', concept='Hosting Alfa',
        period_start=current.billing_period_start, period_end=current.billing_period_end,
        period_cadence='quarterly', period_date=current.due_date, total_amount=current.amount, vat_rate=None,
    )
    period = read_period(client, row)
    preview = client.post('/api/accounting/collection-accounts/preview/', {
        'income_record_id': income.pk, 'client_profile_id': row.client_id,
        'customer': {'email': row.billing_email}, 'billing_nature': 'hosting',
        'project_hosting_id': period['project_hosting_id'], 'hosting_payment_id': period['hosting_payment_id'],
        'period_version': period['version'], 'show_vat': False, 'due_date_mode': 'none',
        'items': [{'description': 'Servicio de hosting Alfa', 'quantity': '1', 'unit_price': period['balance']}],
    }, format='json')

    assert preview.status_code == 200
    assert preview.data['due_date'] is None
    assert preview.data['show_vat'] is False
    preview_file = client.get(preview.data['pdf_url'])
    assert preview_file.status_code == 200
    preview_text = pdf_text(preview_file.content)
    assert 'Fecha de vencimiento' not in preview_text
    assert 'Valor antes de IVA' not in preview.data['html_body']
    assert not row.collection_documents.exists()
    assert not mail.outbox

    assert confirm(client, row, period).status_code == 201
    document = row.collection_documents.get()
    assert Decimal(preview.data['total']) == document.total
    assert document.collection_account.due_date_mode == 'legacy'
    assert document.due_date is not None
    message, = mail.outbox
    for text in (preview_text, preview.data['html_body'], message.body, pdf_text(message.attachments[0].content)):
        assert '01/04/2026' in text
        assert '30/06/2026' in text


@freeze_time('2026-05-18')
def test_retrying_an_issued_row_sends_only_one_account(row_billing):
    client, row, _ = row_billing
    period = read_period(client, row)
    assert confirm(client, row, period).status_code == 201

    retry = confirm(client, row, period)

    assert retry.status_code == 400
    assert row.collection_documents.count() == 1
    assert len(mail.outbox) == 1


@freeze_time('2026-05-18')
def test_payment_reconciled_after_read_prevents_delivery(row_billing):
    client, row, current = row_billing
    period = read_period(client, row)
    current.status = 'paid'
    current.save(update_fields=['status'])

    result = confirm(client, row, period)

    assert result.status_code == 400
    assert not row.collection_documents.exists()
    assert not mail.outbox
    row.refresh_from_db()
    assert row.billing_requested_at is None
