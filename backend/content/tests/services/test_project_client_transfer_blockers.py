"""Client transfer previews preserve the guards' financial and historical rules."""

from datetime import date

import pytest
from accounts.models import (
    BugReport,
    ChangeRequest,
    CollectionAccountContext,
    HostingSubscription,
    Payment,
    Project,
    ProjectHosting,
)
from accounts.services.billing_reassignment import validate_project_billing_reassignment
from accounts.services.delivery_access import DeliveryConflict
from accounts.services.delivery_client_transfer import (
    assert_delivery_client_transfer_safe,
)
from accounts.services.issue_client_transfer import assert_issue_client_transfer_safe
from accounts.services.project_client_transfer import client_transfer_blockers
from accounts.tests.delivery_authoring_helpers import signed_amendment
from accounts.tests.delivery_helpers import build_delivery_context, prepare_prompt
from accounts.tests.test_delivery_client_transfer import (
    create_amendment_signature,
    create_message,
    create_publication,
    create_signature,
    sign_contract_document,
)
from rest_framework.exceptions import ValidationError

from content.models import Document, HostingRecord
from content.services.document_type_utils import get_collection_account_document_type
from content.services.project_service import change_client_preview
from content.tests.mcp_parity import assert_no_writes

pytestmark = pytest.mark.django_db


@pytest.fixture
def transfer_case(make_client_profile):
    context = build_delivery_context()
    context.document.signed_at = None
    context.document.save(update_fields=['signed_at'])
    return context, make_client_profile()


def subscription_history(context):
    subscription = HostingSubscription.objects.create(
        project=context.project, base_monthly_amount=800, effective_monthly_amount=800,
        billing_amount=4800, plan='semiannual', status='active',
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


def project_hosting(context):
    return ProjectHosting.objects.create(project=context.project)


def prompt_context(context):
    prepare_prompt(context)
    return context.project.delivery_prompt_contexts.get()


def hosting_record(context):
    return HostingRecord.objects.create(
        project=context.project, client=context.client.profile,
        client_name='Titular histórico', monthly_value=800,
    )


def issued_account(context):
    return Document.objects.create(
        project=context.project, client_user=context.client, title='Cuenta histórica',
        document_type=get_collection_account_document_type(), commercial_status='cancelled',
    )


def account_context(context):
    document = issued_account(context)
    document.commercial_status = 'draft'
    document.save(update_fields=['commercial_status'])
    return CollectionAccountContext.objects.create(
        document=document, nature='contract', contract=context.contract,
    )


def signed_contract(context):
    sign_contract_document(context)
    return context.contract


def bug_report(context):
    return BugReport.objects.create(
        project=context.project, reported_by=context.admin, title='Bug archivado', is_archived=True,
    )


def change_request(context):
    return ChangeRequest.objects.create(
        project=context.project, created_by=context.admin, title='Solicitud histórica',
    )


BILLING_MESSAGE = 'El proyecto tiene cuentas o hosting con historia financiera; no puede trasladarse a otro cliente.'
DELIVERY_MESSAGE = (
    'Este proyecto conserva entregas, firmas, fuentes o conversaciones del cliente actual. '
    'No puedes transferirlo a otra persona porque expondría esa historia. '
    'Crea un proyecto separado para el nuevo cliente.'
)
ISSUE_MESSAGE = (
    'El proyecto conserva bugs o solicitudes del cliente actual. '
    'Cambiar de cliente expondría esa historia.'
)
BILLING_CASE = (validate_project_billing_reassignment, ValidationError, 400, 'client_change_financial_history', BILLING_MESSAGE, None)
DELIVERY_CASE = (assert_delivery_client_transfer_safe, ValidationError, 400, 'delivery_client_history_frozen', DELIVERY_MESSAGE, 'delivery_client_history_frozen')
ISSUE_CASE = (assert_issue_client_transfer_safe, DeliveryConflict, 409, 'issue_client_transfer_history', ISSUE_MESSAGE, 'issue_client_transfer_history')


def resource_identity(resource):
    return resource.pk if isinstance(resource.pk, int) else str(resource.pk)


@pytest.mark.parametrize('builder,resource_type,guard_contract', [
    (subscription_history, 'hosting_subscription', BILLING_CASE),
    (project_hosting, 'project_hosting', BILLING_CASE),
    (hosting_record, 'hosting_record', BILLING_CASE),
    (issued_account, 'collection_account', BILLING_CASE),
    (account_context, 'collection_account_context', BILLING_CASE),
    (create_publication, 'delivery_publication', DELIVERY_CASE),
    (prompt_context, 'delivery_prompt_context', DELIVERY_CASE),
    (create_signature, 'contract_signature_evidence', DELIVERY_CASE),
    (create_amendment_signature, 'contract_signature_evidence', DELIVERY_CASE),
    (signed_contract, 'project_contract', DELIVERY_CASE),
    (signed_amendment, 'contract_amendment', DELIVERY_CASE),
    (create_message, 'delivery_message', DELIVERY_CASE),
    (bug_report, 'bug_report', ISSUE_CASE),
    (change_request, 'change_request', ISSUE_CASE),
], ids=lambda value: value if isinstance(value, str) else None)
def test_resource_history_preserves_guard_contract(transfer_case, builder, resource_type, guard_contract):
    context, target = transfer_case
    resource = builder(context)
    guard, exception_class, status, blocker_code, message, guard_code = guard_contract

    evaluation = assert_no_writes(client_transfer_blockers, context.project, target.user)
    with pytest.raises(exception_class) as caught:
        assert_no_writes(guard, context.project, target.user)

    assert evaluation['blockers'] == [{
        'code': blocker_code, 'message': message, 'resource_type': resource_type,
        'resource_id': resource_identity(resource),
        'resolution': 'create_new_project',
    }]
    assert evaluation['blocker_counts'][resource_type] == 1
    assert type(caught.value) is exception_class
    assert caught.value.status_code == status
    assert caught.value.detail.get('code') == guard_code
    assert str(caught.value.detail['detail']) == message
    assert caught.value.detail['blockers'] == evaluation['blockers']
    assert Project.objects.get(pk=context.project.pk).client_id == context.client.pk


def test_capped_ticket_history_keeps_exact_totals_after_other_categories(transfer_case):
    context, target = transfer_case
    subscription_history(context)
    create_message(context)
    BugReport.objects.bulk_create([
        BugReport(project=context.project, reported_by=context.admin, title=f'Bug {index}')
        for index in range(105)
    ])

    evaluation = client_transfer_blockers(context.project, target.user)
    with pytest.raises(ValidationError) as caught:
        validate_project_billing_reassignment(context.project, target.user)

    assert [row['resource_type'] for row in evaluation['blockers']] == [
        'hosting_subscription', 'delivery_message', *(['bug_report'] * 100),
    ]
    assert evaluation['blocker_counts']['bug_report'] == 105
    assert caught.value.detail['blockers'] == evaluation['blockers']
    assert caught.value.detail['blocker_counts']['bug_report'] == 105


def test_current_owner_can_keep_a_project_with_financial_history(transfer_case):
    context, _target = transfer_case
    subscription = subscription_history(context)
    context.project.client = _target.user

    evaluation = client_transfer_blockers(context.project, context.client, lock=True)
    validate_project_billing_reassignment(context.project, context.client)
    assert_issue_client_transfer_safe(context.project, context.client)

    assert evaluation['blockers'] == []
    assert sum(evaluation['blocker_counts'].values()) == 0
    assert list(subscription.payments.order_by('pk').values_list('status', flat=True)) == ['paid', 'pending']


def test_delivery_guard_keeps_the_owner_race_conflict(transfer_case):
    context, target = transfer_case
    Project.objects.filter(pk=context.project.pk).update(client=target.user)

    with pytest.raises(DeliveryConflict) as caught:
        assert_delivery_client_transfer_safe(context.project, target.user, actor=context.admin)

    assert caught.value.status_code == 409
    assert caught.value.default_code == 'delivery_conflict'
    assert str(caught.value.detail) == 'El cliente del proyecto cambió. Revisa el propietario actual antes de continuar.'
    assert Project.objects.get(pk=context.project.pk).client_id == target.user_id


def test_payment_identity_changes_the_financial_impact_hash(transfer_case):
    context, target = transfer_case
    subscription = subscription_history(context)
    before = assert_no_writes(change_client_preview, context.project, target)
    payment = Payment.objects.create(
        subscription=subscription, amount=4800, status='pending',
        billing_period_start=date(2027, 6, 1), billing_period_end=date(2027, 11, 30),
        due_date=date(2027, 6, 1),
    )

    after = assert_no_writes(change_client_preview, context.project, target)

    assert after['blockers'] == before['blockers']
    assert after['impact_hash'] != before['impact_hash']
    assert after['hosting_ids'] == before['hosting_ids'] == []
    assert after['income_ids'] == before['income_ids'] == []
    assert after['financial_history']['subscriptions'][0]['payments'][-1] == {
        'id': payment.pk, 'status': 'pending', 'due_date': '2027-06-01',
    }


def test_classifying_a_draft_account_invalidates_the_impact_hash(transfer_case):
    context, target = transfer_case
    document = issued_account(context)
    document.commercial_status = 'draft'
    document.save(update_fields=['commercial_status'])
    before = change_client_preview(context.project, target)
    account = CollectionAccountContext.objects.create(document=document, nature='contract', contract=context.contract)

    after = change_client_preview(context.project, target)

    assert before['can_apply'] is True
    assert after['can_apply'] is False
    assert after['impact_hash'] != before['impact_hash']
    assert after['financial_history']['collection_account_contexts'] == [{
        'id': account.pk, 'document_id': document.pk, 'nature': 'contract',
        'contract_id': context.contract.pk, 'amendment_id': None, 'project_hosting_id': None,
    }]
    assert after['blockers'][0]['resource_type'] == 'collection_account_context'


def test_history_beyond_the_response_cap_invalidates_the_impact_hash(transfer_case):
    context, target = transfer_case
    BugReport.objects.bulk_create([
        BugReport(project=context.project, reported_by=context.admin, title=f'Bug {index}')
        for index in range(105)
    ])
    before = change_client_preview(context.project, target)
    bug_report(context)

    after = change_client_preview(context.project, target)

    assert after['blockers'] == before['blockers']
    assert after['blocker_counts']['bug_report'] == 106
    assert after['impact_hash'] != before['impact_hash']
