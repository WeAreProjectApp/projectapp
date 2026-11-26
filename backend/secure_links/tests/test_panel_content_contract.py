"""PA-304. Exercise the panel catalog through its authenticated HTTP endpoints."""
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from secure_links.models import SecureLink, SecureLinkEvent

from .conftest import token_from

pytestmark = pytest.mark.django_db
BASE = '/api/secure-links/'
MINIMUM = {
    'credentials': 'password',
    'api_key': 'secret_key',
    'server_access': 'credential',
    'database': 'password',
    'env_vars': 'content',
    'bank_account': 'account_number',
    'recovery_codes': 'codes',
    'confidential_message': 'message',
    'custom': 'content',
}


def panel_content(client, link_id):
    response = client.post(f'{BASE}{link_id}/content/')
    assert response.status_code == 200
    return {field['key']: field['value'] for field in response.json()['fields']}


def test_catalog_advertises_the_panel_minimum_for_each_type(staff_client):
    types = staff_client.get(BASE + 'public/types/').json()['types']

    assert {
        item['key']: [field['key'] for field in item['fields'] if field['panel_required']]
        for item in types
    } == {key: [field] for key, field in MINIMUM.items()}
    assert {
        (item['key'], field['key']) for item in types for field in item['fields'] if field['panel_create_hidden']
    } == {('credentials', 'service'), ('credentials', 'url')}


@pytest.mark.parametrize('kind,essential', MINIMUM.items())
def test_minimal_panel_content_round_trips_through_edit(staff_client, kind, essential):
    fields = {essential: '  Contenido ficticio  '}
    created = staff_client.post(BASE + 'create/', {
        'secret_type': kind, 'title': 'Prueba de contenido mínimo', 'fields': fields,
    }, format='json')
    assert created.status_code == 201
    link_id = created.json()['id']
    assert panel_content(staff_client, link_id) == fields

    types = staff_client.get(BASE + 'public/types/').json()['types']
    definition = next(item for item in types if item['key'] == kind)
    blank_optionals = {field['key']: '' for field in definition['fields'] if field['key'] != essential}
    updated = {essential: '  Otro contenido ficticio  '}
    saved = staff_client.patch(f'{BASE}{link_id}/', {'fields': {**blank_optionals, **updated}}, format='json')

    assert saved.status_code == 200
    assert panel_content(staff_client, link_id) == updated


@pytest.mark.parametrize('kind,essential', MINIMUM.items())
@pytest.mark.parametrize('fields_for', [lambda key: {}, lambda key: {key: ' \n '}], ids=['omitted', 'whitespace'])
def test_missing_panel_content_identifies_the_field(staff_client, kind, essential, fields_for):
    response = staff_client.post(BASE + 'create/', {
        'secret_type': kind, 'title': 'Prueba de validación', 'fields': fields_for(essential),
    }, format='json')

    assert response.status_code == 400
    assert response.json()['field_codes'] == {essential: 'required'}
    assert response.json()[essential]
    assert not SecureLink.objects.exists()
    assert not SecureLinkEvent.objects.exists()


def test_historical_credential_survives_panel_edits(staff_client, make_link):
    fields = {'service': 'Sistema de prueba', 'url': 'https://sistema.example', 'password': 'Ficticio'}
    link, _url = make_link(fields=fields)
    ciphertext = link.payload_encrypted
    renamed = staff_client.patch(f'{BASE}{link.pk}/', {'title': 'Otro título'}, format='json')
    assert renamed.status_code == 200
    link.refresh_from_db()
    assert link.payload_encrypted == ciphertext
    read_fields = panel_content(staff_client, link.pk)
    assert read_fields == fields

    saved = staff_client.patch(f'{BASE}{link.pk}/', {'fields': {**read_fields, 'note': 'Otra nota'}}, format='json')

    assert saved.status_code == 200
    assert panel_content(staff_client, link.pk) == {**fields, 'note': 'Otra nota'}
    assert saved.json()['status'] == 'active'
    assert saved.json()['expires_at'] == renamed.json()['expires_at']


@pytest.mark.parametrize('days', [1, 3, 7, 30])
@pytest.mark.parametrize('rotate,old_status', [(False, 200), (True, 404)], ids=['retain', 'rotate'])
@freeze_time('2026-11-26T12:00:00Z')
def test_expired_link_reactivation_grants_one_use(staff_client, make_link, days, rotate, old_status):
    link, url = make_link()
    SecureLink.objects.filter(pk=link.pk).update(expires_at=timezone.now() - timedelta(days=1))
    guest = APIClient()

    response = staff_client.post(f'{BASE}{link.pk}/reactivate/', {'validity_days': days, 'rotate': rotate}, format='json')

    assert response.status_code == 200
    link.refresh_from_db()
    assert link.expires_at == timezone.now() + timedelta(days=days)
    assert link.events.get(kind=SecureLinkEvent.Kind.REACTIVATED).details['rotated'] is rotate
    assert (response.json()['url'] != url) is rotate
    assert guest.post(BASE + 'public/status/', {'token': token_from(url)}, format='json').status_code == old_status
    current = {'token': token_from(response.json()['url'])}
    assert guest.post(BASE + 'public/reveal/', current, format='json').status_code == 200
    assert guest.post(BASE + 'public/reveal/', current, format='json').status_code == 410
