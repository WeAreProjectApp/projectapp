"""Settling an expected income collected short.

The governing arithmetic (see the service docstring):

    paid = liquid children + linked deductions
    received + deductions + follow_ups + unassigned = pending
    new parent total = old total - follow_ups   (deductions keep it gross)
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.models import AccountingChangeLog, Document, DocumentType, ExpenseRecord, IncomeRecord
from content.services import accounting_service, accounting_settlement_service

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify') as notify:
        yield notify


def make_expected(**overrides):
    fields = {
        'concept': 'Kore - Inicio 40%',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-07-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def settlement(**overrides):
    data = {
        'concept': 'Kore - Inicio 40%',
        'period_date': '2026-07-15',
        'destination': IncomeRecord.Destination.PARTNERS,
        'total_amount': Decimal('992000.00'),
        'notes': '',
        'deductions': [],
        'expected_incomes': [],
    }
    data.update(overrides)
    return data


def gateway_fee(amount='8000.00'):
    return {
        'type': ExpenseRecord.DeductionType.GATEWAY_FEE,
        'detail': '',
        'amount': Decimal(amount),
    }


def issue_collection_account(income):
    return Document.objects.create(
        title=f'Cuenta de {income.concept}',
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income,
        client_user=income.client.user,
        project=income.project,
    )


class TestClientInheritance:
    """The settled money must stay attributed to the same client."""

    def test_liquid_child_and_follow_up_inherit_client_and_origin(
        self, superuser, make_client_profile,
    ):
        profile = make_client_profile()
        income = make_expected(
            client=profile, origin=IncomeRecord.Origin.DEVELOPMENT,
        )
        issue_collection_account(income)

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('600000.00'),
                expected_incomes=[{
                    'concept': 'Kore - Saldo',
                    'period_date': '2026-09-01',
                    'amount': Decimal('400000.00'),
                }],
            ),
            superuser,
        )

        assert result['liquid'].client_id == profile.pk
        assert result['liquid'].origin == IncomeRecord.Origin.DEVELOPMENT
        follow_up = result['expected_incomes'][0]
        assert follow_up.client_id == profile.pk
        assert follow_up.origin == IncomeRecord.Origin.DEVELOPMENT

    def test_liquid_child_inherits_the_project(
        self, superuser, make_client_profile,
    ):
        from accounts.models import Project

        profile = make_client_profile()
        project = Project.objects.create(name='Kore', client=profile.user)
        income = make_expected(client=profile, project=project)
        issue_collection_account(income)

        result = accounting_settlement_service.settle_expected_income(
            income, settlement(), superuser,
        )

        assert result['liquid'].project_id == project.pk

    def test_client_less_income_settles_without_a_client(self, superuser):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income, settlement(), superuser,
        )

        assert result['liquid'].client_id is None
        assert result['liquid'].origin == ''


class TestNoAllocations:
    """With nothing to allocate the flow must behave exactly like today."""

    def test_leaves_the_parent_untouched(self, superuser):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income, settlement(total_amount=Decimal('1000000.00')), superuser,
        )

        income.refresh_from_db()
        assert income.total_amount == Decimal('1000000.00')
        assert result['liquid'].kind == IncomeRecord.Kind.LIQUID
        assert result['liquid'].expected_income_id == income.pk
        assert result['expenses'] == []
        assert result['expected_incomes'] == []

    def test_sends_exactly_one_email(self, superuser, _mute_notifications):
        income = make_expected()

        # 942.000 received + 8.000 fee + 50.000 rescheduled = 1.000.000
        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('942000.00'),
                deductions=[gateway_fee()],
                expected_incomes=[{
                    'concept': 'Kore - Saldo',
                    'period_date': '2026-08-01',
                    'amount': Decimal('50000.00'),
                }],
            ),
            superuser,
        )

        # Four records are written but the settlement is one user action.
        assert _mute_notifications.call_count == 1


class TestDeduction:
    def test_closes_the_parent_and_books_the_fee(self, superuser):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income, settlement(deductions=[gateway_fee()]), superuser,
        )

        income.refresh_from_db()
        # The expected total stays gross: 992.000 received + 8.000 fee
        # credited through the link close the full 1.000.000.
        assert income.total_amount == Decimal('1000000.00')
        assert accounting_settlement_service._paid_total(income) == (
            income.total_amount
        )

        expense = result['expenses'][0]
        assert expense.deduction_type == ExpenseRecord.DeductionType.GATEWAY_FEE
        assert expense.total_amount == Decimal('8000.00')
        assert expense.concept == 'Comisión plataforma de pago — Kore - Inicio 40%'
        assert expense.source_ref == f'income:{income.pk}:settlement'
        assert expense.source_income_id == income.pk

    def test_never_touches_the_pocket(self, superuser):
        """That money was discounted before the transfer ever arrived."""
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income, settlement(deductions=[gateway_fee()]), superuser,
        )

        assert result['expenses'][0].pocket_movement_id is None

    def test_other_uses_the_free_text_as_concept(self, superuser):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(deductions=[{
                'type': ExpenseRecord.DeductionType.OTHER,
                'detail': 'Descuento pactado',
                'amount': Decimal('8000.00'),
            }]),
            superuser,
        )

        assert result['expenses'][0].concept.startswith('Descuento pactado —')

    def test_several_deductions_in_one_settlement(self, superuser):
        """A single payment can carry a fee AND a withholding."""
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('900000.00'),
                deductions=[
                    gateway_fee('30000.00'),
                    {
                        'type': ExpenseRecord.DeductionType.WITHHOLDING,
                        'detail': '',
                        'amount': Decimal('70000.00'),
                    },
                ],
            ),
            superuser,
        )

        income.refresh_from_db()
        assert len(result['expenses']) == 2
        # 900.000 received + 30.000 + 70.000 in fees = the gross total.
        assert income.total_amount == Decimal('1000000.00')
        assert accounting_settlement_service._paid_total(income) == (
            Decimal('1000000.00')
        )


class TestFollowUpExpectedIncomes:
    def test_reschedules_the_balance_and_shrinks_the_parent(self, superuser):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('900000.00'),
                deductions=[gateway_fee()],
                expected_incomes=[{
                    'concept': 'Kore - Saldo agosto',
                    'period_date': '2026-08',
                    'amount': Decimal('92000.00'),
                }],
            ),
            superuser,
        )

        income.refresh_from_db()
        follow_up = result['expected_incomes'][0]
        # Only the follow-up leaves the parent; the fee stays inside it as
        # payment credit: 1.000.000 − 92.000 rescheduled = 908.000.
        assert income.total_amount == Decimal('908000.00')
        assert follow_up.kind == IncomeRecord.Kind.EXPECTED
        assert follow_up.total_amount == Decimal('92000.00')
        assert str(follow_up.period_date) == '2026-08-01'
        # Parent + follow-up still add up to the original expected amount.
        assert (
            income.total_amount + follow_up.total_amount
        ) == Decimal('1000000.00')
        # And the parent is closed: 900.000 received + 8.000 fee credit.
        assert accounting_settlement_service._paid_total(income) == (
            Decimal('908000.00')
        )

    def test_inherits_ledger_and_destination(self, superuser):
        income = make_expected(destination=IncomeRecord.Destination.PARTNERS)

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(expected_incomes=[{
                'concept': 'Saldo',
                'period_date': '2026-08',
                'amount': Decimal('8000.00'),
            }]),
            superuser,
        )

        follow_up = result['expected_incomes'][0]
        assert follow_up.ledger == income.ledger
        assert follow_up.destination == income.destination

    def test_more_than_one_follow_up(self, superuser):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('500000.00'),
                expected_incomes=[
                    {'concept': 'Cuota 2', 'period_date': '2026-08',
                     'amount': Decimal('250000.00')},
                    {'concept': 'Cuota 3', 'period_date': '2026-09',
                     'amount': Decimal('250000.00')},
                ],
            ),
            superuser,
        )

        income.refresh_from_db()
        assert len(result['expected_incomes']) == 2
        assert income.total_amount == Decimal('500000.00')


class TestPartialAllocation:
    def test_unassigned_balance_stays_pending(self, superuser):
        """Not deciding yet is still allowed — the rest simply stays open."""
        income = make_expected()

        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('900000.00'),
                deductions=[gateway_fee()],
            ),
            superuser,
        )

        income.refresh_from_db()
        # The parent stays gross; received + fee credit leave 92.000 open.
        assert income.total_amount == Decimal('1000000.00')
        pending = income.total_amount - accounting_settlement_service._paid_total(income)
        assert pending == Decimal('92000.00')

    def test_settling_a_partially_collected_record(self, superuser):
        income = make_expected()
        IncomeRecord.objects.create(
            concept='Abono previo',
            kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-07-05',
            total_amount=Decimal('600000.00'),
            gustavo_amount=Decimal('300000.00'),
            carlos_amount=Decimal('300000.00'),
            expected_income=income,
        )

        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('390000.00'),
                deductions=[gateway_fee('10000.00'),],
            ),
            superuser,
        )

        income.refresh_from_db()
        assert income.total_amount == Decimal('1000000.00')
        # 600.000 + 390.000 collected + 10.000 fee credit → closed.
        assert accounting_settlement_service._paid_total(income) == (
            Decimal('1000000.00')
        )


class TestResidualOnly:
    """Zero received with the shortfall fully allocated: pure bookkeeping.

    The typical case: an old partial collection left a fee-sized residual
    that will never arrive, and there is no new payment to register.
    """

    def make_partially_collected(self):
        income = make_expected()
        IncomeRecord.objects.create(
            concept='Abono previo',
            kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-07-05',
            total_amount=Decimal('950000.00'),
            gustavo_amount=Decimal('475000.00'),
            carlos_amount=Decimal('475000.00'),
            expected_income=income,
        )
        return income

    def test_zero_received_with_a_deduction_closes_the_parent_without_a_liquid_child(
        self, superuser,
    ):
        income = self.make_partially_collected()

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('0'),
                deductions=[gateway_fee('50000.00')],
            ),
            superuser,
        )

        income.refresh_from_db()
        assert result['liquid'] is None
        # Only the pre-existing collection remains — no zero-amount payment.
        assert income.liquid_records.count() == 1
        # Parent stays gross; 950.000 collected + 50.000 fee credit → paid.
        assert income.total_amount == Decimal('1000000.00')
        assert accounting_settlement_service._paid_total(income) == (
            Decimal('1000000.00')
        )
        expense = result['expenses'][0]
        assert expense.total_amount == Decimal('50000.00')
        assert expense.source_ref == f'income:{income.pk}:settlement'
        assert expense.source_income_id == income.pk

    def test_zero_received_sends_no_email(self, superuser, _mute_notifications):
        """Nothing was collected, so there is no payment to announce."""
        income = self.make_partially_collected()

        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('0'),
                deductions=[gateway_fee('50000.00')],
            ),
            superuser,
        )

        assert _mute_notifications.call_count == 0

    def test_zero_received_with_a_partial_allocation_keeps_the_rest_pending(
        self, superuser,
    ):
        income = make_expected()

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('0'),
                deductions=[gateway_fee('8000.00')],
            ),
            superuser,
        )

        income.refresh_from_db()
        assert result['liquid'] is None
        # The fee credits 8.000; the remaining 992.000 stays pending.
        assert income.total_amount == Decimal('1000000.00')
        pending = income.total_amount - accounting_settlement_service._paid_total(income)
        assert pending == Decimal('992000.00')
        assert income.liquid_records.count() == 0


class TestPartnerSplit:
    def test_follow_up_keeps_the_parent_ratio(self, superuser):
        income = make_expected(
            gustavo_amount=Decimal('600000.00'),
            carlos_amount=Decimal('400000.00'),
        )

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('900000.00'),
                expected_incomes=[{
                    'concept': 'Saldo',
                    'period_date': '2026-08',
                    'amount': Decimal('100000.00'),
                }],
            ),
            superuser,
        )

        follow_up = result['expected_incomes'][0]
        assert follow_up.gustavo_amount == Decimal('60000.00')
        assert follow_up.carlos_amount == Decimal('40000.00')

    def test_parent_split_is_rescaled_when_a_follow_up_reduces_it(self, superuser):
        income = make_expected(
            gustavo_amount=Decimal('600000.00'),
            carlos_amount=Decimal('400000.00'),
        )

        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('992000.00'),
                expected_incomes=[{
                    'concept': 'Saldo',
                    'period_date': '2026-08',
                    'amount': Decimal('8000.00'),
                }],
            ),
            superuser,
        )

        income.refresh_from_db()
        assert income.total_amount == Decimal('992000.00')
        assert income.gustavo_amount == Decimal('595200.00')
        assert income.carlos_amount == Decimal('396800.00')

    def test_a_deduction_leaves_the_parent_split_untouched(self, superuser):
        income = make_expected(
            gustavo_amount=Decimal('600000.00'),
            carlos_amount=Decimal('400000.00'),
        )

        accounting_settlement_service.settle_expected_income(
            income,
            settlement(deductions=[gateway_fee()]), superuser,
        )

        income.refresh_from_db()
        assert income.total_amount == Decimal('1000000.00')
        assert income.gustavo_amount == Decimal('600000.00')
        assert income.carlos_amount == Decimal('400000.00')

    def test_split_never_exceeds_the_amount_on_odd_cents(self, superuser):
        income = make_expected(
            total_amount=Decimal('1000.00'),
            gustavo_amount=Decimal('333.33'),
            carlos_amount=Decimal('666.67'),
        )

        result = accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('900.01'),
                expected_incomes=[{
                    'concept': 'Saldo',
                    'period_date': '2026-08',
                    'amount': Decimal('99.99'),
                }],
            ),
            superuser,
        )

        follow_up = result['expected_incomes'][0]
        assert (
            follow_up.gustavo_amount + follow_up.carlos_amount
            <= follow_up.total_amount
        )


class TestValidation:
    def test_rejects_allocations_above_the_pending_balance(self, superuser):
        income = make_expected()

        with pytest.raises(ValueError, match='no puede superar el saldo'):
            accounting_settlement_service.settle_expected_income(
                income,
                settlement(deductions=[gateway_fee('50000.00')]),
                superuser,
            )

    def test_rejects_a_non_expected_record(self, superuser):
        liquid = make_expected(kind=IncomeRecord.Kind.LIQUID)

        with pytest.raises(ValueError, match='ingreso esperado'):
            accounting_settlement_service.settle_expected_income(
                liquid, settlement(), superuser,
            )

    def test_rejects_a_zero_payment_with_nothing_allocated(self, superuser):
        """Zero received is only meaningful when the shortfall is resolved."""
        income = make_expected()

        with pytest.raises(ValueError, match='mayor a cero'):
            accounting_settlement_service.settle_expected_income(
                income, settlement(total_amount=Decimal('0')), superuser,
            )

    def test_rejects_an_already_paid_record(self, superuser):
        income = make_expected()
        IncomeRecord.objects.create(
            concept='Pago total',
            kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-07-05',
            total_amount=Decimal('1000000.00'),
            gustavo_amount=Decimal('500000.00'),
            carlos_amount=Decimal('500000.00'),
            expected_income=income,
        )

        with pytest.raises(ValueError, match='completamente pagado'):
            accounting_settlement_service.settle_expected_income(
                income, settlement(), superuser,
            )

    def test_nothing_is_written_when_validation_fails(self, superuser):
        income = make_expected()
        before = ExpenseRecord.objects.count()

        with pytest.raises(ValueError):
            accounting_settlement_service.settle_expected_income(
                income,
                settlement(deductions=[gateway_fee('50000.00')]),
                superuser,
            )

        income.refresh_from_db()
        assert ExpenseRecord.objects.count() == before
        assert income.total_amount == Decimal('1000000.00')


class TestAudit:
    def test_every_record_is_audited(self, superuser):
        income = make_expected()

        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('900000.00'),
                deductions=[gateway_fee()],
                expected_incomes=[{
                    'concept': 'Saldo',
                    'period_date': '2026-08',
                    'amount': Decimal('92000.00'),
                }],
            ),
            superuser,
        )

        actions = AccountingChangeLog.objects.values_list(
            'entity_type', 'action',
        )
        assert (
            AccountingChangeLog.EntityType.EXPENSE,
            AccountingChangeLog.Action.CREATED,
        ) in actions
        assert (
            AccountingChangeLog.EntityType.INCOME,
            AccountingChangeLog.Action.UPDATED,
        ) in actions


class TestUtilityImpact:
    def test_a_deduction_hits_expected_utility_but_not_liquid(self, superuser):
        """Asymmetric on purpose: the expected side is gross, so its
        utility subtracts the known fees; the liquid total already arrived
        net of them, so subtracting the fee there too would count the same
        loss twice.
        """
        income = make_expected()
        accounting_settlement_service.settle_expected_income(
            income, settlement(deductions=[gateway_fee()]), superuser,
        )

        totals = accounting_service.year_totals(2026)

        assert totals['expected_total'] == Decimal('1000000.00')
        assert totals['liquid_total'] == Decimal('992000.00')
        assert totals['expenses_total'] == Decimal('0')
        assert totals['deductions_total'] == Decimal('8000.00')
        assert totals['expected_utility'] == Decimal('992000.00')
        assert totals['liquid_utility'] == Decimal('992000.00')

    def test_an_ordinary_expense_still_reduces_utility(self, superuser):
        income = make_expected()
        accounting_settlement_service.settle_expected_income(
            income, settlement(deductions=[gateway_fee()]), superuser,
        )
        ExpenseRecord.objects.create(
            concept='Hosting',
            period_date='2026-07-01',
            total_amount=Decimal('100000.00'),
            gustavo_amount=Decimal('50000.00'),
            carlos_amount=Decimal('50000.00'),
        )

        totals = accounting_service.year_totals(2026)

        assert totals['expenses_total'] == Decimal('100000.00')
        assert totals['liquid_utility'] == Decimal('892000.00')


class TestIterativeSettlement:
    def test_a_second_settlement_after_a_fee_sees_the_right_pending(self, superuser):
        """The fee credit must feed the next settlement's pending math."""
        income = make_expected()
        accounting_settlement_service.settle_expected_income(
            income,
            settlement(
                total_amount=Decimal('500000.00'),
                deductions=[gateway_fee()],
            ),
            superuser,
        )

        # 1.000.000 − 500.000 received − 8.000 fee = 492.000 pending.
        result = accounting_settlement_service.settle_expected_income(
            income, settlement(total_amount=Decimal('492000.00')), superuser,
        )

        income.refresh_from_db()
        assert result['liquid'].total_amount == Decimal('492000.00')
        assert income.total_amount == Decimal('1000000.00')
        assert accounting_settlement_service._paid_total(income) == (
            Decimal('1000000.00')
        )

    def test_a_settled_income_with_fee_rejects_another_settlement(self, superuser):
        income = make_expected()
        accounting_settlement_service.settle_expected_income(
            income, settlement(deductions=[gateway_fee()]), superuser,
        )

        with pytest.raises(ValueError, match='completamente pagado'):
            accounting_settlement_service.settle_expected_income(
                income, settlement(total_amount=Decimal('1.00')), superuser,
            )


class TestGrossRegrossMigration:
    """Migration 0173 links settle-born deductions and re-grosses parents.

    Pre-migration rows carry only the ``income:<pk>:settlement`` stamp and a
    netted parent total; the backfill must recover the link and the gross
    total using the deduction's own stored split (exact, no re-derivation).
    """

    @staticmethod
    def _migration():
        from importlib import import_module

        return import_module(
            'content.migrations.0173_expense_source_income_and_regross',
        )

    def test_links_by_source_ref_and_regrosses_with_the_stored_split(
        self, make_expense,
    ):
        from django.apps import apps

        income = make_expected(
            total_amount=Decimal('81546.00'),
            gustavo_amount=Decimal('40773.00'),
            carlos_amount=Decimal('40773.00'),
        )
        deduction = make_expense(
            deduction_type=ExpenseRecord.DeductionType.GATEWAY_FEE,
            total_amount=Decimal('4854.00'),
            gustavo_amount=Decimal('2427.00'),
            carlos_amount=Decimal('2427.00'),
            source_ref=f'income:{income.pk}:settlement',
        )

        self._migration().link_and_regross(apps, None)

        income.refresh_from_db()
        deduction.refresh_from_db()
        assert deduction.source_income_id == income.pk
        assert income.total_amount == Decimal('86400.00')
        assert income.gustavo_amount == Decimal('43200.00')
        assert income.carlos_amount == Decimal('43200.00')

    def test_ignores_stale_refs_and_ordinary_expenses(self, make_expense):
        from django.apps import apps

        ordinary = make_expense(source_ref='income:999999:settlement')
        stale = make_expense(
            deduction_type=ExpenseRecord.DeductionType.BANK_FEE,
            source_ref='income:999999:settlement',
        )

        self._migration().link_and_regross(apps, None)

        ordinary.refresh_from_db()
        stale.refresh_from_db()
        assert ordinary.source_income_id is None
        assert stale.source_income_id is None
