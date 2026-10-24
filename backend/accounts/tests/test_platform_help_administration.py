"""Help preferences, account filters and validated progress through real endpoints."""
import pytest
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from accounts.models_platform_help import PlatformGuidedTour, PlatformTourProgress
from accounts.services import platform_help as help_service
from accounts.tests.platform_help_helpers import help_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def actors():
    """Give the isolated clients distinct searchable display names."""
    result = help_context()
    result.client.first_name = 'Camila'
    result.client.email = 'camila@example.test'
    result.client.save(update_fields=['first_name', 'email'])
    result.other.first_name = ''
    result.other.email = 'other@example.test'
    result.other.save(update_fields=['first_name', 'email'])
    return result


@pytest.fixture
def panel(actors):
    """Authenticate only the administrator on the panel transport."""
    api = APIClient()
    api.force_authenticate(actors.admin)
    return api


@pytest.fixture
def client_api(actors):
    """Authenticate an active onboarded client on the client transport."""
    api = APIClient()
    api.force_authenticate(actors.client)
    return api


def test_panel_reads_default_global_preferences(panel):
    """Breaks when administration displays disabled defaults for first-time clients."""
    response = panel.get('/api/platform/help/settings/')

    assert response.status_code == 200
    assert response.data == {'tour_enabled': True, 'video_enabled': True, 'version': 0}
    assert 'no-store' in response['Cache-Control']


def test_panel_reads_default_client_preferences(panel, actors):
    """Breaks when a client without a preferences row cannot be configured."""
    response = panel.get(f'/api/platform/help/clients/{actors.other.pk}/')

    assert response.status_code == 200
    assert response.data == {
        'user_id': actors.other.pk, 'name': 'other@example.test',
        'tour_enabled': True, 'video_enabled': True, 'version': 0,
    }


@pytest.mark.parametrize(('search', 'expected_names'), [
    ('', ['Camila', 'other@example.test']), ('camila@', ['Camila']),
])
def test_panel_client_search_excludes_other_accounts(panel, search, expected_names):
    """Breaks when the client picker ignores its search or includes staff accounts."""
    response = panel.get('/api/platform/help/clients/', {'search': search})

    assert response.status_code == 200
    assert [item['name'] for item in response.data['results']] == expected_names
    assert response.data['count'] == len(expected_names)
    assert response.data['page'] == 1


@pytest.mark.parametrize('method', ['get', 'patch'])
def test_panel_rejects_staff_as_client(panel, actors, method):
    """Breaks when per-client help preferences can be assigned to an administrator."""
    response = getattr(panel, method)(f'/api/platform/help/clients/{actors.admin.pk}/', {
        'expected_version': 0, 'tour_enabled': False,
    }, format='json')

    assert response.status_code == 404
    assert str(response.data['detail']) == 'Cliente no encontrado.'


def test_service_rejects_client_administrator_access(actors):
    """Breaks when a conversational caller bypasses panel authorization at the service boundary."""
    with pytest.raises(PermissionDenied, match='Solo los administradores'):
        help_service.settings_payload(actors.client)


@pytest.mark.parametrize(('global_enabled', 'client_enabled', 'expected'), [
    (False, True, False), (True, False, False), (True, True, True),
])
def test_video_gate_requires_both_preferences(actors, global_enabled, client_enabled, expected):
    """Breaks when the video handoff ignores either the global or client help switch."""
    help_service.update_flags(actors.admin, {'expected_version': 0, 'video_enabled': global_enabled})
    help_service.update_flags(actors.admin, {'expected_version': 0, 'video_enabled': client_enabled}, actors.client.pk)

    result = help_service.effective_video_enabled(actors.client)

    assert result is expected


@pytest.mark.parametrize(('query', 'expected_statuses'), [
    ('', ['completed', 'paused']), ('?user_id={client_id}', ['completed']),
])
def test_progress_report_respects_client_filter(panel, actors, query, expected_statuses):
    """Breaks when the administrator's per-client report includes another client's progress."""
    tour = PlatformGuidedTour.objects.get(slug='platform-general')
    help_service.record_progress(actors.client, tour.pk, {
        'status': 'completed', 'revision': 1, 'last_step': 'projects',
    })
    help_service.record_progress(actors.other, tour.pk, {
        'status': 'paused', 'revision': 1, 'last_step': 'notifications',
    })

    response = panel.get('/api/platform/help/admin/progress/' + query.format(client_id=actors.client.pk))

    assert response.status_code == 200
    assert sorted(item['status'] for item in response.data['results']) == expected_statuses
    assert response.data['count'] == len(expected_statuses)


def test_progress_rejects_unpublished_revision(client_api):
    """Breaks when a client can acknowledge a revision that was never published."""
    tour = PlatformGuidedTour.objects.get(slug='platform-general')

    response = client_api.post(f'/api/platform/help/tours/{tour.pk}/progress/', {
        'status': 'completed', 'revision': 999, 'last_step': 'projects',
    }, format='json')

    assert response.status_code == 400
    assert str(response.data['revision']) == 'Revisión no disponible.'
    assert PlatformTourProgress.objects.count() == 0


def test_progress_rejects_step_from_another_guide(client_api):
    """Breaks when a valid target from another guide can corrupt a user's resume position."""
    tour = PlatformGuidedTour.objects.get(slug='platform-general')

    response = client_api.post(f'/api/platform/help/tours/{tour.pk}/progress/', {
        'status': 'paused', 'revision': 1, 'last_step': 'voice-report',
    }, format='json')

    assert response.status_code == 400
    assert str(response.data['last_step']) == 'Este paso no pertenece al recorrido.'
    assert PlatformTourProgress.objects.count() == 0


def test_pause_updates_existing_resume_position(client_api, actors):
    """Breaks when pausing an already started tour leaves its original resume position."""
    tour = PlatformGuidedTour.objects.get(slug='platform-general')
    client_api.post(f'/api/platform/help/tours/{tour.pk}/progress/', {
        'status': 'in_progress', 'revision': 1, 'last_step': 'welcome',
    }, format='json')

    response = client_api.post(f'/api/platform/help/tours/{tour.pk}/progress/', {
        'status': 'paused', 'revision': 1, 'last_step': 'notifications',
    }, format='json')

    assert response.status_code == 200
    progress = PlatformTourProgress.objects.get(user=actors.client, tour=tour)
    assert progress.status == 'paused'
    assert progress.last_step == 'notifications'
    assert PlatformTourProgress.objects.filter(user=actors.client, tour=tour).count() == 1


def test_project_progress_accepts_owned_context(client_api, actors):
    """Breaks when a client cannot pause a contextual guide for their own project."""
    tour = PlatformGuidedTour.objects.get(slug='platform-project')

    response = client_api.post(f'/api/platform/help/tours/{tour.pk}/progress/', {
        'status': 'paused', 'revision': 1, 'last_step': 'project-summary', 'project_id': actors.project.pk,
    }, format='json')

    assert response.status_code == 200
    progress = PlatformTourProgress.objects.get(user=actors.client, tour=tour)
    assert progress.status == 'paused'
    assert progress.last_step == 'project-summary'


@pytest.mark.parametrize(('url', 'field'), [
    ('/api/platform/help/?project_id=0', 'project_id'),
    ('/api/platform/help/clients/?page=0', 'page'),
    ('/api/platform/help/admin/progress/?user_id=0', 'user_id'),
])
def test_query_validation_rejects_nonpositive_identifiers(panel, url, field):
    """Breaks when malformed context or pagination is accepted instead of returning a private 400."""
    response = panel.get(url)

    assert response.status_code == 400
    assert response.data[field][0].code == 'min_value'
    assert 'no-store' in response['Cache-Control']
