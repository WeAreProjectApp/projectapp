"""Dedicated AI credential key: external to the database, never generated on a read."""
import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from decouple import config
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def cipher():
    key = getattr(settings, 'PLATFORM_AI_CIPHER_KEY', '') or config('AI_CREDENTIALS_CIPHER_KEY', default='')
    if not key:
        path = config('AI_CREDENTIALS_CIPHER_KEY_FILE', default='') or Path(settings.PRIVATE_MEDIA_ROOT) / 'runtime-secrets' / 'platform-ai.key'
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_uid not in (0, os.geteuid()) or info.st_size > 128 or info.st_nlink != 1:
                    raise ValueError
                key = stream.read(129).decode('ascii').strip()
        except (OSError, ValueError, UnicodeError) as exc:
            raise ImproperlyConfigured('Configura la llave privada de cifrado de IA antes de guardar credenciales.') from exc
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured('La llave privada de cifrado de IA no es válida.') from exc


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise ImproperlyConfigured('No se puede descifrar la credencial de IA.') from exc
