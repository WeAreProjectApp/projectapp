"""Commit-only cleanup for an explicitly confirmed project purge."""

from contextlib import contextmanager
from contextvars import ContextVar
import logging

from django.apps import apps
from django.db import models, transaction

from content.storage import get_private_storage

logger = logging.getLogger(__name__)
_purging = ContextVar('project_file_cleanup', default=False)


def project_cleanup_active():
    return _purging.get()


@contextmanager
def deferred_project_cleanup():
    token = _purging.set(True)
    try:
        yield
    finally:
        _purging.reset(token)


def _image_paths(image):
    return set(image.get('paths', {}).values()) if isinstance(image, dict) else set()


def _package_paths(assets, screenshots=None):
    paths = set()
    for image in (assets or {}).values():
        paths.update(_image_paths(image))
    paths.update((screenshots or {}).values())
    return paths


def project_row_files(row):
    files = []
    for field in row._meta.concrete_fields:
        if isinstance(field, models.FileField):
            value = getattr(row, field.name)
            if value:
                files.append((value.storage, value.name))
    paths = set()
    if row._meta.label_lower == 'content.linktreeasset':
        paths = _image_paths(row.image)
    elif row._meta.label_lower == 'content.linktreetemplateversion':
        paths = _package_paths(row.assets, row.screenshots)
    files.extend((get_private_storage(), path) for path in paths if path)
    return files


def _retained_package_paths():
    # Template packages are independent catalog entries. A version or a
    # library image on another card can also share these private files.
    from content.models import LinktreeAsset, LinktreeTemplate, LinktreeTemplateVersion
    paths = set()
    for image in LinktreeAsset.objects.values_list('image', flat=True).iterator():
        paths.update(_image_paths(image))
    for assets in LinktreeTemplate.objects.values_list('assets', flat=True).iterator():
        paths.update(_package_paths(assets))
    for assets, screenshots in LinktreeTemplateVersion.objects.values_list('assets', 'screenshots').iterator():
        paths.update(_package_paths(assets, screenshots))
    return paths


def schedule_project_files(files):
    """Retained proposal/history files win over cleanup of any shared name."""
    files = {(id(storage), name): (storage, name) for storage, name in files if name}
    if not files:
        return

    def cleanup():
        names = {name for _, name in files.values()}
        retained = _retained_package_paths()
        for model in apps.get_models():
            for field in model._meta.concrete_fields:
                if isinstance(field, models.FileField):
                    retained.update(model._base_manager.filter(
                        **{f'{field.name}__in': names},
                    ).values_list(field.name, flat=True))
        for storage, name in files.values():
            if name in retained:
                continue
            try:
                storage.delete(name)
            except Exception:
                # The database commit is final; a failed cleanup must not make
                # the caller retry a deletion that already happened.
                logger.exception('Project purge file cleanup failed: %s', name)

    transaction.on_commit(cleanup, robust=True)
