import pytest
from accounts.models import Project
from accounts.services.billing_context import associate_account
from content.models import Document

pytestmark = pytest.mark.django_db


def test_platform_hosting_read_does_not_accept_a_panel_session(client_user, project):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_login(client_user)

    response = client.get(f'/api/accounts/projects/{project.pk}/hosting-context/')

    assert response.status_code == 401
    assert 'accounting_sources' not in response.json()


def test_non_project_account_has_no_pending_contract_requirement(api_client, client_headers, account):
    account.project = None
    account.save(update_fields=['project'])

    response = api_client.get(f'/api/accounts/collection-accounts/{account.pk}/', **client_headers)

    assert response.status_code == 200
    assert response.json()['context']['status'] == 'not_applicable'
    assert response.json()['context']['contract'] is None


def test_historical_issued_account_is_visible_as_pending(api_client, client_headers, account):
    response = api_client.get('/api/accounts/collection-accounts/', **client_headers)
    assert response.status_code == 200
    assert response.json()[0]['context']['status'] == 'pending'


def test_client_detail_excludes_internal_financial_data(api_client, client_headers, account):
    response = api_client.get(f'/api/accounts/collection-accounts/{account.pk}/', **client_headers)
    assert response.status_code == 200
    assert 'notes' not in response.json()
    assert 'metadata' not in response.json()
    assert response.json()['collection_account']['customer_project_name'] == 'Marca congelada'


def test_contradictory_customer_document_is_hidden(api_client, client_headers, account, admin_user):
    account.client_user = admin_user
    account.save()
    response = api_client.get(f'/api/accounts/collection-accounts/{account.pk}/', **client_headers)
    assert response.status_code == 404


def test_foreign_project_accounts_are_isolated(api_client, client_headers, account, admin_user):
    other = Project.objects.create(name='Proyecto ajeno', client=admin_user)
    account.project = other
    account.save()
    response = api_client.get('/api/accounts/collection-accounts/', **client_headers)
    assert response.json() == []


def test_client_filters_by_explicit_contract(api_client, client_headers, account, contract, admin_user):
    associate_account(account.pk, admin_user, {'billing_nature': 'contract', 'contract_id': contract.pk,
                                             'expected_version': 0, 'reason': 'Contrato confirmado'})
    response = api_client.get('/api/accounts/collection-accounts/', {'contract_id': contract.pk}, **client_headers)
    assert [row['id'] for row in response.json()] == [account.pk]


def test_new_project_account_requires_context(api_client, admin_headers, project):
    before = Document.objects.count()
    response = api_client.post('/api/accounts/collection-accounts/', {'title': 'Nuevo', 'project_id': project.pk},
                               format='json', **admin_headers)
    assert response.status_code == 400
    assert Document.objects.count() == before


def test_new_project_account_has_contract_relation(api_client, admin_headers, project, contract):
    response = api_client.post('/api/accounts/collection-accounts/', {
        'title': 'Nuevo', 'project_id': project.pk, 'billing_nature': 'contract', 'contract_id': contract.pk,
    }, format='json', **admin_headers)
    assert response.status_code == 201
    assert response.json()['context']['contract']['id'] == contract.pk


def test_legacy_draft_cannot_be_issued_without_context(api_client, admin_headers, account):
    account.commercial_status = 'draft'
    account.save()
    response = api_client.post(f'/api/accounts/collection-accounts/{account.pk}/issue/', **admin_headers)
    assert response.status_code == 400
    account.refresh_from_db()
    assert account.public_number == 'HIST-001'
    assert account.commercial_status == 'draft'
