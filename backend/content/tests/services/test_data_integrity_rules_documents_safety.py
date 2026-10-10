"""Document boundary cases: normalized siblings, derived ownership and retained data."""
import pytest

from content.models import DocumentFolder
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.services.project_deletion_service import delete_empty_project
from content.tests.data_integrity_documents_factories import (
    make_document,
    make_document_thread,
    make_folder,
    project_root,
)
from content.tests.data_integrity_helpers import (
    apply,
    make_project,
    only,
    scan,
    selection,
    undo,
)
from content.tests.data_integrity_projects_factories import make_retention_context

pytestmark = pytest.mark.django_db


def found(rule_id, scope_kind='all', scope_id=None):
    return only(scan(scope_kind, scope_id, rule_ids=[rule_id]), rule_id)


def test_accent_and_space_variants_are_duplicate_document_siblings():
    """Fails if document folder duplicates use a different normalizer from the rest of the catalog."""
    parent = make_folder('Clientes')
    first = make_folder('Revisión final', parent=parent)
    second = make_folder(' revision  FINAL ', parent=parent)

    [finding] = found('DC4')

    assert finding.evidence == {'parent': parent.pk, 'key': 'revision final', 'folders': [first.pk, second.pk]}


def test_folders_under_different_parents_are_not_duplicate_siblings():
    """Fails if folders sharing a name but not a parent are grouped."""
    make_folder('Revisión', parent=make_folder('Uno'))
    make_folder('revision', parent=make_folder('Dos'))

    assert found('DC4') == []


def test_document_scope_preserves_the_complete_duplicate_folder_group():
    """Fails if a document review hides the sibling outside its own ancestor chain."""
    parent = make_folder('Clientes')
    first = make_folder('Contratos', parent=parent)
    second = make_folder(' contratos ', parent=parent)
    document = make_document('Contrato', folder=second)

    [finding] = found('DC4', 'document', document.pk)

    assert finding.evidence['folders'] == [first.pk, second.pk]
    assert finding.fingerprint == found('DC4')[0].fingerprint


def test_folder_rename_can_restore_a_client_derived_from_its_project(make_client_profile, superuser):
    """Fails if undo leaves the client the folder serializer filled while renaming."""
    client = make_client_profile()
    project = make_project(client)
    parent = project_root(project)
    make_folder('Contratos', parent=parent)
    duplicate = make_folder(' contratos ', parent=parent, project=project)
    DocumentFolder.objects.filter(pk=duplicate.pk).update(client_user=None)
    [finding] = found('DC4')

    _, result = apply(superuser, [selection(finding, 'rename', folder=duplicate.pk, name='Firmados')])

    duplicate.refresh_from_db()
    assert (duplicate.name, duplicate.client_user_id) == ('Firmados', client.user_id)
    undo(superuser, result['operation_id'])
    duplicate.refresh_from_db()
    assert (duplicate.name, duplicate.client_user_id) == (' contratos ', None)


def test_copying_a_project_only_folder_preserves_a_manual_document_label(make_client_profile, admin_user):
    """Fails if the association copy drops an existing document label or undo misses the old editor."""
    client = make_client_profile()
    project = make_project(client)
    parent = make_folder('Entregas', project=project)
    DocumentFolder.objects.filter(pk=parent.pk).update(client_user=None)
    document = make_document('Acta', folder=parent, client_name='Etiqueta histórica')
    [finding] = found('DC2')

    _, result = apply(admin_user, [selection(finding)])

    document.refresh_from_db()
    assert (document.client_user_id, document.project_id, document.client_name) == (
        client.user_id, project.pk, 'Etiqueta histórica')
    undo(admin_user, result['operation_id'])
    document.refresh_from_db()
    assert (document.client_user_id, document.project_id, document.client_name, document.updated_by_id) == (
        None, None, 'Etiqueta histórica', None)


def test_generated_document_mismatch_has_no_relink_option(make_client_profile):
    """Fails if a generated proposal file is offered a document relink."""
    client = make_client_profile()
    foreign = make_project(make_client_profile(), 'Ajeno')
    generated = make_document('Propuesta generada', client_user=client.user, project=foreign,
                              generated_file='documents/generated/test.pdf')

    [finding] = found('DC1')

    assert finding.evidence['document'] == generated.pk
    assert finding.fix_kinds == ('report_only',)


def test_retained_documents_do_not_produce_live_association_findings(make_client_profile, superuser):
    """Fails if retained documents are offered live relinks or folder association copies."""
    client = make_client_profile()
    foreign = make_project(make_client_profile(), 'Ajeno')
    context = make_retention_context(client, superuser)
    make_document('Conservado', client_user=client.user, project=foreign, retention_context=context)
    make_document('Sin asociación', folder=project_root(foreign), retention_context=context)

    assert found('DC1') + found('DC2') == []


def test_active_document_below_an_archived_ancestor_is_visible_to_its_scope():
    """Fails if only the direct folder is checked for archival or a document scope misses the ancestor."""
    archived = make_folder('Archivado', is_archived=True)
    intermediate = make_folder('Activo', parent=archived)
    document = make_document('Acta', folder=intermediate)

    [finding] = found('DC6', 'document', document.pk)

    assert finding.evidence['ancestor'] == archived.pk
    assert document.pk in finding.evidence['documents']


def test_client_root_duplicate_is_blocked_before_the_folder_rename(make_client_profile, superuser):
    """Fails if a managed client root can be renamed outside the client merge."""
    client = make_client_profile()
    managed = make_folder('Cliente', client_user=client.user, managed_client=client.user)
    make_folder('cliente')
    [finding] = found('DC4')

    impact = engine.preview_fixes(resolve_scope('all'), [selection(finding, 'rename', folder=managed.pk, name='Otro')],
                                  actor=superuser)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['managed_read_only']


def test_folder_rename_restores_a_missing_slug_on_undo(superuser):
    """Fails if a legacy slug generated during rename is missing from the undo snapshot."""
    make_folder('Contratos')
    duplicate = make_folder('contratos')
    DocumentFolder.objects.filter(pk=duplicate.pk).update(slug='')
    [finding] = found('DC4')

    _, result = apply(superuser, [selection(finding, 'rename', folder=duplicate.pk, name='Firmados')])

    assert DocumentFolder.objects.get(pk=duplicate.pk).slug == 'firmados'
    undo(superuser, result['operation_id'])
    assert DocumentFolder.objects.get(pk=duplicate.pk).slug == ''


def test_document_thread_with_retained_history_has_no_live_consistency_finding(make_client_profile, superuser):
    """Fails if a document thread's conserved history is reviewed as a live mixed-client group."""
    client = make_client_profile()
    retained = make_document('Conservado', client_user=client.user,
                             retention_context=make_retention_context(client, superuser))
    live = make_document('Vigente', client_user=make_client_profile().user)
    make_document_thread([retained, live])

    assert found('DC8') == []


def test_removed_original_project_blocks_document_relink_undo(make_client_profile, superuser):
    """Fails if undo is offered when the document's original project no longer exists."""
    client = make_client_profile()
    original = make_project(make_client_profile(), 'Ajeno')
    make_document('Acta', client_user=client.user, project=original)
    [finding] = found('DC1', 'client', client.pk)
    _, result = apply(superuser, [selection(finding, project='none')])
    delete_empty_project(original.pk, actor=superuser)

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']
