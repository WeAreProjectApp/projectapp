"""Synthetic operating service and the two public payment entry points for billing tests."""
from datetime import date
from uuid import uuid4

import pytest

from accounts.models import Payment
from accounts.services.hosting_context import reconcile_hosting
from content.models import IncomeRecord
from content.services import hosting_periods


@pytest.fixture
def billing(api_client, admin_user, hosting_record, subscription, monkeypatch):
    monkeypatch.setattr(hosting_periods, 'today_bogota', lambda: date(2026, 11, 26))
    admin_user.is_superuser = True
    admin_user.save(update_fields=['is_superuser'])
    api_client.force_authenticate(admin_user)
    reconcile_hosting(hosting_record.project_id, admin_user, {
        'expected_version': 0, 'reason': 'Fixture de cobros', 'subscription_id': subscription.pk,
        'hosting_record_ids': [hosting_record.pk], 'operational_record_id': hosting_record.pk,
    })
    payment = Payment.objects.create(subscription=subscription, amount=233280, status='pending',
                                     billing_period_start=date(2026, 4, 1), billing_period_end=date(2026, 6, 30),
                                     due_date=date(2026, 4, 5))
    income = IncomeRecord.objects.create(project=hosting_record.project, client=hosting_record.client, kind='expected',
                                         concept='Hosting de prueba', origin='hosting', period_start=payment.billing_period_start,
                                         period_end=payment.billing_period_end, period_cadence='quarterly',
                                         period_date=payment.due_date, total_amount=payment.amount)
    return api_client, hosting_record, income


def payment_inputs(billing, value='50000.00', folio='A', **cycle_options):
    client, record, income = billing
    identity = {'issuer': 'Recibos DEV', 'reference': folio,
                'entries': [{'income_id': income.pk, 'hosting_record_id': record.pk}]}
    shared = {'destination': 'pocket', 'hosting_receipt': identity}
    cycle = {**shared, 'request_id': str(uuid4()), 'amount': value, 'income_id': income.pk,
             'paid_at': '2026-05-17', **cycle_options}
    settlement = {**shared, 'request_id': str(uuid4()), 'total_amount': value,
                  'income_ids': [income.pk], 'period_date': '2026-05-17'}
    return cycle, settlement


def from_hosting(billing, payload):
    client, record, _ = billing
    url = f'/api/accounting/hostings/{record.pk}/cycle-receipt/'
    preview = client.post(url + '?preview=1', payload, format='json')
    assert preview.status_code == 200, preview.data
    return client.post(url, {**payload, 'preview_hash': preview.data['preview_hash']}, format='json')


def from_incomes(billing, payload):
    client, _, _ = billing
    return client.post('/api/accounting/incomes/bulk-settle/', payload, format='json')
