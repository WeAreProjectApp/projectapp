"""HTTP contract coverage for staff secure-link folder administration."""
import pytest

from secure_links import folder_services as filing, services
from secure_links.models import SecureLink, SecureLinkFolder
from .conftest import token_from


pytestmark = pytest.mark.django_db

FOLDERS_URL = '/api/secure-links/folders/'


def detail_url(folder):
    return f'{FOLDERS_URL}{folder.pk}/'


def test_folder_index_exposes_navigation_inventory(staff_client, make_link):
    """Falla si el índice HTTP deja de exponer carpetas, conteos o navegación del panel."""
    folder = filing.save_folder(data={'name': 'Accesos'})
    make_link(folder=folder)

    response = staff_client.get(FOLDERS_URL)

    entry = next(row for row in response.data['folders'] if row['id'] == folder.pk)
    assert response.status_code == 200
    assert (entry['name'], entry['link_count'], entry['archived_link_count']) == ('Accesos', 1, 0)
    assert response.data['navigation']['totals']['active']['folders'] == 1


def test_create_folder_inherits_project_context_from_parent(staff_client, project):
    """Falla si crear por HTTP una subcarpeta de proyecto pierde su cliente o proyecto."""
    root = project.secure_link_root_folder

    response = staff_client.post(FOLDERS_URL, {'name': 'Credenciales', 'parent': root.pk}, format='json')

    folder = SecureLinkFolder.objects.get(pk=response.data['id'])
    assert response.status_code == 201
    assert (folder.parent_id, folder.client_id, folder.project_id) == (
        root.pk, project.client.profile.pk, project.pk,
    )


def test_create_folder_requires_name(staff_client):
    """Falla si el endpoint crea una carpeta sin nombre."""
    response = staff_client.post(FOLDERS_URL, {}, format='json')

    assert response.status_code == 400
    assert response.data['name'] == ['El nombre es obligatorio.']
    assert SecureLinkFolder.objects.count() == 0


def test_create_folder_rejects_unknown_parent(staff_client):
    """Falla si una subcarpeta puede apuntar a un padre inexistente."""
    response = staff_client.post(FOLDERS_URL, {'name': 'Huérfana', 'parent': 99999}, format='json')

    assert response.status_code == 400
    assert response.data['parent']
    assert not SecureLinkFolder.objects.filter(name='Huérfana').exists()


def test_folder_detail_serializes_manual_folder(staff_client):
    """Falla si consultar una carpeta no devuelve su identidad de navegación."""
    folder = filing.save_folder(data={'name': 'Operaciones'})

    response = staff_client.get(detail_url(folder))

    assert response.status_code == 200
    assert (response.data['id'], response.data['name'], response.data['folder_kind']) == (
        folder.pk, 'Operaciones', 'manual',
    )


def test_folder_detail_returns_not_found_for_missing_folder(staff_client):
    """Falla si una ruta de carpeta inexistente deja de responder como recurso ausente."""
    response = staff_client.get(f'{FOLDERS_URL}99999/')

    assert (response.status_code, response.data['code']) == (404, 'folder_not_found')


def test_patch_folder_renames_manual_folder(staff_client):
    """Falla si renombrar por HTTP no persiste el nuevo nombre de una carpeta manual."""
    folder = filing.save_folder(data={'name': 'Antes'})

    response = staff_client.patch(detail_url(folder), {'name': 'Después'}, format='json')

    folder.refresh_from_db()
    assert (response.status_code, response.data['name'], folder.name) == (200, 'Después', 'Después')


def test_patch_folder_reparents_existing_folder(staff_client):
    """Falla si mover una carpeta con PATCH no cambia su padre persistido."""
    parent = filing.save_folder(data={'name': 'Padre'})
    child = filing.save_folder(data={'name': 'Hija'})

    response = staff_client.patch(detail_url(child), {'parent': parent.pk}, format='json')

    child.refresh_from_db()
    assert (response.status_code, response.data['parent'], child.parent_id) == (200, parent.pk, parent.pk)


def test_patch_folder_rejects_empty_name(staff_client):
    """Falla si editar por HTTP permite borrar el nombre de una carpeta existente."""
    folder = filing.save_folder(data={'name': 'Inicial'})

    response = staff_client.patch(
        detail_url(folder),
        {'name': ''},
        format='json',
    )

    folder.refresh_from_db()
    assert response.status_code == 400
    assert response.data['name']
    assert folder.name == 'Inicial'


def test_delete_empty_folder_removes_it(staff_client):
    """Falla si borrar por HTTP una carpeta vacía deja el registro persistido."""
    folder = filing.save_folder(data={'name': 'Vacía'})

    response = staff_client.delete(detail_url(folder), format='json')

    assert response.status_code == 204
    assert not SecureLinkFolder.objects.filter(pk=folder.pk).exists()


def test_delete_nonempty_folder_preserves_content(staff_client, make_link):
    """Falla si borrar una carpeta con enlaces elimina o separa su contenido."""
    folder = filing.save_folder(data={'name': 'Con enlace'})
    link, _ = make_link(folder=folder)

    response = staff_client.delete(detail_url(folder), format='json')

    link.refresh_from_db()
    assert (response.status_code, response.data['code'], link.folder_id) == (409, 'folder_not_empty', folder.pk)


def test_archive_folder_archives_descendants_without_revoking_bearer_link(staff_client, make_link):
    """Falla si archivar por HTTP no cubre descendientes o revoca el enlace disponible."""
    parent = filing.save_folder(data={'name': 'Archivo'})
    child = filing.save_folder(data={'name': 'Historial', 'parent': parent})
    link, url = make_link(folder=child)

    response = staff_client.post(f'{detail_url(parent)}archive/', {}, format='json')

    child.refresh_from_db()
    link.refresh_from_db()
    assert (response.status_code, response.data, child.is_archived, link.is_archived) == (
        200, {'folders': 1, 'links': 1}, True, True,
    )
    assert services.public_status(token_from(url))['can_reveal'] is True


def test_restore_folder_restores_archived_descendants(staff_client, make_link):
    """Falla si restaurar por HTTP deja archivados los descendientes que archivó la carpeta."""
    parent = filing.save_folder(data={'name': 'Archivo'})
    child = filing.save_folder(data={'name': 'Historial', 'parent': parent})
    link, _ = make_link(folder=child)
    filing.archive_folder(parent)

    response = staff_client.post(f'{detail_url(parent)}restore/', {}, format='json')

    child.refresh_from_db()
    link.refresh_from_db()
    assert (response.status_code, response.data, child.is_archived, link.is_archived) == (
        200, {'folders': 2, 'links': 1}, False, False,
    )


def test_archive_folder_rejects_invalid_revision(staff_client):
    """Falla si archivar acepta una revisión que no contiene fecha y hora válida."""
    folder = filing.save_folder(data={'name': 'Pendiente'})

    response = staff_client.post(
        f'{detail_url(folder)}archive/',
        {'expected_updated_at': 'not-a-timestamp'},
        format='json',
    )

    folder.refresh_from_db()
    assert response.status_code == 400
    assert 'expected_updated_at' in response.data
    assert folder.is_archived is False


def test_reorder_folders_persists_requested_sibling_order(staff_client):
    """Falla si ordenar por HTTP confirma éxito sin cambiar el orden persistido de hermanas."""
    parent = filing.save_folder(data={'name': 'Raíz manual'})
    first = filing.save_folder(data={'name': 'Primera', 'parent': parent})
    second = filing.save_folder(data={'name': 'Segunda', 'parent': parent})

    response = staff_client.post(
        f'{FOLDERS_URL}reorder/',
        {'ids': [second.pk, first.pk], 'parent': parent.pk},
        format='json',
    )

    assert response.data == {'success': True}
    assert response.status_code == 200
    assert list(SecureLinkFolder.objects.filter(parent=parent).values_list('pk', flat=True)) == [second.pk, first.pk]


def test_reorder_folders_rejects_incomplete_siblings(staff_client):
    """Falla si ordenar por HTTP acepta una lista que omite una carpeta hermana."""
    parent = filing.save_folder(data={'name': 'Raíz manual'})
    first = filing.save_folder(data={'name': 'Primera', 'parent': parent})
    second = filing.save_folder(data={'name': 'Segunda', 'parent': parent})

    response = staff_client.post(
        f'{FOLDERS_URL}reorder/',
        {'ids': [second.pk], 'parent': parent.pk},
        format='json',
    )

    assert (response.status_code, response.data['code']) == (409, 'invalid_folder_order')
    assert list(SecureLinkFolder.objects.filter(parent=parent).values_list('pk', flat=True)) == [first.pk, second.pk]


def test_move_link_changes_only_its_folder(staff_client, make_link, project):
    """Falla si mover un enlace por HTTP cambia su cliente o proyecto junto con la ubicación."""
    destination = filing.save_folder(data={'name': 'Propia'})
    link, _ = make_link(project=project)

    response = staff_client.post(
        f'/api/secure-links/{link.pk}/move/',
        {'folder': destination.pk},
        format='json',
    )

    link.refresh_from_db()
    assert (response.status_code, response.data['folder'], response.data['client'], response.data['project']) == (
        200, destination.pk, project.client.profile.pk, project.pk,
    )
    assert (link.folder_id, link.client_id, link.project_id) == (
        destination.pk, project.client.profile.pk, project.pk,
    )


def test_move_link_requires_folder_value(staff_client, make_link):
    """Falla si el endpoint mueve un enlace cuando falta el destino explícito."""
    link, _ = make_link()

    response = staff_client.post(f'/api/secure-links/{link.pk}/move/', {}, format='json')

    link.refresh_from_db()
    assert response.status_code == 400
    assert response.data['folder'] == ['This field is required.']
    assert link.folder_id is None
