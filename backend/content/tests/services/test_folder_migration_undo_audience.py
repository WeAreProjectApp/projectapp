"""Undo preserves the original portal audience across project owner changes."""

from types import SimpleNamespace

import pytest
from accounts.document_views import _visible_docs_qs
from accounts.models import Project

from content.models import Document, DocumentFolder, DocumentOwnershipOperation
from content.services import folder_migration_service as service
from content.services.diagnostic_privacy import safe_mcp_error_code
from content.tests.mcp_parity import assert_no_writes, ownership_state

pytestmark = pytest.mark.django_db


@pytest.fixture
def migrated_document(make_client_profile, superuser):
    original_owner = make_client_profile(company='Original audience')
    destination_owner = make_client_profile(company='Destination audience')
    replacement_owner = make_client_profile(company='Replacement audience')
    original_project = Project.objects.create(name='Original project', client=original_owner.user)
    destination_project = Project.objects.create(name='Destination project', client=destination_owner.user)
    source = DocumentFolder.objects.create(name='Manual source', creation_source='panel')
    document = Document.objects.create(
        title='Private original document', folder=source, project=original_project,
        client_user=None, is_client_visible=True,
    )
    initial = ownership_state()
    plan = service.preview_folder_migration({
        'source_folder_id': source.pk, 'strategy': 'move_contents',
        'target': {'project_id': destination_project.pk},
        'client_policy': 'inherit', 'portal_policy': 'hide_new_exposure',
    }, actor=superuser)
    assert plan['can_apply'], plan['blockers']
    report = service.apply_folder_migration(
        plan['plan_token'], 'Organizar los documentos', 'audience-migration', actor=superuser,
    )
    return SimpleNamespace(
        document=document, source=source, original_project=original_project,
        original_owner=original_owner, replacement_owner=replacement_owner,
        destination_project=destination_project, report=report, actor=superuser, initial=initial,
    )


def test_undo_blocks_a_replacement_project_audience(migrated_document):
    case = migrated_document
    operation = DocumentOwnershipOperation.objects.get(pk=case.report['migration_id'])
    original = next(item['before'] for item in operation.items if item['model'] == 'content.document')
    Project.objects.filter(pk=case.original_project.pk).update(client=case.replacement_owner.user)
    migrated = ownership_state()

    preview = assert_no_writes(service.preview_undo_migration, operation.pk)
    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(operation.pk, preview['impact_hash'], 'Restaurar', 'undo-audience', actor=case.actor)

    assert original['portal_audience'] == case.original_owner.user_id
    assert preview['can_undo'] is False
    assert {row['code'] for row in preview['blockers']} == {'undo_audience_changed'}
    blocker = error.value.details['blockers'][0]
    assert blocker['document_id'] == case.document.pk
    assert blocker['before_audience'] == case.original_owner.user_id
    assert blocker['after_audience'] == case.replacement_owner.user_id
    assert case.document.title in blocker['message']
    assert safe_mcp_error_code('UNDO_AUDIENCE_CHANGED') == 'UNDO_AUDIENCE_CHANGED'
    assert ownership_state() == migrated
    assert not _visible_docs_qs(SimpleNamespace(user=case.replacement_owner.user)).filter(pk=case.document.pk).exists()
    assert not DocumentOwnershipOperation.objects.filter(reverts=operation).exists()


def test_undo_restores_the_unchanged_original_audience(migrated_document):
    case = migrated_document
    preview = assert_no_writes(service.preview_undo_migration, case.report['migration_id'])

    report = service.undo_migration(
        case.report['migration_id'], preview['impact_hash'], 'Volver al cliente original',
        'undo-same-audience', actor=case.actor,
    )

    case.document.refresh_from_db()
    assert preview['can_undo'] is True
    assert report['reverts'] == case.report['migration_id']
    assert ownership_state() == case.initial
    assert (case.document.client_user_id, case.document.project_id, case.document.is_client_visible) == (
        None, case.original_project.pk, True,
    )
    assert _visible_docs_qs(SimpleNamespace(user=case.original_owner.user)).filter(pk=case.document.pk).exists()


def test_legacy_receipt_blocks_an_unrecorded_visible_audience(migrated_document):
    case = migrated_document
    operation = DocumentOwnershipOperation.objects.get(pk=case.report['migration_id'])
    item = next(item for item in operation.items if item['model'] == 'content.document')
    del item['before']['portal_audience']
    operation.save(update_fields=['items'])
    migrated = ownership_state()

    preview = service.preview_undo_migration(operation.pk)
    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(operation.pk, preview['impact_hash'], 'Revisar legado', 'undo-legacy', actor=case.actor)

    blocker = error.value.details['blockers'][0]
    assert blocker['code'] == 'undo_audience_changed'
    assert blocker['before_audience'] is None
    assert blocker['after_audience'] == case.original_owner.user_id
    assert ownership_state() == migrated


def test_legacy_receipt_can_restore_without_a_portal_audience(migrated_document):
    case = migrated_document
    operation = DocumentOwnershipOperation.objects.get(pk=case.report['migration_id'])
    item = next(item for item in operation.items if item['model'] == 'content.document')
    del item['before']['portal_audience']
    item['before']['is_client_visible'] = False
    operation.save(update_fields=['items'])

    preview = service.preview_undo_migration(operation.pk)
    service.undo_migration(operation.pk, preview['impact_hash'], 'Restaurar privado', 'undo-private-legacy', actor=case.actor)

    case.document.refresh_from_db()
    assert preview['can_undo'] is True
    assert case.document.project_id == case.original_project.pk
    assert case.document.is_client_visible is False
    assert not _visible_docs_qs(SimpleNamespace(user=case.original_owner.user)).filter(pk=case.document.pk).exists()


def test_undo_rechecks_project_audience_under_locks(migrated_document, monkeypatch):
    case = migrated_document
    preview = service.preview_undo_migration(case.report['migration_id'])
    lock_scope = service._lock_scope

    def replace_owner_at_lock(*args, **kwargs):
        assert case.original_project.pk in kwargs['restore_project_ids']
        Project.objects.filter(pk=case.original_project.pk).update(client=case.replacement_owner.user)
        return lock_scope(*args, **kwargs)

    monkeypatch.setattr(service, '_lock_scope', replace_owner_at_lock)
    migrated = ownership_state()

    with pytest.raises(service.FolderMigrationError) as error:
        service.undo_migration(
            case.report['migration_id'], preview['impact_hash'], 'Revalidar audiencia',
            'undo-racing-audience', actor=case.actor,
        )

    assert error.value.code == 'stale_version'
    assert ownership_state() == migrated
    assert not DocumentOwnershipOperation.objects.filter(reverts_id=case.report['migration_id']).exists()
