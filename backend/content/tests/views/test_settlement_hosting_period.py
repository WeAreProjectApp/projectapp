"""Settling a hosting income: the window belongs to the expected record.

PA-51 made the covered period mandatory on hosting incomes, and settling ended
up on the wrong side of that rule: its children copy the parent's `origin` but
are born with no window — nobody hands them one — so the check fired on EVERY
hosting income, the ones with a complete window included. Liquidar, the abono
and the rescheduled balance were all refused with a message asking for a field
none of those flows can fill.

These tests pin both halves of the contract: the records a settlement DERIVES
are exempt, and the window is completed where it belongs — on the expected
income — without ever holding up the registration of the money.

The form path is untouched and keeps demanding it: see
``views/test_income_period_fields.py``.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.models import AccountingChangeLog, IncomeRecord
from content.services import accounting_service

pytestmark = pytest.mark.django_db

BULK_SETTLE_URL = '/api/accounting/incomes/bulk-settle/'


def settle_url(income):
    return f'/api/accounting/incomes/{income.pk}/settle/'


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify') as notify:
        yield notify


@pytest.fixture
def hosting_income(make_income):
    """A quarterly hosting charge with its window complete (post-PA-51).

    July→September on purpose: every payment below is made in August, so a
    child that took the parent's window instead of the payment date would land
    in a different month and the assertions would say so.
    """
    return make_income(
        concept='Hosting: Trimestral',
        origin=IncomeRecord.Origin.HOSTING,
        period_date=date(2026, 7, 1),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 9, 30),
        period_cadence='quarterly',
    )


@pytest.fixture
def legacy_hosting_income(make_income):
    """A hosting charge from before PA-51: no window recorded."""
    return make_income(
        concept='Vastago (Hosting) - Semestre 1',
        origin=IncomeRecord.Origin.HOSTING,
        period_date=date(2026, 10, 1),
    )


def settlement(**overrides):
    data = {
        'concept': 'Hosting: Trimestral',
        'period_date': '2026-08-18',
        'destination': IncomeRecord.Destination.POCKET,
        'total_amount': '1000000.00',
        'notes': '',
    }
    data.update(overrides)
    return data


class TestSettlingIsNoLongerBlocked:
    def test_a_hosting_income_with_its_window_can_be_settled(
        self, super_client, hosting_income,
    ):
        """The reported case: the cuenta de cobro of a quarterly hosting."""
        response = super_client.post(
            settle_url(hosting_income), settlement(), format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['liquid']['total_amount'] == '1000000.00'

    def test_a_hosting_income_without_a_window_can_be_settled_too(
        self, super_client, legacy_hosting_income,
    ):
        """Pre-PA-51 rows settle without being sent anywhere to be completed."""
        response = super_client.post(
            settle_url(legacy_hosting_income), settlement(), format='json',
        )

        assert response.status_code == 201, response.data

    def test_the_payment_keeps_its_own_date_and_takes_no_window(
        self, super_client, hosting_income,
    ):
        """The child is the payment, not the service window.

        The parent's July service window must not replace the child's August
        payment date or be repeated on every payment.
        """
        super_client.post(
            settle_url(hosting_income), settlement(), format='json',
        )

        liquid = IncomeRecord.objects.get(kind=IncomeRecord.Kind.LIQUID)
        assert liquid.period_date == date(2026, 8, 18)
        assert liquid.period_start is None
        assert liquid.period_end is None
        assert liquid.period_cadence == ''
        # Still classified as what it collects — only the window is exempt.
        assert liquid.origin == IncomeRecord.Origin.HOSTING

    def test_the_rescheduled_balance_keeps_the_month_it_is_expected_in(
        self, super_client, hosting_income,
    ):
        response = super_client.post(
            settle_url(hosting_income),
            settlement(
                total_amount='600000.00',
                expected_incomes=[{
                    'concept': 'Hosting: Trimestral - saldo',
                    'period_date': '2026-11',
                    'amount': '400000.00',
                }],
            ),
            format='json',
        )

        assert response.status_code == 201, response.data
        follow_up = IncomeRecord.objects.get(
            concept='Hosting: Trimestral - saldo',
        )
        assert follow_up.period_date == date(2026, 11, 1)
        assert follow_up.period_start is None
        assert follow_up.origin == IncomeRecord.Origin.HOSTING

    def test_an_abono_can_cover_several_hosting_incomes(
        self, super_client, hosting_income, legacy_hosting_income,
    ):
        """PA-69's flow was refused by the same rule, with or without window."""
        response = super_client.post(
            BULK_SETTLE_URL,
            {
                'allocations': [
                    {'income_id': hosting_income.pk, 'amount': '400000.00'},
                    {
                        'income_id': legacy_hosting_income.pk,
                        'amount': '300000.00',
                    },
                ],
                'total_amount': '700000.00',
                'period_date': '2026-08-18',
                'notes': 'Transferencia Bancolombia',
            },
            format='json',
        )

        assert response.status_code == 201, response.data
        children = IncomeRecord.objects.filter(kind=IncomeRecord.Kind.LIQUID)
        assert children.count() == 2
        assert all(child.period_date == date(2026, 8, 18) for child in children)


class TestCompletingTheWindowWhileSettling:
    def test_the_window_sent_with_the_settlement_completes_the_parent(
        self, super_client, legacy_hosting_income,
    ):
        response = super_client.post(
            settle_url(legacy_hosting_income),
            settlement(period={
                'period_start': '2026-10-01',
                'period_end': '2027-03-31',
                'period_cadence': 'semiannual',
            }),
            format='json',
        )

        assert response.status_code == 201, response.data
        legacy_hosting_income.refresh_from_db()
        assert legacy_hosting_income.period_start == date(2026, 10, 1)
        assert legacy_hosting_income.period_end == date(2027, 3, 31)
        assert legacy_hosting_income.period_cadence == 'semiannual'
        # The stored expected-payment date is preserved; in this case it
        # happens to match the completed window's start.
        assert legacy_hosting_income.period_date == date(2026, 10, 1)

    def test_completing_a_legacy_window_keeps_its_expected_payment_month(
        self, super_client, make_income,
    ):
        """Completing an October window keeps the legacy parent's November payment month."""
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 11, 1),
        )

        response = super_client.post(
            settle_url(income),
            settlement(period={
                'period_start': '2026-10-01',
                'period_end': '2027-03-31',
                'period_cadence': 'semiannual',
            }),
            format='json',
        )

        assert response.status_code == 201, response.data
        income.refresh_from_db()
        assert income.period_start == date(2026, 10, 1)
        assert income.period_date == date(2026, 11, 1)

    def test_completing_the_window_notifies_only_for_the_payment(
        self, super_client, legacy_hosting_income, _mute_notifications,
    ):
        """The parent window edit is audited silently; only the liquid child notifies."""
        response = super_client.post(
            settle_url(legacy_hosting_income),
            settlement(period={
                'period_start': '2026-10-01',
                'period_end': '2027-03-31',
                'period_cadence': 'semiannual',
            }),
            format='json',
        )

        assert response.status_code == 201, response.data
        parent_log = AccountingChangeLog.objects.get(
            entity_type=AccountingChangeLog.EntityType.INCOME,
            object_id=legacy_hosting_income.pk,
            action=AccountingChangeLog.Action.UPDATED,
        )
        assert {change['field'] for change in parent_log.changes} == {
            'period_start', 'period_end', 'period_cadence',
        }
        payment_log = AccountingChangeLog.objects.get(
            entity_type=AccountingChangeLog.EntityType.INCOME,
            object_id=response.data['liquid']['id'],
            action=AccountingChangeLog.Action.CREATED,
        )
        _mute_notifications.assert_called_once_with(payment_log)

    def test_completing_the_window_does_not_drag_the_payment_with_it(
        self, super_client, legacy_hosting_income,
    ):
        super_client.post(
            settle_url(legacy_hosting_income),
            settlement(period={
                'period_start': '2026-10-01',
                'period_end': '2027-03-31',
                'period_cadence': 'semiannual',
            }),
            format='json',
        )

        liquid = IncomeRecord.objects.get(kind=IncomeRecord.Kind.LIQUID)
        assert liquid.period_date == date(2026, 8, 18)
        assert liquid.period_start is None

    def test_settling_without_the_block_leaves_the_income_as_it_was(
        self, super_client, legacy_hosting_income,
    ):
        """The window is a courtesy, never a condition."""
        response = super_client.post(
            settle_url(legacy_hosting_income), settlement(), format='json',
        )

        assert response.status_code == 201, response.data
        legacy_hosting_income.refresh_from_db()
        assert legacy_hosting_income.period_start is None
        assert legacy_hosting_income.period_date == date(2026, 10, 1)

    def test_a_half_filled_window_is_refused_before_anything_is_written(
        self, super_client, legacy_hosting_income,
    ):
        response = super_client.post(
            settle_url(legacy_hosting_income),
            settlement(period={'period_start': '2026-10-01'}),
            format='json',
        )

        assert response.status_code == 400
        assert 'period' in response.data
        assert not IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.LIQUID,
        ).exists()

    def test_an_end_before_the_start_is_refused_and_nothing_is_settled(
        self, super_client, legacy_hosting_income,
    ):
        response = super_client.post(
            settle_url(legacy_hosting_income),
            settlement(period={
                'period_start': '2026-10-01',
                'period_end': '2026-09-30',
                'period_cadence': 'semiannual',
            }),
            format='json',
        )

        assert response.status_code == 400
        legacy_hosting_income.refresh_from_db()
        assert legacy_hosting_income.period_start is None
        assert not IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.LIQUID,
        ).exists()

    def test_a_window_on_an_income_that_is_not_hosting_is_refused(
        self, super_client, make_income,
    ):
        income = make_income(
            concept='Kore - Inicio 40%',
            origin=IncomeRecord.Origin.DEVELOPMENT,
            period_date=date(2026, 7, 1),
        )

        response = super_client.post(
            settle_url(income),
            settlement(concept='Kore - Inicio 40%', period={
                'period_start': '2026-10-01',
                'period_end': '2027-03-31',
                'period_cadence': 'semiannual',
            }),
            format='json',
        )

        assert response.status_code == 400
        assert 'hosting' in str(response.data).lower()
        income.refresh_from_db()
        assert income.period_start is None


class TestTheFormPathIsUntouched:
    def test_creating_a_hosting_income_by_hand_still_demands_the_window(
        self, super_client,
    ):
        """The exemption is the settlement's, not everybody's."""
        response = super_client.post(
            '/api/accounting/incomes/create/',
            {
                'concept': 'Hosting: Trimestral',
                'kind': 'expected',
                'origin': 'hosting',
                'total_amount': '1000000.00',
                'period_date': '2026-08-01',
            },
            format='json',
        )

        assert response.status_code == 400
        assert 'period_start' in response.data
