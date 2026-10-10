"""Contracts that make model/tool drift fail loudly during delivery."""
import re
from datetime import date, datetime, timezone
from itertools import product
from unittest.mock import Mock, call

import pytest
from accounts.models import HostingSubscription, Payment, Project
from django.apps import apps
from django.urls import NoReverseMatch, resolve, reverse

from content.mcp.contracts import MCP_MODEL_CONTRACTS
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import call_tool_inprocess
from content.mcp.connectors import CONNECTORS
from content.views.mcp_blog import TOOLS_BY_SLUG

CONNECTOR_SLUGS = tuple(MCP_MODEL_CONTRACTS)
CANONICAL_CONNECTOR_SLUGS = tuple(
    slug for slug, spec in CONNECTORS.items() if not spec.compatibility
)
TOOL_NAME = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$')
pytestmark = pytest.mark.django_db


def _current_fields(model_label):
    return {
        field.name
        for field in apps.get_model(model_label)._meta.get_fields()
        if not (field.auto_created and not field.concrete)
    }


def _field_contract_problems(slug):
    problems = []
    for contract in MCP_MODEL_CONTRACTS[slug]:
        overlaps = (
            (contract.read_only & contract.read_write)
            | (contract.read_only & frozenset(contract.excluded))
            | (contract.read_write & frozenset(contract.excluded))
        )
        if overlaps:
            problems.append(
                f'{contract.model_label}: clasificación duplicada {sorted(overlaps)}'
            )
        current = _current_fields(contract.model_label)
        missing = current - contract.classified_fields
        stale = contract.classified_fields - current
        if missing:
            problems.append(
                f'{contract.model_label}: campos nuevos sin revisar {sorted(missing)}'
            )
        if stale:
            problems.append(
                f'{contract.model_label}: campos obsoletos {sorted(stale)}'
            )
        empty_reasons = sorted(
            field for field, reason in contract.excluded.items() if not reason.strip()
        )
        if empty_reasons:
            problems.append(
                f'{contract.model_label}: exclusiones sin motivo {empty_reasons}'
            )
    return problems


def _tool_contract_problems(slug):
    tools = TOOLS_BY_SLUG[slug]
    names = [tool['name'] for tool in tools]
    problems = []
    if len(names) != len(set(names)):
        problems.append('hay nombres de herramienta duplicados')
    invalid_names = sorted(name for name in names if not TOOL_NAME.fullmatch(name))
    if invalid_names:
        problems.append(f'nombres fuera de snake_case: {invalid_names}')
    short_descriptions = sorted(
        tool['name'] for tool in tools if len(tool['description'].strip()) < 40
    )
    if short_descriptions:
        problems.append(f'descripciones imprecisas: {short_descriptions}')
    invalid_schemas = sorted(
        tool['name']
        for tool in tools
        if tool.get('input_schema', {}).get('type') != 'object'
        or not isinstance(tool.get('input_schema', {}).get('properties'), dict)
    )
    if invalid_schemas:
        problems.append(f'input schemas inválidos: {invalid_schemas}')
    invalid_risks = sorted(
        tool['name'] for tool in tools
        if tool.get('risk') not in {'read', 'write', 'sensitive'}
    )
    if invalid_risks:
        problems.append(f'niveles de riesgo inválidos: {invalid_risks}')
    invalid_outputs = sorted(
        tool['name'] for tool in tools
        if tool.get('output_schema', {}).get('type') != 'object'
    )
    if invalid_outputs:
        problems.append(f'output schemas inválidos: {invalid_outputs}')
    return problems


def _resolve_panel_adapter_url(operation):
    candidate_uuid = '12345678-1234-1234-1234-123456789abc'
    for args in product((1, candidate_uuid), repeat=len(operation['path_params'])):
        try:
            return reverse(operation['route_name'], args=args)
        except NoReverseMatch:
            continue
    return None


def test_registry_and_field_contracts_cover_the_same_connectors():
    assert set(TOOLS_BY_SLUG) == set(MCP_MODEL_CONTRACTS)


def test_project_has_no_module_specific_catalog_opt_out():
    project_contract = next(
        contract
        for contract in MCP_MODEL_CONTRACTS['documents']
        if contract.model_label == 'accounts.Project'
    )

    assert 'document_manager_enabled' not in _current_fields('accounts.Project')
    assert 'document_manager_enabled' not in project_contract.classified_fields


def test_document_threads_are_exposed_by_the_documents_connector():
    contracts = {
        contract.model_label: contract
        for contract in MCP_MODEL_CONTRACTS['documents']
    }

    thread = contracts['content.DocumentThread']
    assert thread.read_write == frozenset({'title'})
    assert thread.read_only == frozenset({
        'id', 'created_by', 'updated_by', 'created_at', 'updated_at',
    })
    assert thread.excluded == {}

    item = contracts['content.DocumentThreadItem']
    assert item.read_write == frozenset({'thread', 'document', 'occurred_on'})
    assert item.read_only == frozenset({
        'id', 'linked_by', 'updated_by', 'linked_at', 'updated_at',
    })
    # La posición es derivada: el conector envía fechas y el servidor ordena.
    assert set(item.excluded) == {'position'}
    assert item.excluded['position'].strip()


def test_documents_connector_keeps_native_tools_and_adds_panel_parity():
    tool_names = {tool['name'] for tool in TOOLS_BY_SLUG['documents']}

    assert {
        'get_document_thread',
        'list_document_threads',
        'create_document_thread',
        'update_document_thread',
        'dissolve_document_thread',
    } <= tool_names
    assert {
        'browse_documents',
        'update_document',
        'archive_document',
        'move_documents',
        'preview_move',
        'render_document_pdf',
        'describe_capabilities',
        'confirm_action',
        'begin_upload',
        'list_contract_mirrors',
        'preview_folder_migration',
        'apply_folder_migration',
        'get_folder_migration',
        'preview_folder_migration_undo',
        'undo_folder_migration',
        'adopt_folder_as_project_root',
    } <= tool_names
    assert len(TOOLS_BY_SLUG['documents']) == 73
    mirror_listing = next(
        tool for tool in TOOLS_BY_SLUG['documents']
        if tool['name'] == 'list_contract_mirrors'
    )
    assert mirror_listing['annotations']['readOnlyHint'] is True


def test_projects_hosting_contract_uses_lifecycle_actions(superuser, make_client_profile):
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Projects'},
    )
    credential = McpCredential.objects.create(
        connector=connector, label='Hosting field contract', actor=superuser,
    )
    project = Project.objects.create(
        name='Archived hosting payment', client=make_client_profile().user,
    )
    subscription = HostingSubscription.objects.create(
        project=project, plan='quarterly', status='cancelled',
        base_monthly_amount=100, effective_monthly_amount=100, billing_amount=300,
        start_date=date(2026, 1, 1), next_billing_date=None,
    )
    archived_at = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    payment = Payment.objects.create(
        subscription=subscription, amount=300, status=Payment.STATUS_VOIDED,
        billing_period_start=date(2026, 1, 1), billing_period_end=date(2026, 3, 31),
        due_date=date(2026, 1, 1), is_archived=True, archived_at=archived_at,
    )
    payment.full_clean()

    hosting = call_tool_inprocess(
        'projects', 'get_project_hosting', {'project_id': project.pk},
        credential=credential,
    )
    rejected = call_tool_inprocess(
        'projects', 'change_hosting_subscription', {
            'subscription_id': subscription.pk, 'action': 'resume',
            'reason': 'Revisar campos del ciclo', 'expected_impact_hash': 'unused',
            'status': 'active', 'next_billing_date': '2026-04-01',
        }, credential=credential,
    )

    assert hosting['subscription']['status'] == 'cancelled'
    assert hosting['subscription']['next_billing_date'] is None
    archived_payment = next(
        row for row in hosting['subscription']['payments'] if row['id'] == payment.pk
    )
    assert archived_payment['status'] == 'voided'
    assert archived_payment['is_archived'] is True
    assert archived_payment['archived_at'] == archived_at
    assert rejected['error']['code'] == 'unknown_field'
    assert {row['field'] for row in rejected['error']['details']['errors']} == {
        'status', 'next_billing_date',
    }
    subscription.refresh_from_db()
    assert subscription.status == 'cancelled'
    assert subscription.next_billing_date is None

    contracts = {
        slug: {contract.model_label: contract for contract in MCP_MODEL_CONTRACTS[slug]}
        for slug in ('projects', 'accounting-billing')
    }
    project_subscription = contracts['projects']['accounts.HostingSubscription']
    accounting_subscription = contracts['accounting-billing']['accounts.HostingSubscription']
    lifecycle_fields = frozenset({'status', 'next_billing_date'})
    assert project_subscription.read_write == lifecycle_fields
    assert accounting_subscription.read_write == frozenset()
    assert project_subscription.read_only == accounting_subscription.read_only - lifecycle_fields
    assert project_subscription.excluded == accounting_subscription.excluded
    assert {'status', 'is_archived', 'archived_at'} <= contracts['projects']['accounts.Payment'].read_only
    assert contracts['projects']['accounts.Payment'] == contracts['accounting-billing']['accounts.Payment']

    tools = {tool['name']: tool for tool in TOOLS_BY_SLUG['projects']}
    assert len(tools) == len(TOOLS_BY_SLUG['projects']) == 171
    assert tools['preview_hosting_subscription_change']['annotations']['readOnlyHint'] is True
    assert tools['change_hosting_subscription']['requires_confirmation'] is True
    assert 'change_hosting_subscription' not in {
        tool['name'] for tool in TOOLS_BY_SLUG['accounting-billing']
    }


def test_communications_contract_exposes_archive_state():
    contracts = {
        contract.model_label: contract
        for contract in MCP_MODEL_CONTRACTS['communications']
    }

    thread = contracts['content.CommunicationThread']
    assert {'is_archived', 'archived_at'} <= thread.read_only
    assert 'is_archived' not in thread.excluded
    assert 'archived_at' not in thread.excluded


def test_accounting_ledger_exposes_receivables_forecast():
    tool_names = {tool['name'] for tool in TOOLS_BY_SLUG['accounting-ledger']}

    assert 'get_receivables' in tool_names


@pytest.mark.parametrize('slug', CONNECTOR_SLUGS)
def test_model_fields_are_classified_for_connector(slug):
    assert _field_contract_problems(slug) == []


@pytest.mark.parametrize('slug', CONNECTOR_SLUGS)
def test_tool_metadata_is_actionable_for_connector(slug):
    assert _tool_contract_problems(slug) == []


@pytest.mark.parametrize('slug', CANONICAL_CONNECTOR_SLUGS)
def test_canonical_sensitive_tools_require_confirmation(slug):
    unguarded = sorted(
        tool['name'] for tool in TOOLS_BY_SLUG[slug]
        if tool['risk'] == 'sensitive'
        and tool['name'] != 'confirm_action'
        and not tool.get('requires_confirmation')
    )

    assert unguarded == []


@pytest.mark.parametrize('slug', CANONICAL_CONNECTOR_SLUGS)
def test_panel_adapters_resolve_to_a_view_supporting_the_declared_method(slug):
    problems = []
    for tool in TOOLS_BY_SLUG[slug]:
        operation = tool.get('_panel_operation')
        if not operation:
            continue
        url = _resolve_panel_adapter_url(operation)
        if url is None:
            problems.append(f"{tool['name']}: ruta {operation['route_name']} no resuelve")
            continue
        match = resolve(url)
        allowed = {
            method.upper()
            for method in getattr(getattr(match.func, 'cls', None), 'http_method_names', [])
            if method not in {'head', 'options'}
        }
        if allowed and operation['method'] not in allowed:
            problems.append(
                f"{tool['name']}: {operation['method']} no está en {sorted(allowed)}"
            )

    assert problems == []


def test_panel_adapter_url_resolver_tries_next_candidate_after_no_reverse_match(monkeypatch):
    """Falla si una ruta UUID válida deja de probarse tras un NoReverseMatch inicial."""
    candidate_uuid = '12345678-1234-1234-1234-123456789abc'
    expected_url = '/panel/blog/12345678-1234-1234-1234-123456789abc/'
    reverse_mock = Mock(
        side_effect=(NoReverseMatch('integer is not accepted'), expected_url),
    )
    monkeypatch.setattr(
        'content.tests.views.test_mcp_contracts.reverse',
        reverse_mock,
    )

    url = _resolve_panel_adapter_url({
        'route_name': 'panel-blog-detail',
        'path_params': ('blog_id',),
    })

    assert url == expected_url
    reverse_mock.assert_called_with('panel-blog-detail', args=(candidate_uuid,))
    assert reverse_mock.call_args_list == [
        call('panel-blog-detail', args=(1,)),
        call('panel-blog-detail', args=(candidate_uuid,)),
    ]


def test_panel_adapter_url_resolver_propagates_unexpected_reverse_error(monkeypatch):
    """Falla si un error de configuración de reverse queda oculto como ruta ausente."""
    reverse_mock = Mock(side_effect=RuntimeError('invalid route configuration'))
    monkeypatch.setattr(
        'content.tests.views.test_mcp_contracts.reverse',
        reverse_mock,
    )

    with pytest.raises(RuntimeError, match='invalid route configuration'):
        _resolve_panel_adapter_url({
            'route_name': 'panel-blog-detail',
            'path_params': ('blog_id',),
        })

    reverse_mock.assert_called_once_with('panel-blog-detail', args=(1,))
