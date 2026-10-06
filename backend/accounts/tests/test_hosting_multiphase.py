"""Test multi-phase hosting billing.

Cover per-phase costs, summed activation, and prorated phase onboarding.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import DEFAULT, patch

import pytest
from django.contrib.auth import get_user_model
from django.db import OperationalError, transaction
from freezegun import freeze_time
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Notification,
    Payment,
    Project,
    ProjectPhase,
    UserProfile,
)
from accounts.services import hosting_billing
from accounts.tasks import _onboard_due_phases
from content.models import ProjectRetentionContext

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """Return an API client for subscription endpoint tests."""
    return APIClient()


@pytest.fixture
def client_user():
    """Return an onboarded client who owns the test project."""
    user = User.objects.create_user(
        username='client@mp.com', email='client@mp.com', password='clientpass1',
        first_name='Carla', last_name='Mora',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    """Return a platform access bearer for the test client."""
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@mp.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    """Return an active project for hosting scenarios."""
    return Project.objects.create(
        name='Multi Phase Project', client=client_user, status=Project.STATUS_ACTIVE,
    )


def _proposal(total):
    """Build a BusinessProposal pinned to the fixed hosting percentage.

    hosting_percent is set explicitly (not left to the model default) so the
    billing-math assertions below stay stable regardless of the production
    default.
    """
    from content.models import BusinessProposal
    return BusinessProposal.objects.create(
        title=f'Proposal {total}', client_name='Test', total_investment=Decimal(total),
        hosting_percent=40,
    )


def _phase(project, total, order, start_date=None, activated_at=None):
    return ProjectPhase.objects.create(
        project=project, business_proposal=_proposal(total), order=order,
        hosting_start_date=start_date, hosting_activated_at=activated_at,
    )


# ===========================================================================
# hosting_billing service
# ===========================================================================

class TestHostingBilling:
    """Verify pure per-phase hosting billing calculations."""

    def test_phase_billing_amount_per_frequency(self, project):
        """Ensure each plan applies its configured billing frequency."""
        # total 12,000,000 * 40% / 12 = 400,000 monthly base
        phase = _phase(project, 12_000_000, order=1)
        assert hosting_billing.phase_billing_amount(phase, 'monthly') == Decimal('400000')
        # quarterly: 400000 * 3 * 0.90
        assert hosting_billing.phase_billing_amount(phase, 'quarterly') == Decimal('1080000')
        # semiannual: 400000 * 6 * 0.80
        assert hosting_billing.phase_billing_amount(phase, 'semiannual') == Decimal('1920000')

    def test_project_billing_amount_sums_only_activated_phases(self, project):
        """Ensure an inactive phase is excluded from recurring billing."""
        _phase(project, 12_000_000, order=1, activated_at=date(2026, 1, 1))
        _phase(project, 6_000_000, order=2)  # not activated
        # only the activated phase counts: 1,920,000
        assert hosting_billing.project_billing_amount(project, 'semiannual') == Decimal('1920000')

    def test_project_billing_amount_sums_all_activated(self, project):
        """Ensure each activated phase contributes to recurring billing."""
        _phase(project, 12_000_000, order=1, activated_at=date(2026, 1, 1))
        _phase(project, 6_000_000, order=2, activated_at=date(2026, 1, 1))
        # 1,920,000 + 960,000
        assert hosting_billing.project_billing_amount(project, 'semiannual') == Decimal('2880000')

    def test_prorated_amount_partial_cycle(self, project):
        """Ensure a mid-cycle phase pays only its remaining days."""
        phase = _phase(project, 12_000_000, order=1)  # monthly amount 400,000
        # 10-day cycle, joining on day 6 -> 5 of 10 days remain -> half
        result = hosting_billing.prorated_amount(
            phase, 'monthly',
            join_date=date(2026, 1, 6),
            cycle_start=date(2026, 1, 1),
            cycle_end=date(2026, 1, 10),
        )
        assert result == Decimal('200000')

    def test_prorated_amount_zero_outside_cycle(self, project):
        """Ensure a phase outside the billing cycle has no prorated charge."""
        phase = _phase(project, 12_000_000, order=1)
        result = hosting_billing.prorated_amount(
            phase, 'monthly',
            join_date=date(2026, 2, 1),
            cycle_start=date(2026, 1, 1),
            cycle_end=date(2026, 1, 10),
        )
        assert result == Decimal('0')

    def test_prorated_amount_ignores_frequency_discount(self, project):
        """Proration uses the full (undiscounted) rate, not the plan discount."""
        phase = _phase(project, 12_000_000, order=1)  # monthly base 400,000
        # A whole cycle on the semiannual plan -> the full undiscounted amount.
        result = hosting_billing.prorated_amount(
            phase, 'semiannual',
            join_date=date(2026, 1, 1),
            cycle_start=date(2026, 1, 1),
            cycle_end=date(2026, 1, 10),
        )
        # 400,000 * 6 months, NOT 1,920,000 (the 20%-discounted semiannual price)
        assert result == Decimal('2400000')
        assert result > hosting_billing.phase_billing_amount(phase, 'semiannual')


# ===========================================================================
# Multi-phase activation
# ===========================================================================

class TestMultiPhaseActivation:
    """Verify subscription activation across project phases."""

    def _url(self, project):
        """Return the subscription endpoint for a project."""
        return f'/api/accounts/projects/{project.id}/subscription/'

    def test_activation_sums_started_phases(self, api_client, client_headers, project):
        """Ensure activation includes every phase already started."""
        _phase(project, 12_000_000, order=1)
        _phase(project, 6_000_000, order=2)
        resp = api_client.post(self._url(project), {'plan': 'semiannual'}, **client_headers)
        assert resp.status_code == 201
        assert Decimal(resp.json()['billing_amount']) == Decimal('2880000')

    def test_activation_excludes_future_phase(self, api_client, client_headers, project):
        """Ensure activation excludes a phase that has not started."""
        _phase(project, 12_000_000, order=1)
        future = _phase(project, 6_000_000, order=2, start_date=date.today() + timedelta(days=90))
        resp = api_client.post(self._url(project), {'plan': 'semiannual'}, **client_headers)
        assert resp.status_code == 201
        assert Decimal(resp.json()['billing_amount']) == Decimal('1920000')
        future.refresh_from_db()
        assert future.hosting_activated_at is None

    def test_activation_rejects_when_no_started_phase(self, api_client, client_headers, project):
        """Ensure activation rejects projects with only future phases."""
        _phase(project, 12_000_000, order=1, start_date=date.today() + timedelta(days=30))
        _phase(project, 6_000_000, order=2, start_date=date.today() + timedelta(days=30))
        resp = api_client.post(self._url(project), {'plan': 'semiannual'}, **client_headers)
        assert resp.status_code == 400


# ===========================================================================
# Phase onboarding cron (_onboard_due_phases)
# ===========================================================================

@freeze_time('2026-04-04')
class TestPhaseOnboarding:
    """Verify the recurring task that activates hosting phases."""

    def _active_subscription(self, project):
        """Return an active semiannual subscription with a July renewal."""
        return HostingSubscription.objects.create(
            project=project, plan=HostingSubscription.PLAN_SEMIANNUAL,
            base_monthly_amount=Decimal('400000'), discount_percent=0,
            effective_monthly_amount=Decimal('320000'), billing_amount=Decimal('1920000'),
            status=HostingSubscription.STATUS_ACTIVE,
            start_date=date(2026, 1, 1), next_billing_date=date(2026, 7, 1),
        )

    def test_onboards_due_phase_with_prorated_payment(self, project):
        """Ensure a due phase creates its prorated catch-up payment."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        phase2 = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        sub = self._active_subscription(project)

        count = _onboard_due_phases()

        assert count == 1
        phase2.refresh_from_db()
        sub.refresh_from_db()
        assert phase2.hosting_activated_at is not None
        # recurring total grew to include phase 2: 1,920,000 + 960,000
        assert sub.billing_amount == Decimal('2880000')
        # a prorated catch-up payment was created, charged at the full
        # (undiscounted) rate — phase 2 monthly base 200,000 * 6 = 1,200,000
        prorated = Payment.objects.filter(subscription=sub, description__icontains='prorrateado')
        assert prorated.count() == 1
        assert Decimal('0') < prorated.first().amount < Decimal('1200000')

    def test_skips_phase_without_subscription(self, project):
        """Ensure a phase without an active subscription stays inactive."""
        phase = _phase(project, 6_000_000, order=1, start_date=date(2026, 3, 1))
        count = _onboard_due_phases()
        assert count == 0
        phase.refresh_from_db()
        assert phase.hosting_activated_at is None

    def test_skips_legacy_unclassified_project(self, project):
        """Ensure an unresolved legacy project is skipped by onboarding."""
        Project.objects.filter(pk=project.pk).update(
            status=Project.STATUS_ARCHIVED,
            current_state=None,
            state_review_required=True,
        )
        phase = _phase(project, 6_000_000, order=1, start_date=date(2026, 3, 1))
        self._active_subscription(project)

        count = _onboard_due_phases()

        assert count == 0
        phase.refresh_from_db()
        assert phase.hosting_activated_at is None

    def test_skips_retained_phase_while_onboarding_operational_phase(self, project):
        """Fails if retained project history is picked up by phase-onboarding automation."""
        active_phase = _phase(project, 12_000_000, order=1, start_date=date(2026, 3, 1))
        retained_phase = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        self._active_subscription(project)
        context = ProjectRetentionContext.objects.create(
            client=project.client,
            original_project_id=project.pk,
            project_name=project.name,
            retained_records={},
            created_by=project.client,
        )
        ProjectPhase.objects.filter(pk=retained_phase.pk).update(
            project=None,
            retention_context=context,
        )

        count = _onboard_due_phases()

        active_phase.refresh_from_db()
        retained_phase.refresh_from_db()
        assert count == 1
        assert active_phase.hosting_activated_at == date(2026, 4, 4)
        assert retained_phase.hosting_activated_at is None

    @pytest.mark.parametrize('failure_target', [
        'accounts.models.Payment.objects.create',
        'accounts.models.HostingSubscription.save',
        'django.db.models.query.QuerySet.update',
    ])
    def test_write_failure_rolls_back_due_phase(
        self, project, django_capture_on_commit_callbacks, failure_target,
    ):
        """Fails if a failed phase write leaves hosting marked as activated."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        phase = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        sub = self._active_subscription(project)

        with patch(failure_target, side_effect=RuntimeError('database write failed')):
            with patch('accounts.tasks._notify_phase_onboarded') as notify:
                with django_capture_on_commit_callbacks(execute=True):
                    count = _onboard_due_phases()

        phase.refresh_from_db()
        sub.refresh_from_db()
        assert count == 0
        assert phase.hosting_activated_at is None
        assert Payment.objects.filter(subscription=sub, description__icontains='prorrateado').count() == 0
        assert sub.billing_amount == Decimal(1920000)
        assert notify.call_count == 0

    def test_rolled_back_phase_retries_once(
        self, project, django_capture_on_commit_callbacks,
    ):
        """Fails if a rolled-back phase remains invisible to the next cron run."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        phase = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        sub = self._active_subscription(project)

        with patch('accounts.models.Payment.objects.create', side_effect=RuntimeError('write failed')):
            _onboard_due_phases()
        with django_capture_on_commit_callbacks(execute=True):
            retry_count = _onboard_due_phases()

        phase.refresh_from_db()
        sub.refresh_from_db()
        assert retry_count == 1
        assert phase.hosting_activated_at == date(2026, 4, 4)
        assert Payment.objects.filter(subscription=sub, description__icontains='prorrateado').count() == 1
        assert sub.billing_amount == Decimal(2880000)
        assert _onboard_due_phases() == 0

    def test_failed_phase_does_not_stop_other_due_phase(
        self, project, django_capture_on_commit_callbacks,
    ):
        """Fails if one failed phase prevents another due phase from onboarding."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        failed_phase = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        healthy_phase = _phase(project, 3_000_000, order=3, start_date=date(2026, 3, 1))
        sub = self._active_subscription(project)

        with patch(
            'accounts.models.Payment.objects.create',
            wraps=Payment.objects.create,
            side_effect=[RuntimeError('first phase write failed'), DEFAULT],
        ), django_capture_on_commit_callbacks(execute=True):
            count = _onboard_due_phases()

        failed_phase.refresh_from_db()
        healthy_phase.refresh_from_db()
        sub.refresh_from_db()
        assert count == 1
        assert failed_phase.hosting_activated_at is None
        assert healthy_phase.hosting_activated_at == date(2026, 4, 4)
        assert Payment.objects.filter(subscription=sub, description__icontains='prorrateado').count() == 1
        assert sub.billing_amount == Decimal(2400000)

    def test_notification_runs_after_outer_transaction_commits(
        self, project, django_capture_on_commit_callbacks,
    ):
        """Fails if the phase notification runs before the billing transaction commits."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        phase = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        sub = self._active_subscription(project)

        with transaction.atomic():
            with django_capture_on_commit_callbacks(execute=False) as callbacks:
                count = _onboard_due_phases()
            assert count == 1
            assert len(callbacks) == 1
            assert Notification.objects.filter(
                project=project, title='Nueva fase en tu hosting',
            ).count() == 0

        phase.refresh_from_db()
        sub.refresh_from_db()
        assert phase.hosting_activated_at == date(2026, 4, 4)
        assert Payment.objects.filter(subscription=sub, description__icontains='prorrateado').count() == 1
        assert sub.billing_amount == Decimal(2880000)
        callbacks[0]()

        assert Notification.objects.filter(
            project=project, title='Nueva fase en tu hosting',
        ).count() == 1

    def test_notification_persistence_failure_keeps_committed_billing(
        self, project, django_capture_on_commit_callbacks, caplog,
    ):
        """Fails if a notification database failure undoes committed phase billing."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        phase = _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        phase.business_proposal.title = 'notification-payload-sentinel'
        phase.business_proposal.save(update_fields=['title'])
        sub = self._active_subscription(project)

        with patch(
            'accounts.models.Notification.objects.create',
            side_effect=OperationalError('notification storage unavailable'),
        ), caplog.at_level(logging.WARNING, logger='accounts.tasks'):
            with transaction.atomic():
                with django_capture_on_commit_callbacks(execute=False) as callbacks:
                    count = _onboard_due_phases()
            callbacks[0]()

        phase.refresh_from_db()
        sub.refresh_from_db()
        messages = caplog.text
        assert count == 1
        assert phase.hosting_activated_at == date(2026, 4, 4)
        assert Payment.objects.filter(subscription=sub, description__icontains='prorrateado').count() == 1
        assert sub.billing_amount == Decimal(2880000)
        assert Notification.objects.filter(project=project).count() == 0
        assert 'Failed to send phase-onboarded notification' in messages
        assert 'notification-payload-sentinel' not in messages

    def test_onboarding_changes_only_future_pending_payments(self, project):
        """Fails if onboarding rewrites historical or non-pending payment amounts."""
        _phase(project, 12_000_000, order=1, start_date=date(2026, 1, 1),
               activated_at=date(2026, 1, 1))
        _phase(project, 6_000_000, order=2, start_date=date(2026, 3, 1))
        sub = self._active_subscription(project)
        previous_pending = Payment.objects.create(
            subscription=sub, amount=Decimal(1900000), description='Previous pending',
            billing_period_start=date(2026, 1, 1), billing_period_end=date(2026, 6, 30),
            due_date=date(2026, 1, 1), status=Payment.STATUS_PENDING,
        )
        future_pending = Payment.objects.create(
            subscription=sub, amount=Decimal(1900000), description='Future pending',
            billing_period_start=date(2026, 7, 1), billing_period_end=date(2026, 12, 31),
            due_date=date(2026, 7, 1), status=Payment.STATUS_PENDING,
        )
        future_paid = Payment.objects.create(
            subscription=sub, amount=Decimal(1900000), description='Future paid',
            billing_period_start=date(2026, 7, 1), billing_period_end=date(2026, 12, 31),
            due_date=date(2026, 7, 1), status=Payment.STATUS_PAID,
        )

        count = _onboard_due_phases()

        previous_pending.refresh_from_db()
        future_pending.refresh_from_db()
        future_paid.refresh_from_db()
        assert count == 1
        assert previous_pending.amount == Decimal(1900000)
        assert future_pending.amount == Decimal(2880000)
        assert future_paid.amount == Decimal(1900000)


# ===========================================================================
# Frequency change while the subscription is still pending
# ===========================================================================

class TestFrequencyChangeWhilePending:
    """Verify pending subscriptions can change their billing frequency."""

    def _activate(self, api_client, headers, project, plan='quarterly'):
        """Activate a subscription with the requested plan."""
        return api_client.post(
            f'/api/accounts/projects/{project.id}/subscription/', {'plan': plan}, **headers,
        )

    def test_client_changes_plan_while_pending_realigns_first_payment(
        self, api_client, client_headers, project,
    ):
        """Ensure a pending plan change rewrites its first unpaid payment."""
        _phase(project, 12_000_000, order=1)
        assert self._activate(api_client, client_headers, project, 'quarterly').status_code == 201

        resp = api_client.patch(
            f'/api/accounts/projects/{project.id}/subscription/',
            {'plan': 'semiannual'}, format='json', **client_headers,
        )
        assert resp.status_code == 200
        assert Decimal(resp.json()['billing_amount']) == Decimal('1920000')
        # the unpaid first payment is realigned to the new frequency
        sub = HostingSubscription.objects.get(project=project)
        first = Payment.objects.filter(subscription=sub).order_by('billing_period_start').first()
        assert first.amount == Decimal('1920000')

    def test_client_cannot_change_plan_after_active(
        self, api_client, client_headers, project,
    ):
        """Ensure an active subscription rejects a client plan change."""
        _phase(project, 12_000_000, order=1)
        self._activate(api_client, client_headers, project, 'quarterly')
        sub = HostingSubscription.objects.get(project=project)
        sub.status = HostingSubscription.STATUS_ACTIVE
        sub.save(update_fields=['status'])

        resp = api_client.patch(
            f'/api/accounts/projects/{project.id}/subscription/',
            {'plan': 'semiannual'}, format='json', **client_headers,
        )
        assert resp.status_code == 403


class TestFirstBillingDate:
    """Free month + always-bill-on-the-1st date logic (pure function)."""

    @pytest.mark.parametrize(('delivery', 'expected'), [
        (date(2026, 6, 28), date(2026, 8, 1)),   # mid-month -> 1st of following month
        (date(2026, 7, 10), date(2026, 9, 1)),   # early month, still >= 1 free month
        (date(2026, 7, 1), date(2026, 8, 1)),    # on the 1st -> exactly one free month
        (date(2026, 12, 15), date(2027, 2, 1)),  # year rollover
    ])
    def test_first_billing_date(self, delivery, expected):
        """Ensure the free month moves the first bill to the next first day."""
        assert hosting_billing.first_billing_date(delivery) == expected


class TestNineMonthPlan:
    """Nine-month hosting plan: discount + billing amount."""

    def test_plan_discount_nine_month_uses_model_field(self, project):
        """Ensure the nine-month plan reads its configured discount."""
        phase = _phase(project, 12_000_000, order=1)
        assert hosting_billing.plan_discount(
            phase, HostingSubscription.PLAN_NINE_MONTH,
        ) == Decimal('40')

    def test_nine_month_billing_amount(self, project):
        """Ensure the nine-month plan applies its discount to recurring billing."""
        # monthly base 400,000; nine-month = 400,000 * 9 * 0.60
        phase = _phase(project, 12_000_000, order=1)
        assert hosting_billing.phase_billing_amount(
            phase, HostingSubscription.PLAN_NINE_MONTH,
        ) == Decimal('2160000')
