"""Lifecycle decisions preserve money and have an explicit paired pause."""

from datetime import date
from decimal import Decimal

import pytest
from accounts.models import (
    BillingContextEvent,
    CollectionAccountContext,
    HostingSubscription,
    Payment,
    PaymentHistory,
    ProjectHosting,
    ProjectHostingAccountingSource,
)
from accounts.services.hosting_subscription_lifecycle import (
    SubscriptionLifecycleError,
    apply_change,
    plan_change,
)
from content.models import HostingCycle, IncomeRecord, ProjectRetentionContext
from content.tests.mcp_parity import assert_no_writes
from freezegun import freeze_time

pytestmark = pytest.mark.django_db
TODAY = date(2026, 10, 9)


@pytest.fixture(autouse=True)
def clock():
    with freeze_time('2026-10-09 12:00:00'):
        yield


@pytest.fixture
def lifecycle(subscription):
    subscription.plan = HostingSubscription.PLAN_SEMIANNUAL
    subscription.base_monthly_amount = Decimal(800)
    subscription.effective_monthly_amount = Decimal(800)
    subscription.billing_amount = Decimal(4800)
    subscription.next_billing_date = date(2026, 12, 1)
    subscription.save()
    return subscription


@pytest.fixture
def obligation(lifecycle):
    return Payment.objects.create(
        subscription=lifecycle, amount=4800, due_date=date(2026, 12, 1),
        billing_period_start=date(2026, 12, 1), billing_period_end=date(2027, 5, 31),
    )


def enact(subscription, actor, action, effective_date=TODAY):
    preview = plan_change(subscription, action, effective_date)
    return apply_change(subscription.pk, action, effective_date, 'Decisión administrativa', preview['impact_hash'], actor)


@pytest.mark.parametrize('initial,action,target', [
    ('active', 'pause', 'suspended'), ('pending', 'pause', 'suspended'),
    ('active', 'cancel', 'cancelled'), ('pending', 'cancel', 'cancelled'),
    ('suspended', 'cancel', 'cancelled'), ('suspended', 'resume', 'active'),
])
def test_transition_matrix(lifecycle, obligation, admin_user, initial, action, target):
    lifecycle.status = initial
    lifecycle.save()
    BillingContextEvent.objects.create(
        project=lifecycle.project, actor=admin_user, operation='hosting_subscription.pause',
        reason='Pausa anterior', before={}, after={'subscription_id': lifecycle.pk, 'voided_payment_ids': []},
    )
    preview = assert_no_writes(plan_change, lifecycle, action)

    result = apply_change(lifecycle.pk, action, TODAY, 'Transición solicitada', preview['impact_hash'], admin_user)

    lifecycle.refresh_from_db()
    obligation.refresh_from_db()
    assert lifecycle.status == target
    assert result['subscription']['after']['status'] == target
    assert BillingContextEvent.objects.get(pk=result['event_id']).operation == f'hosting_subscription.{action}'
    assert obligation.status == {'pause': 'voided', 'cancel': 'voided', 'resume': 'pending'}[action]
    assert lifecycle.next_billing_date == {'pause': date(2026, 12, 1), 'cancel': None, 'resume': TODAY}[action]


@pytest.mark.parametrize('initial,action', [
    ('suspended', 'pause'), ('cancelled', 'pause'), ('cancelled', 'cancel'),
    ('active', 'resume'), ('pending', 'resume'), ('cancelled', 'resume'),
])
def test_invalid_transition_matrix(lifecycle, obligation, admin_user, initial, action):
    HostingSubscription.objects.filter(pk=lifecycle.pk).update(status=initial)
    before = list(Payment.objects.filter(subscription=lifecycle).values())
    preview = assert_no_writes(plan_change, lifecycle, action)

    with pytest.raises(SubscriptionLifecycleError) as caught:
        apply_change(lifecycle.pk, action, TODAY, 'Transición solicitada', preview['impact_hash'], admin_user)

    assert 'invalid_transition' in {row['code'] for row in preview['blockers']}
    assert caught.value.detail['code'] == 'subscription_change_blocked'
    assert list(Payment.objects.filter(subscription=lifecycle).values()) == before
    assert not BillingContextEvent.objects.exists()


@pytest.mark.parametrize('fault', ['retained', 'no_project', 'archived', 'future', 'in_flight', 'failure_suspension'])
def test_blocker_refuses_financial_writes(lifecycle, obligation, admin_user, fault):
    context = ProjectRetentionContext.objects.create(
        client=lifecycle.project.client, original_project_id=99999, project_name='Anterior', created_by=admin_user,
    )
    updates = {
        'retained': {'retention_context': context, 'project': None},
        'no_project': {'project': None}, 'archived': {'is_archived': True},
        'future': {}, 'in_flight': {}, 'failure_suspension': {'status': 'suspended'},
    }[fault]
    HostingSubscription.objects.filter(pk=lifecycle.pk).update(**updates)
    payment_updates = {'in_flight': {'status': 'processing', 'wompi_transaction_id': 'txn-live'}}.get(fault, {})
    Payment.objects.filter(pk=obligation.pk).update(**payment_updates)
    action = {'failure_suspension': 'resume'}.get(fault, 'cancel')
    effective = {'future': date(2026, 10, 10)}.get(fault, TODAY)
    codes = {'retained': 'subscription_retained', 'no_project': 'subscription_without_project',
             'archived': 'subscription_archived', 'future': 'effective_date_in_future',
             'in_flight': 'payment_in_flight', 'failure_suspension': 'suspended_by_payment_failure'}
    before = list(Payment.objects.values())

    preview = assert_no_writes(plan_change, lifecycle, action, effective)

    assert codes[fault] in {row['code'] for row in preview['blockers']}
    with pytest.raises(SubscriptionLifecycleError) as caught:
        apply_change(lifecycle.pk, action, effective, 'Cambio bloqueado', preview['impact_hash'], admin_user)
    assert {row['code'] for row in caught.value.detail['blockers']} == {row['code'] for row in preview['blockers']}
    assert list(Payment.objects.values()) == before
    assert not BillingContextEvent.objects.exists()


@pytest.mark.parametrize('effect', ['suspended', 'completed', 'decommissioned'])
def test_resume_refuses_project_that_blocks_billing(lifecycle, obligation, admin_user, effect):
    from content.models import DocumentState, DocumentStateGroup
    enact(lifecycle, admin_user, 'pause')
    state = DocumentState.objects.filter(catalog=DocumentStateGroup.Catalog.PROJECTS, operational_effect=effect).first()
    lifecycle.project.current_state = state
    lifecycle.project.save(update_fields=['current_state'])

    preview = plan_change(lifecycle, 'resume')

    assert preview['can_apply'] is False
    assert preview['blockers'] == [{'code': 'project_blocks_billing', 'message': 'El estado del proyecto impide reanudar la facturación.',
                                   'resource_type': 'project', 'resource_id': lifecycle.project_id}]
    with pytest.raises(SubscriptionLifecycleError):
        apply_change(lifecycle.pk, 'resume', TODAY, 'Intento de reanudación', preview['impact_hash'], admin_user)
    obligation.refresh_from_db()
    assert obligation.status == Payment.STATUS_VOIDED


def test_cancel_audits_future_voids_without_touching_accounting(lifecycle, obligation, admin_user, hosting_record, account):
    hosting = ProjectHosting.objects.create(project=lifecycle.project, subscription=lifecycle)
    source = ProjectHostingAccountingSource.objects.create(hosting=hosting, hosting_record=hosting_record)
    hosting.operational_accounting_source = source
    hosting.save()
    CollectionAccountContext.objects.create(document=account, nature='hosting', hosting=hosting)
    cycle = HostingCycle.objects.create(hosting_record=hosting_record, modality='semiannual', amount=4800, paid_at=date(2026, 6, 11))
    income = IncomeRecord.objects.create(project=lifecycle.project, client=lifecycle.project.client.profile,
                                         concept='Ingreso futuro', kind='expected', period_date=date(2026, 12, 1), total_amount=4800)
    paid = Payment.objects.create(subscription=lifecycle, amount=4800, status='paid', paid_at='2026-06-11T12:00:00Z',
                                  due_date=date(2026, 6, 1), billing_period_start=date(2026, 6, 1), billing_period_end=date(2026, 11, 30))
    PaymentHistory.objects.create(payment=paid, from_status='pending', to_status='paid')
    due = Payment.objects.create(subscription=lifecycle, amount=100, due_date=TODAY, billing_period_start=TODAY,
                                 billing_period_end=TODAY, status='overdue')
    obligation.wompi_payment_link_id = 'published-link'
    obligation.save()
    untouched = (list(Payment.objects.filter(pk=paid.pk).values()), list(HostingCycle.objects.values()),
                 list(IncomeRecord.objects.values()), list(CollectionAccountContext.objects.values()))
    preview = assert_no_writes(plan_change, lifecycle, 'cancel')

    result = apply_change(lifecycle.pk, 'cancel', TODAY, 'Cancelar PRUEBA', preview['impact_hash'], admin_user)

    obligation.refresh_from_db()
    due.refresh_from_db()
    assert (obligation.status, obligation.is_archived, obligation.archived_at.date()) == ('voided', True, TODAY)
    assert due.status == 'overdue' and due.is_archived is False
    assert {row['code'] for row in preview['warnings']} == {'payment_link_outstanding', 'due_payments_remain_collectible', 'accounting_records_untouched'}
    assert preview['kept_history']['paid_payments'][0]['id'] == paid.pk
    assert preview['kept_history']['payment_history_count'] == 1
    assert preview['kept_history']['hosting_cycles'][0]['id'] == cycle.pk
    assert preview['kept_history']['collection_accounts'][0]['id'] == account.pk
    assert income.pk in preview['warnings'][-1]['future_income_ids']
    assert untouched == (list(Payment.objects.filter(pk=paid.pk).values()), list(HostingCycle.objects.values()),
                         list(IncomeRecord.objects.values()), list(CollectionAccountContext.objects.values()))
    event = BillingContextEvent.objects.get(pk=result['event_id'])
    assert (event.actor, event.operation, event.reason) == (admin_user, 'hosting_subscription.cancel', 'Cancelar PRUEBA')
    assert event.before['subscription'] == {'status': 'active', 'next_billing_date': '2026-12-01'}
    assert event.after == {'subscription_id': lifecycle.pk, 'subscription': {'status': 'cancelled', 'next_billing_date': None},
                           'voided_payment_ids': [obligation.pk], 'restored_payment_ids': [],
                           'generated_payment_id': None, 'effective_date': '2026-10-09'}
    history = obligation.history.get()
    assert (history.from_status, history.to_status, history.source) == ('pending', 'voided', 'manual')
    assert history.metadata == {'event_id': event.pk, 'action': 'cancel'}


@pytest.mark.parametrize('old_status', ['pending', 'failed', 'overdue', 'processing'])
def test_short_pause_restores_only_its_future_charge(lifecycle, obligation, admin_user, old_status):
    obligation.status = old_status
    obligation.save()
    unrelated = Payment.objects.create(subscription=lifecycle, amount=800, due_date=date(2026, 12, 1),
                                       billing_period_start=date(2026, 12, 1), billing_period_end=date(2026, 12, 31),
                                       status='voided', is_archived=True)
    pause = enact(lifecycle, admin_user, 'pause')
    assert 'project_state_suggestion' in {row['code'] for row in pause['warnings']}

    with freeze_time('2026-10-10'):
        result = enact(lifecycle, admin_user, 'resume', date(2026, 10, 10))

    obligation.refresh_from_db()
    unrelated.refresh_from_db()
    lifecycle.refresh_from_db()
    assert (obligation.status, obligation.is_archived, obligation.archived_at) == (old_status, False, None)
    assert unrelated.status == 'voided' and unrelated.is_archived
    assert lifecycle.status == 'active' and lifecycle.next_billing_date == date(2026, 12, 1)
    assert result['generated_payment'] is None
    assert [row['id'] for row in result['restored_payments']] == [obligation.pk]
    assert obligation.history.first().metadata == {'event_id': result['event_id'], 'action': 'resume'}


def test_resume_after_due_date_opens_cycle_without_paused_time(lifecycle, obligation, admin_user):
    enact(lifecycle, admin_user, 'pause')

    with freeze_time('2026-12-05'):
        result = enact(lifecycle, admin_user, 'resume', date(2026, 12, 5))

    lifecycle.refresh_from_db()
    obligation.refresh_from_db()
    event = BillingContextEvent.objects.get(pk=result['event_id'])
    generated = Payment.objects.get(pk=event.after['generated_payment_id'])
    assert obligation.status == 'voided' and obligation.is_archived
    assert result['restored_payments'] == []
    assert (generated.billing_period_start, generated.billing_period_end, generated.due_date) == (
        date(2026, 12, 5), date(2027, 6, 4), date(2026, 12, 5),
    )
    assert generated.amount == 4800 and generated.status == 'pending'
    assert lifecycle.next_billing_date == date(2026, 12, 5)
    assert generated.history.get().metadata == {'event_id': event.pk, 'action': 'resume'}


def test_stale_preview_preserves_current_obligation(lifecycle, obligation, admin_user):
    preview = plan_change(lifecycle, 'cancel')
    Payment.objects.filter(pk=obligation.pk).update(amount=4900)

    with pytest.raises(SubscriptionLifecycleError) as caught:
        apply_change(lifecycle.pk, 'cancel', TODAY, 'Cancelar con vista vieja', preview['impact_hash'], admin_user)

    assert caught.value.status_code == 409
    assert caught.value.detail['code'] == 'stale_subscription_preview'
    lifecycle.refresh_from_db()
    obligation.refresh_from_db()
    assert lifecycle.status == 'active' and obligation.amount == 4900 and obligation.status == 'pending'
    assert not BillingContextEvent.objects.exists()


def test_lifecycle_failure_rolls_back_decision(lifecycle, obligation, admin_user, monkeypatch):
    from accounts.services import hosting_subscription_lifecycle
    from django.db import OperationalError
    preview = plan_change(lifecycle, 'cancel')

    def fail_history(*args, **kwargs):
        raise OperationalError('History unavailable')

    monkeypatch.setattr(hosting_subscription_lifecycle, 'record_payment_status_change', fail_history)

    with pytest.raises(OperationalError):
        apply_change(lifecycle.pk, 'cancel', TODAY, 'Cancelar con auditoría', preview['impact_hash'], admin_user)

    lifecycle.refresh_from_db()
    obligation.refresh_from_db()
    assert lifecycle.status == 'active' and obligation.status == 'pending' and not obligation.is_archived
    assert not BillingContextEvent.objects.exists()
