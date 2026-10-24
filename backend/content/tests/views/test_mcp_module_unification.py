"""HTTP contracts for the canonical one-connector-per-module MCP catalog."""
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG
from content.mcp.module_catalog import INFRASTRUCTURE_TOOLS, catalog_problems
from content.models import (
    IncomeRecord,
    McpActionIntent,
    McpConnector,
    McpCredential,
    McpUsageDaily,
)

pytestmark = pytest.mark.django_db


def _rpc(method, params=None):
    message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _result(response):
    return response.data['result']


def _payload(response):
    return json.loads(_result(response)['content'][0]['text'])


def _endpoint(api_client, token, method, params=None, *, slug='accounting'):
    return api_client.post(
        f'/api/mcp/{slug}/{token}/', _rpc(method, params), format='json',
    )


def _credential(
    connector, label, token, *, catalog='canonical', allowed_tools=None,
    income_kinds=None,
):
    return McpCredential.objects.create(
        connector=connector,
        label=label,
        catalog=catalog,
        token_hash=McpCredential.hash_token(token),
        token_prefix=token[:8],
        allowed_tools=allowed_tools or [],
        income_kinds=income_kinds or [],
    )


@pytest.fixture
def accounting_connector():
    connector, _ = McpConnector.objects.update_or_create(
        slug='accounting',
        defaults={'name': 'Contabilidad', 'is_active': True, 'retired_at': None, 'aliases_retired_at': None},
    )
    connector.credentials.all().delete()
    return connector


def test_canonical_catalog_enforces_unique_module_ownership():
    """Fails if consolidation exposes two canonical connectors for one module."""
    canonical = {
        spec.module_id: slug for slug, spec in CONNECTORS.items()
        if not spec.compatibility
    }
    assert canonical == {
        'overview': 'operations', 'commercial': 'commercial', 'platform': 'projects',
        'documents': 'documents', 'communications': 'communications', 'site': 'content',
        'accounting': 'accounting', 'tasks': 'tasks', 'offerings': 'offerings',
        'programs': 'programs',
    }
    ownership = {
        name: slug
        for slug, spec in CONNECTORS.items() if not spec.compatibility
        for name in (tool['name'] for tool in TOOLS_BY_SLUG[slug])
        if name not in INFRASTRUCTURE_TOOLS
    }
    assert {
        'list_clients': ownership['list_clients'],
        'list_hour_packages': ownership['list_hour_packages'],
        'create_additional_module': ownership['create_additional_module'],
        'get_partnership_agreement': ownership['get_partnership_agreement'],
        'get_building_with_us_program': ownership['get_building_with_us_program'],
        'get_building_on_demand_program': ownership['get_building_on_demand_program'],
    } == {
        'list_clients': 'commercial', 'list_hour_packages': 'offerings',
        'create_additional_module': 'offerings', 'get_partnership_agreement': 'programs',
        'get_building_with_us_program': 'programs',
        'get_building_on_demand_program': 'programs',
    }
    assert catalog_problems(CONNECTORS, TOOLS_BY_SLUG) == []


def _panel_segmentation_connectors():
    for slug in ('commercial', 'offerings', 'programs', 'additional-modules',
                 'partnership-program', 'building-on-demand'):
        McpConnector.objects.update_or_create(
            slug=slug,
            defaults={'name': slug, 'is_active': False, 'retired_at': None,
                      'aliases_retired_at': None},
        )


@pytest.mark.parametrize(
    ('slug', 'field', 'phrase'),
    [
        ('commercial', 'description', 'relación con clientes'),
        ('commercial', 'section_note', 'Defaults'),
        ('offerings', 'description', 'paquetes de requerimientos'),
        ('offerings', 'section_note', 'Módulos adicionales'),
        ('programs', 'description', 'Building on Demand'),
        ('programs', 'section_note', 'contratos'),
    ],
)
def test_panel_explains_canonical_connector_scope(
    super_client, slug, field, phrase,
):
    """Fails if the MCP detail accordion loses the explanation of a canonical section."""
    _panel_segmentation_connectors()
    response = super_client.get('/api/mcp-connectors/')
    connectors = {item['slug']: item for item in response.data}

    assert response.status_code == 200
    assert phrase.lower() in connectors[slug][field].lower()


@pytest.mark.parametrize(
    ('slug', 'phrase'),
    [
        ('additional-modules', 'Nuestra oferta'),
        ('partnership-program', 'Programas'),
        ('building-on-demand', 'Programas'),
    ],
)
def test_panel_describes_retiring_connector_replacement(
    super_client, slug, phrase,
):
    """Fails if a retiring MCP detail omits the section that replaces it."""
    _panel_segmentation_connectors()
    response = super_client.get('/api/mcp-connectors/')
    connectors = {item['slug']: item for item in response.data}

    assert response.status_code == 200
    assert phrase.lower() in connectors[slug]['description'].lower()


@pytest.mark.parametrize(
    ('slug', 'field', 'other_field', 'resource_prefix'),
    [
        ('commercial', 'show_proposal_video', 'show_financing_video', 'proposal:'),
        ('offerings', 'show_additional_modules_video', 'show_proposal_video', 'additional-modules:'),
        ('programs', 'show_financing_video', 'show_additional_modules_video', 'financing:'),
    ],
)
def test_section_video_tools_expose_only_their_own_switch(
    api_client, slug, field, other_field, resource_prefix,
):
    """Fails if a segmented MCP can read or submit another section's video switch."""
    connector, _ = McpConnector.objects.update_or_create(
        slug=slug,
        defaults={'name': slug, 'is_active': True, 'retired_at': None,
                  'aliases_retired_at': None},
    )
    connector.credentials.all().delete()
    token = f'{slug}-video-scope'
    _credential(connector, 'Video scope', token)
    resource = {'commercial': 'proposal', 'offerings': 'additional_modules', 'programs': 'partnership'}[slug]

    read = _payload(_endpoint(
        api_client, token, 'tools/call',
        {'name': f'get_{resource}_video_settings', 'arguments': {}}, slug=slug,
    ))
    rejected = _payload(_endpoint(
        api_client, token, 'tools/call',
        {'name': f'update_{resource}_video_settings', 'arguments': {other_field: False}}, slug=slug,
    ))

    assert set(read) == {field, 'resources', 'updated_at'}
    assert all(key.startswith(resource_prefix) for key in read['resources'])
    assert rejected['error']['code'] == 'VALIDATION_ERROR'


@pytest.mark.parametrize(
    ('slug', 'expected_tool'),
    [('offerings', 'list_hour_packages'), ('programs', 'get_building_with_us_program')],
)
def test_new_section_primary_token_exposes_its_canonical_catalog(api_client, slug, expected_tool):
    """Fails if generating a new section's primary token exposes only a compatibility fragment."""
    connector, _ = McpConnector.objects.update_or_create(
        slug=slug, defaults={'name': slug, 'is_active': True, 'retired_at': None},
    )
    connector.credentials.all().delete()

    token = connector.generate_token()
    response = _endpoint(api_client, token, 'tools/list', slug=slug)

    assert connector.credentials.get(label='Default').catalog == 'canonical'
    assert response.status_code == 200
    assert expected_tool in {tool['name'] for tool in _result(response)['tools']}


def test_pre_split_access_survives_legacy_alias_retirement(api_client):
    """Fails if previously retired legacy aliases disable a preserved commercial consumer."""
    connector, _ = McpConnector.objects.update_or_create(
        slug='commercial', defaults={
            'name': 'Comercial', 'is_active': True, 'retired_at': None,
            'aliases_retired_at': datetime(2026, 10, 1, tzinfo=UTC),
            'pre_split_retired_at': None,
        },
    )
    token = 'preserved-pre-split-token'
    _credential(connector, 'Preserved split scope', token,
                catalog='pre_split', allowed_tools=['list_clients'])

    response = _endpoint(api_client, token, 'tools/list', slug='commercial')

    assert response.status_code == 200
    assert 'list_clients' in {tool['name'] for tool in _result(response)['tools']}


def test_pre_split_access_does_not_reopen_a_retired_hidden_alias(api_client):
    """Fails if preserving Commercial access revives an already retired legacy operation."""
    connector, _ = McpConnector.objects.update_or_create(
        slug='commercial', defaults={
            'name': 'Comercial', 'is_active': True, 'retired_at': None,
            'aliases_retired_at': datetime(2026, 10, 1, tzinfo=UTC),
            'pre_split_retired_at': None,
        },
    )
    token = 'retired-hidden-pre-split-token'
    _credential(connector, 'Preserved full scope', token, catalog='pre_split')

    response = _endpoint(api_client, token, 'tools/call', {
        'name': 'launch_proposal_to_platform', 'arguments': {},
    }, slug='commercial')

    assert response.status_code == 410
    assert response.data['error']['code'] == 'CONNECTOR_RETIRED'


def test_catalog_rejects_a_second_canonical_accounting_connector():
    """Fails if a future registry entry can silently claim Contable a second time."""
    mirror = replace(
        CONNECTORS['accounting'], slug='accounting-mirror', compatibility=False,
        module_id='accounting', canonical_area='accounting',
    )
    connectors = {**CONNECTORS, mirror.slug: mirror}
    tools = {**TOOLS_BY_SLUG, mirror.slug: []}

    assert 'accounting-mirror: duplicate or missing module accounting' in catalog_problems(connectors, tools)


@pytest.mark.parametrize(
    ('catalog', 'allowed_tool', 'expected_name'),
    [('canonical', 'list_incomes', 'list_incomes'), ('legacy', 'list_income', 'list_income')],
)
def test_credential_catalog_discovery_preserves_its_existing_scope(
    api_client, accounting_connector, catalog, allowed_tool, expected_name,
):
    """Fails if migrating a credential broadens its tool scope or hides its compatible name."""
    token = f'{catalog}-scope-token'
    _credential(
        accounting_connector, f'{catalog} scope', token, catalog=catalog,
        allowed_tools=[allowed_tool],
    )

    response = _endpoint(api_client, token, 'tools/list')
    names = {tool['name'] for tool in _result(response)['tools']}

    assert response.status_code == 200
    assert names == {expected_name, 'describe_capabilities', 'confirm_action', 'cancel_action'}


def test_canonical_credential_hides_and_forbids_legacy_alias(api_client, accounting_connector):
    """Fails if an undiscoverable compatibility alias can bypass a canonical credential's scope."""
    token = 'canonical-alias-scope-token'
    _credential(
        accounting_connector, 'Canonical alias scope', token,
        allowed_tools=['list_incomes'],
    )

    listed = _endpoint(api_client, token, 'tools/list')
    attempted = _endpoint(
        api_client, token, 'tools/call', {'name': 'list_income', 'arguments': {}},
    )

    assert 'list_income' not in {tool['name'] for tool in _result(listed)['tools']}
    assert _result(attempted)['isError'] is True
    assert _result(attempted)['structuredContent']['error']['code'] == 'FORBIDDEN'


def test_retired_legacy_credential_returns_a_machine_readable_replacement(
    api_client, accounting_connector,
):
    """Fails if a retired compatibility credential becomes an ambiguous 404 instead of naming its replacement."""
    token = 'retired-legacy-token'
    _credential(
        accounting_connector, 'Retired legacy', token, catalog='legacy',
        allowed_tools=['list_income'],
    )
    accounting_connector.aliases_retired_at = datetime(2026, 10, 19, tzinfo=UTC)
    accounting_connector.save(update_fields=['aliases_retired_at'])

    response = _endpoint(api_client, token, 'tools/list')

    assert response.status_code == 410
    assert response.data['error']['code'] == 'CONNECTOR_RETIRED'
    assert 'accounting' in response.data['error']['message']


def test_retired_accounting_alias_rejects_list_income_for_a_full_canonical_credential(
    api_client, accounting_connector,
):
    """Fails if a canonical full-scope credential can keep executing an alias after alias retirement."""
    token = 'retired-canonical-alias-token'
    _credential(accounting_connector, 'Canonical full scope', token)
    accounting_connector.aliases_retired_at = datetime(2026, 10, 19, tzinfo=UTC)
    accounting_connector.save(update_fields=['aliases_retired_at'])

    response = _endpoint(
        api_client, token, 'tools/call', {'name': 'list_income', 'arguments': {}},
    )

    assert response.status_code == 410
    assert response.data['error']['code'] == 'CONNECTOR_RETIRED'


def test_retiring_pre_split_commercial_access_leaves_the_new_canonical_catalog_usable(api_client):
    """Fails if the pre-segmentation retirement flag disables the new Comercial credential too."""
    connector, _ = McpConnector.objects.update_or_create(
        slug='commercial',
        defaults={'name': 'Comercial', 'is_active': True, 'retired_at': None,
                  'aliases_retired_at': None, 'pre_split_retired_at': datetime(2026, 10, 20, tzinfo=UTC)},
    )
    connector.credentials.all().delete()
    old_token, new_token = 'pre-split-retired-token', 'canonical-commercial-token'
    _credential(connector, 'Pre-split retired', old_token, catalog='pre_split', allowed_tools=['list_clients'])
    _credential(connector, 'Canonical commercial', new_token, allowed_tools=['list_clients'])

    retired = _endpoint(api_client, old_token, 'tools/list', slug='commercial')
    usable = _endpoint(api_client, new_token, 'tools/list', slug='commercial')

    assert (retired.status_code, retired.data['error']['code']) == (410, 'CONNECTOR_RETIRED')
    assert usable.status_code == 200
    assert 'list_clients' in {tool['name'] for tool in _result(usable)['tools']}


def test_canonical_commercial_scope_cannot_grant_a_hidden_pre_split_alias(super_client):
    """Fails if a current credential can be expanded with the retired proposal-launch alias."""
    connector, _ = McpConnector.objects.update_or_create(
        slug='commercial',
        defaults={'name': 'Comercial', 'is_active': True, 'retired_at': None,
                  'aliases_retired_at': None, 'pre_split_retired_at': None},
    )
    connector.credentials.all().delete()
    credential = _credential(
        connector, 'Current commercial scope', 'current-commercial-scope',
        allowed_tools=['list_clients'],
    )

    response = super_client.patch(
        f'/api/mcp-connectors/commercial/credentials/{credential.pk}/',
        {'allowed_tools': ['launch_proposal_to_platform']}, format='json',
    )

    credential.refresh_from_db()
    assert response.status_code == 400
    assert 'launch_proposal_to_platform' in str(response.data['detail'])
    assert credential.allowed_tools == ['list_clients']


def test_malformed_modern_request_records_legacy_usage_before_rejection(
    api_client, accounting_connector,
):
    """Fails if an invalid modern envelope bypasses durable usage evidence for a legacy credential."""
    token = 'malformed-legacy-token'
    credential = _credential(
        accounting_connector, 'Malformed legacy', token, catalog='legacy',
        allowed_tools=['list_income'],
    )

    response = api_client.post(
        f'/api/mcp/accounting/{token}/', _rpc('tools/list'), format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
    )

    usage = McpUsageDaily.objects.get(credential=credential)
    assert response.status_code == 400
    assert response.data['error']['code'] == -32020
    assert (usage.legacy, usage.tool_name, usage.count) == (True, '', 1)


def test_expected_income_requires_preview_and_its_confirmation_owner(
    api_client, accounting_connector,
):
    """Fails if an expected income writes before confirmation or another credential can approve it."""
    owner_token, other_token = 'income-owner-token', 'income-other-token'
    _credential(accounting_connector, 'Income owner', owner_token, allowed_tools=['create_income'])
    _credential(accounting_connector, 'Income other', other_token, allowed_tools=['create_income'])
    arguments = {
        'concept': 'Cobro esperado unificado', 'kind': 'expected', 'origin': 'development',
        'vat_rate': None, 'period_date': '2026-11-01', 'total_amount': '1200',
    }

    preview = _payload(_endpoint(
        api_client, owner_token, 'tools/call', {'name': 'create_income', 'arguments': arguments},
    ))
    assert preview['confirmation_required'] is True
    assert IncomeRecord.objects.count() == 0
    rejected = _result(_endpoint(api_client, other_token, 'tools/call', {
        'name': 'confirm_action', 'arguments': {'confirmation_id': preview['confirmation_id']},
    }))
    confirmed = _payload(_endpoint(api_client, owner_token, 'tools/call', {
        'name': 'confirm_action', 'arguments': {'confirmation_id': preview['confirmation_id']},
    }))

    assert rejected['structuredContent']['error']['code'] == 'FORBIDDEN'
    saved = IncomeRecord.objects.get(pk=confirmed['result']['income']['id'])
    assert (saved.kind, saved.total_amount, saved.vat_rate) == ('expected', Decimal('1200.00'), None)
    assert McpActionIntent.objects.get(pk=preview['confirmation_id']).credential.label == 'Income owner'


@pytest.mark.parametrize('kind', ['liquid', 'lost'])
def test_unified_income_confirms_non_expected_kinds_without_vat(
    api_client, accounting_connector, kind,
):
    """Fails if a liquid or lost income inherits the expected-only IVA requirement."""
    token = f'{kind}-income-token'
    _credential(accounting_connector, f'{kind} income', token, allowed_tools=['create_income'])
    preview = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'create_income',
        'arguments': {
            'concept': f'Ingreso {kind}', 'kind': kind, 'origin': 'development',
            'period_date': '2026-11-01', 'total_amount': '400',
        },
    }))
    confirmed = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'confirm_action', 'arguments': {'confirmation_id': preview['confirmation_id']},
    }))

    saved = IncomeRecord.objects.get(pk=confirmed['result']['income']['id'])
    assert (saved.kind, saved.total_amount) == (kind, Decimal('400.00'))


def test_unified_expected_income_requires_vat_on_create(api_client, accounting_connector):
    """Fails if expected-income creation can omit its explicit IVA classification."""
    token = 'expected-guard-token'
    _credential(
        accounting_connector, 'Expected guard', token,
        allowed_tools=['create_income'],
    )

    missing_vat = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'create_income',
        'arguments': {
            'concept': 'Sin IVA', 'kind': 'expected', 'origin': 'development',
            'period_date': '2026-11-01', 'total_amount': '400',
        },
    }))
    assert missing_vat['error']['code'] == 'VALIDATION_ERROR'
    assert missing_vat['error']['details']['errors'][0]['field'] == 'vat_rate'


def test_unified_expected_income_blocks_financial_update_after_payment(
    api_client, accounting_connector, make_income,
):
    """Fails if payment-linked expected income permits a financial update through the unified endpoint."""
    token = 'expected-payment-lock-token'
    _credential(accounting_connector, 'Expected payment lock', token, allowed_tools=['update_income'])
    expected = make_income(kind='expected', total_amount=Decimal('1000.00'))
    make_income(
        kind='liquid', expected_income=expected, total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
    )

    locked = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'update_income',
        'arguments': {
            'income_id': expected.pk, 'total_amount': '1200',
            'gustavo_amount': '600', 'carlos_amount': '600', 'company_amount': '0',
        },
    }))

    assert locked['error']['code'] == 'INCOME_LOCKED'
    assert locked['error']['details']['blockers'][0]['code'] == 'payments'
    expected.refresh_from_db()
    assert expected.total_amount == Decimal('1000.00')


def test_unified_income_can_change_an_unpaid_expected_income_to_lost(
    api_client, accounting_connector, make_income,
):
    """Fails if the unified serializer drops an unpaid expected-to-lost kind change."""
    token = 'expected-to-lost-token'
    _credential(accounting_connector, 'Expected to lost', token, allowed_tools=['update_income'])
    expected = make_income(kind='expected')

    preview = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'update_income',
        'arguments': {'income_id': expected.pk, 'kind': 'lost'},
    }))

    assert preview['confirmation_required'] is True
    expected.refresh_from_db()
    assert expected.kind == 'expected'

    confirmed = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'confirm_action', 'arguments': {'confirmation_id': preview['confirmation_id']},
    }))

    expected.refresh_from_db()
    assert confirmed['confirmed'] is True
    assert expected.kind == 'lost'


def test_unified_income_blocks_expected_to_lost_after_payment(
    api_client, accounting_connector, make_income,
):
    """Fails if a paid expected income can be written off through the unified endpoint."""
    token = 'paid-expected-to-lost-token'
    _credential(accounting_connector, 'Paid expected to lost', token, allowed_tools=['update_income'])
    expected = make_income(kind='expected', total_amount=Decimal('1000.00'))
    make_income(
        kind='liquid', expected_income=expected, total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'),
    )

    rejected = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'update_income',
        'arguments': {'income_id': expected.pk, 'kind': 'lost'},
    }))

    assert rejected['error']['code'] == 'INCOME_LOCKED'
    expected.refresh_from_db()
    assert expected.kind == 'expected'


def _expected_only_credential(accounting_connector):
    token = 'expected-only-token'
    return token, _credential(
        accounting_connector, 'Expected only', token,
        allowed_tools=['list_incomes', 'get_income', 'create_income'],
        income_kinds=['expected'],
    )


def test_expected_only_credential_lists_only_expected_income(
    api_client, accounting_connector, make_income,
):
    """Fails if expected-only migration exposes liquid or lost rows in the unified list."""
    token, _ = _expected_only_credential(accounting_connector)
    expected = make_income(kind='expected')
    make_income(kind='liquid', concept='Ingreso líquido')
    make_income(kind='lost', concept='Ingreso perdido')

    listed = _payload(_endpoint(
        api_client, token, 'tools/call', {'name': 'list_incomes', 'arguments': {}},
    ))

    assert [row['id'] for row in listed['results']] == [expected.pk]


def test_expected_only_credential_cannot_get_liquid_income(
    api_client, accounting_connector, make_income,
):
    """Fails if expected-only migration permits reading a liquid income by identifier."""
    token, _ = _expected_only_credential(accounting_connector)
    liquid = make_income(kind='liquid', concept='Ingreso líquido')
    got_liquid = _payload(_endpoint(
        api_client, token, 'tools/call', {'name': 'get_income', 'arguments': {'income_id': liquid.pk}},
    ))

    assert got_liquid['error']['code'] == 'FORBIDDEN'


def test_expected_only_credential_cannot_create_liquid_income(api_client, accounting_connector):
    """Fails if expected-only migration permits creating a liquid income."""
    token, _ = _expected_only_credential(accounting_connector)
    created_liquid = _payload(_endpoint(api_client, token, 'tools/call', {
        'name': 'create_income',
        'arguments': {
            'concept': 'Líquido no autorizado', 'kind': 'liquid', 'origin': 'development',
            'period_date': '2026-11-01', 'total_amount': '400',
        },
    }))

    assert created_liquid['error']['code'] == 'FORBIDDEN'
    assert IncomeRecord.objects.filter(concept='Líquido no autorizado').count() == 0
