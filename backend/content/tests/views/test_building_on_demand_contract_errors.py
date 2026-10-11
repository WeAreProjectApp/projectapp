"""Real cell contract errors retain the published HTTP shape without accepting writes."""
import pytest
from django.urls import reverse

from content.models import BuildingOnDemandContract, BuildingOnDemandContractMirror, BuildingOnDemandContractRevision

pytestmark = pytest.mark.django_db
HISTORY_ROUTE = 'admin-building-on-demand-contract-versions'


@pytest.mark.parametrize('field', ['limit', 'offset'])
def test_contract_history_rejects_non_integer_queries(admin_client, field):
    """Fails if malformed contract pagination becomes a server error."""
    response = admin_client.get(reverse(HISTORY_ROUTE), {field: 'invalid'})

    assert response.status_code == 400
    assert response.data == {
        'limit': ['Usa un entero entre 1 y 50.'], 'offset': ['Usa un entero no negativo.'],
    }


@pytest.mark.parametrize('query', [{'limit': 0}, {'limit': 51}, {'offset': -1}])
def test_contract_history_rejects_out_of_range_queries(admin_client, query):
    """Fails if invalid contract pagination escapes the service's structured error mapping."""
    response = admin_client.get(reverse(HISTORY_ROUTE), query)

    assert response.status_code == 400
    assert response.data == {
        'message': 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.',
        'code': 'VALIDATION_ERROR', 'details': {},
    }


@pytest.mark.parametrize('route', ['admin-building-on-demand-contract', 'admin-building-on-demand-contract-pdf'])
def test_contract_endpoint_reports_a_missing_singleton(admin_client, building_on_demand_contract, route):
    """Fails if an absent contract is exposed as an empty result or a server error."""
    BuildingOnDemandContract.objects.filter(pk=building_on_demand_contract.pk).delete()

    response = admin_client.get(reverse(route))

    assert response.status_code == 404
    assert response.data == {
        'message': 'El contrato no está configurado.', 'code': 'NOT_FOUND', 'details': {},
    }


@pytest.mark.parametrize('route', [
    'admin-building-on-demand-contract', 'admin-building-on-demand-contract-versions',
    'admin-building-on-demand-contract-pdf',
])
@pytest.mark.parametrize('method', ['post', 'patch', 'delete'])
def test_contract_endpoint_refuses_mutations(admin_client, building_on_demand_contract, route, method):
    """Fails if a Panel write changes the MCP-owned contract or initializes its mirror."""
    before_revision = building_on_demand_contract.current_revision_id

    response = getattr(admin_client, method)(reverse(route), {'markdown': '# Cambio prohibido'}, format='json')
    building_on_demand_contract.refresh_from_db()

    assert response.status_code == 405
    assert building_on_demand_contract.current_revision_id == before_revision
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert not BuildingOnDemandContractMirror.objects.exists()
