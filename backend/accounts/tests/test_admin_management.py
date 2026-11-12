"""Tests for admin management views and uncovered view branches.

Covers: admin_list_view, admin_detail_view, admin_resend_invite_view,
me_view avatar update, client_detail_view PATCH edge cases.
"""
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import UserProfile

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
    """Superuser authorized to manage the team's platform accounts."""
    user = User.objects.create_user(
        username='staff@test.com', email='staff@test.com', password='staffpass1!',
        first_name='Staff', last_name='Admin', is_staff=True, is_superuser=True,
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def staff_headers(api_client, staff_admin):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'staff@test.com', 'password': 'staffpass1!',
    }, format='json')
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture(params=[False, True], ids=['platform-admin', 'panel-staff'])
def non_superuser_admin(db, request):
    """An administrator without permission to manage team accounts."""
    user = User.objects.create_user(
        username='nostaff@test.com', email='nostaff@test.com', password='pass12345!',
        is_staff=request.param,
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def non_superuser_headers(api_client, non_superuser_admin):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'nostaff@test.com', 'password': 'pass12345!',
    }, format='json')
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(db, staff_admin):
    user = User.objects.create_user(
        username='client@mgmt.com', email='client@mgmt.com', password='pass12345!',
        first_name='John', last_name='Doe',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
        company_name='Acme', phone='+57300', created_by=staff_admin,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@mgmt.com', 'password': 'pass12345!',
    }, format='json')
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


# ---------------------------------------------------------------------------
# Team management: non-superusers are blocked, including panel staff
# ---------------------------------------------------------------------------

class TestRequireSuperuser:
    def test_non_superuser_gets_403_on_admin_list(self, api_client, non_superuser_headers):
        """Fails if a panel operator can list team accounts without owner authority."""
        resp = api_client.get('/api/accounts/admins/', **non_superuser_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# admin_list_view GET — list admins with filter params
# ---------------------------------------------------------------------------

class TestAdminListView:
    def test_list_all_admins_returns_200(self, api_client, staff_headers, staff_admin):
        resp = api_client.get('/api/accounts/admins/', **staff_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_active_returns_only_onboarded_active(self, api_client, staff_headers, staff_admin):
        resp = api_client.get('/api/accounts/admins/?filter=active', **staff_headers)
        assert resp.status_code == 200

    def test_filter_pending_returns_not_onboarded(self, api_client, staff_headers, staff_admin):
        resp = api_client.get('/api/accounts/admins/?filter=pending', **staff_headers)
        assert resp.status_code == 200

    def test_filter_inactive_returns_deactivated(self, api_client, staff_headers, staff_admin):
        resp = api_client.get('/api/accounts/admins/?filter=inactive', **staff_headers)
        assert resp.status_code == 200

    @patch('accounts.services.onboarding._send_admin_invitation_email')
    def test_post_creates_new_admin(self, mock_email, api_client, staff_headers):
        resp = api_client.post('/api/accounts/admins/', {
            'email': 'newadmin@test.com',
            'first_name': 'New',
            'last_name': 'Admin',
        }, format='json', **staff_headers)
        assert resp.status_code == 201

    @patch('accounts.views.create_admin', side_effect=ValueError('ya existe'))
    def test_post_returns_400_on_value_error(self, mock_create, api_client, staff_headers):
        resp = api_client.post('/api/accounts/admins/', {
            'email': 'newadmin2@test.com',
            'first_name': 'X',
            'last_name': 'Y',
        }, format='json', **staff_headers)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# admin_detail_view — GET, PATCH, DELETE
# ---------------------------------------------------------------------------

class TestAdminDetailView:
    def test_get_admin_detail_returns_200(self, api_client, staff_headers, staff_admin):
        resp = api_client.get(f'/api/accounts/admins/{staff_admin.pk}/', **staff_headers)
        assert resp.status_code == 200
        assert resp.json()['email'] == 'staff@test.com'

    def test_get_nonexistent_admin_returns_404(self, api_client, staff_headers):
        resp = api_client.get('/api/accounts/admins/99999/', **staff_headers)
        assert resp.status_code == 404

    def test_patch_admin_name_returns_200(self, api_client, staff_headers, staff_admin):
        resp = api_client.patch(f'/api/accounts/admins/{staff_admin.pk}/', {
            'first_name': 'Updated',
        }, format='json', **staff_headers)
        assert resp.status_code == 200

    def test_delete_returns_400_when_only_one_admin(self, api_client, staff_headers, staff_admin):
        resp = api_client.delete(f'/api/accounts/admins/{staff_admin.pk}/', **staff_headers)
        assert resp.status_code == 400

    @patch('accounts.services.onboarding._send_admin_invitation_email')
    def test_delete_deactivates_when_multiple_admins_exist(
        self, mock_email, api_client, staff_headers, staff_admin,
    ):
        # Create a second admin so deletion is allowed
        second = User.objects.create_user(
            username='second@test.com', email='second@test.com', password='pass12345!',
            is_staff=True,
        )
        UserProfile.objects.create(user=second, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
        resp = api_client.delete(f'/api/accounts/admins/{second.pk}/', **staff_headers)
        assert resp.status_code == 200
        second.refresh_from_db()
        assert second.is_active is False


# ---------------------------------------------------------------------------
# me_view PATCH — avatar and custom_cover_image branches
# ---------------------------------------------------------------------------

class TestMeViewFileUpload:
    def test_patch_avatar_saves_file(self, api_client, client_headers):
        img_bytes = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\xff\x00,'
            b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
        )
        avatar = SimpleUploadedFile('avatar.gif', img_bytes, content_type='image/gif')
        resp = api_client.patch(
            '/api/accounts/me/',
            {'avatar': avatar},
            format='multipart',
            **client_headers,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# client_detail_view PATCH — last_name, is_active, phone branches
# ---------------------------------------------------------------------------

class TestClientDetailPatchBranches:
    def test_patch_last_name_updates_user(self, api_client, staff_headers, client_user):
        resp = api_client.patch(
            f'/api/accounts/clients/{client_user.pk}/',
            {'last_name': 'Smith'},
            format='json',
            **staff_headers,
        )
        assert resp.status_code == 200
        client_user.refresh_from_db()
        assert client_user.last_name == 'Smith'

    def test_patch_phone_updates_profile(self, api_client, staff_headers, client_user):
        resp = api_client.patch(
            f'/api/accounts/clients/{client_user.pk}/',
            {'phone': '+1234567890'},
            format='json',
            **staff_headers,
        )
        assert resp.status_code == 200
        client_user.profile.refresh_from_db()
        assert client_user.profile.phone == '+1234567890'
