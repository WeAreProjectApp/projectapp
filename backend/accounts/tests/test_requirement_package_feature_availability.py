"""Package availability is enforced before client business operations."""
import pytest

from accounts.models_feature_flags import ClientPlatformFeatureSettings, PlatformFeatureSettings
from accounts.models_requirement_packages import PackageOrder, PackageRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def package_client(api_client, client_user):
    api_client.force_authenticate(client_user)
    return api_client


@pytest.mark.parametrize(('method', 'path'), [
    ('get', 'projects/1/'),
    ('get', 'examples/'),
    ('get', 'projects/1/examples/'),
    ('get', 'projects/1/requests/1/'),
    ('post', 'projects/1/orders/'),
    ('post', 'projects/1/orders/00000000-0000-0000-0000-000000000001/checkout/'),
    ('post', 'projects/1/requests/'),
    ('post', 'projects/1/requests/1/decide/'),
])
def test_disabled_package_endpoint_denies_client(package_client, client_user, method, path):
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.requirement_packages': False})

    response = getattr(package_client, method)('/api/requirement-packages/' + path, {}, format='json')

    assert response.status_code == 403
    assert response.data['code'] == 'feature_disabled'
    assert response.data['feature'] == 'platform.requirement_packages'


@pytest.mark.parametrize(('path', 'model'), [('orders/', PackageOrder), ('requests/', PackageRequest)])
def test_disabled_package_creation_has_no_side_effect(package_client, client_user, project, path, model):
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.requirement_packages': False})

    response = package_client.post(f'/api/requirement-packages/projects/{project.pk}/{path}', {}, format='json')

    assert response.status_code == 403
    assert not model.objects.exists()


def test_package_administrator_retains_support_access(api_client, admin_user, project):
    PlatformFeatureSettings.objects.create(values={'platform.requirement_packages': False})
    api_client.force_authenticate(admin_user)

    response = api_client.get(f'/api/requirement-packages/projects/{project.pk}/')

    assert response.status_code == 200
    assert response.data['project_id'] == project.pk


def test_client_override_reenables_own_package_workspace(package_client, client_user, project):
    PlatformFeatureSettings.objects.create(values={'platform.requirement_packages': False})
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.requirement_packages': True})

    response = package_client.get(f'/api/requirement-packages/projects/{project.pk}/')

    assert response.status_code == 200
    assert response.data['project_id'] == project.pk
