"""Creation failures must be actionable without exposing sensitive content."""

import pytest
from accounts.services import credential_cipher
from rest_framework.test import APIClient

from secure_links import services
from secure_links.models import SecureLink, SecureLinkEvent

pytestmark = pytest.mark.django_db

BASE = '/api/secure-links/'
CUSTOM_FIELDS = {'custom_name': 'Instrucciones privadas', 'content': '  Línea uno\nLínea dos  '}


@pytest.mark.parametrize('key', ['', 'invalid-key'])
@pytest.mark.parametrize('path', ['create/', 'public/create/'])
def test_cipher_configuration_failure_returns_actionable_json(staff_client, monkeypatch, caplog, key, path):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', key)
    credential_cipher._get_cipher.cache_clear()

    response = staff_client.post(BASE + path, {
        'secret_type': 'credentials', 'title': 'Acceso',
        'fields': {'password': 'never-log-this-value'}, 'creator_name': 'Ana',
    }, format='json')

    assert response.status_code == 503
    assert response.json()['code'] == 'secure_links_unavailable'
    assert 'Contacta al administrador' in response.json()['error']
    assert 'never-log-this-value' not in response.content.decode()
    assert 'never-log-this-value' not in caplog.text
    assert not SecureLink.objects.exists()
    assert not SecureLinkEvent.objects.exists()


@pytest.mark.parametrize('associations', [{}, {'client': None, 'project': None}])
def test_create_without_associations_returns_usable_link(staff_client, associations):
    response = staff_client.post(BASE + 'create/', {
        'secret_type': 'credentials', 'title': 'Acceso',
        'fields': {'password': 'test-value'}, **associations,
    }, format='json')

    assert response.status_code == 201
    assert response.json()['client'] is None
    assert response.json()['project'] is None
    token = response.json()['url'].split('#')[1]
    revealed = APIClient().post(BASE + 'public/reveal/', {'token': token}, format='json')
    assert revealed.json()['fields'][0]['value'] == 'test-value'


def test_create_with_only_client(staff_client, client_profile):
    response = staff_client.post(BASE + 'create/', {
        'secret_type': 'credentials', 'title': 'Acceso',
        'fields': {'password': 'test-value'}, 'client': client_profile.pk,
    }, format='json')

    assert response.status_code == 201
    assert response.json()['client'] == client_profile.pk
    assert response.json()['project'] is None


def test_custom_content_is_encrypted_until_explicit_reveal(staff_client):
    created = staff_client.post(BASE + 'create/', {
        'secret_type': 'custom', 'title': 'Referencia interna', 'fields': CUSTOM_FIELDS,
    }, format='json')
    assert created.status_code == 201
    token = created.json()['url'].split('#')[1]
    guest = APIClient()

    status = guest.post(BASE + 'public/status/', {'token': token}, format='json')
    revealed = guest.post(BASE + 'public/reveal/', {'token': token}, format='json')
    repeated = guest.post(BASE + 'public/reveal/', {'token': token}, format='json')

    assert status.json()['type_label'] == 'Personalizado'
    assert CUSTOM_FIELDS['custom_name'] not in str(status.json())
    assert CUSTOM_FIELDS['content'] not in SecureLink.objects.get().payload_encrypted
    assert {field['key']: field['value'] for field in revealed.json()['fields']} == CUSTOM_FIELDS
    assert repeated.status_code == 410


@pytest.mark.parametrize('field,value', [
    ('custom_name', ''), ('content', '   '),
    ('custom_name', 'x' * 201), ('content', 'x' * 15001),
])
def test_custom_content_reports_invalid_field(staff_client, field, value):
    response = staff_client.post(BASE + 'create/', {
        'secret_type': 'custom', 'title': 'Referencia',
        'fields': {**CUSTOM_FIELDS, field: value},
    }, format='json')

    assert response.status_code == 400
    assert field in response.json()
    assert not SecureLink.objects.exists()


def test_public_custom_link_remains_team_only(staff_client):
    guest = APIClient()
    created = guest.post(BASE + 'public/create/', {
        'secret_type': 'custom', 'fields': CUSTOM_FIELDS, 'creator_name': 'Ana',
    }, format='json')
    assert created.status_code == 201
    token = created.json()['url'].split('#')[1]

    denied = guest.post(BASE + 'public/reveal/', {'token': token}, format='json')
    revealed = staff_client.post(BASE + 'public/reveal/', {'token': token}, format='json')

    assert denied.status_code == 403
    assert revealed.json()['fields'][1]['value'] == CUSTOM_FIELDS['content']


def test_edit_replaces_custom_content(staff_client, make_link):
    link, _url = make_link()

    response = staff_client.patch(BASE + f'{link.pk}/', {
        'secret_type': 'custom', 'fields': CUSTOM_FIELDS,
    }, format='json')

    assert response.status_code == 200
    link.refresh_from_db()
    assert services.content_for(link)['fields'][0]['value'] == CUSTOM_FIELDS['custom_name']
