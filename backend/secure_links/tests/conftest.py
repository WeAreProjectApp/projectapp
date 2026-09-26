import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from secure_links import services
from secure_links.models import SecureLink

CREDENTIALS = {'service': 'Django admin', 'username': 'admin', 'password': 'S3cr3t-value!'}


@pytest.fixture(autouse=True)
def _reset_throttles():
    """Anonymous throttles share the cache; isolate every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username='secure-staff', password='test-password', is_staff=True,
    )


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_login(staff_user)
    return client


@pytest.fixture
def regular_client(db):
    user = get_user_model().objects.create_user(username='secure-regular', password='test-password')
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def client_profile(db):
    user = get_user_model().objects.create_user(
        username='cliente-seguro', email='cliente@example.com', first_name='Ana', last_name='Cliente',
    )
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': UserProfile.ROLE_CLIENT})
    return profile


@pytest.fixture
def project(client_profile):
    return Project.objects.create(client=client_profile.user, name='Portal Demo')


@pytest.fixture
def make_link(staff_user):
    def factory(origin=SecureLink.Origin.PANEL, fields=None, **kwargs):
        return services.create_link(
            secret_type=kwargs.pop('secret_type', 'credentials'),
            title=kwargs.pop('title', 'Admin producción'),
            fields=fields or dict(CREDENTIALS),
            origin=origin,
            actor=staff_user if origin != SecureLink.Origin.PUBLIC else None,
            creator_name='Cliente Uno' if origin == SecureLink.Origin.PUBLIC else '',
            **kwargs,
        )
    return factory


def token_from(url):
    return url.split('#', 1)[1]
