"""Proposal findings and reversible snapshot/order corrections (PR1-PR8)."""
from decimal import Decimal

import pytest
from accounts.models import Deliverable
from accounts.services.proposal_client_service import sync_snapshot

from content.models import BusinessProposal, ProposalSection
from content.tests.data_integrity_helpers import (
    apply,
    make_phase,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
    undo,
)
from content.tests.data_integrity_projects_factories import make_retention_context

pytestmark = pytest.mark.django_db


def found(rule_id, scope_kind='all', scope_id=None):
    return only(scan(scope_kind, scope_id, rule_ids=[rule_id]), rule_id)


def section(proposal, order, title, kind='greeting'):
    return ProposalSection.objects.create(proposal=proposal, order=order, title=title, section_type=kind)


def deliverable(project, actor, **values):
    return Deliverable.objects.create(project=project, title='Alcance aprobado', uploaded_by=actor, **values)


def test_outdated_client_copy_in_a_proposal_is_reported(make_client_profile):
    """Fails if stale name, phone or email copies are ignored."""
    client = make_client_profile(phone='3001234567')
    proposal = make_proposal(client, client_name='Nombre anterior', client_phone='111', client_email='old@example.com')

    [finding] = found('PR1')

    assert finding.evidence['proposal'] == proposal.pk
    assert set(finding.evidence['stale']) == {'client_name', 'client_phone', 'client_email'}
    assert finding.fix_kinds == ('sync_copy',)


def test_current_client_copy_has_no_snapshot_finding(make_client_profile):
    """Fails if a proposal already synchronized from its client is flagged."""
    proposal = make_proposal(make_client_profile(phone='3001234567'))
    sync_snapshot(proposal)

    assert found('PR1') == []


def test_synchronizing_a_client_copy_restores_all_old_values_on_undo(make_client_profile, admin_user):
    """Fails if snapshot sync leaves stale data or undo loses an old copied value."""
    client = make_client_profile(phone='3001234567')
    proposal = make_proposal(client, client_name='Anterior', client_phone='111', client_email='old@example.com')
    [finding] = found('PR1')

    _, result = apply(admin_user, [selection(finding)])

    proposal.refresh_from_db()
    assert (proposal.client_name, proposal.client_phone, proposal.client_email) == (
        client.user.get_full_name(), client.phone, client.user.email)
    assert found('PR1') == []
    undo(admin_user, result['operation_id'])
    proposal.refresh_from_db()
    assert (proposal.client_name, proposal.client_phone, proposal.client_email) == ('Anterior', '111', 'old@example.com')


def test_provisional_email_does_not_replace_the_proposals_real_email(make_client_profile):
    """Fails if a placeholder email is treated as stale proposal contact data."""
    client = make_client_profile(email='pending@temp.example.com')
    proposal = make_proposal(client, client_email='contact@example.com')
    sync_snapshot(proposal)

    assert found('PR1') == []
    proposal.refresh_from_db()
    assert proposal.client_email == 'contact@example.com'


def test_proposal_without_a_client_is_report_only(make_client_profile):
    """Fails if an unassigned proposal is missed or offered an automatic assignment."""
    client = make_client_profile()
    proposal = make_proposal(client)
    BusinessProposal.objects.filter(pk=proposal.pk).update(client=None)

    [finding] = found('PR2')

    assert finding.evidence == {'proposal': proposal.pk}
    assert finding.fix_kinds == ('report_only',)


def test_proposal_with_a_client_has_no_unassigned_finding(make_client_profile):
    """Fails if an assigned proposal is flagged as clientless."""
    make_proposal(make_client_profile())

    assert found('PR2') == []


def test_proposal_phase_on_a_foreign_project_points_to_reassignment(make_client_profile):
    """Fails if a proposal linked to another client's phase is missed."""
    client = make_client_profile()
    proposal = make_proposal(client)
    foreign = make_project(make_client_profile(), 'Otro cliente')
    phase = make_phase(foreign, proposal, 1)

    [finding] = found('PR3')

    assert finding.evidence['reasons'] == ['phase_other_client']
    assert finding.evidence['phases'] == [[phase.pk, foreign.pk, foreign.client_id]]
    assert finding.fix_kinds == ('existing_tool',)
    assert finding.tool['name'] == 'preview_proposal_project_reassignment'


def test_proposal_phase_matching_its_deliverable_has_no_project_finding(make_client_profile, admin_user):
    """Fails if coherent proposal, phase and deliverable links are flagged."""
    client = make_client_profile()
    project = make_project(client)
    proposal = make_proposal(client, deliverable=deliverable(project, admin_user))
    make_phase(project, proposal, 1)

    assert found('PR3') == []


def test_proposal_phases_in_two_projects_are_reported(make_client_profile):
    """Fails if splitting one proposal across projects is missed without a deliverable."""
    client = make_client_profile()
    proposal = make_proposal(client)
    make_phase(make_project(client, 'Primero'), proposal, 1)
    make_phase(make_project(client, 'Segundo'), proposal, 1)

    [finding] = found('PR3')

    assert finding.evidence['proposal'] == proposal.pk
    assert 'multiple_projects' in finding.evidence['reasons']


def test_accepted_or_finished_proposal_without_links_is_reported(make_client_profile):
    """Fails if an approved proposal lacking both a phase and deliverable is missed."""
    client = make_client_profile()
    accepted = make_proposal(client, status='accepted')
    finished = make_proposal(client, title='Terminada', status='finished')

    findings = found('PR4')

    assert [finding.evidence['proposal'] for finding in findings] == [accepted.pk, finished.pk]
    assert [finding.fix_kinds for finding in findings] == [('report_only',), ('report_only',)]


def test_unapproved_or_linked_proposals_have_no_missing_project_finding(make_client_profile, admin_user):
    """Fails if an unapproved proposal or an approved one with a link is flagged."""
    client = make_client_profile()
    project = make_project(client)
    make_proposal(client, status='draft')
    make_phase(project, make_proposal(client, status='finished'), 1)
    make_proposal(client, title='Con entregable', deliverable=deliverable(project, admin_user))

    assert found('PR4') == []


def test_proposal_with_a_retained_phase_points_to_reassignment(make_client_profile, superuser):
    """Fails if a proposal still tied to a deleted project's retained phase is missed."""
    client = make_client_profile()
    proposal = make_proposal(client)
    phase = make_phase(make_project(client), proposal, 1)
    context = make_retention_context(client, superuser)
    type(phase).objects.filter(pk=phase.pk).update(project=None, retention_context=context)

    [finding] = found('PR5')

    assert finding.evidence == {'proposal': proposal.pk, 'deliverable': None, 'phases': [[phase.pk, context.pk]]}
    assert finding.tool['name'] == 'reassign_proposal_project'
    assert finding.fix_kinds == ('existing_tool',)


def test_proposal_with_live_links_has_no_retained_link_finding(make_client_profile, admin_user):
    """Fails if a proposal with only live phases and deliverables is flagged."""
    client = make_client_profile()
    project = make_project(client)
    proposal = make_proposal(client, deliverable=deliverable(project, admin_user))
    make_phase(project, proposal, 1)

    assert found('PR5') == []


def test_proposal_with_a_retained_deliverable_is_reported(make_client_profile, superuser):
    """Fails if a retained deliverable is ignored when no retained phase exists."""
    client = make_client_profile()
    context = make_retention_context(client, superuser)
    retained = deliverable(None, superuser, retention_context=context)
    proposal = make_proposal(client, deliverable=retained)

    [finding] = found('PR5')

    assert finding.evidence == {'proposal': proposal.pk, 'deliverable': [retained.pk, context.pk], 'phases': []}


def test_proposal_sections_with_duplicate_positions_offer_reordering(make_client_profile):
    """Fails if sections sharing a position go unreported."""
    proposal = make_proposal(make_client_profile())
    first = section(proposal, 4, 'Saludo')
    second = section(proposal, 4, 'Resumen', 'executive_summary')

    [finding] = found('PR7')

    assert finding.evidence == {'proposal': proposal.pk, 'orders': [[first.pk, 4], [second.pk, 4]]}
    assert finding.fix_kinds == ('reorder',)


def test_distinct_section_positions_have_no_order_finding(make_client_profile):
    """Fails if unique positions are reported merely because they contain gaps."""
    proposal = make_proposal(make_client_profile())
    section(proposal, 0, 'Saludo')
    section(proposal, 4, 'Resumen', 'executive_summary')

    assert found('PR7') == []


def test_reordering_sections_preserves_content_on_undo(make_client_profile, admin_user):
    """Fails if reorder leaves duplicate positions or undo changes content or old positions."""
    proposal = make_proposal(make_client_profile())
    first = section(proposal, 4, 'Saludo')
    second = section(proposal, 4, 'Resumen', 'executive_summary')
    third = section(proposal, 9, 'Alcance', 'functional_requirements')
    approved_content = {'modules': [{'name': 'Entrega aprobada', 'percentage': 42}]}
    ProposalSection.objects.filter(pk=third.pk).update(content_json=approved_content)
    [finding] = found('PR7')

    _, result = apply(admin_user, [selection(finding)])

    assert list(proposal.sections.order_by('pk').values_list('order', flat=True)) == [4, 5, 6]
    assert ProposalSection.objects.get(pk=third.pk).content_json == approved_content
    assert found('PR7') == []
    undo(admin_user, result['operation_id'])
    assert list(proposal.sections.order_by('pk').values_list('pk', 'order', 'title')) == [
        (first.pk, 4, 'Saludo'), (second.pk, 4, 'Resumen'), (third.pk, 9, 'Alcance')]
    assert ProposalSection.objects.get(pk=third.pk).content_json == approved_content


def test_repeated_proposals_form_one_group(make_client_profile):
    """Fails if title normalization hides proposals with the same client, investment and currency."""
    client = make_client_profile()
    first = make_proposal(client, title='Revisión web', total_investment=Decimal('1000000.00'))
    second = make_proposal(client, title=' revision  WEB ', total_investment=Decimal('1000000.00'))

    [finding] = found('PR8')

    assert finding.evidence['proposals'] == [first.pk, second.pk]
    assert finding.fix_kinds == ('report_only',)


def test_proposals_differing_in_client_investment_or_currency_are_not_grouped(make_client_profile):
    """Fails if a shared title alone marks a proposal as a duplicate."""
    client = make_client_profile()
    make_proposal(client, total_investment=Decimal('1000.00'), currency='COP')
    make_proposal(client, total_investment=Decimal('2000.00'), currency='COP')
    make_proposal(client, total_investment=Decimal('1000.00'), currency='USD')
    make_proposal(make_client_profile(), total_investment=Decimal('1000.00'), currency='COP')

    assert found('PR8') == []


def test_project_scope_limits_proposal_findings_to_linked_proposals(make_client_profile):
    """Fails if a project review includes another project's stale client copy."""
    client = make_client_profile()
    project = make_project(client)
    proposal = make_proposal(client, client_phone='111')
    make_phase(project, proposal, 1)
    make_phase(make_project(client, 'Otro'), make_proposal(client, client_phone='222'), 1)

    [finding] = found('PR1', 'project', project.pk)

    assert finding.evidence['proposal'] == proposal.pk
    assert finding.fingerprint == found('PR1')[0].fingerprint
