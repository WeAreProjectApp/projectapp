"""PA-227: a removed custom cover must stay removed after profile reload."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import UserProfile

pytestmark = pytest.mark.django_db


@pytest.fixture(params=[UserProfile.ROLE_ADMIN, UserProfile.ROLE_CLIENT])
def cover_profile(request):
    user = get_user_model().objects.create_user(username=f'cover-{request.param}')
    profile = UserProfile.objects.create(
        user=user,
        role=request.param,
        custom_cover_image='covers/saved-cover.png',
        theme_color='#2874f3',
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, profile


def test_remove_custom_cover_survives_profile_reload(cover_profile):
    client, profile = cover_profile

    response = client.patch(
        '/api/accounts/me/',
        {'cover_image': '', 'custom_cover_image': None},
        format='json',
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert not profile.custom_cover_image
    reloaded = client.get('/api/accounts/me/')
    assert reloaded.status_code == 200
    assert reloaded.data['custom_cover_image'] is None
    assert reloaded.data['cover_image'] == ''
    assert reloaded.data['theme_color'] == '#2874f3'


def test_gallery_selection_replaces_custom_cover(cover_profile):
    client, profile = cover_profile

    response = client.patch(
        '/api/accounts/me/',
        {'cover_image': 'NASA Archive/earth.jpg', 'custom_cover_image': None},
        format='json',
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert not profile.custom_cover_image
    reloaded = client.get('/api/accounts/me/')
    assert reloaded.data['cover_image'] == 'NASA Archive/earth.jpg'
    assert reloaded.data['custom_cover_image'] is None


def test_unrelated_profile_update_preserves_custom_cover(cover_profile):
    client, profile = cover_profile

    response = client.patch(
        '/api/accounts/me/', {'company_name': 'Cover QA'}, format='json',
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.custom_cover_image.name == 'covers/saved-cover.png'
    reloaded = client.get('/api/accounts/me/')
    assert reloaded.data['custom_cover_image'].endswith('/covers/saved-cover.png')
