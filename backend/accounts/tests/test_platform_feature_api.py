"""Real URL resolution enforces availability without replacing authorization."""
import pytest
from rest_framework.test import APIClient

from accounts.models_feature_flags import ClientPlatformFeatureSettings, PlatformFeatureSettings
from accounts.services import platform_features

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_api(client_user):
    api = APIClient()
    api.force_authenticate(client_user)
    return api


def test_self_evaluation_rejects_client_selector(client_api):
    response = client_api.get('/api/platform/features/?user_id=999')

    assert response.status_code == 400


def test_self_evaluation_is_private(client_api, client_user):
    response = client_api.get('/api/platform/features/')

    assert response.status_code == 200
    assert response.data['user_id'] == client_user.pk
    assert response.data['features']['platform.ai_chatbot'] is False
    assert response['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('url', [
    '/api/accounts/bug-reports/', '/api/accounts/projects/1/bug-reports/',
    '/api/accounts/projects/1/bug-reports/1/',
])
def test_disabled_bug_routes_are_denied(client_api, client_user, url):
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.bugs': False})

    response = client_api.get(url)

    assert response.status_code == 403
    assert response.data['code'] == 'feature_disabled'


def test_disabled_bug_creation_has_no_side_effect(client_api, client_user, project):
    from accounts.models import BugReport
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.bugs': False})

    response = client_api.post(f'/api/accounts/projects/{project.pk}/bug-reports/', {'title': 'Blocked'}, format='json')

    assert response.status_code == 403
    assert not BugReport.objects.filter(title='Blocked').exists()


def test_disabled_portal_blocks_pdf(client_api, client_user):
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.documents': False})

    response = client_api.get('/api/accounts/documents/00000000-0000-0000-0000-000000000001/pdf/')

    assert response.status_code == 403
    assert response.data['feature'] == 'platform.documents'


def test_enabled_flag_does_not_grant_administration(client_api):
    response = client_api.get('/api/platform/features/admin/')

    assert response.status_code == 403


def test_panel_updates_persist_with_csrf(admin_user):
    from django.middleware.csrf import get_token
    from django.test import RequestFactory
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    api = APIClient(enforce_csrf_checks=True)
    api.force_login(admin_user)
    request = RequestFactory().get('/')
    token = get_token(request)
    api.cookies['csrftoken'] = request.META['CSRF_COOKIE']

    response = api.patch('/api/platform/features/admin/', {'expected_version': 0, 'values': {'platform.documents': False}},
                         format='json', HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 200
    assert PlatformFeatureSettings.objects.get().values == {'platform.documents': False}


def test_panel_rejects_missing_csrf(admin_user):
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    api = APIClient(enforce_csrf_checks=True)
    api.force_login(admin_user)

    response = api.patch('/api/platform/features/admin/', {'expected_version': 0, 'values': {'platform.documents': False}}, format='json')

    assert response.status_code == 403
    assert not PlatformFeatureSettings.objects.exists()


def test_admin_role_keeps_support_routes(api_client, admin_user):
    PlatformFeatureSettings.objects.create(values={'platform.bugs': False})
    api_client.force_authenticate(admin_user)

    response = api_client.get('/api/accounts/bug-reports/')

    assert response.status_code == 200


def test_client_override_reenables_global_disabled_route(client_api, client_user):
    PlatformFeatureSettings.objects.create(values={'platform.bugs': False})
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.bugs': True})

    response = client_api.get('/api/accounts/bug-reports/')

    assert response.status_code == 200


def test_project_summary_omits_disabled_module_data(client_api, client_user, project):
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={
        'platform.bugs': False, 'platform.delivery': False, 'platform.hosting': False,
    })

    response = client_api.get(f'/api/accounts/projects/{project.pk}/')

    assert response.status_code == 200
    assert response.data['bugs_open_count'] is None
    assert response.data['phases_total_amount'] is None
    assert response.data['next_hosting_payment'] is None


def test_disabled_delivery_blocks_generated_contract_route(client_api, client_user, project):
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.delivery': False})

    response = client_api.get(f'/api/accounts/projects/{project.pk}/delivery/contracts/')

    assert response.status_code == 403
    assert response.data['code'] == 'feature_disabled'


def test_jwt_request_reloads_changed_availability(client_user):
    from accounts.services.tokens import get_tokens_for_user
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(client_user)["access"]}')
    assert api.get('/api/accounts/bug-reports/').status_code == 200
    ClientPlatformFeatureSettings.objects.create(user=client_user, values={'platform.bugs': False})

    response = api.get('/api/accounts/bug-reports/')

    assert response.status_code == 403
    assert response.data['code'] == 'feature_disabled'
