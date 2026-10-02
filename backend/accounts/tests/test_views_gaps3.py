"""Tests for remaining uncovered branches in accounts/views.py — third batch.

Covers:
- deliverable_commercial_proposal_pdf_view: 404 (no deliverable, no BP)
- deliverable_technical_document_pdf_view: 404 (no deliverable, no BP), 410 (expired)
- change_request_convert_view: archived CR returns 400
- project_list_view: admin filters by client_id and status query params
- bug_report_all_view: severity_filter in global endpoint
- project_list_view: admin GET with client_filter query param
"""
from decimal import Decimal
from unittest.mock import patch
import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    ChangeRequest,
    Deliverable,
    Project,
    UserProfile,
    BugReport,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@gaps3.com', email='admin@gaps3.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@gaps3.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@gaps3.com', email='client@gaps3.com', password='clientpass1',
        first_name='Carlos', last_name='Ruiz',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, created_by=admin_user,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@gaps3.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='Gaps3 Project', client=client_user,
        status=Project.STATUS_ACTIVE,
    )


@pytest.fixture
def deliverable(project, admin_user):
    return Deliverable.objects.create(
        project=project,
        title='Main Deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin_user,
    )


@pytest.fixture
def deliverable_with_bp(project, admin_user):
    """Deliverable linked to an accepted BusinessProposal."""
    from content.models import BusinessProposal
    d = Deliverable.objects.create(
        project=project,
        title='Proposal Deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin_user,
    )
    bp = BusinessProposal.objects.create(
        title='Test Proposal',
        client_name='Test Client',
        total_investment=Decimal('5000000'),
        status='accepted',
        deliverable=d,
    )
    d._test_bp = bp  # store for reference in tests
    return d


@pytest.fixture
def deliverable_with_expired_bp(project, admin_user):
    """Deliverable linked to an expired BusinessProposal."""
    from content.models import BusinessProposal
    d = Deliverable.objects.create(
        project=project,
        title='Expired Proposal Deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin_user,
    )
    bp = BusinessProposal.objects.create(
        title='Expired Proposal',
        client_name='Test Client',
        total_investment=Decimal('5000000'),
        status='accepted',
        expires_at=timezone.now() - datetime.timedelta(days=10),
        deliverable=d,
    )
    d._test_bp = bp
    return d


# ===========================================================================
# deliverable_commercial_proposal_pdf_view — 404 cases
# ===========================================================================

class TestDeliverableCommercialProposalPdfView:
    def test_returns_404_when_deliverable_not_found(
        self, api_client, admin_headers, project,
    ):
        """Returns 404 when deliverable_id does not exist in the project."""
        url = f'/api/accounts/projects/{project.id}/deliverables/99999/download/commercial-proposal-pdf/'
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 404

    def test_returns_404_when_deliverable_has_no_business_proposal(
        self, api_client, admin_headers, project, deliverable,
    ):
        """Returns 404 when deliverable exists but has no business proposal linked."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{deliverable.id}/download/commercial-proposal-pdf/'
        )
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 404

    def test_returns_410_when_proposal_is_expired(
        self, api_client, admin_headers, project, deliverable_with_expired_bp,
    ):
        """Returns 410 when the linked proposal has expired."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{deliverable_with_expired_bp.id}/download/commercial-proposal-pdf/'
        )
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 410


# ===========================================================================
# deliverable_technical_document_pdf_view — 404 cases
# ===========================================================================

class TestDeliverableTechnicalDocumentPdfView:
    def test_returns_404_when_deliverable_not_found(
        self, api_client, admin_headers, project,
    ):
        """Returns 404 when deliverable_id does not exist in the project."""
        url = f'/api/accounts/projects/{project.id}/deliverables/99999/download/technical-document-pdf/'
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 404

    def test_returns_404_when_deliverable_has_no_business_proposal(
        self, api_client, admin_headers, project, deliverable,
    ):
        """Returns 404 when deliverable exists but has no business proposal linked."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{deliverable.id}/download/technical-document-pdf/'
        )
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 404

    def test_returns_410_when_proposal_is_expired(
        self, api_client, admin_headers, project, deliverable_with_expired_bp,
    ):
        """Returns 410 when the linked proposal has expired."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{deliverable_with_expired_bp.id}/download/technical-document-pdf/'
        )
        resp = api_client.get(url, **admin_headers)

        assert resp.status_code == 410


# ===========================================================================
# change_request_convert_view — archived CR
# ===========================================================================

class TestChangeRequestConvertArchivedCr:
    def test_archived_cr_returns_400(
        self, api_client, admin_headers, project, admin_user,
    ):
        """Archived change request cannot be converted — returns 400."""
        cr = ChangeRequest.objects.create(
            project=project,
            created_by=admin_user,
            title='Archived CR',
            status=ChangeRequest.STATUS_APPROVED,
            is_archived=True,
        )
        url = f'/api/accounts/projects/{project.id}/change-requests/{cr.id}/convert/'
        resp = api_client.post(url, **admin_headers)

        assert resp.status_code == 400
        cr.refresh_from_db()
        assert cr.is_archived is True
        assert cr.linked_requirement_id is None
        assert cr.issue_events.count() == 0


# ===========================================================================
# project_list_view — admin filters (GET)
# ===========================================================================

class TestProjectListViewAdminFilters:
    def test_admin_filters_projects_by_client_id(
        self, api_client, admin_headers, client_user, project,
    ):
        """Admin can filter projects by client_id query param."""
        other_client = User.objects.create_user(
            username='other@gaps3.com', email='other@gaps3.com', password='pass1',
        )
        UserProfile.objects.create(
            user=other_client, role=UserProfile.ROLE_CLIENT,
            is_onboarded=True, created_by=User.objects.filter(
                profile__role=UserProfile.ROLE_ADMIN,
            ).first(),
        )
        Project.objects.create(
            name='Other Project', client=other_client,
            status=Project.STATUS_ACTIVE,
        )

        resp = api_client.get(
            f'/api/accounts/projects/?client={client_user.id}', **admin_headers,
        )

        assert resp.status_code == 200
        project_ids = [p['id'] for p in resp.json()]
        assert project.id in project_ids
        # All returned projects belong to the filtered client
        for p in resp.json():
            assert p['client_id'] == client_user.id

    def test_admin_filters_projects_by_status(
        self, api_client, admin_headers, client_user, project,
    ):
        """Admin can filter projects by status query param."""
        Project.objects.create(
            name='Archived Project', client=client_user,
            status=Project.STATUS_ARCHIVED,
        )

        resp = api_client.get(
            '/api/accounts/projects/?status=active', **admin_headers,
        )

        assert resp.status_code == 200
        for p in resp.json():
            assert p['status'] == 'active'


# ===========================================================================
# bug_report_all_view — severity filter
# ===========================================================================

class TestBugReportAllViewSeverityFilter:
    def test_global_severity_filter_returns_matching_only(
        self, api_client, admin_headers, project, admin_user,
    ):
        """Global /bug-reports/ endpoint filters by severity query param."""
        BugReport.objects.create(
            project=project,
            reported_by=admin_user,
            title='Critical bug',
            severity=BugReport.SEVERITY_CRITICAL,
            status=BugReport.STATUS_REPORTED,
        )
        BugReport.objects.create(
            project=project,
            reported_by=admin_user,
            title='Low bug',
            severity=BugReport.SEVERITY_LOW,
            status=BugReport.STATUS_REPORTED,
        )

        resp = api_client.get(
            '/api/accounts/bug-reports/?severity=critical', **admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert item['severity'] == 'critical'
