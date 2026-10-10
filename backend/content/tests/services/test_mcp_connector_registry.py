"""Registry identity, accounting boundaries and versioned public contracts."""
import ast
import json
import re
from copy import deepcopy
from dataclasses import replace

import pytest

from content.mcp.accounting_tools import ACCOUNTING_TOOLS
from content.mcp.common_tools import build_common_tools
from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG, accounting_area
from content.mcp.contract_report import CONTRACTS_PATH, backlog_literals, compare, fingerprint, local_snapshot, public_contract
from content.mcp.expected_income_tools import EXPECTED_INCOME_TOOLS
from content.mcp.operation_catalogs import BILLING_PARITY_TOOLS, CARD_PARITY_TOOLS, LEDGER_PARITY_TOOLS
from content.mcp.platform_billing_tools import PLATFORM_BILLING_TOOLS
from content.mcp.registry import normalize_tools, public_tool, with_sensitive_confirmation
from content.mcp.schema_backlog import DEFERRED_SCHEMA_BACKLOG, GENERIC_ADAPTER_BACKLOG, UNDESCRIBED_ARGUMENT_BACKLOG


AREAS = ('ledger', 'billing', 'cards')
PARITY_TOOLS = {'ledger': LEDGER_PARITY_TOOLS, 'billing': BILLING_PARITY_TOOLS, 'cards': CARD_PARITY_TOOLS}
EXTRA_TOOLS = {'ledger': EXPECTED_INCOME_TOOLS, 'billing': PLATFORM_BILLING_TOOLS, 'cards': []}
SEMVER = r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'


@pytest.fixture(scope='module')
def contract_lock():
    return json.loads(CONTRACTS_PATH.read_text())


def _contract_tools(tools):
    return [
        {**public_tool(tool), 'risk': tool.get('risk'), 'requires_confirmation': bool(tool.get('requires_confirmation'))}
        for tool in sorted(tools, key=lambda tool: tool['name'])
    ]


def _accounting_contract(area):
    slug = f'accounting-{area}'
    area_tools = [tool for tool in ACCOUNTING_TOOLS if tool['area'] == area]
    domain = with_sensitive_confirmation([*area_tools, *PARITY_TOOLS[area], *EXTRA_TOOLS[area]])
    common = build_common_tools(CONNECTORS[slug], lambda: TOOLS_BY_SLUG[slug])
    return _contract_tools(normalize_tools([*domain, *common], slug))


def _backlog_values(source):
    assignments = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)]
    return {node.targets[0].id: ast.literal_eval(node.value.args[0] if isinstance(node.value, ast.Call) else node.value) for node in assignments}


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_connector_has_explicit_semver(slug):
    assert re.fullmatch(SEMVER, CONNECTORS[slug].version)


def test_accounting_areas_partition_source_tools():
    partitioned = [tool['name'] for area in AREAS for tool in accounting_area(area)]
    source_names = [tool['name'] for tool in ACCOUNTING_TOOLS]

    assert sorted(partitioned) == sorted(source_names)
    assert len(partitioned) == len(set(partitioned))
    assert all(tool['area'] == area for area in AREAS for tool in accounting_area(area))


@pytest.mark.parametrize('area', AREAS)
def test_accounting_connector_has_exact_area_contract(area):
    assert public_contract(f'accounting-{area}')['tools'] == _accounting_contract(area)


@pytest.mark.parametrize('slug', sorted(slug for slug, spec in CONNECTORS.items() if spec.compatibility))
def test_compatibility_confirmation_is_declared_by_source(slug):
    spec = CONNECTORS[slug]
    sources = [tool for source in spec.sources for tool in source]
    declared = sources + build_common_tools(spec, lambda: TOOLS_BY_SLUG[slug])

    assert spec.confirm_sensitive is False
    assert {tool['name']: bool(tool.get('requires_confirmation')) for tool in TOOLS_BY_SLUG[slug]} == {tool['name']: bool(tool.get('requires_confirmation')) for tool in declared}


def test_contract_lock_contains_every_connector(contract_lock):
    assert set(contract_lock) == set(CONNECTORS)


@pytest.mark.parametrize('slug', sorted(CONNECTORS))
def test_connector_fingerprint_matches_versioned_lock(slug, contract_lock):
    assert contract_lock[slug] == {'version': CONNECTORS[slug].version, 'sha256': fingerprint(slug)}


def test_fingerprint_excludes_connector_version(monkeypatch):
    before = fingerprint('blog')
    monkeypatch.setitem(CONNECTORS, 'blog', replace(CONNECTORS['blog'], version='9.9.9'))

    assert fingerprint('blog') == before


def test_fingerprint_ignores_registry_order(monkeypatch):
    before = fingerprint('blog')
    monkeypatch.setitem(TOOLS_BY_SLUG, 'blog', list(reversed(TOOLS_BY_SLUG['blog'])))

    assert fingerprint('blog') == before


@pytest.mark.parametrize('field,value', [('risk', 'sensitive'), ('requires_confirmation', True)])
def test_fingerprint_tracks_execution_contract(monkeypatch, field, value):
    before = fingerprint('tasks')
    tools = deepcopy(TOOLS_BY_SLUG['tasks'])
    tools[0][field] = value
    monkeypatch.setitem(TOOLS_BY_SLUG, 'tasks', tools)

    assert fingerprint('tasks') != before


def test_fingerprint_tracks_connector_instructions(monkeypatch):
    before = fingerprint('blog')
    monkeypatch.setitem(CONNECTORS, 'blog', replace(CONNECTORS['blog'], notes=('Nota contractual nueva.',)))

    assert fingerprint('blog') != before


def test_local_snapshot_needs_no_database():
    snapshot = local_snapshot('documents')
    result = compare(snapshot)

    assert result['ok'] is True
    assert result['versions']['registry'] == CONNECTORS['documents'].version
    assert result['tools_list_count'] == len(TOOLS_BY_SLUG['documents'])


def test_backlog_literals_preserve_current_exceptions():
    backlogs = _backlog_values(backlog_literals())

    assert backlogs['GENERIC_ADAPTER_BACKLOG'] == GENERIC_ADAPTER_BACKLOG
    assert backlogs['UNDESCRIBED_ARGUMENT_BACKLOG'] == UNDESCRIBED_ARGUMENT_BACKLOG
    assert backlogs['DEFERRED_SCHEMA_BACKLOG'] == DEFERRED_SCHEMA_BACKLOG
