"""Project changes on incomes/hostings propagate to their DRAFT cuentas.

The forward half of the coherence follow-up (F7): a draft inherits the
project once at creation, and issue time reads ``document.project`` for the
frozen ``customer_project_name`` snapshot — so a record whose project is
fixed AFTER the draft was raised used to emit a blank project line forever.
Issued/paid/cancelled cuentas are facts and never move; the single-record
PATCH now also cascades the project to liquid children (parity with bulk).
"""
from decimal import Decimal

import pytest
from accounts.models import Project, ProjectContract
from accounts.services.billing_context import associate_account

from content.models import (
    AccountingChangeLog,
    Document,
    DocumentCollectionAccount,
    HostingRecord,
    IncomeRecord,
    IssuerProfile,
)
from content.services import accounting_service
from content.services.collection_account_service import (
    issue_collection_account,
)
from content.services.document_type_utils import (
    get_collection_account_document_type,
)

pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType


def make_project(profile, name='Vastago'):
    return Project.objects.create(name=name, client=profile.user)


def make_income(profile, **overrides):
    fields = {
        'concept': 'Vastago - Fase 1',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-07-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
        'client': profile,
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def make_hosting(profile, **overrides):
    fields = {
        'client': profile,
        'client_name': 'Ana - Vastago',
        'monthly_value': Decimal('120000.00'),
    }
    fields.update(overrides)
    return HostingRecord.objects.create(**fields)


def make_cuenta(profile, *, status, income=None, hosting=None, title='CC F7'):
    document = Document.objects.create(
        title=title,
        document_type=get_collection_account_document_type(),
        commercial_status=status,
        client_user=profile.user,
        income_record=income,
        hosting_record=hosting,
    )
    DocumentCollectionAccount.objects.create(
        document=document, customer_name='Ana Cliente',
    )
    return document


def cuenta_audit_rows(document_id):
    return AccountingChangeLog.objects.filter(
        entity_type=EntityType.COLLECTION_ACCOUNT, object_id=document_id,
    )


class TestSingleUpdateSyncsDrafts:
    def test_income_project_patch_reaches_its_draft_cuenta(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        income = make_income(profile)
        draft = make_cuenta(
            profile, status=Document.CommercialStatus.DRAFT, income=income,
        )

        response = super_client.patch(
            f'/api/accounting/incomes/{income.pk}/update/',
            {'project': project.pk},
            format='json',
        )

        assert response.status_code == 200, response.data
        draft.refresh_from_db()
        assert draft.project_id == project.pk
        rows = cuenta_audit_rows(draft.pk)
        assert rows.count() == 1
        assert any(
            change['field'] == 'project' for change in rows.first().changes
        )

    def test_hosting_project_patch_reaches_its_draft_cuenta(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        hosting = make_hosting(profile)
        draft = make_cuenta(
            profile, status=Document.CommercialStatus.DRAFT, hosting=hosting,
        )

        response = super_client.patch(
            f'/api/accounting/hostings/{hosting.pk}/update/',
            {'project': project.pk},
            format='json',
        )

        assert response.status_code == 200, response.data
        draft.refresh_from_db()
        assert draft.project_id == project.pk

    def test_income_project_patch_cascades_to_liquid_children(
        self, super_client, make_client_profile,
    ):
        """Parity pin: bulk already cascaded; the single PATCH did not."""
        profile = make_client_profile()
        project = make_project(profile)
        expected = make_income(profile)
        liquid = make_income(
            profile,
            kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected,
            concept='Vastago - Cobro',
        )

        response = super_client.patch(
            f'/api/accounting/incomes/{expected.pk}/update/',
            {'project': project.pk},
            format='json',
        )

        assert response.status_code == 200, response.data
        liquid.refresh_from_db()
        assert liquid.project_id == project.pk


class TestFactsNeverMove:
    @pytest.mark.parametrize('status', [
        Document.CommercialStatus.ISSUED,
        Document.CommercialStatus.PAID,
        Document.CommercialStatus.CANCELLED,
    ])
    def test_non_draft_cuentas_keep_their_project(
        self, superuser, make_client_profile, status,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        income = make_income(profile)
        cuenta = make_cuenta(profile, status=status, income=income)

        accounting_service.bulk_assign_project(
            EntityType.INCOME, [income.pk], project, superuser,
        )

        cuenta.refresh_from_db()
        assert cuenta.project_id is None
        assert cuenta_audit_rows(cuenta.pk).count() == 0


class TestBulkPathsSyncDrafts:
    def test_bulk_assign_project_reaches_the_draft(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        income = make_income(profile)
        draft = make_cuenta(
            profile, status=Document.CommercialStatus.DRAFT, income=income,
        )

        accounting_service.bulk_assign_project(
            EntityType.INCOME, [income.pk], project, superuser,
        )

        draft.refresh_from_db()
        assert draft.project_id == project.pk

    def test_bulk_assign_client_clears_the_foreign_project_on_the_draft(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile()
        other = make_client_profile(company='Otra SAS')
        project = make_project(profile)
        hosting = make_hosting(profile, project=project)
        draft = make_cuenta(
            profile, status=Document.CommercialStatus.DRAFT, hosting=hosting,
        )
        draft.project = project
        draft.save(update_fields=['project'])

        accounting_service.bulk_assign_client(
            EntityType.HOSTING, [hosting.pk], other, superuser,
        )

        hosting.refresh_from_db()
        draft.refresh_from_db()
        assert hosting.project_id is None
        assert draft.project_id is None


class TestIssueAfterSync:
    def test_issue_snapshots_the_synced_project_name(
        self, superuser, make_client_profile,
    ):
        """The end-to-end reason the sync exists: the snapshot the PDF
        prints is written FROM ``document.project`` at issue time."""
        issuer = IssuerProfile.objects.order_by('pk').first()
        profile = make_client_profile()
        project = make_project(profile, name='Vastago Web')
        income = make_income(profile)
        draft = make_cuenta(
            profile, status=Document.CommercialStatus.DRAFT, income=income,
        )

        accounting_service.bulk_assign_project(
            EntityType.INCOME, [income.pk], project, superuser,
        )
        draft.refresh_from_db()
        source_document = Document.objects.create(
            title='Contrato fuente del cobro sincronizado',
            project=project,
            client_user=profile.user,
        )
        contract = ProjectContract.objects.create(
            project=project,
            key='sync-contract',
            title='Contrato sincronizado',
            document=source_document,
        )
        associate_account(draft.pk, superuser, {
            'billing_nature': 'contract',
            'contract_id': contract.pk,
            'expected_version': 0,
            'reason': 'Contexto contractual tras sincronizar el proyecto.',
        })
        issue_collection_account(draft, issuer=issuer, acting_user=superuser)

        extension = DocumentCollectionAccount.objects.get(document=draft)
        assert extension.customer_project_name == 'Vastago Web'
