"""Tests for the credit-card statement MCP tools (slug accounting)."""
from decimal import Decimal
from unittest.mock import patch

import pytest

from content.models import (
    CreditCardStatement,
    CreditCardTransaction,
    McpConnector,
    MerchantAlias,
)
from content.services import accounting_service
from content.tests.mcp_confirmation_helpers import call_confirmed, confirmed_payload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mute_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


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
    return django_user_model.objects.create_user(
        username='mcp_stmt_actor', password='x',
        is_staff=True, is_superuser=True,
    )


def _url(token):
    return f'/api/mcp/accounting/{token}/'


def _payload(response):
    return confirmed_payload(response)


def _rpc(method, params, msg_id=1):
    return {
        'jsonrpc': '2.0', 'id': msg_id, 'method': method,
        'params': params,
    }


def _call(api_client, token, name, arguments, msg_id=1):
    return api_client.post(
        _url(token),
        _rpc('tools/call', {'name': name, 'arguments': arguments}, msg_id),
        format='json',
    )


def _call_confirmed(api_client, token, name, arguments):
    return call_confirmed(api_client, _url(token), _rpc, name, arguments)


CREATE_ARGS = {
    'card_name': 'Visa Bancolombia',
    'period_date': '2026-06',
    'purchases_total': 100000,
    'transactions': [
        {
            'transaction_date': '2026-06-05',
            'raw_description': 'PAYU*NETFLIX 990011',
            'amount': 60000,
        },
        {
            'transaction_date': '2026-06-09',
            'raw_description': 'PRIMAX 8811',
            'amount': 40000,
        },
    ],
}


class TestInstructionsTool:
    def test_returns_phases_and_categories_vocab(
        self, api_client, accounting_connector,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'get_statement_instructions', {})
        result = response.data['result']
        assert result['isError'] is False
        payload = _payload(response)
        assert 'FASE 1' in payload['instructions']
        assert 'NUNCA guardes alias sin aprobación' in payload['instructions']
        assert {'value': 'fuel', 'label': 'Gasolina'} in payload['categories']
        assert payload['workflow_version'] >= 1


class TestCreateStatementTool:
    def test_creates_draft_with_transactions(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        connector, token = accounting_connector
        response = _call(api_client, token, 'create_statement', CREATE_ARGS)
        result = response.data['result']
        assert result['isError'] is False, result
        statement = CreditCardStatement.objects.get()
        credential = connector.credentials.select_related('actor').get(label='Default')
        assert statement.status == 'draft'
        assert statement.transactions.count() == 2
        assert credential.actor_id != mcp_superuser.id
        assert credential.actor.username == 'mcp_accounting'
        assert credential.actor.has_usable_password() is False
        assert statement.created_by_id == credential.actor_id

    def test_duplicate_returns_tool_error_with_existing_id(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        response = _call(api_client, token, 'create_statement', CREATE_ARGS)
        result = response.data['result']
        assert result['isError'] is True
        message = result['content'][0]['text']
        assert 'Ya existe un extracto' in message
        assert f'id={CreditCardStatement.objects.get().pk}' in message


class TestResolveAndLearnFlow:
    def test_resolve_save_finalize_roundtrip(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()

        resolve = _call(api_client, token, 'resolve_merchants', {
            'raw_descriptions': ['PAYU*NETFLIX 990011', 'PRIMAX 8811'],
        })
        payload = _payload(resolve)
        assert payload['resolved'] == []
        assert len(payload['unresolved']) == 2

        save = _call(api_client, token, 'save_merchant_aliases', {
            'aliases': [
                {
                    'raw_description': 'PAYU*NETFLIX 990011',
                    'merchant_name': 'Netflix',
                    'category': 'software',
                },
                {
                    'raw_description': 'PRIMAX 8811',
                    'merchant_name': 'Primax',
                    'category': 'fuel',
                },
            ],
            'statement_id': statement.pk,
        })
        save_payload = _payload(save)
        assert save_payload['updated_transactions'] == 2
        assert MerchantAlias.objects.count() == 2

        finalize = _call_confirmed(api_client, token, 'finalize_statement', {
            'statement_id': statement.pk,
        })
        finalize_payload = _payload(finalize)
        assert finalize_payload['statement']['status'] == 'processed'
        categories = {
            row['category'] for row in finalize_payload['category_totals']
        }
        assert categories == {'software', 'fuel'}

    def test_save_alias_rejects_invalid_category(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'save_merchant_aliases', {
            'aliases': [{
                'raw_description': 'X', 'merchant_name': 'X',
                'category': 'no-existe',
            }],
        })
        assert response.data['result']['isError'] is True

    def test_save_on_processed_statement_saves_and_warns(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        _call_confirmed(api_client, token, 'finalize_statement', {
            'statement_id': statement.pk,
        })
        response = _call(api_client, token, 'save_merchant_aliases', {
            'aliases': [{
                'raw_description': 'PAYU*NETFLIX 990011',
                'merchant_name': 'Netflix', 'category': 'software',
            }],
            'statement_id': statement.pk,
        })
        assert response.data['result'].get('isError') is not True
        payload = _payload(response)
        assert payload['updated_transactions'] == 0
        assert 'ya está procesado' in payload['warning']
        assert MerchantAlias.objects.count() == 1

    def test_update_alias_normalizes_but_keeps_short_numbers(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        alias = MerchantAlias.objects.create(
            match_text='HOSTEL', merchant_name='Hostel 265',
            default_category='travel',
        )
        response = _call(api_client, token, 'update_merchant_alias', {
            'alias_id': alias.pk,
            'match_text': 'HOSTEL 265',
            'is_gateway': False,
        })
        payload = _payload(response)
        # Short numbers are part of the name; long codes still normalize.
        assert payload['match_text'] == 'HOSTEL 265'
        alias.refresh_from_db()
        assert alias.match_text == 'HOSTEL 265'
        assert alias.is_gateway is False


class TestLifecycleGuards:
    def test_finalize_mismatch_reports_difference(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        args = {**CREATE_ARGS, 'purchases_total': 999999}
        _call(api_client, token, 'create_statement', args)
        statement = CreditCardStatement.objects.get()
        response = _call_confirmed(api_client, token, 'finalize_statement', {
            'statement_id': statement.pk,
        })
        result = response.data['result']
        assert result['isError'] is True
        assert 'diferencia' in result['content'][0]['text']

    def test_delete_is_draft_only(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        _call_confirmed(api_client, token, 'finalize_statement', {
            'statement_id': statement.pk, 'force': True,
        })
        response = _call_confirmed(api_client, token, 'delete_statement', {
            'statement_id': statement.pk,
        })
        result = response.data['result']
        assert result['isError'] is True
        assert CreditCardStatement.objects.count() == 1

    def test_status_tool_reports_processed_month(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        _call_confirmed(api_client, token, 'finalize_statement', {
            'statement_id': statement.pk, 'force': True,
        })
        response = _call(api_client, token, 'get_statement_status', {
            'year': 2026,
        })
        payload = _payload(response)
        assert payload['months'][5]['has_processed'] is True
        # `cards` merges statement names with the active catalog (the
        # seed migration adds 'T.C 0064').
        assert 'Visa Bancolombia' in payload['cards']


class TestStatementCrudTools:
    def test_status_tool_rejects_invalid_year(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'get_statement_status', {
            'year': 'no-año',
        })
        assert response.data['result']['isError'] is True

    def test_create_requires_transactions_list(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'create_statement', {
            **{k: v for k, v in CREATE_ARGS.items() if k != 'transactions'},
            'transactions': [],
        })
        assert response.data['result']['isError'] is True

    def test_create_rejects_invalid_header(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        args = {k: v for k, v in CREATE_ARGS.items() if k != 'card_name'}
        response = _call(api_client, token, 'create_statement', args)
        result = response.data['result']
        assert result['isError'] is True
        assert 'Datos inválidos' in result['content'][0]['text']

    def test_create_rejects_invalid_transaction_rows(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'create_statement', {
            **CREATE_ARGS,
            'transactions': [{'raw_description': 'SIN FECHA NI MONTO'}],
        })
        assert response.data['result']['isError'] is True

    def test_resolve_requires_list(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'resolve_merchants', {
            'raw_descriptions': 'PAYU*NETFLIX',
        })
        assert response.data['result']['isError'] is True

    def test_save_aliases_requires_list(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'save_merchant_aliases', {
            'aliases': {},
        })
        assert response.data['result']['isError'] is True

    def test_update_statement_edits_notes(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        response = _call(api_client, token, 'update_statement', {
            'statement_id': statement.pk, 'notes': 'Revisado vía MCP',
        })
        assert response.data['result']['isError'] is False
        statement.refresh_from_db()
        assert statement.notes == 'Revisado vía MCP'

    def test_update_statement_unknown_id_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'update_statement', {
            'statement_id': 999999, 'notes': 'X',
        })
        assert response.data['result']['isError'] is True

    def test_update_statement_invalid_payload_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        response = _call(api_client, token, 'update_statement', {
            'statement_id': statement.pk, 'purchases_total': 'no-numero',
        })
        assert response.data['result']['isError'] is True

    def test_update_transaction_edits_category(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        tx = CreditCardTransaction.objects.order_by('pk').first()
        response = _call(api_client, token, 'update_statement_transaction', {
            'transaction_id': tx.pk, 'category': 'fuel',
        })
        assert _payload(response)['category'] == 'fuel'
        tx.refresh_from_db()
        assert tx.category == 'fuel'

    def test_update_transaction_unknown_id_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'update_statement_transaction', {
            'transaction_id': 999999, 'category': 'fuel',
        })
        assert response.data['result']['isError'] is True

    def test_update_transaction_invalid_payload_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        tx = CreditCardTransaction.objects.order_by('pk').first()
        response = _call(api_client, token, 'update_statement_transaction', {
            'transaction_id': tx.pk, 'amount': 'no-numero',
        })
        assert response.data['result']['isError'] is True

    def test_reopen_processed_statement_returns_draft(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        _call_confirmed(api_client, token, 'finalize_statement', {
            'statement_id': statement.pk, 'force': True,
        })
        response = _call(api_client, token, 'reopen_statement', {
            'statement_id': statement.pk,
        })
        assert _payload(response)['status'] == 'draft'

    def test_reopen_draft_statement_errors(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        response = _call(api_client, token, 'reopen_statement', {
            'statement_id': statement.pk,
        })
        assert response.data['result']['isError'] is True

    def test_list_statements_filters_by_year_card_and_status(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        response = _call(api_client, token, 'list_statements', {
            'year': 2026,
            'card_name': 'Visa Bancolombia',
            'status': 'draft',
        })
        assert _payload(response)['count'] == 1

    def test_list_statements_rejects_invalid_year(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        response = _call(api_client, token, 'list_statements', {
            'year': 'no-año',
        })
        assert response.data['result']['isError'] is True

    def test_get_statement_returns_detail(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        response = _call(api_client, token, 'get_statement', {
            'statement_id': statement.pk,
        })
        payload = _payload(response)
        assert payload['id'] == statement.pk
        assert len(payload['transactions']) == 2

    def test_delete_draft_statement_deletes(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        _, token = accounting_connector
        _call(api_client, token, 'create_statement', CREATE_ARGS)
        statement = CreditCardStatement.objects.get()
        response = _call_confirmed(api_client, token, 'delete_statement', {
            'statement_id': statement.pk,
        })
        assert _payload(response)['deleted'] is True
        assert CreditCardStatement.objects.count() == 0

    def test_list_merchant_aliases_filters_by_term(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        MerchantAlias.objects.create(
            match_text='NETFLIX', merchant_name='Netflix',
            default_category='software',
        )
        MerchantAlias.objects.create(
            match_text='PRIMAX', merchant_name='Primax',
            default_category='fuel',
        )
        _, token = accounting_connector
        response = _call(api_client, token, 'list_merchant_aliases', {
            'q': 'netflix',
        })
        assert _payload(response)['count'] == 1

    def test_delete_merchant_alias_removes_row(
        self, api_client, accounting_connector, mcp_superuser,
    ):
        alias = MerchantAlias.objects.create(
            match_text='NETFLIX', merchant_name='Netflix',
            default_category='software',
        )
        _, token = accounting_connector
        response = _call_confirmed(api_client, token, 'delete_merchant_alias', {
            'alias_id': alias.pk,
        })
        assert _payload(response)['deleted'] is True
        assert MerchantAlias.objects.count() == 0
