"""Folder writers restore the mutex after transactional database flushes."""

from types import SimpleNamespace

import pytest
from accounts.models import Project
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from content.models import Document, DocumentFolder, DocumentOwnershipOperation
from content.models.document_folder import DocumentFolderMutationLock
from content.serializers.document_folder import DocumentFolderSerializer
from content.services import folder_migration_service as migration
from content.services.document_ownership_planner import plan_ownership
from content.services.project_document_folder_service import require_project_folder
from content.tests.mcp_parity import assert_no_writes

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def owner(make_client_profile):
    """Create the explicit profile before its on-commit safety net runs."""
    with transaction.atomic():
        return make_client_profile()


def test_project_creation_provisions_root_without_mutex(owner):
    DocumentFolderMutationLock.objects.all().delete()

    project = Project.objects.create(name='Flushed project', client=owner.user)

    root = require_project_folder(project)
    assert (root.managed_project_id, root.project_id, root.client_user_id, root.name) == (
        project.pk, project.pk, owner.user_id, project.name,
    )
    assert DocumentFolderMutationLock.objects.filter(pk=1).exists()


@pytest.mark.parametrize('strategy', ['adopt_source', 'move_contents'])
def test_migration_applies_without_seeded_mutex(owner, superuser, strategy):
    source = DocumentFolder.objects.create(name='Legacy source')
    document = Document.objects.create(title='Migrated private note', folder=source)
    project = Project.objects.create(name='Migration target', client=owner.user)
    data = {
        'source_folder_id': source.pk,
        'strategy': strategy,
        'target': {'project_id': project.pk},
    }
    DocumentFolderMutationLock.objects.all().delete()

    plan = assert_no_writes(migration.preview_folder_migration, data, actor=superuser)
    assert plan['can_apply'], plan['blockers']
    assert not DocumentFolderMutationLock.objects.exists()
    report = migration.apply_folder_migration(
        plan['plan_token'], 'Organizar la carpeta', f'missing-mutex-{strategy}', actor=superuser,
    )

    root = require_project_folder(project)
    document.refresh_from_db()
    assert (document.folder_id, document.project_id, document.client_user_id) == (
        root.pk, project.pk, owner.user_id,
    )
    operation = DocumentOwnershipOperation.objects.get(pk=report['migration_id'])
    assert (operation.plan_hash, operation.report, report['project_id']) == (
        plan['plan_hash'], report, project.pk,
    )
    assert DocumentFolderMutationLock.objects.filter(pk=1).exists()


def test_locked_ownership_plan_restores_mutex_without_moving_document(owner):
    source = DocumentFolder.objects.create(name='Original location')
    destination = DocumentFolder.objects.create(name='Client destination', client_user=owner.user)
    document = Document.objects.create(title='Planned private note', folder=source)
    args = {
        'document_ids': [document.pk],
        'destination_folder_id': destination.pk,
        'client_policy': 'inherit',
    }
    DocumentFolderMutationLock.objects.all().delete()
    preview = assert_no_writes(plan_ownership, **args)

    with transaction.atomic():
        locked_plan = plan_ownership(**args, lock=True)

    assert locked_plan == preview
    row = locked_plan['rows'][0]
    assert (locked_plan['can_apply'], row['after']['folder_or_parent_id'], row['after']['client_user_id']) == (
        True, destination.pk, owner.user_id,
    )
    document.refresh_from_db()
    assert (document.folder_id, document.client_user_id) == (source.pk, None)
    assert DocumentFolderMutationLock.objects.filter(pk=1).exists()


def test_policy_folder_update_restores_mutex_before_tree_refresh(owner, superuser):
    source = DocumentFolder.objects.create(name='Moving subtree')
    child = DocumentFolder.objects.create(name='Nested folder', parent=source)
    document = Document.objects.create(title='Nested private note', folder=child)
    destination = DocumentFolder.objects.create(name='Owned destination', client_user=owner.user)
    DocumentFolderMutationLock.objects.all().delete()
    serializer = DocumentFolderSerializer(
        source,
        data={'parent_id': destination.pk, 'client_policy': 'inherit', 'portal_policy': 'abort'},
        partial=True,
        context={'request': SimpleNamespace(user=superuser)},
    )
    serializer.is_valid(raise_exception=True)

    with CaptureQueriesContext(connection) as queries:
        updated = serializer.save()

    # Both mutex reads precede the serializer's refresh of the folder tree.
    reads = [query['sql'] for query in queries.captured_queries if query['sql'].lstrip().upper().startswith('SELECT')]
    lock_table = DocumentFolderMutationLock._meta.db_table
    assert tuple(lock_table in sql for sql in reads[:2]) == (True, True)
    child.refresh_from_db()
    document.refresh_from_db()
    assert (updated.parent_id, updated.client_user_id) == (destination.pk, owner.user_id)
    assert (child.parent_id, child.client_user_id, document.folder_id, document.client_user_id) == (
        source.pk, owner.user_id, child.pk, owner.user_id,
    )
    assert DocumentFolderMutationLock.objects.filter(pk=1).exists()
