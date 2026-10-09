"""NM1 fixes: the clean value goes through the Panel writers and undo restores the exact old text."""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth.models import User

from content.models import (
    BusinessProposal,
    CommunicationFolder,
    CommunicationThread,
    DataIntegrityOperation,
    Document,
    DocumentFolder,
)
from content.models.web_app_diagnostic import WebAppDiagnostic
from content.services import diagnostic_service
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_helpers import (
    apply,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
    undo,
)
from content.tests.data_integrity_projects_factories import make_retention_context

pytestmark = pytest.mark.django_db


def nm1_finding(model, pk, field=None):
    [finding] = [item for item in only(scan(rule_ids=['NM1']), 'NM1')
                 if (item.evidence['model'], item.evidence['pk']) == (model, pk)
                 and field in (None, item.evidence['field'])]
    return finding


def fix(actor, finding):
    _, result = apply(actor, [selection(finding)])
    return result['operation_id']


def recorded(operation_id):
    """(model, pk, field) of every non-guard value the operation changed."""
    [step] = DataIntegrityOperation.objects.get(pk=operation_id).steps
    return {(item['model'], item['pk'], item['field']) for item in step['items'] if not item['guard']}


def test_document_title_cleanup_restores_a_missing_slug_on_undo(superuser):
    """Fails if generating a legacy document slug during title cleanup makes undo incomplete."""
    document = Document.objects.create(title=' Acta  final ')
    Document.objects.filter(pk=document.pk).update(slug='')

    operation_id = fix(superuser, nm1_finding('content.document', document.pk, 'title'))

    assert Document.objects.get(pk=document.pk).slug == 'acta-final'
    undo(superuser, operation_id)
    assert (Document.objects.get(pk=document.pk).title, Document.objects.get(pk=document.pk).slug) == (
        ' Acta  final ', '')


def test_new_client_proposal_blocks_undo_of_company_cleanup(make_client_profile, superuser):
    """Fails if undo rewrites a proposal that did not belong to the original identity-change closure."""
    client = make_client_profile(company=' Kore  SAS ', first_name='', last_name='')
    [finding] = only(scan('client', client.pk, rule_ids=['NM1']), 'NM1')
    operation_id = fix(superuser, finding)
    proposal = make_proposal(client, client_name='Kore SAS')

    impact = engine.preview_undo(operation_id)

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']
    assert BusinessProposal.objects.get(pk=proposal.pk).client_name == 'Kore SAS'


def blocker_codes(actor, finding):
    preview = engine.preview_fixes(resolve_scope('all'), [selection(finding)], actor=actor)
    assert preview['blocked'] is True
    return [entry['code'] for entry in preview['steps'][0]['blockers']]


# ── Clients ──────────────────────────────────────────────────────────────────

def test_company_fix_resyncs_client_copies_and_undo_restores_them(make_client_profile, superuser):
    """Fails if a proposal or diagnostic copy keeps the old company, goes unrecorded, or undo misses it."""
    profile = make_client_profile(company=' Kore  SAS', first_name='', last_name='')
    proposal = make_proposal(profile, client_name=' Kore  SAS')
    diagnostic = diagnostic_service.create_diagnostic(client=profile)

    operation_id = fix(superuser, nm1_finding('accounts.userprofile', profile.pk))

    assert UserProfile.objects.get(pk=profile.pk).company_name == 'Kore SAS'
    assert BusinessProposal.objects.get(pk=proposal.pk).client_name == 'Kore SAS'
    assert WebAppDiagnostic.objects.get(pk=diagnostic.pk).client_company == 'Kore SAS'
    assert {('accounts.userprofile', profile.pk, 'company_name'),
            ('content.businessproposal', proposal.pk, 'client_name'),
            ('content.webappdiagnostic', diagnostic.pk, 'client_company')} <= recorded(operation_id)

    undo(superuser, operation_id)

    assert UserProfile.objects.get(pk=profile.pk).company_name == ' Kore  SAS'
    assert BusinessProposal.objects.get(pk=proposal.pk).client_name == ' Kore  SAS'
    assert WebAppDiagnostic.objects.get(pk=diagnostic.pk).client_company == ' Kore  SAS'


def test_name_fix_cleans_first_and_last_name_together_and_undo_restores_both(make_client_profile, superuser):
    """Fails if the writer's split leaves a dirty part, a proposal keeps the old name, or undo is not exact."""
    profile = make_client_profile(first_name='Ana ', last_name='Pérez  Gómez')
    proposal = make_proposal(profile)

    operation_id = fix(superuser, nm1_finding('auth.user', profile.user_id, 'first_name'))

    user = User.objects.get(pk=profile.user_id)
    assert (user.first_name, user.last_name) == ('Ana', 'Pérez Gómez')
    assert BusinessProposal.objects.get(pk=proposal.pk).client_name == 'Ana Pérez Gómez'
    assert only(scan(rule_ids=['NM1']), 'NM1') == []

    undo(superuser, operation_id)

    user.refresh_from_db()
    assert (user.first_name, user.last_name) == ('Ana ', 'Pérez  Gómez')
    assert BusinessProposal.objects.get(pk=proposal.pk).client_name == 'Ana  Pérez  Gómez'


def test_a_name_the_writer_would_split_differently_is_blocked(make_client_profile, superuser):
    """Fails if cleaning a last name would silently move a word of the first name into it."""
    profile = make_client_profile(first_name='Ana María', last_name=' Pérez')

    codes = blocker_codes(superuser, nm1_finding('auth.user', profile.user_id, 'last_name'))

    assert codes == ['name_split_ambiguous']
    assert User.objects.get(pk=profile.user_id).last_name == ' Pérez'


# ── Projects ─────────────────────────────────────────────────────────────────

def _project_names(project, root, thread):
    return [Project.objects.get(pk=project.pk).name, DocumentFolder.objects.get(pk=root.pk).name,
            CommunicationThread.objects.get(pk=thread.pk).title]


def test_project_rename_resyncs_its_root_folder_and_thread_and_undo_restores_all(make_client_profile, superuser):
    """Fails if the managed root folder or thread keeps the old name, goes unrecorded, or stays renamed after undo."""
    project = make_project(make_client_profile(), ' Kore  App')
    root = DocumentFolder.objects.get(managed_project=project)
    thread = CommunicationThread.objects.get(managed_project=project)

    operation_id = fix(superuser, nm1_finding('accounts.project', project.pk))

    assert _project_names(project, root, thread) == ['Kore App'] * 3
    assert recorded(operation_id) == {('accounts.project', project.pk, 'name'),
                                      ('content.documentfolder', root.pk, 'name'),
                                      ('content.communicationthread', thread.pk, 'title')}

    undo(superuser, operation_id)

    assert _project_names(project, root, thread) == [' Kore  App'] * 3


def test_project_rename_records_subfolders_the_root_resync_realigns(make_client_profile, superuser):
    """Fails if a subfolder the rename re-points to the project's client is left out, so undo cannot restore it."""
    profile, other = make_client_profile(), make_client_profile()
    project = make_project(profile, 'Kore  App')
    subfolder = DocumentFolder.objects.get(project=project, name='QA')
    DocumentFolder.objects.filter(pk=subfolder.pk).update(client_user=other.user)

    operation_id = fix(superuser, nm1_finding('accounts.project', project.pk))

    assert DocumentFolder.objects.get(pk=subfolder.pk).client_user_id == profile.user_id
    undo(superuser, operation_id)
    assert DocumentFolder.objects.get(pk=subfolder.pk).client_user_id == other.user_id


# ── Documents and folders ────────────────────────────────────────────────────

def test_folder_fix_and_undo_round_trip(superuser):
    """Fails if the folder keeps its spaces after the fix or loses them for good after undo."""
    folder = DocumentFolder.objects.create(name='Actas  2026')

    operation_id = fix(superuser, nm1_finding('content.documentfolder', folder.pk))
    assert DocumentFolder.objects.get(pk=folder.pk).name == 'Actas 2026'

    undo(superuser, operation_id)
    assert DocumentFolder.objects.get(pk=folder.pk).name == 'Actas  2026'


def test_a_folder_whose_clean_name_exists_beside_it_is_blocked(superuser):
    """Fails if the folder serializer's duplicate-sibling refusal surfaces as a failed apply instead of a blocker."""
    parent = DocumentFolder.objects.create(name='Clientes')
    DocumentFolder.objects.create(name='Actas 2026', parent=parent)
    dirty = DocumentFolder.objects.create(name='Actas  2026', parent=parent)

    assert blocker_codes(superuser, nm1_finding('content.documentfolder', dirty.pk)) == ['name_refused']


def test_document_fix_records_the_editor_and_undo_restores_title_and_editor(superuser):
    """Fails if the title is not cleaned through the panel writer or undo leaves the fixer as last editor."""
    document = Document.objects.create(title='Acta final ')

    operation_id = fix(superuser, nm1_finding('content.document', document.pk))
    document.refresh_from_db()
    assert (document.title, document.updated_by_id) == ('Acta final', superuser.pk)

    undo(superuser, operation_id)
    document.refresh_from_db()
    assert (document.title, document.updated_by_id) == ('Acta final ', None)


def test_a_title_made_only_of_spaces_is_blocked_as_empty(superuser):
    """Fails if NM1 would save an empty title instead of asking for one."""
    document = Document.objects.create(title='   ')

    assert blocker_codes(superuser, nm1_finding('content.document', document.pk)) == ['name_empty']


# ── Communications ───────────────────────────────────────────────────────────

def test_communication_folder_fix_and_undo_round_trip(make_client_profile, superuser):
    """Fails if the communication folder keeps its spaces after the fix or after undo loses them."""
    folder = CommunicationFolder.objects.create(name=' Soporte', client=make_client_profile())

    operation_id = fix(superuser, nm1_finding('content.communicationfolder', folder.pk))
    assert CommunicationFolder.objects.get(pk=folder.pk).name == 'Soporte'

    undo(superuser, operation_id)
    assert CommunicationFolder.objects.get(pk=folder.pk).name == ' Soporte'


def test_thread_fix_and_undo_round_trip(make_client_profile, superuser):
    """Fails if the thread title is not cleaned or undo leaves it clean."""
    thread = CommunicationThread.objects.create(client=make_client_profile(), title='Hilo  de soporte')

    operation_id = fix(superuser, nm1_finding('content.communicationthread', thread.pk))
    assert CommunicationThread.objects.get(pk=thread.pk).title == 'Hilo de soporte'

    undo(superuser, operation_id)
    assert CommunicationThread.objects.get(pk=thread.pk).title == 'Hilo  de soporte'


def test_a_closed_thread_is_blocked_until_reopened(make_client_profile, superuser):
    """Fails if a fix is offered on a thread the writer refuses to edit while closed."""
    thread = CommunicationThread.objects.create(client=make_client_profile(), title='Hilo  cerrado',
                                                status=CommunicationThread.Status.CLOSED)

    assert blocker_codes(superuser, nm1_finding('content.communicationthread', thread.pk)) == ['thread_closed']


def test_proposal_title_cleanup_preserves_pricing_evidence_on_undo(make_client_profile, superuser):
    """Fails if cleaning a proposal title changes its client or stored pricing evidence."""
    client = make_client_profile()
    proposal = make_proposal(client, title='Propuesta  web ')
    pricing = {'total_investment': '1.00', 'discount_percent': 0, 'currency': 'USD'}
    BusinessProposal.objects.filter(pk=proposal.pk).update(legacy_pricing_snapshot=pricing)

    operation_id = fix(superuser, nm1_finding('content.businessproposal', proposal.pk))

    proposal.refresh_from_db()
    assert (proposal.title, proposal.client_id, proposal.legacy_pricing_snapshot) == ('Propuesta web', client.pk, pricing)
    undo(superuser, operation_id)
    proposal.refresh_from_db()
    assert (proposal.title, proposal.client_id, proposal.legacy_pricing_snapshot) == ('Propuesta  web ', client.pk, pricing)


def test_project_title_cleanup_refuses_retained_folder_side_effects(make_client_profile, superuser):
    """Fails if cleaning a project name can rewrite a retained descendant through its signal."""
    client, other = make_client_profile(), make_client_profile()
    project = make_project(client, 'Portal  web')
    descendant = DocumentFolder.objects.get(project=project, name='QA')
    DocumentFolder.objects.filter(pk=descendant.pk).update(
        client_user=other.user, retention_context=make_retention_context(client, superuser))

    assert blocker_codes(superuser, nm1_finding('accounts.project', project.pk)) == ['retained_read_only']


def test_project_title_cleanup_restores_the_roots_archive_cause(make_client_profile, superuser):
    """Fails if undo loses root archive metadata cleared by the project synchronization signal."""
    project = make_project(make_client_profile(), 'Portal  web')
    root = DocumentFolder.objects.get(managed_project=project)
    cause = DocumentFolder.objects.create(name='Archivo')
    DocumentFolder.objects.filter(pk=root.pk).update(archived_via_folder=cause)

    operation_id = fix(superuser, nm1_finding('accounts.project', project.pk))

    assert DocumentFolder.objects.get(pk=root.pk).archived_via_folder_id is None
    undo(superuser, operation_id)
    assert DocumentFolder.objects.get(pk=root.pk).archived_via_folder_id == cause.pk
