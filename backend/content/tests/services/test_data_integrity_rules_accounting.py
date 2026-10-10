"""Accounting rules AC1-AC8: detection on dirty and clean data, writer-backed fixes and exact undo."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import AccountingChangeLog, Document
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_accounting_factories import (
    associate_hosting_context,
    make_cuenta,
    make_cycle,
    make_hosting,
    make_income,
    make_liquid,
    make_recurring,
)
from content.tests.data_integrity_helpers import (
    apply,
    make_project,
    scan,
    selection,
    undo,
)

pytestmark = pytest.mark.django_db

EntityType = AccountingChangeLog.EntityType


def findings(rule_id, scope_kind='all', scope_id=None):
    return scan(scope_kind, scope_id, rule_ids=[rule_id])


def ledger(entity_type, record):
    return AccountingChangeLog.objects.filter(entity_type=entity_type, object_id=record.pk).order_by('pk')


@pytest.fixture
def foreign(make_client_profile):
    """An income of Ana filed under Kore, a project that belongs to Bruno."""
    ana = make_client_profile(company='Ana SAS')
    bruno = make_client_profile(company='Bruno SAS')
    ana_project = make_project(ana, 'Tienda Ana')
    bruno_project = make_project(bruno, 'Kore')
    return {'ana': ana, 'bruno': bruno, 'ana_project': ana_project, 'bruno_project': bruno_project,
            'income': make_income(ana, bruno_project)}


# ── AC1 ──────────────────────────────────────────────────────────────────────

def test_income_on_another_clients_project_is_reported_with_both_sides_to_choose(foreign):
    """Fails if an income under someone else's project goes unreported or the fix offers no side or target."""
    [finding] = findings('AC1')

    assert finding.evidence == {'model': 'content.incomerecord', 'record': foreign['income'].pk,
                                'client': foreign['ana'].pk, 'project': foreign['bruno_project'].pk,
                                'project_owner': foreign['bruno'].user_id}
    assert [option['value'] for option in finding.inputs['side']['options']] == ['project', 'client']
    assert [option['value'] for option in finding.inputs['project']['options']] == ['none', foreign['ana_project'].pk]


def test_records_on_their_own_clients_project_or_without_project_are_not_reported(make_client_profile):
    """Fails if a coherent income, a coherent hosting or an income without project is flagged."""
    ana = make_client_profile()
    project = make_project(ana, 'Tienda')
    make_income(ana, project)
    make_hosting(ana, project)
    make_income(ana, None, concept='Diagnóstico')

    assert findings('AC1') == []


def test_correcting_the_project_side_unlinks_the_income_and_writes_its_ledger_row(foreign, superuser):
    """Fails if the relink bypasses the accounting writer: foreign project kept or no audit row written."""
    [finding] = findings('AC1')

    apply(superuser, [selection(finding, side='project', project='none')])

    foreign['income'].refresh_from_db()
    assert foreign['income'].project_id is None
    assert ledger(EntityType.INCOME, foreign['income']).count() == 1
    assert findings('AC1') == []


def test_correcting_the_client_side_moves_the_hosting_to_the_project_owner(foreign, superuser):
    """Fails if the hosting does not take the project owner as client and as billing snapshot."""
    hosting = make_hosting(foreign['ana'], foreign['bruno_project'])
    [finding] = [item for item in findings('AC1') if item.evidence['model'] == 'content.hostingrecord']

    apply(superuser, [selection(finding, side='client')])

    hosting.refresh_from_db()
    assert hosting.client_id == foreign['bruno'].pk
    assert hosting.client_email == foreign['bruno'].user.email
    assert ledger(EntityType.HOSTING, hosting).count() == 1
    assert [item.evidence['model'] for item in findings('AC1')] == ['content.incomerecord']


def test_undoing_a_relink_restores_the_foreign_project_and_logs_the_reversal(foreign, superuser):
    """Fails if undo leaves the income unlinked or its ledger keeps the relink as the last change."""
    [finding] = findings('AC1')
    _, result = apply(superuser, [selection(finding, side='project', project='none')])

    undo(superuser, result['operation_id'])

    foreign['income'].refresh_from_db()
    assert foreign['income'].project_id == foreign['bruno_project'].pk
    rows = list(ledger(EntityType.INCOME, foreign['income']))
    assert [row.changes[0]['field'] for row in rows] == ['project', 'project']
    assert rows[-1].changes[0]['new'] == 'Kore'


def test_an_income_with_an_associated_cuenta_is_blocked_by_the_billing_guard(foreign, superuser):
    """Fails if the preview offers a relink the writer refuses because a cuenta is bound to that project."""
    cuenta = make_cuenta(foreign['bruno'], foreign['bruno_project'], income_record=foreign['income'])
    associate_hosting_context(cuenta)
    [finding] = findings('AC1')

    preview = engine.preview_fixes(resolve_scope('all'), [selection(finding, side='project', project='none')],
                                   actor=superuser)

    assert [entry['code'] for entry in preview['steps'][0]['blockers']] == ['billing_guard']
    assert preview['blocked'] is True


def test_a_client_scope_reports_only_the_records_that_touch_that_client(foreign, make_client_profile):
    """Fails if a client scan misses a foreign-project income on either side or leaks it to a stranger."""
    stranger = make_client_profile(company='Otra SAS')

    assert [item.evidence['record'] for item in findings('AC1', 'client', foreign['ana'].pk)] == [foreign['income'].pk]
    assert [item.evidence['record'] for item in findings('AC1', 'client', foreign['bruno'].pk)] == [
        foreign['income'].pk]
    assert findings('AC1', 'client', stranger.pk) == []


# ── AC2 ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def split_payment(make_client_profile):
    """A payment of Ana's expected income recorded without client or project."""
    ana = make_client_profile(company='Ana SAS')
    project = make_project(ana, 'Tienda Ana')
    expected = make_income(ana, project)
    return {'ana': ana, 'project': project, 'expected': expected, 'liquid': make_liquid(expected)}


def test_payment_apart_from_its_expected_income_is_reported(split_payment):
    """Fails if a payment can settle an income while sitting under another client and project unreported."""
    [finding] = findings('AC2')

    assert finding.evidence == {'income': split_payment['liquid'].pk, 'parent': split_payment['expected'].pk,
                                'client': None, 'project': None, 'parent_client': split_payment['ana'].pk,
                                'parent_project': split_payment['project'].pk}


def test_payment_matching_its_expected_income_is_not_reported(make_client_profile):
    """Fails if a payment that already shares its expected income's client and project is flagged."""
    ana = make_client_profile()
    project = make_project(ana, 'Tienda')
    make_liquid(make_income(ana, project), ana, project)

    assert findings('AC2') == []


def test_copying_from_the_expected_income_fixes_the_payment_and_undo_restores_it(split_payment, superuser):
    """Fails if the copy skips the writers, leaves the finding, or undo does not bring the payment back."""
    liquid = split_payment['liquid']
    [finding] = findings('AC2')

    _, result = apply(superuser, [selection(finding)])

    liquid.refresh_from_db()
    assert (liquid.client_id, liquid.project_id) == (split_payment['ana'].pk, split_payment['project'].pk)
    assert ledger(EntityType.INCOME, liquid).count() == 2
    assert findings('AC2') == []

    undo(superuser, result['operation_id'])

    liquid.refresh_from_db()
    assert (liquid.client_id, liquid.project_id) == (None, None)
    assert ledger(EntityType.INCOME, liquid).count() == 3


# ── AC3 ──────────────────────────────────────────────────────────────────────

def test_incomes_repeating_client_concept_and_total_are_grouped_across_months(make_client_profile):
    """Fails if the same income registered twice, its concept differing only in case and accents, is not grouped."""
    ana = make_client_profile()
    first = make_income(ana, concept='Kore - Fase 1')
    second = make_income(ana, concept='KORE fase 1', period_date=date(2026, 8, 20), kind='liquid')

    [finding] = findings('AC3')

    assert finding.evidence['incomes'] == [first.pk, second.pk]
    assert finding.evidence['concept'] == 'kore fase 1'
    assert finding.fix_kinds == ('report_only',)


def test_incomes_with_another_total_or_client_are_not_grouped(make_client_profile):
    """Fails if incomes that differ in total or in client are reported as repeated."""
    ana, bruno = make_client_profile(), make_client_profile()
    make_income(ana)
    make_income(ana, total_amount=Decimal('900000.00'), gustavo_amount=Decimal('450000.00'),
                carlos_amount=Decimal('450000.00'))
    make_income(bruno)

    assert findings('AC3') == []


# ── AC4 ──────────────────────────────────────────────────────────────────────

def test_repeated_recurring_payments_are_reported_only_in_a_full_sweep(make_client_profile):
    """Fails if a subscription registered twice goes unreported, or a scoped scan runs this whole-base rule."""
    first = make_recurring('Servidor Kore')
    second = make_recurring('servidor  KORE')
    ana = make_client_profile()

    [finding] = findings('AC4')

    assert finding.evidence['payments'] == [first.pk, second.pk]
    assert findings('AC4', 'client', ana.pk) == []


def test_archived_or_differently_priced_recurring_payments_are_not_reported():
    """Fails if an archived twin or a payment with another price counts as a repetition."""
    make_recurring('Servidor Kore')
    make_recurring('Servidor Kore', is_archived=True)
    make_recurring('Servidor Kore', price=Decimal('300000.00'))

    assert findings('AC4') == []


# ── AC5 ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def stale_hosting(make_client_profile):
    """A hosting with two paid cycles whose totals were never recalculated."""
    ana = make_client_profile()
    hosting = make_hosting(ana, make_project(ana, 'Tienda'))
    make_cycle(hosting, '300000.00')
    make_cycle(hosting, '300000.00')
    return hosting


def test_hosting_totals_apart_from_its_cycles_are_reported(stale_hosting):
    """Fails if a hosting whose paid total ignores its cycles goes unreported."""
    [finding] = findings('AC5')

    assert finding.evidence == {'hosting': stale_hosting.pk, 'total_paid': '0.00', 'cycles_count': 0,
                                'cycles_paid': '600000.00', 'cycles': 2}


def test_recalculating_the_totals_is_logged_and_undo_restores_the_stale_values(stale_hosting, superuser):
    """Fails if the recalculation leaves no ledger row, keeps the finding, or undo is not exact and logged."""
    [finding] = findings('AC5')

    _, result = apply(superuser, [selection(finding)])

    stale_hosting.refresh_from_db()
    assert (stale_hosting.total_paid, stale_hosting.cycles_count) == (Decimal('600000.00'), 2)
    assert ledger(EntityType.HOSTING, stale_hosting).count() == 1
    assert findings('AC5') == []

    undo(superuser, result['operation_id'])

    stale_hosting.refresh_from_db()
    assert (stale_hosting.total_paid, stale_hosting.cycles_count) == (Decimal('0.00'), 0)
    assert ledger(EntityType.HOSTING, stale_hosting).count() == 2


def test_hosting_matching_its_cycle_sums_is_not_reported(make_client_profile):
    """Fails if a hosting matching paid cycles, including an empty zero-total history, is flagged."""
    ana = make_client_profile()
    synced = make_hosting(ana, total_paid=Decimal('300000.00'), cycles_count=1)
    make_cycle(synced, '300000.00')
    make_hosting(ana, client_name='Sin ciclos')

    assert findings('AC5') == []


# ── AC8 ──────────────────────────────────────────────────────────────────────

def test_issued_cuenta_without_billing_context_points_to_the_association_tool(make_client_profile):
    """Fails if an issued cuenta with no contract or hosting context is missed or names the wrong tool."""
    ana = make_client_profile()
    project = make_project(ana, 'Tienda')
    cuenta = make_cuenta(ana, project)

    [finding] = findings('AC8')

    assert finding.tool == {'connector': 'projects', 'name': 'associate_collection_account_context',
                            'arguments': {'project_id': project.pk, 'account_id': cuenta.pk}}
    assert finding.fix_kinds == ('existing_tool',)


def test_draft_cancelled_or_associated_cuentas_are_not_reported(make_client_profile):
    """Fails if a cuenta that needs no billing context, or already has one, is flagged."""
    ana = make_client_profile()
    project = make_project(ana, 'Tienda')
    make_cuenta(ana, project, status=Document.CommercialStatus.DRAFT)
    make_cuenta(ana, project, status=Document.CommercialStatus.CANCELLED)
    associate_hosting_context(make_cuenta(ana, project, status=Document.CommercialStatus.PAID))

    assert findings('AC8') == []
