"""Expected-income MCP rejects unsafe financial edits and stale confirmations."""
from datetime import date
from decimal import Decimal

import pytest

from content.models import Document, DocumentType, IncomeRecord, McpActionIntent, ProjectRetentionContext
from content.services import accounting_expected_income_service as service
from content.tests.views.test_mcp_expected_income_flow import (
    _call, _confirm, _payload, _semester_one,
)
from content.tests.views.test_mcp_expected_income_flow import accounting_connector as accounting_connector
from content.tests.views.test_mcp_expected_income_flow import gm_income as gm_income
from content.tests.views.test_mcp_expected_income_flow import mute_notifications as mute_notifications

pytestmark = pytest.mark.django_db


def _error(response):
    return _payload(response)['error']


def _payment(income, make_income):
    return make_income(kind='liquid', expected_income=income, total_amount=Decimal('100.00'),
                       gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'))


def _collection(income, status):
    document_type, _ = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )
    return Document.objects.create(
        title='Cuenta G&M', document_type=document_type, income_record=income,
        client_user=income.client.user, project=income.project, commercial_status=status,
        total=income.total_amount,
    )


def test_payments_block_amount_changes(api_client, accounting_connector, gm_income, make_income):
    _payment(gm_income, make_income)
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000',
    }))
    assert error['code'] == 'INCOME_LOCKED'
    assert error['details']['blockers'][0]['code'] == 'payments'
    assert McpActionIntent.objects.count() == 0


def test_issued_account_blocks_financial_changes(api_client, accounting_connector, gm_income):
    _collection(gm_income, 'issued')
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000',
    }))
    assert error['code'] == 'INCOME_LOCKED'
    assert error['details']['blockers'][0]['code'] == 'issued_collection_account'
    assert gm_income.total_amount == Decimal('760000.00')


def test_stale_if_match_rejects_preview(api_client, accounting_connector, gm_income):
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'if_match': '0' * 64, 'total_amount': '4200000',
    }))
    assert error['code'] == 'STALE_VERSION'
    assert error['details'] == {'income_id': 172, 'expected': '0' * 64, 'current': service.income_etag(gm_income)}


def test_new_payment_invalidates_confirmation(api_client, accounting_connector, gm_income, make_income):
    preview = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000',
    }))
    _payment(gm_income, make_income)
    error = _error(_call(api_client, accounting_connector[1], 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    }))
    gm_income.refresh_from_db()
    assert error['code'] == 'STALE_VERSION'
    assert gm_income.total_amount == Decimal('760000.00')
    assert McpActionIntent.objects.get(pk=preview['confirmation_id']).status == 'pending'


def test_unknown_amount_argument_preserves_field_code(api_client, accounting_connector, gm_income):
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'amount': '4200000',
    }))
    assert error['code'] == 'unknown_field'
    assert error['details']['errors'] == [{
        'field': 'amount', 'code': 'unknown_field', 'message': 'Campo desconocido para esta herramienta.',
    }]


@pytest.mark.parametrize('key', ['_expected_etag', '_source_etag', 'fields'])
def test_client_cannot_send_server_confirmation_keys(api_client, accounting_connector, gm_income, key):
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, key: '0' * 64,
    }))
    assert error['code'] == 'unknown_field'
    assert error['details']['errors'][0]['field'] == key
    assert McpActionIntent.objects.count() == 0


def test_explicit_split_mismatch_rejected(api_client, accounting_connector, gm_income):
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000', 'gustavo_amount': '2000000',
        'carlos_amount': '2000000', 'company_amount': '100000',
    }))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details'] == {'reason': 'split_mismatch', 'total': '4200000.00', 'sum': '4100000.00'}


def test_vat_mismatch_rejected(api_client, accounting_connector, gm_income):
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000', 'vat_rate': '19', 'base_amount': '3500000',
    }))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details']['reason'] == 'vat_mismatch'
    assert error['details']['expected'] == {
        'vat_rate': '19.00', 'base_amount': '3529411.76', 'vat_amount': '670588.24', 'total_amount': '4200000.00',
    }


def test_liquid_income_rejected_by_expected_tools(api_client, accounting_connector, gm_income, make_income):
    liquid = _payment(gm_income, make_income)
    error = _error(_call(api_client, accounting_connector[1], 'get_expected_income', {'income_id': liquid.pk}))
    assert error['code'] == 'NOT_EXPECTED_INCOME'
    assert error['details'] == {'income_id': liquid.pk, 'kind': 'liquid', 'expected_income_id': 172}


def test_nonexistent_income_returns_not_found(api_client, accounting_connector):
    error = _error(_call(api_client, accounting_connector[1], 'get_expected_income', {'income_id': 999999}))
    assert error['code'] == 'NOT_FOUND'
    assert error['details'] == {'income_id': 999999}


def test_create_requires_explicit_vat_key(api_client, accounting_connector):
    error = _error(_call(api_client, accounting_connector[1], 'create_expected_income', {
        'concept': 'IVA no informado', 'origin': 'development', 'period_date': '2026-11-01', 'total_amount': '1000',
    }))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details']['errors'][0]['field'] == 'vat_rate'
    assert IncomeRecord.objects.count() == 0


def test_hosting_duplicate_requires_billing_window(api_client, accounting_connector, gm_income):
    gm_income.origin = 'hosting'
    gm_income.save(update_fields=['origin'])
    error = _error(_call(api_client, accounting_connector[1], 'duplicate_expected_income', {'income_id': 172}))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details'] == {
        'reason': 'billing_window_required',
        'cycle_options': [
            {'months': 1, 'date': '2026-12-01'}, {'months': 3, 'date': '2027-02-01'},
            {'months': 6, 'date': '2027-05-01'}, {'months': 12, 'date': '2027-11-01'},
        ],
        'period_anchor': {'source': 'original_date', 'start': None, 'origin_start': None,
                          'origin_end': None, 'origin_date': '2026-11-01'},
    }


def test_source_payment_invalidates_duplicate(api_client, accounting_connector, gm_income, make_income):
    source = _semester_one(api_client, accounting_connector[1], gm_income)
    preview = _payload(_call(api_client, accounting_connector[1], 'duplicate_expected_income', {'income_id': 172}))
    _payment(source, make_income)
    error = _error(_call(api_client, accounting_connector[1], 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    }))
    assert error['code'] == 'STALE_VERSION'
    assert IncomeRecord.objects.filter(kind='expected').count() == 1


def test_retained_income_blocks_notes(api_client, accounting_connector, gm_income, admin_user):
    retained = ProjectRetentionContext.objects.create(
        client=gm_income.client.user, original_project_id=8, project_name='G&M', created_by=admin_user,
    )
    IncomeRecord.objects.filter(pk=172).update(retention_context=retained, project=None)
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'notes': 'Editar archivo conservado',
    }))
    assert error['code'] == 'INCOME_LOCKED'
    assert error['details']['blocked_fields'] == ['notes']
    assert error['details']['blockers'][0]['code'] == 'retained_data'


def test_payment_allows_notes_with_lock_warning(api_client, accounting_connector, gm_income, make_income):
    _payment(gm_income, make_income)
    payload = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'notes': 'Esperar el saldo',
    }))
    gm_income.refresh_from_db()
    assert payload['updated'] is True
    assert gm_income.notes == 'Esperar el saldo'
    assert payload['warnings'][0]['code'] == 'financial_fields_locked'


def test_draft_account_warns_before_amount_change(api_client, accounting_connector, gm_income):
    _collection(gm_income, 'draft')
    preview = _payload(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'total_amount': '4200000',
    }))
    assert preview['impact']['warnings'] == [{
        'code': 'draft_collection_account',
        'message': 'Existe una cuenta de cobro en borrador; revisa sus importes antes de emitirla.',
    }]


def test_unknown_override_preserves_nested_path(api_client, accounting_connector, gm_income):
    error = _error(_call(api_client, accounting_connector[1], 'duplicate_expected_income', {
        'income_id': 172, 'overrides': {'amount': '4200000'},
    }))
    assert error['code'] == 'unknown_field'
    assert error['details']['errors'][0]['field'] == 'overrides.amount'


def test_personal_ledger_rejects_a_different_split(api_client, accounting_connector):
    error = _error(_call(api_client, accounting_connector[1], 'create_expected_income', {
        'concept': 'Personal Gustavo', 'origin': 'development', 'vat_rate': None, 'ledger': 'gustavo',
        'period_date': '2026-11-01', 'total_amount': '1000', 'gustavo_amount': '500',
    }))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details']['reason'] == 'personal_ledger_split'


def test_period_alias_must_match_payment_month(api_client, accounting_connector, gm_income):
    error = _error(_call(api_client, accounting_connector[1], 'update_expected_income', {
        'income_id': 172, 'period': '2026-11', 'period_date': '2026-12-01',
    }))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details']['reason'] == 'period_mismatch'


def test_create_requires_base_or_total(api_client, accounting_connector):
    error = _error(_call(api_client, accounting_connector[1], 'create_expected_income', {
        'concept': 'Falta importe', 'origin': 'development', 'vat_rate': None, 'period_date': '2026-11-01',
    }))
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['details'] == {'reason': 'needs_base_or_total'}
    assert McpActionIntent.objects.count() == 0
