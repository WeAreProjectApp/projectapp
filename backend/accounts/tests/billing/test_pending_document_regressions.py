"""Indirect writers, public readers and money flows preserve explicit deferrals."""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import BillingContextEvent, CollectionAccountContext, Project
from accounts.services.billing_context import associate_account
from accounts.services.billing_reassignment import validate_document_reassignment
from accounts.tests.billing.test_pending_document import (  # noqa: F401
    BASE, creation_payload, income, panel, superuser,
)
from content.models import Document, PocketMovement
from content.services.accounting_settlement_service import settle_expected_income
from content.services.collection_account_create_service import create_income_collection_account
from content.services.collection_account_snapshot_service import stored_collection_account_pdf
from content.tests.data_integrity_helpers import scan

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('field', ['pending_by', 'pending_at', 'nature_null', 'nature_invalid', 'unmarked', 'contract'])
def test_database_rejects_invalid_pending_context_updates(account, admin_user, contract, field):
    context = associate_account(account.pk, admin_user, {'document_pending': True}, creating=True)
    changes = {'pending_by': {'pending_by': None}, 'pending_at': {'pending_at': None},
               'nature_null': {'nature': None}, 'nature_invalid': {'nature': 'invalid'},
               'unmarked': {'document_pending': False}, 'contract': {'contract': contract}}[field]
    with pytest.raises(IntegrityError), transaction.atomic():
        CollectionAccountContext.objects.filter(pk=context.pk).update(**changes)
    context.refresh_from_db()
    assert context.document_pending is True
    assert context.pending_by_id == admin_user.pk
    assert context.pending_at is not None
    assert context.contract_id is None


def test_metadata_validation_preserves_pending_decision(account, admin_user):
    context = associate_account(account.pk, admin_user, {'document_pending': True}, creating=True)
    decision = (context.version, context.pending_by_id, context.pending_at)
    with transaction.atomic():
        validate_document_reassignment(account, changes={'notes': 'Documento solicitado.'}, lock=True)
    context.refresh_from_db()
    assert (context.version, context.pending_by_id, context.pending_at) == decision
    assert BillingContextEvent.objects.filter(document=account).count() == 1


def test_pending_reassignment_still_rejects_different_owner_and_detachment(account, admin_user):
    associate_account(account.pk, admin_user, {'document_pending': True}, creating=True)
    other = Project.objects.create(name='Proyecto de otro titular', client=admin_user)
    with pytest.raises(ValidationError, match='mismo cliente'):
        validate_document_reassignment(account, changes={'project': other})
    with pytest.raises(ValidationError, match='desvincular'):
        validate_document_reassignment(account, changes={'project': None})
    assert CollectionAccountContext.objects.get(document=account).document_pending is True


def test_client_readers_omit_private_deferral_metadata(account, admin_user, client_user):
    associate_account(account.pk, admin_user, {'document_pending': True}, creating=True)
    client = APIClient()
    client.force_authenticate(client_user)
    listing = client.get('/api/accounts/collection-accounts/').data
    detail = client.get(f'/api/accounts/collection-accounts/{account.pk}/').data
    assert listing[0]['context']['status'] == 'pending'
    assert detail['context']['status'] == 'pending'
    assert {'pending_by', 'pending_at', 'document_pending'}.isdisjoint(listing[0]['context'])
    assert {'pending_by', 'pending_at', 'document_pending'}.isdisjoint(detail['context'])


def test_jwt_creation_without_project_does_not_silently_ignore_pending_flag(panel):
    before = Document.objects.count()
    result = panel.post('/api/accounts/collection-accounts/', {
        'title': 'Cuenta sin proyecto', 'document_pending': True, 'payment_term_type': 'days_after_issue',
    }, format='json')
    assert result.status_code == 400
    assert Document.objects.count() == before


def test_ac8_distinguishes_legacy_missing_context_from_explicit_pending(account, project, admin_user, contract):
    pending = Document.objects.create(title='Pendiente explícito', document_type=account.document_type,
                                      commercial_status='issued', project=project, client_user=project.client)
    complete = Document.objects.create(title='Cuenta completa', document_type=account.document_type,
                                       commercial_status='issued', project=project, client_user=project.client)
    associate_account(pending.pk, admin_user, {'document_pending': True}, creating=True)
    associate_account(complete.pk, admin_user, {'billing_nature': 'contract', 'contract_id': contract.pk,
                                              'expected_version': 0, 'reason': 'Comprobado.'})
    findings = scan('all', rule_ids=['AC8'])
    assert len(findings) == 1
    assert findings[0].tool['arguments']['account_id'] == account.pk


def test_real_settlement_of_a_pending_account_preserves_pdf_and_deferral(project, income, superuser):
    from content.serializers.collection_accounts_panel import CollectionAccountCreateSerializer
    serializer = CollectionAccountCreateSerializer(data=creation_payload(project, income, document_pending=True))
    serializer.is_valid(raise_exception=True)
    document = create_income_collection_account(serializer.validated_data, acting_user=superuser)
    before_pdf = stored_collection_account_pdf(document)
    before_pocket = PocketMovement.objects.count()
    result = settle_expected_income(income, {
        'concept': 'Pago recibido', 'period_date': date(2026, 10, 29),
        'destination': 'partners', 'total_amount': Decimal('150000'),
        'notes': '', 'deductions': [], 'expected_incomes': [],
    }, superuser)
    assert result['liquid'].expected_income_id == income.pk
    assert result['liquid'].total_amount == Decimal('150000')
    assert result['liquid'].gustavo_amount + result['liquid'].carlos_amount == Decimal('150000')
    assert PocketMovement.objects.count() == before_pocket
    document.refresh_from_db()
    assert document.commercial_status == 'paid'
    assert document.billing_context.document_pending is True
    assert stored_collection_account_pdf(document) == before_pdf
