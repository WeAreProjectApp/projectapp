"""Folder merges (DC4): preconditions, the walk, the receipt and an exact undo through the engine."""
from datetime import datetime

import pytest
from accounts.models import UserProfile

from content.management.commands.audit_archive_integrity import _audit
from content.models import (
    AccountingChangeLog,
    ContractTemplate,
    DataIntegrityOperation,
    Document,
    DocumentFolder,
    EntityRevision,
    ProjectRetentionContext,
)
from content.services import document_folder_merge
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.services.entity_history import history_operation
from content.tests.data_integrity_helpers import apply, only, scan, selection, undo
from content.tests.data_integrity_merge_factories import (
    archived,
    make_document,
    make_folder,
    make_user,
    merge_state,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def twins():
    parent = make_folder('Clientes')
    survivor = make_folder('Facturas', parent=parent, order=1)
    duplicate = make_folder(' facturas', parent=parent, order=2)
    return parent, survivor, duplicate


def _merge(actor, survivor, duplicate):
    [finding] = only(scan(), 'DC4')
    return apply(actor, [selection(finding, 'merge_folders', survivor=survivor.pk, duplicate=duplicate.pk)])


def _preview(actor, survivor, duplicate):
    [finding] = only(scan(), 'DC4')
    chosen = [selection(finding, 'merge_folders', survivor=survivor.pk, duplicate=duplicate.pk)]
    return engine.preview_fixes(resolve_scope('all'), chosen, actor=actor)


def _codes(entries):
    return {entry['code'] for entry in entries}


def _row(model, pk):
    return model._base_manager.get(pk=pk)


def test_changed_folder_plan_is_refused_before_writing(twins, superuser):
    """Fails if the locked writer trusts a plan whose folder identity changed after preview."""
    _, survivor, duplicate = twins
    document = make_document('Factura 1', folder=duplicate)
    plan = document_folder_merge.plan_folder_merge(survivor, duplicate)
    DocumentFolder.objects.filter(pk=duplicate.pk).update(name='Otra identidad')

    with history_operation(actor=superuser, source='http'):
        with pytest.raises(document_folder_merge.FolderMergeError, match='estado cambió'):
            document_folder_merge.apply_folder_merge(plan, actor=superuser)

    assert _row(Document, document.pk).folder_id == duplicate.pk
    assert _row(DocumentFolder, duplicate.pk).is_archived is False


def test_merging_into_a_client_root_matches_the_reviewed_repair(superuser):
    """Fails if the repair case moves documents with new associations or leaves no revisions and receipt."""
    owner = make_user('folder-owner')
    UserProfile.objects.create(user=owner, role=UserProfile.ROLE_CLIENT)
    source = make_folder('Littigio', creation_source='unknown')
    target = make_folder('Littigio', managed_client=owner, client_user=owner)
    documents = [make_document(f'Documento {index}', folder=source) for index in range(3)]

    _, result = _merge(superuser, target, source)

    moved = Document.objects.filter(pk__in=[document.pk for document in documents])
    assert set(moved.values_list('folder_id', 'client_user_id', 'project_id')) == {(target.pk, None, None)}
    source = _row(DocumentFolder, source.pk)
    assert (source.is_archived, source.archived_via_folder_id) == (True, None)
    operation = DataIntegrityOperation.objects.get(pk=result['operation_id'])
    revisions = EntityRevision.objects.filter(operation_id=operation.history_operation_id,
                                              history__entity_type='document')
    assert revisions.count() == 3
    receipt = AccountingChangeLog.objects.get(entity_type='document_folder', object_id=source.pk)
    assert {'field': 'merged_into', 'old': '', 'new': target.pk} in receipt.changes
    assert receipt.actor == superuser


def test_merge_moves_active_content_in_order_and_leaves_archived_content_behind(twins, superuser):
    """Fails if moved children lose the deterministic order or archived content leaves the duplicate."""
    _, survivor, duplicate = twins
    make_folder('Existente', parent=survivor, order=4)
    beta = make_folder('Beta', parent=duplicate, order=0)
    alfa = make_folder('Alfa', parent=duplicate, order=0)
    active = make_document('Activo', folder=duplicate)
    old = make_document('Viejo', folder=duplicate, **archived())
    shelved = make_folder('Archivada', parent=duplicate, **archived())

    _merge(superuser, survivor, duplicate)

    assert [(row.pk, row.parent_id, row.order) for row in (_row(DocumentFolder, alfa.pk), _row(DocumentFolder, beta.pk))] \
        == [(alfa.pk, survivor.pk, 5), (beta.pk, survivor.pk, 6)]
    assert _row(Document, active.pk).folder_id == survivor.pk
    assert _row(Document, old.pk).folder_id == duplicate.pk
    assert _row(DocumentFolder, shelved.pk).parent_id == duplicate.pk
    audit = _audit()
    assert (audit['lost_documents'], audit['buried_folders']) == ([], [])


def test_same_named_children_merge_recursively_and_are_archived_once_empty(twins, superuser):
    """Fails if a child with a twin in the survivor is re-parented instead of merged into the twin."""
    _, survivor, duplicate = twins
    kept = make_folder('2026', parent=survivor)
    nested = make_folder('2026 ', parent=duplicate)
    deep = make_document('Enero', folder=nested)

    _merge(superuser, survivor, duplicate)

    assert _row(Document, deep.pk).folder_id == kept.pk
    nested = _row(DocumentFolder, nested.pk)
    assert (nested.parent_id, nested.is_archived, nested.archived_via_folder_id) == (duplicate.pk, True, None)
    assert _row(DocumentFolder, duplicate.pk).is_archived is True


def test_accented_folder_names_merge_with_an_exact_undo(superuser):
    """DC4 and the recursive walk use the same accent, case, punctuation and space normalization."""
    parent = make_folder('Raíz')
    survivor = make_folder('Revisión final', parent=parent)
    duplicate = make_folder('revision  FINAL', parent=parent)
    kept = make_folder('Anexos: revisión', parent=survivor)
    child = make_folder('anexos  REVISION', parent=duplicate)
    direct = make_document('Revisión', folder=duplicate)
    nested = make_document('Anexo', folder=child)
    [finding] = only(scan(rule_ids=['DC4']), 'DC4')
    assert {subject.pk for subject in finding.subjects} == {survivor.pk, duplicate.pk}
    plan = document_folder_merge.plan_folder_merge(survivor, duplicate)
    before = merge_state(plan['closure'])

    _, result = apply(superuser, [selection(finding, 'merge_folders',
                                           survivor=survivor.pk, duplicate=duplicate.pk)])

    assert _row(Document, direct.pk).folder_id == survivor.pk
    assert _row(Document, nested.pk).folder_id == kept.pk
    assert _row(DocumentFolder, child.pk).is_archived is True
    assert _row(DocumentFolder, duplicate.pk).is_archived is True
    undo(superuser, result['operation_id'])
    assert merge_state(plan['closure']) == before


def test_undo_puts_every_folder_and_document_back(twins, superuser):
    """Fails if undoing a merge leaves any folder, order or document away from where it was."""
    _, survivor, duplicate = twins
    make_folder('2026', parent=survivor)
    child = make_folder('Alfa', parent=duplicate, order=3)
    nested = make_folder('2026', parent=duplicate)
    documents = [make_document('Uno', folder=duplicate), make_document('Dos', folder=nested)]
    folders = [duplicate.pk, child.pk, nested.pk]

    def state():
        return (list(DocumentFolder.objects.filter(pk__in=folders).order_by('pk')
                     .values_list('parent_id', 'order', 'is_archived', 'archived_at')),
                list(Document.objects.filter(pk__in=[row.pk for row in documents]).order_by('pk')
                     .values_list('folder_id', flat=True)))

    before = state()
    _, result = _merge(superuser, survivor, duplicate)

    undo(superuser, result['operation_id'])

    assert state() == before
    assert len(only(scan(), 'DC4')) == 1


@pytest.mark.parametrize(('change', 'code'), [('document_moved', 'changed_since'), ('parent_archived', 'parent_archived')])
def test_undo_is_blocked_when_the_merged_content_changed_since(twins, superuser, change, code):
    """Fails if an undo would overwrite a later move or restore the duplicate under an archived parent."""
    parent, survivor, duplicate = twins
    document = make_document('Uno', folder=duplicate)
    _, result = _merge(superuser, survivor, duplicate)
    changes = {
        'document_moved': lambda: Document.objects.filter(pk=document.pk).update(folder=make_folder('Otra')),
        'parent_archived': lambda: DocumentFolder.objects.filter(pk=parent.pk).update(
            is_archived=True, archived_at=datetime.fromisoformat('2026-10-09T10:00:00+00:00')),
    }
    changes[change]()

    preview = engine.preview_undo(result['operation_id'])

    assert code in _codes(preview['blockers'])
    assert all(row.get('rule_id') == 'DC4' for row in preview['blockers'] if row['code'] == 'parent_archived')


def test_only_an_active_superuser_can_merge_folders(twins, admin_user):
    """Fails if a staff user who is not a superuser gets an applicable folder merge."""
    _, survivor, duplicate = twins

    preview = _preview(admin_user, survivor, duplicate)

    assert 'actor_not_superuser' in _codes(preview['steps'][0]['blockers'])


def test_merge_limits_refuse_oversized_plans(twins, superuser, monkeypatch):
    """Fails if either the document-movement cap or the closure cap can be exceeded."""
    _, survivor, duplicate = twins
    monkeypatch.setattr(document_folder_merge, 'MAX_DOCUMENTS', 1)
    make_document('Uno', folder=duplicate)
    make_document('Dos', folder=duplicate)

    document_preview = _preview(superuser, survivor, duplicate)

    assert 'merge_too_large' in _codes(document_preview['steps'][0]['blockers'])

    monkeypatch.setattr(document_folder_merge, 'MAX_DOCUMENTS', 200)
    monkeypatch.setattr(document_folder_merge, 'MAX_ITEMS', 3)
    closure_preview = _preview(superuser, survivor, duplicate)

    assert 'merge_too_large' in _codes(closure_preview['steps'][0]['blockers'])


# ── Each blocker, on the service plan ────────────────────────────────────────

def _pair(name='Facturas', **survivor_values):
    parent = make_folder('Raíz')
    return make_folder(name, parent=parent, **survivor_values), make_folder(name, parent=parent)


def _mismatch():
    return make_folder('Facturas'), make_folder('Cobros', parent=make_folder('Otra'))


def _archived():
    return _pair(**archived())


def _system():
    return _pair(system_key='generated:test')


def _wrong_kind():
    owner = make_user('root-owner')
    return make_folder('Ana'), make_folder('Ana', managed_client=owner, client_user=owner)


def _scope():
    survivor, duplicate = _pair(client_user=make_user('cliente-a'))
    make_document('Ajeno', folder=duplicate, client_user=make_user('cliente-b'))
    return survivor, duplicate


def _retained():
    survivor, duplicate = _pair()
    owner = make_user('retained-owner')
    context = ProjectRetentionContext.objects.create(client=owner, original_project_id=987654, project_name='Viejo',
                                                     created_by=owner)
    make_document('Conservado', folder=duplicate, retention_context=context)
    return survivor, duplicate


def _mirror():
    survivor, duplicate = _pair()
    ContractTemplate.objects.create(name='Contrato', content_markdown='# Contrato',
                                    mirror_document=make_document('Contrato', folder=duplicate))
    return survivor, duplicate


def _not_movable():
    survivor, duplicate = _pair()
    make_document('PDF generado', folder=duplicate, generated_file='documents/generated/propuesta.pdf')
    return survivor, duplicate


def _ambiguous():
    survivor, duplicate = _pair()
    make_folder('Anexos', parent=survivor)
    make_folder('anexos ', parent=survivor)
    make_folder('Anexos', parent=duplicate)
    return survivor, duplicate


def _collision():
    survivor, duplicate = _pair()
    make_folder('Anexos', parent=survivor, client_user=make_user('cliente-c'))
    make_folder('Anexos', parent=duplicate, client_user=make_user('cliente-d'))
    return survivor, duplicate


def _anomaly():
    survivor, duplicate = _pair()
    make_document('Procedencia', folder=duplicate, archived_via_folder=make_folder('Causa'))
    return survivor, duplicate


@pytest.mark.parametrize(('build', 'codes'), [
    (_mismatch, {'name_mismatch', 'not_siblings'}), (_archived, {'folder_archived'}),
    (_system, {'system_managed'}), (_wrong_kind, {'wrong_kind'}), (_scope, {'scope_mismatch'}),
    (_retained, {'retained_rows'}), (_mirror, {'contract_mirror'}), (_not_movable, {'document_not_movable'}),
    (_ambiguous, {'ambiguous_survivor_child'}), (_collision, {'unmergeable_child_collision'}),
    (_anomaly, {'tree_anomaly'}),
])
def test_unsafe_merges_are_blocked_with_their_reason(build, codes):
    """Fails if a folder merge that would lose, misplace or corrupt data is planned without its blocker."""
    survivor, duplicate = build()

    plan = document_folder_merge.plan_folder_merge(survivor, duplicate)

    assert codes <= _codes(plan['blockers'])
