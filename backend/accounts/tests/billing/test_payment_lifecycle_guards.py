"""Money paths recheck lifecycle state before writing or contacting Wompi."""

from datetime import date
from unittest.mock import Mock

import pytest
from accounts.models import (
    BillingContextEvent,
    HostingSubscription,
    Notification,
    Payment,
    ProjectPhase,
)
from accounts.services.hosting_subscription_lifecycle import PaymentChargeSkipped
from accounts.tasks import _onboard_due_phases, auto_charge_due_subscriptions
from accounts.tests.billing import (
    test_hosting_subscription_lifecycle as lifecycle_fixtures,
)
from accounts.tests.billing.test_hosting_subscription_lifecycle import (
    TODAY,
    enact,
)
from accounts.views import (
    _charge_payment_with_source,
    _generate_next_payment,
    _handle_payment_approved,
)
from content.models import BusinessProposal
from content.services.project_state_service import project_state_suggestion
from django.test import TestCase

pytestmark = pytest.mark.django_db
clock = lifecycle_fixtures.clock
lifecycle = lifecycle_fixtures.lifecycle
obligation = lifecycle_fixtures.obligation


def prepare_late_settlement(subscription, payment, actor, mode):
    if mode in ('cancelled', 'paused'):
        enact(subscription, actor, {'cancelled': 'cancel', 'paused': 'pause'}[mode])
    else:
        Payment.objects.filter(pk=payment.pk).update(is_archived=True, status={'voided': 'voided', 'archived': 'pending'}[mode])


def candidate_iterator(original_iter, subscription, new_status):
    def iterate(queryset):
        candidates = original_iter(queryset)
        if queryset.model is ProjectPhase and not queryset.query.select_for_update:
            HostingSubscription.objects.filter(pk=subscription.pk).update(status=new_status)
        return candidates
    return iterate


def stale_event_iterator(original_iter):
    def iterate(queryset):
        if queryset.model is BillingContextEvent and not queryset.query.select_for_update:
            return iter([])
        return original_iter(queryset)
    return iterate


@pytest.mark.parametrize('method,endpoint', [
    ('post', 'generate-link'), ('get', 'widget-data'), ('post', 'card-pay'), ('post', 'charge'),
])
@pytest.mark.parametrize('payment_updates', [{'is_archived': True}, {'status': 'voided'}], ids=['archived', 'voided'])
def test_pay_endpoint_refuses_hidden_obligation(api_client, admin_user, obligation, method, endpoint, payment_updates, monkeypatch):
    Payment.objects.filter(pk=obligation.pk).update(**payment_updates)
    provider = Mock()
    monkeypatch.setattr('accounts.services.wompi.create_payment_link', provider)
    monkeypatch.setattr('accounts.services.wompi.tokenize_card', provider)
    monkeypatch.setattr('accounts.services.wompi.charge_with_payment_source', provider)
    api_client.force_authenticate(admin_user)
    before = list(Payment.objects.filter(pk=obligation.pk).values())

    response = getattr(api_client, method)(
        f'/api/accounts/projects/{obligation.subscription.project_id}/payments/{obligation.pk}/{endpoint}/',
        {}, format='json',
    )

    assert response.status_code == 400
    assert 'detail' in response.data
    provider.assert_not_called()
    assert before == list(Payment.objects.filter(pk=obligation.pk).values())
    assert not obligation.history.exists()


@pytest.mark.parametrize('mode', ['cancelled', 'paused', 'archived', 'voided'])
def test_late_approval_settles_without_new_billing(lifecycle, obligation, admin_user, mode, monkeypatch):
    prepare_late_settlement(lifecycle, obligation, admin_user, mode)
    email = Mock()
    monkeypatch.setattr('accounts.tasks.send_payment_status_team_email_task', email)
    previous = HostingSubscription.objects.filter(pk=lifecycle.pk).values('status', 'next_billing_date').get()
    obligation.wompi_transaction_id = 'late-approved'

    with TestCase.captureOnCommitCallbacks(execute=True):
        _handle_payment_approved(obligation, 'webhook')

    assert obligation.status == 'paid' and obligation.paid_at.date() == TODAY
    assert obligation.is_archived is False and obligation.archived_at is None
    assert HostingSubscription.objects.filter(pk=lifecycle.pk).values('status', 'next_billing_date').get() == previous
    assert Payment.objects.filter(subscription=lifecycle).count() == 1
    history = obligation.history.get(to_status='paid')
    assert history.metadata['settled_after_void'] is True
    event = BillingContextEvent.objects.get(pk=history.metadata['event_id'])
    assert event.operation == 'hosting_subscription.settled_after_void'
    assert event.after['subscription_id'] == lifecycle.pk and event.after['payment_id'] == obligation.pk
    assert Notification.objects.filter(user=admin_user, related_object_id=obligation.pk, title__startswith='Cobro tardío').exists()
    paid_at, history_count, event_count = obligation.paid_at, obligation.history.count(), BillingContextEvent.objects.count()

    with TestCase.captureOnCommitCallbacks(execute=True):
        _handle_payment_approved(obligation, 'webhook')

    assert obligation.paid_at == paid_at
    assert obligation.history.count() == history_count and BillingContextEvent.objects.count() == event_count
    assert email.call_count == 1


@pytest.mark.parametrize('action', ['cancel', 'pause'])
def test_manual_payment_preserves_lifecycle(api_client, admin_user, lifecycle, obligation, action):
    enact(lifecycle, admin_user, action)
    before = HostingSubscription.objects.filter(pk=lifecycle.pk).values('status', 'next_billing_date').get()
    api_client.force_authenticate(admin_user)

    response = api_client.post(f'/api/accounts/projects/{lifecycle.project_id}/payments/manual/', {
        'frequency': 'semiannual', 'amount': 4800, 'billing_period_start': '2026-10-09',
    }, format='json')

    assert response.status_code == 201
    assert response.data['status'] == 'paid'
    assert HostingSubscription.objects.filter(pk=lifecycle.pk).values('status', 'next_billing_date').get() == before
    assert Payment.objects.filter(subscription=lifecycle, status='paid').count() == 1


@pytest.mark.parametrize('payment_updates,subscription_status', [
    ({'status': 'voided', 'is_archived': True}, 'active'), ({'is_archived': True}, 'active'),
    ({'status': 'paid'}, 'active'), ({}, 'cancelled'), ({}, 'suspended'),
    ({'status': 'failed'}, 'active'),
])
def test_stored_charge_rechecks_stale_queue_item(lifecycle, obligation, payment_updates, subscription_status, monkeypatch):
    HostingSubscription.objects.filter(pk=lifecycle.pk).update(status=subscription_status, wompi_payment_source_id='source')
    Payment.objects.filter(pk=obligation.pk).update(**payment_updates)
    provider = Mock()
    monkeypatch.setattr('accounts.services.wompi.charge_with_payment_source', provider)
    before = list(Payment.objects.filter(pk=obligation.pk).values())

    with pytest.raises(PaymentChargeSkipped):
        _charge_payment_with_source(obligation)

    provider.assert_not_called()
    assert list(Payment.objects.filter(pk=obligation.pk).values()) == before
    assert not obligation.history.exists()


def test_skipped_cron_charge_does_not_consume_retry(lifecycle, obligation, admin_user, monkeypatch):
    HostingSubscription.objects.filter(pk=lifecycle.pk).update(wompi_payment_source_id='source')
    Payment.objects.filter(pk=obligation.pk).update(due_date=TODAY)
    from accounts import views
    real_charge = views._charge_payment_with_source

    def cancel_before_charge(payment, history_source):
        enact(lifecycle, admin_user, 'cancel')
        return real_charge(payment, history_source)

    monkeypatch.setattr(views, '_charge_payment_with_source', cancel_before_charge)
    provider = Mock()
    monkeypatch.setattr('accounts.services.wompi.charge_with_payment_source', provider)

    result = auto_charge_due_subscriptions.call_local()

    provider.assert_not_called()
    obligation.refresh_from_db()
    lifecycle.refresh_from_db()
    assert result == {'charged': 0, 'failed': 0}
    assert obligation.status == 'pending' and obligation.charge_attempts == 0 and obligation.next_retry_at is None
    assert lifecycle.status == 'cancelled'


@pytest.mark.parametrize('action', ['pause', 'cancel'])
def test_next_payment_stops_on_manual_lifecycle(lifecycle, obligation, admin_user, action):
    enact(lifecycle, admin_user, action)

    result = _generate_next_payment(lifecycle)

    assert result is None
    assert Payment.objects.filter(subscription=lifecycle).count() == 1


def test_failure_suspension_keeps_renewal_behavior(lifecycle, obligation):
    HostingSubscription.objects.filter(pk=lifecycle.pk).update(status='suspended')
    Payment.objects.filter(pk=obligation.pk).update(is_archived=True)

    result = _generate_next_payment(lifecycle)

    assert result.status == 'pending' and result.is_archived is False
    assert result.due_date == date(2026, 12, 1)
    assert Payment.objects.filter(subscription=lifecycle).count() == 2


@pytest.mark.parametrize('new_status', ['suspended', 'cancelled'])
def test_onboarding_rechecks_state_after_candidate_read(lifecycle, obligation, monkeypatch, new_status):
    from django.db.models.query import QuerySet
    proposal = BusinessProposal.objects.create(title='Fase pendiente', client_name='Cliente', total_investment=12000000)
    phase = ProjectPhase.objects.create(project=lifecycle.project, business_proposal=proposal,
                                         hosting_start_date=TODAY, order=1)
    original_iter = QuerySet.__iter__

    monkeypatch.setattr(QuerySet, '__iter__', candidate_iterator(original_iter, lifecycle, new_status))

    result = _onboard_due_phases()

    assert result == 0
    phase.refresh_from_db()
    assert phase.hosting_activated_at is None
    assert Payment.objects.filter(subscription=lifecycle).count() == 1
    lifecycle.refresh_from_db()
    assert lifecycle.billing_amount == 4800


@pytest.mark.parametrize('requested_status', ['cancelled', 'invalid'])
def test_patch_status_requires_audited_lifecycle(api_client, admin_user, lifecycle, requested_status):
    api_client.force_authenticate(admin_user)
    previous = HostingSubscription.objects.filter(pk=lifecycle.pk).values().get()

    response = api_client.patch(f'/api/accounts/projects/{lifecycle.project_id}/subscription/',
                                {'status': requested_status, 'is_archived': True}, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'subscription_lifecycle_required'
    assert HostingSubscription.objects.filter(pk=lifecycle.pk).values().get() == previous
    assert not BillingContextEvent.objects.exists()


def test_manual_pause_has_distinct_project_suggestion(lifecycle, obligation, admin_user):
    enact(lifecycle, admin_user, 'pause')
    project = lifecycle.project
    project.refresh_from_db()

    suggestion = project_state_suggestion(project)

    assert suggestion['reason'] == 'hosting_subscription_paused'
    assert suggestion['message'].startswith('Suscripción pausada manualmente')
    assert 'fallidos' not in suggestion['message']


def test_approval_checks_latest_pause_outside_read_snapshot(lifecycle, obligation, admin_user, monkeypatch):
    from django.db.models.query import QuerySet
    Payment.objects.filter(pk=obligation.pk).update(due_date=TODAY)
    enact(lifecycle, admin_user, 'pause')
    monkeypatch.setattr(QuerySet, '__iter__', stale_event_iterator(QuerySet.__iter__))
    monkeypatch.setattr('accounts.tasks.send_payment_status_team_email_task', Mock())

    _handle_payment_approved(obligation, 'webhook')

    lifecycle.refresh_from_db()
    assert obligation.status == 'paid'
    assert lifecycle.status == 'suspended' and lifecycle.next_billing_date == date(2026, 12, 1)
    assert Payment.objects.filter(subscription=lifecycle).count() == 1
    assert obligation.history.get(to_status='paid').metadata['settled_after_void'] is True
