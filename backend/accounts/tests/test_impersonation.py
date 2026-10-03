"""Tests for the "Log in as this user" (impersonation) feature.

Covers the shared service (accounts/services/impersonation.py), the panel DRF
endpoint, and the Django admin button/view.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.services.impersonation import (
    EXCHANGE_CODE_CLAIM_PREFIX,
    EXCHANGE_CODE_PREFIX,
    EXCHANGE_CODE_TTL_SECONDS,
    ImpersonationError,
    build_impersonation_redirect_url,
    consume_exchange_code,
    create_exchange_code,
    impersonate,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """Provide an API client for impersonation endpoints."""
    return APIClient()


@pytest.fixture
def superuser(db):
    """Provide an active superuser permitted to impersonate clients."""
    user = User.objects.create_superuser(
        username='root@test.com', email='root@test.com', password='rootpass1!',
        first_name='Root', last_name='Admin',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def staff_admin(db):
    """Provide a staff administrator without superuser access."""
    user = User.objects.create_user(
        username='staff@test.com', email='staff@test.com', password='staffpass1!',
        is_staff=True,
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def client_user(db, superuser):
    """Provide an active client profile created by the superuser."""
    user = User.objects.create_user(
        username='client@test.com', email='client@test.com', password='clientpass1!',
        first_name='Client', last_name='User',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True, profile_completed=True,
        created_by=superuser,
    )
    return user


def _bearer(api_client, email, password):
    resp = api_client.post(
        '/api/accounts/login/', {'email': email, 'password': password}, format='json',
    )
    return {'HTTP_AUTHORIZATION': f"Bearer {resp.json()['tokens']['access']}"}


# ---------------------------------------------------------------------------
# Service rules
# ---------------------------------------------------------------------------

def test_impersonate_happy_path_returns_tokens(superuser, client_user):
    """Returns both bearer tokens for an authorized client impersonation."""
    tokens = impersonate(superuser, client_user)
    assert tokens['access']
    assert tokens['refresh']


def test_impersonate_rejects_non_superuser_actor(staff_admin, client_user):
    """Rejects an administrator who lacks superuser permission."""
    with pytest.raises(ImpersonationError) as exc:
        impersonate(staff_admin, client_user)
    assert exc.value.status_code == 403


def test_impersonate_rejects_inactive_superuser_actor(superuser, client_user):
    """Rejects a superuser whose account is inactive."""
    superuser.is_active = False
    with pytest.raises(ImpersonationError) as exc:
        impersonate(superuser, client_user)
    assert exc.value.status_code == 403


def test_impersonate_rejects_other_superuser_target(superuser, db):
    """Rejects impersonation of a different superuser."""
    other = User.objects.create_superuser(
        username='root2@test.com', email='root2@test.com', password='x',
    )
    UserProfile.objects.create(user=other, role=UserProfile.ROLE_ADMIN)
    with pytest.raises(ImpersonationError) as exc:
        impersonate(superuser, other)
    assert exc.value.status_code == 403


def test_impersonate_allows_self_superuser(superuser):
    """Allows a superuser to mint a token for their own account."""
    tokens = impersonate(superuser, superuser)
    assert tokens['access']


def test_impersonate_rejects_inactive_target(superuser, client_user):
    """Rejects an inactive client target."""
    client_user.is_active = False
    client_user.save(update_fields=['is_active'])
    with pytest.raises(ImpersonationError) as exc:
        impersonate(superuser, client_user)
    assert exc.value.status_code == 400


def test_impersonate_rejects_target_without_profile(superuser, db):
    """Rejects a user who has no platform profile."""
    no_profile = User.objects.create_user(
        username='noprofile@test.com', email='noprofile@test.com', password='x',
    )
    with pytest.raises(ImpersonationError) as exc:
        impersonate(superuser, no_profile)
    assert exc.value.status_code == 400


def test_build_redirect_url_carries_only_code(superuser, client_user):
    """Builds a redirect URL that carries the opaque code only."""
    tokens = impersonate(superuser, client_user)
    code = create_exchange_code(tokens)
    url = build_impersonation_redirect_url(code, redirect_path='/platform')
    assert '/platform/admin-login?' in url
    assert f'code={code}' in url
    assert 'access=' not in url
    assert 'refresh=' not in url
    assert 'redirect=%2Fplatform' in url


# ---------------------------------------------------------------------------
# Exchange code (single-use, short-lived)
# ---------------------------------------------------------------------------

def test_exchange_code_round_trip(superuser, client_user):
    """Returns the payload originally stored for a fresh exchange code."""
    tokens = impersonate(superuser, client_user)
    code = create_exchange_code(tokens)
    assert consume_exchange_code(code) == tokens


def test_exchange_code_is_single_use(superuser, client_user):
    """Rejects a code after its first successful exchange."""
    code = create_exchange_code(impersonate(superuser, client_user))
    assert consume_exchange_code(code) is not None
    assert consume_exchange_code(code) is None


def test_consume_unknown_code_returns_none():
    """Fails closed for an exchange code that was never created."""
    assert consume_exchange_code('does-not-exist') is None


def test_consume_empty_code_returns_none():
    """Fails closed for an empty exchange code."""
    assert consume_exchange_code('') is None


def test_exchange_code_allows_exactly_one_simultaneous_consumer(superuser, client_user):
    """Falla si dos consumidores solapados obtienen los tokens del mismo código."""
    tokens = impersonate(superuser, client_user)
    code = create_exchange_code(tokens)
    real_get = cache.get
    readers_ready = Barrier(2, timeout=5)

    def synchronized_get(key, default=None, version=None):
        value = real_get(key, default=default, version=version)
        readers_ready.wait()
        return value

    with (
        patch(
            'accounts.services.impersonation.cache.get', side_effect=synchronized_get,
        ),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        results = tuple(executor.map(consume_exchange_code, (code, code)))

    assert results.count(tokens) == 1
    assert results.count(None) == 1


def test_exchange_code_with_existing_claim_stays_available():
    """Falla si un consumidor sin la reclamación borra un código todavía válido."""
    tokens = {'access': 'access-token', 'refresh': 'refresh-token'}
    code = create_exchange_code(tokens)
    claim_key = f'{EXCHANGE_CODE_CLAIM_PREFIX}{code}'

    assert cache.add(claim_key, True, timeout=EXCHANGE_CODE_TTL_SECONDS) is True

    assert consume_exchange_code(code) is None
    assert cache.get(f'{EXCHANGE_CODE_PREFIX}{code}') == tokens


def test_exchange_code_with_expired_cache_entry_returns_none():
    """Falla si un código de acceso temporal expirado todavía entrega tokens."""
    code = 'expired-exchange-code'
    cache.set(
        f'{EXCHANGE_CODE_PREFIX}{code}',
        {'access': 'expired-access', 'refresh': 'expired-refresh'},
        timeout=0,
    )

    assert consume_exchange_code(code) is None


# ---------------------------------------------------------------------------
# Panel DRF endpoint
# ---------------------------------------------------------------------------

def test_endpoint_superuser_gets_redirect_url(api_client, superuser, client_user):
    """Returns a code-only redirect URL to an authorized superuser."""
    headers = _bearer(api_client, 'root@test.com', 'rootpass1!')
    resp = api_client.post(
        f'/api/accounts/admins/{client_user.id}/login-as/', **headers,
    )
    assert resp.status_code == 200
    redirect_url = resp.json()['redirect_url']
    assert '/platform/admin-login?' in redirect_url
    assert 'code=' in redirect_url
    assert 'access=' not in redirect_url


def test_endpoint_non_superuser_forbidden(api_client, staff_admin, client_user):
    """Rejects the login-as endpoint for a non-superuser administrator."""
    headers = _bearer(api_client, 'staff@test.com', 'staffpass1!')
    resp = api_client.post(
        f'/api/accounts/admins/{client_user.id}/login-as/', **headers,
    )
    assert resp.status_code == 403


def test_endpoint_target_not_found(api_client, superuser):
    """Returns not found when the target user does not exist."""
    headers = _bearer(api_client, 'root@test.com', 'rootpass1!')
    resp = api_client.post('/api/accounts/admins/999999/login-as/', **headers)
    assert resp.status_code == 404


def test_endpoint_requires_auth(api_client, client_user):
    """Requires authentication before issuing an impersonation redirect."""
    resp = api_client.post(f'/api/accounts/admins/{client_user.id}/login-as/')
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Exchange endpoint (public; the code is the bearer of trust)
# ---------------------------------------------------------------------------

def test_exchange_endpoint_swaps_code_for_tokens(api_client, superuser, client_user):
    """Returns access and refresh tokens for a valid exchange code."""
    code = create_exchange_code(impersonate(superuser, client_user))
    resp = api_client.post(
        '/api/accounts/impersonation/exchange/', {'code': code}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['access']
    assert resp.json()['refresh']


def test_exchange_endpoint_rejects_invalid_code(api_client):
    """Rejects an exchange request with an unknown code."""
    resp = api_client.post(
        '/api/accounts/impersonation/exchange/', {'code': 'nope'}, format='json',
    )
    assert resp.status_code == 400


def test_exchange_endpoint_code_cannot_be_reused(api_client, superuser, client_user):
    """Rejects a second endpoint exchange of the same code."""
    code = create_exchange_code(impersonate(superuser, client_user))
    first = api_client.post(
        '/api/accounts/impersonation/exchange/', {'code': code}, format='json',
    )
    second = api_client.post(
        '/api/accounts/impersonation/exchange/', {'code': code}, format='json',
    )
    assert first.status_code == 200
    assert second.status_code == 400


def test_login_as_then_exchange_end_to_end(api_client, superuser, client_user):
    """Completes the panel login-as flow with a code exchange."""
    headers = _bearer(api_client, 'root@test.com', 'rootpass1!')
    login_as = api_client.post(
        f'/api/accounts/admins/{client_user.id}/login-as/', **headers,
    )
    redirect_url = login_as.json()['redirect_url']
    code = redirect_url.split('code=')[1].split('&')[0]
    exchange = api_client.post(
        '/api/accounts/impersonation/exchange/', {'code': code}, format='json',
    )
    assert exchange.status_code == 200
    assert exchange.json()['access']


# ---------------------------------------------------------------------------
# Django admin
# ---------------------------------------------------------------------------

def _admin_instance():
    from content.admin import ProjectAppUserAdmin, admin_site
    return ProjectAppUserAdmin(User, admin_site)


def _request_with_messages(method, path, user):
    factory = RequestFactory()
    request = getattr(factory, method)(path)
    request.user = user
    SessionMiddleware(lambda r: None).process_request(request)
    MessageMiddleware(lambda r: None).process_request(request)
    return request


def test_admin_impersonate_link_renders_button(client_user):
    """Renders the Django admin impersonation action for a saved user."""
    admin = _admin_instance()
    html = admin.impersonate_link(client_user)
    assert 'Log in as this user' in html
    assert f'/{client_user.id}/login_as/' in html


def test_admin_impersonate_link_blank_for_unsaved():
    """Omits the impersonation action for an unsaved user."""
    admin = _admin_instance()
    assert admin.impersonate_link(User()) == '—'


def test_admin_login_as_view_success_redirects_to_frontend(superuser, client_user):
    """Redirects a successful admin login-as action to the frontend callback."""
    admin = _admin_instance()
    request = _request_with_messages('post', '/admin/', superuser)
    response = admin.login_as_user_view(request, client_user.id)
    assert response.status_code == 302
    assert '/platform/admin-login?' in response['Location']
    assert 'code=' in response['Location']
    assert 'access=' not in response['Location']


def test_admin_login_as_view_failure_redirects_to_change(superuser, db):
    """Returns to the change page when the admin target is forbidden."""
    other = User.objects.create_superuser(
        username='root3@test.com', email='root3@test.com', password='x',
    )
    UserProfile.objects.create(user=other, role=UserProfile.ROLE_ADMIN)
    admin = _admin_instance()
    request = _request_with_messages('post', '/admin/', superuser)
    response = admin.login_as_user_view(request, other.id)
    assert response.status_code == 302
    assert 'admin-login' not in response['Location']
