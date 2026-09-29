"""A repair moves only the reviewed documents and records the operation."""
from unittest.mock import patch

import pytest
from accounts.models import UserProfile
from django.db import IntegrityError

from content.models import (
    AccountingChangeLog,
    Document,
    DocumentFolder,
    DocumentType,
    EntityRevision,
)
from content.services.document_folder_repair import (
    FolderRepairError,
    apply_repair,
    fingerprint,
    prepare_repair,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def repair_case(django_user_model):
    owner = django_user_model.objects.create_user(username='folder-owner')
    client = UserProfile.objects.create(user=owner, role=UserProfile.ROLE_CLIENT)
    source = DocumentFolder.objects.create(name='Littigio', creation_source='unknown')
    target = DocumentFolder.objects.create(name='Littigio', managed_client=owner, client_user=owner)
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    documents = [Document.objects.create(title=f'Document {i}', folder=source, document_type=kind, content_markdown=f'# Text {i}') for i in range(5)]
    manifest = prepare_repair(source.pk, target.pk, client.pk, [doc.pk for doc in documents])
    return source, target, documents, manifest


def test_preview_preserves_database_state(repair_case):
    source, _, documents, manifest = repair_case

    assert Document.objects.filter(pk__in=manifest['document_ids'], folder=source).count() == 5
    assert not DocumentFolder.objects.get(pk=source.pk).is_archived
    assert AccountingChangeLog.objects.count() == 0


def test_repair_preserves_document_associations(repair_case, superuser):
    source, target, documents, manifest = repair_case
    before = list(Document.objects.filter(pk__in=manifest['document_ids']).order_by('pk').values('content_markdown', 'client_user_id', 'project_id', 'is_client_visible'))

    apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    after = list(Document.objects.filter(pk__in=manifest['document_ids']).order_by('pk').values('content_markdown', 'client_user_id', 'project_id', 'is_client_visible'))
    assert after == before
    assert target.documents.count() == 5
    source.refresh_from_db()
    assert source.is_archived is True
    assert source.creation_source == 'unknown'


def test_repair_records_folder_changes(repair_case, superuser):
    source, target, _, manifest = repair_case

    apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    revisions = EntityRevision.objects.filter(history__object_id__in=manifest['document_ids'], source='command:repair_document_folder', action='updated')
    assert revisions.count() == 5
    assert AccountingChangeLog.objects.filter(entity_type='document_folder', object_id=source.pk, actor=superuser).count() == 1


def test_repair_repetition_does_not_add_history(repair_case, superuser):
    _, _, _, manifest = repair_case
    apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')
    count = EntityRevision.objects.count()

    result = apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    assert result['changed'] is False
    assert EntityRevision.objects.count() == count


def test_changed_document_invalidates_manifest(repair_case, superuser):
    source, _, documents, manifest = repair_case
    documents[0].title = 'Edited since review'
    documents[0].save()

    with pytest.raises(FolderRepairError, match='estado cambió'):
        apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    assert source.documents.count() == 5


def test_added_document_invalidates_manifest(repair_case, superuser):
    source, _, _, manifest = repair_case
    Document.objects.create(title='Unexpected', folder=source)

    with pytest.raises(FolderRepairError, match='estado cambió'):
        apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    assert source.documents.count() == 6


def test_subfolder_prevents_repair(repair_case, superuser):
    source, _, _, manifest = repair_case
    DocumentFolder.objects.create(name='Unexpected child', parent=source)

    with pytest.raises(FolderRepairError, match='subcarpetas'):
        apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    assert source.documents.count() == 5


def test_invalid_hash_prevents_repair(repair_case, superuser):
    source, _, _, manifest = repair_case

    with pytest.raises(FolderRepairError, match='hash'):
        apply_repair(manifest, expected_hash='invalid', actor=superuser, backup_ref='backup.sql.gz')

    assert source.documents.count() == 5


def test_failed_archive_rolls_back_moves(repair_case, superuser):
    source, target, _, manifest = repair_case
    with patch('content.services.document_folder_repair.archive_folder', side_effect=IntegrityError('database fault')):
        with pytest.raises(IntegrityError, match='database fault'):
            apply_repair(manifest, expected_hash=fingerprint(manifest), actor=superuser, backup_ref='backup.sql.gz')

    assert source.documents.count() == 5
    assert target.documents.count() == 0
    assert not AccountingChangeLog.objects.filter(entity_type='document_folder').exists()
