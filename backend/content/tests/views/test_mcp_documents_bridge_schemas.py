"""Contract and Panel behavior of the independently prepared Documents schemas."""

from copy import deepcopy

import pytest
from django.urls import reverse

from content.mcp.confirmation import confirm_action, preview_sensitive_action
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.operation_catalogs import DOCUMENT_PARITY_TOOLS, _ownership_defaults
from content.mcp.panel_bridge import panel_operation
from content.mcp.protocol import ToolError
from content.mcp.schemas.documents_bridge import DOCUMENTS_BRIDGE_SCHEMAS
from content.models import (
    Document,
    DocumentFolder,
    DocumentState,
    DocumentStateGroup,
    DocumentTag,
    DocumentType,
    McpActionIntent,
    McpConnector,
    McpCredential,
)
from content.tests.mcp_schema_rules import schema_problems
from content.tests.mcp_view_inventory import inventory_tool

_ORIGINAL_TOOLS = {tool['name']: tool for tool in DOCUMENT_PARITY_TOOLS}
_CONTRACT_CASES = [
    pytest.param(name, id=f'batch{index // 18 + 1}-{name}')
    for index, name in enumerate(sorted(DOCUMENTS_BRIDGE_SCHEMAS))
]
_PARTIAL_WRITES = {
    'update_folder', 'update_document_tag', 'update_document_state_group',
    'update_document_state_catalog_item', 'update_document_note',
}

# These are real input transformations before serializer validation, rather
# than exemptions for read-only fields. The behavior tests exercise each one.
_PAYLOAD_ALIASES = {'update_folder': {'parent_id': 'parent'}}
_VIEW_CONTROLS = {'create_document_state': {'confirm_similar'}}
_INJECTED_SERIALIZER_FIELDS = {'change_folder_client': {'portal_policy'}}
_VIEW_SUPPLIED_REQUIRED = {'create_document_state': {'group'}}

# The inventory stops after one helper hop and unwraps decorators. These
# additional reads were followed manually to their source, including the
# delegated query builder and document_write_options.
_DELEGATED_READS = {
    'browse_documents': {
        'query': {
            'scope', 'archived', 'order', 'page', 'page_size', 'client',
            'project', 'folder', 'tags', 'states', 'without_states', 'preset',
            'search',
        },
    },
    'list_document_folders': {
        'query': {'scope', 'archived', 'order', 'search', 'parent_id', 'name'},
    },
    'duplicate_document': {'data': {'include_content'}},
    'archive_document': {'data': {'include_content'}},
    'unarchive_document': {'data': {'include_content'}},
    'change_folder_client': {'data': {'portal_policy'}},
}


def _build_tool(name):
    original = _ORIGINAL_TOOLS[name]
    operation = original['_panel_operation']
    tool = panel_operation(
        name=name,
        description=original['description'],
        route_name=operation['route_name'],
        method=operation['method'],
        path_params=operation['path_params'],
        risk=operation['risk'],
        requires_confirmation=operation['requires_confirmation'],
        confirmation_message=operation['confirmation_message'],
        asset_fields=deepcopy(operation['asset_fields']),
        **deepcopy(DOCUMENTS_BRIDGE_SCHEMAS[name]),
    )
    if name in ('move_documents', 'update_folder'):
        tool['handler'] = _ownership_defaults(tool['handler'])
    elif name == 'change_folder_client':
        tool['handler'] = _ownership_defaults(
            tool['handler'], defaults=(('portal_policy', 'abort'),),
        )
    return tool


def _assert_serializer_payload(name, row, payload):
    serializers = [item for item in row['serializers'] if item['channel'] == 'data']
    if not serializers:
        return
    fields = {
        field_name: field
        for serializer in serializers
        for field_name, field in serializer['fields'].items()
    }
    aliases = _PAYLOAD_ALIASES.get(name, {})
    declared = {aliases.get(key, key) for key in payload['properties']}
    writable = {key for key, field in fields.items() if not field['read_only']}
    writable |= _INJECTED_SERIALIZER_FIELDS.get(name, set())
    assert declared - _VIEW_CONTROLS.get(name, set()) == writable

    required = {key for key, field in fields.items() if field['required'] and not field['read_only']}
    required -= _VIEW_SUPPLIED_REQUIRED.get(name, set())
    if name in _PARTIAL_WRITES:
        required = set()
    assert set(payload.get('required', [])) == required


def _call_handler(name, arguments, context):
    with use_mcp_context(context):
        return _build_tool(name)['handler'](arguments)


@pytest.fixture
def bridge_context(superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documentos'},
    )
    credential = McpCredential.objects.create(
        connector=connector, actor=superuser, label='Documents bridge schemas',
    )
    return McpExecutionContext(
        connector=connector, credential=credential, actor=superuser,
        request_id='documents-bridge-schemas',
    )


@pytest.fixture
def markdown_type(db):
    kind, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    return kind


def test_catalog_covers_the_documents_panel_bridge():
    assert len(DOCUMENTS_BRIDGE_SCHEMAS) == 36
    assert set(DOCUMENTS_BRIDGE_SCHEMAS) == set(_ORIGINAL_TOOLS)


@pytest.mark.parametrize('name', _CONTRACT_CASES)
def test_document_bridge_contract_matches_its_view(name):
    tool = _build_tool(name)
    fragments = DOCUMENTS_BRIDGE_SCHEMAS[name]
    row = inventory_tool(
        'documents', tool,
        definitions={name: 'content.mcp.operation_catalogs'},
    )
    payload = fragments.get('payload_schema', _closed_empty_schema())
    query = fragments.get('query_schema', _closed_empty_schema())
    delegated = _DELEGATED_READS.get(name, {})

    assert row['view'] is not None
    assert set(row['data_reads']) | delegated.get('data', set()) <= set(payload['properties'])
    assert set(row['query_reads']) | delegated.get('query', set()) <= set(query['properties'])
    assert set(row['asset_fields']).isdisjoint(payload['properties'])
    assert set(row['input_schema']['required']) >= set(tool['_panel_operation']['path_params'])
    _assert_serializer_payload(name, row, payload)
    assert schema_problems({'name': name, 'input_schema': payload}) == []
    assert schema_problems({'name': name, 'input_schema': query}) == []
    assert schema_problems(tool) == []


def _closed_empty_schema():
    return {'type': 'object', 'properties': {}, 'additionalProperties': False}


@pytest.mark.django_db
@pytest.mark.parametrize('tag_encoding', ['array', 'csv'])
def test_flat_browse_filters_match_the_panel(bridge_context, markdown_type, admin_client, tag_encoding):
    folder = DocumentFolder.objects.create(name='Filtered bridge folder')
    other = DocumentFolder.objects.create(name='Unselected bridge folder')
    tag = DocumentTag.objects.create(name='Bridge filter', color='blue')
    expected = Document.objects.create(
        title='Selected record', folder=folder, document_type=markdown_type,
    )
    expected.tags.add(tag)
    excluded = Document.objects.create(
        title='Selected elsewhere', folder=other, document_type=markdown_type,
    )
    excluded.tags.add(tag)
    Document.objects.create(
        title='Selected without tag', folder=folder, document_type=markdown_type,
    )
    tag_ids = {'array': [tag.pk], 'csv': str(tag.pk)}[tag_encoding]
    arguments = {
        'scope': 'active', 'folder': folder.pk, 'tags': tag_ids,
        'search': 'Selected', 'order': 'oldest', 'page': 1, 'page_size': 12,
    }

    actual = _call_handler('browse_documents', arguments, bridge_context)
    panel = admin_client.get(
        reverse('browse-documents'), {**arguments, 'tags': str(tag.pk)},
    )

    assert panel.status_code == 200
    assert actual == panel.data
    assert [row['id'] for row in actual['results']] == [expected.pk]
    assert actual['count'] == 1


@pytest.mark.django_db
def test_flat_folder_query_keeps_the_root_sentinel(bridge_context, admin_client):
    root = DocumentFolder.objects.create(name='Bridge root')
    DocumentFolder.objects.create(name='Bridge child', parent=root)
    arguments = {'parent_id': 'null', 'search': 'Bridge', 'scope': 'all'}

    actual = _call_handler('list_document_folders', arguments, bridge_context)
    panel = admin_client.get(reverse('list-document-folders'), arguments)

    assert panel.status_code == 200
    assert actual == panel.data
    assert [row['id'] for row in actual] == [root.pk]


@pytest.mark.django_db
def test_flat_tag_create_persists_the_panel_fields(bridge_context):
    arguments = {'name': 'Bridge created tag', 'color': 'purple'}

    result = _call_handler('create_document_tag', arguments, bridge_context)

    created = DocumentTag.objects.get(pk=result['id'])
    assert (created.name, created.color) == ('Bridge created tag', 'purple')
    assert result['slug'] == created.slug
    assert DocumentTag.objects.filter(name=arguments['name']).count() == 1


@pytest.mark.django_db
def test_flat_tag_patch_preserves_omitted_values(bridge_context):
    tag = DocumentTag.objects.create(name='Bridge original tag', color='blue')
    original_slug = tag.slug

    result = _call_handler('update_document_tag', {'tag_id': tag.pk, 'color': 'red'}, bridge_context)

    tag.refresh_from_db()
    assert (tag.name, tag.color, tag.slug) == ('Bridge original tag', 'red', original_slug)
    assert (result['id'], result['name'], result['color']) == (tag.pk, tag.name, 'red')


@pytest.mark.django_db
def test_flat_state_create_preserves_the_view_group_default(bridge_context):
    group = DocumentStateGroup.objects.filter(
        catalog='documents', selection_mode='additive', is_active=True,
    ).order_by('order').first()
    assert group is not None
    arguments = {'name': 'Bridge custom marker', 'confirm_similar': True}

    result = _call_handler('create_document_state', arguments, bridge_context)

    created = DocumentState.objects.get(pk=result['id'])
    assert (created.group_id, created.catalog, created.color) == (group.pk, 'documents', 'gray')
    assert created.name == arguments['name']
    assert 'group' not in _build_tool('create_document_state')['input_schema']['required']


@pytest.mark.django_db
def test_flat_folder_patch_accepts_the_parent_alias(bridge_context):
    parent = DocumentFolder.objects.create(name='Bridge parent')
    folder = DocumentFolder.objects.create(name='Bridge moving folder')

    result = _call_handler('update_folder', {'folder_id': folder.pk, 'parent_id': parent.pk}, bridge_context)

    folder.refresh_from_db()
    assert folder.parent_id == parent.pk
    assert folder.name == 'Bridge moving folder'
    assert result['parent_id'] == parent.pk


@pytest.mark.django_db
def test_flat_duplicate_exposes_the_decorator_content_option(bridge_context, markdown_type):
    original = Document.objects.create(
        title='Bridge original document', document_type=markdown_type,
        content_markdown='# Bridge document',
    )

    result = _call_handler('duplicate_document', {'document_id': original.pk, 'include_content': True}, bridge_context)

    duplicate = Document.objects.get(pk=result['id'])
    assert duplicate.pk != original.pk
    assert duplicate.content_markdown == original.content_markdown
    assert result['markdown'] == original.content_markdown
    assert duplicate.status == Document.Status.DRAFT


@pytest.mark.django_db
def test_flat_folder_archive_executes_the_confirmed_impact(bridge_context, markdown_type):
    folder = DocumentFolder.objects.create(name='Bridge archive folder')
    child = DocumentFolder.objects.create(name='Bridge archive child', parent=folder)
    document = Document.objects.create(
        title='Bridge archive document', document_type=markdown_type, folder=child,
    )
    tool = _build_tool('archive_folder')
    arguments = {'folder_id': folder.pk}

    with use_mcp_context(bridge_context):
        preview = preview_sensitive_action(tool, arguments)
        folder.refresh_from_db()
        assert folder.is_archived is False
        confirmed = confirm_action({'confirmation_id': preview['confirmation_id']}, [tool])

    intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
    folder.refresh_from_db()
    child.refresh_from_db()
    document.refresh_from_db()
    assert preview['impact']['resources'] == arguments
    assert preview['impact']['operation'] == 'archive_folder'
    assert intent.arguments == arguments
    assert intent.status == McpActionIntent.STATUS_EXECUTED
    # The Panel reports descendants; the requested folder is returned separately.
    assert confirmed['result']['archived_folders'] == 1
    assert confirmed['result']['archived_documents'] == 1
    assert (folder.is_archived, child.is_archived, document.is_archived) == (True, True, True)


@pytest.mark.django_db
def test_flat_client_change_uses_the_injected_portal_policy(bridge_context, make_client_profile):
    current = make_client_profile()
    target = make_client_profile()
    folder = DocumentFolder.objects.create(name='Bridge client folder', client_user=current.user)
    arguments = {
        'folder_id': folder.pk, 'client_profile_id': target.pk,
        'mode': 'folder_only', 'portal_policy': 'hide_new_exposure',
        'document_ids': [], 'folder_ids': [],
    }

    result = _call_handler('change_folder_client', arguments, bridge_context)

    folder.refresh_from_db()
    assert folder.client_user_id == target.user_id
    assert result['folder']['client'] == target.pk


@pytest.mark.django_db
def test_unknown_flat_argument_prevents_a_tag_write(bridge_context):
    arguments = {'name': 'Bridge rejected tag', 'typo': 'purple'}

    with pytest.raises(ToolError) as raised:
        _call_handler('create_document_tag', arguments, bridge_context)

    assert raised.value.code == 'unknown_field'
    assert not DocumentTag.objects.filter(name=arguments['name']).exists()
