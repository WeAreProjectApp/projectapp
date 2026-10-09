"""Document rules: detection, fixes through the Panel's writers and exact undo (DC1-DC4, DC6, DC8)."""
import pytest

from content.models import AccountingChangeLog
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_documents_factories import (
    make_collection_account,
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

pytestmark = pytest.mark.django_db


def found(rule_id, scope_kind='all', scope_id=None):
    return only(scan(scope_kind, scope_id, rule_ids=[rule_id]), rule_id)


def blocker_codes(actor, finding, fix_kind=None, **params):
    impact = engine.preview_fixes(resolve_scope('all'), [selection(finding, fix_kind, **params)], actor=actor)
    return {entry['code'] for entry in impact['steps'][0]['blockers']}


def ledger_rows(document):
    return AccountingChangeLog.objects.filter(entity_type='document', object_id=document.pk).count()


@pytest.fixture
def clients(make_client_profile):
    ana = make_client_profile(company='Kore SAS', first_name='Ana')
    beto = make_client_profile(company='Tienda Beto', first_name='Beto')
    return {'ana': ana, 'beto': beto, 'kore': make_project(ana, 'Kore'), 'tienda': make_project(beto, 'Tienda')}


@pytest.fixture
def misfiled(clients):
    """Ana's document linked to Beto's project."""
    return make_document('Acta', client_user=clients['ana'].user, project=clients['tienda'])


@pytest.fixture
def unlinked(clients):
    """A document without client or project inside Kore's project folder."""
    return make_document('Brief', folder=project_root(clients['kore']))


@pytest.fixture
def twins():
    return make_folder('Contratos'), make_folder('contratos ')


# ── DC1 ──────────────────────────────────────────────────────────────────────

def test_document_on_another_clients_project_offers_only_its_own_clients_projects(clients, misfiled):
    """Fails if a document on a foreign project goes unreported or is offered another client's projects."""
    [finding] = found('DC1')

    assert finding.fix_kinds == ('relink',)
    assert finding.evidence == {'document': misfiled.pk, 'project': clients['tienda'].pk,
                                'client_user': clients['ana'].user_id}
    assert [option['value'] for option in finding.inputs['project']['options']] == ['none', clients['kore'].pk]


def test_collection_account_on_another_clients_project_is_only_reported(clients):
    """Fails if a collection account, which only Contabilidad relinks, is offered a fix here."""
    make_collection_account(client_user=clients['ana'].user, project=clients['tienda'])

    [finding] = found('DC1')

    assert finding.fix_kinds == ('report_only',)
    assert finding.inputs == {}


def test_relinking_moves_the_document_to_the_chosen_project_with_a_ledger_row(clients, misfiled, superuser):
    """Fails if the relink misses the chosen project, leaves the finding or skips the accounting ledger."""
    [finding] = found('DC1')

    apply(superuser, [selection(finding, project=clients['kore'].pk)])

    misfiled.refresh_from_db()
    assert misfiled.project_id == clients['kore'].pk
    assert found('DC1') == []
    assert ledger_rows(misfiled) == 1


def test_undoing_a_relink_restores_the_foreign_project_and_logs_the_reversal(clients, misfiled, superuser):
    """Fails if undo leaves the document unlinked or the ledger hides that the project came back."""
    [finding] = found('DC1')
    _, result = apply(superuser, [selection(finding, project='none')])

    undo(superuser, result['operation_id'])

    misfiled.refresh_from_db()
    assert misfiled.project_id == clients['tienda'].pk
    assert ledger_rows(misfiled) == 2


def test_dc1_is_reported_only_in_the_scope_of_the_project_it_points_at(clients, misfiled):
    """Fails if the scope leaks a document into an unrelated project's review or hides it from its own."""
    assert [finding.evidence['document'] for finding in found('DC1', 'project', clients['tienda'].pk)] == [misfiled.pk]
    assert found('DC1', 'project', clients['kore'].pk) == []


# ── DC2 ──────────────────────────────────────────────────────────────────────

def test_unlinked_document_in_a_linked_folder_is_reported(clients, unlinked):
    """Fails if a document missing the client and project its folder has goes unreported."""
    [finding] = found('DC2')

    assert finding.fix_kinds == ('sync_copy',)
    assert finding.evidence == {'document': unlinked.pk, 'folder': project_root(clients['kore']).pk,
                                'client_user': clients['ana'].user_id, 'project': clients['kore'].pk}


def test_copying_the_folder_association_sets_client_project_and_label(clients, unlinked, superuser):
    """Fails if the copy misses the folder's client or project, or leaves the label empty."""
    [finding] = found('DC2')

    apply(superuser, [selection(finding)])

    unlinked.refresh_from_db()
    assert (unlinked.client_user_id, unlinked.project_id, unlinked.client_name) == (
        clients['ana'].user_id, clients['kore'].pk, clients['ana'].user.get_full_name())
    assert found('DC2') == []


def test_undoing_the_copy_clears_client_project_and_label(unlinked, superuser):
    """Fails if undo keeps any of the three copied values."""
    [finding] = found('DC2')
    _, result = apply(superuser, [selection(finding)])

    undo(superuser, result['operation_id'])

    unlinked.refresh_from_db()
    assert (unlinked.client_user_id, unlinked.project_id, unlinked.client_name) == (None, None, '')


# ── DC3 ──────────────────────────────────────────────────────────────────────

def test_folder_on_another_clients_project_points_to_the_client_change_preview(clients):
    """Fails if a mixed folder goes unreported or the tool call does not target the project's client."""
    folder = make_folder('Diseños', client_user=clients['ana'].user, project=clients['tienda'])

    [finding] = found('DC3')

    assert finding.fix_kinds == ('existing_tool',)
    assert finding.tool == {'connector': 'documents', 'name': 'preview_folder_client_change',
                            'arguments': {'folder_id': folder.pk, 'query': {'client_profile_id': clients['beto'].pk}}}


def test_consistent_documents_and_folders_raise_no_association_finding(clients):
    """Fails if a document or folder that agrees with its project is flagged by DC1, DC2 or DC3."""
    root = project_root(clients['kore'])
    make_folder('Diseños', parent=root, client_user=clients['ana'].user, project=clients['kore'])
    make_document('Acta', folder=root, client_user=clients['ana'].user, project=clients['kore'])

    assert found('DC1') + found('DC2') + found('DC3') == []


# ── DC4 rename ───────────────────────────────────────────────────────────────

def test_renaming_one_twin_folder_resolves_the_duplicate_group(twins, superuser):
    """Fails if the rename does not reach the chosen folder, keeps the padding or leaves the group."""
    _, second = twins
    [finding] = found('DC4')

    apply(superuser, [selection(finding, 'rename', folder=second.pk, name='  Contratos firmados ')])

    second.refresh_from_db()
    assert second.name == 'Contratos firmados'
    assert found('DC4') == []


def test_undoing_a_folder_rename_restores_the_duplicate_name_exactly(twins, superuser):
    """Fails if undo is refused because the old name collides, or restores a normalized name."""
    _, second = twins
    [finding] = found('DC4')
    _, result = apply(superuser, [selection(finding, 'rename', folder=second.pk, name='Contratos firmados')])

    undo(superuser, result['operation_id'])

    second.refresh_from_db()
    assert second.name == 'contratos '
    assert len(found('DC4')) == 1


def test_renaming_into_a_name_that_still_collides_is_blocked(twins, superuser):
    """Fails if a rename that would keep the duplicate reaches the writer."""
    _, second = twins
    [finding] = found('DC4')

    assert blocker_codes(superuser, finding, 'rename', folder=second.pk, name='CONTRATOS') == {'name_collision'}


def test_rename_needs_a_folder_of_the_group_and_a_name(twins, superuser):
    """Fails if a folder outside the group or a blank name is accepted."""
    outsider = make_folder('Otra')
    [finding] = found('DC4')

    assert blocker_codes(superuser, finding, 'rename', folder=outsider.pk, name=' ') == {
        'invalid_input', 'input_required'}


def test_project_root_folder_is_not_renamed_from_the_document_manager(make_client_profile, superuser):
    """Fails if a project's root folder, whose name follows the project, can be renamed here."""
    make_project(make_client_profile(company='Uno'), 'Portal')
    second = make_project(make_client_profile(company='Dos'), 'Portal')
    [finding] = found('DC4')

    assert blocker_codes(superuser, finding, 'rename', folder=project_root(second).pk, name='Portal Dos') == {
        'managed_root'}


# ── DC6 ──────────────────────────────────────────────────────────────────────

def test_active_content_in_an_archived_folder_points_to_restoring_that_folder():
    """Fails if active rows hidden under an archived folder go unreported or the tool targets another folder."""
    archived = make_folder('Archivo 2024', is_archived=True)
    document = make_document('Factura vieja', folder=archived)
    child = make_folder('Facturas', parent=archived)

    [finding] = found('DC6')

    assert finding.evidence == {'ancestor': archived.pk, 'documents': [document.pk], 'folders': [child.pk]}
    assert finding.tool == {'connector': 'documents', 'name': 'unarchive_folder',
                            'arguments': {'folder_id': archived.pk}}


def test_archived_folder_with_archived_content_is_not_reported():
    """Fails if a consistently archived branch is flagged."""
    archived = make_folder('Archivo 2024', is_archived=True)
    make_document('Factura vieja', folder=archived, is_archived=True)
    make_folder('Facturas', parent=archived, is_archived=True)

    assert found('DC6') == []


# ── DC8 ──────────────────────────────────────────────────────────────────────

def test_document_thread_with_a_single_document_is_reported():
    """Fails if a thread that no longer joins two documents goes unreported."""
    document = make_document('Contrato')
    thread = make_document_thread([document])

    [finding] = found('DC8')

    assert finding.evidence == {'thread': thread.pk, 'documents': [document.pk], 'clients': []}
    assert finding.fix_kinds == ('report_only',)


def test_document_thread_mixing_two_clients_is_reported(clients):
    """Fails if a thread joining documents of different clients goes unreported."""
    make_document_thread([make_document('Contrato', client_user=clients['ana'].user),
                          make_document('Otrosí', client_user=clients['beto'].user)])

    [finding] = found('DC8')

    assert finding.evidence['clients'] == sorted([clients['ana'].user_id, clients['beto'].user_id])


def test_document_thread_of_one_client_is_not_reported(clients):
    """Fails if a healthy two-document thread of one client is flagged."""
    make_document_thread([make_document('Contrato', client_user=clients['ana'].user),
                          make_document('Otrosí', client_user=clients['ana'].user)])

    assert found('DC8') == []
