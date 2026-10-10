"""Tests for the Accounting MCP connector HTTP endpoint."""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.mcp.accounting_tools import ACCOUNTING_TOOLS
from content.models import (
    AccountingSettings,
    AdsSpendRecord,
    IncomeRecord,
    McpConnector,
    NotificationRecipient,
    RecurringPayment,
)
from content.serializers.accounting import AccountingSettingsSerializer
from content.services import accounting_service


@pytest.fixture
def accounting_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='accounting', defaults={'name': 'Contabilidad'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


@pytest.fixture
def mcp_superuser(db, django_user_model):
    """A superuser so mcp_actor() can attribute accounting writes."""
    return django_user_model.objects.create_user(
        username='mcp_acc_actor', password='x', is_staff=True, is_superuser=True,
    )


def _url(token):
    return f'/api/mcp/accounting/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(
        _url(token), _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


@pytest.mark.django_db
class TestAccountingMcpToolList:
    def test_exposes_per_ledger_and_non_crud_tools(self, api_client, accounting_connector):
        """The compatibility endpoint retains its accounting actions plus controls."""
        _, token = accounting_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = [t['name'] for t in response.data['result']['tools']]
        # 8 entities × 5 CRUD + 15 non-CRUD + 15 statement tools + 5 expected-income tools + 3 controls.
        assert len(names) == 78
        for expected in (
            'list_income', 'create_expense', 'delete_pocket', 'get_hosting',
            'update_recurring', 'get_dashboard', 'list_change_logs',
            'get_receivables',
            'get_settings', 'update_settings', 'mute_income',
            'get_income_detail', 'settle_income', 'bulk_settle_incomes',
            'get_statement_instructions',
            'create_statement', 'resolve_merchants', 'finalize_statement',
            'list_notification_recipient', 'create_notification_recipient',
            'update_notification_recipient', 'delete_notification_recipient',
            'get_recurring_duplicate_draft', 'set_recurring_active',
            'archive_recurring', 'restore_recurring', 'mute_recurring',
            'bulk_action_recurring',
            'list_expected_incomes', 'get_expected_income', 'update_expected_income',
            'create_expected_income', 'duplicate_expected_income',
            'describe_capabilities', 'confirm_action', 'cancel_action',
        ):
            assert expected in names

    def test_source_registry_keeps_accounting_actions(self):
        assert len(ACCOUNTING_TOOLS) == 70


@pytest.mark.django_db
class TestAccountingMcpCrud:
    def test_create_income_attributed_to_actor(self, api_client, accounting_connector, mcp_superuser):
        connector, token = accounting_connector
        response = _call(api_client, token, 'create_income', {
            'concept': 'Kore v2 anticipo',
            'kind': 'liquid',
            'period_date': '2026-04',
            'total_amount': '1000000',
            # Required since Aug 2026 — creating from the chat classifies a new
            # record just like the panel form does.
            'origin': 'development',
        })
        assert response.data['result']['isError'] is False
        record = IncomeRecord.objects.get(concept='Kore v2 anticipo')
        credential = connector.credentials.select_related('actor').get(label='Default')
        assert credential.actor_id != mcp_superuser.id
        assert credential.actor.username == 'mcp_accounting'
        assert credential.actor.has_usable_password() is False
        assert record.created_by_id == credential.actor_id

    def test_create_income_without_a_business_line_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        """Creating from the chat classifies, so it is held to the same rule.

        Only settling is exempt, and for a reason that does not apply here:
        its children copy the origin of a parent that may predate the field,
        while this creates a record with nothing to copy from.
        """
        _, token = accounting_connector
        response = _call(api_client, token, 'create_income', {
            'concept': 'Sin línea', 'kind': 'liquid',
            'period_date': '2026-04', 'total_amount': '1000',
        })
        result = response.data['result']
        assert result['isError'] is True
        assert 'origin' in result['content'][0]['text']
        assert not IncomeRecord.objects.filter(concept='Sin línea').exists()

    def test_create_income_bootstraps_service_actor_without_human_superuser(
        self, api_client, accounting_connector,
    ):
        connector, token = accounting_connector
        response = _call(api_client, token, 'create_income', {
            'concept': 'Sin actor', 'kind': 'liquid',
            'period_date': '2026-04', 'total_amount': '1000',
            'origin': 'development',
        })
        assert response.data['result']['isError'] is False
        credential = connector.credentials.select_related('actor').get(label='Default')
        assert credential.actor.username == 'mcp_accounting'
        assert credential.actor.has_usable_password() is False
        record = IncomeRecord.objects.get(concept='Sin actor')
        assert record.created_by_id == credential.actor_id

    def test_list_income_filters_by_q(self, api_client, accounting_connector, make_income):
        make_income(concept='Alfa ingreso')
        make_income(concept='Beta ingreso')
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {'q': 'Alfa'})
        text = response.data['result']['content'][0]['text']
        assert 'Alfa ingreso' in text
        assert 'Beta ingreso' not in text

    def test_update_income(self, api_client, accounting_connector, make_income, mcp_superuser):
        record = make_income(concept='Original')
        _, token = accounting_connector
        response = _call(api_client, token, 'update_income', {
            'record_id': record.id, 'concept': 'Editado',
        })
        assert response.data['result']['isError'] is False
        record.refresh_from_db()
        assert record.concept == 'Editado'

    def test_get_missing_record_errors(self, api_client, accounting_connector):
        _, token = accounting_connector
        response = _call(api_client, token, 'get_income', {'record_id': 999999})
        assert response.data['result']['isError'] is True


@pytest.mark.django_db
class TestAccountingMcpNonCrud:
    def test_dashboard(self, api_client, accounting_connector, make_income):
        make_income(concept='X', period_date=__import__('datetime').date(2026, 3, 1))
        _, token = accounting_connector
        response = _call(api_client, token, 'get_dashboard', {'year': 2026})
        assert response.data['result']['isError'] is False

    def test_receivables_returns_manual_green_total(
        self, api_client, accounting_connector, make_income,
    ):
        make_income(
            total_amount=Decimal('1234.00'),
            is_receivable_candidate=True,
            collection_confidence=IncomeRecord.CollectionConfidence.HIGH,
        )

        response = _call(
            api_client, accounting_connector[1], 'get_receivables', {},
        )

        payload = _payload(response)
        assert payload['summary']['high_total'] == '1234'

    def test_update_income_preserves_manual_receivable_selection(
        self, api_client, accounting_connector, make_income,
    ):
        income = make_income()

        response = _call(api_client, accounting_connector[1], 'update_income', {
            'record_id': income.pk,
            'collection_confidence': 'medium',
        })

        assert response.data['result']['isError'] is False
        income.refresh_from_db()
        assert income.is_receivable_candidate is False
        assert income.collection_confidence == 'medium'

    def test_get_settings(self, api_client, accounting_connector, accounting_settings):
        _, token = accounting_connector
        response = _call(api_client, token, 'get_settings', {})
        text = response.data['result']['content'][0]['text']
        assert 'notifications_enabled' in text


def _payload(response):
    return json.loads(response.data['result']['content'][0]['text'])


def _make_recurring(**overrides):
    fields = {
        'name': 'Figma equipo',
        'price': Decimal('270000.00'),
        'frequency': RecurringPayment.Frequency.QUARTERLY,
        'cycle_anchor_date': date(2026, 7, 17),
        'is_active': True,
    }
    fields.update(overrides)
    return RecurringPayment.objects.create(**fields)


@pytest.mark.django_db
class TestAccountingMcpRecurringLifecycle:
    @pytest.fixture(autouse=True)
    def _mute_notifications(self):
        with patch.object(accounting_service, '_notify'):
            yield

    def test_duplicate_tool_returns_an_unsaved_prefill(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        payment = _make_recurring()

        response = _call(
            api_client, accounting_connector[1],
            'get_recurring_duplicate_draft', {'record_id': payment.pk},
        )

        assert _payload(response)['name'] == 'Figma equipo'
        assert RecurringPayment.objects.count() == 1

    def test_state_tool_deactivates_the_payment(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        payment = _make_recurring()

        response = _call(
            api_client, accounting_connector[1], 'set_recurring_active',
            {'record_id': payment.pk, 'is_active': False},
        )

        assert _payload(response)['is_active'] is False

    def test_archive_tool_preserves_the_record(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        payment = _make_recurring()

        response = _call(
            api_client, accounting_connector[1],
            'archive_recurring', {'record_id': payment.pk},
        )

        assert _payload(response)['is_archived'] is True
        assert RecurringPayment.objects.filter(pk=payment.pk).exists()

    def test_restore_tool_returns_an_inactive_payment(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        payment = _make_recurring(is_active=False, is_archived=True)

        response = _call(
            api_client, accounting_connector[1],
            'restore_recurring', {'record_id': payment.pk},
        )

        payload = _payload(response)
        assert payload['is_archived'] is False
        assert payload['is_active'] is False

    def test_mute_tool_silences_the_payment(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        payment = _make_recurring()

        response = _call(
            api_client, accounting_connector[1], 'mute_recurring',
            {'record_id': payment.pk, 'muted': True},
        )

        assert _payload(response)['reminders_effectively_muted'] is True

    def test_bulk_tool_applies_one_transactional_action(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        first = _make_recurring(name='Figma')
        second = _make_recurring(name='Notion')

        response = _call(
            api_client, accounting_connector[1], 'bulk_action_recurring',
            {'recurring_ids': [first.pk, second.pk], 'action': 'deactivate'},
        )

        assert _payload(response)['updated'] == 2
        assert not RecurringPayment.objects.filter(is_active=True).exists()


@pytest.mark.django_db
class TestAccountingMcpHandlerBranches:
    @pytest.fixture(autouse=True)
    def _mute_notifications(self):
        with patch.object(accounting_service, '_notify'):
            yield

    def test_get_income_returns_record(
        self, api_client, accounting_connector, make_income,
    ):
        record = make_income(concept='Visible')
        _, token = accounting_connector
        response = _call(api_client, token, 'get_income', {'record_id': record.id})
        assert _payload(response)['concept'] == 'Visible'

    def test_create_income_invalid_payload_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'create_income', {
            'concept': 'Malo', 'kind': 'liquid',
            'period_date': '2026-04', 'total_amount': 'no-numero',
            # The invalid field under test is the amount; the rest is valid so
            # the assertion cannot pass on a different rejection.
            'origin': 'development',
        })
        result = response.data['result']
        assert result['isError'] is True
        assert 'Datos inválidos' in result['content'][0]['text']

    def test_update_income_without_fields_errors(
        self, api_client, accounting_connector, make_income, mcp_superuser,
    ):
        record = make_income(concept='Quieto')
        _, token = accounting_connector
        response = _call(api_client, token, 'update_income', {'record_id': record.id})
        assert response.data['result']['isError'] is True

    def test_update_income_invalid_payload_errors(
        self, api_client, accounting_connector, make_income, mcp_superuser,
    ):
        record = make_income(concept='Quieto')
        _, token = accounting_connector
        response = _call(api_client, token, 'update_income', {
            'record_id': record.id, 'total_amount': 'no-numero',
        })
        assert response.data['result']['isError'] is True

    def test_delete_income_removes_record(
        self, api_client, accounting_connector, make_income, mcp_superuser,
    ):
        record = make_income(concept='Borrable')
        _, token = accounting_connector
        response = _call(api_client, token, 'delete_income', {'record_id': record.id})
        assert _payload(response)['deleted'] is True
        assert not IncomeRecord.objects.filter(pk=record.pk).exists()

    def test_list_income_coerces_bool_and_skips_none_params(
        self, api_client, accounting_connector, make_income,
    ):
        make_income(concept='Filtrable', period_date=date(2026, 3, 1))
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {
            'year': 2026, 'q': None, 'solo_demo': True,
        })
        assert _payload(response)['count'] == 1

    def test_list_income_invalid_year_errors(self, api_client, accounting_connector):
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {'year': 'no-año'})
        assert response.data['result']['isError'] is True

    def test_list_ads_includes_accumulated(self, api_client, accounting_connector):
        AdsSpendRecord.objects.create(
            spend_date=date(2026, 3, 5), origin_card='T.C 0655',
            amount='150000',
        )
        _, token = accounting_connector
        response = _call(api_client, token, 'list_ads', {})
        results = _payload(response)['results']
        assert len(results) == 1
        assert 'accumulated' in results[0]

    def test_dashboard_invalid_year_errors(self, api_client, accounting_connector):
        _, token = accounting_connector
        response = _call(api_client, token, 'get_dashboard', {'year': 'no-año'})
        assert response.data['result']['isError'] is True

    def test_change_logs_list_and_filter_by_entity(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _call(api_client, token := accounting_connector[1], 'create_income', {
            'concept': 'Log gen', 'kind': 'liquid',
            'period_date': '2026-04', 'total_amount': '5000',
            'origin': 'development',
        })
        response = _call(api_client, token, 'list_change_logs', {
            'entity_type': 'income', 'action': 'created', 'page': 1,
        })
        payload = _payload(response)
        assert payload['count'] >= 1
        assert payload['page'] == 1

    def test_change_logs_invalid_date_errors(self, api_client, accounting_connector):
        _, token = accounting_connector
        response = _call(api_client, token, 'list_change_logs', {
            'date_from': 'no-fecha',
        })
        assert response.data['result']['isError'] is True

    def test_change_logs_invalid_page_falls_back_to_one(
        self, api_client, accounting_connector,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'list_change_logs', {'page': 'xx'})
        assert _payload(response)['page'] == 1

    def test_create_notification_recipient(
        self, api_client, accounting_connector, mcp_superuser, accounting_settings,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'create_notification_recipient', {
            'email': 'socios@x.com',
        })
        assert response.data['result']['isError'] is False
        assert NotificationRecipient.objects.filter(
            email='socios@x.com', is_active=True,
        ).exists()

    def test_create_notification_recipient_rejects_duplicate(
        self, api_client, accounting_connector, mcp_superuser, accounting_settings,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_notification_recipient', {
            'email': 'socios@x.com',
        })
        response = _call(api_client, token, 'create_notification_recipient', {
            'email': 'SOCIOS@x.com',
        })
        assert response.data['result']['isError'] is True
        assert NotificationRecipient.objects.filter(email='socios@x.com').count() == 1

    def test_update_settings_invalid_payload_errors(
        self, api_client, accounting_connector, mcp_superuser, accounting_settings,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'update_settings', {
            'overdue_reminder_frequency': 'cada-rato',
        })
        assert response.data['result']['isError'] is True

    def test_update_settings_changes_income_view_mode(
        self, api_client, accounting_connector, mcp_superuser, accounting_settings,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'update_settings', {
            'income_default_view_mode': 'classic',
        })
        assert response.data['result']['isError'] is False
        assert AccountingSettings.load().income_default_view_mode == 'classic'

    def test_update_settings_changes_collection_grouping(
        self, api_client, accounting_connector, mcp_superuser, accounting_settings,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'update_settings', {
            'collection_accounts_group_by': 'project',
        })

        assert response.data['result']['isError'] is False
        assert AccountingSettings.load().collection_accounts_group_by == 'project'

    def test_update_settings_schema_declares_every_editable_field(self):
        """The declared schema drifted behind the serializer once (it listed
        3 of 6 editable fields); pin them to each other so it cannot again."""
        tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'update_settings')
        properties = tool['input_schema']['properties']
        editable = set(AccountingSettingsSerializer.Meta.fields) - {'updated_at'}
        assert set(properties) == editable
        assert properties['income_default_view_mode']['enum'] == ['classic', 'grouped']
        assert properties['collection_accounts_view_mode']['enum'] == ['classic', 'grouped']
        assert properties['collection_accounts_group_by']['enum'] == ['client', 'project']


@pytest.mark.django_db
class TestAccountingMcpPocketGuardrails:
    """Auto-managed pocket movements (income/expense-backed) must stay locked
    on the MCP surface exactly like the panel — accounting_tools.py:17-18
    documents this guardrail but nothing exercised it until now.
    """

    def _create_liquid_pocket_income(self, api_client, token):
        response = _call(api_client, token, 'create_income', {
            'concept': 'Pago bolsillo directo',
            'kind': 'liquid',
            'destination': 'pocket',
            'period_date': '2026-04',
            'total_amount': '250000',
            'origin': 'development',
        })
        assert response.data['result']['isError'] is False
        record = IncomeRecord.objects.get(concept='Pago bolsillo directo')
        assert record.pocket_movement_id is not None
        return record

    def test_update_pocket_rejects_direction_flip_on_linked_movement(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        """Catches a refactor that drops _ensure_pocket_update_allowed's
        direction lock (accounting_service.py:288-299), letting an AI agent
        silently flip a linked movement in/out and desync it from its income.
        """
        _, token = accounting_connector
        record = self._create_liquid_pocket_income(api_client, token)
        movement = record.pocket_movement
        assert movement.direction == 'in'

        response = _call(api_client, token, 'update_pocket', {
            'record_id': movement.id, 'direction': 'out',
        })

        result = response.data['result']
        assert result['isError'] is True
        assert 'no se puede cambiar' in result['content'][0]['text']
        movement.refresh_from_db()
        assert movement.direction == 'in'

    def test_delete_pocket_cascades_to_linked_income_record(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        """Catches an AI agent silently deleting a real income record via
        delete_pocket without the cascade actually running (or without
        actually running at all) — accounting_service.py:392-426.
        """
        _, token = accounting_connector
        record = self._create_liquid_pocket_income(api_client, token)
        movement_id = record.pocket_movement_id

        response = _call(api_client, token, 'delete_pocket', {'record_id': movement_id})

        assert response.data['result']['isError'] is False
        assert not IncomeRecord.objects.filter(pk=record.id).exists()
        from content.models import PocketMovement

        assert not PocketMovement.objects.filter(pk=movement_id).exists()


@pytest.mark.django_db
class TestAccountingMcpPaymentStatusFilter:
    """list_income exposes the collection-state filter the panel already has."""

    def _seed(self, make_income):
        from decimal import Decimal

        pending = make_income(concept='Esperado sin pagos')
        paid = make_income(concept='Esperado pagado')
        make_income(
            concept='Pago total', kind=IncomeRecord.Kind.LIQUID,
            expected_income=paid,
        )
        partial = make_income(concept='Esperado parcial')
        make_income(
            concept='Abono inicial', kind=IncomeRecord.Kind.LIQUID,
            expected_income=partial,
            total_amount=Decimal('400000.00'),
            gustavo_amount=Decimal('200000.00'),
            carlos_amount=Decimal('200000.00'),
        )
        return pending, paid, partial

    def test_list_income_pending_returns_only_uncollected_expected(
        self, api_client, accounting_connector, make_income,
    ):
        self._seed(make_income)
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {'payment_status': 'pending'})
        text = response.data['result']['content'][0]['text']
        assert 'Esperado sin pagos' in text
        assert 'Esperado pagado' not in text
        assert 'Esperado parcial' not in text

    def test_list_income_paid_returns_only_settled_expected(
        self, api_client, accounting_connector, make_income,
    ):
        self._seed(make_income)
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {'payment_status': 'paid'})
        payload = json.loads(response.data['result']['content'][0]['text'])
        assert [row['concept'] for row in payload['results']] == ['Esperado pagado']

    def test_list_income_partial_rows_carry_annotated_amounts(
        self, api_client, accounting_connector, make_income,
    ):
        self._seed(make_income)
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {'payment_status': 'partial'})
        payload = json.loads(response.data['result']['content'][0]['text'])
        assert [row['concept'] for row in payload['results']] == ['Esperado parcial']
        row = payload['results'][0]
        assert row['payment_status'] == 'partial'
        assert row['paid_amount'] == '400000.00'
        assert row['pending_amount'] == '600000.00'

    def test_list_income_rejects_unknown_payment_status(
        self, api_client, accounting_connector,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'list_income', {'payment_status': 'settled'})
        assert response.data['result']['isError'] is True

    def test_list_income_accepts_several_statuses_at_once(
        self, api_client, accounting_connector, make_income,
    ):
        """The cut the panel's landing tab makes: everything still uncollected."""
        self._seed(make_income)
        _, token = accounting_connector
        response = _call(
            api_client, token, 'list_income', {'payment_status': 'pending,partial'},
        )
        payload = json.loads(response.data['result']['content'][0]['text'])
        assert sorted(row['concept'] for row in payload['results']) == [
            'Esperado parcial', 'Esperado sin pagos',
        ]

    def test_list_income_rejects_an_unknown_value_inside_a_list(
        self, api_client, accounting_connector,
    ):
        _, token = accounting_connector
        response = _call(
            api_client, token, 'list_income', {'payment_status': 'pending,settled'},
        )
        assert response.data['result']['isError'] is True

    def test_income_schema_gates_payment_status_to_income_only(self):
        income_tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'list_income')
        expense_tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'list_expense')
        prop = income_tool['input_schema']['properties']['payment_status']
        # A plain string, not an enum: the filter takes one or several tokens
        # separated by commas, and `_str_params` would stringify a real list as
        # "['pending', 'partial']". The vocabulary lives in the description.
        assert prop['type'] == 'string'
        assert 'enum' not in prop
        for token in ('pending', 'partial', 'paid'):
            assert token in prop['description']
        assert 'payment_status' not in expense_tool['input_schema']['properties']

    def test_partner_schema_also_takes_several_values(self):
        income_tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'list_income')
        prop = income_tool['input_schema']['properties']['partner']
        assert prop['type'] == 'string'
        assert 'enum' not in prop
        for token in ('gustavo', 'carlos', 'projectapp'):
            assert token in prop['description']


@pytest.mark.django_db
class TestAccountingMcpPocketFilters:
    """list_pocket exposes the attribution + linkage cuts the panel has.

    They ride the shared filter layer, so the tool inherits them; the schema
    branch is what makes them discoverable.
    """

    def _seed(self, make_expense):
        from datetime import date
        from decimal import Decimal

        from content.models import PocketMovement

        draw = PocketMovement.objects.create(
            concept='Retiro Gustavo', movement_date=date(2026, 6, 1),
            direction=PocketMovement.Direction.OUT,
            amount=Decimal('300000.00'),
        )
        make_expense(
            pocket_movement=draw, category='personal',
            gustavo_amount=Decimal('800000.00'),
            carlos_amount=Decimal('0.00'),
        )
        PocketMovement.objects.create(
            concept='Movimiento viejo', movement_date=date(2026, 6, 2),
            direction=PocketMovement.Direction.OUT,
            amount=Decimal('80000.00'),
        )

    def test_list_pocket_filters_by_attribution(
        self, api_client, accounting_connector, make_expense,
    ):
        self._seed(make_expense)
        _, token = accounting_connector
        response = _call(api_client, token, 'list_pocket', {'attribution': 'gustavo'})
        payload = json.loads(response.data['result']['content'][0]['text'])
        assert [row['concept'] for row in payload['results']] == ['Retiro Gustavo']

    def test_list_pocket_filters_the_unlinked_movements(
        self, api_client, accounting_connector, make_expense,
    ):
        self._seed(make_expense)
        _, token = accounting_connector
        response = _call(api_client, token, 'list_pocket', {'linked': 'false'})
        payload = json.loads(response.data['result']['content'][0]['text'])
        assert [row['concept'] for row in payload['results']] == ['Movimiento viejo']

    def test_list_pocket_rejects_an_unknown_attribution(
        self, api_client, accounting_connector,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'list_pocket', {'attribution': 'socio'})
        assert response.data['result']['isError'] is True

    def test_schema_gates_the_pocket_filters_to_pocket_only(self):
        pocket_tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'list_pocket')
        income_tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'list_income')
        props = pocket_tool['input_schema']['properties']
        assert 'gustavo' in props['attribution']['description']
        assert 'linked' in props
        assert 'attribution' not in income_tool['input_schema']['properties']


@pytest.mark.django_db
class TestAccountingMcpDeductions:
    """The expense tools see deductions but can never create them."""

    def test_list_expense_filters_by_deduction_type(
        self, api_client, accounting_connector, make_expense,
    ):
        make_expense(concept='Hosting mensual')
        make_expense(
            concept='Comisión Wompi', deduction_type='gateway_fee',
            total_amount=Decimal('4854.00'),
            gustavo_amount=Decimal('2427.00'),
            carlos_amount=Decimal('2427.00'),
        )
        _, token = accounting_connector

        response = _call(api_client, token, 'list_expense', {
            'deduction_type': 'gateway_fee',
        })

        payload = json.loads(response.data['result']['content'][0]['text'])
        assert [row['concept'] for row in payload['results']] == ['Comisión Wompi']

    def test_expense_list_schema_publishes_the_deduction_filter(self):
        tool = next(t for t in ACCOUNTING_TOOLS if t['name'] == 'list_expense')
        assert 'deduction_type' in tool['input_schema']['properties']

    def test_create_expense_with_deduction_type_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector

        response = _call(api_client, token, 'create_expense', {
            'concept': 'Comisión manual',
            'period_date': '2026-07',
            'total_amount': '4854.00',
            'deduction_type': 'gateway_fee',
        })

        assert response.data['result']['isError'] is True
        text = response.data['result']['content'][0]['text']
        assert 'liquidación' in text
