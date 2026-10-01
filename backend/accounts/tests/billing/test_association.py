import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from accounts.models import CollectionAccountContext, ContractAmendment, Project, ProjectContract, ProjectHosting
from accounts.services.billing_access import BillingConflict
from accounts.services.billing_context import associate_account
from content.models import Document

pytestmark = pytest.mark.django_db


def payload(contract, **kwargs):
    return {'billing_nature': 'contract', 'contract_id': contract.pk, 'expected_version': 0,
            'reason': 'Asociación histórica explícita', **kwargs}


def test_historical_association_preserves_financial_snapshot(account, contract, admin_user):
    before = (account.total, account.public_number, account.collection_account.customer_project_name)
    associate_account(account.pk, admin_user, payload(contract))
    account.refresh_from_db()
    assert (account.total, account.public_number, account.collection_account.customer_project_name) == before
    assert account.billing_context.contract_id == contract.pk
    assert account.billing_context_events.get().actor_id == admin_user.pk


def test_many_accounts_can_belong_to_same_contract(account, contract, admin_user):
    other = Document.objects.create(project=account.project, client_user=account.client_user,
                                    document_type=account.document_type, title='Otro cobro')
    associate_account(account.pk, admin_user, payload(contract))
    associate_account(other.pk, admin_user, payload(contract))
    assert contract.collection_contexts.count() == 2


def test_other_contract_amendment_is_rejected(account, contract, project, admin_user):
    source = Document.objects.create(title='Contrato B')
    second = ProjectContract.objects.create(project=project, key='b', title='B', document=source)
    amendment = ContractAmendment.objects.create(contract=second, key='b1', title='B1', document=source)
    with pytest.raises(ValidationError, match='otrosí'):
        associate_account(account.pk, admin_user, payload(contract, amendment_id=amendment.pk))
    assert not CollectionAccountContext.objects.filter(document=account).exists()


def test_same_contract_amendment_is_associated(account, contract, admin_user):
    amendment = ContractAmendment.objects.create(contract=contract, key='a1', title='A1', document=contract.document)
    result = associate_account(account.pk, admin_user, payload(contract, amendment_id=amendment.pk))
    assert result.amendment_id == amendment.pk


def test_other_project_contract_is_rejected(account, contract, client_user, admin_user):
    other = Project.objects.create(name='Otro', client=client_user)
    contract.project = other
    contract.save()
    with pytest.raises(ValidationError, match='contrato del proyecto'):
        associate_account(account.pk, admin_user, payload(contract))


def test_double_nature_is_rejected(account, contract, admin_user):
    hosting = ProjectHosting.objects.create(project=account.project)
    with pytest.raises(ValidationError, match='naturaleza hosting'):
        associate_account(account.pk, admin_user, payload(contract, project_hosting_id=hosting.pk))


def test_database_rejects_double_nature(account, contract):
    hosting = ProjectHosting.objects.create(project=account.project)
    with pytest.raises(IntegrityError), transaction.atomic():
        CollectionAccountContext.objects.create(document=account, nature='contract', contract=contract, hosting=hosting)


def test_database_limits_project_to_one_hosting(project):
    ProjectHosting.objects.create(project=project)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectHosting.objects.create(project=project)


def test_stale_context_update_returns_conflict(account, contract, admin_user):
    associate_account(account.pk, admin_user, payload(contract))
    with pytest.raises(BillingConflict):
        associate_account(account.pk, admin_user, payload(contract))
    assert account.billing_context.version == 1


def test_client_cannot_associate_account(account, contract, client_user):
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        associate_account(account.pk, client_user, payload(contract))


def test_association_rejects_a_document_without_a_type(project, contract, admin_user):
    document = Document.objects.create(project=project, client_user=project.client, title='Documento general')

    with pytest.raises(ValidationError, match='Cuenta de cobro no encontrada'):
        associate_account(document.pk, admin_user, payload(contract))

    assert not CollectionAccountContext.objects.filter(document=document).exists()
