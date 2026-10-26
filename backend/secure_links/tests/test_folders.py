"""Behavioral filing contract: organization never grants access or consumes links."""
import pytest
from accounts.models import Project
from secure_links import folder_services as filing, services
from secure_links.models import SecureLinkFolder
from .conftest import token_from

pytestmark = pytest.mark.django_db


def test_new_project_has_automatic_folder(project):
    root = SecureLinkFolder.objects.get(managed_project=project)
    assert (root.project, root.client, root.name, root.parent_id) == (project, project.client.profile, project.name, None)


def test_project_rename_updates_root(project):
    project.name = 'Nombre actualizado'
    project.save(update_fields=['name'])
    assert SecureLinkFolder.objects.get(managed_project=project).name == project.name


def test_project_link_is_filed_automatically(make_link, project):
    link, _ = make_link(project=project)
    assert link.folder == SecureLinkFolder.objects.get(managed_project=project)


def test_explicit_root_overrides_project_filing(make_link, project):
    link, _ = make_link(project=project, folder=None)
    assert link.folder_id is None


def test_folder_context_is_inherited_at_creation(make_link, project):
    folder = filing.save_folder(data={'name': 'Accesos', 'parent': project.secure_link_root_folder})
    link, _ = make_link(folder=folder)
    assert (link.project, link.client) == (project, project.client.profile)


def test_move_preserves_project(make_link, project):
    other = Project.objects.create(client=project.client, name='Otro proyecto')
    link, _ = make_link(project=project)
    moved = filing.move_link(link, other.secure_link_root_folder)
    assert (moved.project_id, moved.client_id, moved.folder_id) == (project.pk, project.client.profile.pk, other.secure_link_root_folder.pk)


def test_project_edit_preserves_location(make_link, project, staff_user):
    link, _ = make_link()
    services.update_link(link, actor=staff_user, project=project)
    link.refresh_from_db()
    assert link.project_id == project.pk
    assert link.folder_id is None


def test_archive_keeps_bearer_link_working(make_link):
    folder = filing.save_folder(data={'name': 'Activos'})
    link, url = make_link(folder=folder)
    filing.archive_folder(folder)
    link.refresh_from_db()
    assert link.is_archived is True
    assert services.public_status(token_from(url))['can_reveal'] is True


def test_restore_preserves_independent_archive(make_link):
    parent = filing.save_folder(data={'name': 'Padre'})
    child = filing.save_folder(data={'name': 'Hija', 'parent': parent})
    link, _ = make_link(folder=child)
    filing.archive_folder(child)
    filing.archive_folder(parent)
    filing.archive_folder(parent, restore=True)
    child.refresh_from_db()
    link.refresh_from_db()
    assert child.is_archived is True
    assert link.is_archived is True


def test_cycle_is_rejected():
    parent = filing.save_folder(data={'name': 'Padre'})
    child = filing.save_folder(data={'name': 'Hija', 'parent': parent})
    with pytest.raises(services.SecureLinkError, match='subcarpetas'):
        filing.save_folder(folder=parent, data={'parent': child})
    parent.refresh_from_db()
    assert parent.parent_id is None


def test_managed_root_cannot_be_archived(project):
    with pytest.raises(services.SecureLinkError, match='automática'):
        filing.archive_folder(project.secure_link_root_folder)


def test_archived_content_blocks_folder_deletion(make_link):
    folder = filing.save_folder(data={'name': 'Archivo'})
    make_link(folder=folder)
    filing.archive_folder(folder)
    with pytest.raises(services.SecureLinkError, match='vacías'):
        filing.delete_folder(folder)
    assert SecureLinkFolder.objects.filter(pk=folder.pk).exists()


def test_active_link_cannot_move_into_archive(make_link):
    folder = filing.save_folder(data={'name': 'Archivo'})
    filing.archive_folder(folder)
    link, _ = make_link()
    with pytest.raises(services.SecureLinkError, match='Restaura'):
        filing.move_link(link, folder)


def test_scoped_counts_include_descendants(staff_client, make_link):
    parent = filing.save_folder(data={'name': 'Padre'})
    child = filing.save_folder(data={'name': 'Hija', 'parent': parent})
    make_link(folder=child)
    make_link()
    response = staff_client.get('/api/secure-links/', {'folder': parent.pk})
    assert response.status_code == 200
    assert response.data['count'] == response.data['lifecycle_counts']['all'] == 1


def test_received_badge_is_scoped(staff_client, make_link):
    from secure_links.models import SecureLink
    parent = filing.save_folder(data={'name': 'Padre'})
    make_link(origin=SecureLink.Origin.PUBLIC, folder=parent)
    make_link(origin=SecureLink.Origin.PUBLIC)
    response = staff_client.get('/api/secure-links/', {'folder': parent.pk, 'received': 'true'})
    assert response.data['unopened_received'] == 1


def test_folder_api_rejects_regular_user(regular_client):
    response = regular_client.post('/api/secure-links/folders/', {'name': 'Privada'}, format='json')
    assert response.status_code == 403
    assert not SecureLinkFolder.objects.filter(name='Privada').exists()


def test_stale_folder_change_is_rejected(staff_client):
    folder = filing.save_folder(data={'name': 'Original'})
    old_revision = folder.updated_at.isoformat()
    filing.save_folder(folder=folder, data={'name': 'Más reciente'})
    response = staff_client.patch(f'/api/secure-links/folders/{folder.pk}/', {'name': 'Vieja', 'expected_updated_at': old_revision}, format='json')
    assert response.status_code == 409
    folder.refresh_from_db()
    assert folder.name == 'Más reciente'


def test_folder_reorder_requires_complete_siblings():
    first = filing.save_folder(data={'name': 'Primera'})
    second = filing.save_folder(data={'name': 'Segunda'})
    filing.reorder_folders([second.pk, first.pk])
    assert list(SecureLinkFolder.objects.values_list('pk', flat=True)) == [second.pk, first.pk]
