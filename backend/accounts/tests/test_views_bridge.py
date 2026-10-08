"""Only a CSRF-protected Panel session may bootstrap Platform authority."""
import pytest
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.test import RequestFactory
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.services.tokens import get_tokens_for_user

User = get_user_model()

BRIDGE_URL = '/api/accounts/session-token-bridge/'


@pytest.fixture
def api_client():
    """Provide an anonymous HTTP client for existing bridge contracts."""
    return APIClient()


@pytest.fixture
def staff_user():
    """Create a real Panel administrator with an existing Platform profile."""
    user = User.objects.create_user(
        username='staff@bridge.com', email='staff@bridge.com', password='staffpass1!',
        first_name='Staff', last_name='Bridge', is_staff=True,
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def non_staff_user():
    """Create a client without administrative Panel privileges."""
    user = User.objects.create_user(
        username='regular@bridge.com', email='regular@bridge.com', password='pass1!',
        first_name='Regular', last_name='User', is_staff=False,
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return user


@pytest.fixture
def staff_no_profile():
    """Create a Panel staff account before its first Platform visit."""
    return User.objects.create_user(
        username='bare@bridge.com', email='bare@bridge.com', password='barepass1!',
        first_name='Bare', last_name='Staff', is_staff=True,
    )


@pytest.mark.django_db
class TestSessionTokenBridge:
    """Pin session bootstrap without allowing JWT privilege restoration."""

    def test_staff_with_session_receives_jwt_tokens(self, api_client, staff_user):
        """Fails if authorized Panel navigation no longer creates a session."""
        api_client.force_login(staff_user)

        response = api_client.post(BRIDGE_URL)

        assert response.status_code == 200
        data = response.json()
        assert 'tokens' in data
        assert 'access' in data['tokens']
        assert 'refresh' in data['tokens']
        assert 'user' in data
        assert data['user']['email'] == 'staff@bridge.com'
        assert data['user']['role'] == 'admin'

    def test_non_staff_user_gets_403(self, api_client, non_staff_user):
        """Fails if a client session can bootstrap administrative authority."""
        api_client.force_login(non_staff_user)

        response = api_client.post(BRIDGE_URL)

        assert response.status_code == 403

    def test_unauthenticated_request_gets_403(self, api_client):
        """Fails if anonymous requests receive bridge access."""
        response = api_client.post(BRIDGE_URL)

        assert response.status_code == 403

    def test_staff_without_profile_auto_creates_admin_profile(self, api_client, staff_no_profile):
        """Fails if the original Panel first-visit bootstrap is lost."""
        api_client.force_login(staff_no_profile)
        assert not UserProfile.objects.filter(user=staff_no_profile).exists()

        response = api_client.post(BRIDGE_URL)

        assert response.status_code == 200
        profile = UserProfile.objects.get(user=staff_no_profile)
        assert profile.role == UserProfile.ROLE_ADMIN
        assert profile.is_onboarded is True

        data = response.json()
        assert data['user']['role'] == 'admin'

    @pytest.mark.parametrize('role', [UserProfile.ROLE_ADMIN, UserProfile.ROLE_CLIENT])
    def test_jwt_only_request_cannot_bootstrap_platform_authority(self, staff_user, role):
        """Fails if a JWT can bypass Panel authentication to rewrite a profile."""
        profile = staff_user.profile
        profile.role = role
        profile.is_onboarded = False
        profile.profile_completed = False
        profile.save(update_fields=['role', 'is_onboarded', 'profile_completed'])
        api = APIClient(enforce_csrf_checks=True)
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(staff_user)["access"]}')

        response = api.post(BRIDGE_URL)

        profile.refresh_from_db()
        assert response.status_code == 403
        assert 'tokens' not in response.data
        assert profile.role == role
        assert profile.is_onboarded is False
        assert profile.profile_completed is False

    def test_staff_session_without_csrf_cannot_elevate_profile(self, staff_user):
        """Fails if a forged session request can promote a client profile."""
        profile = staff_user.profile
        profile.role = UserProfile.ROLE_CLIENT
        profile.save(update_fields=['role'])
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(staff_user)

        response = api.post(BRIDGE_URL)

        profile.refresh_from_db()
        assert response.status_code == 403
        assert 'tokens' not in response.data
        assert profile.role == UserProfile.ROLE_CLIENT

    def test_staff_session_with_csrf_can_bootstrap_platform_authority(self, staff_user):
        """Fails if valid Panel CSRF cannot perform its authorized promotion."""
        profile = staff_user.profile
        profile.role = UserProfile.ROLE_CLIENT
        profile.save(update_fields=['role'])
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(staff_user)
        csrf_request = RequestFactory().get('/')
        csrf_token = get_token(csrf_request)
        api.cookies['csrftoken'] = csrf_request.META['CSRF_COOKIE']

        response = api.post(BRIDGE_URL, HTTP_X_CSRFTOKEN=csrf_token)

        profile.refresh_from_db()
        assert response.status_code == 200
        assert profile.role == UserProfile.ROLE_ADMIN
        assert response.data['tokens']['access']
        assert response.data['tokens']['refresh']

    def test_staff_session_without_csrf_cannot_create_profile(self, staff_no_profile):
        """Fails if missing CSRF can create a new administrative profile."""
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(staff_no_profile)

        response = api.post(BRIDGE_URL)

        assert response.status_code == 403
        assert 'tokens' not in response.data
        assert not UserProfile.objects.filter(user=staff_no_profile).exists()

    def test_staff_session_with_csrf_creates_admin_profile(self, staff_no_profile):
        """Fails if protected Panel bootstrap cannot create its first profile."""
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(staff_no_profile)
        csrf_request = RequestFactory().get('/')
        csrf_token = get_token(csrf_request)
        api.cookies['csrftoken'] = csrf_request.META['CSRF_COOKIE']

        response = api.post(BRIDGE_URL, HTTP_X_CSRFTOKEN=csrf_token)

        profile = UserProfile.objects.get(user=staff_no_profile)
        assert response.status_code == 200
        assert profile.role == UserProfile.ROLE_ADMIN
        assert profile.is_onboarded is True
        assert response.data['tokens']['access']
        assert response.data['tokens']['refresh']
