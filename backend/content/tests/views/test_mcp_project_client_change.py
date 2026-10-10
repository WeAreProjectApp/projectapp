"""Project transfers over MCP share the Panel's blockers, plan and stale checks."""

from datetime import date
from types import SimpleNamespace

import pytest
from accounts.models import (
    BugReport,
    DeliveryMessage,
    HostingSubscription,
    Payment,
    Project,
    ProjectHosting,
)

from content.mcp.principal import service_actor_for_connector
from content.mcp.protocol import ToolError
from content.models import (
    CommunicationThread,
    Document,
    DocumentFolder,
    IncomeRecord,
    McpActionIntent,
    McpConnector,
)
from content.services.document_type_utils import get_collection_account_document_type
from content.tests.mcp_parity import (
    PreviewApplyPair,
    assert_no_writes,
    call_tool_inprocess,
    check_pair,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def transfer_case(make_client_profile):
    owner, target = make_client_profile(), make_client_profile()
    project = Project.objects.create(name='Proyecto transferible', client=owner.user)
    income = IncomeRecord.objects.create(
        project=project, client=owner, kind='expected', concept='Fase original',
        period_date=date(2026, 10, 1), total_amount=100, gustavo_amount=50, carlos_amount=50,
    )
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    connector.generate_token()
    credential = connector.credentials.get(label='Default')
    credential.actor = service_actor_for_connector(connector)
    credential.save(update_fields=['actor', 'updated_at'])
    return SimpleNamespace(
        owner=owner, target=target, project=project, income=income, credential=credential,
        old_thread_id=project.communication_root_thread.pk,
    )


def call(case, name, arguments):
    payload = call_tool_inprocess('projects', name, arguments, credential=case.credential)
    if payload.get('ok') is False:
        error = payload['error']
        raise ToolError(error['message'], code=error['code'], details=error['details'])
    return payload


def preview_args(case):
    return {'project_id': case.project.pk, 'client_profile_id': case.target.pk}


def transfer(case, arguments, preview, mode):
    intent = call(case, 'change_project_client', {
        **arguments, 'mode': mode, 'expected_impact_hash': preview['impact_hash'],
    })
    confirmed = call(case, 'confirm_action', {'confirmation_id': intent['confirmation_id']})
    return confirmed['result']


def subscription_history(case):
    subscription = HostingSubscription.objects.create(
        project=case.project, plan='semiannual', base_monthly_amount=800,
        effective_monthly_amount=800, billing_amount=4800, status='active',
        start_date=date(2026, 6, 1), next_billing_date=date(2026, 12, 1),
    )
    Payment.objects.create(
        subscription=subscription, amount=4800, status='paid',
        billing_period_start=date(2026, 6, 1), billing_period_end=date(2026, 11, 30),
        due_date=date(2026, 6, 1),
    )
    Payment.objects.create(
        subscription=subscription, amount=4800, status='pending',
        billing_period_start=date(2026, 12, 1), billing_period_end=date(2027, 5, 31),
        due_date=date(2026, 12, 1),
    )
    return subscription


def delivery_history(case):
    return DeliveryMessage.objects.create(
        project=case.project, actor=case.owner.user, level='project',
        target_id=case.project.pk, message='Historia pública del cliente', is_internal=False,
    )


def issue_history(case):
    return BugReport.objects.create(
        project=case.project, reported_by=case.owner.user, title='Historia de tickets', is_archived=True,
    )


def observe(case):
    return {
        'owner': Project.objects.get(pk=case.project.pk).client_id,
        'incomes': {row.pk: (row.client_id, row.project_id) for row in IncomeRecord.objects.order_by('pk')},
        'drafts': {row.pk: (row.client_user_id, row.project_id) for row in Document.objects.filter(
            document_type__code='collection_account',
        ).order_by('pk')},
        'folders': dict(DocumentFolder.objects.filter(project=case.project).values_list('pk', 'client_user_id')),
        'old_thread': CommunicationThread.objects.values_list('client_id', 'project_id', 'managed_project_id').get(pk=case.old_thread_id),
    }


def predicted(case, mode, preview, before):
    records = preview['planned'][mode]['records']
    incomes = dict(before['incomes'])
    for pk in records['incomes_move'] + records['liquid_children_move']:
        incomes[pk] = (case.target.pk, incomes[pk][1])
    for pk in records['incomes_detach'] + records['liquid_children_detach']:
        incomes[pk] = (incomes[pk][0], None)
    drafts = dict(before['drafts'])
    for pk in records['draft_accounts_move']:
        drafts[pk] = (case.target.user_id, drafts[pk][1])
    for pk in records['draft_accounts_detach']:
        drafts[pk] = (drafts[pk][0], None)
    return {
        **before, 'owner': case.target.user_id, 'incomes': incomes, 'drafts': drafts,
        'folders': dict.fromkeys(before['folders'], case.target.user_id),
        'old_thread': (case.owner.pk, None, None),
    }


def test_subscription_history_prevents_creating_an_intent(transfer_case):
    case = transfer_case
    subscription = subscription_history(case)
    pair = PreviewApplyPair(
        'blocked subscription transfer', lambda args: call(case, 'preview_project_client_change', args),
        lambda args, preview: assert_no_writes(transfer, case, args, preview, 'move'),
        observe=lambda: observe(case),
    )

    preview, error = check_pair(pair, preview_args(case))

    assert preview['can_apply'] is False
    assert preview['blocker_counts']['hosting_subscription'] == 1
    assert preview['blockers'][0]['resource_id'] == subscription.pk
    assert preview['blockers'][0]['resource_type'] == 'hosting_subscription'
    payments = list(subscription.payments.order_by('pk'))
    assert preview['financial_history']['subscriptions'] == [{
        'id': subscription.pk, 'payments': [
            {'id': payments[0].pk, 'status': 'paid', 'due_date': '2026-06-01'},
            {'id': payments[1].pk, 'status': 'pending', 'due_date': '2026-12-01'},
        ],
    }]
    assert error.code == 'PROJECT_CLIENT_CHANGE_BLOCKED'
    assert error.details['can_apply'] is False
    assert not McpActionIntent.objects.exists()


@pytest.mark.parametrize('mode', ['move', 'detach'])
def test_confirmed_transfer_matches_the_selected_plan(transfer_case, mode):
    case = transfer_case
    IncomeRecord.objects.create(
        project=case.project, client=case.owner, expected_income=case.income, kind='liquid', concept='Pago recibido',
        period_date=date(2026, 10, 1), total_amount=50, gustavo_amount=25, carlos_amount=25,
    )
    blocked_income = IncomeRecord.objects.create(
        project=case.project, client=case.owner, kind='expected', concept='Fase con borrador',
        period_date=date(2026, 10, 1), total_amount=80, gustavo_amount=40, carlos_amount=40,
    )
    Document.objects.create(
        project=case.project, client_user=case.owner.user, income_record=blocked_income,
        title='Borrador con ingreso', document_type=get_collection_account_document_type(), commercial_status='draft',
    )
    Document.objects.create(
        project=case.project, client_user=case.owner.user, title='Borrador independiente',
        document_type=get_collection_account_document_type(), commercial_status='draft',
    )
    pair = PreviewApplyPair(
        f'{mode} client transfer', lambda args: call(case, 'preview_project_client_change', args),
        lambda args, preview: transfer(case, args, preview, mode), observe=lambda: observe(case),
        predicted=lambda preview, before: predicted(case, mode, preview, before),
    )

    preview, result = check_pair(pair, preview_args(case))

    assert preview['can_apply'] is True
    assert result['moved'] == preview['planned'][mode]['moved']
    assert result['detached'] == preview['planned'][mode]['detached']
    assert result['skipped'] == preview['planned'][mode]['skipped']
    assert result['detached_communications'] == preview['planned'][mode]['detached_communications']
    assert result['project']['client']['profile_id'] == case.target.pk
    intent = McpActionIntent.objects.get()
    assert intent.status == McpActionIntent.STATUS_EXECUTED
    assert intent.resource_etags == {'project_client_change': preview['impact_hash']}


def test_stale_hash_prevents_creating_an_intent(transfer_case):
    case = transfer_case
    before = observe(case)

    with pytest.raises(ToolError) as caught:
        assert_no_writes(call, case, 'change_project_client', {
            **preview_args(case), 'mode': 'move', 'expected_impact_hash': '0' * 64,
        })

    assert caught.value.code == 'STALE_VERSION'
    assert observe(case) == before
    assert not McpActionIntent.objects.exists()


@pytest.mark.parametrize('builder,resource_type,guard_code', [
    (subscription_history, 'hosting_subscription', 'VALIDATION_ERROR'),
    (delivery_history, 'delivery_message', 'DELIVERY_CLIENT_HISTORY_FROZEN'),
    (issue_history, 'bug_report', 'ISSUE_CLIENT_TRANSFER_HISTORY'),
])
def test_new_history_rejects_confirmation_with_the_original_guard(transfer_case, builder, resource_type, guard_code):
    case = transfer_case
    preview = call(case, 'preview_project_client_change', preview_args(case))
    intent = call(case, 'change_project_client', {
        **preview_args(case), 'mode': 'move', 'expected_impact_hash': preview['impact_hash'],
    })
    resource = builder(case)
    before = observe(case)

    with pytest.raises(ToolError) as caught:
        call(case, 'confirm_action', {'confirmation_id': intent['confirmation_id']})

    assert caught.value.code == 'PROJECT_CLIENT_CHANGE_BLOCKED'
    assert caught.value.details['guard_code'] == guard_code
    assert caught.value.details['blockers'][0]['resource_type'] == resource_type
    assert caught.value.details['blockers'][0]['resource_id'] == resource.pk
    assert observe(case) == before
    assert McpActionIntent.objects.get(pk=intent['confirmation_id']).status == McpActionIntent.STATUS_PENDING


def test_guard_firing_after_etag_is_wrapped_as_a_domain_blocker(transfer_case, monkeypatch):
    from accounts.services import billing_reassignment

    case = transfer_case
    preview = call(case, 'preview_project_client_change', preview_args(case))
    intent = call(case, 'change_project_client', {
        **preview_args(case), 'mode': 'detach', 'expected_impact_hash': preview['impact_hash'],
    })
    original_guard = billing_reassignment.validate_project_billing_reassignment

    def late_guard(project, client):
        ProjectHosting.objects.create(project=project)
        original_guard(project, client)

    monkeypatch.setattr(billing_reassignment, 'validate_project_billing_reassignment', late_guard)

    with pytest.raises(ToolError) as caught:
        call(case, 'confirm_action', {'confirmation_id': intent['confirmation_id']})

    assert caught.value.code == 'PROJECT_CLIENT_CHANGE_BLOCKED'
    assert caught.value.details['guard_code'] == 'VALIDATION_ERROR'
    assert caught.value.details['blockers'][0]['resource_type'] == 'project_hosting'
    assert Project.objects.get(pk=case.project.pk).client_id == case.owner.user_id
    assert not ProjectHosting.objects.filter(project=case.project).exists()


@pytest.mark.parametrize('tool,extra_arguments', [
    ('preview_project_client_change', {}),
    ('change_project_client', {'mode': 'move', 'expected_impact_hash': '0' * 64}),
])
def test_unknown_argument_never_reaches_the_operation(transfer_case, tool, extra_arguments):
    case = transfer_case

    with pytest.raises(ToolError) as caught:
        assert_no_writes(call, case, tool, {
            **preview_args(case), **extra_arguments, 'clietn_profile_id': case.target.pk,
        })

    assert caught.value.code == 'unknown_field'
    assert caught.value.details['errors'] == [{
        'field': 'clietn_profile_id', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.',
    }]
    assert not McpActionIntent.objects.exists()


def test_new_income_invalidates_the_confirmed_impact(transfer_case):
    case = transfer_case
    preview = call(case, 'preview_project_client_change', preview_args(case))
    intent = call(case, 'change_project_client', {
        **preview_args(case), 'mode': 'move', 'expected_impact_hash': preview['impact_hash'],
    })
    IncomeRecord.objects.create(
        project=case.project, client=case.owner, kind='expected', concept='Fase posterior',
        period_date=date(2026, 10, 1), total_amount=60, gustavo_amount=30, carlos_amount=30,
    )
    before = observe(case)

    with pytest.raises(ToolError) as caught:
        call(case, 'confirm_action', {'confirmation_id': intent['confirmation_id']})

    assert caught.value.code == 'STALE_VERSION'
    assert caught.value.details['expected'] == {'project_client_change': preview['impact_hash']}
    assert observe(case) == before
    assert McpActionIntent.objects.get(pk=intent['confirmation_id']).status == McpActionIntent.STATUS_PENDING
