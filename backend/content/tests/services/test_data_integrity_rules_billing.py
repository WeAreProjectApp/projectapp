"""Accounting rules AC9-AC13: cuentas de cobro per income, partner splits, overpayment and the pocket mirror.

Each inconsistency is made with a raw ``QuerySet.update``, the way it slips in
for real: the services and serializers that keep these invariants never run.
"""
from decimal import Decimal

import pytest

from content.models import Document, IncomeRecord, PocketMovement
from content.services.data_integrity.types import REPORT_ONLY
from content.tests.data_integrity_accounting_factories import make_cuenta, make_income, make_liquid
from content.tests.data_integrity_helpers import make_project, scan

pytestmark = pytest.mark.django_db


def _found(rule_id):
    return scan(rule_ids=[rule_id])


def _pocket_income(profile):
    """A liquid income mirrored in the pocket, as accounting_service._sync_movement leaves it."""
    income = make_income(profile, kind=IncomeRecord.Kind.LIQUID, destination=IncomeRecord.Destination.POCKET)
    movement = PocketMovement.objects.create(
        concept=income.concept, movement_date=income.period_date,
        direction=PocketMovement.Direction.IN, amount=income.total_amount,
    )
    IncomeRecord.objects.filter(pk=income.pk).update(pocket_movement=movement)
    return income, movement


# ── AC9 · two live cuentas for one income ────────────────────────────────────

def test_income_with_two_live_cuentas_is_reported(make_client_profile):
    """Fails if an income left with two non-cancelled cuentas de cobro goes unreported."""
    client = make_client_profile()
    project = make_project(client)
    income = make_income(client, project)
    first = make_cuenta(client, project, income_record=income)
    second = make_cuenta(client, project, public_number='PA-KORE-002')
    Document.objects.filter(pk=second.pk).update(income_record=income)

    [finding] = _found('AC9')

    assert finding.evidence == {'income': income.pk, 'accounts': [first.pk, second.pk]}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_cancelled_cuenta_beside_its_reissue_is_not_a_second_one(make_client_profile):
    """Fails if a cancelled cuenta next to the one that replaced it is counted as a duplicate."""
    client = make_client_profile()
    project = make_project(client)
    income = make_income(client, project)
    make_cuenta(client, project, income_record=income, status=Document.CommercialStatus.CANCELLED)
    make_cuenta(client, project, income_record=income, public_number='PA-KORE-002')

    assert _found('AC9') == []


# ── AC10 · cuenta apart from its income ──────────────────────────────────────

def test_cuenta_moved_to_another_project_than_its_income_is_reported(make_client_profile):
    """Fails if a cuenta whose project drifted from its income's goes unreported (settlement cannot find it)."""
    client = make_client_profile()
    project = make_project(client)
    other = make_project(client, name='Otro proyecto')
    income = make_income(client, project)
    account = make_cuenta(client, project, income_record=income)
    Document.objects.filter(pk=account.pk).update(project=other)

    [finding] = _found('AC10')

    assert finding.evidence == {'document': account.pk, 'income': income.pk,
                                'project': [other.pk, project.pk], 'client_user': [client.user_id, client.user_id]}
    assert 'el proyecto' in finding.message


def test_matching_cuentas_are_quiet_even_without_project(make_client_profile):
    """Fails if a cuenta that matches its income is reported, including both sides without project (NULL)."""
    client = make_client_profile()
    project = make_project(client)
    make_cuenta(client, project, income_record=make_income(client, project))
    make_cuenta(client, None, income_record=make_income(client, None, concept='Diagnóstico'),
                public_number='PA-KORE-002')

    assert _found('AC10') == []


# ── AC11 · partner split ─────────────────────────────────────────────────────

def test_partner_split_above_the_total_is_reported(make_client_profile):
    """Fails if a raw write that hands the partners more than the total goes unreported."""
    income = make_income(make_client_profile())
    IncomeRecord.objects.filter(pk=income.pk).update(gustavo_amount=Decimal('900000.00'))

    [finding] = _found('AC11')

    assert finding.evidence['id'] == income.pk
    assert finding.evidence['amounts'] == ['1000000.00', '900000.00', '500000.00']
    assert 'más que su total' in finding.message


def test_valid_company_and_personal_splits_are_quiet(make_client_profile):
    """Fails if a company split within the total, or a personal record wholly its owner's, is reported."""
    client = make_client_profile()
    make_income(client)
    make_income(client, concept='Retiro Gustavo', ledger='gustavo',
                gustavo_amount=Decimal('1000000.00'), carlos_amount=Decimal('0'))

    assert _found('AC11') == []


# ── AC12 · expected income paid beyond its total ─────────────────────────────

def test_expected_income_paid_beyond_its_total_is_reported(make_client_profile):
    """Fails if liquid payments above an expected income's total go unreported."""
    client = make_client_profile()
    expected = make_income(client)
    make_liquid(expected, client, total_amount=Decimal('600000.00'))
    second = make_liquid(expected, client, total_amount=Decimal('100000.00'))
    IncomeRecord.objects.filter(pk=second.pk).update(total_amount=Decimal('500000.00'))

    [finding] = _found('AC12')

    assert finding.evidence == {'income': expected.pk, 'total': '1000000.00',
                                'liquid': '1100000.00', 'deducted': '0.00'}


def test_exactly_paid_expected_and_lost_children_are_quiet(make_client_profile):
    """Fails if an exactly paid expected income, or a lost record pointing at it, counts as overpayment."""
    client = make_client_profile()
    expected = make_income(client)
    make_liquid(expected, client, total_amount=Decimal('1000000.00'))
    make_income(client, kind=IncomeRecord.Kind.LOST, expected_income=expected, concept='Perdido',
                total_amount=Decimal('500000.00'))

    assert _found('AC12') == []


# ── AC13 · pocket mirror ─────────────────────────────────────────────────────

def test_pocket_movement_apart_from_its_income_is_reported(make_client_profile):
    """Fails if a pocket mirror whose amount drifted from its income goes unreported."""
    income, movement = _pocket_income(make_client_profile())
    PocketMovement.objects.filter(pk=movement.pk).update(amount=Decimal('1.00'))

    [finding] = _found('AC13')

    assert finding.evidence['movement'] == movement.pk
    assert finding.evidence['incomes'] == '1000000.00'
    assert 'sus ingresos suman 1000000.00' in finding.message


def test_matching_pocket_mirror_is_quiet(make_client_profile):
    """Fails if a pocket movement that mirrors its income exactly is reported."""
    _pocket_income(make_client_profile())

    assert _found('AC13') == []
