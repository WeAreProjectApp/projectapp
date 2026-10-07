"""Administrative MCP safeguards for project ideas and access visibility."""

from uuid import uuid4

import pytest
from accounts.models import Deliverable, ProjectPhase
from accounts.models_project_ideas import ProjectIdea, ProjectIdeaCollection
from accounts.services import project_client_access as access
from accounts.services import project_ideas as ideas
from accounts.tests.project_collaboration_helpers import context, idea, sources
from rest_framework.test import APIClient

from content.models import BusinessProposal, Document, McpConnector

pytestmark = pytest.mark.django_db


@pytest.fixture
def call():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()
    client = APIClient()

    def invoke(name, arguments, *, error=False):
        response = client.post(f'/api/mcp/projects/{token}/', {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments}}, format='json')
        assert response.status_code == 200
        result = response.data['result']
        assert result['isError'] is error, result['content'][0]['text']
        return result['structuredContent']['error'] if error else result['structuredContent']
    return invoke


def test_mcp_team_idea_uses_real_author(call):
    c = context()
    result = call('create_project_idea', {'project_id': c.project.pk, 'text': 'Team suggestion', 'request_id': str(uuid4())})
    assert result['origin'] == 'team'
    assert ProjectIdea.objects.get(pk=result['id']).author.first_name == 'MCP'


def test_mcp_cannot_rewrite_client_idea(call):
    c = context()
    original = idea(c, text='Original client suggestion')
    result = call('update_project_idea', {'project_id': c.project.pk, 'idea_id': original['id'],
                  'text': 'Unauthorized rewrite', 'expected_version': 1}, error=True)
    assert result['code'] == 'FORBIDDEN'
    assert ProjectIdea.objects.get(pk=original['id']).text == 'Original client suggestion'


def test_mcp_archive_preserves_revisions(call):
    c = context()
    original = idea(c)
    call('archive_project_idea', {'project_id': c.project.pk, 'idea_id': original['id'], 'expected_version': 1})
    result = call('list_project_idea_revisions', {'project_id': c.project.pk, 'idea_id': original['id']})
    assert result['results'][0]['text'] == original['text']


def test_mcp_collection_freezes_selected_version(call):
    c = context()
    original = idea(c, text='Selected original')
    result = call('create_project_idea_collection', {'project_id': c.project.pk, 'title': 'Future contract',
                  'items': [{'idea_id': original['id'], 'expected_version': 1}], 'request_id': str(uuid4())})
    ideas.edit_idea(c.project.pk, c.client, original['id'], {'text': 'Edited later', 'expected_version': 1})
    snapshot = call('get_project_idea_collection', {'project_id': c.project.pk, 'collection_id': result['id']})
    assert snapshot['items'][0]['text'] == 'Selected original'


def test_mcp_collection_rejects_other_project(call):
    c = context()
    original = idea(c)
    call('create_project_idea_collection', {'project_id': c.other_project.pk, 'title': 'Wrong project',
         'items': [{'idea_id': original['id'], 'expected_version': 1}], 'request_id': str(uuid4())}, error=True)
    assert ProjectIdeaCollection.objects.count() == 0


def policy_arguments(c, call):
    policy = call('get_project_client_access_policy', {'project_id': c.project.pk})
    permissions = access.empty_matrix()
    permissions['production']['site_url'] = True
    return {'project_id': c.project.pk, 'expected_version': policy['version'],
            'source_token': policy['source_token'], 'permissions': permissions}


def test_mcp_visibility_changes_only_after_confirmation(call):
    c = context()
    sources(c)
    preview = call('set_project_client_access_policy', policy_arguments(c, call))
    assert access.client_access(c.project.pk, c.client)['environments'] == []
    call('confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert access.client_access(c.project.pk, c.client)['environments'][0]['site_url'] == 'https://client.example.test/'


def test_mcp_confirmation_rejects_changed_source(call):
    c = context()
    sources(c)
    preview = call('set_project_client_access_policy', policy_arguments(c, call))
    c.project.production_url = 'https://unapproved.example.test/'
    c.project.save()
    result = call('confirm_action', {'confirmation_id': preview['confirmation_id']}, error=True)
    assert result['code'] == 'STALE_VERSION'
    assert access.client_access(c.project.pk, c.client)['environments'] == []


def test_mcp_policy_read_contains_no_internal_values(call):
    c = context()
    sources(c)
    result = call('get_project_client_access_policy', {'project_id': c.project.pk})
    assert result['available_fields']['production']['admin_password'] is True
    assert 'production-secret' not in str(result)
    assert 'production-user' not in str(result)
    assert 'Internal operations message' not in str(result)


def test_mcp_exposes_no_client_credential_revelation_tool():
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save()
    response = APIClient().post(f'/api/mcp/projects/{connector.generate_token()}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json')
    names = {tool['name'] for tool in response.data['result']['tools']}
    assert 'get_project_client_access_policy' in names
    assert not names.intersection({'reveal_project_client_credential', 'reveal_project_client_access_password'})
    assert not any('client' in name and 'reveal' in name for name in names)


def test_project_mcp_registers_administrative_project_and_history_tools():
    """Fails if project administration exists in the Panel but is absent from the MCP discovery contract."""
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save()
    response = APIClient().post(f'/api/mcp/projects/{connector.generate_token()}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json')

    names = {tool['name'] for tool in response.data['result']['tools']}
    assert {
        'get_project', 'list_project_commercial_phases', 'add_project_commercial_phase',
        'update_project_commercial_phase', 'remove_project_commercial_phase',
        'reorder_project_commercial_phases', 'get_project_brand',
        'upload_project_brand_asset', 'download_project_brand_asset',
        'delete_project_brand_asset',
        'link_project_billing_contract', 'list_project_history',
        'get_project_history_version', 'compare_project_history',
    } <= names


def test_project_mcp_filters_project_rows_by_the_requested_client_profile(call):
    """Fails if an MCP proposal selector receives projects from a different client."""
    c = context()

    result = call('list_projects', {'query': {'client_profile_id': c.client.profile.pk}})

    assert [row['id'] for row in result['results']] == [c.project.pk]


def test_project_mcp_rejects_an_invalid_client_profile_filter(call):
    """Fails if a malformed client selector silently returns unrelated projects."""

    result = call('list_projects', {'query': {'client_profile_id': 0}}, error=True)

    assert result['code'] == 'INVALID_CLIENT_PROFILE'


def test_project_mcp_rejects_a_commercial_phase_owned_by_another_client(call):
    """Fails if the MCP phase endpoint can attach another client's proposal to this project."""
    c = context()
    foreign_package = Deliverable.objects.create(
        project=c.other_project, title='Foreign package', uploaded_by=c.admin,
    )
    foreign = BusinessProposal.objects.create(
        title='Foreign proposal', client=c.other.profile, client_name='Other client',
        total_investment=1, status=BusinessProposal.Status.ACCEPTED,
        deliverable=foreign_package,
    )

    error = call('add_project_commercial_phase', {
        'project_id': c.project.pk, 'proposal_id': foreign.pk,
    }, error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert ProjectPhase.objects.filter(project=c.project).count() == 0


def test_project_mcp_rejects_an_unlinked_commercial_phase(call):
    """Fails if MCP can create the initial proposal-project binding without the approval review."""
    c = context()
    unlinked_package = Deliverable.objects.create(
        project=c.other_project, title='Wrong project package', uploaded_by=c.admin,
    )
    unlinked = BusinessProposal.objects.create(
        title='Unlinked proposal', client=c.client.profile, client_name='Client',
        total_investment=1, status=BusinessProposal.Status.ACCEPTED,
        deliverable=unlinked_package,
    )

    error = call('add_project_commercial_phase', {
        'project_id': c.project.pk, 'proposal_id': unlinked.pk,
    }, error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert ProjectPhase.objects.filter(project=c.project).count() == 0


def test_project_mcp_reuses_a_confirmed_billing_contract_source(call):
    """Fails if confirming the same MCP billing source twice creates duplicate project contracts."""
    c = context()
    source = Document.objects.create(
        title='MCP billing contract', project=c.project, client_user=c.client,
    )
    options = call('get_project_billing_options', {'project_id': c.project.pk})
    arguments = {
        'project_id': c.project.pk,
        'payload': {
            'source_type': 'document', 'source_id': source.pk,
            'expected_version': options['delivery_version'], 'request_id': 'mcp-contract-link-one',
        },
    }
    preview = call('link_project_billing_contract', arguments)
    first = call('confirm_action', {'confirmation_id': preview['confirmation_id']})
    retry_options = call('get_project_billing_options', {'project_id': c.project.pk})
    retry = call('link_project_billing_contract', {
        **arguments,
        'payload': {
            **arguments['payload'], 'expected_version': retry_options['delivery_version'],
            'request_id': 'mcp-contract-link-retry',
        },
    })
    second = call('confirm_action', {'confirmation_id': retry['confirmation_id']})

    assert preview['confirmation_required'] is True
    assert preview['impact']['project_name'] == c.project.name
    assert preview['impact']['source'] == {
        'source_type': 'document', 'id': source.pk, 'title': 'MCP billing contract',
        'origin_label': 'Documento del proyecto',
    }
    assert first['result']['reused'] is False
    assert second['result'] == {
        'id': first['result']['id'], 'title': 'MCP billing contract', 'reused': True,
    }
