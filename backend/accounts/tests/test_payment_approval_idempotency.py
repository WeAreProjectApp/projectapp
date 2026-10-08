"""Approved payment retries preserve committed financial effects."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Notification,
    Payment,
    PaymentHistory,
    Project,
    UserProfile,
)
from accounts.tests.wompi_event_helpers import signed_transaction_event
from accounts.views import _handle_payment_approved

pytestmark = pytest.mark.django_db
APPROVED_AT = datetime(2026, 2, 1, 12, tzinfo=timezone.utc)
REPLAYED_AT = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def payment():
    """Create a pending hosting obligation with a client and administrator."""
    users = get_user_model()
    client = users.objects.create_user(username='approval-client', email='approval-client@example.com')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT)
    admin = users.objects.create_user(username='approval-admin', email='approval-admin@example.com')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN)
    project = Project.objects.create(name='Approval project', client=client, status=Project.STATUS_ACTIVE)
    subscription = HostingSubscription.objects.create(
        project=project, plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('100000'), effective_monthly_amount=Decimal('100000'),
        billing_amount=Decimal('300000'), start_date=date(2026, 1, 1),
        next_billing_date=date(2026, 1, 1), status=HostingSubscription.STATUS_PENDING,
    )
    return Payment.objects.create(
        subscription=subscription, amount=subscription.billing_amount,
        billing_period_start=date(2026, 1, 1), billing_period_end=date(2026, 3, 31),
        due_date=date(2026, 1, 1), wompi_payment_link_id='approval-link',
        wompi_transaction_id='approval-transaction',
    )


@pytest.fixture
def email_transport(monkeypatch):
    """Replace only the outbound email queue boundary."""
    transport = Mock()
    monkeypatch.setattr('accounts.tasks.send_payment_status_team_email_task', transport)
    return transport


@pytest.fixture
def clock(monkeypatch):
    """Freeze the approval clock independently of the repeated request."""
    monkeypatch.setattr('django.utils.timezone.now', lambda: APPROVED_AT)
    return monkeypatch


@pytest.fixture(params=['webhook', 'verify'])
def approve(request, payment, email_transport, clock, monkeypatch):
    """Approve through the actual webhook or authenticated verification API."""
    provider_transaction = {
        'id': payment.wompi_transaction_id, 'status': 'APPROVED',
        'amount_in_cents': int(payment.amount * 100), 'currency': 'COP',
        'reference': 'provider-reference', 'payment_link_id': payment.wompi_payment_link_id,
    }
    monkeypatch.setattr(
        'accounts.services.wompi.verify_transaction', lambda transaction_id: provider_transaction,
    )
    client = APIClient()
    client.force_authenticate(payment.subscription.project.client)
    requests = {
        'webhook': ('/api/accounts/webhooks/wompi/', signed_transaction_event(provider_transaction)),
        'verify': (
            f'/api/accounts/projects/{payment.subscription.project_id}/payments/{payment.pk}/verify/',
            {'transaction_id': payment.wompi_transaction_id},
        ),
    }
    path, payload = requests[request.param]
    expected_response = {
        'webhook': {'status': 'ok'},
        'verify': {
            'payment_id': payment.pk,
            'payment_status': Payment.STATUS_PAID,
            'transaction_status': 'APPROVED',
        },
    }[request.param]

    def submit():
        with TestCase.captureOnCommitCallbacks(execute=True):
            response = client.post(path, payload, format='json')
        assert response.status_code == 200
        assert response.json() == expected_response
        return response.json()

    return submit


def _effects(payment):
    payment.refresh_from_db()
    return {
        'paid_at': payment.paid_at,
        'history_count': PaymentHistory.objects.filter(payment=payment).count(),
        'payment_count': Payment.objects.filter(subscription_id=payment.subscription_id).count(),
        'notification_count': Notification.objects.filter(
            related_object_type='payment', related_object_id=payment.pk,
        ).count(),
    }


@pytest.mark.parametrize('effect', ['paid_at', 'history_count', 'payment_count', 'notification_count'])
def test_replay_preserves_confirmed_payment_effect(payment, approve, clock, effect):
    """A repeated approval preserves each committed financial effect."""
    approve()
    confirmed = _effects(payment)
    expected_first_effect = {
        'paid_at': APPROVED_AT,
        'history_count': 1,
        'payment_count': 2,
        'notification_count': 2,
    }
    assert confirmed[effect] == expected_first_effect[effect]
    clock.setattr('django.utils.timezone.now', lambda: REPLAYED_AT)

    approve()

    assert _effects(payment)[effect] == confirmed[effect]


def test_old_cycle_replay_preserves_later_renewal(payment, approve, clock):
    """An old paid cycle cannot move the subscription renewal backwards."""
    approve()
    later_renewal = date(2026, 10, 1)
    HostingSubscription.objects.filter(pk=payment.subscription_id).update(next_billing_date=later_renewal)
    clock.setattr('django.utils.timezone.now', lambda: REPLAYED_AT)

    approve()

    assert HostingSubscription.objects.get(pk=payment.subscription_id).next_billing_date == later_renewal


def test_stale_payment_instance_cannot_repeat_approval(payment, email_transport, clock):
    """An instance loaded before settlement observes the committed approval."""
    stale = Payment.objects.get(pk=payment.pk)
    with TestCase.captureOnCommitCallbacks(execute=True):
        _handle_payment_approved(payment)
    committed = _effects(payment)
    clock.setattr('django.utils.timezone.now', lambda: REPLAYED_AT)

    with TestCase.captureOnCommitCallbacks(execute=True):
        _handle_payment_approved(stale)

    assert _effects(payment) == committed
    assert stale.status == Payment.STATUS_PAID


def test_failed_approval_rolls_back_financial_effects(payment, email_transport, clock):
    """A failure after settlement writes rolls back the financial effects."""
    Payment.objects.filter(pk=payment.pk).update(billing_period_end=date.max)
    before = _effects(payment)

    with TestCase.captureOnCommitCallbacks(execute=True), pytest.raises(OverflowError):
        _handle_payment_approved(payment)

    assert _effects(payment) == before
    assert Payment.objects.get(pk=payment.pk).status == Payment.STATUS_PENDING


def test_failed_approval_does_not_enqueue_email(payment, email_transport, clock):
    """A rolled-back settlement cannot send an approval email."""
    Payment.objects.filter(pk=payment.pk).update(billing_period_end=date.max)

    with TestCase.captureOnCommitCallbacks(execute=True), pytest.raises(OverflowError):
        _handle_payment_approved(payment)

    assert email_transport.call_count == 0
    assert PaymentHistory.objects.filter(payment=payment).count() == 0


def test_retry_completes_rolled_back_approval(payment, email_transport, clock):
    """A corrected retry completes the previously rolled-back settlement."""
    Payment.objects.filter(pk=payment.pk).update(billing_period_end=date.max)
    with TestCase.captureOnCommitCallbacks(execute=True), pytest.raises(OverflowError):
        _handle_payment_approved(payment)
    Payment.objects.filter(pk=payment.pk).update(billing_period_end=date(2026, 3, 31))

    with TestCase.captureOnCommitCallbacks(execute=True):
        _handle_payment_approved(payment)

    payment.refresh_from_db()
    assert payment.status == Payment.STATUS_PAID
    assert PaymentHistory.objects.filter(payment=payment).count() == 1
    assert Payment.objects.filter(subscription_id=payment.subscription_id).count() == 2


def test_approval_email_waits_for_commit(payment, email_transport, clock):
    """The transport receives only an approval whose transaction committed."""
    with TestCase.captureOnCommitCallbacks(execute=True):
        with transaction.atomic():
            _handle_payment_approved(payment)
            assert email_transport.call_count == 0

    assert email_transport.call_count == 1
    assert Payment.objects.get(pk=payment.pk).status == Payment.STATUS_PAID


def test_replay_does_not_enqueue_another_email(payment, approve, email_transport):
    """A repeated API approval does not queue another outcome email."""
    approve()

    approve()

    assert email_transport.call_count == 1
    assert PaymentHistory.objects.filter(payment=payment).count() == 1
