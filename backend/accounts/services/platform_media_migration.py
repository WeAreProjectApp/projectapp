"""Inventory and verified conversion of resource files, including retained rows.

The immutable private manifest binds every file to its original bytes and owner.
Conversion changes only the file pointer, after copying and checking the bytes.
Public originals remain in place; HTTP denial is independent of conversion.
"""
import hashlib
import json
import os
import re
import uuid
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.files.storage import storages
from django.db import transaction

from accounts.platform_media_storage import resource_storage, resource_storage_kind

SCHEMA = 1
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _models():
    from accounts.models import (
        Deliverable,
        DeliverableClientUpload,
        DeliverableFile,
        DeliverableVersion,
    )
    return (Deliverable, DeliverableVersion, DeliverableFile, DeliverableClientUpload)


def _rows(*, lock=False):
    rows = []
    for model in _models():
        query = model._base_manager.exclude(file='').filter(file__isnull=False).order_by('pk')
        if lock:
            query = query.select_for_update()
        elif model._meta.model_name == 'deliverable':
            query = query.select_related('project', 'retention_context')
        else:
            query = query.select_related('deliverable__project', 'deliverable__retention_context')
        rows.extend(query)
    return rows


def _owner(row):
    parent = row if row._meta.model_name == 'deliverable' else row.deliverable
    return {
        'deliverable_id': parent.pk,
        'project_id': parent.project_id,
        'client_id': parent.project.client_id if parent.project_id else None,
        'retention_context_id': parent.retention_context_id,
        'retained_client_id': parent.retention_context.client_id if parent.retention_context_id else None,
    }


def _hash(name):
    digest, size = hashlib.sha256(), 0
    with resource_storage(name).open(name, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _roots():
    public = Path(storages['default'].path('')).resolve()
    private = Path(storages['private'].path('')).resolve()
    if private == public or private.is_relative_to(public):
        raise ValueError('El almacenamiento privado no puede estar dentro de media pública.')
    if private != Path(settings.PRIVATE_MEDIA_ROOT).resolve():
        raise ValueError('La configuración del almacenamiento privado no coincide.')
    return {'public': str(public), 'private': str(private)}


def _target(model, pk, name, digest):
    if resource_storage_kind(name) == 'private':
        return name
    return f'platform-resources/migrated/{model}/{pk}/{digest}/{PurePosixPath(name).name}'


def build_inventory():
    """Read all four families, even without a live project or with no root file."""
    records = []
    for row in _rows():
        record = {'model': row._meta.label_lower, 'id': row.pk, 'name': row.file.name,
                  'owner': _owner(row)}
        try:
            digest, size = _hash(record['name'])
            record.update(storage=resource_storage_kind(record['name']), sha256=digest, size=size,
                          target_name=_target(record['model'], row.pk, record['name'], digest), status='ready')
        except (OSError, ValueError):
            record.update(status='blocked', error='source_unavailable')
        records.append(record)
    return {'schema': SCHEMA, 'roots': _roots(), 'records': records}


def _manifest_path(path):
    path = Path(path).resolve()
    directory = Path(settings.PRIVATE_MEDIA_ROOT).resolve() / 'migration_manifests'
    if path.parent != directory or path.suffix != '.json':
        raise ValueError('Guarda el manifest JSON dentro de private_media/migration_manifests.')
    return path


def write_inventory(path):
    """Write a new private manifest; never overwrite an approved inventory."""
    path = _manifest_path(path)
    inventory = build_inventory()
    raw = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    return {'manifest': str(path), 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'files': len(inventory['records']),
            'blocked': sum(row['status'] == 'blocked' for row in inventory['records'])}


def _load(path, expected_sha256):
    path = _manifest_path(path)
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(expected_sha256):
        raise ValueError('Indica el SHA-256 exacto del manifest.')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('El manifest cambió; genera y revisa un inventario nuevo.')
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('roots') != _roots():
        raise ValueError('El manifest no corresponde a este almacenamiento.')
    records = data.get('records')
    if not isinstance(records, list):
        raise ValueError('El manifest no contiene un inventario válido.')
    labels, seen = {model._meta.label_lower for model in _models()}, set()
    for record in records:
        if (not isinstance(record, dict) or record.get('model') not in labels
                or type(record.get('id')) is not int or record['id'] < 1
                or record.get('status') != 'ready' or not isinstance(record.get('owner'), dict)
                or type(record.get('size')) is not int or record['size'] < 0
                or not isinstance(record.get('sha256'), str) or not SHA256.fullmatch(record['sha256'])):
            raise ValueError('El inventario contiene un archivo bloqueado o inválido.')
        key = (record['model'], record['id'])
        if key in seen:
            raise ValueError('El inventario contiene registros duplicados.')
        seen.add(key)
        if (record.get('storage') != resource_storage_kind(record.get('name'))
                or record.get('target_name') != _target(*key, record['name'], record['sha256'])):
            raise ValueError('El destino del inventario no coincide con su archivo.')
    return records


def _validate_current(records, rows):
    current = {(row._meta.label_lower, row.pk): row for row in rows}
    expected = {(record['model'], record['id']) for record in records}
    if set(current) != expected:
        raise ValueError('El conjunto de archivos cambió; revisa un inventario nuevo.')
    for record in records:
        row = current[(record['model'], record['id'])]
        if _owner(row) != record['owner'] or row.file.name not in (record['name'], record['target_name']):
            raise ValueError('El propietario o el archivo cambió; revisa un inventario nuevo.')
        if _hash(row.file.name) != (record['sha256'], record['size']):
            raise ValueError('Los bytes del archivo cambiaron; revisa un inventario nuevo.')
    return current


def _allow_apply():
    """Only the deployed production command or the isolated pytest boundary writes."""
    test_root = getattr(settings, 'TEST_FILE_ROOT', None)
    selected_module = os.environ.get('DJANGO_SETTINGS_MODULE') or settings.SETTINGS_MODULE
    in_test = (selected_module == 'projectapp.settings_test'
        and os.environ.get('PYTEST_CURRENT_TEST')
        and not settings.IS_PRODUCTION and settings.DJANGO_ENV != 'production'
        and settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
        and test_root and Path(test_root).resolve().name.startswith('projectapp-pytest-')
        and Path(settings.MEDIA_ROOT).resolve().is_relative_to(Path(test_root).resolve())
        and Path(settings.PRIVATE_MEDIA_ROOT).resolve().is_relative_to(Path(test_root).resolve()))
    if in_test:
        return
    if '.wt' in Path(settings.BASE_DIR).resolve().parts:
        raise ValueError('La conversión no se ejecuta desde un worktree de sesión.')
    if selected_module != 'projectapp.settings_prod' or not settings.IS_PRODUCTION:
        raise ValueError('Ejecuta la conversión desde el checkout desplegado con settings_prod.')


def _lock_owners(records):
    from content.models import ProjectRetentionContext

    from accounts.models import Deliverable, Project
    owners = [record['owner'] for record in records]
    project_ids = {owner.get('project_id') for owner in owners} - {None}
    context_ids = {owner.get('retention_context_id') for owner in owners} - {None}
    parent_ids = {owner.get('deliverable_id') for owner in owners} - {None}
    list(Project.objects.select_for_update().filter(pk__in=project_ids).order_by('pk'))
    list(ProjectRetentionContext.objects.select_for_update().filter(pk__in=context_ids).order_by('pk'))
    list(Deliverable._base_manager.select_for_update().filter(pk__in=parent_ids).order_by('pk'))


def _copy(record, created):
    target = record['target_name']
    private = storages['private']
    if private.exists(target):
        if _hash(target) != (record['sha256'], record['size']):
            raise ValueError('La copia privada existente no coincide; no se reemplaza.')
        return
    stage = f'platform-resources/migration-staging/{uuid.uuid4().hex}.bin'
    created.append(stage)
    with resource_storage(record['name']).open(record['name'], 'rb') as source:
        saved = private.save(stage, source)
    created.append(saved)
    if _hash(saved) != (record['sha256'], record['size']):
        raise ValueError('La copia privada no pasó la verificación de bytes.')
    destination = Path(private.path(target))
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        # Exclusive publication preserves a previously existing verified copy.
        os.link(private.path(saved), destination)
    except FileExistsError:
        if _hash(target) != (record['sha256'], record['size']):
            raise ValueError('La copia privada existente no coincide; no se reemplaza.')
    else:
        created.append(target)
    private.delete(saved)


def privatize(path, expected_sha256, *, apply=False):
    """Copy, verify, lock and rebind; replay is safe and originals are preserved."""
    records = _load(path, expected_sha256)
    if not apply:
        _validate_current(records, _rows())
        return {'manifest_sha256': expected_sha256, 'planned': sum(row['storage'] == 'legacy' for row in records)}
    _allow_apply()
    created, converted = [], 0
    try:
        with transaction.atomic():
            _lock_owners(records)
            current = _validate_current(records, _rows(lock=True))
            for record in records:
                row = current[(record['model'], record['id'])]
                if row.file.name == record['target_name']:
                    continue
                _copy(record, created)
                if _hash(row.file.name) != (record['sha256'], record['size']):
                    raise ValueError('El original cambió durante la copia; no se modifica su registro.')
                changed = type(row)._base_manager.filter(pk=row.pk, file=row.file.name).update(file=record['target_name'])
                if changed != 1:
                    raise ValueError('El archivo cambió durante la conversión.')
                converted += 1
    except Exception:
        for name in created:
            if not any(model._base_manager.filter(file=name).exists() for model in _models()):
                storages['private'].delete(name)
        raise
    return {'manifest_sha256': expected_sha256, 'converted': converted,
            'already_private': len(records) - converted, 'originals_deleted': 0}
