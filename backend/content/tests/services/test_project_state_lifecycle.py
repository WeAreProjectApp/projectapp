from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time

from accounts.models import HostingSubscription, Payment, Project, UserProfile
from content.models import (
    DocumentState,
    DocumentStateEpisode,
    DocumentStateEpisodeEvent,
    DocumentStateGroup,
    HostingRecord,
    IncomeRecord,
)
from content.services.project_state_service import (
    ProjectStateError,
    apply_transition,
    merge_project_states,
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


def custom_project_state_group(name):
    return DocumentStateGroup.objects.create(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        name=name,
        selection_mode=DocumentStateGroup.SelectionMode.EXCLUSIVE,
    )


def custom_project_state(group, name, *, effect='operating', **kwargs):
    return DocumentState.objects.create(
        group=group,
        name=name,
        color=DocumentState.Color.BLUE,
        operational_effect=effect,
        **kwargs,
    )


def same_merge_state():
    group = custom_project_state_group('Mismo destino')
    source = custom_project_state(group, 'Origen igual')
    return source, source


def catalog_mismatch_states():
    source_group = DocumentStateGroup.objects.create(
        catalog=DocumentStateGroup.Catalog.DOCUMENTS,
        name='Estados de documentos',
    )
    target_group = custom_project_state_group('Estados de proyectos')
    source = DocumentState.objects.create(group=source_group, name='Documento')
    target = custom_project_state(target_group, 'Proyecto')
    return source, target


def different_group_states():
    source = custom_project_state(
        custom_project_state_group('Grupo de origen'), 'Origen de otro grupo',
    )
    target = custom_project_state(
        custom_project_state_group('Grupo de destino'), 'Destino de otro grupo',
    )
    return source, target


def seeded_source_states():
    group = custom_project_state_group('Grupo semilla')
    source = custom_project_state(group, 'Estado semilla', system_key='custom-seed')
    target = custom_project_state(group, 'Estado destino')
    return source, target


def retired_target_states():
    group = custom_project_state_group('Grupo retirado')
    source = custom_project_state(group, 'Origen vigente')
    target = custom_project_state(group, 'Destino retirado', is_active=False)
    return source, target


def mismatched_effect_states():
    group = custom_project_state_group('Grupo de efectos')
    source = custom_project_state(group, 'Origen operativo')
    target = custom_project_state(group, 'Destino suspendido', effect='suspended')
    return source, target


def document_catalog_preview_target(project):
    group = DocumentStateGroup.objects.create(
        catalog=DocumentStateGroup.Catalog.DOCUMENTS,
        name='Estados de documentos para vista previa',
    )
    return DocumentState.objects.create(group=group, name='Estado documental'), None


def merged_project_preview_target(project):
    group = custom_project_state_group('Estados fusionados para vista previa')
    recipient = custom_project_state(group, 'Estado consolidado')
    target = custom_project_state(group, 'Estado retirado', merged_into=recipient)
    return target, None


def current_project_preview_target(project):
    return project.current_state, None


def future_project_preview_target(project):
    return state('suspended'), timezone.now() + timedelta(days=1)


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


def hosting_payment(project, *, due_date):
    subscription = HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('100000.00'),
        effective_monthly_amount=Decimal('90000.00'),
        billing_amount=Decimal('270000.00'),
        status=HostingSubscription.STATUS_ACTIVE,
        start_date=timezone.localdate(),
        next_billing_date=due_date,
    )
    return Payment.objects.create(
        subscription=subscription,
        amount=Decimal('270000.00'),
        billing_period_start=due_date,
        billing_period_end=due_date,
        due_date=due_date,
        status=Payment.STATUS_PENDING,
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


def test_merging_custom_project_states_preserves_active_history(
    project, actor,
):
    """Fails if a catalog merge retires a state while active project history stays behind."""
    group = custom_project_state_group('Estados comerciales')
    source = custom_project_state(group, 'Operación anterior')
    target = custom_project_state(group, 'Operación consolidada')
    active_episode = project.state_episodes.get(closed_at__isnull=True)
    active_episode.state = source
    active_episode.save(update_fields=('state', 'updated_at'))
    project.current_state = source
    project.save(update_fields=('current_state', 'updated_at'))
    closed_episode = DocumentStateEpisode.objects.create(
        project=project,
        state=source,
        closed_at=timezone.now(),
        outcome=DocumentStateEpisode.Outcome.COMPLETED,
    )

    merged = merge_project_states(source, target, actor=actor)

    project.refresh_from_db()
    source.refresh_from_db()
    active_episode.refresh_from_db()
    closed_episode.refresh_from_db()
    event = DocumentStateEpisodeEvent.objects.get(
        episode=active_episode,
        event_type=DocumentStateEpisodeEvent.EventType.MERGED,
    )
    assert merged.pk == source.pk
    assert (source.is_active, source.merged_into_id, source.updated_by_id) == (
        False,
        target.pk,
        actor.pk,
    )
    assert (project.current_state_id, active_episode.state_id, closed_episode.state_id) == (
        target.pk,
        target.pk,
        source.pk,
    )
    assert (event.actor_id, event.details) == (
        actor.pk,
        {
            'source_state_id': source.pk,
            'source_state_name': source.name,
            'target_state_id': target.pk,
            'target_state_name': target.name,
        },
    )


@pytest.mark.parametrize(
    ('state_builder', 'expected_code'),
    [
        pytest.param(same_merge_state, 'same_merge_target', id='same-state'),
        pytest.param(
            catalog_mismatch_states,
            'state_catalog_mismatch',
            id='document-catalog',
        ),
        pytest.param(
            different_group_states,
            'merge_group_mismatch',
            id='different-group',
        ),
        pytest.param(
            seeded_source_states,
            'system_state_merge_blocked',
            id='seeded-source',
        ),
        pytest.param(
            retired_target_states,
            'merge_target_retired',
            id='retired-target',
        ),
        pytest.param(
            mismatched_effect_states,
            'merge_effect_mismatch',
            id='different-effect',
        ),
    ],
)
def test_merging_invalid_catalog_states_preserves_both_states(
    state_builder, expected_code,
):
    """Fails if an invalid merge mutates either catalog state before rejection."""
    source, target = state_builder()
    before_source = (source.is_active, source.merged_into_id)
    before_target = (target.is_active, target.merged_into_id)

    with pytest.raises(ProjectStateError) as exc_info:
        merge_project_states(source, target)

    source.refresh_from_db()
    target.refresh_from_db()
    assert exc_info.value.code == expected_code
    assert (source.is_active, source.merged_into_id) == before_source
    assert (target.is_active, target.merged_into_id) == before_target


@pytest.mark.parametrize(
    ('target_builder', 'expected_code'),
    [
        pytest.param(
            document_catalog_preview_target,
            'state_catalog_mismatch',
            id='document-catalog',
        ),
        pytest.param(
            merged_project_preview_target,
            'state_retired',
            id='merged-project-state',
        ),
        pytest.param(
            current_project_preview_target,
            'state_already_active',
            id='current-project-state',
        ),
        pytest.param(
            future_project_preview_target,
            'effective_at_in_future',
            id='future-effective-date',
        ),
    ],
)
def test_preview_rejects_invalid_project_transition(
    project, target_builder, expected_code,
):
    """Fails if preview accepts an impossible lifecycle transition before any write."""
    target, effective_at = target_builder(project)
    before_state_id = project.current_state_id

    with pytest.raises(ProjectStateError) as exc_info:
        preview_transition(project, target, effective_at=effective_at)

    project.refresh_from_db()
    assert exc_info.value.code == expected_code
    assert project.current_state_id == before_state_id


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


def test_operating_preview_leaves_future_income_collectible(project, client_profile, actor):
    """Falla si API/MCP anuncian una cancelación que la transición no ejecuta."""
    with freeze_time(project.created_at + timedelta(hours=1)):
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


def test_decommission_write_off_marks_an_unpaid_income_lost(
    project, client_profile, actor,
):
    """Fails if a write-off leaves an unpaid caused income collectible or duplicates it."""
    with freeze_time(project.created_at + timedelta(hours=1)):
        income = expected_income(project, client_profile)
        transition(project, state('suspended'), actor)
        preview = preview_transition(project, state('decommissioned'))

        apply_transition(
            project,
            state('decommissioned'),
            actor=actor,
            impact_token=preview['impact_token'],
            resolutions=[{'income_id': income.pk, 'action': 'write_off'}],
        )

        income.refresh_from_db()
        assert (income.kind, income.reminders_muted) == (
            IncomeRecord.Kind.LOST,
            True,
        )
        assert IncomeRecord.objects.filter(expected_income=income).count() == 0


def test_decommission_write_off_preserves_a_partial_payment_split(
    project, client_profile, actor,
):
    """Fails if a write-off loses a partial payment or misallocates partner balances."""
    with freeze_time(project.created_at + timedelta(hours=1)):
        income = IncomeRecord.objects.create(
            concept='Hosting con abono',
            kind=IncomeRecord.Kind.EXPECTED,
            client=client_profile,
            project=project,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=timezone.localdate(),
            total_amount=Decimal('900.00'),
            gustavo_amount=Decimal('450.00'),
            carlos_amount=Decimal('450.00'),
        )
        IncomeRecord.objects.create(
            concept='Abono de hosting',
            kind=IncomeRecord.Kind.LIQUID,
            client=client_profile,
            project=project,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=timezone.localdate(),
            total_amount=Decimal('300.00'),
            gustavo_amount=Decimal('150.00'),
            carlos_amount=Decimal('150.00'),
            expected_income=income,
        )
        transition(project, state('suspended'), actor)
        preview = preview_transition(project, state('decommissioned'))

        apply_transition(
            project,
            state('decommissioned'),
            actor=actor,
            impact_token=preview['impact_token'],
            resolutions=[{'income_id': income.pk, 'action': 'write_off'}],
        )

        income.refresh_from_db()
        lost = IncomeRecord.objects.get(
            expected_income=income,
            kind=IncomeRecord.Kind.LOST,
        )
        assert (
            income.total_amount,
            income.gustavo_amount,
            income.carlos_amount,
            income.reminders_muted,
        ) == (Decimal('300.00'), Decimal('150.00'), Decimal('150.00'), True)
        assert (
            lost.total_amount,
            lost.gustavo_amount,
            lost.carlos_amount,
            lost.source_ref,
        ) == (
            Decimal('600.00'),
            Decimal('300.00'),
            Decimal('300.00'),
            f'project-state:{project.pk}:decommission',
        )


@pytest.mark.parametrize('target_key', ('completed', 'decommissioned'))
def test_terminal_transition_blocks_caused_hosting_payment(
    project, actor, target_key,
):
    """Fails if a terminal transition can bypass an open hosting charge already due."""
    with freeze_time(project.created_at + timedelta(hours=1)):
        hosting_payment(project, due_date=timezone.localdate())
        target = state(target_key)
        preview = preview_transition(project, target)
        before_state_id = project.current_state_id

        with pytest.raises(ProjectStateError) as exc_info:
            apply_transition(
                project,
                target,
                actor=actor,
                impact_token=preview['impact_token'],
            )

        project.refresh_from_db()
        assert [row['code'] for row in preview['blockers']] == [
            'pending_hosting_payments'
        ]
        assert exc_info.value.code == 'pending_hosting_payments'
        assert project.current_state_id == before_state_id


def test_decommission_archives_future_hosting_payment(project, actor):
    """Fails if decommissioning leaves a scheduled hosting charge available to collect."""
    with freeze_time(project.created_at + timedelta(hours=1)):
        payment = hosting_payment(
            project,
            due_date=timezone.localdate() + timedelta(days=1),
        )
        preview = preview_transition(project, state('decommissioned'))

        apply_transition(
            project,
            state('decommissioned'),
            actor=actor,
            impact_token=preview['impact_token'],
            note='Cliente solicita la baja definitiva.',
        )

        payment.refresh_from_db()
        payment.subscription.refresh_from_db()
        assert payment.is_archived is True
        assert payment.subscription.status == HostingSubscription.STATUS_CANCELLED


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
