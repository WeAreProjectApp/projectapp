"""Financial mutations recheck decisions made after an initial resource read."""

import hashlib
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from accounts import views
from accounts.models import BillingContextEvent, HostingSubscription, Payment, Project
from accounts.services.hosting_subscription_lifecycle import (
    PaymentChargeSkipped,
    SubscriptionLifecycleError,
    apply_change,
    plan_change,
)
from content.mcp.principal import service_actor_for_connector
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import call_tool_inprocess
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time

pytestmark = pytest.mark.django_db
TODAY = date(2026, 10, 9)
CARD_PAYLOAD = {
    'card_number': '4111111111111111',
    'exp_month': '12',
    'exp_year': '2030',
    'cvc': '123',
    'card_holder': 'Billing Test Client',
}


@pytest.fixture(autouse=True)
def billing_clock():
    with freeze_time('2026-10-09 12:00:00'):
        yield


@pytest.fixture
def billable_subscription(subscription):
    subscription.next_billing_date = date(2026, 12, 1)
    subscription.wompi_payment_source_id = 'source-race-guard'
    subscription.save(update_fields=['next_billing_date', 'wompi_payment_source_id'])
    return subscription


@pytest.fixture
def open_payment(billable_subscription):
    return Payment.objects.create(
        subscription=billable_subscription,
        amount=billable_subscription.billing_amount,
        due_date=date(2026, 12, 1),
        billing_period_start=date(2026, 12, 1),
        billing_period_end=date(2027, 2, 28),
    )


@pytest.fixture
def projects_credential():
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Projects'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return McpCredential.objects.create(
        connector=connector, label='Billing race guards',
        actor=service_actor_for_connector(connector),
    )


def change_lifecycle(subscription, actor, action):
    preview = plan_change(subscription, action, TODAY)
    return apply_change(
        subscription.pk, action, TODAY, 'Administrative billing decision',
        preview['impact_hash'], actor,
    )


@pytest.mark.parametrize('action,expected_status,expected_date', [
    ('cancel', HostingSubscription.STATUS_CANCELLED, None),
    ('pause', HostingSubscription.STATUS_SUSPENDED, date(2026, 12, 1)),
])
@pytest.mark.parametrize('payload', [{'plan': 'semiannual'}, {'is_archived': True}])
def test_subscription_patch_preserves_lifecycle_after_access_read(
    api_client, admin_user, billable_subscription, open_payment, monkeypatch,
    action, expected_status, expected_date, payload,
):
    access_check = views._get_project_or_403

    def access_then_decide(*args, **kwargs):
        project, error = access_check(*args, **kwargs)
        assert project.hosting_subscription.status == HostingSubscription.STATUS_ACTIVE
        change_lifecycle(billable_subscription, admin_user, action)
        return project, error

    monkeypatch.setattr(views, '_get_project_or_403', access_then_decide)
    api_client.force_authenticate(admin_user)

    response = api_client.patch(
        f'/api/accounts/projects/{billable_subscription.project_id}/subscription/',
        payload, format='json',
    )

    billable_subscription.refresh_from_db()
    open_payment.refresh_from_db()
    assert response.status_code == 200
    assert response.data['status'] == expected_status
    assert billable_subscription.status == expected_status
    assert billable_subscription.next_billing_date == expected_date
    assert response.data['plan'] == payload.get('plan', HostingSubscription.PLAN_QUARTERLY)
    assert billable_subscription.is_archived == payload.get('is_archived', False)
    assert (open_payment.status, open_payment.is_archived) == (Payment.STATUS_VOIDED, True)


@pytest.mark.parametrize('payload', [{}, {'plan': 'quarterly'}, {'is_archived': False}])
def test_subscription_patch_without_changes_performs_no_writes(
    api_client, admin_user, billable_subscription, open_payment, payload,
):
    api_client.force_authenticate(admin_user)
    before = HostingSubscription.objects.filter(pk=billable_subscription.pk).values().get()

    with CaptureQueriesContext(connection) as queries:
        response = api_client.patch(
            f'/api/accounts/projects/{billable_subscription.project_id}/subscription/',
            payload, format='json',
        )

    assert response.status_code == 200
    assert response.data['payments'][0]['id'] == open_payment.pk
    assert HostingSubscription.objects.filter(pk=billable_subscription.pk).values().get() == before
    assert not [
        row['sql'] for row in queries
        if row['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE '))
    ]


def test_pending_plan_patch_realigns_first_open_payment(
    api_client, client_user, billable_subscription, open_payment,
):
    HostingSubscription.objects.filter(pk=billable_subscription.pk).update(
        status=HostingSubscription.STATUS_PENDING,
    )
    api_client.force_authenticate(client_user)

    response = api_client.patch(
        f'/api/accounts/projects/{billable_subscription.project_id}/subscription/',
        {'plan': 'semiannual'}, format='json',
    )

    billable_subscription.refresh_from_db()
    open_payment.refresh_from_db()
    assert response.status_code == 200
    assert billable_subscription.status == HostingSubscription.STATUS_PENDING
    assert billable_subscription.plan == HostingSubscription.PLAN_SEMIANNUAL
    assert billable_subscription.next_billing_date == date(2027, 6, 1)
    assert open_payment.billing_period_end == date(2027, 5, 31)
    assert open_payment.amount == billable_subscription.billing_amount
    assert 'Semestral' in open_payment.description


@pytest.mark.parametrize('initial,target', [(False, True), (True, False)])
def test_subscription_archive_patch_preserves_billing_fields(
    api_client, admin_user, billable_subscription, initial, target,
):
    HostingSubscription.objects.filter(pk=billable_subscription.pk).update(
        is_archived=initial, archived_at='2026-10-08T12:00:00Z' if initial else None,
        updated_at='2026-10-08T12:00:00Z',
    )
    api_client.force_authenticate(admin_user)

    response = api_client.patch(
        f'/api/accounts/projects/{billable_subscription.project_id}/subscription/',
        {'is_archived': target}, format='json',
    )

    billable_subscription.refresh_from_db()
    assert response.status_code == 200
    assert billable_subscription.is_archived is target
    assert bool(billable_subscription.archived_at) is target
    assert billable_subscription.updated_at.date() == TODAY
    assert billable_subscription.status == HostingSubscription.STATUS_ACTIVE
    assert billable_subscription.next_billing_date == date(2026, 12, 1)


@pytest.mark.parametrize('action', ['cancel', 'pause'])
@pytest.mark.parametrize('provider_step,result', [
    ('tokenize_card', {'id': 'token-race-guard'}),
    ('get_acceptance_token', 'acceptance-race-guard'),
])
def test_card_payment_refuses_lifecycle_decision_during_tokenization(
    api_client, client_user, admin_user, billable_subscription, open_payment,
    monkeypatch, action, provider_step, result,
):
    def decide_during_provider_call(*args):
        change_lifecycle(billable_subscription, admin_user, action)
        return result

    monkeypatch.setattr('accounts.services.wompi.tokenize_card', Mock(return_value={'id': 'token-race-guard'}))
    monkeypatch.setattr('accounts.services.wompi.get_acceptance_token', Mock(return_value='acceptance-race-guard'))
    monkeypatch.setattr(f'accounts.services.wompi.{provider_step}', decide_during_provider_call)
    charge = Mock()
    monkeypatch.setattr('accounts.services.wompi.create_card_transaction', charge)
    api_client.force_authenticate(client_user)

    response = api_client.post(
        f'/api/accounts/projects/{billable_subscription.project_id}/payments/{open_payment.pk}/card-pay/',
        CARD_PAYLOAD, format='json',
    )

    open_payment.refresh_from_db()
    assert response.status_code == 400
    assert response.data == {'detail': 'Este pago no está disponible para cobro.'}
    charge.assert_not_called()
    assert (open_payment.status, open_payment.is_archived) == (Payment.STATUS_VOIDED, True)
    assert open_payment.wompi_transaction_id == ''
    assert open_payment.history.get().to_status == Payment.STATUS_VOIDED


@pytest.mark.parametrize('payment_updates,subscription_updates,project_updates', [
    ({'is_archived': True}, {}, {}),
    ({'status': Payment.STATUS_PROCESSING}, {}, {}),
    ({}, {'status': HostingSubscription.STATUS_CANCELLED}, {}),
    ({}, {'is_archived': True}, {}),
    ({}, {}, {'current_state': None, 'state_review_required': True}),
], ids=['archived-payment', 'processing-payment', 'cancelled-subscription', 'archived-subscription', 'project-review'])
def test_card_payment_rechecks_eligibility_after_provider_wait(
    api_client, client_user, billable_subscription, open_payment, monkeypatch,
    payment_updates, subscription_updates, project_updates,
):
    def tokenize_after_changes(*args):
        Payment.objects.filter(pk=open_payment.pk).update(**payment_updates)
        HostingSubscription.objects.filter(pk=billable_subscription.pk).update(**subscription_updates)
        Project.objects.filter(pk=billable_subscription.project_id).update(**project_updates)
        return {'id': 'token-race-guard'}

    monkeypatch.setattr('accounts.services.wompi.tokenize_card', tokenize_after_changes)
    monkeypatch.setattr('accounts.services.wompi.get_acceptance_token', Mock(return_value='acceptance-race-guard'))
    charge = Mock()
    monkeypatch.setattr('accounts.services.wompi.create_card_transaction', charge)
    api_client.force_authenticate(client_user)

    response = api_client.post(
        f'/api/accounts/projects/{billable_subscription.project_id}/payments/{open_payment.pk}/card-pay/',
        CARD_PAYLOAD, format='json',
    )

    open_payment.refresh_from_db()
    assert response.status_code == 400
    assert response.data == {'detail': 'Este pago no está disponible para cobro.'}
    charge.assert_not_called()
    assert open_payment.wompi_transaction_id == ''
    assert not open_payment.history.exists()


def test_card_payment_charges_the_amount_reread_after_tokenization(
    api_client, client_user, billable_subscription, open_payment, monkeypatch, settings,
):
    settings.WOMPI_INTEGRITY_SECRET = 'test-billing-integrity'

    def tokenize_after_amount_change(*args):
        Payment.objects.filter(pk=open_payment.pk).update(amount=Decimal(200000))
        return {'id': 'token-race-guard'}

    def pending_transaction(payment, card_token, acceptance_token, reference, signature):
        expected_signature = hashlib.sha256(
            f'{reference}20000000COPtest-billing-integrity'.encode(),
        ).hexdigest()
        assert signature == expected_signature
        return {
            'id': 'transaction-current-amount', 'status': 'PENDING',
            'amount_in_cents': int(payment.amount * 100), 'currency': 'COP',
            'reference': reference,
        }

    monkeypatch.setattr('accounts.services.wompi.tokenize_card', tokenize_after_amount_change)
    monkeypatch.setattr('accounts.services.wompi.get_acceptance_token', Mock(return_value='acceptance-race-guard'))
    charge = Mock(side_effect=pending_transaction)
    monkeypatch.setattr('accounts.services.wompi.create_card_transaction', charge)
    api_client.force_authenticate(client_user)

    response = api_client.post(
        f'/api/accounts/projects/{billable_subscription.project_id}/payments/{open_payment.pk}/card-pay/',
        CARD_PAYLOAD, format='json',
    )

    open_payment.refresh_from_db()
    assert response.status_code == 200
    assert charge.call_args.args[0].amount == Decimal(200000)
    assert open_payment.wompi_transaction_id == 'transaction-current-amount'
    assert open_payment.status == Payment.STATUS_PROCESSING
    assert open_payment.history.get().to_status == Payment.STATUS_PROCESSING


def test_resume_refuses_project_requiring_state_review(
    admin_user, billable_subscription, open_payment,
):
    change_lifecycle(billable_subscription, admin_user, 'pause')
    Project.objects.filter(pk=billable_subscription.project_id).update(
        current_state=None, state_review_required=True,
    )
    before = (
        HostingSubscription.objects.filter(pk=billable_subscription.pk).values().get(),
        Payment.objects.filter(pk=open_payment.pk).values().get(),
        BillingContextEvent.objects.count(),
    )
    preview = plan_change(billable_subscription, 'resume', TODAY)

    with pytest.raises(SubscriptionLifecycleError) as caught:
        apply_change(
            billable_subscription.pk, 'resume', TODAY, 'Review pending project state',
            preview['impact_hash'], admin_user,
        )

    assert preview['can_apply'] is False
    assert preview['blockers'][0]['code'] == 'project_blocks_billing'
    assert caught.value.detail['blockers'] == preview['blockers']
    assert before == (
        HostingSubscription.objects.filter(pk=billable_subscription.pk).values().get(),
        Payment.objects.filter(pk=open_payment.pk).values().get(),
        BillingContextEvent.objects.count(),
    )


def test_stored_charge_refuses_project_requiring_review_after_cached_read(
    billable_subscription, open_payment, monkeypatch,
):
    assert open_payment.subscription.project.current_state_id is not None
    Project.objects.filter(pk=billable_subscription.project_id).update(
        current_state=None, state_review_required=True,
    )
    charge = Mock()
    monkeypatch.setattr('accounts.services.wompi.charge_with_payment_source', charge)
    before = Payment.objects.filter(pk=open_payment.pk).values().get()

    with pytest.raises(PaymentChargeSkipped):
        views._charge_payment_with_source(open_payment)

    charge.assert_not_called()
    assert Payment.objects.filter(pk=open_payment.pk).values().get() == before
    assert not open_payment.history.exists()


def test_owner_charge_refuses_project_review_after_access_read(
    api_client, client_user, billable_subscription, open_payment, monkeypatch,
):
    access_check = views._get_project_or_403

    def access_then_require_review(*args, **kwargs):
        project, error = access_check(*args, **kwargs)
        Project.objects.filter(pk=project.pk).update(current_state=None, state_review_required=True)
        return project, error

    monkeypatch.setattr(views, '_get_project_or_403', access_then_require_review)
    charge = Mock()
    monkeypatch.setattr('accounts.services.wompi.charge_with_payment_source', charge)
    api_client.force_authenticate(client_user)
    before = Payment.objects.filter(pk=open_payment.pk).values().get()

    response = api_client.post(
        f'/api/accounts/projects/{billable_subscription.project_id}/payments/{open_payment.pk}/charge/',
        {}, format='json',
    )

    assert response.status_code == 400
    assert response.data == {'detail': 'Este pago no está disponible para cobro.'}
    charge.assert_not_called()
    assert Payment.objects.filter(pk=open_payment.pk).values().get() == before
    assert not open_payment.history.exists()


def test_mcp_resume_refuses_project_requiring_state_review(
    admin_user, billable_subscription, open_payment, projects_credential,
):
    change_lifecycle(billable_subscription, admin_user, 'pause')
    Project.objects.filter(pk=billable_subscription.project_id).update(
        current_state=None, state_review_required=True,
    )
    arguments = {'subscription_id': billable_subscription.pk, 'action': 'resume'}
    preview = call_tool_inprocess(
        'projects', 'preview_hosting_subscription_change', arguments,
        credential=projects_credential,
    )

    rejected = call_tool_inprocess(
        'projects', 'change_hosting_subscription',
        {**arguments, 'reason': 'Review pending project state',
         'expected_impact_hash': preview['impact_hash']},
        credential=projects_credential,
    )

    billable_subscription.refresh_from_db()
    open_payment.refresh_from_db()
    assert preview['can_apply'] is False
    assert preview['blockers'][0]['code'] == 'project_blocks_billing'
    assert rejected['error']['code'] == 'SUBSCRIPTION_CHANGE_BLOCKED'
    assert rejected['error']['details']['blockers'] == preview['blockers']
    assert billable_subscription.status == HostingSubscription.STATUS_SUSPENDED
    assert (open_payment.status, open_payment.is_archived) == (Payment.STATUS_VOIDED, True)
    assert BillingContextEvent.objects.count() == 1
