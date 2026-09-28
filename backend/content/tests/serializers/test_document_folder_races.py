"""Validation is repeated under the tree mutex at commit time."""
import pytest
from rest_framework.exceptions import ValidationError

from content.models import DocumentFolder
from content.serializers.document_folder import DocumentFolderSerializer

pytestmark = pytest.mark.django_db


def test_stale_validation_cannot_create_a_duplicate():
    first = DocumentFolderSerializer(data={'name': 'Littigio'})
    second = DocumentFolderSerializer(data={'name': 'littigio'})
    assert first.is_valid()
    assert second.is_valid()
    first.save()

    with pytest.raises(ValidationError, match='duplicate_folder_name'):
        second.save()

    assert DocumentFolder.objects.filter(name__iexact='littigio').count() == 1


def test_stale_validation_cannot_create_a_reciprocal_cycle():
    first = DocumentFolder.objects.create(name='First')
    second = DocumentFolder.objects.create(name='Second')
    move_first = DocumentFolderSerializer(first, data={'parent_id': second.pk}, partial=True)
    move_second = DocumentFolderSerializer(second, data={'parent_id': first.pk}, partial=True)
    assert move_first.is_valid()
    assert move_second.is_valid()
    move_first.save()

    with pytest.raises(ValidationError, match='subcarpetas'):
        move_second.save()

    second.refresh_from_db()
    assert second.parent_id is None
