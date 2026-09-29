"""Provenance on folders created by automatic document workflows."""
from datetime import date

import pytest
from accounts.models import Project, UserProfile

from content.management.commands.create_fake_documents import _ensure_folders
from content.models import DocumentFolder
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.generated_document_filing_service import (
    ensure_generated_folder_path,
)
from content.services.project_document_folder_service import ensure_project_folder

pytestmark = pytest.mark.django_db


@pytest.fixture
def project_with_client(django_user_model):
    user = django_user_model.objects.create_user(
        username='provenance-client@example.com',
        email='provenance-client@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    return Project.objects.create(name='Provenance project', client=user)


def test_project_tree_keeps_system_provenance_when_reused(project_with_client):
    """Falla si sincronizar un proyecto reemplaza el origen de sus carpetas automáticas."""
    root = ensure_project_folder(project_with_client)
    original = {
        folder.pk: (folder.creation_source, folder.creation_operation, folder.created_by_id)
        for folder in DocumentFolder.objects.filter(project=project_with_client)
    }

    reused = ensure_project_folder(project_with_client)

    assert reused.pk == root.pk
    assert original[root.pk] == ('system', 'ensure_project_folder', None)
    assert {
        folder.pk: (folder.creation_source, folder.creation_operation, folder.created_by_id)
        for folder in DocumentFolder.objects.filter(project=project_with_client)
    } == original
    assert {
        folder.creation_operation for folder in root.children.all()
    } == {'ensure_project_folder.template'}


def test_generated_path_keeps_system_provenance_when_reused(project_with_client):
    """Falla si una jerarquía generada pierde su operación original al volver a archivarse."""
    first = ensure_generated_folder_path(
        COLLECTION_ACCOUNT,
        business_date=date(2026, 9, 28),
        project=project_with_client,
    )
    original = {
        folder.pk: (folder.creation_source, folder.creation_operation, folder.created_by_id)
        for folder in DocumentFolder.objects.filter(
            creation_operation='ensure_generated_folder_path',
        )
    }

    reused = ensure_generated_folder_path(
        COLLECTION_ACCOUNT,
        business_date=date(2026, 9, 28),
        project=project_with_client,
    )

    assert reused.pk == first.pk
    assert len(original) == 2
    assert set(original.values()) == {('system', 'ensure_generated_folder_path', None)}
    assert {
        folder.pk: (folder.creation_source, folder.creation_operation, folder.created_by_id)
        for folder in DocumentFolder.objects.filter(
            creation_operation='ensure_generated_folder_path',
        )
    } == original


def test_fake_folder_seed_keeps_system_provenance_when_reused():
    """Falla si la siembra de documentos crea carpetas sin procedencia del sistema."""
    _ensure_folders()
    original = {
        folder.pk: (folder.creation_source, folder.creation_operation, folder.created_by_id)
        for folder in DocumentFolder.objects.all()
    }

    _ensure_folders()

    assert len(original) == 8
    assert set(original.values()) == {('system', 'create_fake_documents', None)}
    assert {
        folder.pk: (folder.creation_source, folder.creation_operation, folder.created_by_id)
        for folder in DocumentFolder.objects.all()
    } == original
