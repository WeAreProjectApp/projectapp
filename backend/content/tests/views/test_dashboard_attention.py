"""Radar lists, resolution and access rules."""
from datetime import date
from uuid import uuid4

import pytest
from django.utils import timezone
from freezegun import freeze_time

from content.models import BusinessProposal, Document, DocumentType, EmailBody, EmailDeliverySnapshot, EmailLog, RecurringPayment, Task
from content.services.dashboard_attention_service import failed_email_incidents
from content.services.panel_dashboard_service import build_panel_dashboard

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock():
    with freeze_time('2026-10-26 15:00:00'):
        yield timezone.now()
BASE = '/api/panel/dashboard/attention/'


def attempt(parent=None, status='failed', snapshot=None, **extra):
    snapshot = snapshot or EmailDeliverySnapshot.objects.create(
        delivery_id=uuid4(), body=EmailBody.objects.create(text='Retained message'),
        template_key='standalone', classification='client', resend_of=parent,
    )
    return EmailLog.objects.create(
        recipient='client@example.test', template_key='standalone', subject='Invoice',
        status=status, snapshot=snapshot, delivery_id=snapshot.delivery_id, **extra,
    )


def test_task_page_limits_results(admin_client):
    for number in range(7):
        Task.objects.create(title=f'Late {number}', due_date=date(2026, 10, 20))
    data = admin_client.get(f'{BASE}tasks_overdue/').json()
    assert len(data['results']) == 5
    assert data['total'] == 7
    assert data['has_next'] is True


def test_second_page_keeps_order(admin_client):
    tasks = [Task.objects.create(title=f'Late {n}', due_date=date(2026, 10, 20)) for n in range(7)]
    data = admin_client.get(f'{BASE}tasks_overdue/?page=2').json()
    assert [row['id'] for row in data['results']] == [row.pk for row in tasks[5:]]
    assert data['has_next'] is False


def test_completed_task_is_excluded(admin_client):
    Task.objects.create(title='Done', due_date=date(2026, 10, 20), status='done')
    assert admin_client.get(f'{BASE}tasks_overdue/').json()['total'] == 0


def test_changed_record_is_inspectable(admin_client):
    task = Task.objects.create(title='Done', status='done')
    data = admin_client.get(f'{BASE}tasks_overdue/{task.pk}/').json()
    assert data['eligible'] is False
    assert data['destination'] == f'/panel/tasks?task={task.pk}&radar=1'


def test_missing_record_returns_not_found(admin_client):
    assert admin_client.get(f'{BASE}tasks_overdue/999999/').status_code == 404


def test_staff_cannot_read_recurring_detail(admin_client):
    payment = RecurringPayment.objects.create(name='Private', price=500, billing_day=28)
    assert admin_client.get(f'{BASE}recurring_due/{payment.pk}/').status_code == 403


def test_anonymous_is_rejected(api_client):
    assert api_client.get(f'{BASE}tasks_overdue/').status_code in (401, 403)


def test_unknown_type_is_rejected(admin_client):
    assert admin_client.get(f'{BASE}unknown/').status_code == 404


def test_invalid_page_is_rejected(admin_client):
    assert admin_client.get(f'{BASE}tasks_overdue/?page=0').status_code == 400


def test_recurring_payload_keeps_currency(super_client):
    payment = RecurringPayment.objects.create(name='Service', price='12.50', currency='USD', billing_day=28)
    data = super_client.get(f'{BASE}recurring_due/').json()['results'][0]
    assert data['id'] == payment.pk
    assert data['amount'] == '12.50'
    assert data['due_date'] == '2026-10-28'


def test_muted_recurring_is_excluded(super_client):
    RecurringPayment.objects.create(name='Muted', price=500, billing_day=28, reminders_muted=True)
    assert super_client.get(f'{BASE}recurring_due/').json()['total'] == 0


def test_collection_payload_identifies_client(admin_client):
    kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Collection'})
    doc = Document.objects.create(title='CC-42', document_type=kind, client_name='ACME', commercial_status='issued', due_date=date(2026, 10, 20), total=900)
    data = admin_client.get(f'{BASE}documents_overdue/').json()['results'][0]
    assert data['client'] == 'ACME'
    assert data['destination'] == f'/panel/documents/{doc.pk}/edit?radar=1'


def test_stale_proposal_counts_days(admin_client):
    proposal = BusinessProposal.objects.create(title='Website', client_name='ACME', status='sent', sent_at=timezone.datetime(2026, 10, 10, 15, tzinfo=timezone.get_current_timezone()))
    data = admin_client.get(f'{BASE}proposals_stale/').json()['results'][0]
    assert data['id'] == proposal.pk
    assert data['days_unopened'] == 16


def test_recipient_rows_form_one_incident(admin_client):
    original = attempt()
    attempt(snapshot=original.snapshot, recipient_kind='cc')
    assert admin_client.get(f'{BASE}emails_failed/').json()['total'] == 1


def test_successful_retry_clears_incident(frozen_clock):
    original = attempt()
    attempt(parent=original.snapshot, status='sent')
    assert failed_email_incidents(frozen_clock) == []


def test_failed_retry_does_not_multiply_incidents(frozen_clock):
    original = attempt()
    retry = attempt(parent=original.snapshot)
    assert [row['id'] for row in failed_email_incidents(frozen_clock)] == [retry.pk]


def test_nested_retry_success_clears_incident(frozen_clock):
    original = attempt()
    retry = attempt(parent=original.snapshot)
    attempt(parent=retry.snapshot, status='delivered')
    assert failed_email_incidents(frozen_clock) == []


def test_email_diagnostics_are_safe(admin_client):
    original = attempt(error_message='smtp-password-secret')
    data = admin_client.get(f'{BASE}emails_failed/{original.pk}/').json()
    assert 'smtp-password-secret' not in str(data)
    assert data['error_message'] == 'No se pudo completar el envío de correo.'


def test_copy_success_cannot_clear_failure(frozen_clock):
    original = attempt()
    attempt(parent=original.snapshot, status='sent', delivery_role='copy')
    assert len(failed_email_incidents(frozen_clock)) == 1


def test_summary_total_matches_list(admin_client):
    original = attempt()
    attempt(parent=original.snapshot)
    summary = build_panel_dashboard(include_finance=False)
    count = next(item['count'] for item in summary['attention'] if item['type'] == 'emails_failed')
    assert count == admin_client.get(f'{BASE}emails_failed/').json()['total']
