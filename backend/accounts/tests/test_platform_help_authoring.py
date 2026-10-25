"""Real panel operations for draft identity and immutable publication history."""
from copy import deepcopy

import pytest
from rest_framework.test import APIClient

from accounts.models_platform_help import PlatformGuidedTour, PlatformGuidedTourRevision
from accounts.tests.platform_help_helpers import help_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def actors():
    """Create independent administrator and client accounts."""
    return help_context()


@pytest.fixture
def panel(actors):
    """Authenticate the panel administrator at the HTTP boundary."""
    api = APIClient()
    api.force_authenticate(actors.admin)
    return api


@pytest.fixture
def tour(actors):
    """Use the real seeded general guide and its initial publication."""
    return PlatformGuidedTour.objects.get(slug='platform-general')


def novelty_payload():
    """Provide complete bilingual copy for a new general announcement."""
    return {
        'slug': 'new-client-dashboard', 'context': 'general', 'kind': 'novelty',
        'content': {
            'title_es': 'Nuevo resumen', 'title_en': 'New overview',
            'steps': [{
                'target': 'welcome', 'title_es': 'Tu resumen', 'title_en': 'Your overview',
                'description_es': 'Aquí ves tus proyectos.', 'description_en': 'Find your projects here.',
            }],
        },
    }


def test_panel_catalog_exposes_editable_guides(panel):
    """Breaks when the editor cannot discover the seeded guides or their valid targets."""
    response = panel.get('/api/platform/help/admin/tours/')

    assert response.status_code == 200
    assert [item['slug'] for item in response.data['results']] == [
        'platform-general', 'platform-project', 'platform-voice',
    ]
    assert response.data['targets']['voice-report']['context'] == 'voice'


def test_creating_novelty_keeps_it_unpublished(panel):
    """Breaks when saving an announcement silently publishes it to clients."""
    response = panel.post('/api/platform/help/admin/tours/', novelty_payload(), format='json')

    assert response.status_code == 201
    saved = PlatformGuidedTour.objects.get(slug='new-client-dashboard')
    assert saved.published_revision == 0
    assert saved.version == 1
    assert saved.draft['steps'][0]['title_en'] == 'Your overview'
    assert saved.revisions.count() == 0


def test_panel_rewrites_bilingual_draft(panel, tour):
    """Breaks when editing a card loses the saved bilingual text."""
    detail = panel.get(f'/api/platform/help/admin/tours/{tour.pk}/')
    draft = deepcopy(detail.data['content'])
    draft['steps'][0]['title_es'] = 'Tu nuevo punto de partida'
    draft['steps'][0]['title_en'] = 'Your new starting point'

    response = panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {
        'expected_version': detail.data['version'], 'content': draft,
    }, format='json')

    assert response.status_code == 200
    tour.refresh_from_db()
    assert tour.draft['steps'][0]['title_es'] == 'Tu nuevo punto de partida'
    assert tour.draft['steps'][0]['title_en'] == 'Your new starting point'
    assert tour.version == detail.data['version'] + 1


def test_metadata_update_preserves_draft(panel, tour):
    """Breaks when saving priority without content erases the existing cards."""
    original = deepcopy(tour.draft)

    response = panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {
        'expected_version': tour.version, 'priority': 17,
    }, format='json')

    assert response.status_code == 200
    tour.refresh_from_db()
    assert tour.priority == 17
    assert tour.draft == original


def test_publication_history_preserves_original_copy(panel, tour):
    """Breaks when publishing revised copy overwrites the previous snapshot."""
    draft = deepcopy(tour.draft)
    draft['title_es'] = 'Recorrido actualizado'
    tour.draft = draft
    tour.save(update_fields=['draft'])
    published = panel.post(f'/api/platform/help/admin/tours/{tour.pk}/publish/', {
        'expected_version': tour.version,
    }, format='json')

    response = panel.get(f'/api/platform/help/admin/tours/{tour.pk}/revisions/')

    assert published.status_code == 200
    assert response.status_code == 200
    assert [item['number'] for item in response.data['results']] == [2, 1]
    assert response.data['results'][0]['content']['title_es'] == 'Recorrido actualizado'
    assert response.data['results'][1]['content']['title_es'] == 'Recorrido de la plataforma'


def test_panel_archive_keeps_publication_history(panel, tour):
    """Breaks when retiring a guide deletes its already published history."""
    response = panel.post(f'/api/platform/help/admin/tours/{tour.pk}/archive/', {
        'expected_version': tour.version,
    }, format='json')

    assert response.status_code == 200
    tour.refresh_from_db()
    assert tour.is_active is False
    assert PlatformGuidedTourRevision.objects.filter(tour=tour).count() == 1


def test_creation_requires_content(panel):
    """Breaks when an empty announcement can be saved without bilingual cards."""
    payload = novelty_payload()
    payload.pop('content')

    response = panel.post('/api/platform/help/admin/tours/', payload, format='json')

    assert response.status_code == 400
    assert str(response.data[0]) == 'Se requieren identificador, contexto y contenido bilingüe.'
    assert PlatformGuidedTour.objects.filter(slug='new-client-dashboard').count() == 0


def test_creation_rejects_existing_slug(panel):
    """Breaks when duplicate identifiers become an unhandled database error."""
    payload = novelty_payload()
    payload['slug'] = 'platform-general'

    response = panel.post('/api/platform/help/admin/tours/', payload, format='json')

    assert response.status_code == 400
    assert str(response.data['slug']) == 'Este identificador ya existe.'
    assert PlatformGuidedTour.objects.filter(slug='platform-general').count() == 1


def test_creation_rejects_repeated_target(panel):
    """Breaks when a tour can contain the same highlighted control twice."""
    payload = novelty_payload()
    payload['content']['steps'] *= 2

    response = panel.post('/api/platform/help/admin/tours/', payload, format='json')

    assert response.status_code == 400
    assert str(response.data['content']['steps'][0]) == 'Cada destino solo puede aparecer una vez.'
    assert PlatformGuidedTour.objects.filter(slug='new-client-dashboard').count() == 0


@pytest.mark.parametrize(('field', 'replacement'), [
    ('slug', 'another-identity'), ('context', 'project'), ('kind', 'novelty'),
])
def test_edit_preserves_tour_identity(panel, tour, field, replacement):
    """Breaks when editing metadata silently moves existing user acknowledgements to another tour."""
    original = getattr(tour, field)

    response = panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {
        'expected_version': tour.version, field: replacement,
    }, format='json')

    assert response.status_code == 400
    assert str(response.data[0]) == 'La identidad y el contexto no cambian; crea otra novedad.'
    tour.refresh_from_db()
    assert getattr(tour, field) == original


def test_edit_requires_current_version(panel, tour):
    """Breaks when panel edits bypass the optimistic concurrency contract."""
    response = panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {'priority': 17}, format='json')

    assert response.status_code == 400
    assert str(response.data['expected_version']) == 'Se requiere la versión vigente.'
    tour.refresh_from_db()
    assert tour.priority == 0


def test_edit_rejects_stale_version(panel, tour):
    """Breaks when an old editor overwrites a newer saved priority."""
    panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {
        'expected_version': tour.version, 'priority': 17,
    }, format='json')

    response = panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {
        'expected_version': tour.version, 'priority': 25,
    }, format='json')

    assert response.status_code == 409
    tour.refresh_from_db()
    assert tour.priority == 17


def test_edit_rejects_undeclared_fields(panel, tour):
    """Breaks when panel input silently accepts fields forbidden through MCP."""
    response = panel.patch(f'/api/platform/help/admin/tours/{tour.pk}/', {
        'expected_version': tour.version, 'published_revision': 99,
    }, format='json')

    assert response.status_code == 400
    assert str(response.data['published_revision']) == 'Campo no permitido.'
    tour.refresh_from_db()
    assert tour.published_revision == 1


def test_panel_returns_not_found_for_absent_tour(panel):
    """Breaks when opening a removed guide leaks a server error."""
    response = panel.get('/api/platform/help/admin/tours/999999/')

    assert response.status_code == 404
    assert str(response.data['detail']) == 'Recorrido no encontrado.'
