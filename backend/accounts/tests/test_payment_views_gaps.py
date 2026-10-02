"""Tests for uncovered branches in payment views.

Covers:
- payment_widget_data_view: success, not-found, invalid status
- payment_verify_transaction_view: success (APPROVED/DECLINED/other), not-found, missing transaction_id
- wompi_webhook_view: PA-pattern reference lookup, integer reference fallback,
  missing data (empty transaction_id/reference), other transaction status
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    UserProfile,
)
from accounts.tests.wompi_event_helpers import signed_transaction_event

User = get_user_model()

pytestmark = pytest.mark.django_db


def _binding_transaction(
    payment, transaction_id, transaction_status, *, reference=None,
    payment_link_id=None, amount_in_cents=None, currency='COP',
):
    return {
        'id': transaction_id,
        'status': transaction_status,
        'amount_in_cents': (
            int(payment.amount * 100)
            if amount_in_cents is None else amount_in_cents
        ),
        'currency': currency,
        'reference': (
            f'PA{payment.id}P{payment.subscription.project_id}T1700000000'
            if reference is None else reference
        ),
        'payment_link_id': payment_link_id,
    }


@pytest.fixture
def api_client():
    """Provide an API client for endpoint requests."""
    return APIClient()


@pytest.fixture
def admin_user():
    """Provide an authenticated administrator user."""
    user = User.objects.create_user(
        username='admin@wpv.com', email='admin@wpv.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    """Provide bearer headers for the administrator."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@wpv.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    """Provide an authenticated client user."""
    user = User.objects.create_user(
        username='client@wpv.com', email='client@wpv.com', password='clientpass1',
        first_name='Carlos', last_name='Ruiz',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, created_by=admin_user,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    """Provide bearer headers for the client."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@wpv.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    """Provide an active project owned by the client."""
    return Project.objects.create(
        name='Widget Project', client=client_user,
        status=Project.STATUS_ACTIVE,
    )


@pytest.fixture
def subscription(project):
    """Provide an active hosting subscription for the project."""
    sub = HostingSubscription(
        project=project, plan=HostingSubscription.PLAN_MONTHLY,
        base_monthly_amount=Decimal('300000'), discount_percent=0,
        start_date='2026-01-01', next_billing_date='2026-02-01',
        status=HostingSubscription.STATUS_ACTIVE,
    )
    sub.calculate_amounts()
    sub.save()
    return sub


@pytest.fixture
def pending_payment(subscription):
    """Provide an open payment for the subscription."""
    return Payment.objects.create(
        subscription=subscription,
        amount=subscription.billing_amount,
        description='Monthly hosting',
        billing_period_start='2026-02-01',
        billing_period_end='2026-02-28',
        due_date='2026-02-01',
        status=Payment.STATUS_PENDING,
    )


@pytest.fixture
def paid_payment(subscription):
    """Provide a settled payment for the subscription."""
    return Payment.objects.create(
        subscription=subscription,
        amount=subscription.billing_amount,
        description='Paid hosting',
        billing_period_start='2026-01-01',
        billing_period_end='2026-01-31',
        due_date='2026-01-01',
        status=Payment.STATUS_PAID,
    )


# ===========================================================================
# payment_widget_data_view
# ===========================================================================

class TestPaymentWidgetDataView:
    """Covers payment widget data view behavior."""

    @override_settings(
        WOMPI_PUBLIC_KEY='pub_test_key',
        WOMPI_INTEGRITY_SECRET='integrity_secret',
        FRONTEND_BASE_URL='http://localhost:3000',
    )
    def test_client_gets_widget_data_for_pending_payment(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Client can GET widget data for their own pending payment."""
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/widget-data/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert 'public_key' in data
        assert 'integrity_signature' in data
        assert 'amount_in_cents' in data
        assert data['currency'] == 'COP'

    @override_settings(
        WOMPI_PUBLIC_KEY='pub_test_key',
        WOMPI_INTEGRITY_SECRET='integrity_secret',
        FRONTEND_BASE_URL='https://projectapp.co',
    )
    def test_https_base_url_includes_redirect_url(
        self, api_client, client_headers, project, pending_payment,
    ):
        """When FRONTEND_BASE_URL is https, redirect_url is included in response."""
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/widget-data/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert 'redirect_url' in data
        assert 'https://projectapp.co' in data['redirect_url']

    @override_settings(
        WOMPI_PUBLIC_KEY='pub_test_key',
        WOMPI_INTEGRITY_SECRET='integrity_secret',
        FRONTEND_BASE_URL='http://localhost:3000',
    )
    def test_returns_400_for_paid_payment(
        self, api_client, client_headers, project, paid_payment,
    ):
        """Returns 400 when payment status is not payable."""
        url = f'/api/accounts/projects/{project.id}/payments/{paid_payment.id}/widget-data/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 400

    def test_returns_404_for_nonexistent_payment(
        self, api_client, client_headers, project,
    ):
        """Returns 404 when payment_id does not exist."""
        url = f'/api/accounts/projects/{project.id}/payments/99999/widget-data/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# payment_verify_transaction_view
# ===========================================================================

class TestPaymentVerifyTransactionView:
    """Covers payment verify transaction view behavior."""

    def test_returns_400_when_transaction_id_missing(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Returns 400 when transaction_id is not provided in body."""
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
        resp = api_client.post(url, {}, format='json', **client_headers)

        assert resp.status_code == 400

    def test_returns_404_for_nonexistent_payment(
        self, api_client, client_headers, project,
    ):
        """Returns 404 when payment_id does not exist."""
        url = f'/api/accounts/projects/{project.id}/payments/99999/verify/'
        resp = api_client.post(url, {'transaction_id': 'txn_x'}, format='json', **client_headers)

        assert resp.status_code == 404

    def test_returns_502_when_wompi_verify_raises(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Returns 502 when the Wompi verify call raises an exception."""
        with patch('accounts.services.wompi.verify_transaction', side_effect=Exception('timeout')):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
            resp = api_client.post(url, {'transaction_id': 'txn_x'}, format='json', **client_headers)

        assert resp.status_code == 502

    @patch('accounts.services.wompi.verify_transaction')
    def test_approved_transaction_marks_payment_paid(
        self, mock_verify, api_client, client_headers, project, pending_payment,
    ):
        """APPROVED transaction marks payment as paid."""
        mock_verify.return_value = _binding_transaction(
            pending_payment, 'txn_ok', 'APPROVED',
        )
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
        resp = api_client.post(url, {'transaction_id': 'txn_ok'}, format='json', **client_headers)

        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    @patch('accounts.services.wompi.verify_transaction')
    def test_declined_transaction_marks_payment_failed(
        self, mock_verify, api_client, client_headers, project, pending_payment,
    ):
        """DECLINED transaction marks payment as failed."""
        mock_verify.return_value = _binding_transaction(
            pending_payment, 'txn_no', 'DECLINED',
        )
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
        resp = api_client.post(url, {'transaction_id': 'txn_no'}, format='json', **client_headers)

        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_FAILED

    @patch('accounts.services.wompi.verify_transaction')
    def test_pending_transaction_saves_id_without_status_change(
        self, mock_verify, api_client, client_headers, project, pending_payment,
    ):
        """Other transaction status saves wompi_transaction_id but keeps payment status."""
        mock_verify.return_value = _binding_transaction(
            pending_payment, 'txn_wait', 'PENDING',
        )
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
        resp = api_client.post(url, {'transaction_id': 'txn_wait'}, format='json', **client_headers)

        assert resp.status_code == 200
        assert resp.json()['transaction_status'] == 'PENDING'
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING  # unchanged

    def test_binding_mismatch_leaves_manual_verification_payment_unchanged(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Fails if a mismatched canonical response writes during manual verification."""
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
        with patch(
            'accounts.services.wompi.verify_transaction',
            return_value=_binding_transaction(
                pending_payment, 'txn-bound', 'APPROVED', amount_in_cents=1,
            ),
        ):
            response = api_client.post(
                url, {'transaction_id': 'txn-bound'}, format='json', **client_headers,
            )

        assert response.status_code == 400
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert pending_payment.paid_at is None
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history


# ===========================================================================
# wompi_webhook_view — additional reference lookup paths
# ===========================================================================

class TestWompiWebhookAdditionalPaths:
    """Covers wompi webhook additional paths behavior."""

    def test_missing_transaction_id_returns_400(self, api_client, subscription):
        """Missing transaction_id in webhook payload returns 400."""
        resp = api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': '',
                'status': 'APPROVED',
                'reference': 'some_ref',
            }),
            format='json',
        )

        assert resp.status_code == 400

    def test_missing_reference_returns_400(self, api_client, subscription):
        """Missing reference in webhook payload returns 400."""
        resp = api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': 'txn_123',
                'status': 'APPROVED',
                'reference': '',
            }),
            format='json',
        )

        assert resp.status_code == 400

    def test_pa_pattern_reference_finds_payment(
        self, api_client, subscription, pending_payment,
    ):
        """Webhook with PA{id}P{proj}T{ts} reference finds payment via regex."""
        reference = f'PA{pending_payment.id}P{subscription.project.id}T1234567890'
        with patch(
            'accounts.services.wompi.verify_transaction',
            return_value=_binding_transaction(
                pending_payment, 'txn_pa_test', 'DECLINED', reference=reference,
            ),
        ):
            resp = api_client.post(
                '/api/accounts/webhooks/wompi/',
                signed_transaction_event({
                    'id': 'txn_pa_test', 'status': 'DECLINED', 'reference': reference,
                }),
                format='json',
            )

        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_FAILED

    def test_other_transaction_status_saves_txn_id(
        self, api_client, subscription, pending_payment,
    ):
        """Webhook with unknown status (e.g. PROCESSING) saves transaction_id only."""
        pending_payment.wompi_payment_link_id = 'link_other_status'
        pending_payment.save(update_fields=['wompi_payment_link_id'])

        with patch(
            'accounts.services.wompi.verify_transaction',
            return_value=_binding_transaction(
                pending_payment,
                'txn_processing',
                'PROCESSING',
                reference='provider-reference',
                payment_link_id='link_other_status',
            ),
        ):
            resp = api_client.post(
                '/api/accounts/webhooks/wompi/',
                signed_transaction_event({
                    'id': 'txn_processing', 'status': 'PROCESSING',
                    'reference': 'link_other_status',
                }),
                format='json',
            )

        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.wompi_transaction_id == 'txn_processing'
        assert pending_payment.status == Payment.STATUS_PENDING  # unchanged

    def test_binding_mismatch_leaves_webhook_payment_unchanged(
        self, api_client, pending_payment,
    ):
        """Fails if a signed event can write before canonical binding rejects it."""
        pending_payment.wompi_payment_link_id = 'link-local-payment'
        pending_payment.save(update_fields=['wompi_payment_link_id'])
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        canonical_transaction = _binding_transaction(
            pending_payment,
            'txn-webhook-bound',
            'APPROVED',
            reference='provider-reference',
            payment_link_id='link-local-payment',
            amount_in_cents=1,
        )
        event = signed_transaction_event({
            'id': 'txn-webhook-bound', 'status': 'APPROVED',
            'amount_in_cents': int(pending_payment.amount * 100),
        })
        with patch(
            'accounts.services.wompi.verify_transaction',
            return_value=canonical_transaction,
        ) as mock_verify:
            response = api_client.post('/api/accounts/webhooks/wompi/', event, format='json')

        assert response.status_code == 400
        mock_verify.assert_called_once_with('txn-webhook-bound')
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert pending_payment.paid_at is None
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history
