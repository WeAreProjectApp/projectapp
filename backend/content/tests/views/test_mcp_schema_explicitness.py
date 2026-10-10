"""Ratchets for the breaking documents 4 / projects 3 input contract sweep."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from content.mcp.schemas.projects_bridge import PANEL_ONLY_FIELDS
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import assert_no_writes, call_tool_inprocess
from content.tests.mcp_schema_rules import (
    ALIAS_BACKLOG,
    CONNECTORS,
    DRIFT_BACKLOG,
    EXCLUDED_TOOLS,
    INITIAL_ALIAS_COUNT,
    INITIAL_DRIFT_COUNT,
    INITIAL_OPEN_SCHEMA_COUNT,
    OPEN_SCHEMA_BACKLOG,
    PARITY_PAIRS,
    UNPAIRED_PREVIEWS,
    parity_evidence_problems,
    schema_problems,
)
from content.tests.mcp_view_inventory import build_inventory, schema_drift
from content.views.mcp_blog import TOOLS_BY_SLUG


@pytest.fixture(scope='module')
def inventory():
    return build_inventory()


def _ratchet(actual, backlog, ceiling):
    assert len(backlog) <= ceiling, 'The initial ceiling cannot grow.'
    assert len(actual) <= ceiling, f'Initial ceiling exceeded: {len(actual)} > {ceiling}'
    assert actual == set(backlog), (
        f'New failures: {sorted(actual - set(backlog))}; '
        f'remove resolved entries: {sorted(set(backlog) - actual)}'
    )


def test_published_tools_outside_the_backlog_satisfy_the_policy(inventory):
    candidates = [row for row in inventory
                  if (row['connector'], row['name']) not in OPEN_SCHEMA_BACKLOG
                  and (row['connector'], row['name']) not in EXCLUDED_TOOLS]

    offenders = {(row['connector'], row['name']): row['schema_problems']
                 for row in candidates if row['schema_problems']}

    assert candidates, 'The explicitness guard must exercise published tools.'
    assert not offenders, offenders


def test_open_schema_backlog_matches_the_current_failures(inventory):
    current = {(row['connector'], row['name']) for row in inventory
               if row['schema_problems'] and (row['connector'], row['name']) not in EXCLUDED_TOOLS}

    _ratchet(current, OPEN_SCHEMA_BACKLOG, INITIAL_OPEN_SCHEMA_COUNT)


def test_exclusions_match_the_modules_owned_by_pr_503(inventory):
    owned = {(row['connector'], row['name']) for row in inventory
             if row['schema_module'] in {'content.mcp.entity_history_tools', 'content.mcp.common_tools'}}

    assert set(EXCLUDED_TOOLS) == owned
    assert set(EXCLUDED_TOOLS.values()) == {'owned by PR #503'}
    assert not owned & OPEN_SCHEMA_BACKLOG


def test_alias_backlog_matches_the_accepted_envelopes(inventory):
    current = {(row['connector'], row['name']) for row in inventory if row['aliases']}

    _ratchet(current, ALIAS_BACKLOG, INITIAL_ALIAS_COUNT)


def test_drift_backlog_matches_resolved_explicit_views(inventory):
    current = schema_drift(inventory)

    _ratchet(current, DRIFT_BACKLOG, INITIAL_DRIFT_COUNT)


def test_panel_only_read_exemptions_keep_their_reasons(inventory):
    rows = {row['name']: row for row in inventory
            if row['connector'] == 'projects' and row['name'] in PANEL_ONLY_FIELDS}

    assert set(rows) == set(PANEL_ONLY_FIELDS)
    assert all(isinstance(reason, str) and reason.strip()
               for fields in PANEL_ONLY_FIELDS.values() for reason in fields.values())
    assert {name: row['panel_only_fields'] for name, row in rows.items()} == PANEL_ONLY_FIELDS
    client_change = rows['change_project_client']
    assert set(client_change['undeclared_data']) == set(PANEL_ONLY_FIELDS['change_project_client'])
    missing_reason = deepcopy(client_change)
    missing_reason['panel_only_fields']['hosting_ids'] = ''
    assert schema_drift([missing_reason]) == {('projects', 'change_project_client', 'data', 'hosting_ids')}


def _sample(schema):
    if 'const' in schema:
        return schema['const']
    if schema.get('enum'):
        return schema['enum'][0]
    for combinator in ('anyOf', 'oneOf', 'allOf'):
        if schema.get(combinator):
            return _sample(schema[combinator][0])
    kind = schema.get('type')
    if isinstance(kind, list):
        kind = next((value for value in kind if value != 'null'), 'null')
    if kind == 'object':
        return {name: _sample(schema['properties'][name]) for name in schema.get('required', [])}
    if kind == 'array':
        return [_sample(schema['items']) for _ in range(schema.get('minItems', 0))]
    if kind in ('integer', 'number'):
        return max(schema.get('minimum', 1), 1)
    if kind == 'boolean':
        return False
    if kind == 'null':
        return None
    if schema.get('format') == 'uuid':
        return '00000000-0000-4000-8000-000000000001'
    return 'schema probe'


@pytest.mark.django_db
def test_every_closed_tool_rejects_unknown_arguments_before_execution(monkeypatch, superuser):
    credentials = {}
    for slug in CONNECTORS:
        connector, _ = McpConnector.objects.get_or_create(slug=slug, defaults={'name': slug})
        credentials[slug] = McpCredential.objects.create(connector=connector, actor=superuser, label='Schema guard')
    offenders, probed = [], []
    unknown = '__p2_unknown_argument__'
    callbacks = ('handler', 'impact_builder', 'prepare_arguments', 'confirmation_predicate', 'etag_resolver')

    # Deliberately one test over the complete closed-root population, including
    # partially typed tools: descriptions must not make this probe vacuous.
    for slug in CONNECTORS:
        for tool in TOOLS_BY_SLUG[slug]:
            if tool['input_schema'].get('additionalProperties') is not False:
                continue
            key = (slug, tool['name'])
            probed.append(key)
            boundary = Mock(side_effect=AssertionError(f'{key}: execution reached before argument rejection'))
            with monkeypatch.context() as patch:
                for callback in callbacks:
                    if callable(tool.get(callback)):
                        patch.setitem(tool, callback, boundary)
                arguments = {unknown: True}
                try:
                    result = assert_no_writes(call_tool_inprocess, slug, tool['name'], arguments,
                                              credential=credentials[slug])
                    errors = result.get('error', {}).get('details', {}).get('errors', [])
                    if any(error['code'] == 'required' for error in errors):
                        accepted = tool.get('accepted_arguments_schema') or tool['input_schema']
                        # Error normalization treats a field named "message" as
                        # non_field_errors; use the contract to recover names.
                        required = set(accepted.get('required', [])) - arguments.keys()
                        arguments.update({name: _sample(accepted['properties'][name]) for name in required})
                        result = assert_no_writes(call_tool_inprocess, slug, tool['name'], arguments,
                                                  credential=credentials[slug])
                        errors = result.get('error', {}).get('details', {}).get('errors', [])
                    if result.get('ok') is not False or not errors or any(
                        error.get('code') != 'unknown_field' or error.get('field') != unknown for error in errors
                    ):
                        offenders.append((key, result))
                except AssertionError as exc:
                    offenders.append((key, str(exc)))
                if boundary.called:
                    offenders.append((key, 'An execution callback ran.'))

    assert {slug for slug, _ in probed} == set(CONNECTORS)
    assert not offenders, offenders


def test_parity_pair_evidence_still_names_the_exercised_operations():
    problems = parity_evidence_problems()

    assert not problems, problems
    assert all(apply_tools for _file, _scenario, apply_tools in PARITY_PAIRS.values())


def test_unpaired_preview_whitelist_is_exact(inventory):
    previews = {(row['connector'], row['name']) for row in inventory if row['name'].startswith('preview_')}
    missing = previews - set(PARITY_PAIRS)

    assert missing == set(UNPAIRED_PREVIEWS), (
        f'Unexplained previews: {sorted(missing - set(UNPAIRED_PREVIEWS))}; '
        f'stale exceptions: {sorted(set(UNPAIRED_PREVIEWS) - missing)}'
    )
    assert set(PARITY_PAIRS) <= previews
    assert all(reason.strip() for reason in UNPAIRED_PREVIEWS.values())


@pytest.fixture
def policy_tool():
    return {'name': 'policy_witness', 'input_schema': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'settings': {'type': 'object', 'description': 'Opciones declaradas.', 'additionalProperties': False,
                         'properties': {'flag': {'type': 'boolean'}},
                         'allOf': [{'not': {'required': ['flag']}}]},
            'mapping': {'type': 'object', 'description': 'Mapa tipado.',
                        'additionalProperties': {'type': 'array', 'items': {'anyOf': [{'type': 'integer'}, {'type': 'null'}]}}},
            'payload': {'type': 'object', 'description': 'Contrato externo documentado.',
                        'additionalProperties': True, 'x-mcp-open-reason': 'Versioned external authoring format.'},
            'choice': {'enum': ['manual'], 'description': 'Selección.'},
            'version': {'const': 1, 'description': 'Versión.'},
        },
    }}


@pytest.mark.parametrize(('path', 'value', 'pointer'), [
    (('type',), 'array', '/type'),
    (('properties',), [], '/properties'),
    (('additionalProperties',), True, '/additionalProperties'),
    (('oneOf',), [{'required': ['choice']}], '/oneOf'),
    (('properties', 'choice'), {'description': 'Sin tipo.'}, '/properties/choice'),
    (('properties', 'mapping', 'additionalProperties', 'items'), {}, '/properties/mapping/additionalProperties/items'),
    (('properties', 'settings', 'additionalProperties'), True, '/properties/settings/additionalProperties'),
    (('properties', 'payload', 'x-mcp-open-reason'), ' ', '/properties/payload/x-mcp-open-reason'),
    (('properties', 'settings', 'allOf'), [{'not': {'required': ['ghost']}}], '/properties/settings/allOf/0/not/required/0'),
    (('properties', 'choice', 'description'), '', '/properties/choice'),
    (('properties', 'data'), {'type': 'string', 'description': 'Envelope legado.'}, '/properties/data'),
    (('properties', 'mapping', 'additionalProperties'), {}, '/properties/mapping/additionalProperties'),
    (('properties', 'payload', 'properties'), {'untyped': {}}, '/properties/payload/additionalProperties'),
])
def test_policy_reports_a_mutated_contract_at_its_pointer(policy_tool, path, value, pointer):
    before = deepcopy(policy_tool)
    target = policy_tool['input_schema']
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = value

    problems = schema_problems(policy_tool)

    assert schema_problems(before) == []
    assert any(problem.startswith(f'policy_witness:{pointer}:') for problem in problems), problems
