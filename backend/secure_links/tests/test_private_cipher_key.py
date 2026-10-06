"""The panel must create usable single-use links with a private file key."""

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from secure_links.models import SecureLink


@pytest.fixture
def private_cipher_key(monkeypatch, settings):
    path = Path(settings.PRIVATE_MEDIA_ROOT) / 'runtime-secrets' / 'project-access.key'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(Fernet.generate_key())
    path.chmod(0o600)
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', '')
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', '')
    yield path
    path.unlink()


@pytest.mark.django_db
def test_panel_create_uses_the_private_cipher_key(staff_client, private_cipher_key):
    response = staff_client.post('/api/secure-links/create/', {
        'secret_type': 'credentials', 'title': 'Private key validation',
        'fields': {'password': 'synthetic-private-value'},
    }, format='json')

    assert response.status_code == 201
    assert 'synthetic-private-value' not in SecureLink.objects.get().payload_encrypted


@pytest.mark.django_db
def test_recipient_reveals_file_encrypted_content_once(staff_client, private_cipher_key):
    created = staff_client.post('/api/secure-links/create/', {
        'secret_type': 'credentials', 'title': 'Private key validation',
        'fields': {'password': 'synthetic-private-value'},
    }, format='json')
    token = created.json()['url'].split('#', 1)[1]
    guest = APIClient()

    first = guest.post('/api/secure-links/public/reveal/', {'token': token}, format='json')
    repeated = guest.post('/api/secure-links/public/reveal/', {'token': token}, format='json')

    assert first.status_code == 200
    assert first.json()['fields'][0]['value'] == 'synthetic-private-value'
    assert repeated.status_code == 410
    assert repeated.json()['code'] == 'link_consumed'


@pytest.mark.django_db
def test_unsafe_private_key_file_leaves_no_link(staff_client, private_cipher_key):
    private_cipher_key.chmod(0o644)

    response = staff_client.post('/api/secure-links/create/', {
        'secret_type': 'credentials', 'title': 'Private key validation',
        'fields': {'password': 'synthetic-private-value'},
    }, format='json')

    assert response.status_code == 503
    assert response.json()['code'] == 'secure_links_unavailable'
    assert not SecureLink.objects.exists()
