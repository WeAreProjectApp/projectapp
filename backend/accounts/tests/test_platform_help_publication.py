"""Client-facing publication and availability safeguards for platform help."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from accounts.models_platform_help import (
    PlatformGuidedTour,
    PlatformGuidedTourRevision,
    PlatformTourProgress,
)
from accounts.services import platform_help as help_service
from accounts.tests.project_collaboration_helpers import context

pytestmark = pytest.mark.django_db


@pytest.fixture
def actors():
    """Create isolated client and administrator accounts."""
    return context()


def general_tour():
    """Return the seeded general onboarding tour."""
    return PlatformGuidedTour.objects.get(slug='platform-general')


def acknowledgement():
    """Build a valid terminal acknowledgement for the general tour."""
    return {'status': 'completed', 'revision': 1, 'last_step': 'projects'}


def test_client_catalog_uses_published_revision_after_draft_edit(actors):
    """Breaks when an unpublished editor draft becomes visible to clients."""
    tour = general_tour()
    published = PlatformGuidedTourRevision.objects.get(tour=tour, number=tour.published_revision)
    draft = deepcopy(tour.draft)
    draft['title_es'] = 'Un borrador todavía no publicado'
    draft['steps'][0]['title_es'] = 'Un paso todavía no publicado'
    tour.draft = draft
    tour.save(update_fields=['draft'])
    api = APIClient()
    api.force_authenticate(actors.client)

    with patch.object(help_service, '_capabilities', return_value={'chatbot': {'available': True}}):
        response = api.get('/api/platform/help/')

    assert response.status_code == 200
    catalogued = next(item for item in response.data['tours'] if item['id'] == tour.pk)
    assert catalogued['revision'] == published.number
    assert catalogued['content'] == published.content


def test_archived_tour_progress_endpoint_returns_not_found(actors):
    """Breaks when an archived guide accepts a client progress acknowledgement."""
    tour = general_tour()
    tour.is_active = False
    tour.save(update_fields=['is_active'])
    api = APIClient()
    api.force_authenticate(actors.client)

    response = api.post(f'/api/platform/help/tours/{tour.pk}/progress/', acknowledgement(), format='json')

    assert response.status_code == 404
    assert response.data['detail'].code == 'not_found'
    assert PlatformTourProgress.objects.filter(user=actors.client, tour=tour).count() == 0


def test_non_client_help_catalog_endpoint_returns_forbidden(actors):
    """Breaks when an authenticated non-client can read client onboarding guides."""
    api = APIClient()
    api.force_authenticate(actors.admin)

    response = api.get('/api/platform/help/')

    assert response.status_code == 403
    assert response.data['detail'].code == 'permission_denied'


def test_unavailable_voice_capability_omits_voice_tour_from_project_catalog(actors):
    """Breaks when a client is offered a voice guide for an unavailable control."""
    api = APIClient()
    api.force_authenticate(actors.client)
    capabilities = {'voice_reporting': {'available': False}}

    with patch.object(help_service, '_capabilities', return_value=capabilities):
        response = api.get(f'/api/platform/help/?project_id={actors.project.pk}')

    assert response.status_code == 200
    targets = [step['target'] for tour in response.data['tours'] for step in tour['content']['steps']]
    assert 'voice-report' not in targets
