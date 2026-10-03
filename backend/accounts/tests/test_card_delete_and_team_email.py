"""Tests for card removal and the team payment-status email.

Covers:
- card_delete_view: clears the stored card (best-effort Wompi delete) / 400 when none.
- record_payment_status_change: triggers a team email on PAID/FAILED only.
"""
import logging
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    UserProfile,
)
from accounts.services.payment_history import record_payment_status_change

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """Provide an API client for subscription card requests."""
    return APIClient()


@pytest.fixture
def client_user():
    """Provide a client account that owns the subscription project."""
    user = User.objects.create_user(
        username='client@del.com', email='client@del.com', password='clientpass1',
        first_name='Mimi', last_name='Tos',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    """Provide JWT credentials for the client account."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@del.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    """Provide an active project for subscription fixtures."""
    return Project.objects.create(
        name='Mimitos', client=client_user, status=Project.STATUS_ACTIVE,
    )


@pytest.fixture
def subscription(project):
    """Provide an active quarterly hosting subscription."""
    sub = HostingSubscription(
        project=project, plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('300000'), discount_percent=0,
        start_date='2026-01-01', next_billing_date='2026-04-01',
        status=HostingSubscription.STATUS_ACTIVE,
    )
    sub.calculate_amounts()
    sub.save()
    return sub


@pytest.fixture
def subscription_with_card(subscription):
    """Provide a subscription with a stored Wompi card source."""
    subscription.wompi_payment_source_id = '12345'
    subscription.card_brand = 'VISA'
    subscription.card_last_four = '4242'
    subscription.card_exp_month = '12'
    subscription.card_exp_year = '30'
    subscription.save()
    return subscription


@pytest.fixture
def payment(subscription):
    """Provide a pending payment attached to the subscription."""
    return Payment.objects.create(
        subscription=subscription, amount=Decimal('900000'),
        description='Hosting', billing_period_start='2026-04-01',
        billing_period_end='2026-06-30', due_date='2026-04-01',
        status=Payment.STATUS_PENDING,
    )


DELETE_URL = '/api/accounts/projects/{}/subscription/card/remove/'


# ---------------------------------------------------------------------------
# card_delete_view
# ---------------------------------------------------------------------------

class TestCardDelete:
    """Card removal endpoint behavior."""

    def test_delete_clears_card_and_calls_wompi(
        self, api_client, client_headers, project, subscription_with_card,
    ):
        """Clears locally stored card details after Wompi accepts deletion."""
        with patch('accounts.services.wompi.delete_payment_source', return_value=True) as m:
            resp = api_client.delete(DELETE_URL.format(project.id), **client_headers)

        assert resp.status_code == 200
        m.assert_called_once_with('12345')
        subscription_with_card.refresh_from_db()
        assert subscription_with_card.wompi_payment_source_id == ''
        assert subscription_with_card.card_brand == ''
        assert subscription_with_card.card_last_four == ''
        body = resp.json()
        assert body['subscription']['has_payment_source'] is False

    def test_delete_succeeds_even_if_wompi_fails(
        self, api_client, client_headers, project, subscription_with_card,
    ):
        """Clears local card details when best-effort Wompi deletion fails."""
        # delete_payment_source is best-effort and returns False on Wompi error.
        with patch('accounts.services.wompi.delete_payment_source', return_value=False):
            resp = api_client.delete(DELETE_URL.format(project.id), **client_headers)

        assert resp.status_code == 200
        subscription_with_card.refresh_from_db()
        assert subscription_with_card.wompi_payment_source_id == ''

    def test_delete_without_card_returns_400(
        self, api_client, client_headers, project, subscription,
    ):
        """Rejects card removal when the subscription has no card source."""
        resp = api_client.delete(DELETE_URL.format(project.id), **client_headers)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# team payment-status email trigger
# ---------------------------------------------------------------------------

@pytest.fixture
def team_email(db):
    """Recipients of the payment email now come from the accounting catalog.

    They used to be one inbox pinned in settings; migration 0191 seeds the
    real ones into every test database, so they are cleared first and this
    fixture owns the whole list.
    """
    from content.models import NotificationRecipient

    NotificationRecipient.objects.all().delete()
    NotificationRecipient.objects.create(email='team-test@proyegarts.co')
    # Paused: it must not receive anything.
    NotificationRecipient.objects.create(
        email='pausado@proyegarts.co', is_active=False,
    )
    return 'team-test@proyegarts.co'


class TestTeamPaymentEmailTrigger:
    """record_payment_status_change enqueues the team email on terminal states."""

    def test_paid_transition_enqueues_task(self, payment):
        """Enqueues the team notification for a paid transition."""
        with patch('accounts.tasks.send_payment_status_team_email_task') as m:
            record_payment_status_change(
                payment, Payment.STATUS_PENDING, Payment.STATUS_PAID, source='webhook',
            )
        m.assert_called_once_with(payment.id, Payment.STATUS_PAID, 'webhook')

    def test_failed_transition_enqueues_task(self, payment):
        """Enqueues the team notification for a failed transition."""
        with patch('accounts.tasks.send_payment_status_team_email_task') as m:
            record_payment_status_change(
                payment, Payment.STATUS_PENDING, Payment.STATUS_FAILED, source='webhook',
            )
        m.assert_called_once_with(payment.id, Payment.STATUS_FAILED, 'webhook')

    def test_non_terminal_transition_does_not_enqueue(self, payment):
        """Skips team notification for a processing transition."""
        with patch('accounts.tasks.send_payment_status_team_email_task') as m:
            record_payment_status_change(
                payment, Payment.STATUS_PENDING, Payment.STATUS_PROCESSING, source='webhook',
            )
        m.assert_not_called()

    def test_noop_transition_does_not_enqueue(self, payment):
        """Skips history notification work when the status is unchanged."""
        with patch('accounts.tasks.send_payment_status_team_email_task') as m:
            result = record_payment_status_change(
                payment, Payment.STATUS_PAID, Payment.STATUS_PAID, source='webhook',
            )
        assert result is None
        m.assert_not_called()

    @pytest.mark.parametrize(
        'destination_status',
        [Payment.STATUS_PAID, Payment.STATUS_FAILED],
    )
    def test_terminal_enqueue_failure_preserves_history_with_redacted_warning(
        self, payment, caplog, destination_status,
    ):
        """Falla si un error al encolar borra el historial o filtra datos privados."""
        source = 'source-secret'
        metadata = {'private': 'metadata-secret'}
        caplog.set_level('WARNING', logger='accounts.services.payment_history')

        with patch(
            'accounts.tasks.send_payment_status_team_email_task',
            side_effect=RuntimeError('task-secret'),
        ) as task:
            history = record_payment_status_change(
                payment,
                Payment.STATUS_PENDING,
                destination_status,
                source=source,
                metadata=metadata,
            )

        stored_history = PaymentHistory.objects.get(pk=history.pk)
        warning_messages = [record.getMessage() for record in caplog.records]
        expected_warning = (
            'PAYMENT_STATUS_EMAIL_ENQUEUE_FAILED '
            f'payment_id={payment.id} status={destination_status}'
        )

        assert stored_history.payment_id == payment.id
        assert stored_history.to_status == destination_status
        assert stored_history.metadata == metadata
        task.assert_called_once_with(payment.id, destination_status, source)
        assert warning_messages == [expected_warning]
        assert caplog.records[0].levelno == logging.WARNING
        assert caplog.records[0].exc_info is None


class TestTeamPaymentEmailSend:
    """The send function renders and delivers the team notification."""

    def test_paid_email_goes_to_the_active_recipients_only(self, payment, team_email):
        """Delivers the paid notification to the configured active recipient."""
        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        mail.outbox = []
        ok = send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')
        assert ok is True
        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        assert msg.to == ['team-test@proyegarts.co']
        assert 'Pago aprobado' in msg.subject
        assert 'Mimitos' in msg.subject

    def test_send_is_traced_one_row_per_recipient(self, payment, team_email):
        """Records a sent email audit row for each active recipient."""
        from content.models import EmailLog, NotificationRecipient

        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        NotificationRecipient.objects.create(email='socia@proyegarts.co')
        mail.outbox = []
        send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')

        logs = EmailLog.objects.filter(template_key='payment_status_team')
        assert sorted(logs.values_list('recipient', flat=True)) == [
            'socia@proyegarts.co', 'team-test@proyegarts.co',
        ]
        assert set(logs.values_list('status', flat=True)) == {EmailLog.Status.SENT}
        assert logs.first().metadata['payment_id'] == payment.id

    def test_failed_email_subject(self, payment, team_email):
        """Uses the failed-payment subject for a failed status email."""
        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        mail.outbox = []
        send_payment_status_team_email(payment.id, Payment.STATUS_FAILED, 'webhook')
        assert len(mail.outbox) == 1
        assert 'Pago fallido' in mail.outbox[0].subject

    def test_email_formats_amount_and_dates(self, payment, team_email):
        """Renders the payment amount and billing period in the email."""
        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        mail.outbox = []
        send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')
        msg = mail.outbox[0]
        assert '$900.000 COP' in msg.subject
        assert '$900.000 COP' in msg.body
        assert 'Mié, 1 abr 2026 — Mar, 30 jun 2026' in msg.body


class TestTeamPaymentEmailBranches:
    """Payment-email delivery branches that suppress or trace sending."""

    def test_skips_when_no_recipient_is_active(self, payment, db):
        """Skips delivery when every team recipient is inactive."""
        from content.models import NotificationRecipient

        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        NotificationRecipient.objects.all().update(is_active=False)
        mail.outbox = []
        ok = send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')
        assert ok is False
        assert len(mail.outbox) == 0

    def test_skips_when_the_master_switch_is_off(self, payment, team_email):
        """Skips delivery when accounting notifications are disabled."""
        from content.models import AccountingSettings

        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        config = AccountingSettings.load()
        config.notifications_enabled = False
        config.save()
        mail.outbox = []
        ok = send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')
        assert ok is False
        assert len(mail.outbox) == 0

    def test_returns_false_for_unknown_payment(self, team_email):
        """Reports no delivery for an unknown payment ID."""
        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        mail.outbox = []
        ok = send_payment_status_team_email(999999, Payment.STATUS_PAID, 'webhook')
        assert ok is False
        assert len(mail.outbox) == 0

    def test_send_failure_is_swallowed(self, payment, team_email):
        """Returns false when the email backend raises during delivery."""
        from django.core.mail import EmailMultiAlternatives

        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        with patch.object(
            EmailMultiAlternatives, 'send', side_effect=Exception('SMTP down'),
        ):
            ok = send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')
        assert ok is False

    def test_a_failed_send_is_traced_with_its_reason(self, payment, team_email):
        """Persists the email backend failure reason in the audit log."""
        from content.models import EmailLog
        from django.core.mail import EmailMultiAlternatives

        from accounts.services.payment_notifications import (
            send_payment_status_team_email,
        )

        with patch.object(
            EmailMultiAlternatives, 'send', side_effect=Exception('SMTP down'),
        ):
            send_payment_status_team_email(payment.id, Payment.STATUS_PAID, 'webhook')

        log = EmailLog.objects.get(template_key='payment_status_team')
        assert log.recipient == 'team-test@proyegarts.co'
        assert log.status == EmailLog.Status.FAILED
        assert 'SMTP down' in log.error_message
