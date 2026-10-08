"""Private resource storage with an explicit, read-only legacy namespace.

Old database names still identify files in public storage. New names identify
private storage exclusively; a missing private file never falls back to media.
Callers authorize the record before opening it. No storage URL is available.
"""
from pathlib import PurePosixPath

from django.core.files.storage import Storage, storages

PRIVATE_PREFIX = 'platform-resources/'
LEGACY_PREFIX = 'deliverables/'


def resource_storage_kind(name):
    """Validate the persisted name without normalizing or changing its meaning."""
    if (not isinstance(name, str) or not name or '\\' in name
            or any(ord(char) < 32 for char in name)
            or any(part in ('', '.', '..') for part in name.split('/'))
            or PurePosixPath(name).is_absolute()):
        raise ValueError('Nombre de archivo de recurso inválido.')
    if name.startswith(PRIVATE_PREFIX):
        return 'private'
    if name.startswith(LEGACY_PREFIX):
        return 'legacy'
    raise ValueError('El archivo no pertenece al almacenamiento de recursos.')


def resource_storage(name):
    """Select exactly one namespace; never reinterpret a legacy pointer."""
    return storages['private' if resource_storage_kind(name) == 'private' else 'default']


class PlatformResourceStorage(Storage):
    """Write private bytes; permit authorized callers to read historical names."""

    @property
    def location(self):
        """Expose the effective write root to the existing test isolation guard."""
        return storages['private'].location

    def _open(self, name, mode='rb'):
        if mode not in ('r', 'rb'):
            raise ValueError('La lectura de recursos no permite modificar el archivo.')
        return resource_storage(name).open(name, mode)

    def _save(self, name, content):
        if resource_storage_kind(name) != 'private':
            raise ValueError('Las cargas nuevas deben usar almacenamiento privado.')
        return storages['private'].save(name, content)

    def exists(self, name):
        return resource_storage(name).exists(name)

    def size(self, name):
        return resource_storage(name).size(name)

    def path(self, name):
        return resource_storage(name).path(name)

    def delete(self, name):
        if resource_storage_kind(name) != 'private':
            raise ValueError('La conversión conserva el original histórico.')
        return storages['private'].delete(name)

    def url(self, name):
        # ModelForm widgets can inspect this property without publishing a URL.
        return None


def get_platform_resource_storage():
    """Callable storage entry point serialized by Django migrations."""
    return PlatformResourceStorage()


def open_retained_file(value):
    """Read after the retained-record route has applied its own session guards."""
    return value.open('rb')
