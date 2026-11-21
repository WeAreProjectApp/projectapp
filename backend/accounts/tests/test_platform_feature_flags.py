"""PA-263 precedence, persistence, isolation and versioned writes."""
import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models_feature_flags import ClientPlatformFeatureSettings, PlatformFeatureEvent, PlatformFeatureSettings
from accounts.services import platform_features as features

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor(admin_user):
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    return admin_user


def test_new_installation_enables_every_catalogued_feature(client_user):
    result = features.values_for(client_user.pk)

    assert result == dict.fromkeys(features.FEATURES, True)
    assert not PlatformFeatureSettings.objects.exists()
    assert not ClientPlatformFeatureSettings.objects.exists()


@pytest.mark.parametrize('key', ['platform.new_reports', 'platform.ai_new_reports'])
def test_new_feature_inherits_its_default_in_existing_accounts(actor, client_user, monkeypatch, key):
    features.update(actor, {'expected_version': 0, 'values': {'platform.ai_chatbot': False}})
    features.update(actor, {'expected_version': 0, 'values': {'platform.documents': False}}, client_user.pk)
    monkeypatch.setitem(features.FEATURES, key, {'key': key, 'default_enabled': True})

    result = features.values_for(client_user.pk)

    assert result[key] is True
    assert result['platform.ai_chatbot'] is False
    assert result['platform.documents'] is False
    assert PlatformFeatureEvent.objects.count() == 2


@pytest.mark.parametrize('global_value', [True, False])
def test_client_without_override_inherits_global(actor, client_user, global_value):
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': global_value}})

    assert features.values_for(client_user.pk)['platform.bugs'] is global_value


@pytest.mark.parametrize(('global_value', 'override'), [(False, True), (True, False)])
def test_explicit_client_value_precedes_global(actor, client_user, global_value, override):
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': global_value}})
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': override}}, client_user.pk)

    result = features.payload(actor, client_user.pk)
    flag = next(item for item in result['features'] if item['key'] == 'platform.bugs')
    assert flag['effective'] is override
    assert flag['source'] == 'client'
    assert ClientPlatformFeatureSettings.objects.get(user=client_user).values['platform.bugs'] is override


def test_removing_override_restores_current_global(actor, client_user):
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': False}})
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': True}}, client_user.pk)

    result = features.update(actor, {'expected_version': 1, 'values': {'platform.bugs': None}}, client_user.pk)

    assert features.values_for(client_user.pk)['platform.bugs'] is False
    assert result['version'] == 2
    assert ClientPlatformFeatureSettings.objects.get(user=client_user).values == {}


def test_other_client_retains_inheritance(actor, client_user, django_user_model):
    other = django_user_model.objects.create_user(username='feature-other')
    from accounts.models import UserProfile
    UserProfile.objects.update_or_create(user=other, defaults={'role': 'client'})
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': False}}, client_user.pk)

    assert features.values_for(client_user.pk)['platform.bugs'] is False
    assert features.values_for(other.pk)['platform.bugs'] is True


@pytest.mark.parametrize('search', ['María Torres', 'TechStartup', 'maria@example.test'])
def test_client_search_matches_displayed_identity(actor, client_user, search):
    client_user.first_name = 'María'
    client_user.last_name = 'Torres'
    client_user.email = 'maria@example.test'
    client_user.save(update_fields=['first_name', 'last_name', 'email'])
    client_user.profile.company_name = 'TechStartup'
    client_user.profile.save(update_fields=['company_name'])

    result = features.list_clients(actor, search=search)

    assert result['results'] == [{'user_id': client_user.pk, 'name': 'María Torres'}]


def test_stale_write_keeps_persisted_value(actor):
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': False}})

    with pytest.raises(features.FeatureConflict):
        features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': True}})

    assert features.values_for()['platform.bugs'] is False
    assert PlatformFeatureEvent.objects.count() == 1


@pytest.mark.parametrize('values', [{'unknown': True}, {'platform.bugs': 'false'}, {'platform.bugs': None}, {}])
def test_invalid_global_change_has_no_effect(actor, values):
    with pytest.raises(ValidationError):
        features.update(actor, {'expected_version': 0, 'values': values})

    assert not PlatformFeatureSettings.objects.exists()
    assert not PlatformFeatureEvent.objects.exists()


def test_client_cannot_administer_flags(client_user):
    with pytest.raises(PermissionDenied):
        features.update(client_user, {'expected_version': 0, 'values': {'platform.bugs': False}})

    assert not PlatformFeatureEvent.objects.exists()


def test_override_refuses_administrator_as_client(actor):
    with pytest.raises(features.NotFound):
        features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': False}}, actor.pk)

    assert not ClientPlatformFeatureSettings.objects.exists()


def test_audit_records_author_scope_before_after(actor, client_user):
    features.update(actor, {'expected_version': 0, 'values': {'platform.bugs': False}}, client_user.pk)

    event = PlatformFeatureEvent.objects.get()
    assert event.actor_id == actor.pk
    assert event.client_id == client_user.pk
    assert event.changes == {'platform.bugs': {'before': None, 'after': False}}

