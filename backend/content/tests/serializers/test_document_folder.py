"""Tests for DocumentFolderSerializer — client/project association.

Una carpeta lleva el nombre de un cliente o de un proyecto desde siempre; acá
se verifica que lo diga como relación, con la MISMA regla que ya gobierna a los
documentos (`apply_client_project_association`): el proyecto manda sobre el
cliente, un par incoherente se rechaza en `project`, y cambiar de cliente sin
reasignar el proyecto lo desvincula.
"""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model

from content.models import DocumentFolder
from content.serializers.document_folder import DocumentFolderSerializer

pytestmark = pytest.mark.django_db


def make_client(email, *, first='Ana', last='Pérez'):
    user = get_user_model().objects.create_user(
        username=email, email=email, password='pass12345',
        first_name=first, last_name=last,
    )
    return UserProfile.objects.create(user=user, cedula='1049654583')


class TestDocumentFolderAssociation:
    def test_client_writes_client_user(self):
        profile = make_client('ana@example.com')
        serializer = DocumentFolderSerializer(
            data={'name': 'Ana Pérez', 'client': profile.pk},
        )
        assert serializer.is_valid(), serializer.errors
        folder = serializer.save()
        assert folder.client_user == profile.user

    def test_project_alone_derives_the_client(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        serializer = DocumentFolderSerializer(
            data={'name': 'Kore - Diseño archivos', 'project': project.pk},
        )
        assert serializer.is_valid(), serializer.errors
        folder = serializer.save()
        assert folder.project == project
        assert folder.client_user == profile.user

    def test_project_of_another_client_is_rejected(self):
        mine = make_client('ana@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        project = Project.objects.create(name='MIMITTOS', client=other.user)
        serializer = DocumentFolderSerializer(
            data={'name': 'Ana', 'client': mine.pk, 'project': project.pk},
        )
        assert not serializer.is_valid()
        assert 'pertenece a otro cliente' in str(serializer.errors['project'])

    def test_changing_client_without_project_clears_the_project(self):
        kore = make_client('kore@example.com', first='Kore', last='SAS')
        ana = make_client('ana@example.com')
        project = Project.objects.create(name='Kore - Diseño', client=kore.user)
        folder = DocumentFolder.objects.create(
            name='Kore', client_user=kore.user, project=project,
        )
        serializer = DocumentFolderSerializer(
            folder, data={'client': ana.pk}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        folder = serializer.save()
        assert folder.client_user == ana.user
        assert folder.project is None

    def test_client_null_unlinks_the_folder(self):
        profile = make_client('ana@example.com')
        folder = DocumentFolder.objects.create(
            name='Ana', client_user=profile.user,
        )
        serializer = DocumentFolderSerializer(
            folder, data={'client': None}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.save().client_user is None

    def test_reads_back_the_profile_pk_and_the_names(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        folder = DocumentFolder.objects.create(
            name='Kore', client_user=profile.user, project=project,
        )
        data = DocumentFolderSerializer(folder).data
        assert data['client'] == profile.pk
        assert data['project'] == project.pk
        assert data['project_name'] == 'Kore - Diseño'
        assert data['client_display_name']

    def test_a_folder_without_association_reads_nulls(self):
        folder = DocumentFolder.objects.create(name='Sin dueño')
        data = DocumentFolderSerializer(folder).data
        assert data['client'] is None
        assert data['project'] is None
        assert data['client_display_name'] is None
        assert data['project_name'] is None
