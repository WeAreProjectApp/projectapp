"""Financial evidence stays frozen while explicit project context evolves."""
from django.db import connection
from django.test.utils import CaptureQueriesContext
import pytest
from rest_framework.exceptions import ValidationError

from accounts.models import (
    BillingContextEvent, CollectionAccountContext, ContractAmendment,
    Payment, Project, ProjectContract, ProjectHosting,
)
from accounts.serializers_billing_read import BillingAccountDetailSerializer
from accounts.services.billing_context import associate_account
from accounts.services.billing_read import visible_accounts
from accounts.services.billing_reassignment import validate_document_reassignment
from accounts.services.hosting_context import register_new_hosting_origin
from content.models import Document, HostingCycle, HostingRecord
from content.services.collection_account_service import delete_collection_account
from content.services.collection_account_snapshot_service import persist_collection_account_pdf

pytestmark = pytest.mark.django_db


def contract_payload(contract, version=0, **fields):
    return {
        'billing_nature': 'contract', 'contract_id': contract.pk,
        'expected_version': version, 'reason': 'Relación verificada administrativamente', **fields,
    }


def test_reclassification_keeps_the_exact_archived_pdf(api_client, client_headers, account, contract, admin_user):
    """Una reclasificación administrativa conserva los bytes financieros ya emitidos."""
    stored = persist_collection_account_pdf(account)
    before = (account.generated_file.name, account.metadata, account.total, account.public_number,
              account.collection_account.customer_name)

    associate_account(account.pk, admin_user, contract_payload(contract))
    amendment = ContractAmendment.objects.create(contract=contract, key='change-a', title='Cambio A', document=contract.document)
    associate_account(account.pk, admin_user, contract_payload(contract, 1, amendment_id=amendment.pk))

    response = api_client.get(f'/api/accounts/collection-accounts/{account.pk}/pdf/', **client_headers)
    account.refresh_from_db()
    assert response.status_code == 200
    assert response.content == stored.pdf_bytes
    assert (account.generated_file.name, account.metadata, account.total, account.public_number,
            account.collection_account.customer_name) == before


def test_foreign_customer_cannot_download_the_archived_pdf(api_client, client_headers, account, admin_user):
    persist_collection_account_pdf(account)
    account.client_user = admin_user
    account.save(update_fields=['client_user'])

    response = api_client.get(f'/api/accounts/collection-accounts/{account.pk}/pdf/', **client_headers)

    assert response.status_code == 404
    assert response['Content-Type'] != 'application/pdf'


def test_foreign_project_hosting_read_is_not_found(api_client, client_headers, admin_user):
    foreign = Project.objects.create(name='Proyecto privado', client=admin_user)
    ProjectHosting.objects.create(project=foreign)

    response = api_client.get(f'/api/accounts/projects/{foreign.pk}/hosting-context/', **client_headers)

    assert response.status_code == 404
    assert 'accounting_sources' not in response.json()
    assert 'subscription' not in response.json()


def test_new_subscription_bridge_does_not_create_financial_rows(subscription):
    before = (Payment.objects.count(), HostingCycle.objects.count(), HostingRecord.objects.count())

    register_new_hosting_origin(subscription, None, subscription=True)

    assert ProjectHosting.objects.get(project=subscription.project).subscription_id == subscription.pk
    assert (Payment.objects.count(), HostingCycle.objects.count(), HostingRecord.objects.count()) == before


def test_duplicate_accounting_hosting_origin_rolls_back_its_mapping(project, hosting_record, admin_user):
    other = HostingRecord.objects.create(project=project, client=project.client.profile, client_name='Origen nuevo',
                                         monthly_value=50000, payment_per_cycle=150000)

    with pytest.raises(ValidationError, match='históricos'):
        register_new_hosting_origin(other, admin_user)

    assert not ProjectHosting.objects.filter(project=project).exists()
    assert HostingRecord.objects.filter(pk=hosting_record.pk).exists()


def test_historical_hosting_notes_can_be_edited_before_obligation_reconciliation(account, admin_user):
    hosting = ProjectHosting.objects.create(project=account.project)
    associate_account(account.pk, admin_user, {
        'billing_nature': 'hosting', 'project_hosting_id': hosting.pk,
        'expected_version': 0, 'reason': 'Hosting histórico confirmado',
    })

    validate_document_reassignment(account, changes={})

    assert account.billing_context.hosting_id == hosting.pk


def test_associated_account_cannot_be_moved_to_another_project(account, contract, client_user, admin_user):
    associate_account(account.pk, admin_user, contract_payload(contract))
    foreign = Project.objects.create(name='Segundo proyecto', client=client_user)

    with pytest.raises(ValidationError, match='contrato del proyecto'):
        validate_document_reassignment(account, changes={'project': foreign})

    account.refresh_from_db()
    assert account.project_id == contract.project_id


def test_delete_unissued_classified_draft_preserves_context_audit(account, contract, admin_user):
    account.commercial_status = 'draft'
    account.save(update_fields=['commercial_status'])
    associate_account(account.pk, admin_user, contract_payload(contract))
    account_id = account.pk

    delete_collection_account(account, acting_user=admin_user)

    assert not Document.objects.filter(pk=account_id).exists()
    event = BillingContextEvent.objects.get(operation='associate_account')
    assert event.document_id is None
    assert event.after['document_id'] == account_id


def test_two_contracts_in_one_project_remain_distinct_in_customer_filters(api_client, client_headers, account, contract, admin_user):
    source = Document.objects.create(title='Otro contrato', project=account.project, client_user=account.client_user)
    other = ProjectContract.objects.create(project=account.project, key='contract-b', title='Contrato B', document=source)
    second = Document.objects.create(title='Cobro B', project=account.project, client_user=account.client_user,
                                    document_type=account.document_type, commercial_status='issued')
    associate_account(account.pk, admin_user, contract_payload(contract))
    associate_account(second.pk, admin_user, contract_payload(other))

    response = api_client.get(f'/api/accounts/projects/{account.project_id}/collection-accounts/',
                              {'contract_id': other.pk}, **client_headers)

    assert response.status_code == 200
    assert [row['id'] for row in response.json()] == [second.pk]


@pytest.fixture
def many_project_accounts(account, contract, client_user):
    for number in range(12):
        doc = Document.objects.create(title=f'Cuenta {number}', project=account.project, client_user=client_user,
                                      document_type=account.document_type, commercial_status='issued')
        CollectionAccountContext.objects.create(document=doc, nature='contract', contract=contract)


def test_account_projection_uses_bounded_queries(account, many_project_accounts, client_user):

    with CaptureQueriesContext(connection) as queries:
        data = BillingAccountDetailSerializer(visible_accounts(client_user), many=True).data

    assert len(data) == 13
    assert len(queries) <= 4
