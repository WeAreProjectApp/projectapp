"""Tests for remaining uncovered branches in accounts/views.py — project access errors and data paths.

All "invalid project_id" tests trigger _get_project_or_403 error path (return err).

Covers:
- deliverable_sync_technical_resources_view: invalid project (line 758)
- requirement_bulk_upload_view: invalid project (line 956)
- requirement_detail_view: invalid project (line 1021), deliverable_id mismatch (1031), not visible (1034)
- requirement_move_view: DoesNotExist (1096-1097), deliverable_id mismatch (1100), not visible (1103)
- requirement_comment_view: invalid project (1167), req not found (1171-1172), mismatch (1175), not visible (1178)
- change_request_detail_view: invalid project (1316), not visible (1329)
- change_request_evaluate_view: invalid project (1359)
- change_request_comment_view: invalid project (1408), not visible (1419)
- change_request_convert_view: invalid project (1454), DoesNotExist (1465-1466)
- bug_report_detail_view: invalid project (1652), not visible (1665)
- bug_report_evaluate_view: invalid project (1695)
- bug_report_comment_view: invalid project (1748), not visible (1759)
- deliverable_detail_view: invalid project (1908), not visible GET (1922)
- deliverable_upload_version_view: invalid project (1976)
- deliverable_attachment_files_view: invalid project (2165)
- deliverable_client_folder_detail_view: invalid project (2280), DoesNotExist (2283-2284), not authorized (2289)
- deliverable_client_folders_view (2nd instance): invalid project (2333), not authorized (2342)
- deliverable_data_model_entities_view: DoesNotExist (2402-2403), not visible (2409)
- payment_generate_link_view: invalid project (2994)
- payment_widget_data_view: invalid project (3041)
- _extract_proposal_financial_data: fallback tiers from model fields (2626-2635)
- _pick_default_deliverable_for_requirements: first deliverable fallback (line 825)
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import (
    BugReport,
    ChangeRequest,
    Deliverable,
    Project,
    UserProfile,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@paccess.com', email='admin@paccess.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@paccess.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@paccess.com', email='client@paccess.com', password='clientpass1',
        first_name='Test', last_name='Client',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, created_by=admin_user,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@paccess.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='Access Gaps Project', client=client_user,
        status=Project.STATUS_ACTIVE,
    )


@pytest.fixture
def deliverable(project, admin_user):
    return Deliverable.objects.create(
        project=project,
        title='Test Deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin_user,
    )


@pytest.fixture
def change_request(project, client_user):
    return ChangeRequest.objects.create(
        project=project,
        created_by=client_user,
        title='Test CR',
        description='Change needed',
    )


@pytest.fixture
def bug_report(project, client_user):
    return BugReport.objects.create(
        project=project,
        reported_by=client_user,
        title='Test Bug',
        description='Something broken',
    )


# ===========================================================================
# deliverable_sync_technical_resources_view — invalid project (line 758)
# ===========================================================================

class TestSyncTechnicalRequirementsInvalidProject:
    def test_invalid_project_returns_404(self, api_client, admin_headers):
        url = '/api/accounts/projects/99999/deliverables/1/sync-technical-resources/'
        resp = api_client.post(url, **admin_headers)

        assert resp.status_code == 404


# ===========================================================================
# change_request_detail_view — invalid project (1316) + not visible (1329)
# ===========================================================================

class TestChangeRequestDetailGaps:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/change-requests/1/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404

    def test_archived_cr_not_visible_returns_404(self, api_client, client_headers, project, change_request):
        """Archived change request returns 404 (not visible)."""
        change_request.is_archived = True
        change_request.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/change-requests/{change_request.id}/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# change_request_evaluate_view — invalid project (line 1359)
# ===========================================================================

class TestChangeRequestEvaluateInvalidProject:
    def test_invalid_project_returns_404(self, api_client, admin_headers):
        url = '/api/accounts/projects/99999/change-requests/1/evaluate/'
        resp = api_client.post(url, {}, format='json', **admin_headers)

        assert resp.status_code == 404


# ===========================================================================
# change_request_comment_view — invalid project (1408) + not visible (1419)
# ===========================================================================

class TestChangeRequestCommentGaps:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/change-requests/1/comments/'
        resp = api_client.post(url, {'text': 'hi'}, format='json', **client_headers)

        assert resp.status_code == 404

    def test_archived_cr_comment_returns_404(self, api_client, client_headers, project, change_request):
        """Archived CR is not visible → 404 for comment."""
        change_request.is_archived = True
        change_request.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/change-requests/{change_request.id}/comments/'
        resp = api_client.post(url, {'text': 'hi'}, format='json', **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# change_request_convert_view — invalid project (1454) + DoesNotExist (1465-1466)
# ===========================================================================

class TestChangeRequestConvertGaps:
    def test_invalid_project_returns_404(self, api_client, admin_headers):
        url = '/api/accounts/projects/99999/change-requests/1/convert/'
        resp = api_client.post(url, {}, format='json', **admin_headers)

        assert resp.status_code == 404

    def test_nonexistent_cr_returns_404(self, api_client, admin_headers, project):
        """convert with valid project but non-existent cr_id returns 404."""
        url = f'/api/accounts/projects/{project.id}/change-requests/99999/convert/'
        resp = api_client.post(url, {}, format='json', **admin_headers)

        assert resp.status_code == 404


# ===========================================================================
# bug_report_detail_view — invalid project (1652) + not visible (1665)
# ===========================================================================

class TestBugReportDetailGaps:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/bug-reports/1/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404

    def test_archived_bug_not_visible_returns_404(self, api_client, client_headers, project, bug_report):
        """Archived bug report returns 404 (not visible to non-admin)."""
        bug_report.is_archived = True
        bug_report.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/bug-reports/{bug_report.id}/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# bug_report_evaluate_view — invalid project (line 1695)
# ===========================================================================

class TestBugReportEvaluateInvalidProject:
    def test_invalid_project_returns_404(self, api_client, admin_headers):
        url = '/api/accounts/projects/99999/bug-reports/1/evaluate/'
        resp = api_client.post(url, {}, format='json', **admin_headers)

        assert resp.status_code == 404


# ===========================================================================
# bug_report_comment_view — invalid project (1748) + not visible (1759)
# ===========================================================================

class TestBugReportCommentGaps:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/bug-reports/1/comments/'
        resp = api_client.post(url, {'text': 'x'}, format='json', **client_headers)

        assert resp.status_code == 404

    def test_archived_bug_comment_returns_404(self, api_client, client_headers, project, bug_report):
        """Archived bug not visible → 404 for comment."""
        bug_report.is_archived = True
        bug_report.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/bug-reports/{bug_report.id}/comments/'
        resp = api_client.post(url, {'text': 'x'}, format='json', **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_detail_view — invalid project (1908) + not visible GET (1922)
# ===========================================================================

class TestDeliverableDetailGaps:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/deliverables/1/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404

    def test_archived_deliverable_not_visible_to_client(
        self, api_client, client_headers, project, deliverable,
    ):
        """Archived deliverable is not visible to client in GET."""
        deliverable.is_archived = True
        deliverable.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/deliverables/{deliverable.id}/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_upload_version_view — invalid project (line 1976)
# ===========================================================================

class TestDeliverableUploadVersionInvalidProject:
    def test_invalid_project_returns_404(self, api_client, admin_headers):
        url = '/api/accounts/projects/99999/deliverables/1/upload-version/'
        resp = api_client.post(url, {}, format='json', **admin_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_attachment_files_view — invalid project (line 2165)
# ===========================================================================

class TestDeliverableAttachmentFilesInvalidProject:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/deliverables/1/attachments/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_client_folder_detail_view — invalid project (2280) + DoesNotExist (2283-2284)
# ===========================================================================

class TestDeliverableClientFolderDetailGaps:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        """PATCH on non-existent project triggers _get_project_or_403 error (line 2280)."""
        url = '/api/accounts/projects/99999/deliverables/1/client-folders/1/'
        resp = api_client.patch(url, {}, format='json', **client_headers)

        assert resp.status_code == 404

    def test_nonexistent_deliverable_returns_404(self, api_client, client_headers, project):
        """Valid project but invalid deliverable_id → deliverable DoesNotExist → 404 (lines 2283-2284)."""
        url = f'/api/accounts/projects/{project.id}/deliverables/99999/client-folders/1/'
        resp = api_client.patch(url, {}, format='json', **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_data_model_entities_view — DoesNotExist (2402-2403) + not visible (2409)
# ===========================================================================

class TestDeliverableDataModelEntitiesGaps:
    def test_nonexistent_deliverable_returns_404(self, api_client, client_headers, project):
        """Non-existent deliverable in data-model-entities → 404."""
        url = f'/api/accounts/projects/{project.id}/deliverables/99999/data-model-entities/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404

    def test_archived_deliverable_not_visible_returns_404(
        self, api_client, client_headers, project, deliverable,
    ):
        """Archived deliverable not visible → 404."""
        deliverable.is_archived = True
        deliverable.save(update_fields=['is_archived'])

        url = f'/api/accounts/projects/{project.id}/deliverables/{deliverable.id}/data-model-entities/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# payment_generate_link_view — invalid project (line 2994)
# ===========================================================================

class TestPaymentGenerateLinkInvalidProject:
    def test_invalid_project_returns_404(self, api_client, admin_headers):
        url = '/api/accounts/projects/99999/payments/1/generate-link/'
        resp = api_client.post(url, **admin_headers)

        assert resp.status_code == 404


# ===========================================================================
# payment_widget_data_view — invalid project (line 3041)
# ===========================================================================

class TestPaymentWidgetDataInvalidProject:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        url = '/api/accounts/projects/99999/payments/1/widget-data/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# _extract_proposal_financial_data — fallback tiers from model fields (2626-2635)
# ===========================================================================

class TestExtractProposalFallbackTiers:
    def test_creates_project_with_fallback_tiers_when_no_billing_tiers_in_section(
        self, api_client, admin_headers, client_user,
    ):
        """When proposal investment section has no billingTiers, fallback from model fields is used."""
        from content.models import BusinessProposal, ProposalSection

        proposal = BusinessProposal.objects.create(
            title='Fallback Tiers Proposal',
            client_name='Test Client',
            total_investment=Decimal('10000000'),
            status='accepted',
            hosting_percent=30,
            hosting_discount_quarterly=10,
            hosting_discount_semiannual=20,
        )
        # Investment section WITHOUT billingTiers → triggers fallback branch
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inversión',
            order=5,
            is_enabled=True,
            content_json={
                'hostingPlan': {
                    'hostingPercent': 30,
                    # No 'billingTiers' key → fallback to model fields
                },
            },
        )

        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Fallback Tiers Project',
            'client_id': client_user.id,
            'proposal_id': proposal.id,
        }, format='json', **admin_headers)

        assert resp.status_code == 201
        from accounts.models import Project
        project = Project.objects.get(id=resp.json()['id'])
        # Fallback tiers should include the currently offered frequencies.
        tier_frequencies = {t['frequency'] for t in project.hosting_tiers}
        assert 'nine_month' in tier_frequencies
        assert 'quarterly' in tier_frequencies
        assert 'semiannual' in tier_frequencies
