"""Tests for the explainer-video panel settings endpoints."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from content.models import ExplainerVideoSettings

pytestmark = pytest.mark.django_db
REBUILD_TARGET = 'content.views.explainer_videos.schedule_rebuild_after_publish'


@pytest.fixture
def non_staff_client():
    user = get_user_model().objects.create_user(
        username='video-viewer',
        password='video-pass',
        is_staff=False,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestExplainerVideoSettingsEndpoints:
    def test_get_requires_authentication(self, api_client):
        response = api_client.get(reverse('explainer-video-settings'))

        assert response.status_code in (401, 403)

    def test_patch_rejects_non_staff_user(self, non_staff_client):
        """Fails if a non-admin can hide the proposal welcome video for clients."""
        response = non_staff_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_proposal_video': False},
            format='json',
        )

        assert response.status_code == 403
        assert ExplainerVideoSettings.load().show_proposal_video is True

    def test_get_returns_all_videos_visible_by_default(self, admin_client):
        """Fails if the proposal welcome-video switch is absent or defaults to hidden."""
        response = admin_client.get(reverse('explainer-video-settings'))

        assert response.status_code == 200
        assert response.data['show_additional_modules_video'] is True
        assert response.data['show_financing_video'] is True
        assert response.data['show_proposal_video'] is True

    @patch(REBUILD_TARGET)
    def test_patch_hides_proposal_video_without_static_rebuild(
        self, mock_rebuild, admin_client,
    ):
        """Fails if hiding the runtime proposal video does not persist or rebuilds static pages."""
        response = admin_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_proposal_video': False},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['show_proposal_video'] is False
        assert ExplainerVideoSettings.load().show_proposal_video is False
        mock_rebuild.assert_not_called()

    @patch(REBUILD_TARGET)
    def test_patch_hides_one_video_and_schedules_rebuild(self, mock_rebuild, admin_client):
        """Fails if hiding a video does not persist or leaves the prerendered page stale."""
        response = admin_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_financing_video': False},
            format='json',
        )

        stored = ExplainerVideoSettings.load()
        assert response.status_code == 200
        assert response.data['show_financing_video'] is False
        assert stored.show_financing_video is False
        assert stored.show_additional_modules_video is True
        mock_rebuild.assert_called_once_with()

    @patch(REBUILD_TARGET)
    def test_patch_without_change_skips_rebuild(self, mock_rebuild, admin_client):
        response = admin_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_additional_modules_video': True},
            format='json',
        )

        assert response.status_code == 200
        mock_rebuild.assert_not_called()

    @patch(REBUILD_TARGET)
    def test_patch_rejects_non_boolean_proposal_video_value(
        self, mock_rebuild, admin_client,
    ):
        """Fails if the global proposal-video switch accepts text as a boolean."""
        response = admin_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_proposal_video': 'tal vez'},
            format='json',
        )

        assert response.status_code == 400
        assert 'show_proposal_video' in response.data
        mock_rebuild.assert_not_called()
