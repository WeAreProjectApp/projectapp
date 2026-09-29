"""Deployment diagnostics must reject unusable keys without revealing them."""
import pytest
from cryptography.fernet import Fernet

from accounts.services.credential_cipher import _get_cipher
from projectapp.checks import check_project_access_cipher


@pytest.mark.parametrize('key', ['', 'invalid-private-key-material'])
def test_deploy_check_reports_unusable_key(monkeypatch, key):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', key)

    errors = check_project_access_cipher(None)

    assert [error.id for error in errors] == ['projectapp.E002']
    assert 'invalid-private-key-material' not in str(errors)


def test_deploy_check_accepts_fernet_key(monkeypatch):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', Fernet.generate_key().decode())

    assert check_project_access_cipher(None) == []


def test_deploy_check_does_not_reuse_cached_cipher(monkeypatch):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', Fernet.generate_key().decode())
    _get_cipher.cache_clear()
    _get_cipher()
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', '')

    errors = check_project_access_cipher(None)

    assert [error.id for error in errors] == ['projectapp.E002']
    _get_cipher.cache_clear()
