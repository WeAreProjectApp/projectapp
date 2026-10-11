"""Private cell contract reads preserve provenance and the Panel session boundary."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from content.models import BuildingOnDemandContract
from content.services import building_on_demand_contract_service as service
from content.tests.building_on_demand_fixtures import contract_update

pytestmark = pytest.mark.django_db
CONTRACT_ROUTES = [
    'admin-building-on-demand-contract', 'admin-building-on-demand-contract-versions',
    'admin-building-on-demand-contract-pdf',
]


def test_contract_read_exposes_seed_provenance(admin_client, building_on_demand_contract):
    """Fails if the private endpoint drops the initial Markdown or its revision identity."""
    revision = building_on_demand_contract.current_revision

    response = admin_client.get(reverse(CONTRACT_ROUTES[0]))

    assert response.status_code == 200
    assert response.data == {
        'markdown': revision.markdown, 'version': 1, 'version_id': revision.pk,
        'updated_at': building_on_demand_contract.updated_at.isoformat(), 'author': 'Sistema',
        'change_note': revision.change_note, 'etag': service.resource_etags()['contract'],
        'mirror': {
            'status': 'not_initialized', 'document_id': None, 'title': service.CONTRACT_TITLE,
            'folder_id': None, 'folder_path': None, 'version': None, 'last_synced_at': None,
        },
    }


def test_contract_read_links_the_synchronized_document(
    admin_client, building_on_demand_contract, pinned_contracts_folder, superuser,
):
    """Fails if staff cannot find the live Gestor mirror through the contract endpoint."""
    synced = service.sync_mirror(actor=superuser)

    response = admin_client.get(reverse(CONTRACT_ROUTES[0]))

    assert response.status_code == 200
    assert response.data['mirror'] == synced['mirror']
    assert response.data['mirror']['status'] == 'synchronized'
    assert response.data['mirror']['folder_path'] == 'ProjectApp › Contratos'
    assert response.data['version_id'] == building_on_demand_contract.current_revision_id


def test_overview_contains_the_contract_summary(
    admin_client, building_on_demand_program, building_on_demand_contract, pinned_contracts_folder, superuser,
):
    """Fails if the overview loses the contract provenance or returns its full Markdown."""
    synced = service.sync_mirror(actor=superuser)
    contract = building_on_demand_contract

    response = admin_client.get(reverse('admin-building-on-demand-overview'))

    assert response.status_code == 200
    assert response.data['contract'] == {
        'version': 1, 'version_id': contract.current_revision_id,
        'updated_at': contract.updated_at.isoformat(), 'author': 'Sistema',
        'change_note': contract.current_revision.change_note, 'mirror': synced['mirror'],
    }
    assert response.data['program']['version_id'] == building_on_demand_program.current_revision_id


def test_overview_accepts_an_absent_contract(admin_client, building_on_demand_program, building_on_demand_contract):
    """Fails if the overview cannot represent an installation without the contract singleton."""
    BuildingOnDemandContract.objects.filter(pk=building_on_demand_contract.pk).delete()

    response = admin_client.get(reverse('admin-building-on-demand-overview'))

    assert response.status_code == 200
    assert response.data['contract'] is None
    assert response.data['program']['version_id'] == building_on_demand_program.current_revision_id


def test_contract_history_pages_the_original_revision(
    admin_client, building_on_demand_contract, pinned_contracts_folder, admin_user,
):
    """Fails if contract history pagination loses the original author or restore provenance."""
    initial = building_on_demand_contract.current_revision
    service.apply_update(contract_update(service.read_contract()), actor=admin_user)

    response = admin_client.get(reverse(CONTRACT_ROUTES[1]), {'limit': 1, 'offset': 1})

    assert response.status_code == 200
    assert response.data == {'total': 2, 'versions': [{
        'version_id': initial.pk, 'version': 1, 'author': initial.author_label,
        'created_at': initial.created_at.isoformat(), 'change_note': initial.change_note,
        'restored_from_version_id': None, 'restored_from_version': None,
    }]}


def test_contract_history_returns_an_empty_trailing_page(admin_client, building_on_demand_contract):
    """Fails if a valid trailing history offset repeats a contract revision."""
    response = admin_client.get(reverse(CONTRACT_ROUTES[1]), {'limit': 1, 'offset': 3})

    assert response.status_code == 200
    assert response.data == {'total': 1, 'versions': []}


@pytest.mark.parametrize(('route', 'content_type'), [
    (CONTRACT_ROUTES[0], 'application/json'), (CONTRACT_ROUTES[1], 'application/json'),
    (CONTRACT_ROUTES[2], 'application/pdf'),
])
def test_contract_endpoint_accepts_a_staff_session(admin_user, building_on_demand_contract, route, content_type):
    """Fails if the Panel's Django session cannot read a private contractual resource."""
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin_user)

    response = client.get(reverse(route))

    assert response.status_code == 200
    assert response['Content-Type'] == content_type


@pytest.mark.parametrize('route', CONTRACT_ROUTES)
def test_contract_endpoint_denies_non_staff_readers(django_user_model, route):
    """Fails if a regular authenticated user gains access to private cell contract data."""
    client = APIClient()
    client.force_authenticate(user=django_user_model.objects.create_user(username='cell-contract-reader'))

    response = client.get(reverse(route))

    assert response.status_code == 403
    assert response.data['detail'].code == 'permission_denied'


@pytest.mark.parametrize('route', CONTRACT_ROUTES)
def test_contract_endpoint_denies_anonymous_readers(route):
    """Fails if an anonymous request reads the private contract, history, or PDF."""
    response = APIClient().get(reverse(route))

    assert response.status_code == 403
    assert response.data['detail'].code == 'not_authenticated'


@pytest.mark.parametrize('route', CONTRACT_ROUTES)
def test_contract_endpoint_refuses_platform_jwt(admin_user, route):
    """Fails if a valid Platform JWT crosses the private Panel session boundary."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin_user)}')

    response = client.get(reverse(route))

    assert response.status_code == 403
    assert response.data['detail'].code == 'not_authenticated'
