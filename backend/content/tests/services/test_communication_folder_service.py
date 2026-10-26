"""Business rules for filing complete communication threads."""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model

from content.models import CommunicationFolder, CommunicationThread
from content.services import communication_folder_service, communication_service, project_service
from content.services.communication_service import CommunicationError


pytestmark = pytest.mark.django_db
User = get_user_model()


def make_client(email):
    user = User.objects.create_user(
        username=email, email=email, password='testpass123',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


def test_save_folder_builds_a_subfolder_in_its_client_project_context():
    """Falla si una subcarpeta válida deja de conservar el contexto de su padre."""
    client = make_client('folder-service@example.com')
    project = Project.objects.create(name='Archivo', client=client.user)
    root = communication_folder_service.save_folder(data={
        'name': 'Contratos', 'client': client, 'project': project,
    })

    child = communication_folder_service.save_folder(data={
        'name': 'Firmados', 'client': client, 'project': project, 'parent': root,
    })

    assert (child.name, child.parent_id, child.client_id, child.project_id) == (
        'Firmados', root.id, client.id, project.id,
    )


def test_save_folder_rejects_a_parent_from_another_context():
    """Falla si una carpeta puede cruzar árboles de clientes o proyectos."""
    first = make_client('folder-first@example.com')
    second = make_client('folder-second@example.com')
    foreign_parent = CommunicationFolder.objects.create(name='Ajena', client=second)

    with pytest.raises(CommunicationError) as error:
        communication_folder_service.save_folder(data={
            'name': 'No permitida', 'client': first, 'parent': foreign_parent,
        })

    assert error.value.args[0]['parent'] == ['La carpeta debe pertenecer al mismo contexto.']
    assert CommunicationFolder.objects.filter(client=first).count() == 0


def test_save_folder_rejects_reparenting_a_folder_below_its_descendant():
    """Falla si mover una carpeta debajo de su hija permite crear un ciclo."""
    client = make_client('folder-cycle@example.com')
    root = CommunicationFolder.objects.create(name='Raíz', client=client)
    child = CommunicationFolder.objects.create(name='Hija', client=client, parent=root)
    grandchild = CommunicationFolder.objects.create(name='Nieta', client=client, parent=child)

    with pytest.raises(CommunicationError) as error:
        communication_folder_service.save_folder(folder=root, data={'parent': grandchild})

    assert error.value.args[0]['parent'] == ['Una carpeta no puede contenerse a sí misma.']
    root.refresh_from_db()
    assert root.parent_id is None


def test_delete_folder_rejects_a_child_and_preserves_the_tree():
    """Falla si eliminar una carpeta con subcarpetas borra la jerarquía."""
    client = make_client('folder-child@example.com')
    root = CommunicationFolder.objects.create(name='Raíz', client=client)
    child = CommunicationFolder.objects.create(name='Hija', client=client, parent=root)

    with pytest.raises(CommunicationError):
        communication_folder_service.delete_folder(root)

    assert CommunicationFolder.objects.filter(pk__in=[root.id, child.id]).count() == 2


def test_delete_folder_rejects_an_archived_thread_and_preserves_it(admin_user):
    """Falla si una carpeta borra un hilo archivado que aún la referencia."""
    client = make_client('folder-archived@example.com')
    folder = CommunicationFolder.objects.create(name='Histórico', client=client)
    thread = communication_service.create_thread(
        actor=admin_user, client=client, folder=folder, title='Conversación archivada',
    )
    communication_service.archive_thread(thread, actor=admin_user)

    with pytest.raises(CommunicationError):
        communication_folder_service.delete_folder(folder)

    thread.refresh_from_db()
    assert (CommunicationFolder.objects.filter(pk=folder.id).exists(), thread.folder_id) == (
        True, folder.id,
    )


def test_project_client_change_detaches_historical_threads_and_folders(superuser):
    """Falla si reasignar proyecto conserva correspondencia bajo el nuevo cliente."""
    old_client = make_client('folder-old-owner@example.com')
    new_client = make_client('folder-new-owner@example.com')
    project = Project.objects.create(name='Cambio de cliente', client=old_client.user)
    folder = CommunicationFolder.objects.create(
        name='Histórico del proyecto', client=old_client, project=project,
    )
    thread = communication_service.create_thread(
        actor=superuser,
        client=old_client,
        project=project,
        folder=folder,
        title='Conversación histórica',
    )

    project_service.change_client_apply(
        project, new_client, project_service.MODE_MOVE, superuser,
    )

    thread.refresh_from_db()
    folder.refresh_from_db()
    assert (thread.client_id, thread.project_id, thread.folder_id) == (
        old_client.id, None, None,
    )
    assert (folder.client_id, folder.project_id) == (old_client.id, None)
