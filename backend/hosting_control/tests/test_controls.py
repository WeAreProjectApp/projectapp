"""Panel/MCP share one audited, production-scoped write boundary."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from hosting_control.models import Control, Event, RuntimeCredential, Target
from hosting_control.services import runtime_payload
from monitoring.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def control():
    server = Resource.objects.create(key='vps-test', name='VPS de prueba', kind='server')
    resource = Resource.objects.create(key='site-a', name='Sitio A', kind='project', server=server)
    value = Control.objects.create(resource=resource)
    Target.objects.create(control=value, key='site-a', origins=['https://site-a.example'], adapter='django')
    return value


@pytest.fixture
def admin_client():
    user = get_user_model().objects.create_user(username='hosting-admin', is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def machine(control):
    # Disposable fixture, unrelated to any deployed credential.
    credential = RuntimeCredential.objects.create(label='fixture', token_hash=RuntimeCredential.hash_token('fixture-runtime'))
    credential.targets.add(control.targets.get())
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer fixture-runtime')
    return client, credential


def test_initial_control_is_normal(admin_client, control):
    result = admin_client.get(f'/api/hosting-controls/{control.pk}/').json()
    assert result['mode'] == 'normal'
    assert result['targets'][0]['state'] == 'unintegrated'


@pytest.mark.parametrize('mode', ['suspended', 'banner', 'normal'])
def test_transition_persists_one_mode(admin_client, control, mode):
    control.mode = 'banner' if mode != 'banner' else 'suspended'
    control.save()
    response = admin_client.patch(f'/api/hosting-controls/{control.pk}/mode/', {'expected_version': 0, 'mode': mode}, format='json')
    control.refresh_from_db()
    assert response.status_code == 200
    assert control.mode == mode
    assert control.version == 1
    assert Event.objects.get().after['mode'] == mode


def test_message_edit_preserves_other_mode(admin_client, control):
    before = control.suspension_text
    response = admin_client.patch(f'/api/hosting-controls/{control.pk}/message/', {
        'expected_version': 0, 'message_mode': 'banner', 'title': 'Pago de prueba', 'text': 'Contacta al proveedor de prueba.',
    }, format='json')
    control.refresh_from_db()
    assert response.status_code == 200
    assert control.suspension_text == before
    assert control.mode == 'normal'
    assert control.banner_title == 'Pago de prueba'


def test_stale_write_does_not_create_event(admin_client, control):
    response = admin_client.patch(f'/api/hosting-controls/{control.pk}/mode/', {'expected_version': 9, 'mode': 'suspended'}, format='json')
    assert response.status_code == 409
    assert not Event.objects.exists()


def test_non_admin_cannot_change_mode(control):
    user = get_user_model().objects.create_user(username='hosting-client')
    client = APIClient()
    client.force_authenticate(user)
    response = client.patch(f'/api/hosting-controls/{control.pk}/mode/', {'expected_version': 0, 'mode': 'suspended'}, format='json')
    assert response.status_code == 403
    assert not Event.objects.exists()


def test_staging_write_is_rejected(admin_client, control):
    control.resource.environment = 'staging'
    control.resource.save()
    response = admin_client.patch(f'/api/hosting-controls/{control.pk}/mode/', {'expected_version': 0, 'mode': 'suspended'}, format='json')
    assert response.status_code == 403
    assert not Event.objects.exists()


def test_runtime_credential_does_not_grant_panel_access(machine, control):
    client, _ = machine
    assert client.get(f'/api/hosting-controls/{control.pk}/').status_code == 403


def test_download_does_not_confirm_application(machine, admin_client, control):
    client, _ = machine
    result = client.get('/api/hosting-runtime/configs/').json()
    assert result['configs'][0]['mode'] == 'normal'
    assert admin_client.get(f'/api/hosting-controls/{control.pk}/').json()['targets'][0]['state'] == 'unintegrated'


def test_matching_receipt_confirms_site(machine, admin_client, control):
    client, _ = machine
    payload = runtime_payload(control.targets.get())
    result = client.post('/api/hosting-runtime/receipts/', {key: payload[key] for key in ['target_key', 'version', 'digest']} | {'applied': True}, format='json')
    assert result.status_code == 200
    assert admin_client.get(f'/api/hosting-controls/{control.pk}/').json()['targets'][0]['state'] == 'confirmed'


def test_new_message_invalidates_old_receipt(machine, admin_client, control):
    client, _ = machine
    target = control.targets.get()
    target.acknowledged_version = 0
    target.acknowledged_digest = runtime_payload(target)['digest']
    target.last_seen_at = timezone.now()
    target.save()
    admin_client.patch(f'/api/hosting-controls/{control.pk}/message/', {'expected_version': 0, 'message_mode': 'banner', 'title': 'Nuevo título', 'text': 'Nuevo aviso de prueba.'}, format='json')
    assert admin_client.get(f'/api/hosting-controls/{control.pk}/').json()['targets'][0]['state'] == 'pending'


def test_foreign_target_cannot_be_acknowledged(machine, control):
    client, _ = machine
    response = client.post('/api/hosting-runtime/receipts/', {'target_key': 'other', 'version': 0, 'digest': 'a' * 64, 'applied': True}, format='json')
    assert response.status_code == 404


def test_stale_receipt_is_rejected(machine, control):
    client, _ = machine
    response = client.post('/api/hosting-runtime/receipts/', {'target_key': 'site-a', 'version': 0, 'digest': 'a' * 64, 'applied': True}, format='json')
    assert response.status_code == 409


def test_unknown_switch_fields_are_rejected(admin_client, control):
    response = admin_client.patch(f'/api/hosting-controls/{control.pk}/mode/', {'expected_version': 0, 'mode': 'banner', 'suspended': True}, format='json')
    assert response.status_code == 400
    assert not Event.objects.exists()


def test_changing_one_project_preserves_another(admin_client, control):
    other = Control.objects.create(resource=Resource.objects.create(key='site-b', name='Sitio B', kind='project'))
    admin_client.patch(f'/api/hosting-controls/{control.pk}/mode/', {'expected_version': 0, 'mode': 'suspended'}, format='json')
    other.refresh_from_db()
    assert other.mode == 'normal'
    assert other.version == 0


def test_failed_application_does_not_confirm_intent(machine, admin_client, control):
    client, _ = machine
    value = runtime_payload(control.targets.get())
    client.post('/api/hosting-runtime/receipts/', {key: value[key] for key in ['target_key', 'version', 'digest']} | {'applied': False}, format='json')
    result = admin_client.get(f'/api/hosting-controls/{control.pk}/').json()['targets'][0]
    assert result['state'] == 'error'
    assert result['acknowledged_version'] is None


def test_runtime_payload_does_not_expose_inactive_message(machine, control):
    client, _ = machine
    control.mode = 'banner'
    control.suspension_text = 'Texto inactivo privado de prueba'
    control.save()
    result = client.get('/api/hosting-runtime/configs/').json()
    assert result['configs'][0]['message']['text'] == control.banner_text
    assert 'Texto inactivo privado de prueba' not in json.dumps(result)


def test_monitoring_switch_does_not_hide_hosting_control(machine, control):
    client, _ = machine
    control.resource.enabled = False
    control.resource.save()
    result = client.get('/api/hosting-runtime/configs/').json()
    assert result['configs'][0]['target_key'] == 'site-a'
