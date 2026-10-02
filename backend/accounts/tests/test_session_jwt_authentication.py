"""Regression tests for the boundary between challenge and session JWTs."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import (
    DeliveryMessage,
    DeliveryPublication,
    ProjectAdminAccess,
    UserProfile,
    VerificationCode,
)
from accounts.services.credential_cipher import decrypt_secret, encrypt_secret
from accounts.services.tokens import (
    get_password_reset_request_token,
    get_password_reset_verified_token,
    get_tokens_for_user,
    get_verification_token_for_user,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def _purpose_token(user, purpose):
    """Return a signed access JWT carrying the supplied constrained purpose."""
    token = AccessToken.for_user(user)
    token['purpose'] = purpose
    return str(token)


PLATFORM_READ_ENDPOINTS = (
    '/api/accounts/projects/{project_id}/delivery/',
    '/api/accounts/projects/{project_id}/billing-options/',
    '/api/accounts/projects/{project_id}/ideas/',
    '/api/accounts/projects/{project_id}/secure-links/types/',
)


@pytest.fixture
def pending_user():
    """Return a client whose onboarding remains incomplete."""
    user = User.objects.create_user(
        username='pending-auth@example.test',
        email='pending-auth@example.test',
        password='OldPassword123!',
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=False,
    )
    return user


@pytest.fixture
def project_access(project, admin_user):
    """Return an encrypted production credential for the test project."""
    return ProjectAdminAccess.objects.create(
        project=project,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_password_encrypted=encrypt_secret('production-secret'),
        updated_by=admin_user,
    )


@pytest.fixture
def locmem_mailer(settings):
    """Route recovery emails through Django's in-memory backend."""
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }


@pytest.mark.parametrize('purpose', [
    'verification',
    'password_reset_request',
    'password_reset_verified',
    '',
    None,
])
def test_purpose_claim_rejects_profile_session(api_client, admin_user, purpose):
    """Fails if a signed challenge JWT can read a platform profile."""
    response = api_client.get(
        '/api/accounts/me/',
        HTTP_AUTHORIZATION=f'Bearer {_purpose_token(admin_user, purpose)}',
    )

    assert response.status_code == 401


def test_purpose_claim_cannot_change_profile(api_client, admin_user):
    """Fails if a challenge JWT can mutate the account profile."""
    response = api_client.patch(
        '/api/accounts/me/',
        {'first_name': 'Leaked'},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {_purpose_token(admin_user, "verification")}',
    )

    admin_user.refresh_from_db()
    assert response.status_code == 401
    assert admin_user.first_name == 'Admin'


@pytest.mark.parametrize('purpose', [
    'verification',
    'password_reset_request',
    'password_reset_verified',
])
def test_purpose_claim_cannot_reveal_project_password(
    api_client, admin_user, project, project_access, purpose,
):
    """Fails if a challenge JWT can reveal an encrypted project password."""
    before = project_access.admin_password_encrypted
    response = api_client.post(
        f'/api/accounts/projects/{project.pk}/access/environments/production/password/reveal/',
        {},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {_purpose_token(admin_user, purpose)}',
    )

    project_access.refresh_from_db()
    assert response.status_code == 401
    assert project_access.admin_password_encrypted == before
    assert decrypt_secret(project_access.admin_password_encrypted) == 'production-secret'


@pytest.mark.parametrize('purpose', [
    'verification',
    'password_reset_request',
    'password_reset_verified',
])
@pytest.mark.parametrize('endpoint', PLATFORM_READ_ENDPOINTS)
def test_purpose_claim_cannot_read_platform_project_adapters(
    api_client, client_user, project, endpoint, purpose,
):
    """Fails if a challenge JWT reaches any project-scoped Platform adapter."""
    mail.outbox = []
    before = (DeliveryMessage.objects.count(), DeliveryPublication.objects.count())

    response = api_client.get(
        endpoint.format(project_id=project.pk),
        HTTP_AUTHORIZATION=f'Bearer {_purpose_token(client_user, purpose)}',
    )

    assert response.status_code == 401
    assert (DeliveryMessage.objects.count(), DeliveryPublication.objects.count()) == before
    assert mail.outbox == []


@pytest.mark.parametrize('endpoint', PLATFORM_READ_ENDPOINTS)
def test_regular_owner_token_reads_platform_project_adapters(
    api_client, client_user, project, endpoint,
):
    """Fails if the session guard rejects the project owner's ordinary JWT."""
    response = api_client.get(
        endpoint.format(project_id=project.pk),
        HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(client_user)["access"]}',
    )

    assert response.status_code == 200


@pytest.mark.parametrize('endpoint', PLATFORM_READ_ENDPOINTS)
def test_other_client_token_cannot_read_platform_project_adapters(
    api_client, admin_user, project, endpoint,
):
    """Fails if an ordinary client JWT can read another client's project adapter."""
    other_client = User.objects.create_user(
        username='other-platform-client@example.test',
        email='other-platform-client@example.test',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=other_client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin_user,
    )

    response = api_client.get(
        endpoint.format(project_id=project.pk),
        HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(other_client)["access"]}',
    )

    assert response.status_code == 404


def test_normal_access_token_reads_profile(api_client, admin_headers):
    """Fails if the session guard rejects an ordinary platform access JWT."""
    response = api_client.get('/api/accounts/me/', **admin_headers)

    assert response.status_code == 200
    assert response.json()['role'] == UserProfile.ROLE_ADMIN


def test_client_access_token_cannot_reveal_project_password(
    api_client, client_headers, project, project_access,
):
    """Fails if the session guard bypasses the admin role required for secrets."""
    before = project_access.admin_password_encrypted
    response = api_client.post(
        f'/api/accounts/projects/{project.pk}/access/environments/production/password/reveal/',
        {},
        format='json',
        **client_headers,
    )

    project_access.refresh_from_db()
    assert response.status_code == 403
    assert project_access.admin_password_encrypted == before


def test_panel_session_keeps_panel_access(api_client, admin_user, project):
    """Fails if session authentication stops working on the panel endpoint."""
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    api_client.force_login(admin_user)

    response = api_client.get(f'/api/projects/{project.pk}/access/')

    assert response.status_code == 200
    assert response.json()['project']['id'] == project.pk


def test_public_reset_request_token_cannot_read_profile(
    api_client, admin_user, locmem_mailer,
):
    """Fails if a real reset-request token is accepted by the profile endpoint."""
    mail.outbox = []
    reset = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': admin_user.email},
        format='json',
    )
    token = reset.json()['reset_request_token']
    response = api_client.get(
        '/api/accounts/me/',
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )

    assert reset.status_code == 200
    assert token.count('.') == 2
    assert len(mail.outbox) == 1
    assert response.status_code == 401


def test_public_reset_request_token_cannot_change_profile(
    api_client, admin_user, locmem_mailer,
):
    """Fails if a real reset-request token can mutate the profile endpoint."""
    mail.outbox = []
    reset = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': admin_user.email},
        format='json',
    )
    token = reset.json()['reset_request_token']
    response = api_client.patch(
        '/api/accounts/me/',
        {'first_name': 'Changed'},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )

    admin_user.refresh_from_db()
    assert reset.status_code == 200
    assert token.count('.') == 2
    assert len(mail.outbox) == 1
    assert response.status_code == 401
    assert admin_user.first_name == 'Admin'


@pytest.mark.parametrize('token_factory', [
    lambda user: get_tokens_for_user(user)['access'],
    get_password_reset_request_token,
    get_password_reset_verified_token,
])
def test_wrong_purpose_cannot_consume_onboarding_code(
    api_client, pending_user, token_factory,
):
    """Fails if a non-verification credential can complete onboarding."""
    code = VerificationCode.create_for_user(pending_user)
    response = api_client.post(
        '/api/accounts/verify/',
        {'code': code.code, 'new_password': 'NewPassword123!'},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {token_factory(pending_user)}',
    )

    code.refresh_from_db()
    pending_user.refresh_from_db()
    assert response.status_code == 401
    assert code.is_used is False
    assert pending_user.check_password('OldPassword123!')
    assert pending_user.profile.is_onboarded is False


@pytest.mark.parametrize('token_factory', [
    lambda user: get_tokens_for_user(user)['access'],
    get_password_reset_request_token,
    get_password_reset_verified_token,
])
def test_wrong_purpose_cannot_resend_onboarding_code(
    api_client, pending_user, token_factory,
):
    """Fails if a non-verification credential can create another onboarding OTP."""
    VerificationCode.create_for_user(pending_user)
    response = api_client.post(
        '/api/accounts/resend-code/',
        {},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {token_factory(pending_user)}',
    )

    assert response.status_code == 401
    assert VerificationCode.objects.filter(user=pending_user).count() == 1


def test_verification_token_completes_onboarding(api_client, pending_user):
    """Fails if the purpose check blocks the valid onboarding credential."""
    code = VerificationCode.create_for_user(pending_user)
    response = api_client.post(
        '/api/accounts/verify/',
        {'code': code.code, 'new_password': 'NewPassword123!'},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {get_verification_token_for_user(pending_user)}',
    )

    pending_user.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['tokens']['access'].count('.') == 2
    assert pending_user.profile.is_onboarded is True
