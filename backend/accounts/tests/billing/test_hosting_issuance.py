"""Explicit periodic obligations prevent a second issued account for one payment."""
from datetime import date

import pytest

from accounts.models import CollectionAccountContext, HostingEvidence, Payment
from accounts.services.hosting_context import reconcile_hosting
from content.models import HostingCycle, HostingRecord, IssuerProfile
from content.services.collection_account_service import CollectionAccountError, issue_collection_account
from content.services.hosting_billing_service import create_hosting_collection_account

pytestmark = pytest.mark.django_db


@pytest.fixture
def mapped_hosting(project, admin_user, hosting_record, subscription):
    reconcile_hosting(project.pk, admin_user, {
        'expected_version': 0, 'reason': 'Suscripción y origen verificados para la emisión.',
        'subscription_id': subscription.pk, 'hosting_record_ids': [hosting_record.pk],
        'operational_record_id': hosting_record.pk,
    })
    return hosting_record


@pytest.fixture
def issuer():
    return IssuerProfile.objects.create(
        name='ProjectApp', legal_name='ProjectApp SAS', identification_number='900123456',
        email='issuer@example.test', public_number_prefix='PA',
    )


def test_same_subscription_obligation_cannot_issue_a_second_account(mapped_hosting, payment, admin_user, issuer):
    first = create_hosting_collection_account(mapped_hosting, acting_user=admin_user, hosting_payment_id=payment.pk)
    issue_collection_account(first, issuer=issuer, acting_user=admin_user)
    second = create_hosting_collection_account(mapped_hosting, acting_user=admin_user, hosting_payment_id=payment.pk)

    with pytest.raises(CollectionAccountError, match='ya tiene una cuenta emitida'):
        issue_collection_account(second, issuer=issuer, acting_user=admin_user)

    second.refresh_from_db()
    assert second.commercial_status == 'draft'
    assert second.public_number == ''
    assert HostingEvidence.objects.get(document=first).group_id == HostingEvidence.objects.get(document=second).group_id
    assert Payment.objects.count() == 1
    assert HostingCycle.objects.count() == 0


def test_different_periodic_obligations_can_issue_multiple_hosting_accounts(mapped_hosting, payment, admin_user, issuer):
    next_payment = Payment.objects.create(
        subscription=payment.subscription, amount=payment.amount, status='pending',
        billing_period_start=date(2026, 4, 1), billing_period_end=date(2026, 6, 30),
        due_date=date(2026, 4, 1),
    )
    first = create_hosting_collection_account(mapped_hosting, acting_user=admin_user, hosting_payment_id=payment.pk)
    second = create_hosting_collection_account(mapped_hosting, acting_user=admin_user, hosting_payment_id=next_payment.pk)

    issue_collection_account(first, issuer=issuer, acting_user=admin_user)
    issue_collection_account(second, issuer=issuer, acting_user=admin_user)

    assert CollectionAccountContext.objects.filter(nature='hosting', document__commercial_status='issued').count() == 2
    assert HostingEvidence.objects.get(document=first).group_id != HostingEvidence.objects.get(document=second).group_id
    assert Payment.objects.count() == 2
    assert HostingCycle.objects.count() == 0


def test_unreconciled_historical_source_blocks_new_hosting_issuance(mapped_hosting, payment, admin_user, issuer):
    document = create_hosting_collection_account(mapped_hosting, acting_user=admin_user, hosting_payment_id=payment.pk)
    manual = HostingRecord.objects.create(
        project=mapped_hosting.project, client=mapped_hosting.client, client_name='Fuente histórica',
        monthly_value=50000, payment_per_cycle=150000,
    )

    with pytest.raises(CollectionAccountError, match='pendientes de asociar'):
        issue_collection_account(document, issuer=issuer, acting_user=admin_user)

    document.refresh_from_db()
    assert document.commercial_status == 'draft'
    assert document.public_number == ''
    assert not hasattr(manual, 'billing_source')
