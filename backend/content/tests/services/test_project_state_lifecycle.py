from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time

from accounts.models import HostingSubscription, Project, UserProfile
from content.models import (
    DocumentState,
    DocumentStateEpisode,
    HostingRecord,
    IncomeRecord,
)
from content.services.project_state_service import (
    ProjectStateError,
    apply_transition,
    preview_transition,
    project_allows_billing,
    project_state_suggestion,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def actor():
    return User.objects.create_superuser(
        username='state-admin@example.com',
        email='state-admin@example.com',
        password='pass12345',
    )


@pytest.fixture
def client_profile():
    user = User.objects.create_user(
        username='state-client@example.com',
        email='state-client@example.com',
        password='pass12345',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


@pytest.fixture
def project(client_profile):
    return Project.objects.create(
        name='Proyecto ciclo real',
        client=client_profile.user,
        status=Project.STATUS_ACTIVE,
    )


def state(key):
    return DocumentState.objects.get(catalog='projects', system_key=key)


def expected_income(project, client_profile, *, days=0):
    return IncomeRecord.objects.create(
        concept='Hosting pendiente',
        kind=IncomeRecord.Kind.EXPECTED,
        client=client_profile,
        project=project,
        origin=IncomeRecord.Origin.HOSTING,
        period_date=timezone.localdate() + timedelta(days=days),
        total_amount=Decimal('900000.00'),
        gustavo_amount=Decimal('450000.00'),
        carlos_amount=Decimal('450000.00'),
    )


def transition(project, target, actor, *, note='', resolutions=None):
    preview = preview_transition(project, target)
    result, episode = apply_transition(
        project,
        target,
        actor=actor,
        impact_token=preview['impact_token'],
        note=note,
        resolutions=resolutions or [],
    )
    project.refresh_from_db()
    return result, episode


def test_direct_project_creation_opens_the_requested_legacy_state(project):
    project.refresh_from_db()

    assert project.current_state.system_key == Project.STATUS_ACTIVE
    assert DocumentStateEpisode.objects.filter(
        project=project,
        state=project.current_state,
        closed_at__isnull=True,
    ).count() == 1


def test_unclassified_legacy_archive_blocks_billing(client_profile):
    legacy = Project.objects.create(
        name='Proyecto archivado sin clasificar',
        client=client_profile.user,
        status=Project.STATUS_ARCHIVED,
    )

    legacy.refresh_from_db()
    assert legacy.current_state_id is None
    assert legacy.state_review_required is True
    assert project_allows_billing(legacy) is False


def test_suspended_preview_preserves_caused_debt(project, client_profile):
    income = expected_income(project, client_profile)

    preview = preview_transition(project, state('suspended'))

    assert preview['pending_incomes'][0]['id'] == income.pk
    assert preview['future_incomes'] == []
    assert preview['blockers'] == []


@freeze_time('2026-11-07 12:00:00')
def test_operating_preview_leaves_future_income_collectible(project, client_profile, actor):
    """Falla si API/MCP anuncian una cancelación que la transición no ejecuta."""
    income = expected_income(project, client_profile, days=7)
    target = state('evolving')

    preview = preview_transition(project, target)
    apply_transition(project, target, actor=actor, impact_token=preview['impact_token'])

    income.refresh_from_db()
    assert preview['target_effect'] == 'operating'
    assert preview['future_incomes'] == []
    assert income.kind == IncomeRecord.Kind.EXPECTED
    assert income.total_amount == Decimal('900000.00')


def test_suspended_transition_keeps_expected_income(project, client_profile, actor):
    income = expected_income(project, client_profile)

    transition(project, state('suspended'), actor)

    income.refresh_from_db()
    assert project.current_state.system_key == 'suspended'
    assert income.kind == IncomeRecord.Kind.EXPECTED


def test_suspended_transition_cancels_future_projection(
    project, client_profile, actor,
):
    future = expected_income(project, client_profile, days=30)

    transition(project, state('suspended'), actor)

    future.refresh_from_db()
    assert future.kind == IncomeRecord.Kind.CANCELLED


def test_transition_rejects_a_stale_preview(project, actor):
    target = state('suspended')
    preview = preview_transition(project, target)
    project.name = 'Cambió mientras se confirmaba'
    project.save(update_fields=('name', 'updated_at'))

    with pytest.raises(ProjectStateError) as exc_info:
        apply_transition(
            project,
            target,
            actor=actor,
            impact_token=preview['impact_token'],
        )

    assert exc_info.value.code == 'stale_transition_preview'


def test_completed_preview_blocks_a_pending_income(
    project, client_profile,
):
    expected_income(project, client_profile)

    preview = preview_transition(project, state('completed'))

    assert preview['blockers'][0]['code'] == 'pending_incomes'


def test_direct_decommission_requires_a_note(project, actor):
    target = state('decommissioned')
    preview = preview_transition(project, target)

    with pytest.raises(ProjectStateError) as exc_info:
        apply_transition(
            project,
            target,
            actor=actor,
            impact_token=preview['impact_token'],
        )

    assert exc_info.value.code == 'direct_decommission_note_required'


def test_decommission_requires_one_resolution_per_caused_income(
    project, client_profile, actor,
):
    expected_income(project, client_profile)
    transition(project, state('suspended'), actor)
    preview = preview_transition(project, state('decommissioned'))

    with pytest.raises(ProjectStateError) as exc_info:
        apply_transition(
            project,
            state('decommissioned'),
            actor=actor,
            impact_token=preview['impact_token'],
        )

    assert exc_info.value.code == 'income_resolutions_required'


def test_decommission_keeps_debt_and_cancels_future_service(
    project, client_profile, actor,
):
    caused = expected_income(project, client_profile)
    future = expected_income(project, client_profile, days=30)
    hosting = HostingRecord.objects.create(
        client=client_profile,
        project=project,
        client_name='Cliente - Proyecto',
        monthly_value=Decimal('100000.00'),
    )
    subscription = HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('100000.00'),
        effective_monthly_amount=Decimal('90000.00'),
        billing_amount=Decimal('270000.00'),
        status=HostingSubscription.STATUS_ACTIVE,
        start_date=timezone.localdate(),
        next_billing_date=timezone.localdate() + timedelta(days=60),
    )
    transition(project, state('suspended'), actor)
    preview = preview_transition(project, state('decommissioned'))

    apply_transition(
        project,
        state('decommissioned'),
        actor=actor,
        impact_token=preview['impact_token'],
        resolutions=[{'income_id': caused.pk, 'action': 'keep_receivable'}],
    )

    caused.refresh_from_db()
    future.refresh_from_db()
    hosting.refresh_from_db()
    subscription.refresh_from_db()
    assert caused.kind == IncomeRecord.Kind.EXPECTED
    assert caused.reminders_muted is True
    assert future.kind == IncomeRecord.Kind.CANCELLED
    assert hosting.is_active is False
    assert subscription.status == HostingSubscription.STATUS_CANCELLED


def test_suspended_subscription_returns_a_manual_state_suggestion(project):
    HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('100000.00'),
        effective_monthly_amount=Decimal('90000.00'),
        billing_amount=Decimal('270000.00'),
        status=HostingSubscription.STATUS_SUSPENDED,
        start_date=timezone.localdate(),
        next_billing_date=timezone.localdate(),
    )

    suggestion = project_state_suggestion(project)

    assert suggestion['reason'] == 'hosting_payment_failed'
    assert suggestion['state_name'] == 'Suspendido'
