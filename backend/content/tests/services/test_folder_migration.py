"""Folder migrations preserve reviewed intent and roll back every side effect."""

from types import SimpleNamespace

import pytest
from accounts.models import Project
from django.core import signing
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import PermissionDenied, ValidationError

from content.models import (
    AccountingChangeLog,
    Document,
    DocumentFolder,
    DocumentOwnershipOperation,
)
from content.services import folder_migration_service as service
from content.services.project_document_folder_service import require_project_folder
from content.tests.mcp_parity import assert_no_writes, ownership_state

pytestmark = pytest.mark.django_db


@pytest.fixture
def migration_case(make_client_profile, superuser):
    owner = make_client_profile()
    source = DocumentFolder.objects.create(name='Legacy tree', creation_source='panel', created_by=superuser)
    child = DocumentFolder.objects.create(name='Notes', parent=source, creation_source='panel')
    nested = Document.objects.create(title='Nested note', folder=child)
    loose = Document.objects.create(title='Loose note', folder=source)
    project = Project.objects.create(name='Existing target', client=owner.user)
    return SimpleNamespace(owner=owner, source=source, child=child, nested=nested,
                           loose=loose, project=project, actor=superuser)


def migration_input(case, strategy='adopt_source', target='new', **overrides):
    targets = {'new': {'create_project': {'name': 'New target', 'client_profile_id': case.owner.pk}},
               'existing': {'project_id': case.project.pk}}
    return {'source_folder_id': case.source.pk, 'strategy': strategy, 'target': targets[target], **overrides}


def apply(case, data, request_id='migration'):
    plan = assert_no_writes(service.preview_folder_migration, data, actor=case.actor)
    assert plan['can_apply'], plan['blockers']
    return plan, service.apply_folder_migration(plan['plan_token'], 'Organizar el proyecto', request_id, actor=case.actor)


@pytest.mark.parametrize('strategy', ['adopt_source', 'move_contents'])
@pytest.mark.parametrize('target', ['new', 'existing'])
def test_migration_strategies_restore_exact_tree(migration_case, strategy, target):
    case = migration_case
    before = ownership_state()
    count = Project.objects.count()

    plan, report = apply(case, migration_input(case, strategy, target))

    project = Project.objects.get(pk=report['project_id'])
    root = require_project_folder(project)
    case.child.refresh_from_db()
    case.loose.refresh_from_db()
    assert case.child.parent_id == root.pk
    assert (case.loose.project_id, case.loose.client_user_id) == (project.pk, case.owner.user_id)
    assert report['plan_hash'] == plan['plan_hash']
    operation = DocumentOwnershipOperation.objects.get(pk=report['migration_id'])
    assert operation.kind == {'adopt_source': 'adoption', 'move_contents': 'migration'}[strategy]
    assert all('updated_at' not in item['before'] and 'updated_at' not in item['after'] for item in operation.items)
    undo = assert_no_writes(service.preview_undo_migration, operation.pk)
    assert undo['can_apply'], undo['blockers']
    service.undo_migration(operation.pk, undo['impact_hash'], 'Volver al árbol original', 'undo', actor=case.actor)
    assert ownership_state() == before
    assert Project.objects.count() == count
    assert DocumentOwnershipOperation.objects.get(pk=operation.pk).reverted_by.kind == 'undo'


def test_include_filters_keep_archived_content_pending(migration_case):
    case = migration_case
    archived = Document.objects.create(title='Historical loose item', folder=case.source, is_archived=True)
    args = migration_input(case, 'move_contents', include_folder_ids=[case.child.pk], include_document_ids=[], archive_source_when_empty=True)

    plan, report = apply(case, args)

    case.source.refresh_from_db()
    case.loose.refresh_from_db()
    archived.refresh_from_db()
    assert case.source.is_archived is False
    assert case.loose.folder_id == archived.folder_id == case.source.pk
    assert report['pending'] == plan['archive']['pending'] == [
        {'resource_type': 'document', 'id': case.loose.pk}, {'resource_type': 'document', 'id': archived.pk},
    ]
    assert report['archived_folder_ids'] == []
    assert report['pending_reason']


def test_move_renames_source_before_project_creation(migration_case, monkeypatch):
    case = migration_case
    case.source.name = ' New target '
    case.source.archived_at = timezone.now()
    case.source.save(update_fields=['name', 'archived_at'])
    initial = ownership_state()
    previous_archive_date = case.source.archived_at
    blocked = assert_no_writes(service.preview_folder_migration, migration_input(case, 'move_contents'), actor=case.actor)
    assert 'source_name_conflict' in {row['code'] for row in blocked['blockers']}
    original_create = service._create_project

    def create_after_rename(*args, **kwargs):
        assert DocumentFolder.objects.get(pk=case.source.pk).name == 'Previous ProjectApp'
        return original_create(*args, **kwargs)

    monkeypatch.setattr(service, '_create_project', create_after_rename)
    plan, report = apply(case, migration_input(case, 'move_contents', source_rename_to='Previous ProjectApp', archive_source_when_empty=True))

    case.source.refresh_from_db()
    assert case.source.is_archived is True
    assert report['archived_folder_ids'] == [case.source.pk]
    undo = service.preview_undo_migration(report['migration_id'])
    service.undo_migration(report['migration_id'], undo['impact_hash'], 'Restaurar nombre y archivo', 'undo-rename', actor=case.actor)
    case.source.refresh_from_db()
    assert case.source.archived_at == previous_archive_date
    assert ownership_state() == initial
    assert plan['renames'][0]['after'] == 'Previous ProjectApp'


@pytest.mark.parametrize('target', ['new', 'existing'])
def test_adoption_reuses_manual_template_children(migration_case, target):
    case = migration_case
    qa = DocumentFolder.objects.create(name='QA', parent=case.source, creation_source='panel')
    deliveries = DocumentFolder.objects.create(name='Entregables', parent=case.source, creation_source='panel')
    before = ownership_state()

    plan, report = apply(case, migration_input(case, target=target))

    root = require_project_folder(Project.objects.get(pk=report['project_id']))
    assert set(root.children.filter(name__in=['QA', 'Entregables']).values_list('pk', flat=True)) == {qa.pk, deliveries.pk}
    assert {row['name'] for row in plan['template_folders'] if row['action'] == 'create'} == {'new': {'Cuentas de cobro', 'Propuestas'}, 'existing': set()}[target]
    Project.objects.get(pk=report['project_id']).save()
    root.refresh_from_db()
    assert root.name == {'new': 'New target', 'existing': 'Existing target'}[target]
    assert root.parent_id is None
    assert root.is_archived is False
    undo = service.preview_undo_migration(report['migration_id'])
    service.undo_migration(report['migration_id'], undo['impact_hash'], 'Restaurar también la plantilla', 'undo-template-reuse', actor=case.actor)
    assert ownership_state() == before


@pytest.mark.parametrize(('strategy', 'child_name', 'code'), [
    ('adopt_source', 'Cuentas de cobro', 'template_name_conflict'),
    ('adopt_source', 'Propuestas', 'template_name_conflict'),
    ('move_contents', 'QA', 'duplicate_folder_name'),
])
def test_template_collisions_block_without_suffixing(migration_case, strategy, child_name, code):
    case = migration_case
    DocumentFolder.objects.create(name=child_name, parent=case.source, creation_source='panel')
    before = ownership_state()
    plan = assert_no_writes(service.preview_folder_migration, migration_input(case, strategy), actor=case.actor)

    with pytest.raises(service.FolderMigrationError) as error:
        service.apply_folder_migration(plan['plan_token'], 'No permitir duplicados', 'blocked', actor=case.actor)

    assert code in {row['code'] for row in error.value.details['blockers']}
    assert ownership_state() == before
    assert DocumentOwnershipOperation.objects.count() == 0


def test_non_disposable_existing_root_blocks_adoption(migration_case):
    case = migration_case
    root = require_project_folder(case.project)
    Document.objects.create(title='Existing business data', folder=root)
    plan = assert_no_writes(service.preview_folder_migration, migration_input(case, target='existing'), actor=case.actor)

    with pytest.raises(service.FolderMigrationError) as error:
        service.apply_folder_migration(plan['plan_token'], 'No perder información', 'blocked-existing', actor=case.actor)

    assert any(row.get('folder_id') == root.pk for row in error.value.details['blockers'])
    assert require_project_folder(case.project).pk == root.pk


@pytest.mark.parametrize('strategy', ['adopt_source', 'move_contents'])
def test_failure_after_ownership_rolls_back_creation(migration_case, monkeypatch, strategy):
    case = migration_case
    plan = service.preview_folder_migration(migration_input(case, strategy), actor=case.actor)
    before = ownership_state()
    count = Project.objects.count()
    audit_count = AccountingChangeLog.objects.count()

    def fail_postconditions(*args):
        raise RuntimeError('Injected postcondition failure')

    monkeypatch.setattr(service, '_check_postconditions', fail_postconditions)
    with pytest.raises(RuntimeError, match='Injected'):
        service.apply_folder_migration(plan['plan_token'], 'Atomicidad completa', 'rollback', actor=case.actor)

    assert ownership_state() == before
    assert Project.objects.count() == count
    assert AccountingChangeLog.objects.count() == audit_count
    assert DocumentOwnershipOperation.objects.count() == 0


def test_request_id_replays_original_report(migration_case):
    case = migration_case
    second = service.preview_folder_migration(migration_input(case, 'move_contents', target='existing'), actor=case.actor)
    plan, report = apply(case, migration_input(case))
    state = ownership_state()

    replay = service.apply_folder_migration(plan['plan_token'], 'Otro motivo no repite', 'migration', actor=case.actor)
    with pytest.raises(service.FolderMigrationError) as error:
        service.apply_folder_migration(second['plan_token'], 'Otro plan', 'migration', actor=case.actor)

    assert replay == report
    assert error.value.code == 'request_id_conflict'
    assert DocumentOwnershipOperation.objects.count() == 1
    assert ownership_state() == state


@pytest.mark.parametrize('invalid', ['expired', 'tampered'])
def test_invalid_token_preserves_tree(migration_case, invalid):
    case = migration_case
    with freeze_time('2026-10-10 12:00:00'):
        plan = service.preview_folder_migration(migration_input(case), actor=case.actor)
    token = {'expired': plan['plan_token'], 'tampered': plan['plan_token'] + 'x'}[invalid]
    before = ownership_state()

    with freeze_time('2026-10-10 12:30:01'), pytest.raises(service.FolderMigrationError) as error:
        service.apply_folder_migration(token, 'Rechazar intención inválida', 'invalid-token', actor=case.actor)

    assert error.value.code == 'plan_token_invalid'
    assert ownership_state() == before


def test_plan_token_is_bound_to_actor(migration_case):
    case = migration_case
    plan = service.preview_folder_migration(migration_input(case), actor=case.actor)

    with pytest.raises(PermissionDenied):
        service.apply_folder_migration(plan['plan_token'], 'Actor diferente', 'wrong-actor', actor=case.owner.user)

    assert not DocumentOwnershipOperation.objects.exists()
    assert signing.loads(plan['plan_token'], salt=service.TOKEN_SALT)['actor_id'] == case.actor.pk


def test_closed_serializer_rejects_invalid_filters(migration_case):
    case = migration_case
    with pytest.raises(ValidationError):
        service.preview_folder_migration(migration_input(case, include_document_ids=[]), actor=case.actor)
    with pytest.raises(ValidationError):
        service.preview_folder_migration(migration_input(case, 'move_contents', include_folder_ids=[require_project_folder(case.project).pk]), actor=case.actor)
    with pytest.raises(ValidationError) as error:
        service.preview_folder_migration(migration_input(case, typo=True), actor=case.actor)
    assert error.value.get_codes() == {'typo': ['unknown_field']}


def test_existing_project_without_root_adopts_source(migration_case):
    case = migration_case
    root = require_project_folder(case.project)
    root.children.all().delete()
    root.delete()
    before = ownership_state()

    _plan, report = apply(case, migration_input(case, target='existing'))

    assert report['root_folder_id'] == case.source.pk
    assert report['created_project_id'] is None
    preview = service.preview_undo_migration(report['migration_id'])
    service.undo_migration(report['migration_id'], preview['impact_hash'], 'Restaurar proyecto histórico', 'undo-no-root', actor=case.actor)
    assert ownership_state() == before
