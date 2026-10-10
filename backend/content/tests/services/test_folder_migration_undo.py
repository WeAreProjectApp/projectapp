"""Exact undo refuses later ownership, placement or dependent business data."""

import pytest
from accounts.models import Project, ProjectContract
from django.utils import timezone

from content.models import (
    Document,
    DocumentFolder,
    DocumentOwnershipOperation,
    DocumentType,
)
from content.services import folder_migration_service as service
from content.tests.mcp_parity import assert_no_writes, ownership_state
from content.tests.services.test_folder_migration import (
    apply,
    migration_input,
)
from content.tests.services.test_folder_migration import (
    migration_case as migration_case,  # noqa: PLC0414 -- Re-export the shared pytest fixture.
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('changed', ['document', 'folder', 'template'])
def test_undo_refuses_changed_rows(migration_case, changed):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    rows = {'document': (Document, case.nested.pk, {'is_client_visible': True}),
            'folder': (DocumentFolder, case.child.pk, {'name': 'Operator rename'}),
            'template': (DocumentFolder, report['created_folder_ids'][0], {'order': 99})}
    model, pk, values = rows[changed]
    model.objects.filter(pk=pk).update(**values)
    before = ownership_state()
    preview = assert_no_writes(service.preview_undo_migration, report['migration_id'])

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(report['migration_id'], preview['impact_hash'], 'No pisar cambios', 'undo-changed', actor=case.actor)

    assert error.value.code == 'undo_blocked'
    assert 'changed_since' in {row['code'] for row in error.value.details['blockers']}
    assert ownership_state() == before


@pytest.mark.parametrize('content', ['document', 'folder'])
def test_undo_refuses_new_content_in_created_folders(migration_case, content):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    folder = DocumentFolder.objects.get(pk=report['created_folder_ids'][0])
    factories = {'document': lambda: Document.objects.create(title='New delivery evidence', folder=folder, is_archived=True),
                 'folder': lambda: DocumentFolder.objects.create(name='New nested folder', parent=folder, is_archived=True)}
    factories[content]()
    before = ownership_state()
    preview = assert_no_writes(service.preview_undo_migration, report['migration_id'])

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(report['migration_id'], preview['impact_hash'], 'Conservar contenido nuevo', 'undo-content', actor=case.actor)

    assert 'new_content_since' in {row['code'] for row in error.value.details['blockers']}
    assert ownership_state() == before


def test_undo_refuses_created_project_in_use(migration_case):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    Project.objects.filter(pk=report['created_project_id']).update(production_url='https://project.example.test')
    before = ownership_state()
    preview = assert_no_writes(service.preview_undo_migration, report['migration_id'])

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(report['migration_id'], preview['impact_hash'], 'Conservar proyecto usado', 'undo-used', actor=case.actor)

    blocker = next(row for row in error.value.details['blockers'] if row['code'] == 'project_in_use')
    assert blocker['dependencies'] == [{'key': 'configuration', 'label': 'Configuración operativa del proyecto', 'count': 1}]
    assert ownership_state() == before
    assert Project.objects.filter(pk=report['project_id']).exists()


def test_undo_replays_the_original_receipt(migration_case):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    preview = service.preview_undo_migration(report['migration_id'])
    undo = service.undo_migration(report['migration_id'], preview['impact_hash'], 'Restaurar', 'undo-replay', actor=case.actor)

    replay = service.undo_migration(report['migration_id'], preview['impact_hash'], 'Restaurar otra vez', 'undo-replay', actor=case.actor)
    reverted = assert_no_writes(service.preview_undo_migration, report['migration_id'])
    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(report['migration_id'], reverted['impact_hash'], 'No repetir', 'undo-again', actor=case.actor)

    assert replay == undo
    assert error.value.code == 'undo_blocked'
    assert 'already_reverted' in {row['code'] for row in error.value.details['blockers']}
    assert DocumentOwnershipOperation.objects.count() == 2


def test_undo_requires_lifo_for_rows_touched_later(migration_case):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    operation = DocumentOwnershipOperation.objects.get(pk=report['migration_id'])
    later = DocumentOwnershipOperation.objects.create(
        kind='migration', origin='panel', request_id='later', plan_hash='b' * 64,
        reason='Otra operación', actor=case.actor, items=operation.items,
    )
    preview = assert_no_writes(service.preview_undo_migration, operation.pk)

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(operation.pk, preview['impact_hash'], 'Respetar el orden', 'undo-lifo', actor=case.actor)

    blocker = next(row for row in error.value.details['blockers'] if row.get('reason') == 'lifo')
    assert blocker['operation_ids'] == [later.pk]
    assert DocumentOwnershipOperation.objects.filter(reverts=operation).exists() is False


def test_undo_hash_uses_only_ownership(migration_case):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    preview = service.preview_undo_migration(report['migration_id'])
    Document.objects.filter(pk=case.nested.pk).update(updated_at=timezone.now(), content_markdown='New content is preserved')
    changed = assert_no_writes(service.preview_undo_migration, report['migration_id'])

    service.undo_migration(report['migration_id'], preview['impact_hash'], 'Restaurar propiedad', 'undo-content-edit', actor=case.actor)

    case.nested.refresh_from_db()
    assert changed['impact_hash'] == preview['impact_hash']
    assert case.nested.content_markdown == 'New content is preserved'
    assert case.nested.project_id is None


def test_stale_undo_rolls_back(migration_case):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    preview = service.preview_undo_migration(report['migration_id'])
    case.child.name = 'Changed after preview'
    case.child.save(update_fields=['name'])
    before = ownership_state()

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(report['migration_id'], preview['impact_hash'], 'Revalidar intención', 'undo-stale', actor=case.actor)

    assert error.value.code == 'stale_version'
    assert ownership_state() == before
    assert DocumentOwnershipOperation.objects.count() == 1


@pytest.mark.parametrize('freeze', ['generated', 'contract', 'issued_account'])
def test_undo_keeps_new_frozen_ownership(migration_case, freeze):
    case = migration_case
    _plan, report = apply(case, migration_input(case, target='existing'))
    kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Cuenta de cobro'})
    mutations = {
        'generated': lambda: Document.objects.filter(pk=case.nested.pk).update(generated_file='documents/generated/new.pdf'),
        'contract': lambda: ProjectContract.objects.create(project=case.project, document=case.nested, key='after', title='New contract'),
        'issued_account': lambda: Document.objects.filter(pk=case.nested.pk).update(document_type=kind, commercial_status='issued'),
    }
    mutations[freeze]()
    before = ownership_state()
    preview = assert_no_writes(service.preview_undo_migration, report['migration_id'])

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(report['migration_id'], preview['impact_hash'], 'Conservar propiedad congelada', 'undo-frozen', actor=case.actor)

    blocker = next(row for row in error.value.details['blockers'] if row['code'] == 'changed_since')
    assert {'model': 'content.document', 'id': case.nested.pk, 'reason': 'ownership_frozen'} in blocker['records']
    assert ownership_state() == before


def test_failure_during_undo_restores_migrated_state(migration_case, monkeypatch):
    case = migration_case
    _plan, report = apply(case, migration_input(case))
    preview = service.preview_undo_migration(report['migration_id'])
    before = ownership_state()
    count = Project.objects.count()

    def fail_deletion(*args, **kwargs):
        raise RuntimeError('Injected undo failure')

    monkeypatch.setattr(service, 'delete_empty_project', fail_deletion)
    with pytest.raises(RuntimeError, match='Injected undo'):
        service.undo_migration(report['migration_id'], preview['impact_hash'], 'Deshacer atómicamente', 'undo-rollback', actor=case.actor)

    assert ownership_state() == before
    assert Project.objects.count() == count
    assert DocumentOwnershipOperation.objects.count() == 1
