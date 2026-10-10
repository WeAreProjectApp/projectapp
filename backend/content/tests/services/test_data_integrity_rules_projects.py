"""Project rules PJ1-PJ6: detection, fixes through the domain writers and exact undo."""
import pytest
from accounts.models import Project

from content.models import (
    AccountingChangeLog,
    CommunicationThread,
    DocumentFolder,
    IncomeRecord,
)
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.services.document_type_utils import get_collection_account_document_type
from content.tests.data_integrity_helpers import (
    apply,
    make_phase,
    make_project,
    make_proposal,
    scan,
    selection,
    undo,
)
from content.tests.data_integrity_projects_factories import (
    drop_roots,
    make_document,
    make_hosting,
    make_retention_context,
    set_state,
)

pytestmark = pytest.mark.django_db

INCOME, HOSTING, DOCUMENT = 'content.incomerecord', 'content.hostingrecord', 'content.document'
ASSIGN_TOOL = 'assign_project_unlinked_records'


def _found(rule_id, scope_kind='all', scope_id=None):
    return scan(scope_kind, scope_id, rule_ids=[rule_id])


def _blocker_codes(finding, actor, **params):
    preview = engine.preview_fixes(resolve_scope('all'), [selection(finding, **params)], actor=actor)
    return [entry['code'] for entry in preview['steps'][0]['blockers']]


def _names(project):
    project.refresh_from_db()
    return (project.name, DocumentFolder.objects.get(managed_project=project).name,
            CommunicationThread.objects.get(managed_project=project).title)


# ── PJ1 · records with a client and no project ───────────────────────────────

def test_loose_income_hosting_and_document_offer_a_relink_to_the_only_active_project(
        make_client_profile, make_income):
    """Fails if a record with a client and no project goes unreported or misses its single-project suggestion."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    income = make_income(client=profile)
    hosting = make_hosting(profile)
    document = make_document(profile.user)

    findings = {finding.evidence['model']: finding for finding in _found('PJ1')}

    assert {label: finding.evidence['id'] for label, finding in findings.items()} == {
        INCOME: income.pk, HOSTING: hosting.pk, DOCUMENT: document.pk}
    assert findings[INCOME].evidence['client_user'] == profile.user_id
    assert [finding.fix_kinds for finding in findings.values()] == [('relink',)] * 3
    assert [finding.suggestion for finding in findings.values()] == [{'project': project.pk}] * 3


def test_linked_retained_archived_and_cascaded_records_are_not_reported(make_client_profile, make_income, superuser):
    """Fails if PJ1 flags a linked, retained or archived record, or a liquid child its parent's relink carries."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    make_income(client=profile, project=project, concept='Con proyecto')
    make_income(client=profile, concept='Conservado', retention_context=make_retention_context(profile, superuser))
    make_document(profile.user, is_archived=True)
    parent = make_income(client=profile, concept='Fase 1')
    make_income(client=profile, concept='Fase 1 (pago)', kind=IncomeRecord.Kind.LIQUID, expected_income=parent)

    assert [finding.evidence['id'] for finding in _found('PJ1')] == [parent.pk]


def test_loose_collection_account_is_sent_to_the_assign_tool(make_client_profile):
    """Fails if a cuenta de cobro is offered the engine relink, which would skip refiling it in its folder."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    cuenta = make_document(profile.user, title='Cuenta PA-001', commercial_status='issued',
                           document_type=get_collection_account_document_type())

    [finding] = _found('PJ1')

    assert finding.fix_kinds == ('existing_tool',)
    assert finding.tool == {'connector': 'projects', 'name': ASSIGN_TOOL,
                            'arguments': {'project_id': project.pk, 'document_ids': [cuenta.pk]}}


def test_relinking_an_income_is_audited_and_undo_leaves_it_loose_again(make_client_profile, make_income, superuser):
    """Fails if the relink skips the accounting writer's audit row or the undo does not clear the project."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    income = make_income(client=profile)
    [finding] = _found('PJ1')

    _, result = apply(superuser, [selection(finding, project=project.pk)])

    income.refresh_from_db()
    assert income.project_id == project.pk
    assert AccountingChangeLog.objects.filter(
        entity_type=AccountingChangeLog.EntityType.INCOME, object_id=income.pk).count() == 1
    assert _found('PJ1') == []
    undo(superuser, result['operation_id'])
    income.refresh_from_db()
    assert income.project_id is None


def test_relinking_a_plain_document_sets_its_project_and_undo_restores_it(make_client_profile, superuser):
    """Fails if a loose document is not linked through the documents writer or stays linked after the undo."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    document = make_document(profile.user)
    [finding] = _found('PJ1')

    _, result = apply(superuser, [selection(finding, project=project.pk)])

    document.refresh_from_db()
    assert document.project_id == project.pk
    undo(superuser, result['operation_id'])
    document.refresh_from_db()
    assert document.project_id is None


def test_relink_is_blocked_for_a_closed_project_another_clients_project_or_no_choice(
        make_client_profile, make_income, superuser):
    """Fails if the relink would file a record under a closed project, someone else's project, or none at all."""
    profile = make_client_profile(company='Kore SAS')
    make_project(profile, 'Kore')
    closed = set_state(make_project(profile, 'Kore viejo'), 'completed')
    foreign = make_project(make_client_profile(company='Otra'), 'Ajeno')
    make_income(client=profile)
    [finding] = _found('PJ1')

    assert _blocker_codes(finding, superuser, project=closed.pk) == ['terminal_project']
    assert _blocker_codes(finding, superuser, project=foreign.pk) == ['invalid_input']
    assert _blocker_codes(finding, superuser) == ['input_required']


def test_project_scope_lists_its_clients_loose_records_only(make_client_profile, make_income):
    """Fails if a project-scoped scan misses its client's loose records or shows another client's."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    income = make_income(client=profile)
    make_income(client=make_client_profile(company='Otra'), concept='Ajeno')

    assert [finding.evidence['id'] for finding in _found('PJ1', 'project', project.pk)] == [income.pk]


# ── PJ2 · retained rows with a project again ─────────────────────────────────

def test_retained_row_pointing_at_a_project_again_is_reported(make_client_profile, make_income, superuser):
    """Fails if a retained income that regained a project goes unreported, or a merely retained one is flagged."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    context = make_retention_context(profile, superuser)
    relinked = make_income(client=profile, project=project, retention_context=context)
    make_income(client=profile, concept='Sólo conservado', retention_context=context)

    [finding] = _found('PJ2')

    assert finding.evidence == {'model': INCOME, 'id': relinked.pk, 'context': context.pk,
                                'projects': {'project': project.pk}}
    assert [subject.key() for subject in finding.subjects] == [(INCOME, relinked.pk), ('accounts.project', project.pk)]
    assert finding.fix_kinds == ('report_only',)


# ── PJ3 · retained rows a live project can adopt ─────────────────────────────

def test_retained_rows_of_a_client_with_an_active_project_point_to_the_assign_tool(
        make_client_profile, make_income, superuser):
    """Fails if retained records the client's live project can adopt are not sent to the assign tool."""
    profile = make_client_profile(company='Kore SAS')
    target = make_project(profile, 'Kore')
    context = make_retention_context(profile, superuser)
    income = make_income(client=profile, retention_context=context)
    DocumentFolder.objects.create(name='Kore anterior', client_user=profile.user, retention_context=context)

    [finding] = _found('PJ3')

    assert finding.evidence == {'context': context.pk, 'project': target.pk, 'records': {INCOME: [income.pk]}}
    assert finding.tool == {'connector': 'projects', 'name': ASSIGN_TOOL,
                            'arguments': {'project_id': target.pk, 'income_ids': [income.pk]}}
    assert finding.fix_kinds == ('existing_tool',)
    assert 'carpeta conservada' in finding.message


def test_retained_rows_wait_while_their_client_has_no_active_project(make_client_profile, make_income, superuser):
    """Fails if PJ3 proposes adopting into a closed project, which the assign flow refuses."""
    profile = make_client_profile(company='Kore SAS')
    set_state(make_project(profile, 'Kore'), 'completed')
    make_income(client=profile, retention_context=make_retention_context(profile, superuser))
    other = make_client_profile(company='Otra')
    live = make_project(other, 'Otra')
    make_income(client=other, retention_context=make_retention_context(other, superuser, 'Otra anterior', 9002))

    assert [finding.evidence['project'] for finding in _found('PJ3')] == [live.pk]


# ── PJ4 · same-named projects ────────────────────────────────────────────────

def test_same_named_projects_of_one_client_form_a_rename_group(make_client_profile):
    """Fails if a client's projects named alike go unreported, or homonyms of different clients are grouped."""
    profile = make_client_profile(company='Kore SAS')
    first = make_project(profile, 'Kore')
    second = make_project(profile, 'KORE!')
    make_project(make_client_profile(company='Otra'), 'Kore')

    [finding] = _found('PJ4')

    assert finding.evidence == {'client': profile.user_id, 'key': 'kore', 'projects': [first.pk, second.pk]}
    assert [option['value'] for option in finding.inputs['project']['options']] == [first.pk, second.pk]
    assert finding.inputs['name']['required'] is True
    assert finding.fix_kinds == ('rename',)


def test_renaming_a_duplicate_renames_its_roots_and_undo_restores_every_name(make_client_profile, superuser):
    """Fails if the rename leaves the managed root folder or thread behind, or the undo misses one of them."""
    profile = make_client_profile(company='Kore SAS')
    make_project(profile, 'Kore')
    second = make_project(profile, 'KORE')
    [finding] = _found('PJ4')

    _, result = apply(superuser, [selection(finding, project=second.pk, name='  Kore   Web ')])

    assert _names(second) == ('Kore Web', 'Kore Web', 'Kore Web')
    assert _found('PJ4') == []
    undo(superuser, result['operation_id'])
    assert _names(second) == ('KORE', 'KORE', 'KORE')


def test_rename_is_blocked_while_the_new_name_still_reads_the_same(make_client_profile, superuser):
    """Fails if a rename that only changes case or punctuation, or names nothing, is accepted."""
    profile = make_client_profile(company='Kore SAS')
    make_project(profile, 'Kore')
    second = make_project(profile, 'KORE')
    [finding] = _found('PJ4')

    assert _blocker_codes(finding, superuser, project=second.pk, name='kore.') == ['invalid_input']
    assert _blocker_codes(finding, superuser, project=second.pk) == ['input_required']


# ── PJ5 · missing managed roots ──────────────────────────────────────────────

def test_project_missing_its_managed_roots_is_reported_and_a_provisioned_one_is_not(make_client_profile):
    """Fails if a project without its managed root folder and thread goes unreported, or a healthy one is flagged."""
    profile = make_client_profile(company='Kore SAS')
    make_project(profile, 'Kore')
    historical = make_project(profile, 'Vastago')
    drop_roots(historical)

    [finding] = _found('PJ5')

    assert finding.evidence == {'project': historical.pk, 'missing': ['folder', 'thread']}
    assert finding.fix_kinds == ('report_only',)
    assert 'reconstruyen las carpetas' in finding.message


# ── PJ6 · legacy status mirror ───────────────────────────────────────────────

def test_project_whose_legacy_status_disagrees_with_its_state_is_reported(make_client_profile):
    """Fails if a stale legacy status goes unreported, or a project whose mirror matches is flagged."""
    profile = make_client_profile(company='Kore SAS')
    make_project(profile, 'Kore')
    drifted = make_project(profile, 'Vastago')
    Project.objects.filter(pk=drifted.pk).update(status=Project.STATUS_ACTIVE)

    [finding] = _found('PJ6')

    assert finding.evidence == {'project': drifted.pk, 'state': drifted.current_state_id,
                                'effect': 'development', 'status': Project.STATUS_ACTIVE}
    assert finding.fix_kinds == ('sync_copy',)


def test_syncing_the_status_mirror_writes_the_expected_value_and_undo_restores_the_stale_one(
        make_client_profile, superuser):
    """Fails if the sync does not copy the state's legacy status or the undo does not bring the old one back."""
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    Project.objects.filter(pk=project.pk).update(status=Project.STATUS_SUSPENDED)
    [finding] = _found('PJ6')

    impact, result = apply(superuser, [selection(finding)])

    project.refresh_from_db()
    assert impact['steps'][0]['changes'][0]['before'] == 'Suspendido'
    assert impact['steps'][0]['changes'][0]['after'] == 'En desarrollo'
    assert project.status == Project.STATUS_DEVELOPMENT
    assert _found('PJ6') == []
    undo(superuser, result['operation_id'])
    project.refresh_from_db()
    assert project.status == Project.STATUS_SUSPENDED


def test_phases_with_gaps_or_repeated_orders_are_reported(make_client_profile):
    """Fails if a project's phases are not checked against consecutive positions starting at one."""
    client = make_client_profile()
    project = make_project(client)
    first = make_phase(project, make_proposal(client), 2)
    second = make_phase(project, make_proposal(client), 2)

    [finding] = _found('PJ7')

    assert finding.evidence == {'project': project.pk, 'orders': [[first.pk, 2], [second.pk, 2]]}
    assert finding.fix_kinds == ('reorder',)


def test_consecutive_phase_positions_have_no_order_finding(make_client_profile):
    """Fails if phases already numbered one through their count are flagged."""
    client = make_client_profile()
    project = make_project(client)
    make_phase(project, make_proposal(client), 1)
    make_phase(project, make_proposal(client), 2)

    assert _found('PJ7') == []


def test_reordering_phases_restores_the_old_positions_on_undo(make_client_profile, superuser):
    """Fails if reorder loses phase links or undo fails to restore the original duplicate positions."""
    client = make_client_profile()
    project = make_project(client)
    first = make_phase(project, make_proposal(client), 2)
    second = make_phase(project, make_proposal(client), 2)
    [finding] = _found('PJ7')

    _, result = apply(superuser, [selection(finding)])

    assert list(project.phases.order_by('pk').values_list('pk', 'order')) == [(first.pk, 1), (second.pk, 2)]
    assert _found('PJ7') == []
    undo(superuser, result['operation_id'])
    assert list(project.phases.order_by('pk').values_list('pk', 'order')) == [(first.pk, 2), (second.pk, 2)]


def test_phase_reorder_refuses_retained_phases_still_linked_to_the_project(make_client_profile, superuser):
    """Fails if a retained phase causes a writer exception instead of a read-only preview blocker."""
    client = make_client_profile()
    project = make_project(client)
    make_phase(project, make_proposal(client), 3)
    retained = make_phase(project, make_proposal(client), 4)
    type(retained).objects.filter(pk=retained.pk).update(retention_context=make_retention_context(client, superuser))
    [finding] = _found('PJ7')

    assert _blocker_codes(finding, superuser) == ['retained_read_only']
