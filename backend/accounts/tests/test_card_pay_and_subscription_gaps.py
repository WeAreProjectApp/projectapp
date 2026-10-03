"""Tests for uncovered branches in payment_card_pay_view and project_subscription_view.

Covers:
- payment_card_pay_view: missing fields, not found, not payable, APPROVED, PENDING,
  DECLINED/ERROR/VOIDED, 502 error
- project_subscription_view PATCH: admin archives/unarchives, client forbidden to archive,
  admin changes status
- project_subscription_view GET: archived subscription hidden from client
- payment_generate_link_view: 404 (payment not found), 502 (service exception)
"""
from decimal import Decimal
from functools import partial
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

User = get_user_model()

pytestmark = pytest.mark.django_db


def _card_transaction(
    payment, card_token, acceptance_token, reference, integrity_signature, *,
    transaction_id, transaction_status,
):
    return {
        'id': transaction_id,
        'status': transaction_status,
        'amount_in_cents': int(payment.amount * 100),
        'currency': 'COP',
        'reference': reference,
    }


@pytest.fixture
def api_client():
    """Provide an API client for endpoint requests."""
    return APIClient()


@pytest.fixture
def admin_user():
    """Provide an authenticated administrator user."""
    user = User.objects.create_user(
        username='admin@cardpay.com', email='admin@cardpay.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    """Provide bearer headers for the administrator."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@cardpay.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    """Provide an authenticated client user."""
    user = User.objects.create_user(
        username='client@cardpay.com', email='client@cardpay.com', password='clientpass1',
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
        'email': 'client@cardpay.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    """Provide an active project owned by the client."""
    return Project.objects.create(
        name='CardPay Project', client=client_user,
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


VALID_CARD_PAYLOAD = {
    'card_number': '4111111111111111',
    'exp_month': '12',
    'exp_year': '2030',
    'cvc': '123',
    'card_holder': 'Carlos Ruiz',
}


# ===========================================================================
# payment_card_pay_view
# ===========================================================================

class TestPaymentCardPayView:
    """Covers payment card pay view behavior."""

    def test_returns_404_when_payment_not_found(
        self, api_client, client_headers, project,
    ):
        """Returns 404 when payment_id does not exist for the project."""
        url = f'/api/accounts/projects/{project.id}/payments/99999/card-pay/'
        resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 404

    def test_returns_400_when_payment_is_paid(
        self, api_client, client_headers, project, paid_payment,
    ):
        """Returns 400 when payment is already paid (not in payable statuses)."""
        url = f'/api/accounts/projects/{project.id}/payments/{paid_payment.id}/card-pay/'
        resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 400

    def test_returns_400_when_card_fields_missing(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Returns 400 when required card fields are missing."""
        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
        resp = api_client.post(
            url,
            {'card_number': '4111111111111111'},  # missing exp_month, exp_year, cvc, card_holder
            format='json',
            **client_headers,
        )

        assert resp.status_code == 400

    @override_settings(WOMPI_INTEGRITY_SECRET='test_secret')
    def test_approved_card_payment_marks_payment_paid(
        self, api_client, client_headers, project, pending_payment,
    ):
        """APPROVED card transaction marks payment as paid."""
        with patch('accounts.services.wompi.tokenize_card', return_value={'id': 'tok_test', 'brand': 'VISA', 'last_four': '4242'}), \
             patch('accounts.services.wompi.get_acceptance_token', return_value='acc_tok'), \
             patch('accounts.services.wompi.create_card_transaction',
                   side_effect=partial(
                       _card_transaction, transaction_id='txn_card_ok',
                       transaction_status='APPROVED',
                   )):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
            resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['transaction_status'] == 'APPROVED'
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    @override_settings(WOMPI_INTEGRITY_SECRET='test_secret')
    def test_pending_card_transaction_sets_processing_status(
        self, api_client, client_headers, project, pending_payment,
    ):
        """PENDING transaction sets payment to PROCESSING status."""
        with patch('accounts.services.wompi.tokenize_card', return_value={'id': 'tok_test', 'brand': 'VISA', 'last_four': '4242'}), \
             patch('accounts.services.wompi.get_acceptance_token', return_value='acc_tok'), \
             patch('accounts.services.wompi.create_card_transaction',
                   side_effect=partial(
                       _card_transaction, transaction_id='txn_card_wait',
                       transaction_status='PENDING',
                   )):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
            resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 200
        assert resp.json()['transaction_status'] == 'PENDING'
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PROCESSING

    @override_settings(WOMPI_INTEGRITY_SECRET='test_secret')
    def test_declined_card_transaction_marks_payment_failed(
        self, api_client, client_headers, project, pending_payment,
    ):
        """DECLINED transaction marks payment as failed."""
        with patch('accounts.services.wompi.tokenize_card', return_value={'id': 'tok_test', 'brand': 'VISA', 'last_four': '4242'}), \
             patch('accounts.services.wompi.get_acceptance_token', return_value='acc_tok'), \
             patch('accounts.services.wompi.create_card_transaction',
                   side_effect=partial(
                       _card_transaction, transaction_id='txn_card_no',
                       transaction_status='DECLINED',
                   )):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
            resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 200
        assert resp.json()['transaction_status'] == 'DECLINED'
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_FAILED

    @override_settings(WOMPI_INTEGRITY_SECRET='test_secret')
    def test_error_status_card_transaction_marks_payment_failed(
        self, api_client, client_headers, project, pending_payment,
    ):
        """ERROR transaction status marks payment as failed."""
        with patch('accounts.services.wompi.tokenize_card', return_value={'id': 'tok_test', 'brand': 'VISA', 'last_four': '4242'}), \
             patch('accounts.services.wompi.get_acceptance_token', return_value='acc_tok'), \
             patch('accounts.services.wompi.create_card_transaction',
                   side_effect=partial(
                       _card_transaction, transaction_id='txn_err',
                       transaction_status='ERROR',
                   )):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
            resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_FAILED

    def test_returns_502_when_tokenize_raises(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Returns 502 when wompi tokenize_card raises an exception."""
        with patch('accounts.services.wompi.tokenize_card',
                   side_effect=Exception('network error')):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
            resp = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert resp.status_code == 502
        assert 'Error' in resp.json()['detail']

    @override_settings(WOMPI_INTEGRITY_SECRET='test_secret')
    def test_binding_failure_leaves_card_payment_pending(
        self, api_client, client_headers, project, pending_payment,
    ):
        """Fails if a rejected card transaction writes status or history before returning 502."""
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        invalid_transaction = {
            'id': 'txn-foreign-card',
            'status': 'APPROVED',
            'amount_in_cents': int(pending_payment.amount * 100),
            'currency': 'COP',
            'reference': f'PA{pending_payment.id + 1}P{project.id}T1700000000',
        }
        with patch('accounts.services.wompi.tokenize_card', return_value={'id': 'tok_test'}), \
             patch('accounts.services.wompi.get_acceptance_token', return_value='acc_tok'), \
             patch(
                 'accounts.services.wompi.create_card_transaction',
                 return_value=invalid_transaction,
             ):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/card-pay/'
            response = api_client.post(url, VALID_CARD_PAYLOAD, format='json', **client_headers)

        assert response.status_code == 502
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history


# ===========================================================================
# payment_generate_link_view — missing 404 and 502 branches
# ===========================================================================

class TestPaymentGenerateLinkViewEdgeCases:
    """Covers payment generate link view edge cases behavior."""

    def test_returns_404_when_payment_not_found(
        self, api_client, admin_headers, project,
    ):
        """Returns 404 when payment_id does not exist."""
        url = f'/api/accounts/projects/{project.id}/payments/99999/generate-link/'
        resp = api_client.post(url, **admin_headers)

        assert resp.status_code == 404

    def test_returns_502_when_wompi_service_raises(
        self, api_client, admin_headers, project, pending_payment,
    ):
        """Returns 502 when the create_payment_link service throws an exception."""
        with patch('accounts.services.wompi.create_payment_link',
                   side_effect=Exception('Wompi API down')):
            url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/generate-link/'
            resp = api_client.post(url, **admin_headers)

        assert resp.status_code == 502
        assert 'Error' in resp.json()['detail']


# ===========================================================================
# project_subscription_view PATCH — is_archived and status branches
# ===========================================================================

class TestProjectSubscriptionPatchEdgeCases:
    """Covers project subscription patch edge cases behavior."""

    def test_admin_archives_subscription(
        self, api_client, admin_headers, project, subscription,
    ):
        """Admin can archive a subscription."""
        url = f'/api/accounts/projects/{project.id}/subscription/'
        resp = api_client.patch(
            url, {'is_archived': True}, format='json', **admin_headers,
        )

        assert resp.status_code == 200
        subscription.refresh_from_db()
        assert subscription.is_archived is True

    def test_admin_unarchives_subscription(
        self, api_client, admin_headers, project, subscription,
    ):
        """Admin can unarchive a previously archived subscription."""
        subscription.is_archived = True
        subscription.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/subscription/'
        resp = api_client.patch(
            url, {'is_archived': False}, format='json', **admin_headers,
        )

        assert resp.status_code == 200
        subscription.refresh_from_db()
        assert subscription.is_archived is False

    def test_client_cannot_archive_subscription(
        self, api_client, client_headers, project, subscription,
    ):
        """Client gets 403 when trying to archive a subscription."""
        url = f'/api/accounts/projects/{project.id}/subscription/'
        resp = api_client.patch(
            url, {'is_archived': True}, format='json', **client_headers,
        )

        assert resp.status_code == 403

    def test_admin_changes_subscription_status(
        self, api_client, admin_headers, project, subscription,
    ):
        """Admin can change subscription status to cancelled."""
        url = f'/api/accounts/projects/{project.id}/subscription/'
        resp = api_client.patch(
            url, {'status': HostingSubscription.STATUS_CANCELLED},
            format='json', **admin_headers,
        )

        assert resp.status_code == 200
        subscription.refresh_from_db()
        assert subscription.status == HostingSubscription.STATUS_CANCELLED


# ===========================================================================
# project_subscription_view GET — archived subscription hidden from client
# ===========================================================================

class TestProjectSubscriptionGetArchivedClient:
    """Covers project subscription get archived client behavior."""

    def test_archived_subscription_returns_404_to_client(
        self, api_client, client_headers, project, subscription,
    ):
        """Client gets 404 when accessing an archived subscription."""
        subscription.is_archived = True
        subscription.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/subscription/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404

    def test_archived_subscription_visible_to_admin(
        self, api_client, admin_headers, project, subscription,
    ):
        """Admin can still see an archived subscription."""
        subscription.is_archived = True
        subscription.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/subscription/'
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 200
