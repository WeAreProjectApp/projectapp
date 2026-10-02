"""Tests for the stored-card subscription flow (Wompi payment sources + 3DS).

Covers:
- wompi service: get_acceptance_tokens, create_payment_source, charge_with_payment_source
- card_setup_start_view / card_setup_status_view / card_setup_confirm_view
- payment_charge_stored_view
- auto_charge_due_subscriptions Huey task (charge, retry, suspension)
"""
from datetime import date, timedelta
from decimal import Decimal
from functools import partial
from unittest.mock import MagicMock, patch

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
from accounts.tasks import auto_charge_due_subscriptions

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """Provide an API client for endpoint requests."""
    return APIClient()


@pytest.fixture
def client_user():
    """Provide an authenticated client user."""
    user = User.objects.create_user(
        username='client@card.com', email='client@card.com', password='clientpass1',
        first_name='Carlos', last_name='Ruiz',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    """Provide bearer headers for the client."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@card.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    """Provide an active project owned by the client."""
    return Project.objects.create(
        name='Card Project', client=client_user, status=Project.STATUS_ACTIVE,
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
        subscription=subscription, amount=subscription.billing_amount,
        description='Hosting', billing_period_start='2026-02-01',
        billing_period_end='2026-02-28', due_date='2020-02-01',
        status=Payment.STATUS_PENDING,
    )


VALID_CARD = {
    'card_number': '4242424242424242', 'exp_month': '12', 'exp_year': '30',
    'cvc': '123', 'card_holder': 'Carlos Ruiz',
}


def _stored_card_transaction(
    payment, payment_source_id, reference, integrity_signature, *,
    transaction_id, transaction_status, status_message='',
):
    return {
        'id': transaction_id,
        'status': transaction_status,
        'status_message': status_message,
        'amount_in_cents': int(payment.amount * 100),
        'currency': 'COP',
        'reference': reference,
    }


def _poll_response_with_other_transaction_id(payment):
    return {
        'id': 'txn-poll-other',
        'status': 'APPROVED',
        'amount_in_cents': int(payment.amount * 100),
        'currency': 'COP',
        'reference': f'PA{payment.id}P{payment.subscription.project_id}T1700000000',
    }


def _poll_response_with_other_generated_reference(payment):
    return {
        'id': 'txn-poll-valid',
        'status': 'APPROVED',
        'amount_in_cents': int(payment.amount * 100),
        'currency': 'COP',
        'reference': f'PA{payment.id}P{payment.subscription.project_id}T1700000001',
    }


def _available_card_source():
    return {
        'id': 3891,
        'status': 'AVAILABLE',
        'customer_email': 'client@card.com',
        'public_data': {
            'brand': 'VISA', 'last_four': '4242',
            'exp_month': '12', 'exp_year': '30',
        },
    }


def _foreign_initial_charge_transaction(payment):
    return {
        'id': 'txn-foreign-initial-charge',
        'status': 'APPROVED',
        'amount_in_cents': int(payment.amount * 100),
        'currency': 'COP',
        'reference': (
            f'PA{payment.id + 1}P{payment.subscription.project_id}T1700000000'
        ),
    }


# ===========================================================================
# wompi service
# ===========================================================================

class TestWompiService:
    """Covers wompi service behavior."""

    @override_settings(WOMPI_API_URL='https://sb.wompi.co/v1', WOMPI_PUBLIC_KEY='pub')
    @patch('accounts.services.wompi.requests.get')
    def test_get_acceptance_tokens_returns_both(self, mock_get):
        """Verifies get acceptance tokens returns both."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={'data': {
                'presigned_acceptance': {'acceptance_token': 'ACC'},
                'presigned_personal_data_auth': {'acceptance_token': 'PERS'},
            }}),
        )
        from accounts.services.wompi import get_acceptance_tokens
        tokens = get_acceptance_tokens()
        assert tokens == {'acceptance_token': 'ACC', 'accept_personal_auth': 'PERS'}

    @override_settings(WOMPI_API_URL='https://sb.wompi.co/v1', WOMPI_PRIVATE_KEY='priv')
    @patch('accounts.services.wompi.requests.post')
    def test_create_payment_source_sends_card_token(self, mock_post):
        """Verifies create payment source sends card token."""
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={'data': {'id': 3891, 'status': 'AVAILABLE'}}),
        )
        from accounts.services.wompi import create_payment_source
        data = create_payment_source('tok_x', 'a@b.com', 'acc', 'auth')
        assert data['id'] == 3891
        payload = mock_post.call_args.kwargs['json']
        assert payload['type'] == 'CARD'
        assert payload['token'] == 'tok_x'
        assert payload['accept_personal_auth'] == 'auth'

    @override_settings(WOMPI_API_URL='https://sb.wompi.co/v1', WOMPI_PRIVATE_KEY='priv')
    @patch('accounts.services.wompi.requests.post')
    def test_charge_with_payment_source_is_recurrent(self, mock_post):
        """Verifies charge with payment source is recurrent."""
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={'data': {'id': 'txn1', 'status': 'APPROVED'}}),
        )
        from accounts.services.wompi import charge_with_payment_source
        payment = MagicMock(id=1, amount=Decimal('100000'))
        payment.subscription.project.client.email = 'a@b.com'
        charge_with_payment_source(payment, '3891', 'REF1', 'sig')
        payload = mock_post.call_args.kwargs['json']
        assert payload['recurrent'] is True
        assert payload['payment_source_id'] == 3891
        assert payload['amount_in_cents'] == 10000000


# ===========================================================================
# card_setup_start_view
# ===========================================================================

class TestCardSetupStart:
    """Covers card setup start behavior."""

    def _url(self, project):
        return f'/api/accounts/projects/{project.id}/subscription/card/'

    def test_missing_card_fields_returns_400(self, api_client, client_headers, project, subscription):
        """Verifies missing card fields returns 400."""
        resp = api_client.post(self._url(project), {'card_number': '4242'}, **client_headers)
        assert resp.status_code == 400

    def test_no_subscription_returns_400(self, api_client, client_headers, project):
        """Verifies no subscription returns 400."""
        resp = api_client.post(self._url(project), VALID_CARD, **client_headers)
        assert resp.status_code == 400

    def test_creates_payment_source_non_3ds(self, api_client, client_headers, project, subscription):
        """Verifies creates payment source non 3ds."""
        with patch('accounts.services.wompi.tokenize_card',
                   return_value={'id': 'tok_x', 'brand': 'VISA', 'last_four': '4242'}), \
             patch('accounts.services.wompi.get_acceptance_tokens',
                   return_value={'acceptance_token': 'a', 'accept_personal_auth': 'b'}), \
             patch('accounts.services.wompi.create_payment_source',
                   return_value={'id': 3891, 'status': 'AVAILABLE', 'extra': {}}):
            resp = api_client.post(self._url(project), VALID_CARD, **client_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['payment_source_id'] == 3891
        assert body['status'] == 'AVAILABLE'
        assert body['is_three_ds'] is False
        assert body['card_last_four'] == '4242'


# ===========================================================================
# card_setup_status_view
# ===========================================================================

class TestCardSetupStatus:
    """Covers card setup status behavior."""

    def test_returns_three_ds_state(self, api_client, client_headers, project, subscription):
        """Verifies returns three ds state."""
        url = f'/api/accounts/projects/{project.id}/subscription/card/3891/status/'
        with patch('accounts.services.wompi.get_payment_source',
                   return_value={'id': 3891, 'status': 'PENDING',
                                 'customer_email': 'client@card.com',
                                 'extra': {'is_three_ds': True,
                                           'three_ds_auth': {'current_step': 'CHALLENGE'}}}):
            resp = api_client.get(url, **client_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['is_three_ds'] is True
        assert body['three_ds_auth']['current_step'] == 'CHALLENGE'


# ===========================================================================
# card_setup_confirm_view
# ===========================================================================

class TestCardSetupConfirm:
    """Covers card setup confirm behavior."""

    def _url(self, project, ps_id=3891):
        return f'/api/accounts/projects/{project.id}/subscription/card/{ps_id}/confirm/'

    def test_rejects_when_source_not_available(self, api_client, client_headers, project, subscription):
        """Verifies rejects when source not available."""
        with patch('accounts.services.wompi.get_payment_source',
                   return_value={'id': 3891, 'status': 'DECLINED',
                                 'customer_email': 'client@card.com'}):
            resp = api_client.post(self._url(project), {}, **client_headers)
        assert resp.status_code == 400

    def test_rejects_foreign_payment_source(self, api_client, client_headers, project, subscription):
        """A payment source created for a different customer_email is rejected."""
        with patch('accounts.services.wompi.get_payment_source',
                   return_value={'id': 3891, 'status': 'AVAILABLE',
                                 'customer_email': 'attacker@evil.com', 'public_data': {}}):
            resp = api_client.post(self._url(project), {}, **client_headers)
        assert resp.status_code == 400
        subscription.refresh_from_db()
        assert subscription.wompi_payment_source_id == ''

    def test_persists_card_and_charges_first_payment(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """Verifies persists card and charges first payment."""
        with patch('accounts.services.wompi.get_payment_source',
                   return_value={'id': 3891, 'status': 'AVAILABLE',
                                 'customer_email': 'client@card.com',
                                 'public_data': {'last_four': '4242', 'exp_month': '12', 'exp_year': '30'}}), \
             patch('accounts.services.wompi.charge_with_payment_source',
                   side_effect=partial(
                       _stored_card_transaction, transaction_id='txn1',
                       transaction_status='APPROVED',
                   )):
            resp = api_client.post(self._url(project), {'card_brand': 'VISA'}, **client_headers)
        assert resp.status_code == 200
        subscription.refresh_from_db()
        pending_payment.refresh_from_db()
        assert subscription.wompi_payment_source_id == '3891'
        assert subscription.card_last_four == '4242'
        assert pending_payment.status == Payment.STATUS_PAID

    def test_persists_verified_card_metadata_after_rejected_first_charge(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """Fails if a rejected first charge rolls back valid stored-card metadata."""
        with patch(
            'accounts.services.wompi.get_payment_source',
            return_value=_available_card_source(),
        ), \
             patch(
                 'accounts.services.wompi.charge_with_payment_source',
                 return_value=_foreign_initial_charge_transaction(pending_payment),
             ):
            response = api_client.post(self._url(project), {}, **client_headers)

        assert response.status_code == 200
        subscription.refresh_from_db()
        assert subscription.wompi_payment_source_id == '3891'
        assert subscription.card_brand == 'VISA'
        assert subscription.card_last_four == '4242'
        assert subscription.card_exp_month == '12'
        assert subscription.card_exp_year == '30'

    def test_returns_charge_error_after_rejected_first_charge(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """Fails if a rejected first charge reports success or writes payment history."""
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        with patch(
            'accounts.services.wompi.get_payment_source',
            return_value=_available_card_source(),
        ), \
             patch(
                 'accounts.services.wompi.charge_with_payment_source',
                 return_value=_foreign_initial_charge_transaction(pending_payment),
             ):
            response = api_client.post(self._url(project), {}, **client_headers)

        assert response.status_code == 200
        assert response.json()['charge'] == {
            'payment_id': pending_payment.id,
            'error': 'La transacción no corresponde a este pago.',
        }
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history

    def test_confirms_card_without_open_payment(
        self, api_client, client_headers, project, subscription,
    ):
        """Verifies confirms card without open payment."""
        with patch('accounts.services.wompi.get_payment_source',
                   return_value={'id': 3891, 'status': 'AVAILABLE',
                                 'customer_email': 'client@card.com', 'public_data': {}}):
            resp = api_client.post(self._url(project), {'card_last_four': '1111'}, **client_headers)
        assert resp.status_code == 200
        subscription.refresh_from_db()
        assert subscription.wompi_payment_source_id == '3891'
        assert resp.json()['charge'] is None


# ===========================================================================
# payment_charge_stored_view
# ===========================================================================

class TestPaymentChargeStored:
    """Covers payment charge stored behavior."""

    def _url(self, project, payment):
        return f'/api/accounts/projects/{project.id}/payments/{payment.id}/charge/'

    def test_rejects_when_no_stored_card(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """Verifies rejects when no stored card."""
        resp = api_client.post(self._url(project, pending_payment), {}, **client_headers)
        assert resp.status_code == 400

    def test_charges_with_stored_card(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """Verifies charges with stored card."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        with patch('accounts.services.wompi.charge_with_payment_source',
                   side_effect=partial(
                       _stored_card_transaction, transaction_id='txn9',
                       transaction_status='APPROVED',
                   )):
            resp = api_client.post(self._url(project, pending_payment), {}, **client_headers)
        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    def test_binding_failure_leaves_stored_card_payment_pending(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """Fails if a rejected stored-card transaction writes payment state before 502."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        invalid_transaction = {
            'id': 'txn-foreign-stored',
            'status': 'APPROVED',
            'amount_in_cents': int(pending_payment.amount * 100),
            'currency': 'COP',
            'reference': f'PA{pending_payment.id + 1}P{project.id}T1700000000',
        }
        with patch(
            'accounts.services.wompi.charge_with_payment_source',
            return_value=invalid_transaction,
        ):
            response = api_client.post(self._url(project, pending_payment), {}, **client_headers)

        assert response.status_code == 502
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history

    def test_pending_charge_resolves_via_polling(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """A PENDING card charge resolves to PAID once polling sees APPROVED."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        with patch('accounts.services.wompi.charge_with_payment_source',
                   side_effect=partial(
                       _stored_card_transaction, transaction_id='txnP',
                       transaction_status='PENDING',
                   )), \
             patch('accounts.services.wompi.verify_transaction',
                   return_value={
                       'id': 'txnP', 'status': 'APPROVED',
                       'amount_in_cents': int(pending_payment.amount * 100),
                       'currency': 'COP',
                       'reference': f'PA{pending_payment.id}P{project.id}T1700000000',
                   }), \
             patch('time.time', return_value=1700000000), \
             patch('time.sleep'):
            resp = api_client.post(self._url(project, pending_payment), {}, **client_headers)
        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    @pytest.mark.parametrize(
        'poll_response_factory',
        [
            _poll_response_with_other_transaction_id,
            _poll_response_with_other_generated_reference,
        ],
        ids=['other-transaction-id', 'other-generated-reference'],
    )
    def test_invalid_poll_result_leaves_pending_charge_unchanged(
        self, api_client, client_headers, project, subscription, pending_payment,
        poll_response_factory,
    ):
        """Fails if a mismatched poll response writes a stored-card payment."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        poll_response = poll_response_factory(pending_payment)
        with patch(
            'accounts.services.wompi.charge_with_payment_source',
            side_effect=partial(
                _stored_card_transaction, transaction_id='txn-poll-valid',
                transaction_status='PENDING',
            ),
        ), patch(
            'accounts.services.wompi.verify_transaction',
            return_value=poll_response,
        ) as mock_verify, patch(
            'time.time', return_value=1700000000,
        ), patch('time.sleep'):
            response = api_client.post(self._url(project, pending_payment), {}, **client_headers)

        assert response.status_code == 502
        mock_verify.assert_called_once_with('txn-poll-valid')
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history


# ===========================================================================
# auto_charge_due_subscriptions Huey task
# ===========================================================================

class TestAutoChargeTask:
    """Covers auto charge task behavior."""

    def test_charges_due_payment_with_stored_card(self, subscription, pending_payment):
        """Verifies charges due payment with stored card."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        with patch('accounts.services.wompi.charge_with_payment_source',
                   side_effect=partial(
                       _stored_card_transaction, transaction_id='txn1',
                       transaction_status='APPROVED',
                   )):
            result = auto_charge_due_subscriptions.call_local()
        assert result['charged'] == 1
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    def test_binding_failure_does_not_consume_automatic_charge_attempt(
        self, subscription, pending_payment,
    ):
        """Fails if a binding rejection consumes a retry or changes automatic billing state."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        invalid_transaction = {
            'id': 'txn-auto-foreign',
            'status': 'APPROVED',
            'amount_in_cents': int(pending_payment.amount * 100),
            'currency': 'COP',
            'reference': f'PA{pending_payment.id + 1}P{subscription.project_id}T1700000000',
        }
        with patch(
            'accounts.services.wompi.charge_with_payment_source',
            return_value=invalid_transaction,
        ):
            result = auto_charge_due_subscriptions.call_local()

        assert result == {'charged': 0, 'failed': 0}
        pending_payment.refresh_from_db()
        assert pending_payment.charge_attempts == 0
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.wompi_transaction_id == ''
        assert pending_payment.next_retry_at is None
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history

    def test_skips_subscription_without_stored_card(self, subscription, pending_payment):
        """Verifies skips subscription without stored card."""
        with patch('accounts.services.wompi.charge_with_payment_source') as mock_charge:
            result = auto_charge_due_subscriptions.call_local()
        mock_charge.assert_not_called()
        assert result['charged'] == 0

    def test_legacy_unclassified_project_is_not_auto_charged(
        self, project, subscription, pending_payment,
    ):
        """Verifies legacy unclassified project is not auto charged."""
        Project.objects.filter(pk=project.pk).update(
            status=Project.STATUS_ARCHIVED,
            current_state=None,
            state_review_required=True,
        )
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])

        with patch('accounts.services.wompi.charge_with_payment_source') as mock_charge:
            result = auto_charge_due_subscriptions.call_local()

        mock_charge.assert_not_called()
        pending_payment.refresh_from_db()
        assert result == {'charged': 0, 'failed': 0}
        assert pending_payment.status == Payment.STATUS_PENDING
        assert pending_payment.charge_attempts == 0

    def test_suspends_subscription_after_attempt_limit(self, subscription, pending_payment):
        """Verifies suspends subscription after attempt limit."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        pending_payment.charge_attempts = 2
        pending_payment.save(update_fields=['charge_attempts'])
        with patch('accounts.services.wompi.charge_with_payment_source',
                   side_effect=partial(
                       _stored_card_transaction, transaction_id='txn1',
                       transaction_status='DECLINED', status_message='Fondos insuficientes',
                   )):
            result = auto_charge_due_subscriptions.call_local()
        assert result['failed'] == 1
        subscription.refresh_from_db()
        pending_payment.refresh_from_db()
        assert subscription.status == HostingSubscription.STATUS_SUSPENDED
        assert pending_payment.status == Payment.STATUS_FAILED
        assert pending_payment.charge_attempts == 3

    def test_reschedules_retry_before_limit(self, subscription, pending_payment):
        """Verifies reschedules retry before limit."""
        subscription.wompi_payment_source_id = '3891'
        subscription.save(update_fields=['wompi_payment_source_id'])
        with patch('accounts.services.wompi.charge_with_payment_source',
                   side_effect=partial(
                       _stored_card_transaction, transaction_id='txn1',
                       transaction_status='DECLINED',
                   )):
            auto_charge_due_subscriptions.call_local()
        subscription.refresh_from_db()
        pending_payment.refresh_from_db()
        assert subscription.status == HostingSubscription.STATUS_ACTIVE
        assert pending_payment.charge_attempts == 1
        assert pending_payment.next_retry_at == date.today() + timedelta(days=2)


# ===========================================================================
# Re-verifying PROCESSING payments (async settlement / missed webhook)
# ===========================================================================

class TestPaymentReverify:
    """Covers payment reverify behavior."""

    def test_verify_uses_stored_transaction_id(
        self, api_client, client_headers, project, subscription, pending_payment,
    ):
        """A PROCESSING payment can be re-verified without re-supplying the txn id."""
        pending_payment.status = Payment.STATUS_PROCESSING
        pending_payment.wompi_transaction_id = 'txnStored'
        pending_payment.save(update_fields=['status', 'wompi_transaction_id'])

        url = f'/api/accounts/projects/{project.id}/payments/{pending_payment.id}/verify/'
        with patch('accounts.services.wompi.verify_transaction',
                   return_value={
                       'id': 'txnStored', 'status': 'APPROVED',
                       'amount_in_cents': int(pending_payment.amount * 100),
                       'currency': 'COP',
                       'reference': f'PA{pending_payment.id}P{project.id}T1700000000',
                   }):
            resp = api_client.post(url, {}, **client_headers)

        assert resp.status_code == 200
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    def test_cron_reverifies_stuck_processing_payment(self, subscription, pending_payment):
        """The billing cron resolves a PROCESSING payment via direct verification."""
        from accounts.tasks import _reverify_processing_payments

        pending_payment.status = Payment.STATUS_PROCESSING
        pending_payment.wompi_transaction_id = 'txnStuck'
        pending_payment.save(update_fields=['status', 'wompi_transaction_id'])

        with patch('accounts.services.wompi.verify_transaction',
                   return_value={
                       'id': 'txnStuck', 'status': 'APPROVED',
                       'amount_in_cents': int(pending_payment.amount * 100),
                       'currency': 'COP',
                       'reference': f'PA{pending_payment.id}P{subscription.project_id}T1700000000',
                   }):
            resolved = _reverify_processing_payments()

        assert resolved == 1
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID

    def test_binding_failure_leaves_processing_payment_unchanged(self, subscription, pending_payment):
        """Fails if re-verification changes a processing payment after binding rejects it."""
        from accounts.tasks import _reverify_processing_payments

        pending_payment.status = Payment.STATUS_PROCESSING
        pending_payment.wompi_transaction_id = 'txn-reverify-foreign'
        pending_payment.save(update_fields=['status', 'wompi_transaction_id'])
        before_history = PaymentHistory.objects.filter(payment=pending_payment).count()
        invalid_transaction = {
            'id': 'txn-reverify-foreign',
            'status': 'APPROVED',
            'amount_in_cents': int(pending_payment.amount * 100),
            'currency': 'COP',
            'reference': f'PA{pending_payment.id + 1}P{subscription.project_id}T1700000000',
        }
        with patch(
            'accounts.services.wompi.verify_transaction',
            return_value=invalid_transaction,
        ):
            resolved = _reverify_processing_payments()

        assert resolved == 0
        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PROCESSING
        assert pending_payment.wompi_transaction_id == 'txn-reverify-foreign'
        assert pending_payment.charge_attempts == 0
        assert pending_payment.next_retry_at is None
        assert PaymentHistory.objects.filter(payment=pending_payment).count() == before_history
