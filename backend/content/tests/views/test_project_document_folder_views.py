"""API contract for managed project roots."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Project, UserProfile
from content.models import DocumentFolder, DocumentState, DocumentStateGroup


pytestmark = pytest.mark.django_db


@pytest.fixture
def project():
    user = get_user_model().objects.create_user(
        username='managed-folder@example.com',
        email='managed-folder@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    return Project.objects.create(name='Vastago', client=user)


def test_list_marks_a_managed_project_root(admin_client, project):
    response = admin_client.get(reverse('list-document-folders'))

    root = next(item for item in response.data if item['managed_project'] == project.id)
    assert root['folder_kind'] == 'project'
    assert root['managed_project_state']['system_key'] == 'development'
    assert root['is_project_visible'] is True


def test_readiness_reports_projects_whose_roots_need_reconciliation(
    admin_client, project,
):
    root = project.document_root_folder
    root.children.all().delete()
    root.delete()

    response = admin_client.get(reverse('project-folder-readiness'))

    assert response.status_code == 200
    assert response.data == {
        'status': 'reconciliation_required',
        'project_count': 1,
        'enabled_project_count': 1,
        'disabled_project_count': 0,
        'active_project_count': 1,
        'archived_project_count': 0,
        'managed_root_count': 0,
        'active_managed_root_count': 0,
        'missing_root_count': 1,
        'missing_active_root_count': 1,
    }


def test_readiness_does_not_use_the_obsolete_state_visibility_flag(
    admin_client, project,
):
    state = project.current_state
    state.name = 'Nombre cambiado después de PA-94'
    state.show_in_document_manager = False
    state.save(update_fields=['name', 'show_in_document_manager', 'updated_at'])

    response = admin_client.get(reverse('project-folder-readiness'))

    assert response.status_code == 200
    assert response.data['status'] == 'ready'
    assert response.data['project_count'] == 1
    assert response.data['active_project_count'] == 1
    assert response.data['managed_root_count'] == 1


def test_readiness_counts_suspended_projects_without_excluding_them(
    admin_client, project,
):
    """Falla si un proyecto suspendido deja de clasificarse como archivado."""
    suspended = DocumentState.objects.get(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        system_key=Project.STATUS_SUSPENDED,
    )
    project.current_state = suspended
    project.status = Project.STATUS_SUSPENDED
    project.save(update_fields=['current_state', 'status', 'updated_at'])

    response = admin_client.get(reverse('project-folder-readiness'))

    assert response.status_code == 200
    assert response.data['status'] == 'ready'
    assert response.data['active_project_count'] == 0
    assert response.data['archived_project_count'] == 1


def test_readiness_reports_suspended_projects_as_eligible(
    admin_client, project,
):
    """Falla si una suspensión excluye el proyecto de la conciliación."""
    suspended = DocumentState.objects.get(
        catalog=DocumentStateGroup.Catalog.PROJECTS,
        system_key=Project.STATUS_SUSPENDED,
    )
    project.current_state = suspended
    project.status = Project.STATUS_SUSPENDED
    project.save(update_fields=['current_state', 'status', 'updated_at'])

    response = admin_client.get(reverse('project-folder-readiness'))

    assert response.status_code == 200
    assert response.data['project_count'] == 1
    assert response.data['enabled_project_count'] == 1
    assert response.data['disabled_project_count'] == 0
    assert response.data['missing_root_count'] == 0


def test_readiness_distinguishes_a_real_empty_project_catalog(
    admin_client,
):
    response = admin_client.get(reverse('project-folder-readiness'))

    assert response.status_code == 200
    assert response.data['status'] == 'no_projects'
    assert response.data['project_count'] == 0
    assert response.data['missing_root_count'] == 0


def test_readiness_requires_an_admin(api_client):
    response = api_client.get(reverse('project-folder-readiness'))

    assert response.status_code in {401, 403}


def test_child_created_under_project_inherits_association(admin_client, project):
    root = project.document_root_folder

    response = admin_client.post(
        reverse('create-document-folder'),
        {'name': 'Actas', 'parent': root.id},
        format='json',
    )

    assert response.status_code == 201, response.data
    child = DocumentFolder.objects.get(pk=response.data['id'])
    assert child.project_id == project.id
    assert child.client_user_id == project.client_id
    assert child.managed_project_id is None


def test_project_root_cannot_be_renamed_from_documents(admin_client, project):
    root = project.document_root_folder

    response = admin_client.patch(
        reverse('update-document-folder', kwargs={'folder_id': root.id}),
        {'name': 'Otro nombre'},
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'managed_project_folder'


def test_project_root_cannot_be_archived(admin_client, project):
    root = project.document_root_folder

    response = admin_client.patch(
        reverse('archive-document-folder', kwargs={'folder_id': root.id}),
        {},
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'managed_project_folder'


def test_project_root_cannot_be_deleted(admin_client, project):
    root = project.document_root_folder

    response = admin_client.delete(
        reverse('delete-document-folder', kwargs={'folder_id': root.id}),
    )

    assert response.status_code == 409
    assert DocumentFolder.objects.filter(pk=root.id).exists()


def test_reorder_ignores_a_managed_project_root(admin_client, project):
    """Falla si un payload legado altera el orden de una raíz automática."""
    managed_root = project.document_root_folder
    managed_root.order = 7
    managed_root.save(update_fields=['order'])
    manual_root = DocumentFolder.objects.create(name='Carpeta personal', order=9)

    response = admin_client.post(
        reverse('reorder-document-folders'),
        {'ids': [managed_root.id, manual_root.id]},
        format='json',
    )

    assert response.status_code == 200
    manual_root.refresh_from_db()
    managed_root.refresh_from_db()
    assert manual_root.order == 1
    assert managed_root.order == 7
