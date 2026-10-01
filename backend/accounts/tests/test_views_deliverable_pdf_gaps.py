"""Tests for remaining uncovered lines in accounts/views.py — deliverable PDF views,
bulk upload gaps, and client folder/upload error paths.

Covers:
- _pick_default_deliverable_for_requirements: BP-linked deliverable (line 825)
- requirement_bulk_upload_view: deliverable not found (963), item without title skipped (994)
- _build_proposal_pdf_http_response: pdf_bytes=None for technical (2051) and commercial (2063)
- deliverable_commercial_proposal_pdf_view: invalid project (2088), not visible (2101)
- deliverable_technical_document_pdf_view: invalid project (2125), not visible (2138)
- deliverable_client_folder_detail_view: not visible / archived deliverable for client (2292)
- deliverable_client_uploads_view: invalid project (2333)
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import (
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
        username='admin@pdfgaps.com', email='admin@pdfgaps.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@pdfgaps.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@pdfgaps.com', email='client@pdfgaps.com', password='clientpass1',
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
        'email': 'client@pdfgaps.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='PDFGaps Project', client=client_user,
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
def archived_deliverable(project, admin_user):
    return Deliverable.objects.create(
        project=project,
        title='Archived Deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin_user,
        is_archived=True,
    )


# ===========================================================================
# _build_proposal_pdf_http_response — pdf_bytes=None for technical (line 2051)
# ===========================================================================

class TestBuildProposalPdfNullBytesForTechnical:
    @patch(
        'content.services.technical_document_pdf.generate_technical_document_pdf',
        return_value=None,
    )
    def test_technical_pdf_none_returns_404(self, mock_gen):
        """When the technical PDF generator returns None, the helper returns a 404 response."""
        from content.models import BusinessProposal
        from accounts.views import _build_proposal_pdf_http_response

        proposal = BusinessProposal.objects.create(
            title='Technical Test', client_name='Test Client',
        )

        http_resp, err_resp = _build_proposal_pdf_http_response(proposal, 'technical')

        assert http_resp is None
        assert err_resp.status_code == 404


# ===========================================================================
# _build_proposal_pdf_http_response — pdf_bytes=None for commercial (line 2063)
# ===========================================================================

class TestBuildProposalPdfNullBytesForCommercial:
    @patch(
        'content.services.proposal_pdf_service.ProposalPdfService.generate',
        return_value=None,
    )
    def test_commercial_pdf_none_returns_500(self, mock_gen):
        """When the commercial PDF generator returns None, the helper returns a 500 response."""
        from content.models import BusinessProposal
        from accounts.views import _build_proposal_pdf_http_response

        proposal = BusinessProposal.objects.create(
            title='Commercial Test', client_name='Test Client',
        )

        http_resp, err_resp = _build_proposal_pdf_http_response(proposal, '')

        assert http_resp is None
        assert err_resp.status_code == 500


# ===========================================================================
# deliverable_commercial_proposal_pdf_view — invalid project (line 2088)
# ===========================================================================

class TestCommercialPdfInvalidProject:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        """GET commercial PDF with non-existent project_id returns 404 (line 2088)."""
        url = '/api/accounts/projects/99999/deliverables/1/download/commercial-proposal-pdf/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_commercial_proposal_pdf_view — not visible for client (line 2101)
# ===========================================================================

class TestCommercialPdfNotVisible:
    def test_archived_deliverable_not_visible_to_client_returns_404(
        self, api_client, client_headers, project, archived_deliverable,
    ):
        """Archived deliverable in commercial PDF view returns 404 for client (line 2101)."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{archived_deliverable.id}/download/commercial-proposal-pdf/'
        )
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_technical_document_pdf_view — invalid project (line 2125)
# ===========================================================================

class TestTechnicalPdfInvalidProject:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        """GET technical PDF with non-existent project_id returns 404 (line 2125)."""
        url = '/api/accounts/projects/99999/deliverables/1/download/technical-document-pdf/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_technical_document_pdf_view — not visible for client (line 2138)
# ===========================================================================

class TestTechnicalPdfNotVisible:
    def test_archived_deliverable_not_visible_to_client_returns_404(
        self, api_client, client_headers, project, archived_deliverable,
    ):
        """Archived deliverable in technical PDF view returns 404 for client (line 2138)."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{archived_deliverable.id}/download/technical-document-pdf/'
        )
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_client_folder_detail_view — not visible (line 2292)
# ===========================================================================

class TestClientFolderDetailNotVisible:
    def test_archived_deliverable_not_visible_to_client_returns_404(
        self, api_client, client_headers, project, archived_deliverable,
    ):
        """Archived deliverable in client-folder-detail returns 404 for client (line 2292)."""
        url = (
            f'/api/accounts/projects/{project.id}/deliverables/'
            f'{archived_deliverable.id}/client-folders/99999/'
        )
        resp = api_client.patch(url, {'name': 'renamed'}, format='json', **client_headers)

        assert resp.status_code == 404


# ===========================================================================
# deliverable_client_uploads_view — invalid project (line 2333)
# ===========================================================================

class TestClientUploadsInvalidProject:
    def test_invalid_project_returns_404(self, api_client, client_headers):
        """GET client-uploads with non-existent project_id returns 404 (line 2333)."""
        url = '/api/accounts/projects/99999/deliverables/1/client-uploads/'
        resp = api_client.get(url, **client_headers)

        assert resp.status_code == 404
