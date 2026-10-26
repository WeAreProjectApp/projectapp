"""Single transactional writer for secure-link filing (panel and MCP)."""
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from accounts.retention import READ_ONLY_MESSAGE
from content.services.folder_tree import descendant_ids
from .models import SecureLink, SecureLinkEvent, SecureLinkFolder, SecureLinkFolderLock

UNSET = object()


def error(message, code='invalid_folder', status=400):
    from .services import SecureLinkError
    raise SecureLinkError(message, code=code, status=status)


def lock_tree():
    SecureLinkFolderLock.objects.get_or_create(pk=1)
    SecureLinkFolderLock.objects.select_for_update().get(pk=1)


def editable(row):
    if row.retention_context_id:
        error(READ_ONLY_MESSAGE, 'retained_read_only', 409)


def folder_for(pk, *, lock=False):
    rows = SecureLinkFolder.objects
    if lock:
        rows = rows.select_for_update()
    folder = rows.filter(pk=pk).first()
    if folder is None:
        error('La carpeta ya no existe.', 'folder_not_found', 404)
    return folder


def tree_rows(*, lock=False):
    rows = SecureLinkFolder.objects.all()
    if lock:
        rows = rows.select_for_update()
    return list(rows.values_list('pk', 'parent_id'))


def subtree(folder, *, lock=False):
    return {folder.pk} | descendant_ids(tree_rows(lock=lock), folder.pk)


def revision(row, expected, *, label='carpeta'):
    if not expected:
        return
    try:
        stamp = parse_datetime(expected) if isinstance(expected, str) else expected
    except (TypeError, ValueError):
        stamp = None
    if stamp is None or timezone.is_naive(stamp):
        error('Envía una revisión de fecha y hora con zona horaria.', 'invalid_revision')
    if row.updated_at != stamp:
        error(f'El registro de {label} cambió. Actualiza los datos antes de continuar.', 'version_conflict', 409)


def active_target(folder):
    if folder:
        editable(folder)
        if folder.is_archived:
            error('Restaura la carpeta antes de guardar contenido en ella.', 'folder_archived', 409)


@transaction.atomic
def ensure_project_root(project):
    lock_tree()
    profile = getattr(project.client, 'profile', None)
    root, _ = SecureLinkFolder.objects.get_or_create(
        managed_project=project,
        defaults={'project': project, 'client': profile, 'name': project.name},
    )
    updates = {'name': project.name, 'client': profile, 'project': project}
    if any(getattr(root, key) != value for key, value in updates.items()):
        for key, value in updates.items():
            setattr(root, key, value)
        root.save(update_fields=[*updates, 'updated_at'])
    return root


def initial_location(folder, client, project):
    """Omitted location auto-files; explicit null means unfiled. Inherit once."""
    if folder is UNSET:
        folder = ensure_project_root(project) if project is not UNSET and project else None
    if folder is not None:
        folder = folder_for(folder.pk, lock=True)
        active_target(folder)
        if project is UNSET:
            project = folder.project
        if client is UNSET:
            client = folder.client
    return folder, None if client is UNSET else client, None if project is UNSET else project


@transaction.atomic
def save_folder(*, data, folder=None, actor=None, expected_updated_at=None):
    lock_tree()
    if folder:
        folder = folder_for(folder.pk, lock=True)
        editable(folder)
        revision(folder, expected_updated_at)
        if folder.managed_project_id:
            error('La carpeta automática se administra desde el proyecto.', 'managed_folder', 409)
    else:
        folder = SecureLinkFolder(created_by=actor)
    if 'parent' in data:
        parent = data['parent']
        if parent:
            parent = folder_for(parent.pk, lock=True)
            active_target(parent)
            if folder.pk and parent.pk in subtree(folder, lock=True):
                error('Una carpeta no puede quedar dentro de sí misma o de sus subcarpetas.', 'folder_cycle', 409)
        folder.parent = parent
        if not folder.pk and parent:
            folder.client, folder.project = parent.client, parent.project
    for field in ('name', 'client', 'project'):
        if field in data:
            setattr(folder, field, data[field])
    folder.name = folder.name.strip()
    if not folder.name or len(folder.name) > 120:
        error('Escribe un nombre de hasta 120 caracteres.')
    if folder.client_id and folder.project_id and folder.project.client_id != folder.client.user_id:
        error('El proyecto no pertenece a ese cliente.', 'project_client_mismatch')
    if folder.project_id and not folder.client_id:
        folder.client = getattr(folder.project.client, 'profile', None)
    if not folder.pk:
        folder.order = (SecureLinkFolder.objects.filter(parent=folder.parent).aggregate(last=Max('order'))['last'] or 0) + 1
    folder.save()
    return folder


@transaction.atomic
def delete_folder(folder, *, expected_updated_at=None):
    lock_tree()
    folder = folder_for(folder.pk, lock=True)
    editable(folder)
    revision(folder, expected_updated_at)
    if folder.managed_project_id:
        error('La carpeta automática se administra desde el proyecto.', 'managed_folder', 409)
    if folder.children.exists() or folder.links.exists() or folder.cascade_archived_links.exists() or folder.cascade_archived_folders.exists():
        error('Solo se pueden eliminar carpetas vacías. Mueve antes sus enlaces y subcarpetas o restaura su archivo.', 'folder_not_empty', 409)
    folder.delete()


@transaction.atomic
def reorder_folders(ids, *, parent=None):
    lock_tree()
    if parent:
        active_target(folder_for(parent.pk, lock=True))
    siblings = list(SecureLinkFolder.objects.select_for_update().filter(parent=parent, managed_project__isnull=True))
    if len(ids) != len(set(ids)) or set(ids) != {row.pk for row in siblings}:
        error('Envía todas las carpetas hermanas una sola vez.', 'invalid_folder_order', 409)
    by_id = {row.pk: row for row in siblings}
    for position, pk in enumerate(ids):
        row = by_id[pk]
        editable(row)
        row.order, row.updated_at = position, timezone.now()
    SecureLinkFolder.objects.bulk_update(siblings, ['order', 'updated_at'])


@transaction.atomic
def archive_folder(folder, *, restore=False, actor=None, expected_updated_at=None):
    lock_tree()
    folder = folder_for(folder.pk, lock=True)
    editable(folder)
    revision(folder, expected_updated_at)
    if folder.managed_project_id:
        error('La carpeta automática se administra desde el proyecto.', 'managed_folder', 409)
    ids = subtree(folder, lock=True)
    if restore:
        folders = SecureLinkFolder.objects.filter(archived_via_folder=folder)
        links = SecureLink.objects.filter(archived_via_folder=folder)
    else:
        folders = SecureLinkFolder.objects.filter(pk__in=ids - {folder.pk}, is_archived=False)
        links = SecureLink.objects.filter(folder_id__in=ids, is_archived=False)
    folder_ids = list(folders.values_list('pk', flat=True))
    link_rows = list(links.select_for_update().values_list('pk', 'folder_id', 'retention_context_id'))
    touched = {folder.pk, *folder_ids}
    if SecureLinkFolder.objects.filter(pk__in=touched, retention_context__isnull=False).exists() or any(row[2] for row in link_rows):
        error(READ_ONLY_MESSAGE, 'retained_read_only', 409)
    now = timezone.now()
    if restore:
        # A previously archived link may have been moved. Reopen its CURRENT
        # containing chain too; never restore it underneath a hidden folder.
        by_id = {row.pk: row for row in SecureLinkFolder.objects.select_for_update()}
        targets = touched | {row[1] for row in link_rows if row[1] is not None}
        for target in list(targets):
            seen = set()
            while target is not None:
                if target in seen:
                    error('La jerarquía contiene un ciclo.', 'folder_cycle', 409)
                seen.add(target)
                row = by_id[target]
                editable(row)
                targets.add(target)
                target = row.parent_id
        values = dict(is_archived=False, archived_at=None, archived_via_folder=None, updated_at=now)
        folder_count = SecureLinkFolder.objects.filter(pk__in=targets, is_archived=True).count()
        SecureLinkFolder.objects.filter(pk__in=targets).update(**values)
    else:
        values = dict(is_archived=True, archived_at=now, archived_via_folder=folder, updated_at=now)
        folder_count = folders.update(**values)
        SecureLinkFolder.objects.filter(pk=folder.pk, is_archived=False).update(is_archived=True, archived_at=now, archived_via_folder=None, updated_at=now)
    link_ids = [row[0] for row in link_rows]
    SecureLink.objects.filter(pk__in=link_ids).update(**values)
    SecureLinkEvent.objects.bulk_create([
        SecureLinkEvent(link_id=pk, kind=SecureLinkEvent.Kind.UPDATED, actor=actor,
                        details={'fields': ['archive'], 'folder_id': folder.pk, 'archived': not restore})
        for pk in link_ids
    ])
    return {'folders': folder_count, 'links': len(link_ids)}


@transaction.atomic
def move_link(link, folder, *, actor=None, expected_updated_at=None):
    from .services import _locked_link, log_event
    link = _locked_link(link)
    editable(link)
    revision(link, expected_updated_at, label='enlace')
    if folder:
        folder = folder_for(folder.pk, lock=True)
        editable(folder)
        if not link.is_archived:
            active_target(folder)
    previous = link.folder_id
    link.folder = folder
    link.save(update_fields=['folder', 'updated_at'])
    log_event(link, SecureLinkEvent.Kind.UPDATED, actor=actor, fields=['folder'], previous_folder_id=previous, folder_id=link.folder_id)
    return link
