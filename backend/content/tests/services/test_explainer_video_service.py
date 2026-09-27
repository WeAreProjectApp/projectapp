"""Explainer-video visibility service tests."""

from types import SimpleNamespace

import pytest

from content.models import ExplainerVideoSettings
from content.services.explainer_video_service import explainer_video_visible


pytestmark = pytest.mark.django_db


def test_module_switches_are_independent():
    """Fails if hiding the alliance video also hides the catalog video."""
    ExplainerVideoSettings.objects.create(show_financing_video=False)

    assert explainer_video_visible('financing') is False
    assert explainer_video_visible('additional-modules') is True


@pytest.mark.parametrize(
    ('module_on', 'link_on', 'expected'),
    [(True, True, True), (True, False, False), (False, True, False)],
)
def test_share_link_needs_both_switches_on(module_on, link_on, expected):
    """Fails if a share link can show the video while the catalog switch hides it."""
    ExplainerVideoSettings.objects.create(show_additional_modules_video=module_on)
    share_link = SimpleNamespace(show_explainer_video=link_on)

    assert explainer_video_visible(
        'additional-modules', share_link=share_link,
    ) is expected


def test_unknown_module_is_rejected():
    """Fails if callers can query an explainer-video switch that does not exist."""
    with pytest.raises(ValueError):
        explainer_video_visible('unknown')
