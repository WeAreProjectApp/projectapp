"""Keep new MCP video uploads private without relocating existing MCP files."""
from django.core.files.storage import Storage, default_storage, storages
from django.utils.deconstruct import deconstructible


@deconstructible
class McpUploadStorage(Storage):
    def _storage(self, name):
        return storages['private'] if name.startswith('mcp-video-uploads/') else default_storage

    def _open(self, name, mode='rb'):
        return self._storage(name).open(name, mode)

    def _save(self, name, content):
        return self._storage(name).save(name, content)

    def exists(self, name):
        return self._storage(name).exists(name)

    def delete(self, name):
        return self._storage(name).delete(name)

    def size(self, name):
        return self._storage(name).size(name)

    def path(self, name):
        return self._storage(name).path(name)

    def url(self, name):
        if name.startswith('mcp-video-uploads/'):
            raise ValueError('MCP videos require authenticated access.')
        return default_storage.url(name)
