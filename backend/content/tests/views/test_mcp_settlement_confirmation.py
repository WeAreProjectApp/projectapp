"""Confirmation and schema guards for the unified MCP settlement tools."""
import json
from decimal import Decimal
from uuid import uuid4

import pytest

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentType,
    IncomeRecord,
    IncomeSettlement,
    McpActionIntent,
    McpConnector,
    McpCredential,
    PocketMovement,
)


pytestmark = pytest.mark.django_db


CATALOGS = ('accounting', 'accounting-ledger')


def _rpc(name, arguments):
    return {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }


def _call(api_client, slug, token, name, arguments):
    return api_client.post(
        f'/api/mcp/{slug}/{token}/', _rpc(name, arguments), format='json',
    )


def _payload(response):
    assert response.status_code == 200, response.data
    assert response.data['result']['isError'] is False, response.data
    return json.loads(response.data['result']['content'][0]['text'])


def _error(response):
    assert response.status_code == 200, response.data
    assert response.data['result']['isError'] is True, response.data
    return response.data['result']['structuredContent']['error']


def _credential(slug):
    connector, _ = McpConnector.objects.update_or_create(
        slug=slug,
        defaults={
            'name': f'Contabilidad {slug}',
            'is_active': True,
            'retired_at': None,
            'aliases_retired_at': None,
        },
    )
    credential = McpCredential.objects.create(
        connector=connector,
        label=f'Confirmation regression {slug}',
        catalog='canonical',
    )
    return credential.generate_token()


def _issued_account(income, email):
    document = Document.objects.create(
        document_type=DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )[0],
        title=f'Cuenta {income.pk}',
        commercial_status=Document.CommercialStatus.ISSUED,
        income_record=income,
        client_user=income.client.user,
        public_number=f'PA-CONFIRM-{income.pk}',
        total=income.total_amount,
    )
    return DocumentCollectionAccount.objects.create(
        document=document, customer_email=email,
    )


def _settlement_arguments(income, **overrides):
    arguments = {
        'income_ids': [income.pk],
        'total_amount': '100.00',
        'period_date': '2026-10-20',
        'destination': 'pocket',
        'gustavo_amount': '50.00',
        'carlos_amount': '50.00',
        'send_payment_confirmation': True,
        'confirmation_income_ids': [income.pk],
    }
    arguments.update(overrides)
    return arguments


@pytest.mark.parametrize('slug', CATALOGS)
def test_bulk_confirmation_rejects_a_recipient_changed_after_preview_without_effects(
    api_client, make_client_profile, make_income, mailoutbox, slug,
):
    """Fails if confirming a reviewed settlement can send money or email to a later recipient."""
    token = _credential(slug)
    income = make_income(
        client=make_client_profile(email='client@example.test'),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    issued = _issued_account(income, 'reviewed@example.test')

    preview = _payload(_call(
        api_client, slug, token, 'bulk_settle_incomes', _settlement_arguments(income),
    ))
    issued.customer_email = 'changed-after-preview@example.test'
    issued.save(update_fields=['customer_email'])
    rejected = _error(_call(
        api_client, slug, token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    ))

    assert preview['confirmation_required'] is True
    assert rejected['code'] == 'STALE_VERSION'
    assert (IncomeSettlement.objects.count(), PocketMovement.objects.count()) == (0, 0)
    assert mailoutbox == []


@pytest.mark.parametrize('slug', CATALOGS)
def test_bulk_confirmation_applies_the_unchanged_reviewed_recipient(
    api_client, make_client_profile, make_income, mailoutbox,
    django_capture_on_commit_callbacks, slug,
):
    """Fails if the stale-preview protection rejects the exact recipient that was reviewed."""
    token = _credential(slug)
    income = make_income(
        client=make_client_profile(email='client@example.test'),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    _issued_account(income, 'reviewed@example.test')

    preview = _payload(_call(
        api_client, slug, token, 'bulk_settle_incomes', _settlement_arguments(income),
    ))
    with django_capture_on_commit_callbacks(execute=True):
        confirmed = _payload(_call(
            api_client, slug, token, 'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        ))

    assert (preview['confirmation_required'], confirmed['confirmed']) == (True, True)
    assert (IncomeSettlement.objects.count(), PocketMovement.objects.count()) == (1, 1)
    assert [message.to for message in mailoutbox] == [['reviewed@example.test']]


@pytest.mark.parametrize('slug', CATALOGS)
def test_bulk_confirmation_rejects_a_balance_changed_after_preview_without_effects(
    api_client, make_client_profile, make_income, mailoutbox, slug,
):
    """Fails if confirming a reviewed settlement can apply after its expected balance changed."""
    token = _credential(slug)
    income = make_income(
        client=make_client_profile(email='client@example.test'),
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    _issued_account(income, 'reviewed@example.test')

    preview = _payload(_call(
        api_client, slug, token, 'bulk_settle_incomes', _settlement_arguments(income),
    ))
    make_income(
        concept='Pago que cambió el saldo', kind=IncomeRecord.Kind.LIQUID,
        expected_income=income, total_amount=Decimal('1.00'),
        gustavo_amount=Decimal('1.00'), carlos_amount=Decimal('0.00'),
    )
    rejected = _error(_call(
        api_client, slug, token, 'confirm_action',
        {'confirmation_id': preview['confirmation_id']},
    ))

    assert preview['confirmation_required'] is True
    assert rejected['code'] == 'STALE_VERSION'
    assert (IncomeSettlement.objects.count(), PocketMovement.objects.count()) == (0, 0)
    assert mailoutbox == []


@pytest.mark.parametrize('slug', CATALOGS)
@pytest.mark.parametrize('tool_name', (
    'bulk_settle_incomes',
    'preview_income_settlement',
    'get_income_settlement',
    'update_income_settlement',
    'reverse_income_settlement',
))
def test_settlement_tools_reject_unknown_arguments_before_creating_an_intent(
    api_client, make_income, slug, tool_name,
):
    """Fails if a closed settlement schema lets an unknown field reach a confirmation intent."""
    token = _credential(slug)
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    settlement_id = str(uuid4())
    arguments_by_tool = {
        'bulk_settle_incomes': _settlement_arguments(income),
        'preview_income_settlement': _settlement_arguments(income),
        'get_income_settlement': {'settlement_id': settlement_id},
        'update_income_settlement': {
            **_settlement_arguments(income),
            'settlement_id': settlement_id,
            'revision': 1,
        },
        'reverse_income_settlement': {'settlement_id': settlement_id, 'revision': 1},
    }
    arguments = {**arguments_by_tool[tool_name], 'unexpected_review_argument': True}

    rejected = _error(_call(api_client, slug, token, tool_name, arguments))

    assert rejected['code'] == 'unknown_field'
    assert rejected['details']['errors'] == [{
        'field': 'unexpected_review_argument',
        'code': 'unknown_field',
        'message': 'Campo desconocido o de solo lectura.',
    }]
    assert McpActionIntent.objects.count() == 0


@pytest.mark.parametrize('slug', CATALOGS)
@pytest.mark.parametrize('tool_name', ('update_income_settlement', 'reverse_income_settlement'))
def test_settlement_mutations_require_revision_before_creating_an_intent(
    api_client, make_income, slug, tool_name,
):
    """Fails if correcting or reversing without a revision creates a stale confirmation intent."""
    token = _credential(slug)
    income = make_income(
        total_amount=Decimal('100.00'), gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
    )
    settlement_id = str(uuid4())
    arguments_by_tool = {
        'update_income_settlement': {
            **_settlement_arguments(income), 'settlement_id': settlement_id,
        },
        'reverse_income_settlement': {'settlement_id': settlement_id},
    }

    rejected = _error(_call(api_client, slug, token, tool_name, arguments_by_tool[tool_name]))

    assert rejected['code'] == 'VALIDATION_ERROR'
    assert ('revision', 'required') in [
        (row['field'], row['code']) for row in rejected['details']['errors']
    ]
    assert McpActionIntent.objects.count() == 0
