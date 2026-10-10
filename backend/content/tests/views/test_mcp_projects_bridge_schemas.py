"""Projects bridge contracts against Panel reads and real domain mutations."""

from copy import deepcopy
from importlib import import_module

import pytest
from accounts.models import Project
from accounts.models_project_ideas import ProjectIdea
from accounts.tests.project_collaboration_helpers import context

from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.mcp.schemas.projects_bridge import (
    PANEL_ONLY_FIELDS,
    PROJECTS_BRIDGE_SCHEMAS,
)
from content.models import (
    DocumentFolder,
    DocumentState,
    DocumentStateGroup,
    McpConnector,
    ProjectRetentionContext,
)
from content.serializers.project_retention import CONTAINER_KINDS
from content.tests.mcp_parity import assert_no_writes
from content.tests.mcp_schema_rules import EXCLUDED_TOOLS, schema_problems
from content.tests.mcp_view_inventory import inventory_tool
from content.views.mcp_blog import TOOLS_BY_SLUG

# These views pass a whole map to a service. Each service validates with the
# named serializer before reading the map; no free-form payload is involved.
_SERVICE_SERIALIZERS = {
    'create_project_idea': 'accounts.serializers_project_ideas.IdeaCreateSerializer',
    'update_project_idea': 'accounts.serializers_project_ideas.IdeaEditSerializer',
    'archive_project_idea': 'accounts.serializers_project_ideas.IdeaArchiveSerializer',
    'restore_project_idea': 'accounts.serializers_project_ideas.IdeaArchiveSerializer',
    'create_project_idea_collection': 'accounts.serializers_project_ideas.IdeaCollectionSerializer',
    'set_project_client_access_policy': 'accounts.serializers_project_client_access.ClientAccessPolicySerializer',
}
_VIEW_PAYLOAD_FIELDS = {'create_project_state': {'confirm_similar'}}
_CREATE_DEFAULT_FIELDS = {'create_project_state': {'group'}}
_DELEGATED_QUERY_READS = {'preview_retained_container_cleanup': set(CONTAINER_KINDS)}


def _serializer_class(path):
    module, name = path.rsplit('.', 1)
    return getattr(import_module(module), name)


def _payload_serializers(tool, row):
    paths = [item['class'] for item in row['serializers'] if item['channel'] == 'data']
    if tool['name'] in _SERVICE_SERIALIZERS:
        paths.append(_SERVICE_SERIALIZERS[tool['name']])
    return [_serializer_class(path)() for path in paths]


def _missing_reads(tool):
    row = inventory_tool('projects', tool, definitions={})
    declared = set(tool['input_schema']['properties'])
    excluded = set(PANEL_ONLY_FIELDS.get(tool['name'], {}))
    files = {config['field'] for config in tool['_panel_operation']['asset_fields'].values()}
    data_reads = set(row['data_reads'])
    query_reads = set(row['query_reads']) | _DELEGATED_QUERY_READS.get(tool['name'], set())
    query_schema = tool['_panel_operation']['query_schema'] or {'properties': {}}
    for serializer in _payload_serializers(tool, row):
        data_reads.update(name for name, field in serializer.fields.items() if not field.read_only)
    return {
        'query': sorted(query_reads - declared - excluded),
        'unused_query': sorted(set(query_schema['properties']) - query_reads),
        'payload': sorted(data_reads - declared - excluded - files),
    }


def _nested_serializer_issues(serializer, schema, prefix):
    issues = []
    child = getattr(serializer, 'child', serializer)
    if not hasattr(child, 'fields'):
        return issues
    schema = schema.get('items', schema)
    writable = {name: field for name, field in child.fields.items() if not field.read_only}
    if set(schema.get('properties', {})) != set(writable):
        issues.append(f'{prefix}: nested fields differ from writable serializer fields')
    required = {name for name, field in writable.items() if field.required}
    if set(schema.get('required', [])) != required:
        issues.append(f'{prefix}: nested required fields differ from serializer')
    for name, field in writable.items():
        if name in schema.get('properties', {}):
            issues.extend(_nested_serializer_issues(field, schema['properties'][name], f'{prefix}.{name}'))
    return issues


def _serializer_issues(tool):
    row = inventory_tool('projects', tool, definitions={})
    payload = tool['_panel_operation']['payload_schema']
    if payload is None:
        return []
    declared = set(payload['properties'])
    name = tool['name']
    excluded = set(PANEL_ONLY_FIELDS.get(name, {}))
    files = {config['field'] for config in tool['_panel_operation']['asset_fields'].values()}
    issues = []
    for serializer in _payload_serializers(tool, row):
        fields = {key: field for key, field in serializer.fields.items() if not field.read_only}
        allowed = (set(fields) - excluded - files) | _VIEW_PAYLOAD_FIELDS.get(name, set())
        if declared != allowed:
            issues.append(f'{name}: payload fields differ: {sorted(declared ^ allowed)}')
        if name.startswith('create_'):
            required = {key for key, field in fields.items() if field.required} - files
            required -= _CREATE_DEFAULT_FIELDS.get(name, set())
            if set(payload['required']) != required:
                issues.append(f'{name}: required fields differ from effective create serializer')
        for key in declared & set(fields):
            issues.extend(_nested_serializer_issues(fields[key], payload['properties'][key], f'{name}.{key}'))
    return issues


@pytest.fixture(scope='module')
def original_bridge_tools():
    return {
        tool['name']: tool for tool in TOOLS_BY_SLUG['projects']
        if '_panel_operation' in tool and ('projects', tool['name']) not in EXCLUDED_TOOLS
    }


@pytest.fixture(scope='module')
def bridge_tools(original_bridge_tools):
    return original_bridge_tools


@pytest.fixture
def panel_case(db):
    case = context()
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    execution = McpExecutionContext(
        connector=connector, credential=None, request_id='projects-bridge-schema', actor=case.admin,
    )
    with use_mcp_context(execution):
        yield case


def test_projects_bridge_family_has_complete_closed_schemas(original_bridge_tools, bridge_tools):
    failures = {name: schema_problems(tool) for name, tool in bridge_tools.items()}
    assert all(bridge_tools[name]['_panel_operation'][key] == schema
               for name, fragments in PROJECTS_BRIDGE_SCHEMAS.items()
               for key, schema in fragments.items())

    assert len(original_bridge_tools) == 48
    assert set(PROJECTS_BRIDGE_SCHEMAS) == set(original_bridge_tools)
    assert failures == {name: [] for name in original_bridge_tools}, failures


def test_projects_bridge_contract_covers_panel_reads(bridge_tools):
    missing = {name: _missing_reads(tool) for name, tool in bridge_tools.items()}

    assert missing == {name: {'query': [], 'unused_query': [], 'payload': []} for name in bridge_tools}, missing


def test_projects_bridge_payload_matches_writable_serializers(bridge_tools):
    mismatches = {name: _serializer_issues(tool) for name, tool in bridge_tools.items()}

    assert mismatches == {name: [] for name in bridge_tools}, mismatches


@pytest.mark.parametrize(('tool_name', 'field', 'channel'), [
    ('list_projects', 'scope', 'query'),
    ('create_project_idea', 'request_id', 'payload'),
    ('set_project_client_access_policy', 'permissions', 'payload'),
])
def test_removing_an_input_is_detected_by_the_read_audit(bridge_tools, tool_name, field, channel):
    mutated = deepcopy(bridge_tools[tool_name])
    del mutated['input_schema']['properties'][field]

    missing = _missing_reads(mutated)

    assert missing[channel] == [field]


def test_flat_project_filter_returns_only_the_selected_client(bridge_tools, panel_case):
    arguments = {'scope': 'all', 'client_profile_id': panel_case.client.profile.pk}

    result = assert_no_writes(bridge_tools['list_projects']['handler'], arguments)

    assert [row['id'] for row in result['results']] == [panel_case.project.pk]
    assert result['results'][0]['client']['profile_id'] == panel_case.client.profile.pk


def test_flat_idea_create_persists_the_authenticated_author(bridge_tools, panel_case):
    arguments = {
        'project_id': panel_case.project.pk, 'text': 'Una idea del equipo',
        'request_id': '281bde5c-82b0-475a-87c2-693cc1b2d382',
    }

    result = bridge_tools['create_project_idea']['handler'](arguments)

    persisted = ProjectIdea.objects.get(pk=result['id'])
    assert (persisted.project_id, persisted.author_id, persisted.text) == (
        panel_case.project.pk, panel_case.admin.pk, arguments['text'],
    )
    assert list(persisted.revisions.values_list('number', 'text')) == [(1, arguments['text'])]


def test_flat_project_update_keeps_the_owner(bridge_tools, panel_case):
    arguments = {'project_id': panel_case.project.pk, 'name': 'Proyecto revisado', 'description': 'Descripción revisada'}

    result = bridge_tools['update_project']['handler'](arguments)

    panel_case.project.refresh_from_db()
    assert (panel_case.project.name, panel_case.project.description, panel_case.project.client_id) == (
        arguments['name'], arguments['description'], panel_case.client.pk,
    )
    assert result['id'] == panel_case.project.pk
    assert result['name'] == arguments['name']


def test_flat_client_change_executes_the_reviewed_detach_plan(bridge_tools, panel_case, make_income):
    income = make_income(client=panel_case.client.profile, project=panel_case.project)
    target = {'project_id': panel_case.project.pk, 'client_profile_id': panel_case.other.profile.pk}
    preview = assert_no_writes(bridge_tools['preview_project_client_change']['handler'], target)
    tool = bridge_tools['change_project_client']
    arguments = tool['prepare_arguments']({**target, 'mode': 'detach', 'expected_impact_hash': preview['impact_hash']})

    impact = assert_no_writes(tool['impact_builder'], arguments)
    result = tool['handler'](arguments)

    panel_case.project.refresh_from_db()
    income.refresh_from_db()
    assert tool['requires_confirmation'] is True
    assert impact['selected_plan'] == preview['planned']['detach']
    assert panel_case.project.client_id == panel_case.other.pk
    assert (income.client_id, income.project_id) == (panel_case.client.profile.pk, None)
    assert result['project']['client']['profile_id'] == panel_case.other.profile.pk


def test_client_change_impact_rejects_an_outdated_hash(bridge_tools, panel_case):
    tool = bridge_tools['change_project_client']
    arguments = tool['prepare_arguments']({
        'project_id': panel_case.project.pk, 'client_profile_id': panel_case.other.profile.pk,
        'mode': 'move', 'expected_impact_hash': '0' * 64,
    })

    with pytest.raises(ToolError) as caught:
        assert_no_writes(tool['impact_builder'], arguments)

    assert caught.value.code == 'STALE_VERSION'
    assert Project.objects.get(pk=panel_case.project.pk).client_id == panel_case.client.pk


def test_state_creation_uses_the_default_exclusive_group(bridge_tools, panel_case):
    group = DocumentStateGroup.objects.filter(catalog='projects', selection_mode='exclusive', is_active=True).order_by('order', 'id').first()
    arguments = {
        'name': 'Estado de prueba del puente', 'description': 'Estado operativo usado para revisar el contrato.',
        'operational_effect': 'operating', 'confirm_similar': True,
    }

    result = bridge_tools['create_project_state']['handler'](arguments)

    created = DocumentState.objects.get(pk=result['id'])
    assert group is not None
    assert (created.group_id, created.catalog, created.operational_effect) == (group.pk, 'projects', 'operating')
    assert 'group' not in PROJECTS_BRIDGE_SCHEMAS['create_project_state']['payload_schema']['required']


def test_flat_cleanup_selection_encodes_an_id_list_as_csv(bridge_tools, panel_case):
    retained = ProjectRetentionContext.objects.create(
        client=panel_case.client, original_project_id=9001, project_name='Proyecto eliminado', created_by=panel_case.admin,
    )
    chosen = DocumentFolder.objects.create(name='Carpeta seleccionada', client_user=panel_case.client, retention_context=retained)
    other = DocumentFolder.objects.create(name='Otra carpeta conservada', client_user=panel_case.client, retention_context=retained)
    arguments = {'context_id': retained.pk, 'document_folders': [chosen.pk]}

    result = assert_no_writes(bridge_tools['preview_retained_container_cleanup']['handler'], arguments)

    assert [(item['kind'], item['id']) for item in result['containers']] == [('document_folders', chosen.pk)]
    assert result['blockers'] == []
    assert DocumentFolder.objects.filter(pk=other.pk, retention_context=retained).exists()


@pytest.mark.parametrize('tool_name', ['preview_project_delete', 'delete_project'])
@pytest.mark.parametrize(('field', 'value'), [('force', True), ('delete_keys', [])])
def test_project_delete_rejects_panel_only_arguments(bridge_tools, panel_case, tool_name, field, value):
    tool = bridge_tools[tool_name]
    arguments = {'project_id': panel_case.project.pk, field: value}

    with pytest.raises(ToolError) as caught:
        assert_no_writes(tool['handler'], arguments)

    assert set(tool['input_schema']['properties']) - {'if_match'} == {'project_id'}
    assert caught.value.code == 'unknown_field'
    assert caught.value.details['errors'][0]['field'] == field
    assert Project.objects.filter(pk=panel_case.project.pk).exists()


@pytest.mark.parametrize('field', ['hosting_ids', 'income_ids', 'communication_thread_ids'])
def test_client_change_rejects_legacy_panel_selections(bridge_tools, panel_case, field):
    arguments = {
        'project_id': panel_case.project.pk, 'client_profile_id': panel_case.other.profile.pk,
        'mode': 'move', 'expected_impact_hash': '0' * 64, field: [],
    }

    with pytest.raises(ToolError) as caught:
        assert_no_writes(bridge_tools['change_project_client']['handler'], arguments)

    assert caught.value.code == 'unknown_field'
    assert caught.value.details['errors'][0]['field'] == field
    assert Project.objects.get(pk=panel_case.project.pk).client_id == panel_case.client.pk
