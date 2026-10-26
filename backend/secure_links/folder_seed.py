"""Representative filing fixtures for explicitly permitted development resets."""
from accounts.models import Project
from content.services.folder_tree import descendant_ids

from . import folder_services as filing
from .models import SecureLink, SecureLinkFolder


def create_folder_samples():
    def folder(name, parent=None):
        existing = SecureLinkFolder.objects.filter(name=name, parent=parent).first()
        return existing or filing.save_folder(data={'name': name, 'parent': parent})

    manual = folder('[Demo] Enlaces propios')
    nested = folder('[Demo] Proveedores', manual)
    archive = folder('[Demo] Archivo de enlaces')
    archived_child = folder('[Demo] Historial', archive)
    # A repeat run may add examples to the archive before archiving them again.
    if archive.is_archived:
        filing.archive_folder(archive, restore=True)
    contexts = [{}, {'folder': manual}, {'folder': nested}, {'folder': archived_child}]
    for project in Project.objects.filter(name__startswith='Secure links demo ').order_by('pk'):
        root = filing.ensure_project_root(project)
        child = folder('[Demo] Accesos', root)
        folder('[Demo] Entregas', root)
        contexts.extend([{'project': project}, {'folder': child}])
    return contexts, archive


def clear_project_folder_samples(project_ids, retention_context_ids):
    """Release only the folder graph owned by the confirmed project reset.

    Standalone links can have been moved into these folders. Their association
    still makes them independent, so keep them and return their location to root.
    """
    from django.db.models import Q

    owned = set(SecureLinkFolder.objects.filter(
        Q(project_id__in=project_ids) | Q(managed_project_id__in=project_ids)
        | Q(retention_context_id__in=retention_context_ids),
    ).values_list('pk', flat=True))
    rows = list(SecureLinkFolder.objects.values_list('pk', 'parent_id'))
    ids = owned.copy()
    for pk in owned:
        ids.update(descendant_ids(rows, pk))
    SecureLink.objects.filter(folder_id__in=ids).update(folder=None)
    while SecureLinkFolder.objects.filter(pk__in=ids, children__isnull=True).exists():
        SecureLinkFolder.objects.filter(pk__in=ids, children__isnull=True).delete()
