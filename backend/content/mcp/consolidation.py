"""Assemble one public catalog per module and isolated compatibility catalogs."""
from copy import deepcopy
import json
from pathlib import Path

from content.mcp import registry
from content.mcp.canonical_schemas import complete_canonical_schema
from content.mcp.income_tools import build_income_tools
from content.mcp.module_catalog import (
    ACCOUNTING_SUPERSEDED, CANONICAL_FOR, FINANCIAL_PROJECT_TOOLS, MODULE_CONNECTORS,
    canonical_name, catalog_problems,
    COMMERCIAL_MEMBERS, SHARED_VIDEO_REPLACEMENTS, INFRASTRUCTURE_TOOLS, tool_owner,
)
from content.mcp.section_tools import COMMERCIAL_SECTION_TOOLS

REPLACED_INCOME_NAMES = frozenset({
    'list_income', 'get_income', 'get_income_detail', 'create_income', 'update_income',
    'list_expected_incomes', 'get_expected_income', 'create_expected_income',
    'update_expected_income', 'duplicate_expected_income',
})


def operation_id(tool):
    if tool.get('operation_id'):
        return tool['operation_id']
    operation = tool.get('_panel_operation')
    if operation:
        route = operation['route_name']
        discriminator = ''
        if route.startswith('entity-history-'):
            discriminator = ':' + tool['name'].split('_')[1]
        actions = tool.get('input_schema', {}).get('properties', {}).get('action', {}).get('enum', [])
        if actions:
            discriminator += ':' + ','.join(sorted(actions))
        return f"panel:{operation['method']}:{route}{discriminator}"
    return f"handler:{tool['handler'].__module__}:{tool['name']}"


def _unique(tools):
    """Sources may share the same tool; differing implementations fail loudly."""
    found = {}
    for tool in tools:
        name = tool['name']
        if name in found and operation_id(found[name]) != operation_id(tool):
            raise RuntimeError(f'Conflicting MCP implementations: {name}')
        found.setdefault(name, deepcopy(tool))
    return list(found.values())


def build_catalogs(sources, replace, common, *, pre_split=None):
    from content.mcp.hosting_subscription_tools import HOSTING_SUBSCRIPTION_TOOLS
    from content.mcp import income_tools

    connectors, raw, legacy = {}, {}, {}
    for slug, source in sources.items():
        canonical = CANONICAL_FOR[slug]
        connectors[slug] = replace(
            source, compatibility=slug != canonical, canonical_area=canonical,
            confirm_sensitive=True,
            module_id=MODULE_CONNECTORS[canonical][0],
            version=f'{int(source.version.split(".")[0]) + 1}.0.0',
        )
        raw[slug] = _unique(tool for group in source.sources for tool in group)

    canonical_raw = {}
    for slug, (_, members) in MODULE_CONNECTORS.items():
        tools = _unique(tool for member in members for tool in raw[member])
        if slug == 'commercial':
            tools = [tool for tool in tools if tool['name'] != 'launch_proposal_to_platform']
        if slug in {'commercial', 'offerings', 'programs'}:
            tools = [tool for tool in tools if tool['name'] not in SHARED_VIDEO_REPLACEMENTS
                     and tool_owner(tool['name'], slug) == slug]
            if slug == 'commercial':
                tools.extend(deepcopy(COMMERCIAL_SECTION_TOOLS))
        if slug == 'projects':
            tools = [tool for tool in tools if tool['name'] not in FINANCIAL_PROJECT_TOOLS]
        if slug == 'accounting':
            tools = [tool for tool in tools if tool['name'] not in REPLACED_INCOME_NAMES | ACCOUNTING_SUPERSEDED]
            tools = _unique([*tools, *HOSTING_SUBSCRIPTION_TOOLS, *build_income_tools()])
        for tool in tools:
            tool['operation_id'] = operation_id(tool)
            tool['name'] = canonical_name(tool['name'], slug)
            complete_canonical_schema(tool, slug)
        canonical_raw[slug] = tools
        if slug == 'accounting':
            connectors[slug] = replace(connectors[slug], uploads=True)

    def finish(spec, tools, target):
        tools = deepcopy(tools)
        common_spec = replace(spec, uploads=sources[spec.slug].uploads) if target is legacy else spec
        if target is legacy or spec.compatibility:
            # Generic legacy income writes must not bypass the richer expected
            # service just because the caller still uses the old vocabulary.
            for tool in tools:
                if tool['name'] in {'create_income', 'update_income'}:
                    action = tool['name'].split('_')[0]

                    def prepare(arguments, action=action):
                        arguments = dict(arguments)
                        if action == 'update':
                            arguments['income_id'] = arguments.pop('record_id', None)
                        else:
                            arguments.pop('record_id', None)
                        return income_tools._prepare(arguments, action)

                    tool.update(
                        risk='sensitive', requires_confirmation=True,
                        prepare_arguments=prepare, impact_builder=income_tools._impact,
                        etag_resolver=income_tools._etags,
                        handler=lambda arguments: income_tools._apply(arguments)['income'],
                    )
                    if action == 'create':
                        tool['input_schema']['if'] = {'properties': {'kind': {'const': 'expected'}}}
                        tool['input_schema']['then'] = {'required': ['vat_rate']}
        normalized = registry.normalize_tools(registry.with_sensitive_confirmation(tools), spec.slug)
        target[spec.slug] = normalized
        target[spec.slug] = registry.normalize_tools([
            *normalized, *common(common_spec, lambda slug=spec.slug: target[slug]),
        ], spec.slug)

    public = {}
    if pre_split is not None:
        frozen_names = set(json.loads(Path(__file__).with_name('pre_split_commercial_names.json').read_text()))
        tools = _unique(tool for member in COMMERCIAL_MEMBERS for tool in raw[member])
        tools = [tool for tool in tools if tool['name'] in frozen_names]
        missing = frozen_names - INFRASTRUCTURE_TOOLS - {tool['name'] for tool in tools}
        if missing:
            raise RuntimeError(f'Missing pre-split commercial tools: {sorted(missing)}')
        for tool in tools:
            if tool['name'] == 'launch_proposal_to_platform':
                tool['_hidden'] = True
            tool['operation_id'] = operation_id(tool)
            tool['name'] = canonical_name(tool['name'], 'commercial')
            complete_canonical_schema(tool, 'commercial')
        finish(connectors['commercial'], tools, pre_split)
    for slug, spec in connectors.items():
        finish(spec, canonical_raw.get(slug, raw[slug]), public)
        finish(spec, raw[slug], legacy)
    problems = catalog_problems(connectors, public)
    if problems:
        raise RuntimeError('; '.join(problems))
    return connectors, public, legacy
