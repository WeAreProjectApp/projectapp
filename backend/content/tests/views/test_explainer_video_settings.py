"""Tests for the explainer-video visibility switch (panel settings + public rule)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from content.models import ExplainerVideoSettings
from content.services.explainer_video_service import explainer_video_visible

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
        response = non_staff_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_financing_video': False},
            format='json',
        )

        assert response.status_code == 403
        assert ExplainerVideoSettings.load().show_financing_video is True

    def test_get_returns_both_videos_visible_by_default(self, admin_client):
        response = admin_client.get(reverse('explainer-video-settings'))

        assert response.status_code == 200
        assert response.data['show_additional_modules_video'] is True
        assert response.data['show_financing_video'] is True

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
    def test_patch_rejects_non_boolean_value(self, mock_rebuild, admin_client):
        response = admin_client.patch(
            reverse('update-explainer-video-settings'),
            {'show_additional_modules_video': 'tal vez'},
            format='json',
        )

        assert response.status_code == 400
        assert 'show_additional_modules_video' in response.data
        mock_rebuild.assert_not_called()


class TestExplainerVideoVisibilityRule:
    def test_module_switches_are_independent(self):
        ExplainerVideoSettings.objects.create(show_financing_video=False)

        assert explainer_video_visible('financing') is False
        assert explainer_video_visible('additional-modules') is True

    @pytest.mark.parametrize(
        ('module_on', 'link_on', 'expected'),
        [(True, True, True), (True, False, False), (False, True, False)],
    )
    def test_share_link_needs_both_switches_on(self, module_on, link_on, expected):
        """Fails if a share link can show the video while the catalog switch hides it."""
        ExplainerVideoSettings.objects.create(show_additional_modules_video=module_on)
        share_link = SimpleNamespace(show_explainer_video=link_on)

        assert explainer_video_visible(
            'additional-modules', share_link=share_link,
        ) is expected

    def test_unknown_module_is_rejected(self):
        with pytest.raises(ValueError):
            explainer_video_visible('unknown')
