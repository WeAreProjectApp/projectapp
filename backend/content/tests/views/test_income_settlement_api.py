"""REST and MCP contracts for the unified income-settlement operation."""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from content.models import (
    Document, DocumentCollectionAccount, DocumentType, EmailLog, ExpenseRecord,
    IncomeRecord, IncomeSettlement, McpActionIntent, McpConnector, McpCredential,
    PocketMovement,
)
from content.services import accounting_service
from content.services.income_settlement_operation_service import preview_settlement


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mute_accounting_notifications():
    with patch.object(accounting_service, '_notify'):
        yield


@pytest.fixture
def accounting_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug='accounting', defaults={'name': 'Contabilidad'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    credential, _ = McpCredential.objects.get_or_create(
        connector=connector,
        label='Settlement API canonical accounting',
        defaults={'catalog': 'canonical'},
    )
    credential.catalog = 'canonical'
    credential.save(update_fields=['catalog', 'updated_at'])
    return credential.generate_token()


@pytest.fixture
def accounting_ledger_token():
    connector, _ = McpConnector.objects.get_or_create(
        slug='accounting-ledger', defaults={'name': 'Libro contable'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    credential, _ = McpCredential.objects.get_or_create(
        connector=connector,
        label='Settlement API canonical ledger',
        defaults={'catalog': 'canonical'},
    )
    credential.catalog = 'canonical'
    credential.save(update_fields=['catalog', 'updated_at'])
    return credential.generate_token()


def _settlement_payload(*income_ids, **overrides):
    payload = {
        'income_ids': list(income_ids),
        'total_amount': '180.00',
        'period_date': '2026-10-19',
        'destination': 'pocket',
        'deductions': [{'type': 'bank_fee', 'amount': '20.00'}],
        'gustavo_amount': '110.00',
        'carlos_amount': '70.00',
    }
    payload.update(overrides)
    return payload


def _call_accounting_tool(api_client, token, name, arguments, *, slug='accounting'):
    return api_client.post(
        f'/api/mcp/{slug}/{token}/',
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        },
        format='json',
    )


def _tool_payload(response):
    assert response.status_code == 200, response.data
    assert response.data['result']['isError'] is False, response.data
    return json.loads(response.data['result']['content'][0]['text'])


def _tool_error(response):
    assert response.status_code == 200, response.data
    assert response.data['result']['isError'] is True, response.data
    return response.data['result']['structuredContent']['error']


def _confirm_accounting_tool(api_client, token, name, arguments):
    preview = _tool_payload(_call_accounting_tool(api_client, token, name, arguments))
    confirmed = _tool_payload(_call_accounting_tool(
        api_client, token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    ))
    return preview, confirmed


def _preview_query_count(incomes):
    request_data = _settlement_payload(
        *(income.pk for income in incomes),
        total_amount=str(Decimal('100.00') * len(incomes)), deductions=[],
        gustavo_amount='0.00', carlos_amount='0.00',
    )
    with CaptureQueriesContext(connection) as captured:
        preview_settlement(request_data)
    return len(captured)


def _client_income_group(make_income, make_client_profile, count):
    return [
        make_income(
            concept=f'Cobro {number}', period_date=date(2026, 10, number),
            total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
            carlos_amount=Decimal('50.00'), client=make_client_profile(),
        )
        for number in range(1, count + 1)
    ]


def _issued_collection_account(income, email):
    document = Document.objects.create(
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        title=f'Cuenta {income.pk}', commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income, client_user=income.client.user,
        public_number=f'PA-TEST-{income.pk}', total=income.total_amount,
    )
    DocumentCollectionAccount.objects.create(document=document, customer_email=email)


def _vat_payment(income):
    return _settlement_payload(income.pk, total_amount='119.00', deductions=[],
        gustavo_amount='59.50', carlos_amount='59.50', vat_updates=[{
            'income_id': income.pk, 'vat_rate': '19.00', 'amount': '100.00',
            'amount_mode': 'before_vat',
        }])


def test_rest_vat_configuration_is_atomic_with_the_payment(super_client, make_income):
    """Falla si el panel guarda la tasa sin el pago normalizado que se revisó."""
    income = make_income(vat_rate=None)
    data = _vat_payment(income)
    preview = super_client.post('/api/accounting/incomes/settlement-preview/', data, format='json')
    income.refresh_from_db()
    assert income.vat_rate is None

    result = super_client.post('/api/accounting/incomes/bulk-settle/',
        {**data, 'preview_hash': preview.data['preview_hash']}, format='json')

    income.refresh_from_db()
    assert result.status_code == 201, result.data
    assert income.vat_rate == Decimal('19')
    assert income.liquid_records.get().base_amount == Decimal('100')


def test_mcp_vat_preview_matches_the_panel(super_client, api_client, accounting_token, make_income):
    """Falla si un conector interpreta otra tasa o importe que el panel."""
    income = make_income(vat_rate=None)
    data = _vat_payment(income)
    rest = super_client.post('/api/accounting/incomes/settlement-preview/', data, format='json')
    mcp = _tool_payload(_call_accounting_tool(api_client, accounting_token, 'preview_income_settlement', data))

    assert mcp['rows'] == rest.data['rows']
    assert mcp['rows'][0]['vat_amount'] == '19.00'
    assert IncomeSettlement.objects.count() == 0


def test_mcp_confirmed_vat_configuration_updates_the_source(api_client, accounting_token, make_income):
    """Falla si el esquema MCP admite IVA pero el escritor descarta su configuración."""
    income = make_income(vat_rate=None)
    preview, confirmed = _confirm_accounting_tool(api_client, accounting_token, 'bulk_settle_incomes', _vat_payment(income))

    income.refresh_from_db()
    assert preview['confirmation_required'] is True
    assert income.vat_rate == Decimal('19')
    assert income.liquid_records.get().total_amount == Decimal('119')
    assert confirmed['result']['settlement_id']


def test_mcp_single_vat_configuration_uses_the_shared_writer(api_client, accounting_token, make_income):
    """Falla si el adaptador individual pierde el IVA aceptado por el colectivo."""
    income = make_income(vat_rate=None)
    data = _vat_payment(income)
    data.pop('income_ids')
    data.update(record_id=income.pk, concept=income.concept)
    preview, confirmed = _confirm_accounting_tool(api_client, accounting_token, 'settle_income', data)

    income.refresh_from_db()
    assert income.vat_rate == Decimal('19')
    assert confirmed['result']['liquid']['vat_amount'] == '19.00'
    assert preview['confirmation_required'] is True


def test_mcp_vat_correction_replaces_its_own_rate(super_client, api_client, accounting_token, make_income):
    """Falla si el MCP no puede corregir su cambio fiscal después de confirmar."""
    income = make_income(vat_rate=None)
    created = super_client.post('/api/accounting/incomes/bulk-settle/', _vat_payment(income), format='json')
    data = _vat_payment(income)
    data.update(settlement_id=created.data['settlement_id'], revision=1,
        vat_updates=[{'income_id': income.pk, 'vat_rate': '0'}])
    _, confirmed = _confirm_accounting_tool(api_client, accounting_token, 'update_income_settlement', data)

    income.refresh_from_db()
    assert income.vat_rate == Decimal('0')
    assert confirmed['result']['revision'] == 2


def test_mcp_vat_change_after_emission_is_rejected(api_client, accounting_token, make_income, make_client_profile):
    """Falla si el MCP omite la protección documental que sí aplica el panel."""
    income = make_income(vat_rate=None, client=make_client_profile())
    _issued_collection_account(income, 'cliente@example.com')
    error = _tool_error(_call_accounting_tool(api_client, accounting_token, 'bulk_settle_incomes', _vat_payment(income)))

    assert 'Anula la cuenta' in error['message']
    assert PocketMovement.objects.count() == 0


def test_settlement_preview_requires_a_superuser(api_client, admin_client, make_income):
    """Falla si una sesión anónima o un miembro del staff puede ver un reparto financiero."""
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    request_data = _settlement_payload(income.pk, total_amount='100.00', deductions=[])

    anonymous = api_client.post(
        '/api/accounting/incomes/settlement-preview/', request_data, format='json',
    )
    staff = admin_client.post(
        '/api/accounting/incomes/settlement-preview/', request_data, format='json',
    )

    assert anonymous.status_code == 403
    assert staff.status_code == 403


def test_rest_and_mcp_preview_match_vat_and_deduction_without_writing(
    super_client, api_client, accounting_token, make_income,
):
    """Falla si REST o MCP reparte distinto la comisión, el IVA heredado o escribe al previsualizar."""
    first = make_income(
        concept='Primer cobro', period_date=date(2026, 10, 1),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'), vat_rate=Decimal('19.00'),
    )
    second = make_income(
        concept='Segundo cobro', period_date=date(2026, 10, 2),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'), vat_rate=Decimal('0.00'),
    )
    request_data = _settlement_payload(first.pk, second.pk)

    rest_response = super_client.post(
        '/api/accounting/incomes/settlement-preview/', request_data, format='json',
    )
    mcp_response = _call_accounting_tool(
        api_client, accounting_token, 'preview_income_settlement', request_data,
    )

    assert rest_response.status_code == 200, rest_response.data
    assert rest_response.data == _tool_payload(mcp_response)
    assert [
        (
            row['income_id'], row['amount'], row['deducted'], row['vat_rate'],
            row['base_amount'], row['vat_amount'], row['total_amount'],
        )
        for row in rest_response.data['rows']
    ] == [
        (first.pk, '90.00', '10.00', '19.00', '75.63', '14.37', '90.00'),
        (second.pk, '90.00', '10.00', '0.00', '90.00', '0.00', '90.00'),
    ]
    assert IncomeSettlement.objects.count() == 0
    assert PocketMovement.objects.count() == 0
    assert ExpenseRecord.objects.count() == 0


def test_rest_and_mcp_retry_share_one_idempotent_settlement(
    super_client, api_client, accounting_token, make_income,
):
    """Falla si un reintento por REST o MCP duplica el abono, la comisión o el reparto global."""
    first = make_income(
        concept='Primer cobro', period_date=date(2026, 10, 1),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'), vat_rate=Decimal('19.00'),
    )
    second = make_income(
        concept='Segundo cobro', period_date=date(2026, 10, 2),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'), vat_rate=Decimal('0.00'),
    )
    request_data = _settlement_payload(first.pk, second.pk, request_id=str(uuid4()))

    initial = super_client.post(
        '/api/accounting/incomes/bulk-settle/', request_data, format='json',
    )
    rest_retry = super_client.post(
        '/api/accounting/incomes/bulk-settle/', request_data, format='json',
    )
    mcp_preview, mcp_confirmation = _confirm_accounting_tool(
        api_client, accounting_token, 'bulk_settle_incomes', request_data,
    )
    mcp_retry = mcp_confirmation['result']

    assert (initial.status_code, rest_retry.status_code) == (201, 201), (initial.data, rest_retry.data)
    assert (mcp_preview['confirmation_required'], mcp_confirmation['confirmed']) == (True, True)
    assert (
        initial.data['settlement_id'], rest_retry.data['settlement_id'],
        mcp_retry['settlement_id'],
    ) == (initial.data['settlement_id'],) * 3
    assert (PocketMovement.objects.count(), IncomeSettlement.objects.count()) == (1, 1)
    assert list(
        ExpenseRecord.objects.order_by('source_income_id').values_list(
            'source_income_id', 'total_amount',
        )
    ) == [
        (first.pk, Decimal('10.00')),
        (second.pk, Decimal('10.00')),
    ]
    assert list(
        IncomeRecord.objects.filter(kind='liquid', expected_income__isnull=False)
        .order_by('expected_income_id')
        .values_list('total_amount', 'gustavo_amount', 'carlos_amount')
    ) == [
        (Decimal('90.00'), Decimal('55.00'), Decimal('35.00')),
        (Decimal('90.00'), Decimal('55.00'), Decimal('35.00')),
    ]


def test_stale_rest_correction_and_mcp_reversal_leave_effects_active(
    super_client, api_client, accounting_token, make_income,
):
    """Falla si una revisión obsoleta borra o reemplaza los efectos vigentes de la liquidación."""
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    initial_data = _settlement_payload(
        income.pk, total_amount='80.00', gustavo_amount='40.00', carlos_amount='40.00',
    )
    created = super_client.post(
        '/api/accounting/incomes/bulk-settle/', initial_data, format='json',
    )
    settlement_id = created.data['settlement_id']
    corrected_data = _settlement_payload(
        income.pk, total_amount='90.00', gustavo_amount='50.00', carlos_amount='40.00',
        deductions=[{'type': 'bank_fee', 'amount': '10.00'}], revision=1,
    )

    updated = super_client.patch(
        f'/api/accounting/income-settlements/{settlement_id}/', corrected_data, format='json',
    )
    stale = super_client.patch(
        f'/api/accounting/income-settlements/{settlement_id}/', corrected_data, format='json',
    )
    mcp_preview = _tool_payload(_call_accounting_tool(api_client, accounting_token, 'reverse_income_settlement', {
        'settlement_id': settlement_id, 'revision': 1,
    }))
    mcp_stale = _tool_error(_call_accounting_tool(
        api_client, accounting_token, 'confirm_action',
        {'confirmation_id': mcp_preview['confirmation_id']},
    ))

    operation = IncomeSettlement.objects.get(pk=settlement_id)
    assert (
        created.status_code, updated.status_code, updated.data['revision'],
        stale.status_code, mcp_preview['confirmation_required'], mcp_stale['code'],
    ) == (201, 200, 2, 409, True, 'VALIDATION_ERROR'), (created.data, updated.data, stale.data, mcp_stale)
    assert 'cambió' in mcp_stale['message']
    assert (
        operation.status, operation.revision, PocketMovement.objects.get().amount,
        list(ExpenseRecord.objects.values_list('total_amount', flat=True)),
    ) == (IncomeSettlement.Status.ACTIVE, 2, Decimal('90.00'), [Decimal('10.00')])


def test_paid_follow_up_blocks_rest_and_mcp_reversal_without_partial_delete(
    super_client, api_client, accounting_token, make_income,
):
    """Falla si revertir un saldo ya cobrado elimina solo una parte de las operaciones relacionadas."""
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    initial_data = _settlement_payload(
        income.pk, total_amount='60.00', gustavo_amount='30.00', carlos_amount='30.00',
        deductions=[], expected_incomes=[{
            'income_id': income.pk, 'concept': 'Saldo reprogramado',
            'amount': '40.00', 'period_date': '2026-11-01',
        }],
    )
    created = super_client.post(
        '/api/accounting/incomes/bulk-settle/', initial_data, format='json',
    )
    settlement_id = created.data['settlement_id']
    follow_up = IncomeRecord.objects.get(settlement_id=settlement_id, kind='expected')
    later_payment = super_client.post('/api/accounting/incomes/bulk-settle/', {
        'income_ids': [follow_up.pk], 'total_amount': '10.00',
        'period_date': '2026-11-02', 'destination': 'pocket',
    }, format='json')

    rest_reverse = super_client.delete(
        f'/api/accounting/income-settlements/{settlement_id}/', {'revision': 1}, format='json',
    )
    mcp_preview = _tool_payload(_call_accounting_tool(api_client, accounting_token, 'reverse_income_settlement', {
        'settlement_id': settlement_id, 'revision': 1,
    }))
    mcp_reverse = _tool_error(_call_accounting_tool(
        api_client, accounting_token, 'confirm_action',
        {'confirmation_id': mcp_preview['confirmation_id']},
    ))

    assert (
        created.status_code, later_payment.status_code, rest_reverse.status_code,
        mcp_preview['confirmation_required'], mcp_reverse['code'],
    ) == (201, 201, 400, True, 'VALIDATION_ERROR'), (created.data, later_payment.data, rest_reverse.data, mcp_reverse)
    assert 'impide revertir' in mcp_reverse['message']
    assert (
        IncomeSettlement.objects.filter(status=IncomeSettlement.Status.ACTIVE).count(),
        PocketMovement.objects.count(),
        IncomeRecord.objects.filter(pk=follow_up.pk, kind='expected').count(),
        IncomeRecord.objects.filter(expected_income=follow_up, kind='liquid').count(),
    ) == (2, 2, 1, 1)


def test_ledger_confirmed_settlement_update_persists_json_safe_revision(
    super_client, api_client, accounting_ledger_token, make_income,
):
    """Falla si confirmar una corrección guarda UUID o fecha crudos y deja efectos viejos."""
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    created = super_client.post('/api/accounting/incomes/bulk-settle/', _settlement_payload(
        income.pk, total_amount='80.00', gustavo_amount='50.00', carlos_amount='30.00',
    ), format='json')
    settlement_id = created.data['settlement_id']
    preview = _tool_payload(_call_accounting_tool(
        api_client, accounting_ledger_token, 'update_income_settlement',
        _settlement_payload(
            income.pk, settlement_id=settlement_id, revision=1, total_amount='90.00',
            gustavo_amount='50.00', carlos_amount='40.00',
            deductions=[{'type': 'bank_fee', 'amount': '10.00'}],
        ), slug='accounting-ledger',
    ))
    confirmed = _tool_payload(_call_accounting_tool(
        api_client, accounting_ledger_token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']}, slug='accounting-ledger',
    ))

    result = confirmed['result']
    intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
    operation = IncomeSettlement.objects.get(pk=settlement_id)
    assert created.status_code == 201, created.data
    assert (preview['confirmation_required'], result['id'], result['status'], result['revision']) == (
        True, settlement_id, 'active', 2,
    )
    assert (isinstance(result['created_at'], str), isinstance(result['updated_at'], str)) == (True, True)
    assert (intent.status, intent.result['id'], intent.result['revision']) == ('executed', settlement_id, 2)
    assert (
        operation.status, operation.revision, PocketMovement.objects.get().amount,
        list(ExpenseRecord.objects.values_list('total_amount', flat=True)),
    ) == (IncomeSettlement.Status.ACTIVE, 2, Decimal('90.00'), [Decimal('10.00')])


def test_ledger_confirmed_settlement_reversal_persists_json_safe_result(
    super_client, api_client, accounting_ledger_token, make_income,
):
    """Falla si confirmar una reversa no puede guardar sus fechas o conserva efectos contables."""
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    created = super_client.post('/api/accounting/incomes/bulk-settle/', _settlement_payload(
        income.pk, total_amount='80.00', gustavo_amount='50.00', carlos_amount='30.00',
    ), format='json')
    settlement_id = created.data['settlement_id']
    preview = _tool_payload(_call_accounting_tool(
        api_client, accounting_ledger_token, 'reverse_income_settlement',
        {'settlement_id': settlement_id, 'revision': 1}, slug='accounting-ledger',
    ))
    confirmed = _tool_payload(_call_accounting_tool(
        api_client, accounting_ledger_token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']}, slug='accounting-ledger',
    ))

    result = confirmed['result']
    intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
    operation = IncomeSettlement.objects.get(pk=settlement_id)
    assert created.status_code == 201, created.data
    assert (preview['confirmation_required'], result['id'], result['status'], result['revision']) == (
        True, settlement_id, 'reversed', 2,
    )
    assert (isinstance(result['created_at'], str), isinstance(result['updated_at'], str)) == (True, True)
    assert (intent.status, intent.result['status'], intent.result['revision']) == ('executed', 'reversed', 2)
    assert (
        operation.status, operation.revision, PocketMovement.objects.count(),
        ExpenseRecord.objects.count(),
        IncomeRecord.objects.filter(expected_income=income, kind='liquid').count(),
    ) == (IncomeSettlement.Status.REVERSED, 2, 0, 0, 0)


def test_bulk_hosting_window_is_restored_on_reversal(
    super_client, make_income,
):
    """Falla si una ventana colectiva queda en el líquido o si revertirla deja fechas huérfanas."""
    income = make_income(
        origin=IncomeRecord.Origin.HOSTING, total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
    )
    created = super_client.post('/api/accounting/incomes/bulk-settle/', {
        'income_ids': [income.pk], 'total_amount': '100.00',
        'period_date': '2026-10-19', 'destination': 'pocket',
        'periods': [{
            'income_id': income.pk, 'period_start': '2026-01-01',
            'period_end': '2026-12-31', 'period_cadence': 'annual',
        }],
    }, format='json')
    settlement_id = created.data['settlement_id']
    income.refresh_from_db()
    applied_window = (income.period_start, income.period_end, income.period_cadence)
    reversed_settlement = super_client.delete(
        f'/api/accounting/income-settlements/{settlement_id}/', {'revision': 1}, format='json',
    )
    income.refresh_from_db()

    assert created.status_code == 201, created.data
    assert reversed_settlement.status_code == 200, reversed_settlement.data
    assert applied_window == (date(2026, 1, 1), date(2026, 12, 31), 'annual')
    assert (income.period_start, income.period_end, income.period_cadence) == (None, None, '')
    assert IncomeRecord.objects.filter(
        expected_income=income, period_start__isnull=False,
    ).count() == 0


def test_bulk_confirmation_subset_is_idempotent(
    super_client, make_income, make_client_profile, mailoutbox,
):
    """Falla si un abono colectivo avisa a otro cliente, avisa por cero o duplica un reintento."""
    first = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'), client=make_client_profile(email='one@example.com'),
    )
    zero_cash = make_income(
        concept='Sin efectivo', period_date=date(2026, 10, 2), total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
        client=make_client_profile(email='zero@example.com'),
    )
    unselected = make_income(
        concept='No seleccionado', period_date=date(2026, 10, 3), total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
        client=make_client_profile(email='other@example.com'),
    )
    _issued_collection_account(first, 'pay-one@example.com')
    _issued_collection_account(zero_cash, 'pay-zero@example.com')
    _issued_collection_account(unselected, 'pay-other@example.com')
    request_data = {
        'income_ids': [first.pk, zero_cash.pk, unselected.pk],
        'allocations': [
            {'income_id': first.pk, 'amount': '100.00'},
            {'income_id': zero_cash.pk, 'amount': '0.00'},
            {'income_id': unselected.pk, 'amount': '100.00'},
        ],
        'total_amount': '200.00', 'period_date': '2026-10-19', 'destination': 'pocket',
        'send_payment_confirmation': True, 'confirmation_income_ids': [first.pk, zero_cash.pk],
        'request_id': str(uuid4()),
    }

    created = super_client.post('/api/accounting/incomes/bulk-settle/', request_data, format='json')
    replay = super_client.post('/api/accounting/incomes/bulk-settle/', request_data, format='json')

    confirmations = created.data['payment_confirmations']
    sent_logs = EmailLog.objects.filter(template_key='income_payment_received_client')
    assert (created.status_code, replay.status_code, replay.data['payment_confirmations']) == (201, 201, [])
    assert [(row['income_id'], row['status'], row['recipient']) for row in confirmations] == [
        (first.pk, 'sent', 'pay-one@example.com'),
        (zero_cash.pk, 'skipped', ''),
        (unselected.pk, 'not_requested', ''),
    ]
    assert list(sent_logs.values_list('client_id', flat=True)) == [first.client_id]
    assert [message.to for message in mailoutbox] == [['pay-one@example.com']]


def test_generic_income_delete_rejects_an_active_grouped_settlement_parent(
    super_client, make_income,
):
    """Falla si borrar el esperado original deja sus líquidos o deducciones huérfanos."""
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    created = super_client.post('/api/accounting/incomes/bulk-settle/', _settlement_payload(
        income.pk, total_amount='80.00', gustavo_amount='40.00', carlos_amount='40.00',
    ), format='json')

    deleted = super_client.delete(f'/api/accounting/incomes/{income.pk}/delete/')

    assert created.status_code == 201, created.data
    assert deleted.status_code == 400
    assert IncomeRecord.objects.filter(pk=income.pk, kind='expected').count() == 1
    assert ExpenseRecord.objects.filter(source_income=income, settlement_id=created.data['settlement_id']).count() == 1
    assert PocketMovement.objects.filter(income_settlement__pk=created.data['settlement_id']).count() == 1


def test_unallocated_selected_income_stays_protected_until_the_settlement_reverses(
    super_client, make_income,
):
    """Falla si un esperado seleccionado sin abono puede borrarse y rompe la corrección del grupo."""
    first = make_income(
        concept='Con abono', total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
    )
    second = make_income(
        concept='Sin abono', period_date=date(2026, 10, 2), total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
    )
    created = super_client.post('/api/accounting/incomes/bulk-settle/', _settlement_payload(
        first.pk, second.pk, total_amount='50.00', deductions=[],
        gustavo_amount='25.00', carlos_amount='25.00', allocations=[
            {'income_id': first.pk, 'amount': '50.00'},
            {'income_id': second.pk, 'amount': '0.00'},
        ],
    ), format='json')
    settlement_id = created.data['settlement_id']

    blocked_delete = super_client.delete(f'/api/accounting/incomes/{second.pk}/delete/')
    reversed_settlement = super_client.delete(
        f'/api/accounting/income-settlements/{settlement_id}/', {'revision': 1}, format='json',
    )
    allowed_delete = super_client.delete(f'/api/accounting/incomes/{second.pk}/delete/')

    assert (
        created.status_code, blocked_delete.status_code,
        reversed_settlement.status_code, allowed_delete.status_code,
    ) == (201, 400, 200, 204), (
        created.data, blocked_delete.data, reversed_settlement.data,
    )
    assert IncomeSettlement.objects.get(pk=settlement_id).status == IncomeSettlement.Status.REVERSED
    assert IncomeRecord.objects.filter(pk=second.pk).count() == 0


def test_preview_query_count_is_constant_for_ten_distinct_clients(
    make_income, make_client_profile,
):
    """Falla si la vista previa vuelve a consultar cliente, cuenta o saldo por cada ingreso seleccionado."""
    one_income = _client_income_group(make_income, make_client_profile, 1)
    ten_incomes = _client_income_group(make_income, make_client_profile, 10)

    one_query_count = _preview_query_count(one_income)
    ten_query_count = _preview_query_count(ten_incomes)

    assert ten_query_count == one_query_count
