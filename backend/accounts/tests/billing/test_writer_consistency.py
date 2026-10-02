"""Observable consistency checks for the project, origin, and account writers."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from accounts.admin import ProjectAdmin
from accounts.models import (
    CollectionAccountContext,
    Project,
    ProjectHosting,
    ProjectHostingAccountingSource,
    UserProfile,
)
from accounts.services.billing_context import associate_account
from content.admin import admin_site
from content.models import (
    AccountingChangeLog,
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    EntityHistory,
    EntityRevision,
    HostingRecord,
    IncomeRecord,
    IssuerProfile,
)
from content.services.collection_account_create_service import (
    CollectionAccountError,
    create_income_collection_account_draft,
)
from content.services.collection_account_service import issue_collection_account
from content.services.document_type_utils import get_collection_account_document_type
from content.services.hosting_billing_service import (
    HostingBillingError,
    create_hosting_collection_account,
)
from content.serializers.accounting import IncomeRecordCreateUpdateSerializer
from content.serializers.document import DocumentCreateUpdateSerializer
from content.services.accounting_service import EntityType, bulk_assign_project, update_record


User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def destination_client():
    user = User.objects.create_user(
        username='writer-destination@example.test',
        email='writer-destination@example.test',
        password='pass12345',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


@pytest.fixture
def issuer():
    return IssuerProfile.objects.create(
        name='ProjectApp', legal_name='ProjectApp SAS',
        identification_number='900123456', email='billing@projectapp.test',
        public_number_prefix='PA',
    )


@pytest.fixture
def project_income(project):
    return IncomeRecord.objects.create(
        concept='Implementación', kind=IncomeRecord.Kind.EXPECTED,
        client=project.client.profile, project=project,
        period_date=date(2026, 10, 1), total_amount=Decimal('120000'),
        gustavo_amount=Decimal('60000'), carlos_amount=Decimal('60000'),
    )


def account_payload(project, income, contract):
    return {
        'client_profile_id': project.client.profile.pk,
        'income_record_id': income.pk,
        'billing_nature': 'contract' if contract else None,
        'contract_id': contract.pk if contract else None,
        'items': [{
            'description': 'Implementación', 'quantity': Decimal('1'),
            'unit_price': Decimal('120000'),
        }],
    }


def admin_post_data(project, client):
    return {
        'name': project.name,
        'description': project.description,
        'client': str(client.pk),
        'status': project.status,
        'progress': str(project.progress),
        'start_date': '',
        'estimated_end_date': '',
        'hosting_start_date': '',
        'payment_milestones': '[]',
        'hosting_tiers': '[]',
        'production_url': '',
        'staging_url': '',
        'repository_url': '',
        '_save': 'Save',
    }


def issued_account(project, *, title='Cuenta emitida'):
    document = Document.objects.create(
        title=title,
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.ISSUED,
        public_number='PA-WRITER-001', project=project,
        client_user=project.client,
        total=Decimal('120000'),
    )
    DocumentCollectionAccount.objects.create(document=document, customer_name='Cliente congelado')
    return document


def admin_request(user, project, client):
    request = RequestFactory().post(
        f'/admin/accounts/project/{project.pk}/change/', admin_post_data(project, client),
    )
    request.user = user
    SessionMiddleware(lambda request: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    request._dont_enforce_csrf_checks = True
    return request


class LateAccountProjectAdmin(ProjectAdmin):
    """Materializes a real issued account after form cleaning, before save_model."""

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)
        if change:
            issued_account(Project.objects.get(pk=obj.pk), title='Cuenta concurrente')
        return obj


def test_income_writer_revalidates_current_project_owner_before_creating_document(
    project, project_income, contract, destination_client, issuer, admin_user,
):
    """Falla si un ingreso con propietario obsoleto crea una cuenta para el cliente anterior."""
    project.client = destination_client.user
    project.save(update_fields=['client', 'updated_at'])
    before = (Document.objects.count(), EntityHistory.objects.count(), EntityRevision.objects.count())

    with pytest.raises(CollectionAccountError, match='cliente'):
        create_income_collection_account_draft(
            account_payload(project, project_income, contract), acting_user=admin_user,
        )

    project_income.refresh_from_db()
    assert project_income.client_id != destination_client.pk
    assert (Document.objects.count(), EntityHistory.objects.count(), EntityRevision.objects.count()) == before


def test_income_writer_returns_a_fresh_current_document(
    project, project_income, contract, issuer, admin_user,
):
    """Falla si crear una cuenta devuelve un documento que no refleja su contexto persistido."""
    document = create_income_collection_account_draft(
        account_payload(project, project_income, contract), acting_user=admin_user,
    )

    assert document.pk is not None
    assert document.project_id == project.pk
    assert document.income_record_id == project_income.pk
    assert document.billing_context.contract_id == contract.pk


def test_invalid_project_account_context_rolls_back_document(
    project, project_income, issuer, admin_user,
):
    """Falla si un cobro de proyecto sin vínculo deja documento o historia financiera."""
    payload = account_payload(project, project_income, contract=None)
    payload.pop('billing_nature')
    payload.pop('contract_id')
    before = (Document.objects.count(), AccountingChangeLog.objects.count(), EntityHistory.objects.count())

    with pytest.raises(ValidationError, match='naturaleza'):
        create_income_collection_account_draft(payload, acting_user=admin_user)

    assert (Document.objects.count(), AccountingChangeLog.objects.count(), EntityHistory.objects.count()) == before


def test_hosting_writer_revalidates_current_owner_before_creating_document(
    project, hosting_record, subscription, payment, issuer, destination_client, admin_user,
):
    """Falla si un origen hosting obsoleto crea una cuenta tras cambiar el dueño del proyecto."""
    hosting = ProjectHosting.objects.create(project=project, subscription=subscription)
    ProjectHostingAccountingSource.objects.create(hosting=hosting, hosting_record=hosting_record)
    project.client = destination_client.user
    project.save(update_fields=['client', 'updated_at'])
    before = (Document.objects.count(), AccountingChangeLog.objects.count())

    with pytest.raises(HostingBillingError, match='cliente'):
        create_hosting_collection_account(
            hosting_record, acting_user=admin_user, hosting_payment_id=payment.pk,
        )

    hosting_record.refresh_from_db()
    assert hosting_record.client_id != destination_client.pk
    assert (Document.objects.count(), AccountingChangeLog.objects.count()) == before


def test_issue_rejects_stale_draft_instance(
    project, issuer, admin_user,
):
    """Falla si emitir dos veces reasigna número o reescribe la cuenta ya emitida."""
    document = Document.objects.create(
        title='Cuenta no proyecto', document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.DRAFT, client_user=project.client,
    )
    DocumentCollectionAccount.objects.create(document=document)
    DocumentItem.objects.create(
        document=document, position=1, item_type=DocumentItem.ItemType.SERVICE,
        description='Servicio', quantity=1, unit_price=Decimal('50000'),
        line_total=Decimal('50000'),
    )

    stale_draft = Document.objects.get(pk=document.pk)
    issued = issue_collection_account(document, issuer=issuer, acting_user=admin_user)
    public_number = issued.public_number
    with pytest.raises(CollectionAccountError, match='Only draft'):
        issue_collection_account(stale_draft, issuer=issuer, acting_user=admin_user)

    current = Document.objects.get(pk=document.pk)
    assert issued.pk == current.pk
    assert current.commercial_status == Document.CommercialStatus.ISSUED
    assert current.public_number == public_number


def test_project_admin_post_accepts_an_owner_change_without_financial_history(
    project, destination_client,
):
    """Falla si el formulario Admin rechaza un traslado permitido sin historia financiera."""
    administrator = ProjectAdmin(Project, admin_site)
    user = User.objects.create_superuser(
        username='writer-admin-valid', email='writer-admin-valid@example.test', password='pass12345',
    )

    response = administrator.changeform_view(
        admin_request(user, project, destination_client), str(project.pk),
    )

    assert response.status_code == 302
    project.refresh_from_db()
    assert project.client_id == destination_client.user_id


def test_project_admin_post_shows_client_error_without_financial_write(
    project, destination_client,
):
    """Falla si el Admin responde 500 o cambia dueño cuando ya existe una cuenta emitida."""
    issued_account(project)
    user = User.objects.create_superuser(
        username='writer-admin-blocked', email='writer-admin-blocked@example.test', password='pass12345',
    )
    administrator = ProjectAdmin(Project, admin_site)

    response = administrator.changeform_view(
        admin_request(user, project, destination_client), str(project.pk),
    )

    assert response.status_code == 200
    assert 'historia financiera' in response.rendered_content
    project.refresh_from_db()
    assert project.client_id != destination_client.user_id


def test_admin_race_rolls_back_late_account(
    project, destination_client,
):
    """Falla si una cuenta creada tras clean permite el save o queda grabada tras el rechazo."""
    user = User.objects.create_superuser(
        username='writer-admin-race', email='writer-admin-race@example.test', password='pass12345',
    )
    administrator = LateAccountProjectAdmin(Project, admin_site)

    response = administrator.changeform_view(
        admin_request(user, project, destination_client), str(project.pk),
    )

    assert response.status_code == 200
    assert 'historia financiera' in response.rendered_content
    project.refresh_from_db()
    assert project.client_id != destination_client.user_id
    assert not Document.objects.filter(title='Cuenta concurrente').exists()


def test_association_revalidates_the_current_project_owner_without_history(
    project, account, contract, destination_client, admin_user,
):
    """Falla si asociar una cuenta conserva un cliente obsoleto tras bloquear el proyecto."""
    project.client = destination_client.user
    project.save(update_fields=['client', 'updated_at'])
    before = (EntityHistory.objects.count(), EntityRevision.objects.count())

    with pytest.raises(ValidationError, match='mismo cliente'):
        associate_account(account.pk, admin_user, {
            'billing_nature': 'contract', 'contract_id': contract.pk,
            'expected_version': 0, 'reason': 'Revisión administrativa.',
        })

    account.refresh_from_db()
    assert account.project_id == project.pk
    assert not CollectionAccountContext.objects.filter(document=account).exists()
    assert (EntityHistory.objects.count(), EntityRevision.objects.count()) == before


def test_update_income_revalidates_prevalidated_project_owner(
    project, project_income, destination_client, admin_user,
):
    """Falla si update_record usa el dueño visto antes de validar el serializer."""
    serializer = IncomeRecordCreateUpdateSerializer(
        instance=project_income, data={'project': project.pk}, partial=True,
    )
    serializer.is_valid(raise_exception=True)
    project.client = destination_client.user
    project.save(update_fields=['client', 'updated_at'])
    before = AccountingChangeLog.objects.count()

    with pytest.raises(ValidationError, match='otro cliente'):
        update_record(EntityType.INCOME, project_income, serializer, admin_user, notify=False)

    project_income.refresh_from_db()
    assert project_income.project_id == project.pk
    assert project_income.client_id != destination_client.pk
    assert AccountingChangeLog.objects.count() == before


def test_bulk_income_project_assignment_revalidates_cached_target_owner(
    project, project_income, destination_client, admin_user,
):
    """Falla si bulk_assign_project usa un Project en memoria tras cambiar su dueño."""
    target = Project.objects.create(name='Destino', client=project.client)
    target.client = destination_client.user
    target.save(update_fields=['client', 'updated_at'])
    before = AccountingChangeLog.objects.count()

    with pytest.raises(ValidationError, match='otro cliente'):
        bulk_assign_project(EntityType.INCOME, [project_income.pk], target, admin_user)

    project_income.refresh_from_db()
    assert project_income.project_id == project.pk
    assert AccountingChangeLog.objects.count() == before


def test_document_update_revalidates_the_current_project_owner(
    account, project, destination_client,
):
    """Falla si editar una cuenta conserva un dueño de proyecto visto antes del bloqueo."""
    serializer = DocumentCreateUpdateSerializer(
        instance=account, data={'title': 'Cobro histórico revisado'}, partial=True,
    )
    serializer.is_valid(raise_exception=True)
    project.client = destination_client.user
    project.save(update_fields=['client', 'updated_at'])

    with pytest.raises(ValidationError, match='otro cliente'):
        serializer.save()

    account.refresh_from_db()
    assert account.title == 'Cobro histórico'
    assert account.client_user_id != destination_client.user_id
