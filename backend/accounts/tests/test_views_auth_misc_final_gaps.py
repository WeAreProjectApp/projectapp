"""Tests for remaining uncovered branches in accounts/views.py — auth, profile, and misc helpers.

Covers:
- login_view: inactive user (line 105)
- resend_code_view: invalid token exception (lines 203-204)
- me_view PATCH: custom_cover_image upload (lines 278-279)
- client_list_view POST: duplicate email ValueError (lines 364-365)
- client_detail_view PATCH: is_active update (line 409)
- admin_detail_view: non-staff user rejected (line 504)
- _generate_next_payment: nil billing_start (line 2718)
- _handle_payment_approved: notification exception silenced (lines 2786-2787)
- payment_card_pay_view: invalid project_id (line 3106)
- payment_verify_transaction_view: invalid project_id (line 3195)
- wompi_webhook_view: PA-pattern matches but payment not found (lines 3293-3294)
- project_subscription_view: invalid project_id (line 2840)
- project_payments_view: invalid project_id (line 2970)
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Payment,
    Project,
    UserProfile,
)
from accounts.tests.wompi_event_helpers import signed_transaction_event

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """Provide an API client for endpoint requests."""
    return APIClient()


@pytest.fixture
def admin_user():
    """Provide an authenticated administrator user."""
    user = User.objects.create_user(
        username='admin@authgaps.com', email='admin@authgaps.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    """Provide bearer headers for the administrator."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@authgaps.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    """Provide an authenticated client user."""
    user = User.objects.create_user(
        username='client@authgaps.com', email='client@authgaps.com', password='clientpass1',
        first_name='Test', last_name='Client',
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
        'email': 'client@authgaps.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    """Provide an active project owned by the client."""
    return Project.objects.create(
        name='Auth Gaps Project', client=client_user,
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


# ===========================================================================
# login_view — inactive user (line 105)
# ===========================================================================

class TestLoginViewInactiveUser:
    """Covers login view inactive user behavior."""

    @patch('accounts.views.authenticate')
    def test_inactive_user_returns_403(self, mock_auth, api_client):
        """When authenticate returns an inactive user, login returns 403."""
        inactive = User(
            username='off@authgaps.com', email='off@authgaps.com', is_active=False,
        )
        mock_auth.return_value = inactive

        resp = api_client.post('/api/accounts/login/', {
            'email': 'off@authgaps.com', 'password': 'anypass',
        }, format='json')

        assert resp.status_code == 403


# ===========================================================================
# resend_code_view — invalid token exception (lines 203-204)
# ===========================================================================

class TestResendCodeViewInvalidToken:
    """Covers resend code view invalid token behavior."""

    def test_invalid_bearer_token_returns_401(self, api_client):
        """Malformed or expired JWT token in resend-code/ triggers exception → 401."""
        resp = api_client.post(
            '/api/accounts/resend-code/',
            HTTP_AUTHORIZATION='Bearer this.is.not.a.valid.jwt.token',
        )

        assert resp.status_code == 401


# ===========================================================================
# me_view PATCH — custom_cover_image upload (lines 278-279)
# ===========================================================================

class TestMeViewCustomCoverImage:
    """Covers me view custom cover image behavior."""

    def test_patch_custom_cover_image_updates_profile(self, api_client, client_headers):
        """PATCH /me/ with custom_cover_image file updates the profile field."""
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (1, 1), color='red').save(buf, format='JPEG')
        buf.seek(0)

        resp = api_client.patch(
            '/api/accounts/me/',
            data={'custom_cover_image': ContentFile(buf.read(), name='cover.jpg')},
            format='multipart',
            **client_headers,
        )

        assert resp.status_code == 200


# ===========================================================================
# client_list_view POST — duplicate email ValueError (lines 364-365)
# ===========================================================================

class TestClientListViewDuplicateEmail:
    """Covers client list view duplicate email behavior."""

    def test_duplicate_email_returns_400(self, api_client, admin_headers, client_user):
        """POST /clients/ with existing email raises ValueError → 400."""
        resp = api_client.post('/api/accounts/clients/', {
            'email': client_user.email,  # already exists
            'first_name': 'Dup',
            'last_name': 'Client',
        }, format='json', **admin_headers)

        assert resp.status_code == 400


# ===========================================================================
# client_detail_view PATCH — is_active update (line 409)
# ===========================================================================

class TestClientDetailViewIsActive:
    """Covers client detail view is active behavior."""

    def test_admin_can_deactivate_client(self, api_client, admin_headers, client_user):
        """PATCH /clients/{id}/ with is_active=false deactivates the user."""
        resp = api_client.patch(
            f'/api/accounts/clients/{client_user.id}/',
            {'is_active': False},
            format='json',
            **admin_headers,
        )

        assert resp.status_code == 200
        client_user.refresh_from_db()
        assert client_user.is_active is False


# ===========================================================================
# admin_detail_view — non-staff user rejected (line 504)
# ===========================================================================

class TestAdminDetailViewNonStaff:
    """Covers admin detail view non staff behavior."""

    def test_non_staff_admin_returns_403(self, api_client, admin_headers, admin_user):
        """Non-staff admin accessing admin_detail_view gets 403 (requires is_staff)."""
        resp = api_client.get(
            f'/api/accounts/admins/{admin_user.id}/',
            **admin_headers,
        )

        assert resp.status_code == 403


# ===========================================================================
# _generate_next_payment — nil billing_start (line 2718)
# ===========================================================================

class TestGenerateNextPaymentNilStart:
    """Covers generate next payment nil start behavior."""

    def test_returns_none_when_next_billing_date_is_none(self, subscription):
        """_generate_next_payment returns None immediately when next_billing_date is None."""
        from accounts.views import _generate_next_payment

        # Set next_billing_date to None in memory without DB save (avoids NOT NULL constraint)
        subscription.next_billing_date = None

        result = _generate_next_payment(subscription)

        assert result is None


# ===========================================================================
# _handle_payment_approved — notification exception silenced (lines 2786-2787)
# ===========================================================================

class TestHandlePaymentApprovedNotificationException:
    """Covers handle payment approved notification exception behavior."""

    @patch('accounts.services.notifications.notify', side_effect=Exception('notify fail'))
    def test_notification_exception_is_silenced(self, mock_notify, project, subscription, pending_payment):
        """Exception in the notification block is caught and logged — payment is still updated."""
        from accounts.views import _handle_payment_approved

        # Refresh to get proper date objects (string dates from create() cause TypeError in date arithmetic)
        pending_payment.refresh_from_db()

        _handle_payment_approved(pending_payment, 'test')

        pending_payment.refresh_from_db()
        assert pending_payment.status == Payment.STATUS_PAID


# ===========================================================================
# payment_card_pay_view — invalid project_id returns 404 (line 3106)
# ===========================================================================

class TestPaymentCardPayInvalidProject:
    """Covers payment card pay invalid project behavior."""

    def test_invalid_project_returns_404(self, api_client, client_headers):
        """payment_card_pay_view returns 404 when project_id does not exist."""
        url = '/api/accounts/projects/99999/payments/1/card-pay/'
        resp = api_client.post(url, {}, format='json', **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# payment_verify_transaction_view — invalid project_id returns 404 (line 3195)
# ===========================================================================

class TestPaymentVerifyInvalidProject:
    """Covers payment verify invalid project behavior."""

    def test_invalid_project_returns_404(self, api_client, client_headers):
        """payment_verify_transaction_view returns 404 when project_id does not exist."""
        url = '/api/accounts/projects/99999/payments/1/verify/'
        resp = api_client.post(url, {'transaction_id': 'x'}, format='json', **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# wompi_webhook_view — PA-pattern matches but payment not found (lines 3293-3294)
# ===========================================================================

class TestWompiWebhookPaPatternNotFound:
    """Covers wompi webhook pa pattern not found behavior."""

    def test_pa_pattern_with_nonexistent_payment_id_not_found(self, api_client):
        """PA-pattern reference with non-existent payment ID falls through to 404."""
        reference = 'PA99999P1T1234567890'
        canonical_transaction = {
            'id': 'txn_pa_miss', 'status': 'APPROVED',
            'amount_in_cents': 100,
            'currency': 'COP',
            'reference': reference,
        }
        with patch(
            'accounts.services.wompi.verify_transaction',
            return_value=canonical_transaction,
        ):
            resp = api_client.post(
                '/api/accounts/webhooks/wompi/',
                signed_transaction_event({'id': 'txn_pa_miss', 'status': 'APPROVED'}),
                format='json',
            )

        assert resp.status_code == 404


# ===========================================================================
# project_subscription_view — invalid project_id (line 2840)
# ===========================================================================

class TestProjectSubscriptionInvalidProject:
    """Covers project subscription invalid project behavior."""

    def test_invalid_project_returns_404(self, api_client, client_headers):
        """project_subscription_view returns 404 when project_id does not exist."""
        url = '/api/accounts/projects/99999/subscription/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# project_payments_view — invalid project_id (line 2970)
# ===========================================================================

class TestProjectPaymentsInvalidProject:
    """Covers project payments invalid project behavior."""

    def test_invalid_project_returns_404(self, api_client, client_headers):
        """project_payments_view returns 404 when project_id does not exist."""
        url = '/api/accounts/projects/99999/payments/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404
