import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import (
    Deliverable,
    Project,
    ProjectPhase,
    Requirement,
    UserProfile,
    VerificationCode,
)
from content.models.business_proposal import BusinessProposal
from accounts.services.tokens import get_tokens_for_user, get_verification_token_for_user

User = get_user_model()


# =========================================================================
# Shared fixtures
# =========================================================================

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@edge.com', email='admin@edge.com', password='adminpass1!',
        first_name='Admin', last_name='Edge',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    response = api_client.post('/api/accounts/login/', {
        'email': 'admin@edge.com', 'password': 'adminpass1!',
    })
    token = response.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user():
    user = User.objects.create_user(
        username='client@edge.com', email='client@edge.com', password='clientpass1!',
        first_name='Client', last_name='Edge',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
        company_name='Edge Corp', phone='+57 300',
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    response = api_client.post('/api/accounts/login/', {
        'email': 'client@edge.com', 'password': 'clientpass1!',
    })
    token = response.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


# =========================================================================
# Login view edge cases
# =========================================================================

@pytest.mark.django_db
class TestLoginViewEdgeCases:
    def test_login_with_wrong_password_returns_401(self, api_client, client_user):
        response = api_client.post('/api/accounts/login/', {
            'email': 'client@edge.com', 'password': 'wrongpassword',
        })

        assert response.status_code == 401
        assert 'incorrectas' in response.json()['detail'].lower()

    def test_login_with_nonexistent_email_returns_401(self, api_client):
        response = api_client.post('/api/accounts/login/', {
            'email': 'ghost@nowhere.com', 'password': 'anything',
        })

        assert response.status_code == 401

    def test_login_with_inactive_user_returns_403(self, api_client):
        user = User.objects.create_user(
            username='inactive@test.com', email='inactive@test.com',
            password='pass123!', is_active=False,
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)

        response = api_client.post('/api/accounts/login/', {
            'email': 'inactive@test.com', 'password': 'pass123!',
        })

        assert response.status_code == 401

    def test_login_with_user_without_profile_returns_403(self, api_client):
        User.objects.create_user(
            username='noprof@test.com', email='noprof@test.com', password='pass123!',
        )

        response = api_client.post('/api/accounts/login/', {
            'email': 'noprof@test.com', 'password': 'pass123!',
        })

        assert response.status_code == 403
        assert 'perfil' in response.json()['detail'].lower()

    def test_login_with_empty_body_returns_400(self, api_client):
        response = api_client.post('/api/accounts/login/', {})

        assert response.status_code == 400


# =========================================================================
# Verify view edge cases
# =========================================================================

@pytest.mark.django_db
class TestVerifyViewEdgeCases:
    def test_verify_without_authorization_header_returns_401(self, api_client):
        response = api_client.post('/api/accounts/verify/', {
            'code': '123456', 'new_password': 'NewPass1!',
        })

        assert response.status_code == 401
        assert 'requerido' in response.json()['detail'].lower()

    def test_verify_with_invalid_token_returns_401(self, api_client):
        response = api_client.post(
            '/api/accounts/verify/',
            {'code': '123456', 'new_password': 'NewPass1!'},
            HTTP_AUTHORIZATION='Bearer invalid.token.here',
        )

        assert response.status_code == 401

    def test_verify_with_missing_code_returns_400(self, api_client):
        user = User.objects.create_user(
            username='vc@test.com', email='vc@test.com', password='temp123',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=False)
        token = get_verification_token_for_user(user)

        response = api_client.post(
            '/api/accounts/verify/',
            {'new_password': 'NewPass1!'},
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        assert response.status_code == 400


# =========================================================================
# Token refresh edge cases
# =========================================================================

@pytest.mark.django_db
class TestTokenRefreshEdgeCases:
    def test_refresh_without_token_returns_400(self, api_client):
        response = api_client.post('/api/accounts/token/refresh/', {})

        assert response.status_code == 400
        assert 'requerido' in response.json()['detail'].lower()

    def test_refresh_with_invalid_token_returns_401(self, api_client):
        response = api_client.post('/api/accounts/token/refresh/', {
            'refresh': 'bad.refresh.token',
        })

        assert response.status_code == 401

    def test_refresh_with_valid_token_returns_new_tokens(self, api_client, client_user):
        tokens = get_tokens_for_user(client_user)

        response = api_client.post('/api/accounts/token/refresh/', {
            'refresh': tokens['refresh'],
        })

        assert response.status_code == 200
        assert 'access' in response.json()
        assert 'refresh' in response.json()


# =========================================================================
# Resend code edge cases
# =========================================================================

@pytest.mark.django_db
class TestResendCodeEdgeCases:
    def test_resend_without_authorization_returns_401(self, api_client):
        response = api_client.post('/api/accounts/resend-code/')

        assert response.status_code == 401

    def test_resend_with_valid_token_sends_new_code(self, api_client, mailoutbox):
        user = User.objects.create_user(
            username='resend@test.com', email='resend@test.com', password='temp',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=False)
        token = get_verification_token_for_user(user)

        response = api_client.post(
            '/api/accounts/resend-code/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        assert response.status_code == 200
        assert len(mailoutbox) == 1
        assert VerificationCode.objects.filter(user=user, is_used=False).exists()


# =========================================================================
# Me view edge cases
# =========================================================================

@pytest.mark.django_db
class TestMeViewEdgeCases:
    def test_get_me_unauthenticated_returns_401(self, api_client):
        response = api_client.get('/api/accounts/me/')

        assert response.status_code == 401

    def test_patch_me_with_empty_payload_returns_200(self, api_client, client_headers):
        response = api_client.patch(
            '/api/accounts/me/', {}, content_type='application/json',
            **client_headers,
        )

        assert response.status_code == 200

    def test_patch_me_with_invalid_gender_returns_400(self, api_client, client_headers):
        response = api_client.patch(
            '/api/accounts/me/',
            {'gender': 'invalid_value'},
            content_type='application/json',
            **client_headers,
        )

        assert response.status_code == 400


# =========================================================================
# Complete profile edge cases
# =========================================================================

@pytest.mark.django_db
class TestCompleteProfileEdgeCases:
    @pytest.fixture
    def onboarded_not_completed_user(self, api_client):
        user = User.objects.create_user(
            username='cp@test.com', email='cp@test.com', password='pass123!',
        )
        UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
            profile_completed=False,
        )
        response = api_client.post('/api/accounts/login/', {
            'email': 'cp@test.com', 'password': 'pass123!',
        })
        token = response.json()['tokens']['access']
        return user, {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_complete_profile_missing_required_field_returns_400(
        self, api_client, onboarded_not_completed_user,
    ):
        _, headers = onboarded_not_completed_user

        response = api_client.post(
            '/api/accounts/me/complete-profile/',
            {'company_name': 'ACME', 'phone': '+57 300'},
            content_type='application/json',
            **headers,
        )

        assert response.status_code == 400

    def test_complete_profile_already_completed_returns_400(
        self, api_client, onboarded_not_completed_user,
    ):
        user, headers = onboarded_not_completed_user
        profile = user.profile
        profile.profile_completed = True
        profile.save(update_fields=['profile_completed'])

        response = api_client.post(
            '/api/accounts/me/complete-profile/',
            {
                'company_name': 'A', 'phone': '+57', 'cedula': '123',
                'date_of_birth': '1990-01-01', 'gender': 'male',
                'education_level': 'universitario',
            },
            content_type='application/json',
            **headers,
        )

        assert response.status_code == 400
        assert 'ya fue completado' in response.json()['detail'].lower()


# =========================================================================
# Client resend invite edge cases
# =========================================================================

@pytest.mark.django_db
class TestClientResendInviteEdgeCases:
    def test_resend_invite_to_nonexistent_user_returns_404(
        self, api_client, admin_headers,
    ):
        response = api_client.post(
            '/api/accounts/clients/99999/resend-invite/',
            **admin_headers,
        )

        assert response.status_code == 404

    def test_resend_invite_sends_new_email(
        self, api_client, admin_headers, mailoutbox,
    ):
        target = User.objects.create_user(
            username='target@test.com', email='target@test.com', password='temp',
        )
        UserProfile.objects.create(
            user=target, role=UserProfile.ROLE_CLIENT, is_onboarded=False,
        )
        mailoutbox.clear()

        response = api_client.post(
            f'/api/accounts/clients/{target.id}/resend-invite/',
            **admin_headers,
        )

        assert response.status_code == 200
        assert len(mailoutbox) == 1


# =========================================================================
# Project view edge cases
# =========================================================================

@pytest.mark.django_db
class TestProjectViewEdgeCases:
    def test_non_owner_client_cannot_view_project(self, api_client, admin_user):
        owner = User.objects.create_user(
            username='owner@test.com', email='owner@test.com', password='pass123!',
        )
        UserProfile.objects.create(
            user=owner, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
        )
        project = Project.objects.create(name='Secret', client=owner)

        other = User.objects.create_user(
            username='other@test.com', email='other@test.com', password='pass123!',
        )
        UserProfile.objects.create(
            user=other, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
        )
        resp = api_client.post('/api/accounts/login/', {
            'email': 'other@test.com', 'password': 'pass123!',
        })
        other_token = resp.json()['tokens']['access']

        response = api_client.get(
            f'/api/accounts/projects/{project.id}/',
            HTTP_AUTHORIZATION=f'Bearer {other_token}',
        )

        assert response.status_code == 403

    def test_delete_project_requires_a_lifecycle_transition(
        self, api_client, admin_headers, client_user,
    ):
        project = Project.objects.create(
            name='To Archive', client=client_user, status=Project.STATUS_ACTIVE,
        )

        response = api_client.delete(
            f'/api/accounts/projects/{project.id}/',
            **admin_headers,
        )

        assert response.status_code == 410
        assert response.data['code'] == 'project_archive_replaced'
        project.refresh_from_db()
        assert project.status == Project.STATUS_ACTIVE

    def test_client_cannot_delete_project(self, api_client, client_headers, client_user):
        project = Project.objects.create(name='P', client=client_user)

        response = api_client.delete(
            f'/api/accounts/projects/{project.id}/',
            **client_headers,
        )

        assert response.status_code == 403


# =========================================================================
# Client list filter edge cases
# =========================================================================

@pytest.mark.django_db
class TestClientFilterEdgeCases:
    def test_filter_inactive_clients(self, api_client, admin_headers):
        inactive_user = User.objects.create_user(
            username='inactive@filter.com', email='inactive@filter.com',
            password='pass123!', is_active=False,
        )
        UserProfile.objects.create(
            user=inactive_user, role=UserProfile.ROLE_CLIENT,
        )

        response = api_client.get(
            '/api/accounts/clients/?filter=inactive',
            **admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        emails = [c['email'] for c in data]
        assert 'inactive@filter.com' in emails


# =========================================================================
# Me / complete-profile for user without profile
# =========================================================================

@pytest.mark.django_db
class TestNoProfileEdgeCases:
    def test_me_for_user_without_profile_returns_404(self, api_client):
        user = User.objects.create_user(
            username='noprof2@test.com', email='noprof2@test.com',
            password='pass123!',
        )
        # Get a JWT for this user directly
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)

        response = api_client.get(
            '/api/accounts/me/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        assert response.status_code == 404
        assert 'perfil' in response.json()['detail'].lower()

    def test_complete_profile_for_user_without_profile_returns_404(self, api_client):
        user = User.objects.create_user(
            username='noprof3@test.com', email='noprof3@test.com',
            password='pass123!',
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)

        response = api_client.post(
            '/api/accounts/me/complete-profile/',
            {
                'company_name': 'A', 'phone': '+57', 'cedula': '123',
                'date_of_birth': '1990-01-01', 'gender': 'male',
                'education_level': 'universitario',
            },
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        assert response.status_code == 404
