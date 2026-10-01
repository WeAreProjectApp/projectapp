"""Administrative MCP safeguards for project ideas and access visibility."""

from uuid import uuid4

import pytest
from accounts.models_project_ideas import ProjectIdea, ProjectIdeaCollection
from accounts.services import project_client_access as access
from accounts.services import project_ideas as ideas
from accounts.tests.project_collaboration_helpers import context, idea, sources
from rest_framework.test import APIClient

from content.models import McpConnector

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
