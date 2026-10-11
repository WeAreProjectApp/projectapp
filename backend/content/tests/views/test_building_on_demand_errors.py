"""HTTP error mappings exercise real Building on Demand service validation."""
from copy import deepcopy

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from content.models import BuildingOnDemandProgram, BuildingOnDemandProgramRevision

pytestmark = pytest.mark.django_db
HISTORY_PATH = '/api/building-on-demand/admin/program/versions/'
PUBLIC_PATHS = ['/api/building-on-demand/public/', '/api/building-on-demand/public/pdf/']


@pytest.mark.parametrize('field', ['limit', 'offset'])
def test_history_rejects_non_integer_queries(admin_client, field):
    """Fails if malformed pagination raises a server error instead of a field error."""
    response = admin_client.get(HISTORY_PATH, {field: 'invalid'})

    assert response.status_code == 400
    assert response.data == {
        'limit': ['Usa un entero entre 1 y 50.'], 'offset': ['Usa un entero no negativo.'],
    }


@pytest.mark.parametrize('query', [{'limit': 0}, {'limit': 51}, {'offset': -1}])
def test_history_rejects_out_of_range_queries(admin_client, query):
    """Fails if invalid pagination loses the service's structured validation error."""
    response = admin_client.get(HISTORY_PATH, query)

    assert response.status_code == 400
    assert response.data == {
        'message': 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.',
        'code': 'VALIDATION_ERROR', 'details': {},
    }


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_reports_a_missing_program(building_on_demand_program, path):
    """Fails if an absent singleton becomes a server error or an empty public download."""
    BuildingOnDemandProgram.objects.filter(pk=building_on_demand_program.pk).delete()

    response = APIClient().get(path)

    assert response.status_code == 404
    assert response.data == {
        'message': 'La presentación no está configurada.', 'code': 'NOT_FOUND', 'details': {},
    }


@pytest.mark.parametrize('path', ['/api/building-on-demand/admin/', '/api/building-on-demand/admin/economics/'])
def test_private_endpoint_reports_a_missing_program(building_on_demand_program, admin_client, path):
    """Fails if private inspection hides the absent program singleton."""
    BuildingOnDemandProgram.objects.filter(pk=building_on_demand_program.pk).delete()

    response = admin_client.get(path)

    assert response.status_code == 404
    assert response.data['code'] == 'NOT_FOUND'
    assert response.data['details'] == {}


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_refuses_invalid_stored_copy(building_on_demand_program, path):
    """Fails if invalid historic text can leak public figures through JSON or PDF."""
    content = deepcopy(building_on_demand_program.current_revision.content)
    content['es']['hero']['title'] = 'Aporte USD'
    BuildingOnDemandProgramRevision.objects.filter(pk=building_on_demand_program.current_revision_id).update(content=content)

    response = APIClient().get(path)

    assert response.status_code == 400
    assert response.data['code'] == 'PUBLIC_FIGURE_NOT_ALLOWED'
    assert response.data['details'] == {'path': 'es.hero.title'}


def test_economics_refuses_invalid_stored_inputs(building_on_demand_program, admin_client):
    """Fails if staff receives a calculation based on an invalid stored hourly cost."""
    content = deepcopy(building_on_demand_program.current_revision.content)
    content['internal']['hour_cost'] = 0
    BuildingOnDemandProgramRevision.objects.filter(pk=building_on_demand_program.current_revision_id).update(content=content)

    response = admin_client.get('/api/building-on-demand/admin/economics/')

    assert response.status_code == 400
    assert response.data['code'] == 'VALIDATION_ERROR'
    assert response.data['details'] == {'path': 'internal.hour_cost'}


@pytest.mark.parametrize('path', [
    '/api/building-on-demand/admin/', '/api/building-on-demand/admin/program/versions/',
    '/api/building-on-demand/admin/economics/',
])
def test_private_endpoint_rejects_platform_jwt(admin_user, path):
    """Fails if a valid platform token bypasses the panel's Django session boundary."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin_user)}')

    response = client.get(path)

    assert response.status_code == 403
    assert response.data['detail'].code == 'not_authenticated'
