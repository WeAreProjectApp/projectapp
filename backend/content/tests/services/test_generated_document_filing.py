from datetime import date
from decimal import Decimal

import pytest
from accounts.models import Project, ProjectContract, UserProfile
from accounts.services.billing_context import associate_account
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentFolder,
    DocumentItem,
    IssuerProfile,
)
from content.services.collection_account_service import (
    issue_collection_account,
    mark_collection_account_cancelled,
)
from content.services.accounting_service import assign_project_to_documents
from content.services.generated_document_filing_service import (
    build_generated_folder_path,
    ensure_generated_folder_path,
    file_collection_account,
    file_proposal_snapshot,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.document_type_utils import (
    get_collection_account_document_type,
)
from content.services.project_document_folder_service import (
    ProjectFolderReconciliationRequired,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def client_user():
    user = User.objects.create_user(
        username='filing-client@example.com',
        email='filing-client@example.com',
        first_name='Ana',
        last_name='Pérez',
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_CLIENT,
        company_name='Acme SAS',
        nit='900123456',
    )
    return user


@pytest.fixture
def project(client_user):
    return Project.objects.create(name='Portal Acme', client=client_user)


@pytest.fixture
def issuer():
    return IssuerProfile.objects.create(
        name='ProjectApp',
        legal_name='ProjectApp SAS',
        identification_number='901000000',
        email='billing@projectapp.co',
        public_number_prefix='PA',
    )


@pytest.fixture
def billing_admin():
    return User.objects.create_superuser(
        username='filing-billing-admin',
        email='filing-billing-admin@example.com',
        password='pass12345',
    )


def make_account(*, client_user=None, project=None, concept='Desarrollo web', acting_user=None):
    document = Document.objects.create(
        title=f'Cuenta de cobro — {concept}',
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.DRAFT,
        client_user=client_user,
        project=project,
    )
    DocumentCollectionAccount.objects.create(
        document=document,
        billing_concept=concept,
        payment_term_days=8,
    )
    DocumentItem.objects.create(
        document=document,
        position=1,
        description=concept,
        quantity=Decimal('1'),
        unit_price=Decimal('100000'),
        line_total=Decimal('100000'),
    )
    if project:
        source_document = Document.objects.create(
            title=f'Contrato fuente — {concept}',
            project=project,
            client_user=project.client,
        )
        contract = ProjectContract.objects.create(
            project=project,
            key=f'filing-contract-{document.pk}',
            title=f'Contrato — {concept}',
            document=source_document,
        )
        associate_account(document.pk, acting_user, {
            'billing_nature': 'contract',
            'contract_id': contract.pk,
            'expected_version': 0,
            'reason': 'Contexto contractual de la cuenta generada.',
        })
    return document


def folder_path(document):
    return [
        *(folder.name for folder in document.folder.get_ancestors()),
        document.folder.name,
    ]


@freeze_time('2026-08-14 15:00:00')
def test_issue_files_under_project_month(issuer, project, client_user, billing_admin):
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)

    issue_collection_account(document, issuer=issuer)
    document.refresh_from_db()

    assert folder_path(document) == [
        'Portal Acme',
        'Cuentas de cobro',
        '2026',
        '08 - Agosto',
    ]
    assert document.folder.get_ancestors()[0] == project.document_root_folder
    assert not DocumentFolder.objects.filter(system_key='generated:projects').exists()


def test_project_filing_requires_a_reviewed_managed_root(project, client_user):
    root = project.document_root_folder
    root.children.all().delete()
    root.delete()
    folder_count = DocumentFolder.objects.count()

    with pytest.raises(
        ProjectFolderReconciliationRequired,
        match='conciliación PA-108',
    ):
        ensure_generated_folder_path(
            COLLECTION_ACCOUNT,
            business_date=date(2026, 8, 14),
            project=project,
            client_user=client_user,
        )

    assert DocumentFolder.objects.count() == folder_count
    assert not DocumentFolder.objects.filter(managed_project=project).exists()


@freeze_time('2026-08-14 15:00:00')
def test_issue_applies_account_title_convention(issuer, project, client_user, billing_admin):
    document = make_account(
        client_user=client_user,
        project=project,
        concept='Desarrollo del portal',
        acting_user=billing_admin,
    )

    issue_collection_account(
        document,
        issuer=issuer,
        number_allocator=lambda: 'PA-ACME-007',
    )
    document.refresh_from_db()

    assert document.title == (
        '2026-08-14 · PA-ACME-007 · Desarrollo del portal'
    )


@freeze_time('2026-08-14 15:00:00')
def test_repeated_filing_reuses_hierarchy(issuer, project, client_user, billing_admin):
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)
    issue_collection_account(document, issuer=issuer)
    initial_folder_count = DocumentFolder.objects.count()

    file_collection_account(document)
    file_collection_account(document)

    assert DocumentFolder.objects.count() == initial_folder_count


@freeze_time('2026-08-14 15:00:00')
def test_repeated_filing_repairs_managed_folder(issuer, project, client_user, billing_admin):
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)
    issue_collection_account(document, issuer=issuer)
    month_folder = document.folder
    month_folder.name = 'Mes alterado'
    month_folder.is_archived = True
    month_folder.archived_at = timezone.now()
    month_folder.archived_via_folder = month_folder.parent
    month_folder.save(update_fields=[
        'name', 'is_archived', 'archived_at', 'archived_via_folder',
        'updated_at',
    ])

    file_collection_account(document)
    month_folder.refresh_from_db()

    assert (
        month_folder.name,
        month_folder.is_archived,
        month_folder.archived_at,
        month_folder.archived_via_folder_id,
    ) == ('08 - Agosto', False, None, None)


@freeze_time('2026-08-14 15:00:00')
def test_filing_reparents_a_legacy_project_branch(
    issuer, project, client_user, billing_admin,
):
    root = project.document_root_folder
    root.children.all().delete()
    legacy_root = DocumentFolder.objects.create(
        name='Proyectos', system_key='generated:projects',
    )
    legacy_project = DocumentFolder.objects.create(
        name=project.name,
        system_key=f'generated:project:{project.id}',
        parent=legacy_root,
        project=project,
        client_user=client_user,
    )
    category = DocumentFolder.objects.create(
        name='Cuentas de cobro',
        system_key=f'generated:project:{project.id}:collection_account',
        parent=legacy_project,
        project=project,
        client_user=client_user,
    )
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)

    issue_collection_account(document, issuer=issuer)

    category.refresh_from_db()
    assert category.parent_id == root.id
    assert not DocumentFolder.objects.filter(pk=legacy_project.id).exists()
    assert not DocumentFolder.objects.filter(pk=legacy_root.id).exists()


def test_generated_path_rejects_unknown_document_kind():
    with pytest.raises(ValueError, match='Unsupported generated document kind'):
        build_generated_folder_path('invoice', business_date=date(2026, 8, 14))


def test_generated_path_requires_business_date():
    with pytest.raises(ValueError, match='business date is required'):
        build_generated_folder_path(COLLECTION_ACCOUNT)


def test_proposal_filing_rejects_non_snapshot(client_user):
    document = Document.objects.create(
        title='Documento manual',
        client_user=client_user,
    )

    with pytest.raises(ValueError, match='not a proposal snapshot'):
        file_proposal_snapshot(document)


@freeze_time('2026-08-14 15:00:00')
def test_issue_without_project_uses_client_branch(issuer, client_user):
    document = make_account(client_user=client_user)

    issue_collection_account(document, issuer=issuer)
    document.refresh_from_db()

    assert folder_path(document) == [
        'Clientes',
        'Ana Pérez',
        'Sin proyecto',
        'Cuentas de cobro',
        '2026',
        '08 - Agosto',
    ]


@freeze_time('2026-08-14 15:00:00')
def test_cancelled_issue_moves_to_cancelled_branch(issuer, project, client_user, billing_admin):
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)
    issue_collection_account(document, issuer=issuer)

    mark_collection_account_cancelled(document)
    document.refresh_from_db()

    assert folder_path(document)[-3:] == ['2026', '08 - Agosto', 'Anuladas']


def test_cancelled_draft_uses_unissued_branch(project, client_user, billing_admin):
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)

    mark_collection_account_cancelled(document)
    document.refresh_from_db()

    assert folder_path(document)[-3:] == [
        'Cuentas de cobro', 'Sin emitir', 'Anuladas',
    ]


def test_assigning_project_keeps_unissued_draft_unfiled(project, client_user):
    document = make_account(client_user=client_user)

    assign_project_to_documents([document.pk], project, user=None)
    document.refresh_from_db()

    assert document.project_id == project.pk
    assert document.folder_id is None


@freeze_time('2026-09-01 02:00:00')
def test_issue_uses_bogota_calendar_date(issuer, project, client_user, billing_admin):
    document = make_account(client_user=client_user, project=project, acting_user=billing_admin)

    issue_collection_account(document, issuer=issuer)
    document.refresh_from_db()

    assert document.issue_date == date(2026, 8, 31)
