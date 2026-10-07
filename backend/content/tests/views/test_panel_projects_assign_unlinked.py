"""The PA-51 assign flow: a project completing its client's loose records.

Covers the service (idempotent bulk assign with one audit row per record and
the cascade to liquid children), the preview/apply endpoints (the confirmed
plan runs exactly or not at all — 409 on vanished or no-longer-assignable
ids), the backlog counters the module shows, and the MCP ``project_name``
alias that used to be dropped in silence.
"""
from decimal import Decimal

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model

from content.mcp.accounting_tools import _resolve_project_reference
from content.mcp.protocol import ToolError
from content.models import (
    AccountingChangeLog,
    Document,
    DocumentCollectionAccount,
    HostingRecord,
    IncomeRecord,
)
from content.services import accounting_service
from content.services.document_type_utils import (
    get_collection_account_document_type,
)

User = get_user_model()
pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType


def preview_url(project_id):
    return f'/api/projects/{project_id}/unlinked-records/'


def apply_url(project_id):
    return f'/api/projects/{project_id}/assign-unlinked/'


def make_project(profile, name='Vastago', *, status=Project.STATUS_ACTIVE):
    return Project.objects.create(name=name, client=profile.user, status=status)


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


def audit_rows(entity_type, object_id):
    return AccountingChangeLog.objects.filter(
        entity_type=entity_type, object_id=object_id,
    )


class TestBulkAssignProjectService:
    def test_assigns_and_writes_one_audit_row_per_record(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        hosting = make_hosting(profile)
        other = make_hosting(profile)

        updated = accounting_service.bulk_assign_project(
            EntityType.HOSTING, [hosting.pk, other.pk], project, superuser,
        )

        assert {record.pk for record in updated} == {hosting.pk, other.pk}
        hosting.refresh_from_db()
        assert hosting.project_id == project.pk
        assert audit_rows(EntityType.HOSTING, hosting.pk).count() == 1
        assert audit_rows(EntityType.HOSTING, other.pk).count() == 1

    def test_rerunning_the_same_assignment_writes_nothing(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        income = make_income(profile, project=project)

        updated = accounting_service.bulk_assign_project(
            EntityType.INCOME, [income.pk], project, superuser,
        )

        assert updated == []
        assert audit_rows(EntityType.INCOME, income.pk).count() == 0

    def test_cascades_to_the_liquid_children_of_an_expected(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        expected = make_income(profile)
        liquid = make_income(
            profile,
            kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected,
            concept='Vastago - Fase 1 (pago)',
        )

        accounting_service.bulk_assign_project(
            EntityType.INCOME, [expected.pk], project, superuser,
        )

        liquid.refresh_from_db()
        assert liquid.project_id == project.pk
        assert audit_rows(EntityType.INCOME, liquid.pk).count() == 1


class TestUnlinkedRecordsPreview:
    def test_lists_only_the_clients_unlinked_records(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        stranger = make_client_profile()
        project = make_project(profile)
        loose_hosting = make_hosting(profile)
        loose_income = make_income(profile)
        make_hosting(profile, project=project)  # already linked
        make_income(stranger)  # someone else's backlog

        response = admin_client.get(preview_url(project.pk))

        assert response.status_code == 200
        assert [row['id'] for row in response.data['hostings']] == [loose_hosting.pk]
        assert [row['id'] for row in response.data['incomes']] == [loose_income.pk]
        assert response.data['total'] == 2
        assert response.data['client']['profile_id'] == profile.pk

    def test_a_terminal_project_answers_400(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile, status=Project.STATUS_DECOMMISSIONED)

        response = admin_client.get(preview_url(project.pk))

        assert response.status_code == 400
        assert response.data['code'] == 'project_terminal'


class TestAssignUnlinkedRecords:
    def test_assigns_the_confirmed_ids_and_answers_the_annotated_row(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        hosting = make_hosting(profile)
        income = make_income(profile)

        response = admin_client.post(
            apply_url(project.pk),
            {'hosting_ids': [hosting.pk], 'income_ids': [income.pk]},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['assigned_hostings'] == 1
        assert response.data['assigned_incomes'] == 1
        # The moved counts on the annotated row are pinned by
        # TestBacklogCounters; here only the cleared backlog matters.
        row = response.data['project']
        assert row['unlinked_hostings_count'] == 0
        assert row['unlinked_incomes_count'] == 0
        hosting.refresh_from_db()
        income.refresh_from_db()
        assert hosting.project_id == project.pk
        assert income.project_id == project.pk

    def test_the_response_carries_the_updated_rows(
        self, admin_client, make_client_profile,
    ):
        """Full rows, not just counts: an accounting tab open in the SPA
        rebuilds its table from these instead of keeping the stale cell."""
        profile = make_client_profile()
        project = make_project(profile)
        hosting = make_hosting(profile)
        income = make_income(profile)

        response = admin_client.post(
            apply_url(project.pk),
            {'hosting_ids': [hosting.pk], 'income_ids': [income.pk]},
            format='json',
        )

        assert response.status_code == 200
        hosting_row, = response.data['hostings']
        income_row, = response.data['incomes']
        assert (hosting_row['id'], hosting_row['project']) == (
            hosting.pk, project.pk,
        )
        assert hosting_row['project_name'] == project.name
        assert (income_row['id'], income_row['project']) == (
            income.pk, project.pk,
        )
        assert income_row['project_name'] == project.name

    def test_cascaded_liquid_children_travel_in_the_response_rows(
        self, admin_client, make_client_profile,
    ):
        """The cascade rewrites children the operator never picked; without
        them in the payload the panel would keep a stale child row. The
        count stays parents-only — it answers for the confirmed plan."""
        profile = make_client_profile()
        project = make_project(profile)
        expected = make_income(profile)
        liquid = make_income(
            profile,
            kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected,
            concept='Vastago - Fase 1 (pago)',
        )

        response = admin_client.post(
            apply_url(project.pk), {'income_ids': [expected.pk]}, format='json',
        )

        assert response.status_code == 200
        assert response.data['assigned_incomes'] == 1
        assert {row['id'] for row in response.data['incomes']} == {
            expected.pk, liquid.pk,
        }
        assert all(
            row['project'] == project.pk for row in response.data['incomes']
        )
        assert response.data['hostings'] == []

    def test_a_vanished_id_answers_409_and_writes_nothing(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        hosting = make_hosting(profile)

        response = admin_client.post(
            apply_url(project.pk),
            {'hosting_ids': [hosting.pk, 99999]},
            format='json',
        )

        assert response.status_code == 409
        assert response.data['code'] == 'records_not_found'
        hosting.refresh_from_db()
        assert hosting.project_id is None

    def test_an_id_that_stopped_being_unlinked_answers_409_and_writes_nothing(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        rival = make_project(profile, name='Otro proyecto')
        taken = make_income(profile, project=rival)
        loose = make_income(profile, concept='Vastago - Fase 2')

        response = admin_client.post(
            apply_url(project.pk),
            {'income_ids': [taken.pk, loose.pk]},
            format='json',
        )

        assert response.status_code == 409
        assert response.data['code'] == 'records_changed'
        loose.refresh_from_db()
        taken.refresh_from_db()
        assert loose.project_id is None
        assert taken.project_id == rival.pk

    def test_an_empty_plan_answers_400(self, admin_client, make_client_profile):
        profile = make_client_profile()
        project = make_project(profile)

        response = admin_client.post(apply_url(project.pk), {}, format='json')

        assert response.status_code == 400

    def test_a_terminal_project_answers_400(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile, status=Project.STATUS_DECOMMISSIONED)
        hosting = make_hosting(profile)

        response = admin_client.post(
            apply_url(project.pk), {'hosting_ids': [hosting.pk]}, format='json',
        )

        assert response.status_code == 400
        assert response.data['code'] == 'project_terminal'


class TestBacklogCounters:
    def test_row_counts_and_meta_backlog_move_after_assigning(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        hosting = make_hosting(profile)
        make_income(profile)

        before = admin_client.get('/api/projects/')
        row = before.data['results'][0]
        assert row['unlinked_hostings_count'] == 1
        assert row['unlinked_incomes_count'] == 1
        assert before.data['meta']['records_without_project'] == 2

        admin_client.post(
            apply_url(project.pk), {'hosting_ids': [hosting.pk]}, format='json',
        )

        after = admin_client.get('/api/projects/')
        row = after.data['results'][0]
        assert row['unlinked_hostings_count'] == 0
        assert row['unlinked_incomes_count'] == 1
        assert after.data['meta']['records_without_project'] == 1


class TestMcpProjectNameAlias:
    def test_resolves_the_alias_against_the_clients_projects(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)

        data = _resolve_project_reference(
            'hosting', {'client': profile.pk, 'project_name': 'vastago'},
        )

        assert data['project'] == project.pk
        assert 'project_name' not in data

    def test_an_ambiguous_alias_errors_instead_of_guessing(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        make_project(profile)
        make_project(profile)  # same-name duplicates are legal in the module

        with pytest.raises(ToolError, match='más de un proyecto'):
            _resolve_project_reference(
                'income', {'client': profile.pk, 'project_name': 'Vastago'},
            )

    def test_the_alias_without_a_client_errors(self):
        with pytest.raises(ToolError, match='client'):
            _resolve_project_reference('hosting', {'project_name': 'Vastago'})


def make_document(profile, *, title='Contrato F7', archived=False):
    return Document.objects.create(
        title=title, client_user=profile.user, is_archived=archived,
    )


def make_issued_cuenta(profile, *, number='PA-ACME-001'):
    document = Document.objects.create(
        title='CC F7',
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.ISSUED,
        client_user=profile.user,
        public_number=number,
    )
    DocumentCollectionAccount.objects.create(
        document=document, customer_name='Ana Cliente',
        customer_project_name='',
    )
    return document


class TestDocumentsInTheAssignFlow:
    """F7: the offer also covers the client's documents — cuentas included.

    An issued cuenta with no project has NO other write path (the generic
    PATCH refuses non-drafts), so this confirmed-list flow and the
    retroactive command are how its organisational FK gets filled. The
    frozen snapshot and the lifecycle never move.
    """

    def test_preview_lists_the_documents_with_their_identity(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        document = make_document(profile)
        cuenta = make_issued_cuenta(profile)

        response = admin_client.get(preview_url(project.pk))

        assert response.status_code == 200
        rows = {row['id']: row for row in response.data['documents']}
        assert rows[document.pk]['label'] == 'Contrato F7'
        assert rows[cuenta.pk]['number'] == 'PA-ACME-001'
        assert rows[cuenta.pk]['type_label']
        assert response.data['total'] == 2

    def test_apply_fills_both_kinds_and_keeps_the_issued_facts(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        document = make_document(profile)
        cuenta = make_issued_cuenta(profile)

        response = admin_client.post(
            apply_url(project.pk),
            {'document_ids': [document.pk, cuenta.pk]},
            format='json',
        )

        assert response.status_code == 200, response.data
        assert response.data['assigned_documents'] == 2
        document.refresh_from_db()
        cuenta.refresh_from_db()
        assert document.project_id == project.pk
        assert cuenta.project_id == project.pk
        assert cuenta.commercial_status == Document.CommercialStatus.ISSUED
        extension = DocumentCollectionAccount.objects.get(document=cuenta)
        assert extension.customer_project_name == ''
        assert audit_rows(EntityType.DOCUMENT, document.pk).count() == 1
        assert audit_rows(EntityType.COLLECTION_ACCOUNT, cuenta.pk).count() == 1
        row_names = {
            row['id']: row['project_name']
            for row in response.data['documents']
        }
        assert row_names == {document.pk: 'Vastago', cuenta.pk: 'Vastago'}
        assert response.data['project']['unlinked_documents_count'] == 0

    def test_archived_documents_stay_out_of_the_offer(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        make_document(profile, archived=True)

        response = admin_client.get(preview_url(project.pk))

        assert response.data['documents'] == []
        assert response.data['total'] == 0

    def test_a_document_of_another_client_answers_409(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        stranger = make_client_profile(company='Otra SAS')
        project = make_project(profile)
        foreign = make_document(stranger)

        response = admin_client.post(
            apply_url(project.pk),
            {'document_ids': [foreign.pk]},
            format='json',
        )

        assert response.status_code == 409
        assert response.data['code'] == 'records_changed'
        foreign.refresh_from_db()
        assert foreign.project_id is None

    def test_a_documents_only_plan_is_a_valid_plan(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        document = make_document(profile)

        response = admin_client.post(
            apply_url(project.pk),
            {'document_ids': [document.pk]},
            format='json',
        )

        assert response.status_code == 200, response.data
        assert response.data['assigned_hostings'] == 0
        assert response.data['assigned_documents'] == 1


def test_apply_undoes_earlier_steps_when_a_later_one_is_refused(
    admin_client, make_client_profile, monkeypatch,
):
    """Fails if a refused document step leaves the incomes of the same plan assigned."""
    from rest_framework.exceptions import PermissionDenied

    profile = make_client_profile()
    project = make_project(profile)
    income = make_income(profile)
    document = make_document(profile)

    def refuse(*args, **kwargs):
        raise PermissionDenied('Los datos conservados sin proyecto sólo permiten consulta.')

    monkeypatch.setattr(accounting_service, 'assign_project_to_documents', refuse)
    response = admin_client.post(
        apply_url(project.pk),
        {'income_ids': [income.pk], 'document_ids': [document.pk]},
        format='json',
    )

    assert response.status_code == 403
    income.refresh_from_db()
    assert income.project_id is None
    assert not audit_rows(EntityType.INCOME, income.pk).exists()
