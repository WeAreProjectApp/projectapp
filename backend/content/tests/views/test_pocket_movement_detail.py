"""Behavior contracts for the on-demand pocket movement detail."""
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from content.models import ExpenseRecord, IncomeRecord, Ledger, McpConnector, PocketMovement


DETAIL_URL = '/api/accounting/pocket/{record_id}/'


def make_movement(**overrides):
    fields = {
        'concept': 'Movimiento de bolsillo',
        'movement_date': date(2026, 10, 7),
        'direction': PocketMovement.Direction.IN,
        'amount': Decimal('100.00'),
    }
    fields.update(overrides)
    return PocketMovement.objects.create(**fields)


def company_movement(make_income, make_expense):
    movement = make_movement(concept='Ingreso Empresa')
    make_income(
        concept='Ingreso Empresa',
        kind=IncomeRecord.Kind.LIQUID,
        ledger=Ledger.COMPANY,
        total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('0.00'),
        carlos_amount=Decimal('0.00'),
        pocket_movement=movement,
    )
    return movement


def gustavo_movement(make_income, make_expense):
    movement = make_movement(concept='Retiro Gustavo', direction=PocketMovement.Direction.OUT)
    make_expense(ledger=Ledger.GUSTAVO, pocket_movement=movement)
    return movement


def carlos_movement(make_income, make_expense):
    movement = make_movement(concept='Retiro Carlos', direction=PocketMovement.Direction.OUT)
    make_expense(ledger=Ledger.CARLOS, pocket_movement=movement)
    return movement


def unlinked_movement(make_income, make_expense):
    return make_movement(concept='Movimiento histórico')


def detail(client, movement, query=''):
    return client.get(DETAIL_URL.format(record_id=movement.pk) + query)


def activate_accounting_connector():
    connector, _ = McpConnector.objects.get_or_create(
        slug='accounting', defaults={'name': 'Contabilidad'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def call_get_pocket(api_client, token, record_id):
    return api_client.post(
        f'/api/mcp/accounting/{token}/',
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'get_pocket',
                'arguments': {'record_id': record_id},
            },
        },
        format='json',
    )


@pytest.fixture
def allocated_abono(make_income, make_expense):
    paid_parent = make_income(
        concept='Fase liquidada', total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
    )
    partial_parent = make_income(
        concept='Fase parcial', total_amount=Decimal('500.00'),
        gustavo_amount=Decimal('250.00'), carlos_amount=Decimal('250.00'),
    )
    movement = make_movement(concept='Abono Kore', amount=Decimal('300.00'))
    exact_child = make_income(
        concept='Liquidación Fase liquidada', kind=IncomeRecord.Kind.LIQUID,
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('0.00'),
        carlos_amount=Decimal('0.00'), expected_income=paid_parent,
        pocket_movement=movement,
    )
    partial_child = make_income(
        concept='Liquidación Fase parcial', kind=IncomeRecord.Kind.LIQUID,
        total_amount=Decimal('200.00'), gustavo_amount=Decimal('0.00'),
        carlos_amount=Decimal('0.00'), expected_income=partial_parent,
        pocket_movement=movement,
    )
    later_movement = make_movement(concept='Abono posterior', amount=Decimal('100.00'))
    make_income(
        concept='Abono posterior Fase parcial', kind=IncomeRecord.Kind.LIQUID,
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('0.00'),
        carlos_amount=Decimal('0.00'), expected_income=partial_parent,
        pocket_movement=later_movement,
    )
    make_expense(
        concept='Comisión Fase parcial', total_amount=Decimal('50.00'),
        gustavo_amount=Decimal('0.00'), carlos_amount=Decimal('0.00'),
        source_income=partial_parent,
        deduction_type=ExpenseRecord.DeductionType.GATEWAY_FEE,
    )
    return movement, [
        {
            'income_id': exact_child.pk,
            'expected_income_id': paid_parent.pk,
            'concept': 'Fase liquidada',
            'amount': '100.00',
            'pending_amount': '0.00',
            'is_credit': False,
        },
        {
            'income_id': partial_child.pk,
            'expected_income_id': partial_parent.pk,
            'concept': 'Fase parcial',
            'amount': '200.00',
            'pending_amount': '150.00',
            'is_credit': False,
        },
    ]


pytestmark = pytest.mark.django_db


class TestPocketMovementDetail:
    @pytest.mark.parametrize(
        ('factory', 'expected'),
        [
            pytest.param(company_movement, 'company', id='empresa'),
            pytest.param(gustavo_movement, 'gustavo', id='gustavo'),
            pytest.param(carlos_movement, 'carlos', id='carlos'),
            pytest.param(unlinked_movement, None, id='sin-vincular'),
        ],
    )
    def test_detail_exposes_the_movement_owner(
        self, super_client, make_income, make_expense, factory, expected,
    ):
        """Falla si el detalle deja de identificar Empresa, Gustavo, Carlos o ningún dueño."""
        movement = factory(make_income, make_expense)

        response = detail(super_client, movement)

        assert response.status_code == 200, response.data
        assert response.data['linked_ledger'] == expected

    def test_detail_uses_real_chronology_for_balance_despite_list_filters(self, super_client):
        """Falla si el saldo del detalle usa el filtro de tabla o ignora centavos en empates."""
        first = make_movement(concept='Primero', amount=Decimal('100.10'))
        target = make_movement(
            concept='Objetivo', direction=PocketMovement.Direction.OUT,
            amount=Decimal('25.05'),
        )
        last = make_movement(concept='Después', amount=Decimal('1.00'))
        tied_time = timezone.make_aware(datetime(2026, 10, 7, 12, 0, 0))
        PocketMovement.objects.filter(pk__in=[first.pk, target.pk, last.pk]).update(
            created_at=tied_time,
        )

        response = detail(
            super_client, target, '?attribution=gustavo&date_to=2026-10-01',
        )

        assert response.status_code == 200, response.data
        assert response.data['running_balance'] == '75.05'

    def test_detail_describes_the_linked_expense_and_category(
        self, super_client, make_expense,
    ):
        """Falla si un egreso vinculado pierde su acceso identificable o categoría legible."""
        movement = make_movement(
            concept='Licencia anual', direction=PocketMovement.Direction.OUT,
        )
        expense = make_expense(
            concept='Licencia anual', category=ExpenseRecord.Category.PERSONAL,
            pocket_movement=movement,
        )

        response = detail(super_client, movement)

        assert response.status_code == 200, response.data
        assert response.data['linked_record_detail'] == {
            'type': 'expense', 'id': expense.pk, 'concept': 'Licencia anual',
            'category_label': 'Personal',
        }

    def test_detail_shows_exact_and_partial_allocations_with_current_pending(
        self, super_client, allocated_abono,
    ):
        """Falla si el reparto omite un abono posterior o una deducción del pendiente actual."""
        movement, expected_allocations = allocated_abono

        response = detail(super_client, movement)

        assert response.status_code == 200, response.data
        assert response.data['allocation_details'] == expected_allocations

    def test_detail_marks_an_unparented_abono_child_as_credit(
        self, super_client, make_income,
    ):
        """Falla si el saldo a favor de un abono deja de distinguirse de una imputación."""
        movement = make_movement(concept='Abono con excedente', amount=Decimal('75.00'))
        credit = make_income(
            concept='Saldo a favor', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('75.00'), gustavo_amount=Decimal('0.00'),
            carlos_amount=Decimal('0.00'), pocket_movement=movement,
            source_ref='abono:saldo-a-favor',
        )

        response = detail(super_client, movement)

        assert response.status_code == 200, response.data
        assert response.data['allocation_details'] == [{
            'income_id': credit.pk,
            'expected_income_id': None,
            'concept': 'Saldo a favor',
            'amount': '75.00',
            'pending_amount': None,
            'is_credit': True,
        }]

    def test_detail_additions_do_not_bloat_the_pocket_list(self, super_client):
        """Falla si los campos exclusivos del detalle se filtran a cada fila del listado."""
        movement = make_movement()

        list_response = super_client.get('/api/accounting/pocket/')
        detail_response = detail(super_client, movement)

        assert list_response.status_code == 200, list_response.data
        assert detail_response.status_code == 200, detail_response.data
        assert 'running_balance' not in list_response.data['results'][0]
        assert 'linked_record_detail' not in list_response.data['results'][0]
        assert 'allocation_details' not in list_response.data['results'][0]
        assert detail_response.data['running_balance'] == '100.00'
        assert detail_response.data['allocation_details'] == []

    def test_detail_rejects_staff_without_superuser_permission(self, admin_client):
        """Falla si una cuenta de personal sin permiso puede consultar el detalle financiero."""
        response = admin_client.get(DETAIL_URL.format(record_id=999999))

        assert response.status_code == 403

    def test_detail_returns_404_for_an_absent_movement(self, super_client):
        """Falla si un identificador inexistente deja de devolver el error de recurso ausente."""
        response = super_client.get(DETAIL_URL.format(record_id=999999))

        assert response.status_code == 404

    def test_mcp_get_pocket_matches_the_panel_detail(self, super_client):
        """Falla si MCP deja de entregar el mismo detalle enriquecido que el panel."""
        movement = make_movement(concept='Mismo contrato', amount=Decimal('176120.00'))
        token = activate_accounting_connector()

        panel_response = detail(super_client, movement)
        response = call_get_pocket(super_client, token, movement.pk)

        assert panel_response.status_code == 200, panel_response.data
        assert response.data['result']['isError'] is False
        mcp_payload = json.loads(response.data['result']['content'][0]['text'])
        assert mcp_payload == panel_response.data

    def test_detail_query_count_does_not_grow_with_allocation_count(
        self, super_client, make_income,
    ):
        """Falla si abrir un reparto grande añade una consulta por cada ingreso imputado."""
        small = make_movement(concept='Abono pequeño')
        small_parent = make_income(concept='Padre pequeño')
        make_income(
            concept='Hijo pequeño', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('100.00'), gustavo_amount=Decimal('0.00'),
            carlos_amount=Decimal('0.00'), expected_income=small_parent,
            pocket_movement=small,
        )
        large = make_movement(concept='Abono grande')
        first_parent = make_income(concept='Padre grande 1')
        second_parent = make_income(concept='Padre grande 2')
        third_parent = make_income(concept='Padre grande 3')
        make_income(
            concept='Hijo grande 1', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('100.00'), gustavo_amount=Decimal('0.00'),
            carlos_amount=Decimal('0.00'), expected_income=first_parent,
            pocket_movement=large,
        )
        make_income(
            concept='Hijo grande 2', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('100.00'), gustavo_amount=Decimal('0.00'),
            carlos_amount=Decimal('0.00'), expected_income=second_parent,
            pocket_movement=large,
        )
        make_income(
            concept='Hijo grande 3', kind=IncomeRecord.Kind.LIQUID,
            total_amount=Decimal('100.00'), gustavo_amount=Decimal('0.00'),
            carlos_amount=Decimal('0.00'), expected_income=third_parent,
            pocket_movement=large,
        )

        with CaptureQueriesContext(connection) as small_queries:
            small_response = detail(super_client, small)
        with CaptureQueriesContext(connection) as large_queries:
            large_response = detail(super_client, large)

        assert small_response.status_code == large_response.status_code == 200
        assert len(large_queries) == len(small_queries)
