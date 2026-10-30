"""Real MCP transport for the same contract source search and link as the panel."""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from accounts.models import ProjectContract
from accounts.tests.project_collaboration_helpers import context
from content.models import Document, DocumentFolder, McpActionIntent, McpConnector, McpCredential
from content.tests.views.test_mcp_project_collaboration import call  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(params=['accounting', 'accounting-billing'])
def canonical_call(request, superuser):
    connector, _ = McpConnector.objects.get_or_create(slug=request.param, defaults={'name': request.param})
    connector.is_active = True
    connector.save()
    credential = McpCredential.objects.create(connector=connector, label='Contract search', actor=superuser)
    token = credential.generate_token()
    client = APIClient()

    def invoke(name, arguments):
        response = client.post(f'/api/mcp/{connector.slug}/{token}/', {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }, format='json')
        assert response.status_code == 200
        assert response.data['result']['isError'] is False, response.data
        return response.data['result']['structuredContent']
    return invoke


def test_canonical_accounting_can_search_and_confirm_an_existing_contract(canonical_call):
    c = context()
    source = Document.objects.create(title='Revisión_Contrato_Base', project=c.project)
    options = canonical_call('get_project_billing_options', {'project_id': c.project.pk, 'contract_source_search': 'VISION contrato'})
    assert [row['id'] for row in options['contract_sources']] == [source.pk]

    preview = canonical_call('link_project_billing_contract', {
        'project_id': c.project.pk, 'payload': {
            'source_type': 'document', 'source_id': source.pk,
            'expected_version': options['delivery_version'], 'request_id': 'canonical-search-link',
        },
    })
    assert not ProjectContract.objects.filter(project=c.project).exists()
    result = canonical_call('confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert ProjectContract.objects.get(pk=result['result']['id']).document_id == source.pk


def test_mcp_contract_search_matches_panel_metadata_and_can_link_a_result(call, superuser):
    c = context()
    folder = DocumentFolder.objects.create(name='Firmados', project=c.project)
    source = Document.objects.create(title='Revisión_Contráto_Base', project=c.project, folder=folder)
    Document.objects.create(title='Evidencia', project=c.project)
    Document.objects.create(title='Contrato ajeno', project=c.other_project)
    panel = APIClient()
    panel.force_authenticate(user=superuser)
    response = panel.get(f'/api/admin/billing-context/projects/{c.project.pk}/options/')

    options = call('get_project_billing_options', {'project_id': c.project.pk, 'contract_source_search': 'VISION contrato'})

    assert response.status_code == 200
    assert options['contract_sources'] == [response.data['contract_sources'][0]]
    assert options['contract_sources'][0]['folder_path'] == 'Firmados'
    assert options['contract_sources'][0]['id'] == source.pk
    preview = call('link_project_billing_contract', {
        'project_id': c.project.pk, 'payload': {
            'source_type': 'document', 'source_id': source.pk,
            'expected_version': options['delivery_version'], 'request_id': 'search-then-link',
        },
    })
    assert not ProjectContract.objects.filter(project=c.project).exists()
    result = call('confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert ProjectContract.objects.get(pk=result['result']['id']).document_id == source.pk


@pytest.mark.parametrize('query', [None, 12, 'a' * 301])
def test_mcp_search_rejects_invalid_queries_without_writing(call, query):
    c = context()

    error = call('get_project_billing_options', {'project_id': c.project.pk, 'contract_source_search': query}, error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert not McpActionIntent.objects.exists()


def test_mcp_search_rejects_the_unpublished_query_alias(call):
    c = context()

    error = call('get_project_billing_options', {'project_id': c.project.pk, 'query': 'contrato'}, error=True)

    assert error['code'] == 'unknown_field'
    assert error['details']['errors'] == [{
        'field': 'query', 'code': 'unknown_field', 'message': 'Campo desconocido o de solo lectura.',
    }]
    assert not McpActionIntent.objects.exists()


def test_mcp_empty_search_returns_all_versions_and_no_match_is_empty(call):
    c = context()
    older = Document.objects.create(title='Contrato_Base', project=c.project)
    newer = Document.objects.create(title='Contrato_Base', project=c.project)

    options = call('get_project_billing_options', {'project_id': c.project.pk, 'contract_source_search': ''})
    absent = call('get_project_billing_options', {'project_id': c.project.pk, 'contract_source_search': 'no existe'})

    assert [row['id'] for row in options['contract_sources']] == [newer.pk, older.pk]
    assert absent['contract_sources'] == []


def test_mcp_search_denies_non_admin_actor(call):
    c = context()
    with patch('content.mcp.platform_billing_tools.mcp_actor', return_value=c.client):
        error = call('get_project_billing_options', {'project_id': c.project.pk, 'contract_source_search': 'contrato'}, error=True)

    assert error['code'] == 'FORBIDDEN'
    assert not ProjectContract.objects.exists()
