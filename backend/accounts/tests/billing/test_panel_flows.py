"""Panel-only billing context and issuance boundary tests."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.middleware.csrf import _get_new_csrf_string
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import CollectionAccountContext, Project
from content.models import Document, DocumentCollectionAccount, IncomeRecord, IssuerProfile
from content.services import accounting_service
from content.services.accounting_service import EntityType
from content.services.collection_account_create_service import (
    create_income_collection_account_draft,
)
from content.services.hosting_billing_service import (
    HostingBillingError,
    send_hosting_collection_account,
)


User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def panel_superuser():
    return User.objects.create_superuser(
        username='billing-panel-superuser',
        email='billing-panel-superuser@example.test',
        password='panel-password',
    )


@pytest.fixture
def panel_client(panel_superuser):
    client = APIClient(enforce_csrf_checks=True)
    assert client.login(username=panel_superuser.username, password='panel-password')
    return client


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
        concept='Implementación contractual',
        kind=IncomeRecord.Kind.EXPECTED,
        client=project.client.profile,
        project=project,
        period_date=date(2026, 10, 1),
        total_amount=Decimal('150000'),
        gustavo_amount=Decimal('75000'),
        carlos_amount=Decimal('75000'),
    )


def income_payload(project, income, contract=None):
    payload = {
        'client_profile_id': project.client.profile.pk,
        'income_record_id': income.pk,
        'items': [{
            'description': 'Implementación contractual',
            'quantity': Decimal('1'),
            'unit_price': Decimal('150000'),
        }],
    }
    if contract is not None:
        payload.update({'billing_nature': 'contract', 'contract_id': contract.pk})
    return payload


def csrf_headers(client):
    token = _get_new_csrf_string()
    client.cookies['csrftoken'] = token
    return {'HTTP_X_CSRFTOKEN': token}


def hosting_mapping(record, subscription):
    return {
        'expected_version': 0,
        'reason': 'Se confirma la identidad de las fuentes registradas.',
        'subscription_id': subscription.pk,
        'hosting_record_ids': [record.pk],
        'operational_record_id': record.pk,
    }


def test_panel_context_patch_rejects_session_write_without_csrf(
    panel_client, account, contract,
):
    """Falla si el administrador de Panel puede asociar un cobro sin CSRF."""
    response = panel_client.patch(
        f'/api/admin/billing-context/accounts/{account.pk}/',
        {
            'billing_nature': 'contract',
            'contract_id': contract.pk,
            'expected_version': 0,
            'reason': 'Asociación administrativa documentada.',
        },
        format='json',
    )

    assert response.status_code == 403
    assert not CollectionAccountContext.objects.filter(document=account).exists()


def test_panel_context_patch_accepts_session_with_matching_csrf(
    panel_client, account, contract,
):
    """Falla si el Panel con sesión y CSRF válidos no guarda el contrato elegido."""
    response = panel_client.patch(
        f'/api/admin/billing-context/accounts/{account.pk}/',
        {
            'billing_nature': 'contract',
            'contract_id': contract.pk,
            'expected_version': 0,
            'reason': 'Asociación administrativa documentada.',
        },
        format='json',
        **csrf_headers(panel_client),
    )

    assert response.status_code == 200, response.data
    assert response.data['contract']['id'] == contract.pk
    assert CollectionAccountContext.objects.get(document=account).contract_id == contract.pk


def test_panel_context_refuses_jwt_even_for_superuser(panel_superuser, account):
    """Falla si una credencial JWT obtiene el acceso reservado a sesión del Panel."""
    client = APIClient()
    response = client.get(
        f'/api/admin/billing-context/accounts/{account.pk}/',
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(panel_superuser)}',
    )

    assert response.status_code == 403
    assert not CollectionAccountContext.objects.filter(document=account).exists()


def test_project_income_preview_requires_explicit_context_and_rolls_back(
    panel_client, issuer, project, project_income,
):
    """Falla si el preview deja un cobro o reclasifica el ingreso sin vínculo explícito."""
    response = panel_client.post(
        '/api/accounting/collection-accounts/preview/',
        income_payload(project, project_income),
        format='json',
        **csrf_headers(panel_client),
    )

    assert response.status_code == 400
    assert 'naturaleza contrato u hosting' in response.data['detail']
    assert not Document.objects.filter(income_record=project_income).exists()
    project_income.refresh_from_db()
    assert project_income.client_id == project.client.profile.pk


def test_project_income_preview_with_contract_preserves_financial_rows(
    panel_client, issuer, project, project_income, contract,
):
    """Falla si el preview contractual persiste documentos o altera el ingreso original."""
    before = (
        Document.objects.count(),
        IncomeRecord.objects.count(),
        DocumentCollectionAccount.objects.count(),
    )
    with patch(
        'content.views.collection_accounts_panel.CollectionAccountPdfService.generate',
        return_value=b'%PDF-1.4 preview',
    ):
        response = panel_client.post(
            '/api/accounting/collection-accounts/preview/',
            income_payload(project, project_income, contract),
            format='json',
            **csrf_headers(panel_client),
        )

    assert response.status_code == 200, response.data
    assert response.data['total'] == '150000.00'
    assert (
        Document.objects.count(),
        IncomeRecord.objects.count(),
        DocumentCollectionAccount.objects.count(),
    ) == before
    project_income.refresh_from_db()
    assert project_income.total_amount == Decimal('150000')


def test_nonproject_income_draft_keeps_the_existing_accounting_flow(
    issuer, project, admin_user,
):
    """Falla si un ingreso sin proyecto exige un contrato o un hosting inexistentes."""
    income = IncomeRecord.objects.create(
        concept='Diagnóstico previo',
        kind=IncomeRecord.Kind.EXPECTED,
        client=project.client.profile,
        period_date=date(2026, 10, 1),
        total_amount=Decimal('50000'),
        gustavo_amount=Decimal('25000'),
        carlos_amount=Decimal('25000'),
    )
    document = create_income_collection_account_draft(
        income_payload(project, income), acting_user=admin_user,
    )

    assert document.project_id is None
    assert document.income_record_id == income.pk
    assert not CollectionAccountContext.objects.filter(document=document).exists()


def test_hosting_send_requires_selected_subscription_payment(
    issuer, project, admin_user, hosting_record, payment,
):
    """Falla si una emisión de hosting con suscripción deduce el pago por importe o fecha."""
    from accounts.services.hosting_context import reconcile_hosting

    reconcile_hosting(project.pk, admin_user, hosting_mapping(hosting_record, payment.subscription))
    before = (Document.objects.count(), DocumentCollectionAccount.objects.count(), payment.__class__.objects.count())

    with pytest.raises(HostingBillingError, match='Asocia explícitamente'):
        send_hosting_collection_account(hosting_record, acting_user=admin_user)

    assert (Document.objects.count(), DocumentCollectionAccount.objects.count(), payment.__class__.objects.count()) == before


def test_hosting_send_records_the_selected_payment_without_new_financial_rows(
    issuer, project, admin_user, hosting_record, payment,
):
    """Falla si emitir un hosting reconciliado duplica pagos en vez de enlazar el seleccionado."""
    from accounts.models import HostingEvidence
    from accounts.services.hosting_context import reconcile_hosting

    identity = reconcile_hosting(
        project.pk, admin_user, hosting_mapping(hosting_record, payment.subscription),
    )
    before_payment_count = payment.__class__.objects.count()
    with patch(
        'content.services.hosting_billing_service.persist_collection_account_pdf',
        return_value=None,
    ), patch(
        'content.services.hosting_billing_service._send_client_email',
        return_value=True,
    ):
        result = send_hosting_collection_account(
            hosting_record, acting_user=admin_user, hosting_payment_id=payment.pk,
        )

    document = result['document']
    assert document.commercial_status == Document.CommercialStatus.ISSUED
    assert document.billing_context.hosting_id == identity['id']
    assert HostingEvidence.objects.get(document=document).group.evidence.get(payment=payment).payment_id == payment.pk
    assert payment.__class__.objects.count() == before_payment_count


def test_income_reassignment_rejects_project_change_when_context_is_bound(
    project, project_income, contract, admin_user,
):
    """Falla si mover un ingreso cambia el proyecto de una cuenta contractual ya asociada."""
    document = create_income_collection_account_draft(
        income_payload(project, project_income, contract), acting_user=admin_user,
    )
    other_project = Project.objects.create(name='Proyecto de destino', client=project.client)

    with pytest.raises(ValidationError, match='cuentas asociadas'):
        accounting_service.bulk_assign_project(
            EntityType.INCOME, [project_income.pk], other_project, admin_user,
        )

    project_income.refresh_from_db()
    document.refresh_from_db()
    assert project_income.project_id == project.pk
    assert document.project_id == project.pk
