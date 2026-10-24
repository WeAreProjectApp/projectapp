"""Account isolation and publication safeguards for guided platform help."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models_platform_help import (
    PlatformGuidedTour,
    PlatformHelpEvent,
    PlatformTourProgress,
)
from accounts.services import platform_help as help_service
from accounts.services.project_collaboration_access import CollaborationConflict
from accounts.tests.project_collaboration_helpers import context

pytestmark = pytest.mark.django_db


@pytest.fixture
def actors():
    """Create isolated accounts with independent project ownership."""
    return context()


def general():
    """Read the initial published general guide from migration seeds."""
    return PlatformGuidedTour.objects.get(slug='platform-general')


def acknowledgement(**overrides):
    """Build a complete acknowledgement with explicit test overrides."""
    return {'status': 'completed', 'revision': 1, 'last_step': 'projects', **overrides}


def test_first_visit_has_published_bilingual_guides(actors):
    """Breaks when a first visit cannot obtain the seeded guide."""
    result = help_service.client_catalog(actors.client)
    tour = result['tours'][0]
    assert tour['status'] == ''
    assert tour['content']['steps'][0]['title_es'] == 'Bienvenido a tu plataforma'
    assert tour['content']['steps'][0]['title_en'] == 'Welcome to your platform'


def test_completion_is_visible_on_another_session(actors):
    """Breaks when completion only lives in browser storage."""
    help_service.record_progress(actors.client, general().pk, acknowledgement())
    api = APIClient()
    api.force_authenticate(actors.client)
    result = api.get('/api/platform/help/')
    assert result.data['tours'][0]['status'] == 'completed'


def test_other_account_keeps_its_unseen_guide(actors):
    """Breaks when client completion is shared between people."""
    help_service.record_progress(actors.client, general().pk, acknowledgement())
    assert help_service.client_catalog(actors.other)['tours'][0]['status'] == ''


def test_skipped_state_survives_replay(actors):
    """Breaks when replaying the same tour clears a durable dismissal."""
    help_service.record_progress(actors.client, general().pk, acknowledgement(status='skipped'))
    help_service.record_progress(actors.client, general().pk, acknowledgement(status='in_progress', manual=True))
    assert PlatformTourProgress.objects.get(user=actors.client, tour=general()).status == 'skipped'


@pytest.mark.parametrize(('global_enabled', 'client_enabled'), [(False, True), (True, False), (False, False)])
def test_disabled_tour_returns_no_steps(actors, global_enabled, client_enabled):
    """Breaks when either disabled gate fails to hide the tour."""
    help_service.update_flags(actors.admin, {'expected_version': 0, 'tour_enabled': global_enabled})
    help_service.update_flags(actors.admin, {'expected_version': 0, 'tour_enabled': client_enabled}, actors.client.pk)
    assert help_service.client_catalog(actors.client)['tours'] == []


def test_client_cannot_update_global_settings(actors):
    """Breaks when client authentication crosses into panel administration."""
    api = APIClient()
    api.force_authenticate(actors.client)
    assert api.patch('/api/platform/help/settings/', {'tour_enabled': False, 'expected_version': 0}, format='json').status_code == 403


def test_client_cannot_read_foreign_project_guide(actors):
    """Breaks when contextual help accepts another client's project."""
    with pytest.raises(NotFound):
        help_service.client_catalog(actors.client, actors.other_project.pk)


def test_project_guide_needs_owned_context(actors):
    """Breaks when the project guide can be marked without a valid project."""
    project_tour = PlatformGuidedTour.objects.get(slug='platform-project')
    with pytest.raises(ValidationError):
        help_service.record_progress(actors.client, project_tour.pk, acknowledgement(last_step='project-summary'))


def test_editor_rejects_unknown_target(actors):
    """Breaks when an editor can inject arbitrary selectors."""
    content = deepcopy(general().draft)
    content['steps'][0]['target'] = 'button[onclick]'
    with pytest.raises(ValidationError):
        help_service.write_tour(actors.admin, {'slug': 'invalid-target', 'context': 'general', 'content': content})


def test_editor_rejects_cross_context_target(actors):
    """Breaks when a general guide can point to a project-only control."""
    content = deepcopy(general().draft)
    content['steps'][0]['target'] = 'project-summary'
    with pytest.raises(ValidationError):
        help_service.write_tour(actors.admin, {'slug': 'invalid-context', 'context': 'general', 'content': content})


def test_publication_preserves_completed_status(actors):
    """Breaks when copy revisions restart an already completed guide."""
    tour = general()
    help_service.record_progress(actors.client, tour.pk, acknowledgement())
    help_service.publish_tour(actors.admin, tour.pk, {'expected_version': tour.version})
    assert help_service.client_catalog(actors.client)['tours'][0]['status'] == 'completed'


def test_old_admin_version_is_rejected(actors):
    """Breaks when concurrent panel/MCP updates silently overwrite settings."""
    help_service.update_flags(actors.admin, {'expected_version': 0, 'video_enabled': False})
    with pytest.raises(CollaborationConflict):
        help_service.update_flags(actors.admin, {'expected_version': 0, 'tour_enabled': False})


def test_unavailable_chatbot_is_removed(actors):
    """Breaks when a guide advertises an unavailable chatbot."""
    with patch.object(help_service, '_capabilities', return_value={'chatbot': {'available': False}}):
        result = help_service.client_catalog(actors.client)
    assert 'platform-appi-launcher' not in [step['target'] for step in result['tours'][0]['content']['steps']]


def test_admin_preview_does_not_write_progress(actors):
    """Breaks when previewing a draft gives a user a completed state."""
    result = help_service.preview_tour(actors.admin, general().pk)
    assert result['preview'] is True
    assert PlatformTourProgress.objects.count() == 0


def test_disabled_tour_rejects_progress_write(actors):
    """Breaks when a disabled feature still permits client mutations."""
    help_service.update_flags(actors.admin, {'expected_version': 0, 'tour_enabled': False})
    with pytest.raises(PermissionDenied):
        help_service.record_progress(actors.client, general().pk, acknowledgement())


def test_sensitive_mcp_uses_same_audited_settings_service(actors):
    """Breaks when MCP configuration bypasses the panel's audited service."""
    from content.mcp.platform_help_tools import PLATFORM_HELP_TOOLS
    tool = next(item for item in PLATFORM_HELP_TOOLS if item['name'] == 'update_platform_help_settings')
    with patch('content.mcp.panel_bridge.mcp_actor', return_value=actors.admin):
        result = tool['handler']({'expected_version': 0, 'tour_enabled': False})
    assert result['tour_enabled'] is False
    assert PlatformHelpEvent.objects.filter(action='update_flags', actor=actors.admin).count() == 1
