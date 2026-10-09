"""The G&M hosting renewal can be read, reviewed and confirmed over MCP HTTP."""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.models import Project
from content.mcp.expected_income_tools import EXPECTED_INCOME_TOOLS
from content.models import AccountingChangeLog, IncomeRecord, McpActionIntent, McpConnector
from content.serializers.accounting import split_half
from content.services import accounting_service

pytestmark = pytest.mark.django_db
SEMESTER_ONE = {
    'concept': 'G&M (Hosting: Semestral) – Semestre 1', 'total_amount': '4200000',
    'gustavo_amount': '2100000', 'carlos_amount': '2100000', 'company_amount': '0',
    'period_date': '2026-11-01', 'period_start': '2026-10-01', 'period_end': '2027-03-31',
    'period_cadence': 'semiannual', 'origin': 'hosting',
    'notes': 'Propuesta Fase IA 2027 §11 (doc #84). Reajuste por renovación: % aumento SMMLV + 8%.',
}


@pytest.fixture
def accounting_connector(db):
    connector, _ = McpConnector.objects.get_or_create(slug='accounting', defaults={'name': 'Contabilidad'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


@pytest.fixture
def mcp_superuser(db, django_user_model):
    return django_user_model.objects.create_user(
        username='mcp_expected_actor', password='x', is_staff=True, is_superuser=True,
    )


@pytest.fixture(autouse=True)
def mute_notifications():
    with patch.object(accounting_service, '_notify') as notifier:
        yield notifier


@pytest.fixture
def gm_income(make_income, make_client_profile):
    profile = make_client_profile(company='G&M', id=54, first_name='G&M', last_name='')
    project = Project.objects.create(id=8, name='G&M', client=profile.user)
    return make_income(
        id=172, concept='G&M (Hosting: Anual)', client=profile, project=project,
        kind='expected', total_amount=Decimal('760000.00'), gustavo_amount=Decimal('380000.00'),
        carlos_amount=Decimal('380000.00'), destination='partners', ledger='company',
        period_date=date(2026, 11, 1), origin='', vat_rate=None, collection_confidence='high',
    )


def _rpc(method, params=None):
    message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(f'/api/mcp/accounting/{token}/',
                          _rpc('tools/call', {'name': name, 'arguments': arguments}), format='json')


def _payload(response):
    return json.loads(response.data['result']['content'][0]['text'])


def _confirm(api_client, token, preview):
    return _payload(_call(api_client, token, 'confirm_action', {'confirmation_id': preview['confirmation_id']}))


def _semester_one(api_client, token, income):
    preview = _payload(_call(api_client, token, 'update_expected_income', {'income_id': income.pk, **SEMESTER_ONE}))
    _confirm(api_client, token, preview)
    income.refresh_from_db()
    return income


@pytest.mark.parametrize('slug', ['accounting', 'accounting-ledger'])
def test_connector_lists_five_expected_income_tools(api_client, slug):
    connector = McpConnector.objects.create(slug=slug, name=slug, is_active=True)
    token = connector.generate_token()
    response = api_client.post(f'/api/mcp/{slug}/{token}/', _rpc('tools/list'), format='json')
    names = {row['name'] for row in response.data['result']['tools']}
    expected = {tool['name'] for tool in EXPECTED_INCOME_TOOLS}
    assert names & expected == expected
    assert len(expected) == 5


def test_list_finds_gm_by_client_text_and_unclassified_origin(api_client, accounting_connector, gm_income):
    """Find the legacy row without inferring a business line from its concept."""
    payload = _payload(_call(api_client, accounting_connector[1], 'list_expected_incomes', {
        'client_id': 54, 'q': 'G&M', 'origin': ['none'],
    }))
    assert {key: payload[key] for key in ('count', 'page', 'page_size', 'num_pages', 'has_next')} == {
        'count': 1, 'page': 1, 'page_size': 25, 'num_pages': 1, 'has_next': False,
    }
    assert payload['results'] == [{
        'id': 172, 'concept': 'G&M (Hosting: Anual)', 'client_id': 54, 'client_name': 'G&M',
        'project_id': 8, 'project_name': 'G&M', 'origin': '', 'ledger': 'company', 'period': '2026-11',
        'period_date': '2026-11-01', 'period_start': None, 'period_end': None, 'period_cadence': '',
        'total_amount': '760000.00', 'gustavo_amount': '380000.00', 'carlos_amount': '380000.00',
        'company_amount': '0.00', 'vat_rate': None, 'paid_amount': '0.00', 'pending_amount': '760000.00',
        'payment_status': 'pending', 'collection_account_status': None, 'collection_confidence': 'high',
        'is_receivable_candidate': False, 'locks': [],
    }]


def test_get_returns_etag_and_editability(api_client, accounting_connector, gm_income):
    """Return the complete editable shape, including confirmation-triggering fields."""
    payload = _payload(_call(api_client, accounting_connector[1], 'get_expected_income', {'income_id': 172}))
    assert payload['income']['id'] == 172
    assert len(payload['etag']) == 64
    assert {key: payload[key] for key in ('payments', 'deductions', 'collection_account')} == {
        'payments': [], 'deductions': [], 'collection_account': None,
    }
    assert payload['editability'] == {
        'blockers': [], 'locked_fields': [], 'confirmation_fields': [
            'total_amount', 'vat_rate', 'gustavo_amount', 'carlos_amount', 'company_amount', 'ledger', 'client', 'project',
        ],
    }


def test_money_preview_leaves_income_unchanged(api_client, accounting_connector, gm_income):
    """Financial edits must remain a preview until confirm_action is called."""
    preview = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, **SEMESTER_ONE,
    }))
    gm_income.refresh_from_db()
    assert preview['confirmation_required'] is True
    assert preview['impact']['before']['total_amount'] == '760000.00'
    assert preview['impact']['after']['total_amount'] == '4200000.00'
    assert gm_income.concept == 'G&M (Hosting: Anual)'
    assert gm_income.total_amount == Decimal('760000.00')
    assert AccountingChangeLog.objects.filter(object_id=172).count() == 0
    intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
    assert set(intent.arguments) == {'income_id', 'fields', '_expected_etag'}


def test_confirm_applies_semester_one(api_client, accounting_connector, gm_income, mute_notifications):
    """The exact G&M proposal edit persists through the panel's audited writer."""
    preview = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, **SEMESTER_ONE,
    }))
    confirmed = _confirm(api_client, accounting_connector[1], preview)
    gm_income.refresh_from_db()
    assert confirmed['confirmed'] is True
    assert {key: getattr(gm_income, key) for key in (*SEMESTER_ONE, 'client_id', 'project_id', 'vat_rate')} == {
        **SEMESTER_ONE, 'total_amount': Decimal('4200000.00'), 'gustavo_amount': Decimal('2100000.00'),
        'carlos_amount': Decimal('2100000.00'), 'company_amount': Decimal('0'),
        'period_date': date(2026, 11, 1), 'period_start': date(2026, 10, 1), 'period_end': date(2027, 3, 31),
        'client_id': 54, 'project_id': 8, 'vat_rate': None,
    }
    assert AccountingChangeLog.objects.get(object_id=172).actor.username == 'mcp_accounting'
    mute_notifications.assert_called_once()


def test_duplicate_confirm_opens_semester_two(api_client, accounting_connector, gm_income):
    """A new cycle preserves the November-to-May payment offset and no child links."""
    source = _semester_one(api_client, accounting_connector[1], gm_income)
    preview = _payload(_call(api_client, accounting_connector[1], 'duplicate_expected_income', {
        'income_id': 172, 'overrides': {'concept': 'G&M (Hosting: Semestral) – Semestre 2',
                                      'total_amount': '4200000', 'collection_confidence': 'medium'},
    }))
    assert IncomeRecord.objects.count() == 1
    assert preview['impact']['period_rule']['rule'] == 'kept_payment_offset'
    confirmed = _confirm(api_client, accounting_connector[1], preview)
    new = IncomeRecord.objects.get(pk=confirmed['result']['income']['id'])
    gustavo, carlos = split_half(Decimal('4200000.00'))
    assert {key: getattr(new, key) for key in (
        'concept', 'kind', 'period_date', 'period_start', 'period_end', 'period_cadence',
        'total_amount', 'gustavo_amount', 'carlos_amount', 'vat_rate', 'client_id', 'project_id',
        'collection_confidence', 'expected_income_id',
    )} == {
        'concept': 'G&M (Hosting: Semestral) – Semestre 2', 'kind': 'expected', 'period_date': date(2027, 5, 1),
        'period_start': date(2027, 4, 1), 'period_end': date(2027, 9, 30), 'period_cadence': 'semiannual',
        'total_amount': Decimal('4200000.00'), 'gustavo_amount': gustavo, 'carlos_amount': carlos,
        'vat_rate': None, 'client_id': source.client_id, 'project_id': source.project_id,
        'collection_confidence': 'medium', 'expected_income_id': None,
    }
    read = _payload(_call(api_client, accounting_connector[1], 'get_expected_income', {'income_id': new.pk}))
    assert read['collection_account'] is None


def test_create_previews_until_confirmed(api_client, accounting_connector):
    """Required tax classification prevents an implicit company VAT default."""
    preview = _payload(_call(api_client, accounting_connector[1], 'create_expected_income', {
        'concept': 'Diagnóstico próximo', 'origin': 'diagnostic', 'vat_rate': None,
        'period': '2026-11', 'total_amount': '2000',
    }))
    assert preview['impact']['before'] is None
    assert IncomeRecord.objects.count() == 0
    result = _confirm(api_client, accounting_connector[1], preview)
    income = IncomeRecord.objects.get(pk=result['result']['income']['id'])
    gustavo, carlos = split_half(Decimal('2000.00'))
    assert {key: getattr(income, key) for key in ('kind', 'ledger', 'destination', 'total_amount',
                                                'gustavo_amount', 'carlos_amount', 'vat_rate')} == {
        'kind': 'expected', 'ledger': 'company', 'destination': 'partners', 'total_amount': Decimal('2000.00'),
        'gustavo_amount': gustavo, 'carlos_amount': carlos, 'vat_rate': None,
    }


def test_notes_update_applies_directly(api_client, accounting_connector, gm_income):
    payload = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'notes': 'Seguimiento de renovación',
    }))
    gm_income.refresh_from_db()
    assert payload['updated'] is True
    assert gm_income.notes == 'Seguimiento de renovación'
    assert McpActionIntent.objects.count() == 0


def test_total_only_preview_recalculates_panel_split(api_client, accounting_connector, gm_income):
    preview = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000',
    }))
    gustavo, carlos = split_half(Decimal('4200000.00'))
    assert {key: preview['impact']['split'][key] for key in ('rule', 'gustavo', 'carlos', 'company')} == {
        'rule': 'panel_auto', 'gustavo': str(gustavo), 'carlos': str(carlos), 'company': '0.00',
    }


def test_reconfirmed_create_returns_single_saved_income(api_client, accounting_connector):
    preview = _payload(_call(api_client, accounting_connector[1], 'create_expected_income', {
        'concept': 'Cobro único', 'origin': 'development', 'vat_rate': None,
        'period_date': '2026-11-01', 'total_amount': '2000',
    }))
    first = _confirm(api_client, accounting_connector[1], preview)
    replay = _confirm(api_client, accounting_connector[1], preview)
    assert replay == {'confirmed': True, 'replayed': True, 'result': first['result']}
    assert IncomeRecord.objects.count() == 1


def test_identical_update_writes_no_audit(api_client, accounting_connector, gm_income, mute_notifications):
    payload = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'concept': gm_income.concept,
    }))
    assert payload['updated'] is False
    assert AccountingChangeLog.objects.count() == 0
    mute_notifications.assert_not_called()


def test_create_preview_reports_possible_duplicate(api_client, accounting_connector, gm_income):
    preview = _payload(_call(api_client, accounting_connector[1], 'create_expected_income', {
        'concept': 'Otro cobro', 'origin': 'development', 'vat_rate': None, 'period_date': '2026-11-30',
        'client': 54, 'project': 8, 'total_amount': '2000',
    }))
    assert preview['impact']['warnings'] == [{
        'code': 'possible_duplicate', 'income_ids': [172],
        'message': 'Ya hay ingresos esperados del mismo cliente y proyecto en ese período.',
    }]


def test_month_filter_includes_last_day(api_client, accounting_connector, make_income):
    income = make_income(period_date=date(2026, 11, 30))
    make_income(period_date=date(2026, 12, 1))
    payload = _payload(_call(api_client, accounting_connector[1], 'list_expected_incomes', {
        'period_from': '2026-11', 'period_to': '2026-11', 'client_id': None, 'project_id': None,
    }))
    assert [row['id'] for row in payload['results']] == [income.pk]


def test_list_relation_queries_do_not_grow_per_income(api_client, accounting_connector, gm_income, make_income):
    """The list must batch payment and collection relations, regardless of row count."""
    _call(api_client, accounting_connector[1], 'list_expected_incomes', {})
    with CaptureQueriesContext(connection) as original:
        _call(api_client, accounting_connector[1], 'list_expected_incomes', {})
    make_income(client=gm_income.client, project=gm_income.project)
    make_income(client=gm_income.client, project=gm_income.project)
    with CaptureQueriesContext(connection) as expanded:
        payload = _payload(_call(api_client, accounting_connector[1], 'list_expected_incomes', {}))
    assert payload['count'] == 3
    assert len(expanded) == len(original)
