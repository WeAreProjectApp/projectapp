"""Django-admin folder creation uses the locked public serializer path."""
import pytest
from django.test import RequestFactory

from content.admin import DocumentFolderAdminForm, admin_site
from content.models import DocumentFolder

pytestmark = pytest.mark.django_db


def test_admin_folder_creation_records_the_authenticated_administrator(admin_user):
    """Falla si el admin guarda una carpeta manual sin atribuirla al administrador."""
    form = DocumentFolderAdminForm(data={'name': 'Legal', 'order': 3})
    request = RequestFactory().post('/admin/content/documentfolder/add/')
    request.user = admin_user
    folder = DocumentFolder()
    folder_admin = admin_site._registry[DocumentFolder]

    assert form.is_valid(), form.errors
    folder_admin.save_model(request, folder, form, change=False)
    saved = DocumentFolder.objects.get(name='Legal')

    assert saved.creation_source == 'panel'
    assert saved.created_by_id == admin_user.pk
    assert saved.creation_operation == 'django_admin.create_folder'


def test_admin_folder_form_rejects_a_duplicate_root_name():
    """Falla si el formulario de admin permite duplicar una carpeta manual raíz."""
    DocumentFolder.objects.create(name='Duplicated root')

    form = DocumentFolderAdminForm(data={'name': 'Duplicated root', 'order': 0})

    assert form.is_valid() is False
    assert 'name: Ya existe una carpeta con ese nombre aquí' in form.non_field_errors()


def test_admin_folder_form_rejects_a_user_without_client_profile(admin_user):
    """Falla si el admin descarta silenciosamente la asociación de un usuario sin perfil."""
    form = DocumentFolderAdminForm(
        data={'name': 'Client folder', 'order': 0, 'client_user': admin_user.pk},
    )

    assert form.is_valid() is False
    assert 'El usuario seleccionado no tiene un perfil de cliente.' in form.non_field_errors()
