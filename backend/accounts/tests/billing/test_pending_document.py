"""Explicit deferrals are auditable and never inferred from empty fields."""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models import BillingContextEvent, CollectionAccountContext, Project, ProjectHosting
from accounts.services.billing_access import BillingConflict
from accounts.services.billing_context import associate_account, context_data, validate_account_context
from content.models import Document, IncomeRecord
from content.services.collection_account_service import mark_collection_account_paid
from content.services.collection_account_snapshot_service import stored_collection_account_pdf

pytestmark = pytest.mark.django_db
BASE = '/api/accounting/collection-accounts/'
RADAR = '/api/panel/dashboard/attention/collection_documents_pending/'


@pytest.fixture
def superuser(admin_user):
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()
    return admin_user


@pytest.fixture
def panel(superuser):
    client = APIClient()
    client.force_authenticate(superuser)
    return client


@pytest.fixture
def income(project):
    return IncomeRecord.objects.create(
        project=project, client=project.client.profile, kind='expected', concept='Trabajo acordado',
        period_date=date(2026, 10, 1), total_amount=Decimal('150000'),
        gustavo_amount=Decimal('75000'), carlos_amount=Decimal('75000'),
    )


def creation_payload(project, income, **extra):
    return {'client_profile_id': project.client.profile.pk, 'income_record_id': income.pk,
            'items': [{'quantity': '1', 'unit_price': '150000'}], **extra}


@pytest.mark.parametrize('nature', [None, 'contract', 'hosting'])
def test_defer_records_explicit_decision_and_allows_issuance(account, admin_user, nature):
    before = timezone.now()
    result = associate_account(account.pk, admin_user, {
        'document_pending': True, 'billing_nature': nature,
    }, creating=True)
    data = context_data(result)
    assert data['status'] == 'document_pending'
    assert data['document_pending'] is True
    assert data['nature'] == nature
    assert data['pending_by'] == admin_user.pk
    assert result.pending_at >= before
    assert result.contract_id is result.amendment_id is result.hosting_id is None
    validate_account_context(account)
    event = BillingContextEvent.objects.get(document=account)
    assert event.actor == admin_user
    assert event.operation == 'defer_account_document'
    assert event.after['document_pending'] is True


@pytest.mark.parametrize('key', ['contract_id', 'amendment_id', 'project_hosting_id', 'hosting_payment_id'])
def test_pending_rejects_partial_links_atomically(account, admin_user, key):
    with pytest.raises(ValidationError, match='vínculos parciales'):
        associate_account(account.pk, admin_user, {'document_pending': True, key: 999}, creating=True)
    assert not CollectionAccountContext.objects.filter(document=account).exists()
    assert not BillingContextEvent.objects.filter(document=account).exists()


def test_empty_fields_do_not_infer_a_pending_decision(panel, project, income):
    result = panel.post(BASE + 'create/', creation_payload(project, income), format='json')
    assert result.status_code == 400
    assert not Document.objects.filter(income_record=income).exists()


def test_create_send_pay_and_complete_preserve_pdf(panel, project, income, contract, superuser, mailoutbox):
    response = panel.post(BASE + 'create/', creation_payload(project, income, document_pending=True), format='json')
    assert response.status_code == 201, response.data
    assert response.data['email_sent'] is True
    assert len(mailoutbox) == 1
    document = Document.objects.get(pk=response.data['document']['id'])
    before_pdf = stored_collection_account_pdf(document)
    assert before_pdf.startswith(b'%PDF-')
    mark_collection_account_paid(document, acting_user=superuser)
    pending = document.billing_context
    decision = (pending.pending_by_id, pending.pending_at)
    response = panel.patch(f'/api/admin/billing-context/accounts/{document.pk}/', {
        'billing_nature': 'contract', 'contract_id': contract.pk, 'expected_version': 1,
        'reason': 'Contrato recibido y verificado.',
    }, format='json')
    assert response.status_code == 200, response.data
    assert response.data['document_pending'] is False
    document.refresh_from_db()
    assert document.commercial_status == 'paid'
    assert document.total == Decimal('150000')
    assert stored_collection_account_pdf(document) == before_pdf
    pending.refresh_from_db()
    assert (pending.pending_by_id, pending.pending_at) == decision
    assert pending.version == 2
    assert BillingContextEvent.objects.filter(document=document).count() == 2


def test_pending_without_project_is_rejected(account, admin_user):
    account.project = None
    account.save(update_fields=['project'])
    with pytest.raises(ValidationError, match='solo aplica'):
        associate_account(account.pk, admin_user, {'document_pending': True}, creating=True)
    assert not CollectionAccountContext.objects.filter(document=account).exists()


def test_existing_association_cannot_be_deferred(account, admin_user, contract):
    associate_account(account.pk, admin_user, {'billing_nature': 'contract', 'contract_id': contract.pk,
                                             'expected_version': 0, 'reason': 'Contrato correcto.'})
    with pytest.raises(ValidationError, match='al crear'):
        associate_account(account.pk, admin_user, {'document_pending': True, 'expected_version': 1})
    assert CollectionAccountContext.objects.get(document=account).contract_id == contract.pk


def test_completion_rejects_stale_and_foreign_links(account, admin_user, contract, project):
    associate_account(account.pk, admin_user, {'document_pending': True}, creating=True)
    other = Project.objects.create(name='Otro proyecto', client=project.client)
    contract.project = other
    contract.save()
    with pytest.raises(BillingConflict):
        associate_account(account.pk, admin_user, {'expected_version': 0})
    with pytest.raises(ValidationError, match='contrato del proyecto'):
        associate_account(account.pk, admin_user, {'expected_version': 1, 'reason': 'Revisar contrato.',
                                                 'billing_nature': 'contract', 'contract_id': contract.pk})
    assert CollectionAccountContext.objects.get(document=account).document_pending is True


def test_pending_hosting_cannot_be_completed_without_existing_evidence(account, admin_user, project, subscription):
    associate_account(account.pk, admin_user, {'document_pending': True, 'billing_nature': 'hosting'}, creating=True)
    hosting = ProjectHosting.objects.create(project=project, subscription=subscription)
    with pytest.raises(ValidationError):
        associate_account(account.pk, admin_user, {'expected_version': 1, 'reason': 'Falta la evidencia.',
                                                 'billing_nature': 'hosting', 'project_hosting_id': hosting.pk})
    assert CollectionAccountContext.objects.get(document=account).document_pending is True


def test_database_rejects_unattributed_pending_decision(account):
    with pytest.raises(IntegrityError), transaction.atomic():
        CollectionAccountContext.objects.create(document=account, document_pending=True)


def test_filter_radar_permissions_and_resolution(panel, account, contract, superuser, client_user):
    associate_account(account.pk, superuser, {'document_pending': True}, creating=True)
    listing = panel.get(BASE, {'document_pending': 'true', 'project_id': account.project_id}).data
    assert [row['id'] for row in listing['results']] == [account.pk]
    assert listing['meta']['document_pending_count'] == 1
    assert panel.get(RADAR).data['total'] == 1
    assert panel.get(RADAR).data['results'][0]['destination'] == f'/panel/accounting/collections?account={account.pk}&radar=1'
    staff = APIClient()
    client_user.is_staff = True
    client_user.save()
    staff.force_authenticate(client_user)
    assert staff.get(RADAR).status_code == 403
    assert staff.get(f'{RADAR}{account.pk}/').status_code == 403
    assert staff.get(BASE).status_code == 403
    with pytest.raises(PermissionDenied):
        associate_account(account.pk, client_user, {'expected_version': 1})
    associate_account(account.pk, superuser, {'billing_nature': 'contract', 'contract_id': contract.pk,
                                            'expected_version': 1, 'reason': 'Recibido.'})
    assert panel.get(BASE, {'document_pending': 'true'}).data['meta']['document_pending_count'] == 0
    assert panel.get(RADAR).data['total'] == 0
    assert panel.get(f'{RADAR}{account.pk}/').data['eligible'] is False


@pytest.mark.parametrize('status,archived,included', [('paid', False, True), ('cancelled', False, False), ('issued', True, False)])
def test_radar_keeps_paid_accounts_and_excludes_cancelled_or_archived(panel, account, superuser, status, archived, included):
    associate_account(account.pk, superuser, {'document_pending': True}, creating=True)
    Document.objects.filter(pk=account.pk).update(commercial_status=status, is_archived=archived)
    assert panel.get(RADAR).data['total'] == int(included)
    assert panel.get(BASE, {'document_pending': 'true'}).data['meta']['document_pending_count'] == 1


def test_legacy_context_and_invalid_filter_remain_distinct(panel, account):
    data = panel.get(BASE, {'document_pending': 'true'}).data
    assert data['results'] == []
    assert context_data(None)['document_pending'] is False
    assert context_data(None)['status'] == 'pending'
    assert panel.get(BASE, {'document_pending': 'pending'}).status_code == 400
