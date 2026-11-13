"""Availability administration rejects invalid input and preserves audit scope."""
import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import ResolverMatch
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory

from accounts.feature_permissions import PlatformFeatureAvailable
from accounts.models import UserProfile
from accounts.models_feature_flags import PlatformFeatureEvent, PlatformFeatureSettings
from accounts.services import platform_features as features

pytestmark = pytest.mark.django_db


@pytest.fixture
def feature_admin(admin_user):
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    return admin_user


@pytest.fixture
def feature_api(api_client, feature_admin):
    api_client.force_authenticate(feature_admin)
    return api_client


def test_client_search_matches_company(feature_api, client_user, django_user_model):
    UserProfile.objects.filter(user=client_user).update(company_name='Atlas')
    other = django_user_model.objects.create_user(username='feature-company-other')
    UserProfile.objects.create(user=other, role='client', company_name='Boreal')

    response = feature_api.get('/api/platform/features/admin/clients/', {'search': 'Atlas'})

    assert response.status_code == 200
    assert [row['user_id'] for row in response.data['results']] == [client_user.pk]
    assert response.data['count'] == 1


def test_client_search_rejects_oversized_fragment(feature_api):
    response = feature_api.get('/api/platform/features/admin/clients/', {'search': 'x' * 201})

    assert response.status_code == 400


@pytest.mark.parametrize(('scope', 'expected'), [('all', {'global', 'client'}), ('client', {'client'})])
def test_audit_filter_selects_requested_scope(feature_api, feature_admin, client_user, scope, expected):
    features.update(feature_admin, {'expected_version': 0, 'values': {'platform.requirement_packages': False}})
    features.update(feature_admin, {'expected_version': 0, 'values': {'platform.requirement_packages': True}}, client_user.pk)
    query = {'all': {}, 'client': {'user_id': str(client_user.pk)}}[scope]

    response = feature_api.get('/api/platform/features/admin/events/', query)

    assert response.status_code == 200
    assert {row['scope'] for row in response.data['results']} == expected


@pytest.mark.parametrize('user_id', ['bad-id', '0'])
def test_audit_filter_rejects_invalid_client_identifier(feature_api, user_id):
    response = feature_api.get('/api/platform/features/admin/events/', {'user_id': user_id})

    assert response.status_code == 400


@pytest.mark.parametrize('body', [
    [],
    {'expected_version': 0, 'values': {'platform.requirement_packages': False}, 'extra': True},
    {'expected_version': True, 'values': {'platform.requirement_packages': False}},
])
def test_malformed_configuration_has_no_side_effect(feature_api, body):
    response = feature_api.patch('/api/platform/features/admin/', body, format='json')

    assert response.status_code == 400
    assert not PlatformFeatureSettings.objects.exists()
    assert not PlatformFeatureEvent.objects.exists()


def test_availability_rejects_unknown_feature(client_user):
    with pytest.raises(ValidationError):
        features.enabled(client_user, 'platform.not_registered')


def test_availability_rejects_anonymous_actor():
    with pytest.raises(PermissionDenied):
        features.enabled(AnonymousUser(), 'platform.requirement_packages')


def test_availability_rejects_actor_without_platform_profile(django_user_model):
    actor = django_user_model.objects.create_user(username='feature-unprofiled')

    with pytest.raises(PermissionDenied):
        features.enabled(actor, 'platform.requirement_packages')


def test_unclassified_platform_operation_is_denied(client_user):
    request = APIRequestFactory().get('/api/unclassified-platform-operation/')
    request.user = client_user
    request.resolver_match = ResolverMatch(lambda request: None, (), {}, url_name='unclassified-platform-operation')

    with pytest.raises(PermissionDenied, match='disponibilidad'):
        PlatformFeatureAvailable().has_permission(request, None)
