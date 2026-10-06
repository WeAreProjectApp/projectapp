"""Private cipher keys must work without becoming versioned credentials."""

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from accounts.services import credential_cipher
from projectapp.checks import check_project_access_cipher


@pytest.fixture(autouse=True)
def file_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', '')
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', str(tmp_path / 'missing.key'))


@pytest.fixture
def key_file(monkeypatch, tmp_path):
    path = tmp_path / 'private.key'
    path.write_bytes(Fernet.generate_key() + b'\n')
    path.chmod(0o600)
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', str(path))
    return path


def test_private_file_key_decrypts_existing_ciphertext(key_file):
    expected = Fernet(key_file.read_bytes().strip()).encrypt(b'protected content')

    assert credential_cipher.decrypt_secret(expected.decode()) == 'protected content'


def test_private_file_key_encrypts_content(key_file):
    encrypted = credential_cipher.encrypt_secret('protected content')

    assert Fernet(key_file.read_bytes().strip()).decrypt(encrypted.encode()) == b'protected content'


def test_default_private_media_file_supplies_the_key(monkeypatch, settings):
    path = Path(settings.PRIVATE_MEDIA_ROOT) / 'runtime-secrets' / 'project-access.key'
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    path.write_bytes(key)
    path.chmod(0o600)
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', '')
    try:
        encrypted = credential_cipher.encrypt_secret('default file')

        assert Fernet(key).decrypt(encrypted.encode()) == b'default file'
    finally:
        path.unlink()


def test_environment_key_takes_precedence_over_file(key_file, monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', key.decode())

    encrypted = credential_cipher.encrypt_secret('environment value')

    assert Fernet(key).decrypt(encrypted.encode()) == b'environment value'


def test_invalid_environment_key_does_not_fall_back_to_file(key_file, monkeypatch):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY', 'invalid-key')

    with pytest.raises(ImproperlyConfigured, match='not a valid Fernet key'):
        credential_cipher.encrypt_secret('protected content')


@pytest.mark.parametrize('mode', [0o644, 0o640])
def test_file_permissions_prevent_key_disclosure(key_file, mode):
    key_file.chmod(mode)

    with pytest.raises(ImproperlyConfigured, match='private, readable regular file'):
        credential_cipher.encrypt_secret('protected content')


def test_symlink_cannot_supply_a_cipher_key(key_file, monkeypatch):
    link = key_file.with_name('link.key')
    link.symlink_to(key_file)
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', str(link))

    with pytest.raises(ImproperlyConfigured, match='private, readable regular file'):
        credential_cipher.encrypt_secret('protected content')


def test_hardlinked_key_is_rejected(key_file):
    os.link(key_file, key_file.with_name('another.key'))

    with pytest.raises(ImproperlyConfigured, match='private, readable regular file'):
        credential_cipher.encrypt_secret('protected content')


def test_directory_cannot_supply_a_cipher_key(key_file, monkeypatch):
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', str(key_file.parent))

    with pytest.raises(ImproperlyConfigured, match='private, readable regular file'):
        credential_cipher.encrypt_secret('protected content')


def test_missing_key_file_reports_configuration_error():
    assert [error.id for error in check_project_access_cipher(None)] == ['projectapp.E002']


@pytest.mark.parametrize('payload', [b'invalid-private-key-material', b'\xff', b'x' * 129, b''])
def test_invalid_key_file_has_a_safe_configuration_error(key_file, payload):
    key_file.write_bytes(payload)

    errors = check_project_access_cipher(None)

    assert [error.id for error in errors] == ['projectapp.E002']
    assert 'invalid-private-key-material' not in str(errors)


def test_deploy_check_accepts_private_key_file(key_file):
    assert check_project_access_cipher(None) == []


def test_deploy_check_detects_removed_key_without_reusing_cache(key_file):
    credential_cipher.encrypt_secret('cached value')
    key_file.unlink()

    assert [error.id for error in check_project_access_cipher(None)] == ['projectapp.E002']


def test_file_owned_by_another_user_is_rejected(key_file, monkeypatch):
    monkeypatch.setattr(credential_cipher.os, 'geteuid', lambda: key_file.stat().st_uid + 1)

    with pytest.raises(ImproperlyConfigured, match='private, readable regular file'):
        credential_cipher.encrypt_secret('protected content')


def test_fifo_cannot_block_cipher_initialization(key_file, monkeypatch):
    fifo = key_file.with_name('pipe.key')
    os.mkfifo(fifo, 0o600)
    monkeypatch.setenv('PROJECT_ACCESS_CIPHER_KEY_FILE', str(fifo))

    with pytest.raises(ImproperlyConfigured, match='private, readable regular file'):
        credential_cipher.encrypt_secret('protected content')
