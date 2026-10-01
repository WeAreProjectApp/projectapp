"""Actual project writers preserve financial ownership and amendment parents."""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from accounts.admin import ProjectAdmin
from accounts.forms_billing import BillingProjectAdminConflict, BillingProjectAdminForm
from accounts.models import (
    CollectionAccountContext, ContractAmendment, DeliveryWorkspace,
    Project, ProjectContract, ProjectHosting, UserProfile,
)
from accounts.services.billing_context import associate_account
from content.admin import admin_site
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.delivery_tools import DELIVERY_TOOLS
from content.mcp.principal import service_actor_for_connector
from content.mcp.protocol import handle_message
from content.mcp.registry import normalize_tools
from content.models import AccountingChangeLog, Document, EntityHistory, EntityRevision, McpConnector
from content.services.project_service import MODE_DETACH, MODE_MOVE, change_client_apply

pytestmark = pytest.mark.django_db


@pytest.fixture
def new_client():
    user = get_user_model().objects.create_user(username='billing-destination@example.test')
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    return user


@pytest.fixture
def second_contract(project):
    document = Document.objects.create(title='Contrato B', project=project, client_user=project.client)
    return ProjectContract.objects.create(project=project, key='contract-b', title='Contrato B', document=document)


@pytest.fixture
def amendment(contract):
    return ContractAmendment.objects.create(
        contract=contract, key='amendment-a', title='Otrosí A', document=contract.document,
    )


def _bind(account, contract, admin_user, amendment=None):
    associate_account(account.pk, admin_user, {
        'billing_nature': 'contract', 'contract_id': contract.pk,
        'amendment_id': amendment.pk if amendment else None,
        'expected_version': 0, 'reason': 'Contrato confirmado para esta cuenta.',
    })


@pytest.mark.parametrize('mode', [MODE_MOVE, MODE_DETACH])
def test_project_transfer_rejects_issued_account_without_partial_history(
    project, account, new_client, admin_user, mode,
):
    before = (EntityHistory.objects.count(), EntityRevision.objects.count(), AccountingChangeLog.objects.count())

    with pytest.raises(ValidationError, match='historia financiera'):
        change_client_apply(project, new_client.profile, mode, admin_user)

    project.refresh_from_db()
    account.refresh_from_db()
    assert project.client_id == account.client_user_id
    assert account.project_id == project.pk
    assert (EntityHistory.objects.count(), EntityRevision.objects.count(), AccountingChangeLog.objects.count()) == before


def test_project_transfer_rejects_canonical_hosting(project, new_client, admin_user):
    hosting = ProjectHosting.objects.create(project=project)
    old_client_id = project.client_id

    with pytest.raises(ValidationError, match='historia financiera'):
        change_client_apply(project, new_client.profile, MODE_MOVE, admin_user)

    project.refresh_from_db()
    assert project.client_id == old_client_id
    assert ProjectHosting.objects.get(pk=hosting.pk).project_id == project.pk


def test_project_transfer_allows_an_empty_project(project, new_client, admin_user):
    change_client_apply(project, new_client.profile, MODE_MOVE, admin_user)

    project.refresh_from_db()
    assert project.client_id == new_client.pk


def test_admin_project_form_rejects_a_financial_owner_change(project, account, new_client):
    form = BillingProjectAdminForm(instance=project, data={
        'name': project.name, 'client': new_client.pk, 'status': project.status,
        'progress': project.progress, 'payment_milestones': '[]', 'hosting_tiers': '[]',
    })

    valid = form.is_valid()

    assert valid is False
    assert 'historia financiera' in str(form.errors['client'])
    project.refresh_from_db()
    assert project.client_id == account.client_user_id


def test_admin_save_cannot_bypass_financial_owner_validation(project, account, new_client):
    project.client = new_client
    administrator = ProjectAdmin(Project, admin_site)

    with pytest.raises(BillingProjectAdminConflict, match='historia financiera'):
        administrator.save_model(RequestFactory().post('/admin/'), project, None, change=True)

    project.refresh_from_db()
    assert project.client_id == account.client_user_id


def test_amendment_reparent_rejects_associated_accounts(
    api_client, admin_headers, project, contract, amendment, second_contract, account, admin_user,
):
    """El puente financiero rechaza la modificación antes de avanzar la versión del espacio."""
    _bind(account, contract, admin_user, amendment)

    response = api_client.patch(
        f'/api/accounts/projects/{project.pk}/delivery/amendments/{amendment.pk}/',
        {'expected_version': 0, 'contract_id': second_contract.pk}, format='json', **admin_headers,
    )

    amendment.refresh_from_db()
    assert response.status_code == 400
    assert amendment.contract_id == contract.pk
    assert CollectionAccountContext.objects.get(document=account).amendment_id == amendment.pk
    assert not DeliveryWorkspace.objects.filter(project=project).exists()


def test_unsigned_amendment_can_reparent_without_accounts(
    api_client, admin_headers, project, amendment, second_contract,
):
    response = api_client.patch(
        f'/api/accounts/projects/{project.pk}/delivery/amendments/{amendment.pk}/',
        {'expected_version': 0, 'contract_id': second_contract.pk}, format='json', **admin_headers,
    )

    amendment.refresh_from_db()
    assert response.status_code == 200, response.data
    assert amendment.contract_id == second_contract.pk
    assert DeliveryWorkspace.objects.get(project=project).version == 1


def test_contract_rest_rejects_a_project_field(api_client, admin_headers, project, contract, new_client):
    other = Project.objects.create(name='Otro proyecto', client=new_client)

    response = api_client.patch(
        f'/api/accounts/projects/{project.pk}/delivery/contracts/{contract.pk}/',
        {'expected_version': 0, 'project_id': other.pk}, format='json', **admin_headers,
    )

    contract.refresh_from_db()
    assert response.status_code == 400
    assert contract.project_id == project.pk
    assert not DeliveryWorkspace.objects.filter(project=project).exists()


def test_contract_rest_cannot_address_a_node_from_another_project(
    api_client, admin_headers, contract, new_client,
):
    other = Project.objects.create(name='Otro proyecto', client=new_client)

    response = api_client.patch(
        f'/api/accounts/projects/{other.pk}/delivery/contracts/{contract.pk}/',
        {'expected_version': 0, 'title': 'Identidad ajena'}, format='json', **admin_headers,
    )

    contract.refresh_from_db()
    assert response.status_code == 404
    assert contract.title == 'Contrato A'
    assert not DeliveryWorkspace.objects.filter(project=other).exists()


def test_contract_mcp_rejects_a_project_field(project, contract, new_client):
    """El transporte MCP conserva la misma identidad de proyecto inmutable que REST."""
    connector = McpConnector.objects.create(slug='billing-transfer-test', name='Prueba de traslado', is_active=True)
    connector.generate_token()
    actor = service_actor_for_connector(connector)
    context = McpExecutionContext(
        connector=connector, credential=connector.credentials.get(label='Default'),
        request_id='billing-transfer', actor=actor, request=SimpleNamespace(),
    )
    other = Project.objects.create(name='Otro proyecto', client=new_client)

    with use_mcp_context(context):
        _, response = handle_message({
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'update_delivery_contract', 'arguments': {
                'project_id': project.pk, 'node_id': contract.pk,
                'expected_version': 0, 'data': {'project_id': other.pk},
            }},
        }, normalize_tools(DELIVERY_TOOLS, 'projects'), context=context)

    contract.refresh_from_db()
    assert response['result']['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert contract.project_id == project.pk
    assert not DeliveryWorkspace.objects.filter(project=project).exists()
