"""The retroactive pass: fill missing projects only when unambiguous.

Pins the deterministic rule (exactly ONE active project — the same rule as
the form auto-select, per PA-25 no migration-style guessing), the fill-only
writes with their audit rows (actor-less = system action), the untouchable
parts of an issued cuenta (snapshot, status), and the dry-run/idempotency
contract inherited from ``link_documents_from_folders``.
"""
from decimal import Decimal
from io import StringIO

import pytest
from accounts.models import Project
from django.core.management import call_command

from content.models import (
    AccountingChangeLog,
    Document,
    DocumentCollectionAccount,
    HostingRecord,
    IncomeRecord,
)
from content.services.document_type_utils import (
    get_collection_account_document_type,
)

pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType


def run_command(*args):
    out = StringIO()
    call_command('link_records_single_project', *args, stdout=out)
    return out.getvalue()


def make_project(profile, name='Vastago', *, status=Project.STATUS_ACTIVE):
    return Project.objects.create(
        name=name, client=profile.user, status=status,
    )


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


def audit_rows(entity_type, object_id):
    return AccountingChangeLog.objects.filter(
        entity_type=entity_type, object_id=object_id,
    )


class TestDeterministicRule:
    def test_single_project_client_links_eligible_records(
        self, make_client_profile,
    ):
        """Falla si el backfill omite un registro elegible del cliente."""
        profile = make_client_profile()
        project = make_project(profile)
        income = make_income(profile)
        hosting = make_hosting(profile)

        run_command('--apply')

        income.refresh_from_db()
        hosting.refresh_from_db()
        assert (income.project_id, hosting.project_id) == (
            project.pk, project.pk,
        )

    def test_income_backfill_audit_matches_system_diff(
        self, make_client_profile,
    ):
        """Falla si el backfill registra un actor o diff distinto del sistema."""
        profile = make_client_profile()
        make_project(profile)
        income = make_income(profile)

        run_command('--apply')

        income_audit = audit_rows(EntityType.INCOME, income.pk).get()
        assert {
            'action': income_audit.action,
            'actor': income_audit.actor,
            'actor_username': income_audit.actor_username,
            'changes': income_audit.changes,
        } == {
            'action': AccountingChangeLog.Action.UPDATED,
            'actor': None,
            'actor_username': '',
            'changes': [{
                'field': 'project',
                'label': 'Proyecto',
                'old': '',
                'new': 'Vastago',
            }],
        }

    def test_two_active_projects_skip_with_reason(self, make_client_profile):
        profile = make_client_profile()
        make_project(profile, name='Vastago')
        make_project(profile, name='Mimittos')
        income = make_income(profile)

        output = run_command('--apply')

        income.refresh_from_db()
        assert income.project_id is None
        assert '2 proyectos activos (ambiguo)' in output

    def test_an_archived_sibling_does_not_block_the_active_one(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        active = make_project(profile, name='Vastago')
        make_project(
            profile, name='Vastago Legacy', status=Project.STATUS_ARCHIVED,
        )
        income = make_income(profile)

        run_command('--apply')

        income.refresh_from_db()
        assert income.project_id == active.pk

    def test_only_archived_projects_skip(self, make_client_profile):
        profile = make_client_profile()
        make_project(profile, status=Project.STATUS_ARCHIVED)
        income = make_income(profile)

        output = run_command('--apply')

        income.refresh_from_db()
        assert income.project_id is None
        assert 'cliente sin proyectos activos' in output


class TestDocumentsAndCuentas:
    def test_plain_document_links_with_a_readable_audit_row(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        document = make_document(profile)

        run_command('--apply')

        document.refresh_from_db()
        assert document.project_id == project.pk
        row = audit_rows(EntityType.DOCUMENT, document.pk).get()
        # Pins the object_repr fix: DOCUMENT rows used to fall through to
        # the 'Configuración contable' fallback.
        assert row.object_repr == 'Contrato F7'

    def test_issued_cuenta_gets_the_fk_and_keeps_its_frozen_facts(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        cuenta = make_issued_cuenta(profile)

        output = run_command('--apply')

        cuenta.refresh_from_db()
        extension = DocumentCollectionAccount.objects.get(document=cuenta)
        assert cuenta.project_id == project.pk
        assert cuenta.commercial_status == Document.CommercialStatus.ISSUED
        assert extension.customer_project_name == ''
        row = audit_rows(EntityType.COLLECTION_ACCOUNT, cuenta.pk).get()
        assert row.object_repr == 'PA-ACME-001'
        assert 'PA-ACME-001 (cuenta de cobro)' in output

    def test_archived_documents_stay_out_of_scope(self, make_client_profile):
        profile = make_client_profile()
        make_project(profile)
        document = make_document(profile, archived=True)

        run_command('--apply')

        document.refresh_from_db()
        assert document.project_id is None


class TestRunContract:
    def test_dry_run_prints_the_plan_and_writes_nothing(
        self, make_client_profile,
    ):
        profile = make_client_profile()
        project = make_project(profile)
        income = make_income(profile)

        output = run_command()

        income.refresh_from_db()
        assert income.project_id is None
        assert f'Proyecto #{project.pk} "Vastago"' in output
        assert 'Dry-run: nada se escribió' in output
        assert AccountingChangeLog.objects.count() == 0

    def test_a_second_apply_reports_zero(self, make_client_profile):
        profile = make_client_profile()
        make_project(profile)
        make_income(profile)
        make_document(profile)

        run_command('--apply')
        output = run_command('--apply')

        assert 'ingresos 0/0 por enlazar' in output
        assert 'documentos 0/0 por enlazar' in output
        assert 'Aplicado: 0 ingresos; 0 hostings; 0 documentos.' in output


def test_retained_rows_are_reported_and_never_linked(make_client_profile, admin_user):
    """Fails if --apply tries to fill a row retained from a deleted project and aborts the run."""
    from content.models import ProjectRetentionContext

    profile = make_client_profile()
    project = make_project(profile)
    context = ProjectRetentionContext.objects.create(
        client=profile.user, original_project_id=9014, project_name='Littigio anterior',
        created_by=admin_user,
    )
    retained = make_income(profile, concept='Inicio Fase 1', retention_context=context)
    loose = make_income(profile, concept='Entrega Fase 1')

    output = run_command('--apply')

    assert '[skip] datos conservados de un proyecto eliminado: 1 ingresos' in output
    retained.refresh_from_db()
    loose.refresh_from_db()
    assert retained.project_id is None
    assert loose.project_id == project.pk
