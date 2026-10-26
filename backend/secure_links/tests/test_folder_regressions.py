"""Regression coverage for filing migrations and concurrent folder actions."""
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

from secure_links import folder_services as filing, services
from secure_links.models import SecureLinkFolder


pytestmark = pytest.mark.django_db


def test_classification_migration_files_only_unassigned_project_links(make_link, project):
    """Falla si el backfill deja enlaces de proyecto sin raíz o duplica su carpeta automática."""
    project_link, _ = make_link(project=project)
    unassigned_link, _ = make_link()
    root = project.secure_link_root_folder
    SecureLinkFolder.objects.filter(pk=root.pk).update(name='Raíz del proyecto')
    project_link.folder = None
    project_link.save(update_fields=['folder', 'updated_at'])

    migration = import_module('secure_links.migrations.0007_classify_link_folders')
    migration.classify(django_apps, SimpleNamespace(connection=connection))

    project_link.refresh_from_db()
    unassigned_link.refresh_from_db()
    assert project_link.folder_id == root.pk
    assert unassigned_link.folder_id is None
    assert SecureLinkFolder.objects.filter(managed_project=project).count() == 1


def test_move_rejects_stale_link_revision_without_changing_folder(staff_client, staff_user, make_link):
    """Falla si un traslado tardío puede sobrescribir la ubicación elegida más recientemente."""
    previous_folder = filing.save_folder(data={'name': 'Operaciones'})
    destination = filing.save_folder(data={'name': 'Producción'})
    link, _ = make_link(folder=previous_folder)
    old_revision = link.updated_at.isoformat()
    services.update_link(link, actor=staff_user, title='Acceso actualizado')

    response = staff_client.post(
        f'/api/secure-links/{link.pk}/move/',
        {'folder': destination.pk, 'expected_updated_at': old_revision},
        format='json',
    )

    link.refresh_from_db()
    assert response.status_code == 409
    assert link.folder_id == previous_folder.pk


def test_restore_reopens_current_archived_destination_chain(make_link):
    """Falla si restaurar un enlace movido lo deja dentro de una carpeta aún archivada."""
    source = filing.save_folder(data={'name': 'Origen'})
    destination_parent = filing.save_folder(data={'name': 'Destino'})
    destination = filing.save_folder(data={'name': 'Subcarpeta destino', 'parent': destination_parent})
    link, _ = make_link(folder=source)
    filing.archive_folder(source)
    filing.archive_folder(destination_parent)
    filing.move_link(link, destination)

    filing.archive_folder(source, restore=True)

    link.refresh_from_db()
    destination.refresh_from_db()
    destination_parent.refresh_from_db()
    assert link.is_archived is False
    assert destination.is_archived is False
    assert destination_parent.is_archived is False
