"""Behavioral coverage for development secure-link filing samples."""
from io import StringIO

import pytest
from accounts.models import Project
from django.core.management import call_command

from secure_links import folder_services as filing
from secure_links.models import SecureLink, SecureLinkFolder


pytestmark = pytest.mark.django_db


def run_command(name, *args):
    call_command(name, *args, stdout=StringIO(), verbosity=0)


def test_fake_secure_link_seed_creates_hierarchy_and_archives_without_revoking():
    """Falla si la muestra deja de ofrecer carpetas anidadas, raíces de proyecto o archivo no revocatorio."""
    run_command('create_fake_secure_links')

    manual = SecureLinkFolder.objects.get(name='[Demo] Enlaces propios', parent__isnull=True)
    nested = SecureLinkFolder.objects.get(name='[Demo] Proveedores', parent=manual)
    archive = SecureLinkFolder.objects.get(name='[Demo] Archivo de enlaces', parent__isnull=True)
    archived_child = SecureLinkFolder.objects.get(name='[Demo] Historial', parent=archive)
    archived_link = SecureLink.objects.get(folder=archived_child, revoked_at__isnull=True)
    project_total = Project.objects.filter(name__startswith='Secure links demo ').count()

    assert (manual.parent_id, nested.parent_id) == (None, manual.pk)
    assert SecureLinkFolder.objects.filter(
        name='[Demo] Accesos', parent__managed_project__isnull=False,
    ).count() == project_total
    assert SecureLinkFolder.objects.filter(
        name='[Demo] Entregas', parent__managed_project__isnull=False,
    ).count() == project_total
    assert SecureLink.objects.filter(folder__isnull=True, project__isnull=True).exists()
    assert (archive.is_archived, archived_child.is_archived, archived_link.is_archived,
            archived_link.status) == (
        True, True, True, 'active',
    )


def test_fake_reset_removes_project_folder_tree_and_unfiles_independent_link():
    """Falla si el reset deja el árbol protegido o elimina un enlace sin proyecto movido dentro de él."""
    run_command('create_fake_secure_links')
    project = Project.objects.get(name='Secure links demo 1')
    root = project.secure_link_root_folder
    destination = SecureLinkFolder.objects.get(name='[Demo] Accesos', parent=root)
    standalone = SecureLink.objects.filter(folder__isnull=True, project__isnull=True).order_by('pk').first()
    filing.move_link(standalone, destination)

    run_command('delete_fake_data', '--confirm')

    standalone.refresh_from_db()
    assert not Project.objects.filter(pk=project.pk).exists()
    assert not SecureLinkFolder.objects.filter(pk__in=[root.pk, destination.pk]).exists()
    assert (standalone.project_id, standalone.folder_id) == (None, None)
