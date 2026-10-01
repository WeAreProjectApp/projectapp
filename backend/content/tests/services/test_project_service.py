"""The change-client cascade: preview buckets, the two apply modes, and the
hard-delete blockers.

The rules pinned here preserve financial history before any client cascade:
projects with issued or classified accounts, or hosting history, stay with
their owner. Projects without that history still move their incomes, drafts,
folders, and liquid children through the established audited flow.
"""
from decimal import Decimal

import pytest
from accounts.models import Project
from rest_framework.exceptions import ValidationError

from content.models import (
    AccountingChangeLog,
    CommunicationThread,
    Document,
    DocumentCollectionAccount,
    DocumentFolder,
    HostingRecord,
    IncomeRecord,
)
from content.services import project_service
from content.services.document_type_utils import (
    get_collection_account_document_type,
)

pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType


def make_project(profile, name='Vastago'):
    return Project.objects.create(name=name, client=profile.user)


def make_hosting(profile, project, **overrides):
    fields = {
        'client': profile,
        'project': project,
        'client_name': 'Ana - Vastago',
        'client_email': 'vieja@example.com',
        'monthly_value': Decimal('120000.00'),
    }
    fields.update(overrides)
    return HostingRecord.objects.create(**fields)


def make_income(profile, project, **overrides):
    fields = {
        'concept': 'Vastago - Fase 1',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-07-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
        'client': profile,
        'project': project,
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def make_cuenta(project, *, status, income=None, title='CC Vastago'):
    document = Document.objects.create(
        title=title,
        document_type=get_collection_account_document_type(),
        commercial_status=status,
        project=project,
        client_user=project.client,
        income_record=income,
    )
    DocumentCollectionAccount.objects.create(
        document=document, customer_name='Cliente Viejo',
    )
    return document


def audit_rows(entity_type, object_id):
    return AccountingChangeLog.objects.filter(
        entity_type=entity_type, object_id=object_id,
    )


class TestPreview:
    def test_buckets_split_movable_blocked_clientless_and_documents(
        self, superuser, make_client_profile,
    ):
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        movable_hosting = make_hosting(old, project)
        movable_income = make_income(old, project)
        blocked_income = make_income(old, project, concept='Con cuenta')
        make_cuenta(
            project, status=Document.CommercialStatus.DRAFT,
            income=blocked_income, title='Draft de ingreso',
        )
        loose_income = make_income(None, project, concept='Sin cliente')
        following_draft = make_cuenta(
            project, status=Document.CommercialStatus.DRAFT,
            title='Draft de hosting',
        )
        issued = make_cuenta(
            project, status=Document.CommercialStatus.ISSUED, title='Emitida',
        )

        preview = project_service.change_client_preview(project, new)

        assert [row['id'] for row in preview['hostings_move']] == [
            movable_hosting.pk,
        ]
        assert [row['id'] for row in preview['incomes_move']] == [
            movable_income.pk,
        ]
        assert [row['id'] for row in preview['incomes_blocked']] == [
            blocked_income.pk,
        ]
        assert [row['id'] for row in preview['clientless']] == [loose_income.pk]
        assert {row['id'] for row in preview['draft_accounts']} >= {
            following_draft.pk,
        }
        assert [row['id'] for row in preview['issued_accounts']] == [issued.pk]
        # The staleness token covers EVERY linked record, bucket-independent.
        assert set(preview['income_ids']) == {
            movable_income.pk, blocked_income.pk, loose_income.pk,
        }
        assert preview['hosting_ids'] == [movable_hosting.pk]

    def test_a_cancelled_cuenta_does_not_block_its_income(
        self, superuser, make_client_profile,
    ):
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        income = make_income(old, project)
        make_cuenta(
            project, status=Document.CommercialStatus.CANCELLED, income=income,
        )

        preview = project_service.change_client_preview(project, new)

        assert [row['id'] for row in preview['incomes_move']] == [income.pk]
        assert preview['incomes_blocked'] == []


class TestApplyMove:
    def test_move_refreshes_linked_income_records(
        self, superuser, make_client_profile,
    ):
        """Falla si mover un proyecto sin historia deja ingresos con el cliente previo."""
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        expected = make_income(old, project)
        liquid = make_income(
            old, project, kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected, concept='Abono',
        )

        project_service.change_client_apply(
            project, new, project_service.MODE_MOVE, superuser,
        )

        project.refresh_from_db()
        expected.refresh_from_db()
        liquid.refresh_from_db()
        assert project.client_id == new.user_id
        assert expected.client_id == new.pk
        # The child follows its parent through the cascade — it is never
        # processed as an independent row, so the count names parents only.
        assert liquid.client_id == new.pk
        assert liquid.project_id == project.pk
        assert expected.project_id == project.pk

    def test_move_synchronizes_managed_folder_tree(
        self, superuser, make_client_profile,
    ):
        """Falla si el cambio de cliente deja la raíz o sus hijos con otro dueño."""
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        root = project.document_root_folder
        folder_ids = [root.id, *root.children.values_list('id', flat=True)]

        result = project_service.change_client_apply(
            project, new, project_service.MODE_MOVE, superuser,
        )

        assert result['moved']['project_folders'] == len(folder_ids)
        assert list(
            DocumentFolder.objects.filter(pk__in=folder_ids)
            .order_by('id')
            .values_list('project_id', 'client_user_id')
        ) == [(project.id, new.user_id)] * len(folder_ids)

    def test_move_audits_changed_income_records(
        self, superuser, make_client_profile,
    ):
        """Falla si mover ingresos permitidos deja de registrar su auditoría."""
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        expected = make_income(old, project)
        liquid = make_income(
            old, project, kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected, concept='Abono',
        )

        project_service.change_client_apply(
            project, new, project_service.MODE_MOVE, superuser,
        )

        assert audit_rows(EntityType.PROJECT, project.pk).count() == 1
        assert audit_rows(EntityType.INCOME, expected.pk).count() == 1
        assert audit_rows(EntityType.INCOME, liquid.pk).count() == 1

    def test_a_blocked_income_detaches_and_keeps_its_client(
        self, superuser, make_client_profile,
    ):
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        blocked = make_income(old, project)
        child = make_income(
            old, project, kind=IncomeRecord.Kind.LIQUID,
            expected_income=blocked, concept='Abono',
        )
        draft = make_cuenta(
            project, status=Document.CommercialStatus.DRAFT, income=blocked,
        )

        result = project_service.change_client_apply(
            project, new, project_service.MODE_MOVE, superuser,
        )

        blocked.refresh_from_db()
        child.refresh_from_db()
        draft.refresh_from_db()
        assert blocked.client_id == old.pk
        assert blocked.project_id is None
        # The child follows the parent's cleared project, not the new client.
        assert child.project_id is None
        assert child.client_id == old.pk
        assert draft.project_id is None
        assert result['detached']['incomes'] == 1
        assert result['detached']['draft_accounts'] == 1

    def test_issued_account_blocks_client_change_before_draft_cascade(
        self, superuser, make_client_profile,
    ):
        """Falla si un cobro emitido permite cambiar dueño o reescribir su draft vecino."""
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        issued = make_cuenta(
            project, status=Document.CommercialStatus.ISSUED, title='Emitida',
        )
        following = make_cuenta(
            project, status=Document.CommercialStatus.DRAFT, title='Draft',
        )

        with pytest.raises(ValidationError, match='historia financiera'):
            project_service.change_client_apply(
                project, new, project_service.MODE_MOVE, superuser,
            )

        project.refresh_from_db()
        issued.refresh_from_db()
        following.refresh_from_db()
        assert project.client_id == old.user_id
        assert issued.project_id == project.pk
        assert issued.client_user_id == old.user_id
        assert issued.collection_account.customer_name == 'Cliente Viejo'
        assert audit_rows(EntityType.COLLECTION_ACCOUNT, issued.pk).count() == 0
        assert following.project_id == project.pk
        assert following.client_user_id == old.user_id
        assert following.collection_account.customer_name == 'Cliente Viejo'
        assert audit_rows(EntityType.COLLECTION_ACCOUNT, following.pk).count() == 0

    @pytest.mark.parametrize('mode', [project_service.MODE_MOVE, project_service.MODE_DETACH])
    def test_clientless_hosting_blocks_both_change_modes_before_writes(
        self, superuser, make_client_profile, mode,
    ):
        """Falla si un hosting legado sin cliente se mueve o desvincula por cascada."""
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        loose = make_hosting(None, project, client_name='Sin dueño')

        with pytest.raises(ValidationError, match='historia financiera'):
            project_service.change_client_apply(project, new, mode, superuser)

        project.refresh_from_db()
        loose.refresh_from_db()
        assert project.client_id == old.user_id
        assert loose.project_id == project.pk
        assert loose.client_id is None

class TestApplyDetach:
    def test_every_record_keeps_its_client_and_loses_the_project(
        self, superuser, make_client_profile,
    ):
        old = make_client_profile()
        new = make_client_profile()
        project = make_project(old)
        root = project.document_root_folder
        folder_ids = [root.id, *root.children.values_list('id', flat=True)]
        expected = make_income(old, project)
        child = make_income(
            old, project, kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected, concept='Abono',
        )
        draft = make_cuenta(
            project, status=Document.CommercialStatus.DRAFT, title='Draft',
        )

        result = project_service.change_client_apply(
            project, new, project_service.MODE_DETACH, superuser,
        )

        project.refresh_from_db()
        expected.refresh_from_db()
        child.refresh_from_db()
        draft.refresh_from_db()
        assert project.client_id == new.user_id
        assert expected.project_id is None and expected.client_id == old.pk
        assert child.project_id is None
        assert draft.project_id is None
        assert result['detached'] == {
            'hostings': 0, 'incomes': 1, 'draft_accounts': 1,
        }
        assert list(
            DocumentFolder.objects.filter(pk__in=folder_ids)
            .order_by('id')
            .values_list('project_id', 'client_user_id')
        ) == [(project.id, new.user_id)] * len(folder_ids)


class TestDeletionBlockers:
    def test_counts_every_linked_record_including_cancelled_cuentas(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        make_hosting(profile, project)
        make_cuenta(project, status=Document.CommercialStatus.CANCELLED)
        CommunicationThread.objects.create(
            client=profile,
            project=project,
            title='Histórico del proyecto',
        )

        blockers = project_service.deletion_blockers(project)

        assert blockers == {
            'hostings': 1,
            'incomes': 0,
            'documents': 1,
            # Two: the historical thread created above plus the project's
            # auto-provisioned mother thread. The mother counts on purpose —
            # a hard delete would blank its project with SET_NULL, which is
            # precisely the silent orphaning this guard exists to stop.
            'communication_threads': 2,
        }
