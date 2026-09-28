"""Folder write boundaries apply equally to Panel and MCP callers."""
import pytest

from content.models import DocumentFolder
from content.serializers.document_folder import DocumentFolderSerializer

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('parent_field', ['parent_id', 'parent'])
def test_parent_alias_moves_folder(parent_field):
    folder = DocumentFolder.objects.create(name='Child')
    parent = DocumentFolder.objects.create(name='Parent')
    serializer = DocumentFolderSerializer(folder, data={parent_field: parent.pk}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    folder.refresh_from_db()
    assert folder.parent_id == parent.pk


def test_conflicting_parent_aliases_are_rejected():
    serializer = DocumentFolderSerializer(data={'name': 'Child', 'parent': None, 'parent_id': 12})
    assert not serializer.is_valid()
    assert 'parent_id' in serializer.errors
    assert not DocumentFolder.objects.exists()


@pytest.mark.parametrize('field', ['parent_ids', 'created_by', 'slug'])
def test_unwritable_fields_do_not_partially_rename(field):
    folder = DocumentFolder.objects.create(name='Original')
    serializer = DocumentFolderSerializer(folder, data={'name': 'Changed', field: 'bad'}, partial=True)
    assert not serializer.is_valid()
    assert field in serializer.errors
    folder.refresh_from_db()
    assert folder.name == 'Original'


@pytest.mark.parametrize('parent_field', ['parent_id', 'parent'])
def test_descendant_cycle_is_rejected(parent_field):
    folder = DocumentFolder.objects.create(name='Root')
    child = DocumentFolder.objects.create(name='Child', parent=folder)
    serializer = DocumentFolderSerializer(folder, data={parent_field: child.pk}, partial=True)
    assert not serializer.is_valid()
    folder.refresh_from_db()
    assert folder.parent_id is None


def test_self_parent_is_rejected():
    folder = DocumentFolder.objects.create(name='Root')
    serializer = DocumentFolderSerializer(folder, data={'parent_id': folder.pk}, partial=True)
    assert not serializer.is_valid()
    assert 'parent' in serializer.errors


@pytest.mark.parametrize('archived', [False, True])
def test_sibling_duplicate_is_rejected(archived):
    original = DocumentFolder.objects.create(name='Littigio', is_archived=archived)
    serializer = DocumentFolderSerializer(data={'name': ' littigio '})
    assert not serializer.is_valid()
    assert serializer.errors['code'][0] == 'duplicate_folder_name'
    assert str(original.pk) in serializer.errors['matching_ids']
    assert DocumentFolder.objects.count() == 1


def test_duplicate_name_in_other_parent_is_allowed():
    parent = DocumentFolder.objects.create(name='Parent')
    DocumentFolder.objects.create(name='Littigio')
    serializer = DocumentFolderSerializer(data={'name': 'Littigio', 'parent_id': parent.pk})
    assert serializer.is_valid(), serializer.errors
    assert serializer.save().parent_id == parent.pk


def test_moving_into_duplicate_is_rejected():
    parent = DocumentFolder.objects.create(name='Parent')
    DocumentFolder.objects.create(name='Same', parent=parent)
    folder = DocumentFolder.objects.create(name='Same')
    serializer = DocumentFolderSerializer(folder, data={'parent_id': parent.pk}, partial=True)
    assert not serializer.is_valid()
    assert serializer.errors['code'][0] == 'duplicate_folder_name'


def test_historical_duplicate_can_change_order():
    DocumentFolder.objects.create(name='Same')
    folder = DocumentFolder.objects.create(name='Same')
    serializer = DocumentFolderSerializer(folder, data={'order': 4}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert serializer.save().order == 4


def test_rename_preserves_slug():
    folder = DocumentFolder.objects.create(name='Templates')
    serializer = DocumentFolderSerializer(folder, data={'name': 'Plantillas'}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert serializer.save().slug == 'templates'


@pytest.mark.parametrize('payload', [{'name': 'Renamed'}, {'parent_id': None}, {'order': 3}])
def test_system_folder_is_immutable(payload):
    folder = DocumentFolder.objects.create(name='Automatic', system_key='test:folder')
    serializer = DocumentFolderSerializer(folder, data=payload, partial=True)
    assert not serializer.is_valid()
    assert serializer.errors['code'][0] == 'system_managed_folder'


def test_system_destination_is_rejected():
    parent = DocumentFolder.objects.create(name='Automatic', system_key='test:folder')
    serializer = DocumentFolderSerializer(data={'name': 'Child', 'parent_id': parent.pk})
    assert not serializer.is_valid()
    assert 'parent' in serializer.errors
