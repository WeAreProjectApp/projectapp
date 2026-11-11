import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import UserProfile, VerificationCode

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@test.com', email='admin@test.com', password='adminpass1',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


def _admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@test.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.mark.django_db
class TestFullOnboardingFlow:
    """End-to-end: admin creates client → client logs in → verifies OTP → sets password."""

    def test_complete_onboarding_flow(self, api_client, admin_user, mailoutbox):
        headers = _admin_headers(api_client, admin_user)

        # Step 1: Admin creates client
        resp = api_client.post('/api/accounts/clients/', {
            'email': 'nuevo@cliente.com',
            'first_name': 'Pedro',
            'last_name': 'Ruiz',
            'company_name': 'NuevaCorp',
        }, **headers)
        assert resp.status_code == 201
        assert resp.json()['is_onboarded'] is False
        assert len(mailoutbox) == 1
        assert 'Bienvenido' in mailoutbox[0].subject

        enable = api_client.patch(
            f"/api/accounts/clients/{resp.json()['user_id']}/",
            {'is_active': True}, format='json', **headers,
        )
        assert enable.status_code == 200

        # Extract temp password from plain-text fallback
        body = mailoutbox[0].body
        temp_password = None
        for line in body.split('\n'):
            if 'temporal' in line.lower():
                temp_password = line.split(':')[-1].strip()
                break
        assert temp_password is not None
        mailoutbox.clear()

        # Step 2: Client logs in with temp password → triggers OTP
        resp = api_client.post('/api/accounts/login/', {
            'email': 'nuevo@cliente.com',
            'password': temp_password,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['requires_verification'] is True
        verification_token = data['verification_token']
        assert len(mailoutbox) == 1

        # Get the OTP from the DB
        otp = VerificationCode.objects.filter(
            user__email='nuevo@cliente.com', is_used=False,
        ).latest('created_at')

        # Step 3: Client verifies OTP and sets new password
        resp = api_client.post(
            '/api/accounts/verify/',
            {'code': otp.code, 'new_password': 'MyNewSecurePass1!'},
            HTTP_AUTHORIZATION=f'Bearer {verification_token}',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'tokens' in data
        assert data['user']['is_onboarded'] is True

        # Step 4: Subsequent login with new password works
        resp = api_client.post('/api/accounts/login/', {
            'email': 'nuevo@cliente.com',
            'password': 'MyNewSecurePass1!',
        })
        assert resp.status_code == 200
        assert resp.json()['requires_verification'] is False
        assert 'tokens' in resp.json()

    def test_wrong_otp_code_fails(self, api_client, admin_user, mailoutbox):
        headers = _admin_headers(api_client, admin_user)

        created = api_client.post('/api/accounts/clients/', {
            'email': 'otp@test.com', 'first_name': 'A', 'last_name': 'B',
        }, **headers)
        enable = api_client.patch(
            f"/api/accounts/clients/{created.json()['user_id']}/",
            {'is_active': True}, format='json', **headers,
        )
        assert enable.status_code == 200

        body = mailoutbox[0].body
        temp_password = None
        for line in body.split('\n'):
            if 'temporal' in line.lower():
                temp_password = line.split(':')[-1].strip()
                break
        mailoutbox.clear()

        resp = api_client.post('/api/accounts/login/', {
            'email': 'otp@test.com', 'password': temp_password,
        })
        verification_token = resp.json()['verification_token']

        resp = api_client.post(
            '/api/accounts/verify/',
            {'code': '000000', 'new_password': 'SomePass123!'},
            HTTP_AUTHORIZATION=f'Bearer {verification_token}',
        )
        assert resp.status_code == 400
        assert 'incorrecto' in resp.json()['detail'].lower()
