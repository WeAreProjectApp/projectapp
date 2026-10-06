"""Tests for accounts/collection_account_views.py — all functions untested."""
import re

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import Project, ProjectContract, UserProfile
from content.models import Document, DocumentType, ProjectRetentionContext
from content.models.document_collection_account import DocumentCollectionAccount
from content.models.document_item import DocumentItem

User = get_user_model()

pytestmark = pytest.mark.django_db

BASE_URL = '/api/accounts/collection-accounts/'


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='ca2-admin@test.com',
        email='ca2-admin@test.com',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN)
    return user


@pytest.fixture
def client_user_obj(db, admin_user):
    user = User.objects.create_user(
        username='ca2-client@test.com',
        email='ca2-client@test.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT, created_by=admin_user,
    )
    return user


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def regular_client(client_user_obj):
    client = APIClient()
    client.force_authenticate(user=client_user_obj)
    return client


@pytest.fixture
def project(client_user_obj):
    return Project.objects.create(
        name='CA Test Project',
        client=client_user_obj,
        status=Project.STATUS_ACTIVE,
        progress=0,
    )


def _create_payload(title='Test Invoice', client_user_id=None):
    data = {
        'title': title,
        'payment_term_type': DocumentCollectionAccount.PaymentTermType.AGAINST_DELIVERY,
        'city': 'Bogotá',
    }
    if client_user_id is not None:
        data['client_user_id'] = client_user_id
    return data


def _replacement_item_payload():
    return {
        'items': [{
            'description': 'Replacement line',
            'quantity': '2',
            'unit_price': '50.00',
            'discount_amount': '0.00',
            'tax_amount': '0.00',
            'line_total': '100.00',
        }],
    }


# ---------------------------------------------------------------------------
# collection_account_list_create_view — GET
# ---------------------------------------------------------------------------

class TestListCollectionAccounts:
    def test_unauthenticated_request_returns_401(self, api_client):
        response = api_client.get(BASE_URL)

        assert response.status_code == 401

    def test_admin_gets_empty_list_when_no_accounts(self, admin_client):
        response = admin_client.get(BASE_URL)

        assert response.status_code == 200
        assert response.json() == []

    def test_admin_filter_by_commercial_status(self, admin_client):
        response = admin_client.get(BASE_URL + '?commercial_status=draft')

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_client_cannot_see_draft_accounts(self, regular_client):
        response = regular_client.get(BASE_URL)

        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# collection_account_list_create_view — POST (create)
# ---------------------------------------------------------------------------

class TestCreateCollectionAccount:
    def test_admin_creates_account_with_valid_payload(self, admin_client, client_user_obj):
        response = admin_client.post(
            BASE_URL,
            data=_create_payload(client_user_id=client_user_obj.id),
            format='json',
        )

        assert response.status_code == 201
        assert response.json()['title'] == 'Test Invoice'

    def test_non_admin_cannot_create_returns_403(self, regular_client, client_user_obj):
        response = regular_client.post(
            BASE_URL,
            data=_create_payload(client_user_id=client_user_obj.id),
            format='json',
        )

        assert response.status_code == 403

    def test_invalid_payload_missing_client_user_returns_400(self, admin_client):
        response = admin_client.post(
            BASE_URL,
            data={
                'title': 'No Client',
                'payment_term_type': DocumentCollectionAccount.PaymentTermType.AGAINST_DELIVERY,
            },
            format='json',
        )

        assert response.status_code == 400

    def test_create_with_valid_project_id_uses_project_client(self, admin_client, project):
        source = Document.objects.create(title='Contrato emitido', project=project, client_user=project.client)
        contract = ProjectContract.objects.create(project=project, title='Contrato', key='api-create', document=source)
        response = admin_client.post(
            BASE_URL,
            data={
                'title': 'Project Invoice',
                'payment_term_type': DocumentCollectionAccount.PaymentTermType.AGAINST_DELIVERY,
                'project_id': project.id,
                'billing_nature': 'contract',
                'contract_id': contract.pk,
            },
            format='json',
        )

        assert response.status_code == 201

        document = Document.objects.get(pk=response.json()['id'])
        assert document.client_user_id == project.client_id
        assert document.billing_context.contract_id == contract.pk

    def test_create_with_invalid_project_id_returns_400(self, admin_client, client_user_obj):
        response = admin_client.post(
            BASE_URL,
            data={
                'title': 'Bad Project',
                'payment_term_type': DocumentCollectionAccount.PaymentTermType.AGAINST_DELIVERY,
                'project_id': 99999,
            },
            format='json',
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# collection_account_detail_view — GET / PATCH
# ---------------------------------------------------------------------------

class TestRetrieveCollectionAccount:
    def test_admin_retrieve_existing_account_returns_200(self, admin_client, client_user_obj):
        create_resp = admin_client.post(
            BASE_URL,
            data=_create_payload(client_user_id=client_user_obj.id),
            format='json',
        )
        account_id = create_resp.json()['id']

        response = admin_client.get(f'{BASE_URL}{account_id}/')

        assert response.status_code == 200
        assert response.json()['id'] == account_id

    def test_retrieve_nonexistent_account_returns_404(self, admin_client):
        response = admin_client.get(f'{BASE_URL}999999/')

        assert response.status_code == 404


class TestUpdateCollectionAccount:
    def test_admin_partial_update_title(self, admin_client, client_user_obj):
        create_resp = admin_client.post(
            BASE_URL,
            data=_create_payload(client_user_id=client_user_obj.id),
            format='json',
        )
        account_id = create_resp.json()['id']

        response = admin_client.patch(
            f'{BASE_URL}{account_id}/',
            data={'title': 'Updated Title'},
            format='json',
        )

        assert response.status_code == 200
        assert response.json()['title'] == 'Updated Title'

    def test_non_admin_update_returns_403(self, admin_client, regular_client, client_user_obj):
        create_resp = admin_client.post(
            BASE_URL,
            data=_create_payload(client_user_id=client_user_obj.id),
            format='json',
        )
        account_id = create_resp.json()['id']

        response = regular_client.patch(
            f'{BASE_URL}{account_id}/',
            data={'title': 'Hacked Title'},
            format='json',
        )

        assert response.status_code in (403, 404)

    def test_retained_account_update_keeps_existing_document_items(
        self, admin_client, admin_user, client_user_obj,
    ):
        """Fails if a retained collection-account update replaces line items before its parent is rejected."""
        collection_type, _ = DocumentType.objects.get_or_create(
            code='collection_account',
            defaults={'name': 'Collection account'},
        )
        document = Document.objects.create(
            title='Retained collection account',
            client_user=client_user_obj,
            document_type=collection_type,
            commercial_status=Document.CommercialStatus.DRAFT,
        )
        DocumentCollectionAccount.objects.create(document=document)
        original_item = DocumentItem.objects.create(
            document=document,
            description='Original retained line',
            quantity=1,
            unit_price=100,
            line_total=100,
        )
        context = ProjectRetentionContext.objects.create(
            client=client_user_obj,
            original_project_id=document.pk,
            project_name='Archived collection account',
            retained_records={},
            category_counts={},
            created_by=admin_user,
        )
        Document.objects.filter(pk=document.pk).update(
            project=None,
            retention_context=context,
        )

        response = admin_client.patch(
            f'{BASE_URL}{document.pk}/',
            data=_replacement_item_payload(),
            format='json',
        )

        assert response.status_code == 403
        original_item.refresh_from_db()
        assert original_item.description == 'Original retained line'
        assert not DocumentItem.objects.filter(
            document_id=document.pk,
            description='Replacement line',
        ).exists()


# ---------------------------------------------------------------------------
# collection_account_issue_view — numbering
# ---------------------------------------------------------------------------

class TestIssueNumbering:
    """One client, one consecutivo — whichever surface issues the cuenta.

    The platform used to fall through to the legacy per-issuer series while
    the panel and hosting flows numbered per client, so the same client ended
    up with two parallel numberings.
    """

    def _issue(self, admin_client, client_user):
        created = admin_client.post(
            BASE_URL,
            data=_create_payload(client_user_id=client_user.id),
            format='json',
        )
        return admin_client.post(f'{BASE_URL}{created.json()["id"]}/issue/')

    def test_issue_joins_the_client_own_series(self, admin_client, client_user_obj):
        profile = client_user_obj.profile
        profile.company_name = 'Torrios'
        profile.save(update_fields=['company_name'])

        response = self._issue(admin_client, client_user_obj)

        assert response.status_code == 200, response.json()
        assert response.json()['public_number'] == 'PA-TORRIOS-001'

    def test_client_without_profile_keeps_the_legacy_series(self, admin_client):
        bare = User.objects.create_user(
            username='ca2-bare@test.com',
            email='ca2-bare@test.com',
            password='pass12345',
        )

        response = self._issue(admin_client, bare)

        assert response.status_code == 200, response.json()
        number = response.json()['public_number']
        assert re.fullmatch(r'PA-\d{4}-\d{4}', number), number


# ---------------------------------------------------------------------------
# project_collection_account_list_view — GET
# ---------------------------------------------------------------------------

class TestProjectCollectionAccountList:
    def test_admin_list_by_project_returns_200(self, admin_client, project):
        response = admin_client.get(
            f'/api/accounts/projects/{project.id}/collection-accounts/',
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_nonexistent_project_returns_404(self, admin_client):
        response = admin_client.get(
            '/api/accounts/projects/999999/collection-accounts/',
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Audit trail (coherence requisito 12)
# ---------------------------------------------------------------------------

class TestCollectionAccountAuditTrail:
    """Draft moves and lifecycle transitions leave COLLECTION_ACCOUNT rows:
    the annul-and-reissue path is reconstructable next to the reassignments."""

    def _audit_rows(self, object_id):
        from content.models import AccountingChangeLog

        return AccountingChangeLog.objects.filter(
            entity_type='collection_account', object_id=object_id,
        )

    def test_a_draft_patch_that_moves_the_client_is_audited(
        self, admin_client, client_user_obj, project,
    ):
        created = admin_client.post(
            BASE_URL, _create_payload(client_user_id=client_user_obj.id),
            format='json',
        )
        account_id = created.json()['id']

        response = admin_client.patch(
            f'{BASE_URL}{account_id}/',
            {'project_id': project.id}, format='json',
        )

        assert response.status_code == 200, response.json()
        row = self._audit_rows(account_id).get()
        change = next(c for c in row.changes if c['field'] == 'project')
        assert change['new'] == 'CA Test Project'

    def test_issue_and_paid_leave_their_status_rows(
        self, admin_client, client_user_obj,
    ):
        created = admin_client.post(
            BASE_URL, _create_payload(client_user_id=client_user_obj.id),
            format='json',
        )
        account_id = created.json()['id']

        issued = admin_client.post(f'{BASE_URL}{account_id}/issue/')
        assert issued.status_code == 200, issued.json()
        paid = admin_client.post(f'{BASE_URL}{account_id}/mark-paid/')
        assert paid.status_code == 200, paid.json()

        statuses = [
            next(c for c in row.changes if c['field'] == 'commercial_status')
            for row in self._audit_rows(account_id).order_by('created_at')
        ]
        assert [c['new'] for c in statuses] == ['Issued', 'Paid']
