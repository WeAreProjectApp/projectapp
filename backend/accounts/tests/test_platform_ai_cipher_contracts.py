"""Private Platform AI credential key contracts."""

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models_ai import PlatformAICredential
from accounts.services import platform_ai_cipher


@pytest.fixture(autouse=True)
def clean_ai_cipher_configuration(monkeypatch, settings, tmp_path):
    """Isolate cipher configuration from any server-owned key file."""
    settings.PLATFORM_AI_CIPHER_KEY = ''
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY', '')
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY_FILE', str(tmp_path / 'missing-ai.key'))


def test_environment_key_round_trips_a_provider_secret(monkeypatch):
    """Fails if an environment-supplied AI key cannot protect a provider credential."""
    key = Fernet.generate_key()
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY', key.decode())

    token = platform_ai_cipher.encrypt('provider-secret')

    assert token != 'provider-secret'
    assert Fernet(key).decrypt(token.encode()) == b'provider-secret'
    assert platform_ai_cipher.decrypt(token) == 'provider-secret'


def test_private_file_key_encrypts_a_provider_secret(monkeypatch, tmp_path):
    """Fails if the protected runtime key file cannot encrypt a saved provider credential."""
    path = tmp_path / 'runtime-secrets' / 'platform-ai.key'
    path.parent.mkdir(mode=0o700)
    key = Fernet.generate_key()
    path.write_bytes(key + b'\n')
    path.chmod(0o600)
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY_FILE', str(path))

    token = platform_ai_cipher.encrypt('file-backed-secret')

    assert Fernet(key).decrypt(token.encode()) == b'file-backed-secret'


def test_cipher_rejects_an_insecure_private_key_file(monkeypatch, tmp_path):
    """Fails if a world-readable runtime key file can decrypt provider credentials."""
    path = tmp_path / 'platform-ai.key'
    path.write_bytes(Fernet.generate_key())
    path.chmod(0o644)
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY_FILE', str(path))

    with pytest.raises(ImproperlyConfigured, match='Configura la llave privada'):
        platform_ai_cipher.encrypt('provider-secret')


def test_cipher_rejects_a_token_from_another_key(monkeypatch):
    """Fails if a credential encrypted on another installation is accepted as this server's secret."""
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY', Fernet.generate_key().decode())
    foreign_token = Fernet(Fernet.generate_key()).encrypt(b'provider-secret').decode()

    with pytest.raises(ImproperlyConfigured, match='No se puede descifrar'):
        platform_ai_cipher.decrypt(foreign_token)


@pytest.mark.django_db
def test_key_command_creates_a_private_file_without_exposing_its_value(monkeypatch, settings, tmp_path, capsys):
    """Fails if first-time key provisioning creates a public key or prints its secret."""
    path = tmp_path / 'runtime-secrets' / 'platform-ai.key'
    settings.PRIVATE_MEDIA_ROOT = tmp_path
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY_FILE', str(path))

    call_command('initialize_platform_ai_key')
    output = capsys.readouterr().out

    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(path.read_bytes().strip()) == 44
    assert path.read_text().strip() not in output


@pytest.mark.django_db
def test_key_command_refuses_to_replace_a_missing_key_after_credentials_exist(monkeypatch, settings, tmp_path):
    """Fails if provisioning replaces a lost key and makes stored provider credentials unrecoverable."""
    path = tmp_path / 'runtime-secrets' / 'platform-ai.key'
    settings.PRIVATE_MEDIA_ROOT = tmp_path
    monkeypatch.setenv('AI_CREDENTIALS_CIPHER_KEY_FILE', str(path))
    PlatformAICredential.objects.create(provider='openai', encrypted_value='existing-ciphertext')

    with pytest.raises(CommandError, match='falta su llave'):
        call_command('initialize_platform_ai_key')

    assert not path.exists()
