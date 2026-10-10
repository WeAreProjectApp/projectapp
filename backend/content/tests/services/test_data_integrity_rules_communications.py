"""Communication findings, safe previews and reversible fixes (CM1-CM5)."""
from datetime import datetime, timedelta, timezone

import pytest
from secure_links.models import SecureLink

from content.models import (
    CommunicationFolder,
    CommunicationMessage,
    CommunicationThread,
)
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
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
NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


def found(rule_id, scope_kind='all', scope_id=None):
    return only(scan(scope_kind, scope_id, rule_ids=[rule_id]), rule_id)


def thread(profile, **values):
    return CommunicationThread.objects.create(client=profile, title='Consulta', **values)


def folder(profile, name='Contratos', **values):
    return CommunicationFolder.objects.create(client=profile, name=name, **values)


def secure_link(profile, project, token, **values):
    return SecureLink.objects.create(
        client=profile, project=project, title='Acceso de prueba', token_hash=token,
        expires_at=NOW + timedelta(days=7), origin='panel', **values,
    )


def blockers(finding, actor, **params):
    preview = engine.preview_fixes(resolve_scope('all'), [selection(finding, **params)], actor=actor)
    return [entry['code'] for entry in preview['steps'][0]['blockers']]


@pytest.fixture
def clients(make_client_profile):
    ana = make_client_profile(company='Ana SAS')
    beto = make_client_profile(company='Beto SAS')
    return ana, beto, make_project(ana, 'Tienda Ana'), make_project(beto, 'Tienda Beto')


def test_manual_thread_on_a_foreign_project_offers_its_clients_projects(clients):
    """Fails if a foreign project is missed or offered as a relink destination."""
    ana, _, own, foreign = clients
    misplaced = thread(ana, project=foreign)

    [finding] = found('CM1')

    assert finding.evidence == {'thread': misplaced.pk, 'project': foreign.pk, 'client': ana.pk}
    assert finding.fix_kinds == ('relink',)
    assert [option['value'] for option in finding.inputs['project']['options']] == ['none', own.pk]


def test_consistent_or_retained_thread_has_no_foreign_project_finding(clients, superuser):
    """Fails if a coherent or retained conversation is offered a relink."""
    ana, _, own, foreign = clients
    thread(ana, project=own)
    thread(ana)
    thread(ana, project=foreign, retention_context=make_retention_context(ana, superuser))

    assert found('CM1') == []


def test_relinking_a_thread_restores_its_original_context_on_undo(clients, admin_user):
    """Fails if undo misses the old project, the dropped folder or the previous editor."""
    ana, _, own, foreign = clients
    previous_folder = folder(ana, project=foreign)
    misplaced = thread(ana, project=foreign, folder=previous_folder)
    [finding] = found('CM1')

    _, result = apply(admin_user, [selection(finding, project=own.pk)])

    misplaced.refresh_from_db()
    assert (misplaced.project_id, misplaced.folder_id, misplaced.updated_by_id) == (own.pk, None, admin_user.pk)
    assert found('CM1') == []
    undo(admin_user, result['operation_id'])
    misplaced.refresh_from_db()
    assert (misplaced.project_id, misplaced.folder_id, misplaced.updated_by_id) == (foreign.pk, previous_folder.pk, None)


def test_closed_thread_relink_is_blocked_before_writing(clients, admin_user):
    """Fails if preview accepts a project edit that the closed-thread writer refuses."""
    ana, _, own, foreign = clients
    misplaced = thread(ana, project=foreign, status='closed')
    [finding] = found('CM1')

    assert blockers(finding, admin_user, project=own.pk) == ['thread_closed']
    misplaced.refresh_from_db()
    assert misplaced.project_id == foreign.pk


def test_managed_thread_with_a_foreign_client_is_report_only(clients):
    """Fails if a managed conversation is offered a manual relink."""
    ana, _, _, foreign = clients
    root = CommunicationThread.objects.get(managed_project=foreign)
    CommunicationThread.objects.filter(pk=root.pk).update(client=ana)

    [finding] = found('CM1')

    assert finding.subjects[0].pk == root.pk
    assert finding.fix_kinds == ('report_only',)


def test_thread_in_another_clients_folder_is_reported(clients):
    """Fails if a conversation filed under another client goes unreported."""
    ana, beto, _, _ = clients
    foreign_folder = folder(beto)
    misplaced = thread(ana, folder=foreign_folder)

    [finding] = found('CM2')

    assert finding.evidence == {'thread': misplaced.pk, 'folder': foreign_folder.pk}
    assert finding.fix_kinds == ('relink',)


def test_thread_in_its_own_context_has_no_folder_finding(clients):
    """Fails if a client-wide folder or a folder of the thread's project is flagged."""
    ana, _, own, _ = clients
    thread(ana, project=own, folder=folder(ana))
    thread(ana, project=own, folder=folder(ana, project=own))

    assert found('CM2') == []


def test_moving_a_closed_thread_to_root_can_be_undone(clients, admin_user):
    """Fails if a closed thread cannot move to root or undo misses its old folder."""
    ana, beto, own, _ = clients
    foreign_folder = folder(beto)
    misplaced = thread(ana, project=own, folder=foreign_folder, status='closed')
    [finding] = found('CM2')

    _, result = apply(admin_user, [selection(finding)])

    misplaced.refresh_from_db()
    assert misplaced.folder_id is None
    assert misplaced.status == 'closed'
    assert found('CM2') == []
    undo(admin_user, result['operation_id'])
    misplaced.refresh_from_db()
    assert (misplaced.folder_id, misplaced.updated_by_id) == (foreign_folder.pk, None)


def test_managed_thread_inside_a_folder_is_report_only(clients):
    """Fails if moving a managed root is offered as a manual correction."""
    ana, _, own, _ = clients
    root = CommunicationThread.objects.get(managed_project=own)
    misplaced_folder = folder(ana, project=own)
    CommunicationThread.objects.filter(pk=root.pk).update(folder=misplaced_folder)

    [finding] = found('CM2')

    assert finding.subjects[0].pk == root.pk
    assert finding.fix_kinds == ('report_only',)


def test_same_named_communication_siblings_form_one_group(clients):
    """Fails if accents or extra spaces hide sibling duplicates."""
    ana, _, _, _ = clients
    first = folder(ana, 'Revisión final')
    second = folder(ana, ' revision   FINAL ')

    [finding] = found('CM3')

    assert finding.evidence['folders'] == [first.pk, second.pk]
    assert finding.fix_kinds == ('rename',)


def test_folders_of_distinct_contexts_are_not_sibling_duplicates(clients):
    """Fails if equal names in different clients, projects or parents are grouped."""
    ana, beto, own, _ = clients
    parent = folder(ana, 'Padre')
    folder(ana)
    folder(beto)
    folder(ana, project=own)
    folder(ana, parent=parent)

    assert found('CM3') == []


def test_renaming_a_communication_sibling_can_restore_its_exact_old_name(clients, admin_user):
    """Fails if rename keeps the duplicate or undo normalizes the old padded name."""
    ana, _, _, _ = clients
    folder(ana)
    duplicate = folder(ana, ' contratos ')
    [finding] = found('CM3')

    _, result = apply(admin_user, [selection(finding, folder=duplicate.pk, name='Firmados')])

    duplicate.refresh_from_db()
    assert duplicate.name == 'Firmados'
    assert found('CM3') == []
    undo(admin_user, result['operation_id'])
    duplicate.refresh_from_db()
    assert duplicate.name == ' contratos '


def test_communication_folder_rename_refuses_a_normalized_collision(clients, admin_user):
    """Fails if preview accepts a name matching another sibling after normalization."""
    ana, _, _, _ = clients
    folder(ana)
    duplicate = folder(ana, ' contratos ')
    folder(ana, 'Revisión final')
    [finding] = found('CM3')

    assert blockers(finding, admin_user, folder=duplicate.pk, name='revision  FINAL') == ['name_collision']


def test_old_empty_manual_thread_is_reported(clients, monkeypatch):
    """Fails if an empty manual conversation older than thirty days is missed."""
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW)
    ana, _, _, _ = clients
    empty = thread(ana)
    CommunicationThread.objects.filter(pk=empty.pk).update(created_at=NOW - timedelta(days=31))

    [finding] = found('CM4')

    assert finding.evidence == {'thread': empty.pk}
    assert finding.fix_kinds == ('archive',)


def test_recent_nonempty_managed_or_archived_threads_are_not_stale(clients, monkeypatch):
    """Fails if the thirty-day boundary, messages, managed roots or archives are ignored."""
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW)
    ana, _, own, _ = clients
    boundary = thread(ana)
    nonempty = thread(ana)
    archived = thread(ana, is_archived=True)
    root = CommunicationThread.objects.get(managed_project=own)
    CommunicationThread.objects.filter(pk=boundary.pk).update(created_at=NOW - timedelta(days=30))
    CommunicationThread.objects.filter(pk__in=[nonempty.pk, archived.pk, root.pk]).update(
        created_at=NOW - timedelta(days=31))
    CommunicationMessage.objects.create(
        thread=nonempty, channel='whatsapp', direction='incoming', status='received',
        content='Consulta recibida', occurred_at=NOW,
    )

    assert found('CM4') == []


def test_archiving_an_empty_thread_restores_its_visibility_on_undo(clients, admin_user, monkeypatch):
    """Fails if archiving deletes the thread or undo misses visibility or the old editor."""
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW)
    ana, _, _, _ = clients
    empty = thread(ana)
    CommunicationThread.objects.filter(pk=empty.pk).update(created_at=NOW - timedelta(days=31))
    [finding] = found('CM4')

    _, result = apply(admin_user, [selection(finding)])

    empty.refresh_from_db()
    assert (empty.is_archived, empty.archived_at) == (True, NOW)
    assert found('CM4') == []
    undo(admin_user, result['operation_id'])
    empty.refresh_from_db()
    assert (empty.is_archived, empty.archived_at, empty.updated_by_id) == (False, None, None)


def test_secure_link_on_a_foreign_project_is_report_only(clients):
    """Fails if a secure link filed under another client's project is missed."""
    ana, _, _, foreign = clients
    link = secure_link(ana, foreign, 'foreign-link')

    [finding] = found('CM5')

    assert finding.evidence == {'link': link.pk, 'project': foreign.pk, 'client': ana.pk}
    assert finding.fix_kinds == ('report_only',)


def test_consistent_or_retained_secure_link_has_no_foreign_project_finding(clients, superuser):
    """Fails if a coherent, projectless or retained secure link is flagged."""
    ana, _, own, foreign = clients
    secure_link(ana, own, 'own-link')
    secure_link(ana, None, 'projectless-link')
    secure_link(ana, foreign, 'retained-link', retention_context=make_retention_context(ana, superuser))

    assert found('CM5') == []


def test_client_scope_includes_only_communication_findings_touching_that_client(clients, make_client_profile):
    """Fails if a client review misses its misplaced conversation or leaks it to a stranger."""
    ana, _, _, foreign = clients
    stranger = make_client_profile(company='Otra SAS')
    misplaced = thread(ana, project=foreign)

    [finding] = found('CM1', 'client', ana.pk)

    assert finding.evidence['thread'] == misplaced.pk
    assert finding.fingerprint == found('CM1')[0].fingerprint
    assert found('CM1', 'client', stranger.pk) == []


def test_communication_folder_rename_ignores_conserved_siblings(make_client_profile, superuser):
    """Fails if a conserved folder blocks a new live name outside the duplicate rule's population."""
    client = make_client_profile()
    folder(client)
    duplicate = folder(client, 'contratos')
    folder(client, 'Revisados', retention_context=make_retention_context(client, superuser))
    [finding] = found('CM3')

    _, result = apply(superuser, [selection(finding, folder=duplicate.pk, name='Revisados')])

    assert CommunicationFolder.objects.get(pk=duplicate.pk).name == 'Revisados'
    assert found('CM3') == []
    undo(superuser, result['operation_id'])
    assert CommunicationFolder.objects.get(pk=duplicate.pk).name == 'contratos'
