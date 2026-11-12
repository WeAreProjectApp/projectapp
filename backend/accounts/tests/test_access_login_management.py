"""Panel management coverage for explicitly authorized client accounts."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from accounts.models import Project, UserProfile

pytestmark = pytest.mark.django_db
User = get_user_model()


def make_user(*, email, staff=False):
    """Create a panel staff member or a client with a platform profile."""
    user = User.objects.create_user(
        username=email,
        email=email,
        password="Initial-pass-123",
        is_staff=staff,
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN if staff else UserProfile.ROLE_CLIENT,
        is_onboarded=True,
    )
    return user


def test_staff_can_create_inactive_client_access_without_project():
    """Fails if registering an access client grants access or creates a project implicitly."""
    staff = make_user(email="creator@example.com", staff=True)
    client = Client()
    client.force_login(staff)

    response = client.post(
        "/api/accounts/access/",
        data='{"name": "New client", "email": "new-client@example.com"}',
        content_type="application/json",
    )

    created = User.objects.get(email="new-client@example.com")
    assert response.status_code == 201
    assert created.is_active is False
    assert created.has_usable_password() is False
    assert Project.objects.filter(client=created).exists() is False


def test_access_client_creation_rejects_duplicate_email():
    """Fails if the access module creates a second account for the same email."""
    staff = make_user(email="duplicate-manager@example.com", staff=True)
    make_user(email="already-registered@example.com")
    client = Client()
    client.force_login(staff)

    response = client.post(
        "/api/accounts/access/",
        data='{"name": "Duplicate", "email": "already-registered@example.com"}',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["email"] == [
        "Este correo ya está registrado. Habilita la cuenta existente."
    ]
    assert User.objects.filter(email="already-registered@example.com").count() == 1


def test_client_cannot_manage_access_accounts():
    """Fails if a platform client can use the panel access-management endpoint."""
    client_user = make_user(email="ordinary-client@example.com")
    client = Client()
    client.force_login(client_user)

    response = client.get("/api/accounts/access/")

    assert response.status_code == 403
