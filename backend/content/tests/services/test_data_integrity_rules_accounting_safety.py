"""Accounting boundaries: cascades, empty cycle history and scoped duplicate groups."""
from decimal import Decimal

import pytest

from content.models import HostingCycle, HostingRecord, IncomeRecord
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_accounting_factories import (
    associate_hosting_context,
    make_cuenta,
    make_cycle,
    make_hosting,
    make_income,
    make_liquid,
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


def test_correcting_an_expected_incomes_client_restores_its_child_on_undo(make_client_profile, superuser):
    """Fails if a client relink loses the liquid cascade or undo misses an original client."""
    first, owner = make_client_profile(), make_client_profile()
    project = make_project(owner)
    parent = make_income(first, project)
    child = make_liquid(parent, first, project)
    [finding] = [row for row in found('AC1') if row.evidence['record'] == parent.pk]

    _, result = apply(superuser, [selection(finding, side='client')])

    assert list(IncomeRecord.objects.filter(pk__in=[parent.pk, child.pk]).order_by('pk').values_list('client_id', flat=True)) == [
        owner.pk, owner.pk]
    undo(superuser, result['operation_id'])
    assert list(IncomeRecord.objects.filter(pk__in=[parent.pk, child.pk]).order_by('pk').values_list('client_id', flat=True)) == [
        first.pk, first.pk]


def test_hosting_client_relink_restores_all_billing_copies_on_undo(make_client_profile, superuser):
    """Fails if undo restores the hosting client but leaves a refreshed billing copy behind."""
    first, owner = make_client_profile(), make_client_profile()
    hosting = make_hosting(first, make_project(owner), client_name='Nombre anterior', client_email='old@example.com',
                           client_contact_name='Contacto anterior', client_identification='Identificación anterior')
    [finding] = found('AC1')

    _, result = apply(superuser, [selection(finding, side='client')])

    undo(superuser, result['operation_id'])
    hosting.refresh_from_db()
    assert (hosting.client_id, hosting.client_name, hosting.client_email, hosting.client_contact_name,
            hosting.client_identification) == (
        first.pk, 'Nombre anterior', 'old@example.com', 'Contacto anterior', 'Identificación anterior')


def test_liquid_copy_refuses_an_inconsistent_expected_income(make_client_profile, superuser):
    """Fails if preview accepts copying a parent whose own client and project disagree."""
    client = make_client_profile()
    parent = make_income(client, make_project(make_client_profile(), 'Ajeno'))
    make_liquid(parent)
    [finding] = found('AC2')

    impact = engine.preview_fixes(resolve_scope('all'), [selection(finding)], actor=superuser)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['parent_inconsistent']


def test_liquid_copy_moves_its_draft_account_and_restores_it_on_undo(make_client_profile, superuser):
    """Fails if the payment's draft account is omitted from its project-copy closure."""
    client = make_client_profile()
    project = make_project(client)
    child = make_liquid(make_income(client, project), client)
    draft = make_cuenta(client, None, status='draft', income_record=child)
    [finding] = found('AC2')

    impact, result = apply(superuser, [selection(finding)])

    draft.refresh_from_db()
    assert impact['records'] >= 2
    assert draft.project_id == project.pk
    undo(superuser, result['operation_id'])
    draft.refresh_from_db()
    assert draft.project_id is None


def test_income_duplicate_group_keeps_members_outside_the_project_scope(make_client_profile):
    """Fails if a project review hides an equal income located in the client's other project."""
    client = make_client_profile()
    first_project = make_project(client, 'Uno')
    second_project = make_project(client, 'Dos')
    first = make_income(client, first_project)
    second = make_income(client, second_project)

    [finding] = found('AC3', 'project', first_project.pk)

    assert finding.evidence['incomes'] == [first.pk, second.pk]
    assert finding.fingerprint == found('AC3')[0].fingerprint


def test_retained_incomes_do_not_count_as_live_duplicates(make_client_profile, superuser):
    """Fails if a retained income creates a duplicate group with its live counterpart."""
    client = make_client_profile()
    make_income(client)
    make_income(client, retention_context=make_retention_context(client, superuser))

    assert found('AC3') == []


def test_hosting_with_nonzero_totals_without_cycles_is_corrected_reversibly(make_client_profile, superuser):
    """Fails if empty cycle history hides stale nonzero totals or prevents exact undo."""
    hosting = make_hosting(make_client_profile(), total_paid=Decimal('500000.00'), cycles_count=3)
    [finding] = found('AC5')

    _, result = apply(superuser, [selection(finding)])

    hosting.refresh_from_db()
    assert (hosting.total_paid, hosting.cycles_count) == (Decimal('0.00'), 0)
    assert found('AC5') == []
    undo(superuser, result['operation_id'])
    hosting.refresh_from_db()
    assert (hosting.total_paid, hosting.cycles_count) == (Decimal('500000.00'), 3)


def test_changed_cycle_inputs_block_undo_of_a_totals_recalculation(make_client_profile, superuser):
    """Fails if changing a cycle leaves an old recalculation undo available."""
    hosting = make_hosting(make_client_profile())
    cycle = make_cycle(hosting)
    [finding] = found('AC5')
    _, result = apply(superuser, [selection(finding)])
    HostingCycle.objects.filter(pk=cycle.pk).update(amount=Decimal('350000.00'))

    impact = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in impact['blockers']] == ['guard_changed']
    assert HostingRecord.objects.get(pk=hosting.pk).total_paid == Decimal('300000.00')


def test_projectless_issued_account_is_reported_with_its_assignment_prerequisite(make_client_profile):
    """Fails if missing project ownership hides an issued account's absent billing context."""
    document = make_cuenta(make_client_profile(), None)

    [finding] = found('AC8')

    assert finding.evidence['document'] == document.pk
    assert finding.tool['arguments'] == {'account_id': document.pk}
    assert 'primero a un proyecto' in finding.message


def test_project_relink_refuses_a_foreign_client_liquid_cascade(make_client_profile, superuser):
    """Fails if fixing a parent's project creates a foreign project link on its payment."""
    client, other = make_client_profile(), make_client_profile()
    target = make_project(client)
    foreign = make_project(other, 'Ajeno')
    parent = make_income(client, foreign)
    make_liquid(parent, other, foreign)
    [finding] = [row for row in found('AC1') if row.evidence['record'] == parent.pk]

    impact = engine.preview_fixes(resolve_scope('all'), [selection(finding, side='project', project=target.pk)],
                                  actor=superuser)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['child_client_mismatch']


def test_client_relink_refuses_to_leave_a_payment_on_the_previous_clients_project(make_client_profile, superuser):
    """Fails if correcting a parent's client leaves a carried payment pointing at another client's project."""
    original, owner = make_client_profile(), make_client_profile()
    parent = make_income(original, make_project(owner, 'Dueño'))
    make_liquid(parent, original, make_project(original, 'Anterior'))
    [finding] = [row for row in found('AC1') if row.evidence['record'] == parent.pk]

    impact = engine.preview_fixes(resolve_scope('all'), [selection(finding, side='client')], actor=superuser)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['child_client_mismatch']


def test_project_relink_refuses_to_move_a_payment_with_associated_billing(make_client_profile, superuser):
    """Fails if an income cascade bypasses its payment's issued billing account."""
    client, other = make_client_profile(), make_client_profile()
    target = make_project(client)
    foreign = make_project(other, 'Ajeno')
    parent = make_income(client, foreign)
    child = make_liquid(parent, client, foreign)
    associate_hosting_context(make_cuenta(other, foreign, income_record=child))
    [finding] = [row for row in found('AC1') if row.evidence['record'] == parent.pk]

    impact = engine.preview_fixes(resolve_scope('all'), [selection(finding, side='project', project=target.pk)],
                                  actor=superuser)

    assert [entry['code'] for entry in impact['steps'][0]['blockers']] == ['billing_guard']
