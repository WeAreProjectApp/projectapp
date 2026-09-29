"""Contracts that make model/tool drift fail loudly during delivery."""
import re
from itertools import product
from unittest.mock import Mock, call

import pytest
from django.apps import apps
from django.urls import NoReverseMatch, resolve, reverse

from content.mcp.contracts import MCP_MODEL_CONTRACTS
from content.views.mcp_blog import TOOLS_BY_SLUG

CONNECTOR_SLUGS = tuple(MCP_MODEL_CONTRACTS)
CANONICAL_CONNECTOR_SLUGS = (
    'operations', 'commercial', 'proposals', 'projects', 'documents', 'communications',
    'content', 'tasks', 'accounting-ledger', 'accounting-billing',
    'accounting-cards',
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
        'render_document_pdf',
        'describe_capabilities',
        'confirm_action',
        'begin_upload',
    } <= tool_names
    assert len(TOOLS_BY_SLUG['documents']) == 65


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
