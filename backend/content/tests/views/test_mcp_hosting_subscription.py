"""The real PRUEBA cancellation is confirmed and preserves settled money."""

from copy import deepcopy
from datetime import date

import pytest
from accounts.models import (
    BillingContextEvent,
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    UserProfile,
)
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from content.mcp.principal import service_actor_for_connector
from content.mcp.protocol import ToolError
from content.models import McpActionIntent, McpConnector, McpCredential
from content.tests.mcp_parity import PreviewApplyPair, call_tool_inprocess, check_pair
from content.views.mcp_blog import TOOLS_BY_SLUG

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clock():
    with freeze_time('2026-10-09 12:00:00'):
        yield


@pytest.fixture
def hosting_case():
    user = get_user_model().objects.create_user(username='prueba-client', email='prueba@example.test')
    UserProfile.objects.create(user=user, role='client')
    project = Project.objects.create(pk=7, name='PRUEBA', client=user, status='active')
    subscription = HostingSubscription.objects.create(
        pk=3, project=project, plan='semiannual', status='active', start_date=date(2026, 6, 1),
        base_monthly_amount=800, effective_monthly_amount=800, billing_amount=4800,
        next_billing_date=date(2026, 12, 1),
    )
    paid = Payment.objects.create(
        pk=4, subscription=subscription, amount=4800, status='paid',
        due_date=date(2026, 6, 1), billing_period_start=date(2026, 6, 1), billing_period_end=date(2026, 11, 30),
        paid_at='2026-06-11T12:00:00Z',
    )
    PaymentHistory.objects.create(payment=paid, from_status='pending', to_status='paid', source='webhook')
    future = Payment.objects.create(
        pk=5, subscription=subscription, amount=4800, status='pending',
        due_date=date(2026, 12, 1), billing_period_start=date(2026, 12, 1), billing_period_end=date(2027, 5, 31),
    )
    return subscription, paid, future


@pytest.fixture
def credential():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects', 'is_active': True})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return McpCredential.objects.create(
        connector=connector, label='Hosting lifecycle', actor=service_actor_for_connector(connector),
    )


def invoke(credential, name, arguments):
    payload = call_tool_inprocess('projects', name, arguments, credential=credential)
    if 'error' in payload:
        error = payload['error']
        raise ToolError(error['message'], code=error['code'], details=error['details'])
    return payload


def billing_state():
    return {
        'subscription': HostingSubscription.objects.filter(pk=3).values('status', 'next_billing_date').get(),
        'payments': list(Payment.objects.filter(subscription_id=3).order_by('pk').values(
            'id', 'amount', 'status', 'is_archived', 'paid_at',
        )),
        'histories': PaymentHistory.objects.filter(payment__subscription_id=3).count(),
        'events': BillingContextEvent.objects.count(),
        'intents': McpActionIntent.objects.count(),
    }


def cancellation_pair(credential):
    def apply(args, preview):
        confirmation = invoke(credential, 'change_hosting_subscription', {
            **args, 'reason': 'Cancelar PRUEBA por decisión del operador',
            'expected_impact_hash': preview['impact_hash'],
        })
        return invoke(credential, 'confirm_action', {'confirmation_id': confirmation['confirmation_id']})['result']

    def predicted(preview, before):
        state = deepcopy(before)
        state['subscription'] = {'status': 'cancelled', 'next_billing_date': None}
        state['payments'][1].update(status='voided', is_archived=True)
        state['histories'] += 1
        state['events'] += 1
        state['intents'] += 1
        return state

    return PreviewApplyPair(
        'hosting cancellation', lambda args: invoke(credential, 'preview_hosting_subscription_change', args),
        apply, observe=billing_state, predicted=predicted,
    )


def test_confirmed_cancel_preserves_paid_history(hosting_case, credential):
    subscription, paid, future = hosting_case
    original_paid = Payment.objects.filter(pk=paid.pk).values().get()
    original_history = list(paid.history.values())

    preview, result = check_pair(cancellation_pair(credential), {'subscription_id': 3, 'action': 'cancel'})

    assert preview['voided_payments'] == [{
        'id': 5, 'amount': '4800.00', 'due_date': '2026-12-01',
        'billing_period_start': '2026-12-01', 'billing_period_end': '2027-05-31', 'status_before': 'pending',
    }]
    assert [row['id'] for row in preview['kept_history']['paid_payments']] == [4]
    assert result['event_id'] == BillingContextEvent.objects.get(operation='hosting_subscription.cancel').pk
    hosting = invoke(credential, 'get_project_hosting', {'project_id': 7})
    assert hosting['subscription']['id'] == subscription.pk
    assert hosting['subscription']['status'] == 'cancelled' and hosting['subscription']['next_billing_date'] is None
    by_id = {row['id']: row for row in hosting['subscription']['payments']}
    assert by_id[future.pk]['status'] == 'voided' and by_id[future.pk]['is_archived'] is True
    assert by_id[future.pk]['archived_at'] is not None
    assert by_id[paid.pk]['status'] == 'paid' and by_id[paid.pk]['is_archived'] is False
    assert Payment.objects.filter(pk=paid.pk).values().get() == original_paid
    assert list(paid.history.values()) == original_history


def test_in_flight_preview_matches_confirmation_blocker(hosting_case, credential):
    Payment.objects.filter(pk=5).update(status='processing', wompi_transaction_id='processing-transaction')

    preview, result = check_pair(cancellation_pair(credential), {'subscription_id': 3, 'action': 'cancel'})

    assert preview['can_apply'] is False
    assert preview['blockers'][0]['code'] == 'payment_in_flight'
    assert result.code == 'SUBSCRIPTION_CHANGE_BLOCKED'
    assert not McpActionIntent.objects.exists()


def test_change_waits_for_explicit_confirmation(hosting_case, credential):
    preview = invoke(credential, 'preview_hosting_subscription_change', {'subscription_id': 3, 'action': 'cancel'})
    before = billing_state()

    result = invoke(credential, 'change_hosting_subscription', {
        'subscription_id': 3, 'action': 'cancel', 'reason': 'Cancelar con confirmación',
        'expected_impact_hash': preview['impact_hash'],
    })

    assert result['confirmation_required'] is True
    assert result['impact']['voided_payments'] == preview['voided_payments']
    assert billing_state()['payments'] == before['payments']
    assert billing_state()['subscription'] == before['subscription']
    assert not BillingContextEvent.objects.exists()


def test_confirmation_rejects_changed_obligation(hosting_case, credential):
    preview = invoke(credential, 'preview_hosting_subscription_change', {'subscription_id': 3, 'action': 'cancel'})
    pending = invoke(credential, 'change_hosting_subscription', {
        'subscription_id': 3, 'action': 'cancel', 'reason': 'Confirmar impacto', 'expected_impact_hash': preview['impact_hash'],
    })
    Payment.objects.filter(pk=5).update(amount=4900)

    with pytest.raises(ToolError) as caught:
        invoke(credential, 'confirm_action', {'confirmation_id': pending['confirmation_id']})

    assert caught.value.code == 'STALE_VERSION'
    assert HostingSubscription.objects.get(pk=3).status == 'active'
    assert Payment.objects.get(pk=5).status == 'pending'
    assert not BillingContextEvent.objects.exists()


@pytest.mark.parametrize('arguments,code', [
    ({'subscription_id': 3, 'action': 'cancel', 'status': 'cancelled'}, 'unknown_field'),
    ({'subscription_id': True, 'action': 'cancel'}, 'VALIDATION_ERROR'),
    ({'subscription_id': 3, 'action': 'cancel', 'effective_date': 'invalid'}, 'VALIDATION_ERROR'),
])
def test_preview_validates_flat_arguments(hosting_case, credential, arguments, code):
    before = billing_state()

    with pytest.raises(ToolError) as caught:
        invoke(credential, 'preview_hosting_subscription_change', arguments)

    assert caught.value.code == code
    assert billing_state() == before


def test_explicit_allow_list_omits_new_tools(api_client, credential, hosting_case):
    credential.allowed_tools = ['get_project_hosting']
    token = credential.generate_token()
    credential.save(update_fields=['allowed_tools'])

    response = api_client.post(f'/api/mcp/projects/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list',
    }, format='json')

    assert response.status_code == 200
    tools = {tool['name'] for tool in response.data['result']['tools']}
    assert 'get_project_hosting' in tools
    assert {'preview_hosting_subscription_change', 'change_hosting_subscription'}.isdisjoint(tools)
    names = {'preview_hosting_subscription_change', 'change_hosting_subscription'}
    assert names <= {tool['name'] for tool in TOOLS_BY_SLUG['projects']}
    assert names.isdisjoint({tool['name'] for tool in TOOLS_BY_SLUG['documents']})
    with pytest.raises(ToolError) as caught:
        invoke(credential, 'preview_hosting_subscription_change', {'subscription_id': 3, 'action': 'cancel'})
    assert caught.value.code == 'FORBIDDEN'


@pytest.mark.parametrize('field', ['reason', 'expected_impact_hash'])
def test_confirmation_requires_string_arguments(hosting_case, credential, field):
    preview = invoke(credential, 'preview_hosting_subscription_change', {'subscription_id': 3, 'action': 'cancel'})
    arguments = {'subscription_id': 3, 'action': 'cancel', 'reason': 'Cancelar con motivo',
                 'expected_impact_hash': preview['impact_hash'], field: 1234}

    with pytest.raises(ToolError) as caught:
        invoke(credential, 'change_hosting_subscription', arguments)

    assert caught.value.code == 'VALIDATION_ERROR'
    assert not McpActionIntent.objects.exists()
    assert not BillingContextEvent.objects.exists()
    assert Payment.objects.get(pk=5).status == 'pending'
