"""Audited exit from retention: adopt, undo, discard empty containers, reassign proposals."""
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from accounts.models import Deliverable, HostingSubscription, Project, ProjectPhase
from content.models import (
    AccountingChangeLog, BusinessProposal, CommunicationThread, Document, DocumentFolder,
    IncomeRecord, McpConnector, ProjectRetentionContext, ProjectRetentionOperation,
    ProposalProjectReassignment,
)
from content.services.project_document_folder_service import require_project_folder
from content.services.proposal_project_reassignment import preview_reassignment, reassign_proposal
from content.services.retained_adoption import RetentionConflict, preview_undo, undo_adoption
from content.services.retained_containers import discard_empty_containers, preview_discard
from content.tests.views.test_panel_projects_assign_unlinked import apply_url, make_income, preview_url

pytestmark = pytest.mark.django_db
EntityType = AccountingChangeLog.EntityType


@pytest.fixture
def littigio(admin_user, make_client_profile):
    profile = make_client_profile(company='Littigio')
    target = Project.objects.create(name='Littigio', client=profile.user)
    context = ProjectRetentionContext.objects.create(
        client=profile.user, original_project_id=9014, project_name='Littigio anterior', created_by=admin_user,
    )
    folder = DocumentFolder.objects.create(name='Littigio anterior', client_user=profile.user, retention_context=context)
    expected = make_income(profile, concept='Inicio Fase 1', retention_context=context)
    liquid = make_income(profile, concept='Inicio Fase 1 (pago)', kind=IncomeRecord.Kind.LIQUID,
                         expected_income=expected, retention_context=context)
    document = Document.objects.create(title='Contrato firmado', client_user=profile.user, folder=folder,
                                       retention_context=context)
    thread = CommunicationThread.objects.create(client=profile, title='Littigio', retention_context=context)
    context.retained_records = {
        'content.incomerecord': [str(expected.pk), str(liquid.pk)],
        'content.document': [str(document.pk)],
        'content.documentfolder': [str(folder.pk)],
        'content.communicationthread': [str(thread.pk)],
    }
    context.category_counts = {label: len(ids) for label, ids in context.retained_records.items()}
    context.save(update_fields=['retained_records', 'category_counts'])
    return {'profile': profile, 'target': target, 'context': context, 'folder': folder,
            'expected': expected, 'liquid': liquid, 'document': document, 'thread': thread}


def test_preview_names_the_deleted_project_and_lists_retained_threads(admin_client, littigio):
    """Fails if the assign plan hides where retained rows come from or omits the retained thread."""
    response = admin_client.get(preview_url(littigio['target'].pk))

    incomes = {row['id']: row for row in response.data['incomes']}
    assert incomes[littigio['expected'].pk]['retained'] == {
        'context_id': littigio['context'].pk, 'project_name': 'Littigio anterior',
    }
    root_thread = CommunicationThread.objects.get(managed_project=littigio['target'])
    assert response.data['threads'] == [{
        'id': littigio['thread'].pk, 'label': 'Littigio', 'status_label': 'Abierto',
        'retained': {'context_id': littigio['context'].pk, 'project_name': 'Littigio anterior'},
        'duplicates': [{'id': root_thread.pk, 'label': 'Littigio'}],
    }]
    assert response.data['retained_total'] == 4


def test_assign_moves_a_retained_income_with_its_liquid_child(admin_client, littigio):
    """Fails if a retained income stays read-only, or leaves its settlement child behind."""
    response = admin_client.post(apply_url(littigio['target'].pk), {
        'income_ids': [littigio['expected'].pk], 'reason': 'Unificar Littigio',
    }, format='json')

    assert response.status_code == 200
    for income in (littigio['expected'], littigio['liquid']):
        income.refresh_from_db()
        assert (income.project_id, income.retention_context_id) == (littigio['target'].pk, None)
    operation = ProjectRetentionOperation.objects.get()
    assert (operation.operation, operation.origin, operation.target_project_id, operation.reason) == (
        'adopt', 'assign_unlinked', littigio['target'].pk, 'Unificar Littigio',
    )
    assert {(item['model'], item['id']) for item in operation.items} == {
        ('content.incomerecord', littigio['expected'].pk), ('content.incomerecord', littigio['liquid'].pk),
    }
    assert response.data['adoptions'] == [{
        'operation_id': operation.pk, 'context_id': littigio['context'].pk,
        'project_name': 'Littigio anterior', 'records': 2,
    }]
    assert AccountingChangeLog.objects.filter(entity_type=EntityType.INCOME, object_id=littigio['expected'].pk).exists()


def test_assign_rehomes_a_retained_document_and_assigns_the_thread(admin_client, littigio):
    """Fails if an adopted document stays inside the deleted project's folder or the thread keeps no project."""
    response = admin_client.post(apply_url(littigio['target'].pk), {
        'document_ids': [littigio['document'].pk], 'thread_ids': [littigio['thread'].pk],
    }, format='json')

    assert response.status_code == 200
    assert response.data['assigned_threads'] == 1
    littigio['document'].refresh_from_db()
    littigio['thread'].refresh_from_db()
    root = require_project_folder(littigio['target'])
    assert (littigio['document'].project_id, littigio['document'].folder_id, littigio['document'].retention_context_id) == (
        littigio['target'].pk, root.pk, None,
    )
    assert (littigio['thread'].project_id, littigio['thread'].retention_context_id) == (littigio['target'].pk, None)


def test_assign_refuses_a_retained_thread_of_another_client(admin_client, admin_user, make_client_profile, littigio):
    """Fails if one client's retained conversation can be moved into another client's project."""
    other = make_client_profile(company='Otro cliente')
    other_context = ProjectRetentionContext.objects.create(
        client=other.user, original_project_id=9099, project_name='Ajeno', created_by=admin_user,
    )
    foreign = CommunicationThread.objects.create(client=other, title='Ajeno', retention_context=other_context)

    response = admin_client.post(apply_url(littigio['target'].pk), {'thread_ids': [foreign.pk]}, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'records_changed'
    foreign.refresh_from_db()
    assert (foreign.project_id, foreign.retention_context_id) == (None, other_context.pk)


def test_adopted_rows_leave_the_retained_data_consultation(admin_client, littigio):
    """Fails if the client's 'Datos sin proyecto' keeps listing rows that moved to a live project."""
    admin_client.post(apply_url(littigio['target'].pk), {'income_ids': [littigio['expected'].pk]}, format='json')

    littigio['context'].refresh_from_db()
    assert 'content.incomerecord' not in littigio['context'].retained_records
    response = admin_client.get(f"/api/proposals/client-profiles/{littigio['profile'].pk}/retained-project-data/")
    counts = {row['key']: row['count'] for row in response.data['contexts'][0]['categories']}
    assert 'incomes' not in counts
    assert counts['documents'] == 1


def test_undo_returns_the_records_to_retention_exactly(admin_client, admin_user, littigio):
    """Fails if undoing an adoption does not restore project, folder and the read-only marker."""
    admin_client.post(apply_url(littigio['target'].pk), {
        'income_ids': [littigio['expected'].pk], 'document_ids': [littigio['document'].pk],
    }, format='json')
    operation = ProjectRetentionOperation.objects.get()
    impact = preview_undo(operation.pk)
    assert impact['blockers'] == []

    result = undo_adoption(operation.pk, actor=admin_user, reason='Prueba de vuelta atrás',
                           request_id='undo-littigio', expected_impact_hash=impact['impact_hash'])

    context = littigio['context']
    for income in (littigio['expected'], littigio['liquid']):
        income.refresh_from_db()
        assert (income.project_id, income.retention_context_id) == (None, context.pk)
    littigio['document'].refresh_from_db()
    assert (littigio['document'].project_id, littigio['document'].folder_id, littigio['document'].retention_context_id) == (
        None, littigio['folder'].pk, context.pk,
    )
    context.refresh_from_db()
    assert sorted(context.retained_records['content.incomerecord']) == sorted(
        [str(littigio['expected'].pk), str(littigio['liquid'].pk)],
    )
    undo = ProjectRetentionOperation.objects.get(pk=result['operation_id'])
    assert (undo.operation, undo.reverts_id) == ('undo', operation.pk)


def test_undo_is_refused_after_a_later_edit(admin_client, admin_user, littigio):
    """Fails if undo would silently overwrite an edit made after the adoption."""
    admin_client.post(apply_url(littigio['target'].pk), {'income_ids': [littigio['expected'].pk]}, format='json')
    operation = ProjectRetentionOperation.objects.get()
    income = IncomeRecord.objects.get(pk=littigio['expected'].pk)
    income.concept = 'Inicio Fase 1 ajustado'
    income.save(update_fields=['concept', 'updated_at'])

    impact = preview_undo(operation.pk)

    assert [blocker['code'] for blocker in impact['blockers']] == ['changed_since']
    with pytest.raises(RetentionConflict):
        undo_adoption(operation.pk, actor=admin_user, reason='Prueba', request_id='undo-late',
                      expected_impact_hash=impact['impact_hash'])
    income.refresh_from_db()
    assert (income.project_id, income.retention_context_id) == (littigio['target'].pk, None)


def test_undo_replay_with_the_same_request_id_is_idempotent(admin_client, admin_user, littigio):
    """Fails if a lost response retried with the same request_id undoes twice or errors."""
    admin_client.post(apply_url(littigio['target'].pk), {'income_ids': [littigio['expected'].pk]}, format='json')
    operation = ProjectRetentionOperation.objects.get()
    impact = preview_undo(operation.pk)
    first = undo_adoption(operation.pk, actor=admin_user, reason='Prueba', request_id='undo-replay',
                          expected_impact_hash=impact['impact_hash'])

    again = undo_adoption(operation.pk, actor=admin_user, reason='Prueba', request_id='undo-replay',
                          expected_impact_hash=impact['impact_hash'])

    assert again == {'operation_id': first['operation_id'], 'reverts': operation.pk, 'idempotent': True}
    assert ProjectRetentionOperation.objects.filter(operation='undo').count() == 1


def test_cleanup_deletes_empty_retained_folders_leaf_first(admin_client, admin_user, littigio):
    """Fails if emptied folders of a deleted project cannot be removed, or a parent goes before its child."""
    child = DocumentFolder.objects.create(name='Contratos', parent=littigio['folder'],
                                          client_user=littigio['profile'].user, retention_context=littigio['context'])
    admin_client.post(apply_url(littigio['target'].pk), {'document_ids': [littigio['document'].pk]}, format='json')
    selection = {'document_folders': [littigio['folder'].pk, child.pk]}
    impact = preview_discard(littigio['context'].pk, selection)
    assert [(row['kind'], row['id']) for row in impact['containers']] == [
        ('document_folders', child.pk), ('document_folders', littigio['folder'].pk),
    ]
    assert impact['blockers'] == []

    result = discard_empty_containers(littigio['context'].pk, actor=admin_user, reason='Limpieza Littigio',
                                      request_id='cleanup-littigio', expected_impact_hash=impact['impact_hash'],
                                      selection=selection)

    assert not DocumentFolder.objects.filter(pk__in=[child.pk, littigio['folder'].pk]).exists()
    operation = ProjectRetentionOperation.objects.get(pk=result['operation_id'])
    assert (operation.operation, len(operation.items)) == ('discard', 2)


def test_cleanup_refuses_a_folder_that_still_holds_a_document(admin_user, littigio):
    """Fails if a retained folder with content can be deleted."""
    selection = {'document_folders': [littigio['folder'].pk]}
    impact = preview_discard(littigio['context'].pk, selection)

    assert [blocker['code'] for blocker in impact['blockers']] == ['not_empty']
    with pytest.raises(RetentionConflict):
        discard_empty_containers(littigio['context'].pk, actor=admin_user, reason='Limpieza',
                                 request_id='cleanup-blocked', expected_impact_hash=impact['impact_hash'],
                                 selection=selection)
    assert DocumentFolder.objects.filter(pk=littigio['folder'].pk).exists()


def test_cleanup_endpoint_rejects_a_stale_preview(admin_client, littigio):
    """Fails if the panel deletes containers against an impact the operator never saw."""
    response = admin_client.post(
        f"/api/projects/retained-contexts/{littigio['context'].pk}/cleanup/",
        {'reason': 'Limpieza', 'request_id': 'cleanup-stale', 'expected_impact_hash': '0' * 64,
         'selection': {'communication_threads': [littigio['thread'].pk]}},
        format='json',
    )

    assert response.status_code == 409
    assert str(response.data['code']) == 'stale_impact'
    assert CommunicationThread.objects.filter(pk=littigio['thread'].pk).exists()


@pytest.fixture
def retained_phase_one(admin_user, make_client_profile, proposal):
    profile = make_client_profile(company='Littigio')
    target = Project.objects.create(name='Littigio', client=profile.user)
    context = ProjectRetentionContext.objects.create(
        client=profile.user, original_project_id=9015, project_name='Plataforma educativa fase 1',
        created_by=admin_user,
    )
    package = Deliverable.objects.create(project=None, retention_context=context, title='Paquete aprobado',
                                         uploaded_by=admin_user, category=Deliverable.CATEGORY_DOCUMENTS)
    epic = Deliverable.objects.create(project=None, retention_context=context, title='Módulo de cursos',
                                      uploaded_by=admin_user, category=Deliverable.CATEGORY_DOCUMENTS,
                                      source_epic_key='cursos')
    phase = ProjectPhase.objects.create(project=None, business_proposal=proposal, order=1, retention_context=context)
    BusinessProposal.objects.filter(pk=proposal.pk).update(
        client=profile, status=BusinessProposal.Status.ACCEPTED, deliverable=package,
    )
    proposal.refresh_from_db()
    return {'profile': profile, 'target': target, 'context': context, 'proposal': proposal,
            'package': package, 'epic': epic, 'phase': phase}


def test_preview_from_a_deleted_project_has_no_circular_blocker(retained_phase_one):
    """Fails if a proposal retained from a deleted project still cannot be reassigned (the circle)."""
    case = retained_phase_one
    impact = preview_reassignment(case['proposal'].pk, case['target'].pk)

    assert impact['blockers'] == []
    assert impact['source_project'] == {'id': None, 'name': 'Plataforma educativa fase 1', 'retained': True}
    assert impact['phase_ids'] == [case['phase'].pk]
    assert set(impact['deliverable_ids']) == {case['package'].pk, case['epic'].pk}
    assert impact['attributed_resource_ids'] == [case['epic'].pk]


def test_reassignment_moves_the_retained_graph_keeping_ids(admin_user, retained_phase_one):
    """Fails if the move recreates rows, leaves them read-only, or loses the deleted source in the audit."""
    case = retained_phase_one
    impact = preview_reassignment(case['proposal'].pk, case['target'].pk)

    result = reassign_proposal(case['proposal'].pk, {
        'target_project_id': case['target'].pk, 'reason': 'Unificar Littigio',
        'expected_impact_hash': impact['impact_hash'], 'request_id': 'move-117',
    }, actor=admin_user)

    for row in (case['phase'], case['package'], case['epic']):
        row.refresh_from_db()
    assert (case['phase'].project_id, case['phase'].order, case['phase'].retention_context_id) == (case['target'].pk, 1, None)
    assert (case['package'].project_id, case['package'].retention_context_id) == (case['target'].pk, None)
    assert (case['epic'].project_id, case['epic'].source_proposal_id) == (case['target'].pk, case['proposal'].pk)
    receipt = ProposalProjectReassignment.objects.get(request_id='move-117')
    assert (receipt.source_project_id, receipt.target_project_id) == (9015, case['target'].pk)
    operation = ProjectRetentionOperation.objects.get(operation='proposal_reassignment')
    assert {item['id'] for item in operation.items} == {case['phase'].pk, case['package'].pk, case['epic'].pk}
    assert result['proposal']['linked_project']['id'] == case['target'].pk


def _active_subscription(project):
    today = date.today()
    return HostingSubscription.objects.create(
        project=project, plan=HostingSubscription.PLAN_MONTHLY, status=HostingSubscription.STATUS_ACTIVE,
        base_monthly_amount=Decimal('100'), effective_monthly_amount=Decimal('100'),
        billing_amount=Decimal('100'), discount_percent=0, start_date=today, next_billing_date=today,
    )


def test_a_due_phase_needs_an_explicit_hosting_decision(retained_phase_one):
    """Fails if moving a due phase into an active subscription can trigger an automatic charge unasked."""
    case = retained_phase_one
    _active_subscription(case['target'])
    ProjectPhase.objects.filter(pk=case['phase'].pk).update(hosting_start_date=date.today() - timedelta(days=3))

    blocked = preview_reassignment(case['proposal'].pk, case['target'].pk)
    postponed = preview_reassignment(case['proposal'].pk, case['target'].pk,
                                     hosting_start_date=date.today() + timedelta(days=30))
    accepted = preview_reassignment(case['proposal'].pk, case['target'].pk, accept_hosting_start=True)

    assert [blocker['code'] for blocker in blocked['blockers']] == ['pending_hosting_start']
    assert postponed['blockers'] == []
    assert accepted['blockers'] == []


def test_a_postponed_hosting_start_is_written_on_the_moved_phase(admin_user, retained_phase_one):
    """Fails if the chosen hosting start date is not the one the moved phase keeps."""
    case = retained_phase_one
    _active_subscription(case['target'])
    ProjectPhase.objects.filter(pk=case['phase'].pk).update(hosting_start_date=date.today() - timedelta(days=3))
    start = date.today() + timedelta(days=30)
    impact = preview_reassignment(case['proposal'].pk, case['target'].pk, hosting_start_date=start)

    reassign_proposal(case['proposal'].pk, {
        'target_project_id': case['target'].pk, 'reason': 'Unificar Littigio',
        'expected_impact_hash': impact['impact_hash'], 'request_id': 'move-117-later',
        'hosting_start_date': start.isoformat(),
    }, actor=admin_user)

    case['phase'].refresh_from_db()
    assert (case['phase'].project_id, case['phase'].hosting_start_date) == (case['target'].pk, start)


@pytest.fixture
def projects_token():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def _call(api_client, token, name, arguments):
    response = api_client.post(f'/api/mcp/projects/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments},
    }, format='json')
    return json.loads(response.data['result']['content'][0]['text'])


def test_mcp_undo_needs_the_preview_backed_confirmation(api_client, admin_client, projects_token, littigio):
    """Fails if MCP can undo an adoption without going through its preview and confirmation."""
    admin_client.post(apply_url(littigio['target'].pk), {'income_ids': [littigio['expected'].pk]}, format='json')
    operation = ProjectRetentionOperation.objects.get()
    preview = _call(api_client, projects_token, 'preview_retained_operation_undo', {'operation_id': operation.pk})

    pending = _call(api_client, projects_token, 'undo_retained_operation', {
        'operation_id': operation.pk, 'reason': 'Prueba MCP', 'request_id': 'mcp-undo',
        'expected_impact_hash': preview['impact_hash'],
    })
    littigio['expected'].refresh_from_db()
    assert pending['confirmation_required'] is True
    assert littigio['expected'].project_id == littigio['target'].pk

    _call(api_client, projects_token, 'confirm_action', {'confirmation_id': pending['confirmation_id']})

    littigio['expected'].refresh_from_db()
    assert (littigio['expected'].project_id, littigio['expected'].retention_context_id) == (None, littigio['context'].pk)
