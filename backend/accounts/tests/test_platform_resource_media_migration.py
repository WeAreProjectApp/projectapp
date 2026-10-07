"""Verified conversion is atomic, owner-bound and safe to repeat."""
import json
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from accounts.services import platform_media_migration as migration
from accounts.tests.platform_media_helpers import (
    KINDS,
    file_names,
    legacy_files,
    manifest_path,
)
from accounts.tests.platform_media_helpers import media_context as media_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def inventory(media_context, tmp_path):
    """Approve the actual stored names, owner and bytes of all four families."""
    legacy_files(media_context)
    path = manifest_path(tmp_path.name)
    summary = migration.write_inventory(path)
    return {'path': path, 'sha': summary['manifest_sha256'],
            'data': json.loads(path.read_text()), 'before': file_names(media_context)}


class FailSecondSave:
    """Simulate a disk write failure after one real private copy was created."""

    def __init__(self, save):
        """Keep the real external storage boundary for the first operation."""
        self.save = save
        self.calls = 0

    def __call__(self, name, content, **kwargs):
        """Raise on the second copy, leaving transaction rollback to the service."""
        self.calls += 1
        if self.calls == 2:
            raise OSError('isolated disk failure')
        return self.save(name, content, **kwargs)


def test_media_conversion_preview_keeps_original_references(media_context, inventory):
    """Fails if inspecting an approved inventory mutates file pointers."""
    result = migration.privatize(inventory['path'], inventory['sha'])
    assert result['planned'] == 4
    assert file_names(media_context) == inventory['before']


@pytest.mark.parametrize('kind', KINDS)
def test_media_conversion_preserves_the_original_bytes(media_context, inventory, kind):
    """Fails if any family changes bytes or removes its historical original."""
    result = migration.privatize(inventory['path'], inventory['sha'], apply=True)
    row = media_context['rows'][kind]
    row.refresh_from_db()
    assert result['converted'] == 4
    assert row.file.name.startswith('platform-resources/migrated/')
    assert Path(row.file.path).read_bytes() == media_context['bodies'][kind]
    assert Path(storages['default'].path(inventory['before'][kind])).read_bytes() == media_context['bodies'][kind]


def test_media_conversion_replay_keeps_the_existing_private_references(media_context, inventory):
    """Fails if retrying the same approved manifest creates another conversion."""
    migration.privatize(inventory['path'], inventory['sha'], apply=True)
    converted = file_names(media_context)
    replay = migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert replay['converted'] == 0
    assert replay['already_private'] == 4
    assert file_names(media_context) == converted


def test_media_conversion_rejects_a_changed_owner(media_context, inventory):
    """Fails if conversion approves a different client than the reviewed manifest."""
    project = media_context['project']
    project.client = media_context['foreign']
    project.save(update_fields=['client'])
    with pytest.raises(ValueError, match='propietario'):
        migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert file_names(media_context) == inventory['before']


def test_media_conversion_rejects_changed_source_bytes(media_context, inventory):
    """Fails if conversion silently accepts a file modified after inventory."""
    Path(storages['default'].path(inventory['before']['current'])).write_bytes(b'changed source')
    with pytest.raises(ValueError, match='bytes'):
        migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert file_names(media_context) == inventory['before']


def test_media_conversion_rejects_a_changed_file_pointer(media_context, inventory):
    """Fails if identical bytes at a new pointer bypass the reviewed selection."""
    name = storages['default'].save('deliverables/replaced.pdf', ContentFile(media_context['bodies']['current']))
    resource = media_context['resource']
    type(resource)._base_manager.filter(pk=resource.pk).update(file=name)
    before = file_names(media_context)
    with pytest.raises(ValueError, match='archivo cambió'):
        migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert file_names(media_context) == before


def test_media_conversion_rejects_a_tampered_manifest(media_context, inventory):
    """Fails if conversion trusts JSON that differs from the approved SHA-256."""
    inventory['path'].write_bytes(inventory['path'].read_bytes() + b' ')
    with pytest.raises(ValueError, match='manifest cambió'):
        migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert file_names(media_context) == inventory['before']


def test_media_conversion_rolls_back_after_a_copy_failure(media_context, inventory, monkeypatch):
    """Fails if a disk failure leaves partial pointers or deletes original bytes."""
    private = storages['private']
    monkeypatch.setattr(private, 'save', FailSecondSave(private.save))
    with pytest.raises(OSError, match='disk failure'):
        migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert file_names(media_context) == inventory['before']
    assert not private.exists(inventory['data']['records'][0]['target_name'])
    assert Path(storages['default'].path(inventory['before']['current'])).read_bytes() == media_context['bodies']['current']


def test_media_conversion_refuses_worktree_apply_outside_pytest(media_context, inventory, monkeypatch):
    """Fails if a session worktree can write the symlinked production database."""
    monkeypatch.delenv('PYTEST_CURRENT_TEST')
    with pytest.raises(ValueError, match='worktree'):
        migration.privatize(inventory['path'], inventory['sha'], apply=True)
    assert file_names(media_context) == inventory['before']


def test_media_inventory_blocks_a_missing_source(media_context, tmp_path):
    """Fails if a missing original is treated as a successful private conversion."""
    legacy_files(media_context)
    before = file_names(media_context)
    storages['default'].delete(before['current'])
    path = manifest_path(tmp_path.name)
    inventory = migration.write_inventory(path)
    assert inventory['blocked'] == 1
    with pytest.raises(ValueError, match='bloqueado'):
        migration.privatize(path, inventory['manifest_sha256'], apply=True)
    assert file_names(media_context) == before


def test_media_inventory_cannot_be_published_outside_private_storage(media_context, tmp_path):
    """Fails if ownership, paths and hashes can be written under a public root."""
    path = tmp_path / 'inventory.json'
    with pytest.raises(ValueError, match='private_media'):
        migration.write_inventory(path)
    assert not path.exists()
