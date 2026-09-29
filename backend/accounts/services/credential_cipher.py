"""
Symmetric cipher for project access credentials (Django admin passwords).

Stored ciphertext is a Fernet token (base64-encoded, URL-safe). The key must be a
valid Fernet key and live in the ``PROJECT_ACCESS_CIPHER_KEY`` env var.

If the key is missing, the encrypt/decrypt helpers raise
``ImproperlyConfigured``. Empty inputs are returned as empty strings so callers
can treat "no secret saved" uniformly.

Generate a key once with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from decouple import config
from django.core.exceptions import ImproperlyConfigured


def _configured_cipher() -> Fernet:
    key = config('PROJECT_ACCESS_CIPHER_KEY', default='')
    if not key:
        raise ImproperlyConfigured(
            'PROJECT_ACCESS_CIPHER_KEY is not set. Restore the existing key '
            'before creating a new one if encrypted data already exists.',
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            'PROJECT_ACCESS_CIPHER_KEY is not a valid Fernet key.',
        ) from exc


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    return _configured_cipher()


def cipher_configuration_errors():
    """Validate the current configuration without caching or revealing key material."""
    try:
        _configured_cipher()
    except ImproperlyConfigured as exc:
        return [str(exc)]
    return []


def encrypt_secret(plain: str) -> str:
    """Encrypt a plaintext secret. Empty input returns ''."""
    if not plain:
        return ''
    token = _get_cipher().encrypt(plain.encode('utf-8'))
    return token.decode('ascii')


def decrypt_secret(token: str) -> str:
    """Decrypt a stored secret. Empty or invalid input returns ''."""
    if not token:
        return ''
    try:
        return _get_cipher().decrypt(token.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError):
        return ''


def encrypt_password(plain: str) -> str:
    """Backward-compatible password wrapper around :func:`encrypt_secret`."""
    return encrypt_secret(plain)


def decrypt_password(token: str) -> str:
    """Backward-compatible password wrapper around :func:`decrypt_secret`."""
    return decrypt_secret(token)
