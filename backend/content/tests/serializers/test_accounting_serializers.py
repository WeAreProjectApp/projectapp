"""Serializer tests for the accounting module."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import (
    AccountingChangeLog,
    Document,
    DocumentType,
    HostingRecord,
    IncomeRecord,
    NotificationRecipient,
    PocketMovement,
    RecurringPayment,
)
from accounts.models import Project
from content.serializers.accounting import (
    AccountingSettingsSerializer,
    AccountingChangeLogSerializer,
    CardBalanceSnapshotCreateUpdateSerializer,
    ExpenseRecordCreateUpdateSerializer,
    ExpenseRecordSerializer,
    HostingRecordCreateUpdateSerializer,
    IncomeRecordCreateUpdateSerializer,
    IncomeRecordSerializer,
    NotificationRecipientCreateUpdateSerializer,
    PocketMovementCreateUpdateSerializer,
    PocketMovementSerializer,
    SettlementMovementSerializer,
    RecurringPaymentCreateUpdateSerializer,
    month_label,
)


class TestMonthLabel:
    def test_empty_date_returns_a_blank_label(self):
        assert month_label(None) == ''


def _collection_account_for(income, status):
    return Document.objects.create(
        title='Cuenta de cobro de prueba',
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        commercial_status=status,
        income_record=income,
        client_user=income.client.user,
        project=income.project,
    )


@pytest.mark.django_db
class TestIncomeSettlementEligibilityProjection:
    def test_client_expected_without_collection_account_is_blocked(self, make_income, make_client_profile):
        """Falla si el panel ofrece liquidar un ingreso de cliente sin cuenta emitida."""
        profile = make_client_profile()
        income = make_income(client=profile)

        data = IncomeRecordSerializer(income).data

        assert data['collection_account_status'] is None
        assert data['can_settle'] is False
        assert data['settlement_blocked_reason'] == (
            'Primero genera y emite una cuenta de cobro para este ingreso.'
        )

    def test_client_expected_with_draft_collection_account_is_blocked(self, make_income, make_client_profile):
        """Falla si un borrador desbloquea el pago antes de que la cuenta sea emitida."""
        profile = make_client_profile()
        income = make_income(client=profile)
        _collection_account_for(income, Document.CommercialStatus.DRAFT)

        data = IncomeRecordSerializer(income).data

        assert data['collection_account_status'] == 'draft'
        assert data['can_settle'] is False
        assert data['settlement_blocked_reason'] == (
            'Primero genera y emite una cuenta de cobro para este ingreso.'
        )

    def test_client_expected_with_cancelled_collection_account_is_blocked(self, make_income, make_client_profile):
        """Falla si una cuenta anulada aparece vigente y habilita la liquidación."""
        profile = make_client_profile()
        income = make_income(client=profile)
        _collection_account_for(income, Document.CommercialStatus.CANCELLED)

        data = IncomeRecordSerializer(income).data

        assert data['collection_account_status'] is None
        assert data['can_settle'] is False
        assert data['settlement_blocked_reason'] == (
            'Primero genera y emite una cuenta de cobro para este ingreso.'
        )

    def test_client_expected_with_issued_collection_account_is_settleable(self, make_income, make_client_profile):
        """Falla si una cuenta emitida sigue mostrando un ingreso como bloqueado."""
        profile = make_client_profile()
        project = Project.objects.create(name='Litigio', client=profile.user)
        income = make_income(client=profile, project=project)
        _collection_account_for(income, Document.CommercialStatus.ISSUED)

        data = IncomeRecordSerializer(income).data

        assert data['collection_account_status'] == 'issued'
        assert data['can_settle'] is True
        assert data['settlement_blocked_reason'] == ''

    def test_expected_without_client_remains_settleable(self, make_income):
        """Falla si la regla nueva bloquea ingresos internos que no requieren cuenta."""
        income = make_income(client=None)

        data = IncomeRecordSerializer(income).data

        assert data['collection_account_status'] is None
        assert data['can_settle'] is True
        assert data['settlement_blocked_reason'] == ''

    @pytest.mark.parametrize('mismatch', ['client', 'project'])
    def test_issued_account_outside_the_income_context_stays_blocked(
        self, make_income, make_client_profile, mismatch,
    ):
        """Falla si una cuenta emitida ajena habilita Liquidar en la interfaz."""
        profile = make_client_profile()
        income = make_income(client=profile)
        account = _collection_account_for(income, Document.CommercialStatus.ISSUED)
        foreign = make_client_profile()
        changes = {
            'client': {'client_user': foreign.user},
            'project': {'project': Project.objects.create(name='Otro proyecto', client=profile.user)},
        }
        Document.objects.filter(pk=account.pk).update(**changes[mismatch])

        data = IncomeRecordSerializer(income).data

        assert data['can_settle'] is False
        assert data['settlement_blocked_reason'] == (
            'Primero genera y emite una cuenta de cobro para este ingreso.'
        )

    def test_list_eligibility_uses_one_query_for_several_client_incomes(
        self, make_income, make_client_profile, django_assert_num_queries,
    ):
        """Falla si agregar estado y bloqueo introduce consultas por cada ingreso listado."""
        from content.services.accounting_service import collection_account_subqueries, paid_amount_subquery
        profile = make_client_profile()
        issued = make_income(client=profile)
        draft = make_income(client=profile)
        _collection_account_for(issued, Document.CommercialStatus.ISSUED)
        _collection_account_for(draft, Document.CommercialStatus.DRAFT)
        queryset = IncomeRecord.objects.filter(pk__in=[issued.pk, draft.pk]).annotate(
            paid_amount=paid_amount_subquery(), **collection_account_subqueries(),
        ).select_related('client__user', 'project').order_by('pk')

        with django_assert_num_queries(1):
            data = IncomeRecordSerializer(queryset, many=True).data

        assert [row['can_settle'] for row in data] == [True, False]


class TestAccountingChangeDisplay:
    def test_vat_changes_are_projected_as_percentages_without_rewriting_money(self):
        """Falla si IVA vuelve a mostrarse como COP o si un importe deja de conservar su moneda."""
        log = AccountingChangeLog(
            entity_type=AccountingChangeLog.EntityType.INCOME,
            object_id=1,
            object_repr='Ingreso Litigio',
            action=AccountingChangeLog.Action.UPDATED,
            changes=[
                {'field': 'vat_rate', 'label': 'IVA', 'old': '$19', 'new': '19 %'},
                {'field': 'total_amount', 'label': 'Valor', 'old': '$100.000', 'new': '$119.000'},
            ],
        )

        changes = AccountingChangeLogSerializer(log).data['changes']

        assert changes[0] == {
            'field': 'vat_rate', 'label': 'IVA', 'old': '19 %', 'new': '19 %',
        }
        assert changes[1] == {
            'field': 'total_amount', 'label': 'Valor', 'old': '$100.000', 'new': '$119.000',
        }


def income_payload(**overrides):
    payload = {
        'concept': 'Tendalux - Inicio 40%',
        'kind': 'expected',
        'period_date': '2026-01',
        'total_amount': '1280000.00',
        # Required since Aug 2026: nothing new lands unclassified.
        'origin': 'development',
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestPeriodHandling:
    def test_accepts_year_month_and_normalizes_to_day_one(self):
        serializer = IncomeRecordCreateUpdateSerializer(data=income_payload())
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['period_date'] == date(2026, 1, 1)

    def test_full_date_keeps_the_exact_payment_day(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(period_date='2026-03-15'),
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['period_date'] == date(2026, 3, 15)

    def test_exact_day_shows_up_in_the_period_label(self, make_income):
        income = make_income(period_date=date(2026, 7, 17))
        data = IncomeRecordSerializer(income).data
        assert data['period'] == '2026-07'
        assert data['period_label'] == '17 Julio 2026'

    def test_invalid_month_is_rejected(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(period_date='2026-13'),
        )
        assert not serializer.is_valid()
        assert 'period_date' in serializer.errors

    def test_read_serializer_emits_period_and_spanish_label(self, make_income):
        income = make_income(period_date=date(2026, 3, 1))
        data = IncomeRecordSerializer(income).data
        assert data['period'] == '2026-03'
        assert data['period_label'] == 'Marzo 2026'
        assert data['company_amount'] == '0.00'


@pytest.mark.django_db
class TestPartnerSplitDefaults:
    def test_create_defaults_to_half_and_half(self):
        serializer = IncomeRecordCreateUpdateSerializer(data=income_payload())
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['gustavo_amount'] == Decimal('640000.00')
        assert serializer.validated_data['carlos_amount'] == Decimal('640000.00')

    @pytest.mark.parametrize('total', ['101.00', '100.01'])
    def test_odd_remainder_stays_with_the_company(self, total):
        # Whole-peso halves, the same split the panel shows: the odd peso and
        # any cent stay with ProjectApp instead of going to one partner.
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(total_amount=total),
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['gustavo_amount'] == Decimal('50.00')
        assert serializer.validated_data['carlos_amount'] == Decimal('50.00')

    def test_explicit_split_is_preserved(self):
        serializer = ExpenseRecordCreateUpdateSerializer(data={
            'concept': 'Windsurf',
            'period_date': '2026-03',
            'total_amount': '3000000.00',
            'gustavo_amount': '1000000.00',
            'carlos_amount': '2000000.00',
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['gustavo_amount'] == Decimal('1000000.00')

    def test_split_over_total_is_rejected_in_spanish(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(
                gustavo_amount='700000.00', carlos_amount='700000.00',
            ),
        )
        assert not serializer.is_valid()
        assert 'socios' in str(serializer.errors)

    def test_negative_amount_is_rejected(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(gustavo_amount='-1.00'),
        )
        assert not serializer.is_valid()
        assert 'gustavo_amount' in serializer.errors


@pytest.mark.django_db
class TestPersonalLedger:
    def test_personal_ledger_normalizes_split_to_owner(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(
                ledger='gustavo',
                gustavo_amount='100.00', carlos_amount='200.00',
            ),
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['gustavo_amount'] == Decimal('1280000.00')
        assert serializer.validated_data['carlos_amount'] == Decimal('0')

    def test_personal_ledger_without_split_assigns_owner(self):
        serializer = ExpenseRecordCreateUpdateSerializer(data={
            'concept': 'Aporte Carro Onix',
            'period_date': '2026-06',
            'ledger': 'carlos',
            'total_amount': '3000000.00',
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['carlos_amount'] == Decimal('3000000.00')
        assert serializer.validated_data['gustavo_amount'] == Decimal('0')

    def test_patch_to_personal_ledger_renormalizes_split(self, make_income):
        income = make_income(
            total_amount=Decimal('100.00'),
            gustavo_amount=Decimal('50.00'),
            carlos_amount=Decimal('50.00'),
        )
        serializer = IncomeRecordCreateUpdateSerializer(
            income, data={'ledger': 'gustavo'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['gustavo_amount'] == Decimal('100.00')
        assert serializer.validated_data['carlos_amount'] == Decimal('0')

    def test_patch_amount_on_personal_record_renormalizes(self, make_income):
        income = make_income(
            ledger=IncomeRecord.Ledger.CARLOS,
            total_amount=Decimal('100.00'),
            gustavo_amount=Decimal('0.00'),
            carlos_amount=Decimal('100.00'),
        )
        serializer = IncomeRecordCreateUpdateSerializer(
            income, data={'total_amount': '250.00'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['carlos_amount'] == Decimal('250.00')
        assert serializer.validated_data['gustavo_amount'] == Decimal('0')

    def test_personal_expense_from_pocket_becomes_company_draw(self):
        # Money that leaves the pocket is company money: a personal
        # expense with the pocket toggle on converts into a company
        # expense fully assigned to its owner, so it reduces the company
        # utility instead of silently draining the pocket.
        serializer = ExpenseRecordCreateUpdateSerializer(data={
            'concept': 'Gasolina Carronis',
            'period_date': '2026-07',
            'ledger': 'gustavo',
            'total_amount': '200000.00',
            'register_in_pocket': True,
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['ledger'] == 'company'
        assert serializer.validated_data['gustavo_amount'] == Decimal('200000.00')
        assert serializer.validated_data['carlos_amount'] == Decimal('0')

    def test_personal_expense_outside_pocket_stays_personal(self):
        serializer = ExpenseRecordCreateUpdateSerializer(data={
            'concept': 'Mercado',
            'period_date': '2026-07',
            'ledger': 'gustavo',
            'total_amount': '90000.00',
            'register_in_pocket': False,
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['ledger'] == 'gustavo'
        assert serializer.validated_data['gustavo_amount'] == Decimal('90000.00')

    def test_personal_income_cannot_target_pocket(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(
                kind='liquid', destination='pocket', ledger='gustavo',
            ),
        )
        assert not serializer.is_valid()
        assert 'personales' in str(serializer.errors)

    def test_expected_income_link_must_share_ledger(self, make_income):
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED,
            ledger=IncomeRecord.Ledger.GUSTAVO,
            total_amount=Decimal('100.00'),
            gustavo_amount=Decimal('100.00'),
            carlos_amount=Decimal('0.00'),
        )
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(kind='liquid', expected_income=expected.pk),
        )
        assert not serializer.is_valid()
        assert 'contabilidad' in str(serializer.errors)

    def test_read_serializer_exposes_ledger_label(self, make_income):
        income = make_income(
            ledger=IncomeRecord.Ledger.GUSTAVO,
            total_amount=Decimal('100.00'),
            gustavo_amount=Decimal('100.00'),
            carlos_amount=Decimal('0.00'),
        )
        data = IncomeRecordSerializer(income).data
        assert data['ledger'] == 'gustavo'
        assert data['ledger_label'] == 'Personal Gustavo'


@pytest.mark.django_db
class TestIncomeRules:
    def test_pocket_destination_requires_liquid_kind(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(kind='expected', destination='pocket'),
        )
        assert not serializer.is_valid()
        assert 'líquidos' in str(serializer.errors)

    def test_pocket_destination_allowed_for_liquid(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(kind='liquid', destination='pocket'),
        )
        assert serializer.is_valid(), serializer.errors

    def test_expected_income_link_must_point_to_expected_record(
        self, make_income,
    ):
        liquid = make_income(kind=IncomeRecord.Kind.LIQUID)
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(kind='liquid', expected_income=liquid.pk),
        )
        assert not serializer.is_valid()
        assert 'expected_income' in serializer.errors

    def test_pocket_destination_rejected_for_lost_kind(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(kind='lost', destination='pocket'),
        )
        assert not serializer.is_valid()
        assert 'líquidos' in str(serializer.errors)

    def test_expected_without_payments_can_be_written_off(self, make_income):
        expected = make_income(kind=IncomeRecord.Kind.EXPECTED)
        serializer = IncomeRecordCreateUpdateSerializer(
            expected, data={'kind': 'lost'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_expected_with_payments_cannot_be_written_off(self, make_income):
        """Writing it off would strand the liquid child and skew received_pct."""
        expected = make_income(kind=IncomeRecord.Kind.EXPECTED)
        make_income(
            kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('400000.00'),
            gustavo_amount=Decimal('200000.00'),
            carlos_amount=Decimal('200000.00'),
            expected_income=expected,
        )
        serializer = IncomeRecordCreateUpdateSerializer(
            expected, data={'kind': 'lost'}, partial=True,
        )
        assert not serializer.is_valid()
        assert 'ya tiene liquidaciones' in str(serializer.errors)

    def test_expected_with_only_a_lost_child_can_still_be_written_off(
        self, make_income,
    ):
        expected = make_income(kind=IncomeRecord.Kind.EXPECTED)
        make_income(kind=IncomeRecord.Kind.LOST, expected_income=expected)
        serializer = IncomeRecordCreateUpdateSerializer(
            expected, data={'kind': 'lost'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestZeroAmountPocketGuard:
    """PocketMovement.amount requires >= 0.01; the sync writers bypass model
    validators, so the boundary serializers must reject zero-amount records
    that would mirror a movement."""

    def expense_payload(self, **overrides):
        payload = {
            'concept': 'Ajuste',
            'period_date': '2026-02',
            'total_amount': '0.00',
        }
        payload.update(overrides)
        return payload

    def test_zero_expense_with_pocket_default_is_rejected(self):
        serializer = ExpenseRecordCreateUpdateSerializer(
            data=self.expense_payload(),
        )
        assert not serializer.is_valid()
        assert 'total_amount' in serializer.errors

    def test_zero_expense_without_pocket_is_valid(self):
        serializer = ExpenseRecordCreateUpdateSerializer(
            data=self.expense_payload(register_in_pocket=False),
        )
        assert serializer.is_valid(), serializer.errors

    def test_linked_expense_cannot_be_updated_to_zero(self, make_expense):
        movement = PocketMovement.objects.create(
            concept='Claude Code 20x',
            movement_date=date(2026, 3, 1),
            direction=PocketMovement.Direction.OUT,
            amount=Decimal('800000.00'),
        )
        expense = make_expense(pocket_movement=movement)
        serializer = ExpenseRecordCreateUpdateSerializer(
            expense,
            data={
                'total_amount': '0.00',
                'gustavo_amount': '0.00',
                'carlos_amount': '0.00',
            },
            partial=True,
        )
        assert not serializer.is_valid()
        assert 'total_amount' in serializer.errors

    def test_unlinked_expense_can_be_updated_to_zero(self, make_expense):
        expense = make_expense()
        serializer = ExpenseRecordCreateUpdateSerializer(
            expense,
            data={
                'total_amount': '0.00',
                'gustavo_amount': '0.00',
                'carlos_amount': '0.00',
            },
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_zero_liquid_pocket_income_is_rejected(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(
                kind='liquid', destination='pocket', total_amount='0.00',
            ),
        )
        assert not serializer.is_valid()
        assert 'total_amount' in serializer.errors

    def test_zero_partners_income_remains_valid(self):
        serializer = IncomeRecordCreateUpdateSerializer(
            data=income_payload(
                kind='liquid', destination='partners', total_amount='0.00',
            ),
        )
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestIncomePaymentState:
    def test_payment_state_at_the_three_boundaries(self, make_income):
        cases = [
            (Decimal('0.00'), 'pending', '0.00', '1000000.00'),
            (Decimal('400000.00'), 'partial', '400000.00', '600000.00'),
            (Decimal('1000000.00'), 'paid', '1000000.00', '0.00'),
        ]
        for paid, status, paid_repr, pending_repr in cases:
            expected = make_income(
                kind=IncomeRecord.Kind.EXPECTED,
                total_amount=Decimal('1000000.00'),
            )
            if paid:
                make_income(
                    kind=IncomeRecord.Kind.LIQUID, total_amount=paid,
                    gustavo_amount=Decimal('0'), carlos_amount=Decimal('0'),
                    expected_income=expected,
                )
            data = IncomeRecordSerializer(expected).data
            assert data['payment_status'] == status
            assert data['paid_amount'] == paid_repr
            assert data['pending_amount'] == pending_repr

    def test_non_expected_rows_report_no_payment_state(self, make_income):
        for kind in (IncomeRecord.Kind.LIQUID, IncomeRecord.Kind.LOST):
            data = IncomeRecordSerializer(make_income(kind=kind)).data
            assert data['payment_status'] is None
            assert data['paid_amount'] is None
            assert data['pending_amount'] is None


@pytest.mark.django_db
class TestEntityDefaults:
    def test_hosting_payment_per_cycle_defaults_from_modality(self, make_client_profile):
        serializer = HostingRecordCreateUpdateSerializer(data={
            'client': make_client_profile().pk,
            'client_name': 'German - Kore',
            'monthly_value': '91667.00',
            'payment_modality': HostingRecord.Modality.SEMIANNUAL,
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['payment_per_cycle'] == Decimal('550002.00')

    def test_hosting_validity_range_is_checked(self, make_client_profile):
        serializer = HostingRecordCreateUpdateSerializer(data={
            'client': make_client_profile().pk,
            'client_name': 'X',
            'monthly_value': '100.00',
            'valid_from': '2026-09-02',
            'valid_to': '2026-03-02',
        })
        assert not serializer.is_valid()
        assert 'vigencia' in str(serializer.errors)

    def test_hosting_requires_a_client_on_create_only(self, make_client_profile):
        create = HostingRecordCreateUpdateSerializer(data={
            'client_name': 'X', 'monthly_value': '100.00',
        })
        assert not create.is_valid()
        assert 'client' in create.errors

        # An existing record with no client must stay editable while it is
        # completed — requiring it there would make it unsavable.
        legacy = HostingRecord.objects.create(
            client_name='Legacy', monthly_value=Decimal('100.00'),
        )
        edit = HostingRecordCreateUpdateSerializer(
            legacy, data={'notes': 'al día'}, partial=True,
        )
        assert edit.is_valid(), edit.errors

    def test_hosting_snapshot_is_filled_from_the_client(self, make_client_profile):
        profile = make_client_profile(company='Acme SAS', nit='901234567')
        serializer = HostingRecordCreateUpdateSerializer(data={
            'client': profile.pk, 'monthly_value': '100.00',
        })

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['client_name'] == 'Acme SAS'
        assert serializer.validated_data['client_email'] == profile.user.email
        assert serializer.validated_data['client_identification'] == '901234567'

    def test_recurring_cop_equivalent_is_derived_from_cop_price(self):
        serializer = RecurringPaymentCreateUpdateSerializer(data={
            'name': 'Netflix',
            'price': '39800.00',
            'currency': RecurringPayment.Currency.COP,
        })
        assert serializer.is_valid(), serializer.errors
        payment = serializer.save()
        assert payment.cop_equivalent == Decimal('39800.00')

    def test_recurring_supplied_cop_equivalent_cannot_override_usd_rate(self):
        serializer = RecurringPaymentCreateUpdateSerializer(data={
            'name': 'Claude Code 20x',
            'price': '200.00',
            'currency': RecurringPayment.Currency.USD,
            'cop_equivalent': '1.00',
        })
        assert serializer.is_valid(), serializer.errors
        payment = serializer.save()
        assert payment.cop_equivalent == Decimal('800000.00')

    def test_pocket_movement_amount_must_be_positive(self):
        serializer = PocketMovementCreateUpdateSerializer(data={
            'concept': 'Ajuste',
            'movement_date': '2026-06-01',
            'direction': 'in',
            'amount': '0.00',
        })
        assert not serializer.is_valid()
        assert 'amount' in serializer.errors


@pytest.mark.django_db
class TestSettingsSerializer:
    def test_rejects_an_out_of_range_usd_rate(self):
        serializer = AccountingSettingsSerializer(data={'usd_exchange_rate': '0'})
        assert not serializer.is_valid()
        assert 'usd_exchange_rate' in serializer.errors

    def test_accepts_the_master_switch(self):
        serializer = AccountingSettingsSerializer(data={
            'notifications_enabled': True,
        })
        assert serializer.is_valid(), serializer.errors

    def test_ignores_a_recipient_list_sent_by_an_old_client(self):
        """Recipients moved to their own catalog; the key must not resurface."""
        serializer = AccountingSettingsSerializer(data={
            'notification_recipients': ['gustavo@test.com'],
            'notifications_enabled': True,
        })

        assert serializer.is_valid(), serializer.errors
        assert 'notification_recipients' not in serializer.validated_data


@pytest.mark.django_db
class TestNotificationRecipientSerializer:
    @pytest.fixture(autouse=True)
    def _drop_seeded_recipients(self, db):
        """Migration 0191 seeds two inboxes into every fresh test database."""
        NotificationRecipient.objects.all().delete()

    def test_normalizes_case_and_whitespace(self):
        serializer = NotificationRecipientCreateUpdateSerializer(
            data={'email': '  Carlos18BP@Gmail.COM '},
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['email'] == 'carlos18bp@gmail.com'

    def test_rejects_a_duplicate_ignoring_case(self):
        NotificationRecipient.objects.create(email='team@projectapp.co')

        serializer = NotificationRecipientCreateUpdateSerializer(
            data={'email': 'TEAM@ProjectApp.co'},
        )

        assert not serializer.is_valid()
        assert serializer.errors['email'] == ['Ese correo ya está en la lista.']

    def test_a_row_does_not_collide_with_itself_on_update(self):
        row = NotificationRecipient.objects.create(email='ana@test.com')

        serializer = NotificationRecipientCreateUpdateSerializer(
            row, data={'email': 'ana@test.com'}, partial=True,
        )

        assert serializer.is_valid(), serializer.errors

    def test_rejects_a_malformed_address(self):
        serializer = NotificationRecipientCreateUpdateSerializer(
            data={'email': 'no-es-un-correo'},
        )

        assert not serializer.is_valid()
        assert 'email' in serializer.errors


@pytest.mark.django_db
class TestCardSnapshotDebtComputation:
    """Debt is server-computed (cupo − disponible) for catalog cards."""

    CARD = 'T.C Test 01'

    def _card(self, **overrides):
        from content.models import CreditCard

        defaults = {
            'name': self.CARD,
            'credit_limit': Decimal('8000000.00'),
            'statements_since': date(2026, 5, 1),
        }
        defaults.update(overrides)
        return CreditCard.objects.create(**defaults)

    def test_catalog_card_computes_debt_and_ignores_client_value(self):
        self._card()
        serializer = CardBalanceSnapshotCreateUpdateSerializer(data={
            'snapshot_date': '2026-07-10',
            'card_name': self.CARD,
            'available_amount': '3000000.00',
            'debt_amount': '1.00',
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['debt_amount'] == Decimal('5000000.00')

    def test_available_over_limit_is_rejected(self):
        self._card()
        serializer = CardBalanceSnapshotCreateUpdateSerializer(data={
            'snapshot_date': '2026-07-10',
            'card_name': self.CARD,
            'available_amount': '9000000.00',
        })
        assert not serializer.is_valid()
        assert 'available_amount' in serializer.errors

    def test_non_catalog_card_requires_explicit_debt_on_create(self):
        payload = {
            'snapshot_date': '2026-07-10',
            'card_name': 'T.C Legacy',
            'available_amount': '3000000.00',
        }
        serializer = CardBalanceSnapshotCreateUpdateSerializer(data=payload)
        assert not serializer.is_valid()
        assert 'debt_amount' in serializer.errors

        serializer = CardBalanceSnapshotCreateUpdateSerializer(
            data={**payload, 'debt_amount': '1200000.00'},
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['debt_amount'] == Decimal('1200000.00')

    def test_notes_only_update_keeps_stored_debt(self):
        from content.models import CardBalanceSnapshot

        card = self._card()
        snapshot = CardBalanceSnapshot.objects.create(
            snapshot_date=date(2026, 6, 1),
            card_name=self.CARD,
            available_amount=Decimal('3000000.00'),
            debt_amount=Decimal('5000000.00'),
        )
        # The cupo changed after the snapshot was written: a notes-only
        # edit must not rewrite the historic debt.
        card.credit_limit = Decimal('10000000.00')
        card.save(update_fields=['credit_limit'])

        serializer = CardBalanceSnapshotCreateUpdateSerializer(
            snapshot, data={'notes': 'revisado'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        snapshot.refresh_from_db()
        assert snapshot.debt_amount == Decimal('5000000.00')

    def test_available_change_recomputes_with_current_cupo(self):
        from content.models import CardBalanceSnapshot

        self._card()
        snapshot = CardBalanceSnapshot.objects.create(
            snapshot_date=date(2026, 6, 1),
            card_name=self.CARD,
            available_amount=Decimal('3000000.00'),
            debt_amount=Decimal('5000000.00'),
        )
        serializer = CardBalanceSnapshotCreateUpdateSerializer(
            snapshot, data={'available_amount': '2000000.00'}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['debt_amount'] == Decimal('6000000.00')


class TestDeductionWriteGuard:
    """Deductions are born in the settlement flow only: manual writes may
    neither set nor clear the type, and a deduction never gains a pocket
    movement."""

    def payload(self, **overrides):
        payload = {
            'concept': 'Comisión suelta',
            'period_date': '2026-02',
            'total_amount': '8000.00',
            'gustavo_amount': '4000.00',
            'carlos_amount': '4000.00',
        }
        payload.update(overrides)
        return payload

    def test_manual_create_with_deduction_type_is_rejected(self):
        serializer = ExpenseRecordCreateUpdateSerializer(
            data=self.payload(deduction_type='gateway_fee'),
        )
        assert not serializer.is_valid()
        assert 'deduction_type' in serializer.errors

    def test_settlement_context_may_set_deduction_type(self):
        serializer = ExpenseRecordCreateUpdateSerializer(
            data=self.payload(
                deduction_type='gateway_fee', register_in_pocket=False,
            ),
            context={'settlement': True},
        )
        assert serializer.is_valid(), serializer.errors

    def test_manual_clear_of_deduction_type_is_rejected(self, make_expense):
        deduction = make_expense(deduction_type='gateway_fee')

        serializer = ExpenseRecordCreateUpdateSerializer(
            deduction, data={'deduction_type': ''}, partial=True,
        )

        assert not serializer.is_valid()
        assert 'deduction_type' in serializer.errors

    def test_editing_a_deduction_forces_the_pocket_flag_off(self, make_expense):
        deduction = make_expense(deduction_type='gateway_fee')

        serializer = ExpenseRecordCreateUpdateSerializer(
            deduction,
            data={
                'total_amount': '9000.00',
                'gustavo_amount': '4500.00',
                'carlos_amount': '4500.00',
                'register_in_pocket': True,
            },
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['register_in_pocket'] is False


class TestDeductionReadFields:
    def test_exposes_source_income_and_its_concept(self, make_income, make_expense):
        income = make_income()
        deduction = make_expense(
            deduction_type='gateway_fee', source_income=income,
        )

        data = ExpenseRecordSerializer(deduction).data

        assert data['source_income'] == income.pk
        assert data['source_income_concept'] == income.concept

    def test_ordinary_expense_has_null_source(self, make_expense):
        data = ExpenseRecordSerializer(make_expense()).data

        assert data['source_income'] is None
        assert data['source_income_concept'] is None


@pytest.mark.django_db
class TestPocketMovementAllocations:
    """The reparto of an abono, read from the movement side."""

    def _movement(self, amount='800000.00'):
        return PocketMovement.objects.create(
            concept='Abono Kore',
            movement_date=date(2026, 8, 15),
            direction=PocketMovement.Direction.IN,
            amount=Decimal(amount),
        )

    def _child(self, movement, make_income, concept, amount, parent=None):
        return make_income(
            concept=concept, kind=IncomeRecord.Kind.LIQUID,
            destination=IncomeRecord.Destination.POCKET,
            total_amount=Decimal(amount),
            gustavo_amount=Decimal('0'), carlos_amount=Decimal('0'),
            expected_income=parent, pocket_movement=movement,
        )

    def test_a_shared_movement_lists_every_allocation(self, make_income):
        movement = self._movement()
        parent = make_income(concept='Kore - Fase 2')
        self._child(movement, make_income, 'Kore - Fase 2', '500000.00', parent)
        self._child(movement, make_income, 'Kore - Fase 3', '300000.00')

        data = PocketMovementSerializer(movement).data

        assert data['linked_income_id'] is None
        assert data['linked_ledger'] == 'company'
        assert data['is_auto_managed'] is True
        assert [entry['amount'] for entry in data['allocations']] == [
            '500000.00', '300000.00',
        ]
        assert data['allocations'][0]['expected_income_id'] == parent.pk

    def test_a_single_child_movement_keeps_the_linked_id(self, make_income):
        movement = self._movement(amount='500000.00')
        child = self._child(movement, make_income, 'Kore', '500000.00')

        data = PocketMovementSerializer(movement).data

        assert data['linked_income_id'] == child.pk
        assert len(data['allocations']) == 1

    def test_an_unlinked_movement_has_an_empty_reparto(self):
        data = PocketMovementSerializer(self._movement()).data

        assert data['allocations'] == []
        assert data['linked_income_id'] is None

    def test_the_list_prefetch_keeps_the_queries_flat(
        self, make_income, django_assert_num_queries,
    ):
        for index in range(3):
            movement = self._movement()
            self._child(
                movement, make_income, f'Kore {index}', '100000.00',
            )
            self._child(
                movement, make_income, f'Kore bis {index}', '700000.00',
            )

        queryset = PocketMovement.objects.select_related(
            'expense_record',
        ).prefetch_related('income_records')
        with django_assert_num_queries(2):
            data = PocketMovementSerializer(queryset, many=True).data
        assert len(data) == 3
        assert all(len(row['allocations']) == 2 for row in data)

    def test_the_income_side_reports_the_same_reparto_as_the_pocket_side(
        self, make_income,
    ):
        """Both serializers render the reparto through `allocation_entries`.

        They feed the same panel modal from opposite directions, so a shape
        that drifts on one side breaks the other silently.
        """
        movement = self._movement()
        parent = make_income(concept='Kore - Fase 2')
        self._child(movement, make_income, 'Kore - Fase 2', '500000.00', parent)
        self._child(movement, make_income, 'Kore - Fase 3', '300000.00')

        from_pocket = PocketMovementSerializer(movement).data['allocations']
        from_income = SettlementMovementSerializer(movement).data['allocations']

        assert from_income == from_pocket
        assert len(from_income) == 2

    def test_the_settlement_view_of_a_movement_counts_its_allocations(
        self, make_income,
    ):
        shared = self._movement()
        self._child(shared, make_income, 'Kore - Fase 2', '500000.00')
        self._child(shared, make_income, 'Kore - Fase 3', '300000.00')
        alone = self._movement(amount='500000.00')
        self._child(alone, make_income, 'Kore suelto', '500000.00')

        shared_data = SettlementMovementSerializer(shared).data
        alone_data = SettlementMovementSerializer(alone).data

        assert shared_data['is_shared'] is True
        assert shared_data['allocation_count'] == 2
        assert shared_data['amount'] == '800000.00'
        assert alone_data['is_shared'] is False
        assert alone_data['allocation_count'] == 1

    def test_the_settlement_view_never_touches_the_expense_side(
        self, make_income, django_assert_num_queries,
    ):
        """No `expense_record` read, so the income detail needs no join for it.

        The full PocketMovementSerializer would cost one query per row here
        (reverse OneToOne), for a link that is structurally always NULL on an
        incoming movement.
        """
        movement = self._movement()
        self._child(movement, make_income, 'Kore - Fase 2', '500000.00')
        self._child(movement, make_income, 'Kore - Fase 3', '300000.00')

        queryset = PocketMovement.objects.prefetch_related('income_records')
        with django_assert_num_queries(2):
            data = SettlementMovementSerializer(queryset, many=True).data

        assert [row['allocation_count'] for row in data] == [2]
        assert 'linked_expense_id' not in data[0]
