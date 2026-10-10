"""Behavioral coverage for automatic project roots in Documents."""
import pytest
from accounts.models import Project, UserProfile
from rest_framework.exceptions import PermissionDenied

from content.models import DocumentFolder, ProjectRetentionContext
from content.services import project_document_folder_service as roots
from content.services.project_document_folder_service import (
    ensure_project_folder,
)
from content.services.project_force_deletion import (
    force_delete_project,
    forced_deletion_preview,
)
from content.tests.mcp_parity import ownership_state

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_profile(django_user_model):
    user = django_user_model.objects.create_user(
        username='folder-owner@example.com',
        email='folder-owner@example.com',
        password='pass12345',
    )
    return UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_CLIENT,
    )


@pytest.fixture
def project(client_profile):
    return Project.objects.create(
        name='Kore Health',
        client=client_profile.user,
    )


def test_project_creation_builds_one_managed_root(project):
    root = DocumentFolder.objects.get(managed_project=project)

    assert root.name == 'Kore Health'
    assert root.parent_id is None
    assert root.project_id == project.id
    assert root.client_user_id == project.client_id
    assert root.folder_kind == 'project'


def test_prueba_project_creation_builds_a_managed_root(client_profile):
    project = Project.objects.create(
        name='PRUEBA',
        client=client_profile.user,
    )

    assert DocumentFolder.objects.filter(managed_project=project).exists()


def test_project_creation_builds_standard_children(project):
    """Falla si una raíz nueva deja de crear la estructura documental acordada."""
    root = project.document_root_folder

    assert list(root.children.values_list('name', flat=True)) == [
        'Cuentas de cobro',
        'Propuestas',
        'Entregables',
        'QA',
    ]
    assert not root.children.exclude(
        project=project,
        client_user=project.client,
    ).exists()
    children = {child.name: child for child in root.children.all()}
    assert children['Cuentas de cobro'].system_key == (
        f'generated:project:{project.id}:collection_account'
    )
    assert children['Propuestas'].system_key == (
        f'generated:project:{project.id}:commercial_proposal'
    )
    assert children['Entregables'].system_key is None
    assert children['QA'].system_key is None


def test_ensure_project_folder_is_idempotent(project):
    first = ensure_project_folder(project)
    second = ensure_project_folder(project)

    assert first.pk == second.pk
    assert DocumentFolder.objects.filter(managed_project=project).count() == 1
    assert first.children.count() == 4


def test_project_rename_synchronizes_root_without_changing_slug(project):
    root = project.document_root_folder
    original_slug = root.slug

    project.name = 'Kore Platform'
    project.save(update_fields=['name', 'updated_at'])

    root.refresh_from_db()
    assert root.name == 'Kore Platform'
    assert root.slug == original_slug


def test_updating_a_historical_project_never_recreates_a_missing_root(project):
    root = project.document_root_folder
    root.children.all().delete()
    root.delete()

    project.description = 'Edición ordinaria después de la migración de esquema'
    project.save(update_fields=['description', 'updated_at'])

    assert not DocumentFolder.objects.filter(managed_project=project).exists()


def test_project_client_change_synchronizes_its_folder_tree(
    project,
    django_user_model,
):
    user = django_user_model.objects.create_user(
        username='new-owner@example.com',
        email='new-owner@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)

    project.client = user
    project.save(update_fields=['client', 'updated_at'])

    root = DocumentFolder.objects.get(managed_project=project)
    assert root.client_user_id == user.id
    assert not root.children.exclude(client_user=user).exists()


def test_root_synchronization_failure_rolls_back_project_save(project, make_client_profile, monkeypatch):
    new_owner = make_client_profile()
    before_project = Project.objects.filter(pk=project.pk).values('name', 'client_id', 'updated_at').get()
    before_tree = ownership_state()
    update_root = roots._update_root

    def fail_after_root_update(root, changed_project, *, created):
        update_root(root, changed_project, created=created)
        raise RuntimeError('Injected root synchronization failure')

    monkeypatch.setattr(roots, '_update_root', fail_after_root_update)
    project.name = 'Renamed project'
    project.client = new_owner.user

    with pytest.raises(RuntimeError, match='Injected root synchronization failure'):
        project.save(update_fields=['name', 'client', 'updated_at'])

    assert Project.objects.filter(pk=project.pk).values('name', 'client_id', 'updated_at').get() == before_project
    assert ownership_state() == before_tree


def test_empty_force_selection_retains_project_root_as_read_only(project, superuser):
    """Fails if an unselected project folder becomes an editable manual folder after deletion."""
    root = project.document_root_folder
    project_id = project.pk
    client_id = project.client_id
    preview = forced_deletion_preview(project, actor=superuser, delete_keys=[])

    force_delete_project(
        project_id,
        actor=superuser,
        confirmation='DELETE',
        impact_token=preview['impact_token'],
        delete_keys=[],
    )

    root.refresh_from_db()
    context = ProjectRetentionContext.objects.get(pk=root.retention_context_id)
    assert not Project.objects.filter(pk=project_id).exists()
    assert root.project_id is None
    assert root.managed_project_id is None
    assert root.client_user_id == client_id
    assert context.client_id == client_id
    assert str(root.pk) in context.retained_records['content.documentfolder']
    with pytest.raises(PermissionDenied, match='sólo permiten consulta'):
        root.save()
