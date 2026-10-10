"""API tests for accounting income/expense endpoints."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from content.models import AccountingChangeLog, Document, DocumentType, ExpenseRecord, IncomeRecord
from content.services import accounting_service


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


def income_payload(**overrides):
    payload = {
        'concept': 'Kore - Inicio 40%',
        'kind': 'expected',
        'period_date': '2026-02',
        'total_amount': '1160000.00',
        # Required since Aug 2026: nothing new lands unclassified.
        'origin': 'development',
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestAccountingEndpointAuth:
    def test_staff_non_superuser_gets_403(self, admin_client):
        assert admin_client.get('/api/accounting/incomes/').status_code == 403
        assert admin_client.post(
            '/api/accounting/incomes/create/', income_payload(), format='json',
        ).status_code == 403

    def test_anonymous_is_rejected(self, api_client):
        response = api_client.get('/api/accounting/incomes/')
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestIncomeCrud:
    def test_create_returns_201_with_default_split(self, super_client):
        response = super_client.post(
            '/api/accounting/incomes/create/', income_payload(), format='json',
        )
        assert response.status_code == 201, response.data
        assert response.data['gustavo_amount'] == '580000.00'
        assert response.data['carlos_amount'] == '580000.00'
        assert response.data['period'] == '2026-02'
        assert AccountingChangeLog.objects.filter(
            entity_type='income', action='created',
        ).exists()

    def test_create_with_invalid_split_returns_400(self, super_client):
        response = super_client.post(
            '/api/accounting/incomes/create/',
            income_payload(
                gustavo_amount='700000.00', carlos_amount='700000.00',
            ),
            format='json',
        )
        assert response.status_code == 400

    def test_create_without_a_business_line_is_rejected(self, super_client):
        """The origin decides the shape of the record, so it is not optional.

        Leaving it open is what filled the book with rows nothing can
        duplicate faithfully: a copy can only carry a line of business the
        original recorded.
        """
        payload = income_payload()
        del payload['origin']

        response = super_client.post(
            '/api/accounting/incomes/create/', payload, format='json',
        )

        assert response.status_code == 400
        assert 'origin' in response.data

    def test_create_with_a_blank_business_line_is_rejected(self, super_client):
        response = super_client.post(
            '/api/accounting/incomes/create/',
            income_payload(origin=''),
            format='json',
        )

        assert response.status_code == 400
        assert 'origin' in response.data

    def test_blanking_the_business_line_on_an_edit_is_rejected(
        self, super_client, make_income,
    ):
        income = make_income(origin=IncomeRecord.Origin.DEVELOPMENT)

        response = super_client.patch(
            f'/api/accounting/incomes/{income.pk}/update/',
            {'origin': ''},
            format='json',
        )

        assert response.status_code == 400
        assert 'origin' in response.data

    def test_an_edit_that_does_not_touch_the_line_leaves_a_legacy_row_alone(
        self, super_client, make_income,
    ):
        """The rule reaches what is being written, not what is already stored.

        Most of the book predates the field; making every PATCH re-classify
        its row would block editing the amount of an unclassified income. The
        panel form always sends the origin, so classifying happens there.
        """
        income = make_income(origin='')

        response = super_client.patch(
            f'/api/accounting/incomes/{income.pk}/update/',
            {'concept': 'Kore v2 (Fase 1) - Inicio 40% (ajustado)'},
            format='json',
        )

        assert response.status_code == 200, response.data
        income.refresh_from_db()
        assert income.origin == ''

    def test_list_returns_results_and_meta(self, super_client, make_income):
        make_income()
        response = super_client.get('/api/accounting/incomes/')
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert 'meta' in response.data

    def test_retrieve_update_delete_flow(self, super_client, make_income):
        income = make_income()
        detail = super_client.get(f'/api/accounting/incomes/{income.pk}/')
        assert detail.status_code == 200

        update = super_client.patch(
            f'/api/accounting/incomes/{income.pk}/update/',
            {'total_amount': '2000000.00', 'gustavo_amount': '1000000.00',
             'carlos_amount': '1000000.00'},
            format='json',
        )
        assert update.status_code == 200
        assert update.data['total_amount'] == '2000000.00'

        delete = super_client.delete(
            f'/api/accounting/incomes/{income.pk}/delete/',
        )
        assert delete.status_code == 204
        assert not IncomeRecord.objects.filter(pk=income.pk).exists()

    def test_update_missing_record_returns_404(self, super_client):
        response = super_client.patch(
            '/api/accounting/incomes/999/update/', {}, format='json',
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestIncomeFilters:
    @pytest.fixture
    def dataset(self, make_income):
        make_income(
            concept='Kore expected', kind='expected',
            period_date=date(2026, 2, 1), total_amount=Decimal('1000.00'),
            gustavo_amount=Decimal('500.00'), carlos_amount=Decimal('500.00'),
        )
        make_income(
            concept='Kore liquid', kind='liquid',
            period_date=date(2026, 3, 1), total_amount=Decimal('900.00'),
            gustavo_amount=Decimal('0.00'), carlos_amount=Decimal('900.00'),
        )
        make_income(
            concept='Vastago pocket', kind='liquid', destination='pocket',
            period_date=date(2026, 4, 1), total_amount=Decimal('2000.00'),
            gustavo_amount=Decimal('0.00'), carlos_amount=Decimal('0.00'),
        )

    def _concepts(self, response):
        return {row['concept'] for row in response.data['results']}

    def test_filter_by_kind(self, super_client, dataset):
        response = super_client.get('/api/accounting/incomes/?kind=expected')
        assert self._concepts(response) == {'Kore expected'}

    def test_filter_by_partner_gustavo(self, super_client, dataset):
        response = super_client.get(
            '/api/accounting/incomes/?partner=gustavo',
        )
        assert self._concepts(response) == {'Kore expected'}

    def test_filter_by_partner_projectapp(self, super_client, dataset):
        response = super_client.get(
            '/api/accounting/incomes/?partner=projectapp',
        )
        assert self._concepts(response) == {'Vastago pocket'}

    def test_filter_by_date_range(self, super_client, dataset):
        response = super_client.get(
            '/api/accounting/incomes/?date_from=2026-03-01&date_to=2026-03-31',
        )
        assert self._concepts(response) == {'Kore liquid'}

    def test_filter_by_amount_range(self, super_client, dataset):
        response = super_client.get(
            '/api/accounting/incomes/?amount_min=950&amount_max=1500',
        )
        assert self._concepts(response) == {'Kore expected'}

    def test_search_by_concept(self, super_client, dataset):
        response = super_client.get('/api/accounting/incomes/?q=vastago')
        assert self._concepts(response) == {'Vastago pocket'}

    def test_invalid_date_returns_spanish_error(self, super_client):
        response = super_client.get(
            '/api/accounting/incomes/?date_from=not-a-date',
        )
        assert response.status_code == 400
        assert 'fecha' in response.data['error']

    def test_invalid_partner_returns_400(self, super_client):
        response = super_client.get('/api/accounting/incomes/?partner=bob')
        assert response.status_code == 400


@pytest.mark.django_db
class TestExpenseCrudAndFilters:
    def test_create_and_filter_by_category(self, super_client):
        for concept, category in (
            ('Claude Code 20x', 'business'),
            ('Aporte Carro Onix', 'personal'),
        ):
            response = super_client.post(
                '/api/accounting/expenses/create/',
                {
                    'concept': concept,
                    'period_date': '2026-01',
                    'category': category,
                    'total_amount': '100.00',
                },
                format='json',
            )
            assert response.status_code == 201, response.data

        response = super_client.get(
            '/api/accounting/expenses/?category=personal',
        )
        assert [r['concept'] for r in response.data['results']] == [
            'Aporte Carro Onix',
        ]

    def test_update_and_delete(self, super_client, make_expense):
        expense = make_expense()
        update = super_client.patch(
            f'/api/accounting/expenses/{expense.pk}/update/',
            {'concept': 'Windsurf Marzo'},
            format='json',
        )
        assert update.status_code == 200
        assert update.data['concept'] == 'Windsurf Marzo'

        delete = super_client.delete(
            f'/api/accounting/expenses/{expense.pk}/delete/',
        )
        assert delete.status_code == 204
        assert not ExpenseRecord.objects.filter(pk=expense.pk).exists()


@pytest.mark.django_db
class TestIncomeExpenseMeta:
    def test_income_meta_totals_and_top(self, super_client, make_income):
        from content.utils import today_bogota

        today = today_bogota()
        month_start = today.replace(day=1)
        make_income(
            kind=IncomeRecord.Kind.EXPECTED, period_date=month_start,
            total_amount=Decimal('2000.00'),
            gustavo_amount=Decimal('1000.00'), carlos_amount=Decimal('1000.00'),
        )
        make_income(
            concept='Entrega grande', kind=IncomeRecord.Kind.LIQUID,
            period_date=month_start, total_amount=Decimal('1500.00'),
            gustavo_amount=Decimal('750.00'), carlos_amount=Decimal('750.00'),
        )
        response = super_client.get('/api/accounting/incomes/')
        meta = response.data['meta']
        assert meta['expected_total'] == '2000.00'
        assert meta['liquid_total'] == '1500.00'
        assert meta['received_pct'] == 75
        assert meta['current_month_liquid'] == '1500.00'
        assert meta['top_income']['concept'] == 'Entrega grande'

    def test_income_meta_empty_year(self, super_client):
        response = super_client.get('/api/accounting/incomes/')
        meta = response.data['meta']
        assert meta['received_pct'] is None
        assert meta['top_income'] is None

    def test_income_meta_reports_lost_total_without_touching_the_rest(
        self, super_client, make_income,
    ):
        from content.utils import today_bogota

        month_start = today_bogota().replace(day=1)
        make_income(
            kind=IncomeRecord.Kind.EXPECTED, period_date=month_start,
            total_amount=Decimal('2000.00'),
        )
        make_income(
            concept='Entrega grande', kind=IncomeRecord.Kind.LIQUID,
            period_date=month_start, total_amount=Decimal('1000.00'),
        )
        make_income(
            concept='Catherine Ruiz Candles', kind=IncomeRecord.Kind.LOST,
            period_date=month_start, total_amount=Decimal('460000.00'),
        )
        meta = super_client.get('/api/accounting/incomes/').data['meta']
        assert meta['lost_total'] == '460000.00'
        assert meta['expected_total'] == '2000.00'
        assert meta['liquid_total'] == '1000.00'
        assert meta['received_pct'] == 50
        assert meta['top_income']['concept'] == 'Entrega grande'

    def test_meta_counts_an_expected_once_when_it_has_two_liquid_children(
        self, super_client, make_income,
    ):
        """Regression: the paid_amount annotation must not multiply rows.

        A Sum() over the reverse FK would join one row per child and report
        expected_total as 4000.00 here.
        """
        from content.utils import today_bogota

        month_start = today_bogota().replace(day=1)
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED, period_date=month_start,
            total_amount=Decimal('2000.00'),
        )
        for amount in ('500.00', '300.00'):
            make_income(
                concept='Abono', kind=IncomeRecord.Kind.LIQUID,
                period_date=month_start, total_amount=Decimal(amount),
                expected_income=expected,
            )
        meta = super_client.get('/api/accounting/incomes/').data['meta']
        assert meta['expected_total'] == '2000.00'
        assert meta['liquid_total'] == '800.00'


@pytest.mark.django_db
class TestIncomePaymentState:
    def test_expected_row_reports_paid_pending_and_status(
        self, super_client, make_income,
    ):
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED,
            total_amount=Decimal('1000.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, total_amount=Decimal('400.00'),
            expected_income=expected,
        )
        rows = super_client.get('/api/accounting/incomes/').data['results']
        row = next(r for r in rows if r['id'] == expected.id)
        assert row['paid_amount'] == '400.00'
        assert row['pending_amount'] == '600.00'
        assert row['payment_status'] == 'partial'
        assert row['payment_status_label'] == 'Parcial'

    def test_liquid_and_lost_rows_carry_no_payment_state(
        self, super_client, make_income,
    ):
        make_income(kind=IncomeRecord.Kind.LIQUID)
        make_income(kind=IncomeRecord.Kind.LOST)
        rows = super_client.get('/api/accounting/incomes/').data['results']
        for row in rows:
            assert row['paid_amount'] is None
            assert row['pending_amount'] is None
            assert row['payment_status'] is None
            assert row['payment_status_label'] is None

    def test_single_record_endpoint_computes_state_without_the_annotation(
        self, super_client, make_income,
    ):
        """retrieve/create/update serialize a bare instance, not the list qs."""
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED, total_amount=Decimal('1000.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, total_amount=Decimal('1000.00'),
            expected_income=expected,
        )
        row = super_client.get(f'/api/accounting/incomes/{expected.id}/').data
        assert row['paid_amount'] == '1000.00'
        assert row['pending_amount'] == '0.00'
        assert row['payment_status'] == 'paid'

    def test_a_lost_child_is_not_counted_as_payment(
        self, super_client, make_income,
    ):
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED, total_amount=Decimal('1000.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LOST, total_amount=Decimal('1000.00'),
            expected_income=expected,
        )
        row = super_client.get(f'/api/accounting/incomes/{expected.id}/').data
        assert row['paid_amount'] == '0.00'
        assert row['payment_status'] == 'pending'

    def test_overpaid_row_is_paid_and_never_reports_negative_pending(
        self, super_client, make_income,
    ):
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED, total_amount=Decimal('100.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, total_amount=Decimal('900.00'),
            expected_income=expected,
        )
        row = super_client.get(f'/api/accounting/incomes/{expected.id}/').data
        assert row['payment_status'] == 'paid'
        assert row['pending_amount'] == '0.00'

    def test_paid_client_incomes_without_accounts_are_flagged_without_per_row_queries(
        self, super_client, make_client_profile, make_income,
    ):
        """Falla si el aviso de cuenta pendiente usa una consulta extra por cada ingreso pagado del listado."""
        client = make_client_profile()
        first = make_income(
            kind=IncomeRecord.Kind.EXPECTED, client=client,
            total_amount=Decimal('100.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, client=client,
            total_amount=Decimal('100.00'), expected_income=first,
        )

        with CaptureQueriesContext(connection) as one_income:
            one_response = super_client.get('/api/accounting/incomes/')

        first_row = next(row for row in one_response.data['results'] if row['id'] == first.pk)
        second = make_income(
            concept='Entrega segunda', kind=IncomeRecord.Kind.EXPECTED,
            client=client, total_amount=Decimal('100.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, client=client,
            total_amount=Decimal('100.00'), expected_income=second,
        )
        third = make_income(
            concept='Entrega tercera', kind=IncomeRecord.Kind.EXPECTED,
            client=client, total_amount=Decimal('100.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, client=client,
            total_amount=Decimal('100.00'), expected_income=third,
        )
        issued = make_income(
            concept='Entrega facturada', kind=IncomeRecord.Kind.EXPECTED,
            client=client, total_amount=Decimal('100.00'),
        )
        make_income(
            kind=IncomeRecord.Kind.LIQUID, client=client,
            total_amount=Decimal('100.00'), expected_income=issued,
        )
        collection_type = DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0]
        Document.objects.create(
            title='Cuenta emitida', document_type=collection_type,
            commercial_status=Document.CommercialStatus.ISSUED,
            income_record=issued, client_user=client.user,
        )

        with CaptureQueriesContext(connection) as several_incomes:
            several_response = super_client.get('/api/accounting/incomes/')

        rows = {row['id']: row for row in several_response.data['results']}
        assert first_row['requires_collection_account'] is True
        assert rows[first.pk]['requires_collection_account'] is True
        assert rows[second.pk]['requires_collection_account'] is True
        assert rows[third.pk]['requires_collection_account'] is True
        assert rows[issued.pk]['requires_collection_account'] is False
        assert len(several_incomes) <= len(one_income)

    def test_fully_written_off_zero_total_expected_reads_paid(
        self, super_client, make_income,
    ):
        """A residual-only settlement can shrink an expected to zero."""
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED, total_amount=Decimal('0.00'),
            gustavo_amount=Decimal('0.00'), carlos_amount=Decimal('0.00'),
        )
        row = super_client.get(f'/api/accounting/incomes/{expected.id}/').data
        assert row['payment_status'] == 'paid'
        assert row['pending_amount'] == '0.00'

    def test_liquidating_creates_a_linked_liquid_row_and_keeps_the_expected(
        self, super_client, make_income,
    ):
        expected = make_income(
            kind=IncomeRecord.Kind.EXPECTED, period_date=date(2026, 8, 1),
            total_amount=Decimal('1000.00'),
        )
        response = super_client.post(
            '/api/accounting/incomes/create/',
            income_payload(
                kind='liquid', period_date='2026-11',
                total_amount='700.00', expected_income=expected.id,
            ),
            format='json',
        )
        assert response.status_code == 201
        liquid = IncomeRecord.objects.get(id=response.data['id'])
        assert liquid.expected_income_id == expected.id
        assert liquid.period_date == date(2026, 11, 1)
        assert liquid.pocket_movement is None
        expected.refresh_from_db()
        assert expected.kind == IncomeRecord.Kind.EXPECTED
        assert expected.total_amount == Decimal('1000.00')

    def test_expense_meta_totals_split_and_top(self, super_client):
        from content.utils import today_bogota

        today = today_bogota()
        month_start = today.replace(day=1)
        for concept, category, amount in (
            ('Figma', 'business', '300.00'),
            ('Almuerzo', 'personal', '700.00'),
        ):
            ExpenseRecord.objects.create(
                concept=concept, category=category,
                period_date=month_start, total_amount=Decimal(amount),
            )
        response = super_client.get('/api/accounting/expenses/')
        meta = response.data['meta']
        assert meta['year_total'] == '1000.00'
        assert meta['current_month_total'] == '1000.00'
        assert meta['business_total'] == '300.00'
        assert meta['personal_total'] == '700.00'
        assert meta['top_expense']['concept'] == 'Almuerzo'

    def test_expense_meta_alert_triggers_at_150_pct(self, super_client):
        from content.utils import today_bogota

        today = today_bogota()
        if today.month == 1:
            pytest.skip('sin meses previos en enero')
        prior = today.replace(month=today.month - 1, day=1)
        ExpenseRecord.objects.create(
            concept='Mes previo', period_date=prior,
            total_amount=Decimal('100.00'),
        )
        ExpenseRecord.objects.create(
            concept='Mes actual', period_date=today.replace(day=1),
            total_amount=Decimal('150.00'),
        )
        response = super_client.get('/api/accounting/expenses/')
        assert response.data['meta']['current_month_alert'] is True

    def test_expense_meta_alert_off_below_threshold(self, super_client):
        from content.utils import today_bogota

        today = today_bogota()
        if today.month == 1:
            pytest.skip('sin meses previos en enero')
        prior = today.replace(month=today.month - 1, day=1)
        ExpenseRecord.objects.create(
            concept='Mes previo', period_date=prior,
            total_amount=Decimal('100.00'),
        )
        ExpenseRecord.objects.create(
            concept='Mes actual', period_date=today.replace(day=1),
            total_amount=Decimal('149.00'),
        )
        response = super_client.get('/api/accounting/expenses/')
        assert response.data['meta']['current_month_alert'] is False


@pytest.mark.django_db
class TestIncomeSettlementEndpoint:
    """POST /api/accounting/incomes/<id>/settle/ — liquidate + resolve gap."""

    def _expected(self):
        return IncomeRecord.objects.create(
            concept='Kore - Inicio 40%',
            kind=IncomeRecord.Kind.EXPECTED,
            period_date=date(2026, 7, 1),
            total_amount=Decimal('1000000.00'),
            gustavo_amount=Decimal('500000.00'),
            carlos_amount=Decimal('500000.00'),
        )

    def _payload(self, **overrides):
        payload = {
            'concept': 'Kore - Inicio 40%',
            'period_date': '2026-07-15',
            'destination': 'partners',
            'total_amount': '992000.00',
        }
        payload.update(overrides)
        return payload

    def test_an_unclassified_expected_can_still_be_settled(self, super_client):
        """Collecting money is not the moment to classify it.

        `_expected()` builds the production case: a record from before the
        origin existed. Its children copy that blank instead of being refused
        — requiring a line of business here would block Liquidar on most of
        the book, which is a far worse answer than a liquid that is exactly as
        unclassified as what it collects.
        """
        income = self._expected()
        assert income.origin == ''

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(total_amount='1000000.00'),
            format='json',
        )

        assert response.status_code == 201, response.data
        liquid = IncomeRecord.objects.get(expected_income=income)
        assert liquid.origin == ''

    def test_settles_with_a_gateway_fee(self, super_client):
        income = self._expected()

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(deductions=[
                {'type': 'gateway_fee', 'amount': '8000.00'},
            ]),
            format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['income']['payment_status'] == 'paid'
        assert response.data['income']['pending_amount'] == '0.00'
        expense = response.data['expenses'][0]
        assert expense['deduction_type'] == 'gateway_fee'
        assert expense['deduction_type_label'] == 'Comisión plataforma de pago'

    def test_settles_with_a_follow_up_expected_income(self, super_client):
        income = self._expected()

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(
                total_amount='900000.00',
                deductions=[{'type': 'gateway_fee', 'amount': '8000.00'}],
                expected_incomes=[{
                    'concept': 'Kore - Saldo agosto',
                    'period_date': '2026-08',
                    'amount': '92000.00',
                }],
            ),
            format='json',
        )

        assert response.status_code == 201, response.data
        follow_up = response.data['expected_incomes'][0]
        assert follow_up['kind'] == 'expected'
        assert follow_up['period'] == '2026-08'
        assert follow_up['total_amount'] == '92000.00'

    def test_without_allocations_it_matches_the_plain_liquidation(
        self, super_client,
    ):
        income = self._expected()

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(total_amount='1000000.00'),
            format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['expenses'] == []
        income.refresh_from_db()
        assert income.total_amount == Decimal('1000000.00')

    def test_residual_only_settlement_returns_a_null_liquid(self, super_client):
        """Zero received + full deduction closes the parent without a payment."""
        income = self._expected()
        IncomeRecord.objects.create(
            concept='Abono previo',
            kind=IncomeRecord.Kind.LIQUID,
            period_date=date(2026, 7, 5),
            total_amount=Decimal('950000.00'),
            gustavo_amount=Decimal('475000.00'),
            carlos_amount=Decimal('475000.00'),
            expected_income=income,
        )

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(
                total_amount='0',
                deductions=[{'type': 'gateway_fee', 'amount': '50000.00'}],
            ),
            format='json',
        )

        assert response.status_code == 201, response.data
        assert response.data['liquid'] is None
        assert response.data['income']['payment_status'] == 'paid'
        assert response.data['income']['pending_amount'] == '0.00'
        assert len(response.data['expenses']) == 1

    def test_over_allocation_returns_400_in_spanish(self, super_client):
        income = self._expected()

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(deductions=[
                {'type': 'gateway_fee', 'amount': '50000.00'},
            ]),
            format='json',
        )

        assert response.status_code == 400
        assert 'saldo pendiente' in str(response.data)

    def test_other_requires_a_detail(self, super_client):
        income = self._expected()

        response = super_client.post(
            f'/api/accounting/incomes/{income.pk}/settle/',
            self._payload(deductions=[
                {'type': 'other', 'detail': '  ', 'amount': '8000.00'},
            ]),
            format='json',
        )

        assert response.status_code == 400
        assert not ExpenseRecord.objects.exists()

    def test_rejects_a_deduction_missing_its_type(self, super_client):
        # The frontend now starts rows with no concept selected; the contract
        # it leans on is that the server never accepts a typeless deduction.
        income = self._expected()

        for deduction in ({'amount': '8000.00'}, {'type': '', 'amount': '8000.00'}):
            response = super_client.post(
                f'/api/accounting/incomes/{income.pk}/settle/',
                self._payload(deductions=[deduction]),
                format='json',
            )

            assert response.status_code == 400, deduction
        assert not ExpenseRecord.objects.exists()

    def test_unknown_income_returns_404(self, super_client):
        response = super_client.post(
            '/api/accounting/incomes/999999/settle/',
            self._payload(), format='json',
        )
        assert response.status_code == 404

    def test_staff_without_superuser_is_rejected(self, admin_client):
        response = admin_client.post(
            '/api/accounting/incomes/1/settle/', self._payload(), format='json',
        )
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestIncomePaymentStatusFilter:
    """`payment_status` narrows the list the same way the row badge reads.

    The panel filters client-side, but the CSV export reuses these query
    params, so both must agree on what "uncollected" means.
    """

    @pytest.fixture
    def rows(self, make_income):
        untouched = make_income(
            concept='Sin abonos', total_amount=Decimal('1000.00'),
        )
        partial = make_income(
            concept='Abonado a medias', total_amount=Decimal('1000.00'),
        )
        make_income(
            concept='Abono', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('400.00'), expected_income=partial,
        )
        paid = make_income(
            concept='Cobrado', total_amount=Decimal('1000.00'),
        )
        make_income(
            concept='Pago total', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('1000.00'), expected_income=paid,
        )
        return {'untouched': untouched, 'partial': partial, 'paid': paid}

    def _concepts(self, super_client, value):
        response = super_client.get(
            f'/api/accounting/incomes/?payment_status={value}',
        )
        assert response.status_code == 200, response.data
        return sorted(row['concept'] for row in response.data['results'])

    def test_pending_returns_only_expected_without_any_payment(
        self, super_client, rows,
    ):
        assert self._concepts(super_client, 'pending') == ['Sin abonos']

    def test_partial_returns_only_the_half_paid_expected(
        self, super_client, rows,
    ):
        assert self._concepts(super_client, 'partial') == ['Abonado a medias']

    def test_paid_returns_only_the_fully_paid_expected(
        self, super_client, rows,
    ):
        assert self._concepts(super_client, 'paid') == ['Cobrado']

    def test_a_lost_child_keeps_its_parent_pending(
        self, super_client, make_income,
    ):
        """Regression: the subquery only counts liquid children as payment."""
        expected = make_income(
            concept='Con hijo perdido', total_amount=Decimal('1000.00'),
        )
        make_income(
            concept='Perdido', kind=IncomeRecord.Kind.LOST,
            total_amount=Decimal('1000.00'), expected_income=expected,
        )
        assert self._concepts(super_client, 'pending') == ['Con hijo perdido']

    def test_unknown_value_returns_400(self, super_client, rows):
        response = super_client.get(
            '/api/accounting/incomes/?payment_status=cobrado',
        )
        assert response.status_code == 400

    def test_the_export_applies_the_same_filter(self, super_client, rows):
        response = super_client.get(
            '/api/accounting/export/?section=income&payment_status=pending',
        )
        assert response.status_code == 200
        body = response.content.decode('utf-8-sig')
        assert 'Sin abonos' in body
        assert 'Abonado a medias' not in body
        assert 'Cobrado' not in body

    def test_several_statuses_return_their_union(self, super_client, rows):
        """The ficha's case: "lo que falta por cobrar" is pending OR partial.

        Asking for one of them is what made a partially paid record look like
        it had never been created.
        """
        assert self._concepts(super_client, 'pending,partial') == [
            'Abonado a medias', 'Sin abonos',
        ]

    def test_partial_and_paid_leave_out_the_untouched_row(
        self, super_client, rows,
    ):
        assert self._concepts(super_client, 'partial,paid') == [
            'Abonado a medias', 'Cobrado',
        ]

    def test_every_status_keeps_liquid_and_lost_rows_out(
        self, super_client, rows,
    ):
        """`expected` is AND-ed around the OR, not one of its branches.

        Inside it, `paid` (paid_amount >= total_amount) would also match a
        liquid row, where both are 0.
        """
        assert self._concepts(super_client, 'pending,partial,paid') == [
            'Abonado a medias', 'Cobrado', 'Sin abonos',
        ]

    def test_all_is_not_a_cut(self, super_client, rows):
        response = super_client.get('/api/accounting/incomes/?payment_status=all')
        assert response.status_code == 200
        # Every row, the liquid children included.
        assert len(response.data['results']) == 5

    def test_an_unknown_value_inside_a_list_still_returns_400(
        self, super_client, rows,
    ):
        response = super_client.get(
            '/api/accounting/incomes/?payment_status=pending,cobrado',
        )
        assert response.status_code == 400

    def test_a_zero_total_expected_reads_as_paid_not_pending(
        self, super_client, make_income,
    ):
        """A settlement that closes a record at total 0 is collected.

        `payment_status_for` has always called it 'paid'; the SQL side used to
        answer 'pending' for the same row, so the badge and the export
        disagreed.
        """
        make_income(concept='Cerrado en cero', total_amount=Decimal('0.00'))
        assert self._concepts(super_client, 'pending') == []
        assert self._concepts(super_client, 'paid') == ['Cerrado en cero']

    def test_the_export_applies_a_multi_value_filter(self, super_client, rows):
        response = super_client.get(
            '/api/accounting/export/'
            '?section=income&payment_status=pending,partial',
        )
        assert response.status_code == 200
        body = response.content.decode('utf-8-sig')
        assert 'Sin abonos' in body
        assert 'Abonado a medias' in body
        assert 'Cobrado' not in body


@pytest.mark.django_db
class TestExpenseDeductionSurface:
    """The Gastos list can isolate and totalize deductions by type."""

    def _seed(self, make_income, make_expense):
        income = make_income(concept='Hosting Jimmy Junio')
        make_expense(concept='Hosting mensual')
        make_expense(
            concept='Comisión — Hosting Jimmy Junio',
            deduction_type='gateway_fee',
            source_income=income,
            total_amount=Decimal('4854.00'),
            gustavo_amount=Decimal('2427.00'),
            carlos_amount=Decimal('2427.00'),
        )
        make_expense(
            concept='Retención — Kore',
            deduction_type='withholding',
            total_amount=Decimal('70000.00'),
            gustavo_amount=Decimal('35000.00'),
            carlos_amount=Decimal('35000.00'),
        )
        return income

    def test_list_filters_by_deduction_type_with_csv_multi(
        self, super_client, make_income, make_expense,
    ):
        self._seed(make_income, make_expense)

        response = super_client.get(
            '/api/accounting/expenses/?deduction_type=gateway_fee,withholding',
        )

        concepts = {row['concept'] for row in response.data['results']}
        assert concepts == {
            'Comisión — Hosting Jimmy Junio', 'Retención — Kore',
        }

    def test_rows_carry_the_annotated_source_income_concept(
        self, super_client, make_income, make_expense,
    ):
        income = self._seed(make_income, make_expense)

        response = super_client.get('/api/accounting/expenses/')

        by_concept = {
            row['concept']: row for row in response.data['results']
        }
        deduction = by_concept['Comisión — Hosting Jimmy Junio']
        assert deduction['source_income'] == income.pk
        assert deduction['source_income_concept'] == 'Hosting Jimmy Junio'
        assert by_concept['Hosting mensual']['source_income'] is None

    def test_meta_totalizes_deductions_by_type(
        self, super_client, make_income, make_expense,
    ):
        self._seed(make_income, make_expense)

        response = super_client.get('/api/accounting/expenses/')

        meta = response.data['meta']
        assert meta['deductions_total'] == '74854.00'
        assert meta['deductions_by_type'] == {
            'gateway_fee': '4854.00',
            'withholding': '70000.00',
        }
