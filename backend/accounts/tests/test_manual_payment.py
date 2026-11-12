"""Tests for the manual payment registration endpoint."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    UserProfile,
)
from accounts.services.project_phases import add_phase
from accounts.services.tokens import get_tokens_for_user

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user(db):
    u = User.objects.create_user(
        username='admin@example.com', email='admin@example.com', password='x',
    )
    UserProfile.objects.create(user=u, role='admin', is_onboarded=True, profile_completed=True)
    return u


@pytest.fixture
def client_user(db):
    user = User.objects.create_user(
        username='client@example.com', email='client@example.com', password='x',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return user


@pytest.fixture
def project(client_user):
    return Project.objects.create(name='Test project', client=client_user)


@pytest.fixture
def authed_client(admin_user):
    tokens = get_tokens_for_user(admin_user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    return c


MANUAL_URL = '/api/accounts/projects/{}/payments/manual/'


def test_register_manual_creates_subscription_and_payment(authed_client, project):
    resp = authed_client.post(
        MANUAL_URL.format(project.id),
        {
            'frequency': 'semiannual',
            'amount': '1200000',
            'billing_period_start': '2026-03-01',
            'description': 'Transferencia Bancolombia',
        },
        format='json',
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data['status'] == 'paid'
    assert data['amount'] == '1200000.00'
    assert data['billing_period_start'] == '2026-03-01'
    assert data['billing_period_end'] == '2026-08-31'

    sub = HostingSubscription.objects.get(project=project)
    assert sub.status == HostingSubscription.STATUS_ACTIVE
    assert sub.plan == HostingSubscription.PLAN_SEMIANNUAL
    assert str(sub.next_billing_date) == '2026-09-01'


def test_register_manual_payment_creates_history_with_manual_source(authed_client, project):
    authed_client.post(
        MANUAL_URL.format(project.id),
        {'frequency': 'quarterly', 'amount': '200000', 'billing_period_start': '2026-04-01'},
        format='json',
    )
    payment = Payment.objects.get(subscription__project=project)
    history = PaymentHistory.objects.get(payment=payment)
    assert history.source == PaymentHistory.SOURCE_MANUAL
    assert history.to_status == Payment.STATUS_PAID


def test_register_manual_quarterly_period_end(authed_client, project):
    resp = authed_client.post(
        MANUAL_URL.format(project.id),
        {'frequency': 'quarterly', 'amount': '600000', 'billing_period_start': '2026-01-01'},
        format='json',
    )
    assert resp.status_code == 201
    assert resp.json()['billing_period_end'] == '2026-03-31'


def test_register_manual_on_existing_subscription_extends_next_billing(authed_client, project):
    sub = HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_MONTHLY,
        base_monthly_amount=200000,
        discount_percent=0,
        effective_monthly_amount=200000,
        billing_amount=200000,
        status=HostingSubscription.STATUS_ACTIVE,
        start_date='2026-03-01',
        next_billing_date='2026-04-01',
    )
    authed_client.post(
        MANUAL_URL.format(project.id),
        {'frequency': 'semiannual', 'amount': '1200000', 'billing_period_start': '2026-04-01'},
        format='json',
    )
    sub.refresh_from_db()
    assert str(sub.next_billing_date) == '2026-10-01'


def test_register_manual_rejects_non_admin(project, client_user):
    tokens = get_tokens_for_user(client_user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    resp = c.post(
        MANUAL_URL.format(project.id),
        {'frequency': 'monthly', 'amount': '200000', 'billing_period_start': '2026-04-01'},
        format='json',
    )
    assert resp.status_code == 403


def test_register_manual_rejects_missing_fields(authed_client, project):
    resp = authed_client.post(
        MANUAL_URL.format(project.id),
        {'frequency': 'quarterly'},
        format='json',
    )
    assert resp.status_code == 400


def test_register_manual_rejects_invalid_frequency(authed_client, project):
    resp = authed_client.post(
        MANUAL_URL.format(project.id),
        {'frequency': 'weekly', 'amount': '100000', 'billing_period_start': '2026-04-01'},
        format='json',
    )
    assert resp.status_code == 400
