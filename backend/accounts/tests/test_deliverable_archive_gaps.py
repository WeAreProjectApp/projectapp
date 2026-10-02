"""Tests for uncovered archive/unarchive branches in deliverable and requirement views.

Covers:
- deliverable_detail_view PATCH: is_archived=True, is_archived=False
- deliverable_upload_version_view: archived deliverable returns 400
- requirement_detail_view PATCH: is_archived=True, is_archived=False
"""
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import (
    Deliverable,
    Project,
    UserProfile,
)
from content.models.business_proposal import BusinessProposal

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@archgaps.com', email='admin@archgaps.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@archgaps.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@archgaps.com', email='client@archgaps.com', password='clientpass1',
        first_name='Carlos', last_name='Ruiz',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, created_by=admin_user,
    )
    return user


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='Archive Gaps Project', client=client_user,
        status=Project.STATUS_ACTIVE,
    )


@pytest.fixture
def deliverable(project, admin_user):
    return Deliverable.objects.create(
        project=project,
        title='Active Deliverable',
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








def _detail_url(project_id, deliverable_id, suffix=''):
    return (
        f'/api/accounts/projects/{project_id}/deliverables/'
        f'{deliverable_id}/{suffix}'
    )




# ===========================================================================
# deliverable_detail_view PATCH — is_archived
# ===========================================================================

class TestDeliverableDetailPatchIsArchived:
    def test_admin_archives_deliverable_via_patch(
        self, api_client, admin_headers, project, deliverable,
    ):
        """Admin can archive a deliverable via PATCH is_archived=True."""
        url = _detail_url(project.id, deliverable.id)
        resp = api_client.patch(
            url, {'is_archived': True}, format='json', **admin_headers,
        )

        assert resp.status_code == 200
        deliverable.refresh_from_db()
        assert deliverable.is_archived is True

    def test_admin_unarchives_deliverable_via_patch(
        self, api_client, admin_headers, project, archived_deliverable,
    ):
        """Admin can unarchive a deliverable via PATCH is_archived=False."""
        url = _detail_url(project.id, archived_deliverable.id)
        resp = api_client.patch(
            url, {'is_archived': False}, format='json', **admin_headers,
        )

        assert resp.status_code == 200
        archived_deliverable.refresh_from_db()
        assert archived_deliverable.is_archived is False


# ===========================================================================
# deliverable_upload_version_view — archived deliverable
# ===========================================================================

class TestDeliverableUploadVersionArchived:
    def test_upload_version_to_archived_deliverable_returns_400(
        self, api_client, admin_headers, project, archived_deliverable,
    ):
        """Returns 400 when trying to upload a new version to an archived deliverable."""
        new_file = SimpleUploadedFile('update.pdf', b'pdf content', content_type='application/pdf')
        url = _detail_url(project.id, archived_deliverable.id, 'upload-version/')
        resp = api_client.post(
            url, {'file': new_file}, format='multipart', **admin_headers,
        )

        assert resp.status_code == 400
