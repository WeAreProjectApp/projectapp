"""Tests targeting specific uncovered branches in accounts/views.py.

Covers: cover_gallery_view, admin_resend_invite_view,
proposal_list_for_selector_view, notification_list_view invalid limit,
admin_detail_view PATCH is_active=False last-admin guard.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import Notification, Project, UserProfile

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_admin(db):
    user = User.objects.create_user(
        username='staff@cgap.com', email='staff@cgap.com', password='staffpass1!',
        is_staff=True, is_superuser=True,
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def staff_headers(api_client, staff_admin):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'staff@cgap.com', 'password': 'staffpass1!',
    }, format='json')
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='admin@cgap.com', email='admin@cgap.com', password='adminpass1!',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@cgap.com', 'password': 'adminpass1!',
    }, format='json')
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(db, admin_user):
    user = User.objects.create_user(
        username='client@cgap.com', email='client@cgap.com', password='clientpass1!',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
        created_by=admin_user,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@cgap.com', 'password': 'clientpass1!',
    }, format='json')
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


# ===========================================================================
# cover_gallery_view
# ===========================================================================

class TestCoverGalleryView:
    @override_settings(STATICFILES_DIRS=['/fake'])
    def test_returns_empty_list_when_gallery_dir_missing(
        self, api_client, admin_headers,
    ):
        with patch('os.path.isdir', return_value=False):
            resp = api_client.get('/api/accounts/cover-gallery/', **admin_headers)

        assert resp.status_code == 200
        assert resp.json() == []

    @override_settings(STATICFILES_DIRS=['/fake'])
    def test_returns_categories_with_images(
        self, api_client, admin_headers,
    ):
        import os

        gallery_dir = '/fake/cover_gallery'
        category_dir = os.path.join(gallery_dir, 'abstract')
        image_path = os.path.join(category_dir, 'imgi_01_dark_wave.jpg')

        fake_dirs = {gallery_dir, category_dir}
        fake_listdir = {
            gallery_dir: ['abstract'],
            category_dir: ['imgi_01_dark_wave.jpg'],
        }

        def mock_isdir(path):
            return path in fake_dirs

        def mock_listdir(path):
            return fake_listdir.get(path, [])

        with (
            patch('os.path.isdir', side_effect=mock_isdir),
            patch('os.listdir', side_effect=mock_listdir),
        ):
            resp = api_client.get('/api/accounts/cover-gallery/', **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['name'] == 'abstract'
        assert len(data[0]['images']) == 1
        assert data[0]['images'][0]['filename'] == 'imgi_01_dark_wave.jpg'
        assert data[0]['images'][0]['name'] == 'Dark Wave'

    @override_settings(STATICFILES_DIRS=['/fake'])
    def test_skips_non_image_files_in_category(
        self, api_client, admin_headers,
    ):
        import os

        gallery_dir = '/fake/cover_gallery'
        category_dir = os.path.join(gallery_dir, 'nature')

        fake_dirs = {gallery_dir, category_dir}
        fake_listdir = {
            gallery_dir: ['nature'],
            category_dir: ['readme.txt', 'photo.jpg'],
        }

        def mock_isdir(path):
            return path in fake_dirs

        def mock_listdir(path):
            return fake_listdir.get(path, [])

        with (
            patch('os.path.isdir', side_effect=mock_isdir),
            patch('os.listdir', side_effect=mock_listdir),
        ):
            resp = api_client.get('/api/accounts/cover-gallery/', **admin_headers)

        data = resp.json()
        assert len(data) == 1
        assert len(data[0]['images']) == 1
        assert data[0]['images'][0]['filename'] == 'photo.jpg'

    @override_settings(STATICFILES_DIRS=['/fake'])
    def test_skips_non_directory_entries_in_gallery(
        self, api_client, admin_headers,
    ):
        import os

        gallery_dir = '/fake/cover_gallery'
        readme_path = os.path.join(gallery_dir, 'README.md')

        fake_listdir = {
            gallery_dir: ['README.md'],
        }

        def mock_isdir(path):
            # gallery_dir exists, README.md is a file
            return path == gallery_dir

        def mock_listdir(path):
            return fake_listdir.get(path, [])

        with (
            patch('os.path.isdir', side_effect=mock_isdir),
            patch('os.listdir', side_effect=mock_listdir),
        ):
            resp = api_client.get('/api/accounts/cover-gallery/', **admin_headers)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthenticated_request_rejected(self, api_client):
        resp = api_client.get('/api/accounts/cover-gallery/')

        assert resp.status_code == 401


# ===========================================================================
# admin_resend_invite_view
# ===========================================================================

class TestAdminResendInviteView:
    @patch('accounts.views.resend_invitation')
    def test_staff_user_resends_admin_invitation(
        self, mock_resend, api_client, staff_headers, staff_admin,
    ):
        resp = api_client.post(
            f'/api/accounts/admins/{staff_admin.pk}/resend-invite/',
            **staff_headers,
        )

        assert resp.status_code == 200
        assert resp.json()['detail'] == 'Invitación reenviada.'
        mock_resend.assert_called_once_with(staff_admin)

    def test_resend_invite_for_nonexistent_admin_returns_404(
        self, api_client, staff_headers,
    ):
        resp = api_client.post(
            '/api/accounts/admins/99999/resend-invite/',
            **staff_headers,
        )

        assert resp.status_code == 404

    def test_non_staff_user_cannot_resend_admin_invite(
        self, api_client, admin_headers, staff_admin,
    ):
        resp = api_client.post(
            f'/api/accounts/admins/{staff_admin.pk}/resend-invite/',
            **admin_headers,
        )

        assert resp.status_code == 403


# ===========================================================================
# proposal_list_for_selector_view
# ===========================================================================

class TestProposalListForSelectorView:
    def test_returns_empty_list_when_no_eligible_proposals(
        self, api_client, admin_headers,
    ):
        resp = api_client.get('/api/accounts/proposals/', **admin_headers)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_accepted_proposals_without_deliverable(
        self, api_client, admin_headers,
    ):
        from content.models import BusinessProposal

        BusinessProposal.objects.create(
            title='Open Proposal', status='accepted', slug='open-prop',
        )

        resp = api_client.get('/api/accounts/proposals/', **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['title'] == 'Open Proposal'

    def test_includes_finished_proposals_without_deliverable(
        self, api_client, admin_headers,
    ):
        from content.models import BusinessProposal

        BusinessProposal.objects.create(
            title='Finished Proposal', status='finished', slug='finished-prop',
        )

        resp = api_client.get('/api/accounts/proposals/', **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['title'] == 'Finished Proposal'

    def test_excludes_proposals_with_deliverable_linked(
        self, api_client, admin_headers, admin_user, client_user,
    ):
        from accounts.models import Deliverable
        from content.models import BusinessProposal
        from django.core.files.base import ContentFile

        project = Project.objects.create(
            name='P', client=client_user, status=Project.STATUS_ACTIVE,
        )
        d = Deliverable.objects.create(
            project=project, title='Linked', category=Deliverable.CATEGORY_DOCUMENTS,
            file=ContentFile(b'pdf', name='linked.pdf'),
            uploaded_by=admin_user,
        )
        BusinessProposal.objects.create(
            title='Linked Proposal', status='accepted',
            slug='linked-prop', deliverable=d,
        )

        resp = api_client.get('/api/accounts/proposals/', **admin_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_client_cannot_access_proposals_for_selector(
        self, api_client, client_headers,
    ):
        resp = api_client.get('/api/accounts/proposals/', **client_headers)

        assert resp.status_code == 403


# ===========================================================================
# notification_list_view — invalid limit parameter
# ===========================================================================

class TestNotificationListInvalidLimit:
    def test_invalid_limit_is_ignored_and_returns_all(
        self, api_client, client_headers, client_user,
    ):
        project = Project.objects.create(
            name='P', client=client_user, status=Project.STATUS_ACTIVE,
        )
        for i in range(3):
            Notification.objects.create(
                user=client_user, type=Notification.TYPE_GENERAL,
                title=f'Notif {i}', project=project,
            )

        resp = api_client.get(
            '/api/accounts/notifications/?limit=not-a-number',
            **client_headers,
        )

        assert resp.status_code == 200
        assert len(resp.json()) == 3


# ===========================================================================
# admin_detail_view PATCH — is_active=False last-admin guard
# ===========================================================================

class TestAdminDetailPatchLastAdminGuard:
    def test_patch_is_active_false_blocked_when_only_one_admin(
        self, api_client, staff_headers, staff_admin,
    ):
        resp = api_client.patch(
            f'/api/accounts/admins/{staff_admin.pk}/',
            {'is_active': False},
            format='json',
            **staff_headers,
        )

        assert resp.status_code == 400
        assert 'último administrador' in resp.json()['detail']

    def test_patch_is_active_false_succeeds_when_multiple_admins_exist(
        self, api_client, staff_headers, staff_admin,
    ):
        second = User.objects.create_user(
            username='second@cgap.com', email='second@cgap.com', password='pass123!',
        )
        UserProfile.objects.create(
            user=second, role=UserProfile.ROLE_ADMIN, is_onboarded=True,
        )

        resp = api_client.patch(
            f'/api/accounts/admins/{second.pk}/',
            {'is_active': False},
            format='json',
            **staff_headers,
        )

        assert resp.status_code == 200
        second.refresh_from_db()
        assert second.is_active is False

    def test_patch_last_name_updates_admin(
        self, api_client, staff_headers, staff_admin,
    ):
        resp = api_client.patch(
            f'/api/accounts/admins/{staff_admin.pk}/',
            {'last_name': 'NewLast'},
            format='json',
            **staff_headers,
        )

        assert resp.status_code == 200
        staff_admin.refresh_from_db()
        assert staff_admin.last_name == 'NewLast'
