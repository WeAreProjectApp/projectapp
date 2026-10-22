"""Staff-only inspection of the program, revision history and private economics."""
import pytest
from rest_framework.test import APIClient

from content.models import BuildingOnDemandProgramRevision
from content.services.building_on_demand_program_service import apply_operation, read_program
from content.tests.building_on_demand_fixtures import hero_update

pytestmark = pytest.mark.django_db
PANEL_PATHS = [
    '/api/building-on-demand/admin/', '/api/building-on-demand/admin/program/versions/',
    '/api/building-on-demand/admin/economics/',
]


def test_overview_returns_seed_metadata(building_on_demand_program, building_on_demand_contract, admin_client):
    """Fails if staff cannot inspect the seeded contract before mirror initialization."""
    response = admin_client.get(PANEL_PATHS[0])

    assert response.status_code == 200
    assert response.data['program']['version'] == 1
    assert response.data['program']['version_id'] == building_on_demand_program.current_revision_id
    assert response.data['program']['author'] == 'Sistema'
    contract = building_on_demand_contract
    assert response.data['contract'] == {
        'version': 1, 'version_id': contract.current_revision_id,
        'updated_at': contract.updated_at.isoformat(), 'author': 'Sistema',
        'change_note': contract.current_revision.change_note,
        'mirror': {
            'status': 'not_initialized', 'document_id': None,
            'title': 'Contrato de alquiler de célula — Building on Demand',
            'folder_id': None, 'folder_path': None, 'version': None, 'last_synced_at': None,
        },
    }
    assert response.data['connector'] == {'slug': 'programs', 'is_active': False}
    assert response.data['pdf_paths'] == {
        'es': '/api/building-on-demand/public/pdf/?lang=es',
        'en': '/api/building-on-demand/public/pdf/?lang=en',
    }


def test_versions_returns_paginated_metadata(building_on_demand_program, admin_client, admin_user):
    """Fails if staff history pagination loses the original version's provenance."""
    initial = building_on_demand_program.current_revision
    apply_operation('update_program', hero_update(read_program()), actor=admin_user)

    response = admin_client.get(PANEL_PATHS[1], {'limit': 1, 'offset': 1})

    assert response.status_code == 200
    assert response.data == {'total': 2, 'versions': [{
        'version_id': initial.pk, 'version': 1, 'author': 'Sistema',
        'created_at': initial.created_at.isoformat(), 'change_note': initial.change_note,
        'restored_from_version_id': None, 'restored_from_version': None,
    }]}


def test_versions_returns_an_empty_page_after_history(building_on_demand_program, admin_client):
    """Fails if a valid offset beyond history raises or returns a previous page."""
    response = admin_client.get(PANEL_PATHS[1], {'limit': 1, 'offset': 10})

    assert response.status_code == 200
    assert response.data == {'total': 1, 'versions': []}


def test_economics_exposes_staff_cost_analysis(building_on_demand_program, admin_client):
    """Fails if the private panel loses hosting costs or the pinned breakeven result."""
    response = admin_client.get(PANEL_PATHS[2])

    assert response.status_code == 200
    assert response.data['hour_cost'] == 55000
    assert response.data['provider'] == 'Hostinger'
    assert response.data['tiers'][0]['hosting_cost_monthly'] == 46291
    assert len(response.data['rows']) == 12
    assert response.data['rows'][0]['breakeven_hours'] == 31.9
    assert response.data['rows'][0]['bag_share_percent'] == 33


@pytest.mark.parametrize('path', PANEL_PATHS)
def test_panel_rejects_non_staff_users(path, django_user_model):
    """Fails if ordinary users can inspect the private economics or revision history."""
    client = APIClient()
    client.force_authenticate(user=django_user_model.objects.create_user(username='bod-reader'))

    response = client.get(path)

    assert response.status_code == 403
    assert response.data['detail'].code == 'permission_denied'


@pytest.mark.parametrize('path', PANEL_PATHS)
def test_panel_requires_authentication(path):
    """Fails if anonymous readers gain access to a private program endpoint."""
    response = APIClient().get(path)

    assert response.status_code in (401, 403)
    assert response.data['detail'].code == 'not_authenticated'


@pytest.mark.parametrize('path', PANEL_PATHS)
@pytest.mark.parametrize('method', ['post', 'patch', 'delete'])
def test_panel_rejects_mutations(building_on_demand_program, admin_client, path, method):
    """Fails if even staff can mutate the MCP-owned program through the panel."""
    response = getattr(admin_client, method)(path, {}, format='json')

    assert response.status_code == 405
    assert BuildingOnDemandProgramRevision.objects.count() == 1


def test_staff_session_can_read_overview(building_on_demand_program, admin_user):
    """Fails if the panel's normal Django session cannot read program metadata."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin_user)

    response = client.get(PANEL_PATHS[0])

    assert response.status_code == 200
    assert response.data['program']['version'] == 1
    assert response.data['public_paths']['es'] == '/es-co/building-on-demand'
