"""Development fixtures exercise the real FK graph without live financial writes."""
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.management.commands._billing_seed_helpers import (
    clear_fake_billing, collection_context_for_seed, seed_fake_hosting_billing,
)
from accounts.models import (
    BillingContextEvent, CollectionAccountContext, ContractAmendment,
    HostingEvidence, Payment, Project, ProjectContract, ProjectHosting,
    ProjectHostingAccountingSource,
)
from accounts.services.billing_context import associate_account
from content.fake_data import SeedContext
from content.models import Document, HostingCycle, HostingRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def seed_context(settings):
    settings.FAKE_DATA_ALLOWED = True
    return SeedContext(seed=19, anchor_date=date(2026, 10, 1), namespace='billing-tests')


@pytest.fixture
def fake_hosting(hosting_record, seed_context):
    owner = hosting_record.project.client
    owner.email = 'billing-client@fake.projectapp.test'
    owner.save(update_fields=['email'])
    hosting_record.source_ref = 'fake:accounting'
    hosting_record.save(update_fields=['source_ref'])
    return hosting_record


def test_billing_fixture_helpers_fail_closed(settings, project, admin_user):
    settings.FAKE_DATA_ALLOWED = False
    context = SeedContext(seed=19, anchor_date=date(2026, 10, 1), namespace='billing-tests')

    with pytest.raises(CommandError, match='disabled'):
        collection_context_for_seed(project, 0, context=context, actor=admin_user)

    assert ProjectContract.objects.count() == 0


def test_billing_fixture_contains_multiple_contracts_and_amendments(seed_context, project, account, admin_user):
    payload = collection_context_for_seed(project, 1, context=seed_context, actor=admin_user)

    associate_account(account.pk, admin_user, {**payload, 'expected_version': 0, 'reason': 'Selección ficticia explícita.'})

    context = CollectionAccountContext.objects.get(document=account)
    assert ProjectContract.objects.filter(project=project).count() == 2
    assert ContractAmendment.objects.filter(contract__project=project).count() == 4
    assert context.contract_id == payload['contract_id']
    assert context.amendment.contract_id == context.contract_id


def test_hosting_fixture_does_not_duplicate_financial_sources(fake_hosting, subscription, payment, seed_context, admin_user):
    before = (HostingRecord.objects.count(), Payment.objects.count(), HostingCycle.objects.count())

    seed_fake_hosting_billing(context=seed_context, actor=admin_user)

    assert (HostingRecord.objects.count(), Payment.objects.count(), HostingCycle.objects.count()) == before
    assert ProjectHosting.objects.get(project=fake_hosting.project).subscription_id == subscription.pk
    assert HostingEvidence.objects.get(payment=payment).group.hosting.project_id == fake_hosting.project_id


def test_hosting_fixture_preserves_a_pending_historical_account(fake_hosting, seed_context, admin_user):
    seed_fake_hosting_billing(context=seed_context, actor=admin_user)

    accounts = Document.objects.filter(project=fake_hosting.project, document_type__code='collection_account')
    assert accounts.count() == 3
    assert accounts.filter(billing_context__nature='hosting').count() == 2
    pending = accounts.get(billing_context__isnull=True)
    assert pending.commercial_status == 'issued'
    with pending.generated_file.open('rb') as stored:
        assert stored.read().startswith(b'%PDF-') is True


def test_hosting_fixture_does_not_select_a_manual_accounting_source(fake_hosting, seed_context, admin_user):
    manual = HostingRecord.objects.create(
        project=fake_hosting.project, client=fake_hosting.client, client_name='Origen importado',
        monthly_value=1000, payment_per_cycle=3000, source_ref='manual-import',
    )

    seed_fake_hosting_billing(context=seed_context, actor=admin_user)

    assert not ProjectHosting.objects.filter(project=fake_hosting.project).exists()
    assert HostingRecord.objects.filter(pk=manual.pk).exists()


def test_billing_reset_clears_only_the_selected_project(seed_context, project, account, contract, admin_user):
    associate_account(account.pk, admin_user, {
        'billing_nature': 'contract', 'contract_id': contract.pk,
        'expected_version': 0, 'reason': 'Asociación ficticia explícita.',
    })
    other = Project.objects.create(name='Proyecto conservado', client=project.client)
    preserved = ProjectHosting.objects.create(project=other)

    clear_fake_billing(Project.objects.filter(pk=project.pk))

    assert not CollectionAccountContext.objects.filter(document=account).exists()
    assert not BillingContextEvent.objects.filter(project=project).exists()
    assert ProjectHosting.objects.filter(pk=preserved.pk).exists()
    assert Document.objects.filter(pk=account.pk).exists()


def test_billing_reset_breaks_the_operational_source_protection(fake_hosting, seed_context, admin_user):
    seed_fake_hosting_billing(context=seed_context, actor=admin_user)

    clear_fake_billing(Project.objects.filter(pk=fake_hosting.project_id))

    assert not ProjectHostingAccountingSource.objects.exists()
    assert not ProjectHosting.objects.exists()
    assert not HostingEvidence.objects.exists()
    assert HostingRecord.objects.filter(pk=fake_hosting.pk).exists()


def test_fake_document_command_supplies_required_contract_context(seed_context):
    call_command('create_fake_documents', '--count', '2', '--seed', '19',
                 '--anchor-date', '2026-10-01', stdout=StringIO(), verbosity=0)

    document = Document.objects.get(document_type__code='collection_account')
    assert document.billing_context.nature == 'contract'
    assert document.billing_context.contract.project_id == document.project_id
    assert document.client_user_id == document.project.client_id
