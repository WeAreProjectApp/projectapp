"""Flat discovery preserves deprecated MCP calls through domain validation."""
from copy import deepcopy
import logging
from types import SimpleNamespace

import pytest

from accounts.models import Project
from content.mcp.connectors import TOOLS_BY_SLUG
from content.mcp.entity_history_tools import history_tools
from content.mcp.project_retention_tools import PROJECT_RETENTION_TOOLS
from content.mcp.proposal_approval_tools import PROPOSAL_APPROVAL_TOOLS
from content.mcp.proposal_project_tools import REASSIGN
from content.mcp.registry import normalize_tools
from content.models import (
    Document, EntityHistory, EntityRevision, McpActionIntent,
    ProposalContractSnapshot, ProposalFormalization,
)
from content.services.contract_template_service import read_template
from content.tests.contract_template_fixtures import rpc_call
from content.tests.views.test_mcp_parity_refresh import activate_connector, call_tool
from content.tests.views.test_mcp_proposal_contract_modality import accepted_mcp_proposal, TERMS
from content.tests.views.test_mcp_proposal_formalization import (
    formalization_arguments, formalization_proposal,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def flat_panel_contract(monkeypatch):
    """Simulate the incoming panel bridge contract without changing its owned module."""
    definitions = [REASSIGN, *PROPOSAL_APPROVAL_TOOLS, *PROJECT_RETENTION_TOOLS]
    names = {tool['name'] for tool in definitions if tool['_panel_operation'].get('payload_schema')}
    registered = [tool for slug in ('proposals', 'projects') for tool in TOOLS_BY_SLUG[slug]
                  if tool['name'] in names]
    for tool in [*definitions, *registered]:
        operation = tool['_panel_operation']
        if not operation.get('payload_schema'):
            continue
        accepted = deepcopy(tool.get('accepted_arguments_schema') or tool['input_schema'])
        accepted['required'] = list(operation['path_params'])
        published = deepcopy(tool['input_schema'])
        published['properties'].pop('data', None)
        published['properties'].pop('query', None)
        published['required'] = [*operation['path_params'], *operation['payload_schema'].get('required', [])]
        monkeypatch.setitem(tool, 'input_schema', published)
        monkeypatch.setitem(tool, 'accepted_arguments_schema', accepted)


@pytest.fixture(params=['proposal', 'document', 'project'])
def history_case(request, proposal, admin_user, monkeypatch):
    entity = request.param
    records = {
        'proposal': proposal,
        'document': Document.objects.create(title='History document'),
        'project': Project.objects.create(name='History project', client=admin_user),
    }
    record = records[entity]
    history, _ = EntityHistory.objects.get_or_create(
        entity_type=entity, object_id=record.pk, defaults={'object_label': entity},
    )
    revisions = EntityRevision.objects.bulk_create([
        EntityRevision(history=history, number=1000 + number, action='updated',
                       snapshot={'title': f'Version {number}'})
        for number in range(21)
    ])
    expected_page = list(history.entries.order_by('occurred_at', 'id').values_list('pk', flat=True)[20:40])
    slug = {'proposal': 'proposals', 'document': 'documents', 'project': 'projects'}[entity]
    if entity == 'document':
        # Exercise the generic factory on documents before its catalog integration lands.
        tools = normalize_tools(history_tools(entity), slug)
        names = {tool['name'] for tool in tools}
        monkeypatch.setitem(TOOLS_BY_SLUG, slug, [
            *[tool for tool in TOOLS_BY_SLUG[slug] if tool['name'] not in names], *tools,
        ])
    return SimpleNamespace(entity=entity, slug=slug, token=activate_connector(slug),
                           object_id=record.pk, left=revisions[0], right=revisions[1],
                           expected_page=expected_page)


def test_history_query_preserves_pagination(api_client, history_case, caplog):
    """A legacy query must reach the same page and order on every history connector."""
    case = history_case
    caplog.set_level(logging.INFO)

    result = call_tool(api_client, case.slug, case.token, f'list_{case.entity}_history', {
        'object_id': case.object_id, 'query': {'page': 2, 'order': 'oldest'},
    }).data['result']

    assert result['isError'] is False
    assert result['structuredContent']['page'] == 2
    assert [row['id'] for row in result['structuredContent']['results']] == case.expected_page
    assert f'deprecated_envelope tool=list_{case.entity}_history keys=[\'query\']' in caplog.text


def test_history_query_preserves_version_comparison(api_client, history_case):
    """Legacy from/to IDs must still resolve the two selected historical versions."""
    case = history_case

    result = call_tool(api_client, case.slug, case.token, f'compare_{case.entity}_history', {
        'object_id': case.object_id, 'query': {'from': case.left.pk, 'to': case.right.pk},
    }).data['result']

    assert result['isError'] is False
    assert result['structuredContent']['from']['id'] == case.left.pk
    assert result['structuredContent']['to']['id'] == case.right.pk
    assert result['structuredContent']['changes'][0]['field'] == 'title'


def test_history_query_accepts_legacy_version_identifiers(api_client, history_case):
    """Version IDs sent as strings must retain the panel's existing coercion behavior."""
    case = history_case

    result = call_tool(api_client, case.slug, case.token, f'compare_{case.entity}_history', {
        'object_id': case.object_id, 'query': {'from': str(case.left.pk), 'to': str(case.right.pk)},
    }).data['result']

    assert result['isError'] is False
    assert result['structuredContent']['from']['id'] == case.left.pk
    assert result['structuredContent']['to']['id'] == case.right.pk


def test_history_query_rejects_a_conflicting_flat_page(api_client, proposals_mcp, proposal):
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'list_proposal_history', {
        'object_id': proposal.pk, 'page': 1, 'query': {'page': 2},
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert 'valores distintos' in result['structuredContent']['error']['message']


def test_history_query_accepts_a_matching_flat_page(api_client, proposals_mcp, proposal):
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'list_proposal_history', {
        'object_id': proposal.pk, 'page': 2, 'query': {'page': 2}, 'if_match': 'legacy-etag',
    })

    assert result['isError'] is False
    assert result['structuredContent']['page'] == 2


def test_history_query_reaches_page_validation(api_client, proposals_mcp, proposal):
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'list_proposal_history', {
        'object_id': proposal.pk, 'query': {'page': 0},
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['details']['page'] == 'Página no válida.'


def test_history_query_rejects_an_unknown_field(api_client, proposals_mcp, proposal):
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'list_proposal_history', {
        'object_id': proposal.pk, 'query': {'entity_type': 'project'},
    })

    assert result['isError'] is True
    assert 'entity_type' in result['structuredContent']['error']['message']


def test_history_query_requires_the_object_identifier_at_root(api_client, proposals_mcp, proposal):
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'list_proposal_history', {
        'query': {'object_id': proposal.pk, 'page': 1},
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert 'object_id' in result['structuredContent']['error']['message']


def test_formalization_data_creates_a_private_package(
    api_client, proposals_mcp, formalization_arguments, caplog,
):
    """The old data envelope must prepare a real, credential-owned review package."""
    token, credential = proposals_mcp
    args = dict(formalization_arguments)
    proposal_id = args.pop('proposal_id')
    caplog.set_level(logging.INFO)

    result = rpc_call(api_client, token, 'prepare_proposal_formalization', {
        'proposal_id': proposal_id, 'data': args,
    })

    assert result['isError'] is False
    assert result['structuredContent']['subject'] == args['subject']
    assert ProposalFormalization.objects.get(pk=result['structuredContent']['id']).mcp_credential_id == credential.pk
    assert 'deprecated_envelope tool=prepare_proposal_formalization keys=[\'data\']' in caplog.text


def test_modality_data_returns_the_confirmable_plan(
    api_client, proposals_mcp, accepted_mcp_proposal, caplog,
):
    """Legacy modality payloads must produce the same plan without applying the change."""
    token, _ = proposals_mcp
    caplog.set_level(logging.INFO)

    result = rpc_call(api_client, token, 'update_proposal_contract_modality', {
        'proposal_id': accepted_mcp_proposal.pk,
        'data': {'contract_modality': 'split', 'change_note': 'Separate agreement', 'contract_params': TERMS},
    })

    accepted_mcp_proposal.refresh_from_db()
    assert result['isError'] is False
    assert result['structuredContent']['confirmation_required'] is True
    assert accepted_mcp_proposal.contract_modality == 'single'
    assert 'deprecated_envelope tool=update_proposal_contract_modality keys=[\'data\']' in caplog.text


def test_snapshot_data_reaches_proposal_ownership_validation(
    api_client, proposals_mcp, accepted_mcp_proposal, proposal,
):
    """The restore alias must be accepted before rejecting a different proposal's snapshot."""
    token, _ = proposals_mcp
    snapshot = ProposalContractSnapshot.objects.create(
        proposal=accepted_mcp_proposal, payload={}, actor_label='Admin', source='panel',
        change_note='Original', from_modality='single', to_modality='split',
    )

    result = rpc_call(api_client, token, 'restore_proposal_contract_snapshot', {
        'proposal_id': proposal.pk, 'data': {'snapshot_id': snapshot.pk, 'change_note': 'Restore'},
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'NOT_FOUND'
    assert McpActionIntent.objects.count() == 0


def test_reassignment_data_reaches_target_validation(api_client, proposals_mcp, proposal, flat_panel_contract):
    """A legacy correction must reach its serializer rather than fail as an unknown envelope."""
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'reassign_proposal_project', {
        'proposal_id': proposal.pk, 'data': {
            'target_project_id': 0, 'reason': 'Correction',
            'expected_impact_hash': 'a' * 64, 'request_id': 'legacy-reassignment',
        },
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert 'target_project_id' in result['structuredContent']['error']['details']
    assert McpActionIntent.objects.count() == 0


@pytest.mark.parametrize('name', ['review_proposal_approval', 'launch_proposal_to_platform'])
def test_approval_data_reaches_source_hash_validation(api_client, proposals_mcp, proposal, name, flat_panel_contract):
    """Both legacy approval calls must reach the domain's required source hash check."""
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, name, {'proposal_id': proposal.pk, 'data': {'action': 'confirm'}})

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert 'source_hash' in result['structuredContent']['error']['details']
    assert McpActionIntent.objects.count() == 0


@pytest.mark.parametrize(('name', 'path'), [
    ('undo_retained_operation', 'operation_id'), ('delete_empty_retained_containers', 'context_id'),
])
def test_retention_reason_is_validated_before_confirmation(api_client, name, path):
    """Flat retention calls validate their reason before looking up the resource."""
    token = activate_connector('projects')

    result = call_tool(api_client, 'projects', token, name, {
        path: 1, 'reason': '', 'request_id': 'flat-retention', 'expected_impact_hash': 'a' * 64,
    }).data['result']

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert 'reason' in result['structuredContent']['error']['details']
    assert McpActionIntent.objects.count() == 0


@pytest.mark.parametrize(('name', 'path'), [
    ('undo_retained_operation', 'operation_id'), ('delete_empty_retained_containers', 'context_id'),
])
def test_retention_rejects_a_deprecated_data_envelope(api_client, name, path):
    """Projects 3.0 rejects a legacy envelope before creating a confirmation."""
    token = activate_connector('projects')

    result = call_tool(api_client, 'projects', token, name, {
        path: 1, 'reason': 'Prueba de rechazo', 'request_id': 'unsupported-retention',
        'expected_impact_hash': 'a' * 64, 'data': {'reason': 'Otro valor'},
    }).data['result']

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'unknown_field'
    assert result['structuredContent']['error']['details']['errors'][0]['field'] == 'data'
    assert McpActionIntent.objects.count() == 0


@pytest.mark.parametrize('variant', ['product', 'service'])
def test_template_query_preserves_selected_variant(api_client, proposals_mcp, coherent_template, variant, caplog):
    """The legacy query variant must select the corresponding contract text and metadata."""
    token, _ = proposals_mcp
    caplog.set_level(logging.INFO)

    result = rpc_call(api_client, token, 'get_proposal_contract_template', {'query': {'variant': variant}})

    assert result['isError'] is False
    assert result['structuredContent']['variant'] == variant
    assert result['structuredContent']['markdown'] == read_template(variant)['markdown']
    assert 'deprecated_envelope tool=get_proposal_contract_template keys=[\'query\']' in caplog.text


@pytest.mark.parametrize('name', ['send_branded_email', 'send_custom_proposal_email'])
def test_recipient_alias_reaches_email_content_validation(api_client, proposals_mcp, proposal, name):
    """The single-recipient alias must survive confirmation and reach the real email parser."""
    token, _ = proposals_mcp
    preview = rpc_call(api_client, token, name, {
        'proposal_id': proposal.pk, 'recipient_email': 'legacy@example.com', 'subject': 'Legacy email',
    })

    result = rpc_call(api_client, token, 'confirm_action', {
        'confirmation_id': preview['structuredContent']['confirmation_id'],
    })

    assert result['isError'] is True
    assert 'Debe incluir al menos una sección con contenido.' in result['structuredContent']['error']['message']


@pytest.mark.parametrize('name', ['preview_proposal_contract_template_update', 'update_proposal_contract_template'])
@pytest.mark.parametrize('sources', [{}, {'markdown': '# Invalid', 'patches': []}], ids=['missing', 'both'])
def test_template_source_constraint_is_enforced_by_the_handler(
    api_client, proposals_mcp, coherent_template, name, sources,
):
    """Removing the root constraint must preserve rejection of missing or competing sources."""
    token, _ = proposals_mcp
    before = read_template('combined')

    result = rpc_call(api_client, token, name, {
        'variant': 'combined', 'if_match': before['etag'], 'change_note': 'Invalid edit', **sources,
    })

    assert result['isError'] is True
    assert 'exactamente uno de markdown o patches' in result['structuredContent']['error']['message']
    assert read_template('combined')['etag'] == before['etag']


@pytest.mark.parametrize(('name', 'payload'), [
    ('review_proposal_approval', {'new_client': {'name': 'Client', 'unexpected': True}}),
    ('launch_proposal_to_platform', {'new_client': {'name': 'Client', 'unexpected': True}}),
    ('prepare_proposal_formalization', {'sections': [{'text': 'Body', 'unexpected': True}]}),
    ('reorder_proposal_sections', {'sections': [{'id': 1, 'order': 0, 'unexpected': True}]}),
    ('send_proposal_documents', {'document_descriptions': [{'name': 'Document', 'unexpected': True}]}),
    ('send_branded_email', {'sections': [{'text': 'Body', 'unexpected': True}]}),
    ('send_custom_proposal_email', {'sections': [{'text': 'Body', 'unexpected': True}]}),
])
def test_nested_unknown_field_is_rejected_before_execution(api_client, proposals_mcp, proposal, name, payload):
    """Unknown nested keys must not be silently dropped or create a pending write."""
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, name, {'proposal_id': proposal.pk, **payload})

    assert result['isError'] is True
    assert result['structuredContent']['error']['message'] == 'Campos no editables: unexpected'
    assert McpActionIntent.objects.count() == 0


def test_service_settings_rejects_an_unknown_nested_field(api_client, proposals_mcp, company_settings):
    """The finite service catalog must reject a nested typo without changing stored defaults."""
    token, _ = proposals_mcp
    before = company_settings.service_contract_settings

    result = rpc_call(api_client, token, 'update_proposal_service_settings', {
        'service_contract_settings': {'unexpected': [3, 6]},
    })

    company_settings.refresh_from_db()
    assert result['isError'] is True
    assert result['structuredContent']['error']['message'] == 'Campos no editables: unexpected'
    assert company_settings.service_contract_settings == before


def test_json_import_accepts_section_content_keys(api_client, proposals_mcp, proposal, proposal_section):
    """The open section marker must preserve valid client-specific content on JSON import."""
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'update_proposal_from_json', {
        'proposal_id': proposal.pk, 'title': 'Imported content', 'client_name': proposal.client_name,
        'sections': {'general': {'clientName': proposal.client_name, 'heading': 'Client-specific greeting'}},
    })

    proposal_section.refresh_from_db()
    assert result['isError'] is False
    assert proposal_section.content_json['heading'] == 'Client-specific greeting'


def test_section_update_accepts_content_keys(api_client, proposals_mcp, proposal_section):
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'update_proposal_section', {
        'section_id': proposal_section.pk, 'content_json': {'heading': 'New greeting'},
    })

    proposal_section.refresh_from_db()
    assert result['isError'] is False
    assert proposal_section.content_json == {'heading': 'New greeting'}


@pytest.mark.parametrize('name', [
    'update_proposal_contract_modality', 'restore_proposal_contract_snapshot', 'prepare_proposal_formalization',
    'list_proposal_history', 'get_proposal_history_version', 'compare_proposal_history', 'download_proposal_history_file',
    'get_proposal_contract_template', 'preview_proposal_contract_template_update',
    'update_proposal_contract_template', 'restore_proposal_contract_template_version',
])
def test_handwritten_tool_publishes_flat_arguments(api_client, proposals_mcp, name):
    """Clients must discover a closed, flat input without runtime-only envelopes or root constraints."""
    token, _ = proposals_mcp

    tools = api_client.post(f'/api/mcp/proposals/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list',
    }, format='json').data['result']['tools']
    tool = next(row for row in tools if row['name'] == name)
    schema = tool['inputSchema']

    assert not {'data', 'query'} & schema['properties'].keys()
    assert not {'anyOf', 'oneOf', 'allOf'} & schema.keys()
    assert schema['additionalProperties'] is False
    assert 'accepted_arguments_schema' not in tool
