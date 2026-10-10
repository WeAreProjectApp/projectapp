"""HTTP error contracts exercise the real Building with Us services."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from rest_framework.test import APIClient

from content.models import BuildingWithUsContract, BuildingWithUsProgram, BuildingWithUsProgramRevision
from content.services import building_with_us_contract_service as contract_service

pytestmark = pytest.mark.django_db
HISTORY_PATHS = [
    '/api/building-with-us/admin/program/versions/',
    '/api/building-with-us/admin/contract/versions/',
]
PUBLIC_PATHS = ['/api/building-with-us/public/', '/api/building-with-us/public/pdf/']


@pytest.mark.parametrize('path', HISTORY_PATHS)
@pytest.mark.parametrize('field', ['limit', 'offset'])
def test_history_rejects_non_integer_queries(admin_client, path, field):
    """Fails if malformed pagination raises a server error at either history endpoint."""
    response = admin_client.get(path, {field: 'invalid'})

    assert response.status_code == 400
    assert response.data == {
        'limit': ['Usa un entero entre 1 y 50.'],
        'offset': ['Usa un entero no negativo.'],
    }


@pytest.mark.parametrize('path', HISTORY_PATHS)
@pytest.mark.parametrize('query', [{'limit': 0}, {'limit': 51}, {'offset': -1}])
def test_history_rejects_out_of_range_queries(admin_client, path, query):
    """Fails if a service pagination error loses its HTTP status or machine-readable code."""
    response = admin_client.get(path, query)

    assert response.status_code == 400
    assert response.data == {
        'message': 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.',
        'code': 'VALIDATION_ERROR', 'details': {},
    }


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_reports_a_missing_program(building_with_us_program, path):
    """Fails if a missing presentation becomes a 500 or an empty public PDF."""
    BuildingWithUsProgram.objects.filter(pk=building_with_us_program.pk).delete()

    response = APIClient().get(path)

    assert response.status_code == 404
    assert response.data == {
        'message': 'La presentación no está configurada.', 'code': 'NOT_FOUND', 'details': {},
    }


def test_overview_reports_a_missing_program(admin_client, building_with_us_program):
    """Fails if the private overview hides the absent presentation singleton."""
    BuildingWithUsProgram.objects.filter(pk=building_with_us_program.pk).delete()

    response = admin_client.get('/api/building-with-us/admin/')

    assert response.status_code == 404
    assert response.data == {
        'message': 'La presentación no está configurada.', 'code': 'NOT_FOUND', 'details': {},
    }


@pytest.mark.parametrize('path', [
    '/api/building-with-us/admin/', '/api/building-with-us/admin/contract/',
    '/api/building-with-us/admin/contract/pdf/',
])
def test_private_endpoint_reports_a_missing_contract(admin_client, building_with_us_contract, path):
    """Fails if missing private contract data is converted into a server error."""
    BuildingWithUsContract.objects.filter(pk=building_with_us_contract.pk).delete()

    response = admin_client.get(path)

    assert response.status_code == 404
    assert response.data == {
        'message': 'El contrato no está configurado.', 'code': 'NOT_FOUND', 'details': {},
    }


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_refuses_invalid_stored_content(building_with_us_program, path):
    """Fails if invalid legacy content leaks public economic figures through JSON or PDF."""
    content = deepcopy(building_with_us_program.current_revision.content)
    content['es']['hero']['title'] = 'Aporte USD'
    BuildingWithUsProgramRevision.objects.filter(pk=building_with_us_program.current_revision_id).update(content=content)

    response = APIClient().get(path)

    assert response.status_code == 400
    assert response.data == {
        'message': 'La presentación pública no admite porcentajes ni importes.',
        'code': 'PUBLIC_FIGURE_NOT_ALLOWED', 'details': {'path': 'es.hero.title'},
    }


def test_contract_pdf_reports_a_render_failure(admin_client, building_with_us_contract, monkeypatch):
    """Fails if renderer failure escapes the private PDF endpoint's structured error contract."""
    renderer = Mock(side_effect=RuntimeError('Renderer unavailable'))
    monkeypatch.setattr(contract_service.DocumentPdfService, 'generate_from_markdown', renderer)

    response = admin_client.get('/api/building-with-us/admin/contract/pdf/')

    assert response.status_code == 400
    assert response.data == {'message': 'El PDF vigente no está disponible.', 'code': 'PDF_RENDER_FAILED', 'details': {}}
    renderer.assert_called_once()
