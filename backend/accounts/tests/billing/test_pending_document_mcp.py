"""Accounting MCP operates the same deferral lifecycle as the panel."""
import pytest
from django.test import RequestFactory

from accounts.models import BillingContextEvent, CollectionAccountContext
from accounts.services.billing_context import associate_account
from accounts.tests.billing.test_mcp import _call
from accounts.tests.billing.test_pending_document import creation_payload, income  # noqa: F401
from content.mcp.context import McpExecutionContext
from content.mcp.principal import service_actor_for_connector
from content.models import Document, McpConnector
from content.views.mcp_blog import TOOLS_BY_SLUG

pytestmark = pytest.mark.django_db


@pytest.fixture
def runtime():
    connector, _ = McpConnector.objects.update_or_create(
        slug='accounting', defaults={'name': 'Contabilidad de prueba', 'is_active': True},
    )
    connector.generate_token()
    credential = connector.credentials.get(label='Default')
    credential.catalog = 'canonical'
    credential.save(update_fields=['catalog'])
    return TOOLS_BY_SLUG['accounting'], McpExecutionContext(
        connector=connector, credential=credential, request_id='pending-document-mcp-test',
        actor=service_actor_for_connector(connector), request=RequestFactory().get('/api/mcp/accounting/'),
    )


def test_mcp_creates_lists_reads_and_completes_pending_document(runtime, project, income, contract, mailoutbox):
    tools, context = runtime
    preview = _call(tools, context, 'create_collection_account', creation_payload(project, income, document_pending=True))
    assert Document.objects.filter(income_record=income).count() == 0
    created = _call(tools, context, 'confirm_action', {'confirmation_id': preview['confirmation_id']})
    assert 'result' in created, created
    doc = created['result']['document']
    assert doc['context']['document_pending'] is True
    assert doc['context']['pending_by'] == context.actor.pk
    assert len(mailoutbox) == 1
    listed = _call(tools, context, 'list_collection_accounts', {'document_pending': True, 'project_id': project.pk})
    assert [row['id'] for row in listed['results']] == [doc['id']]
    assert listed['meta']['document_pending_count'] == 1
    read = _call(tools, context, 'get_collection_account', {'doc_id': doc['id']})
    assert read['context'] == doc['context']
    assignment = {'project_id': project.pk, 'account_id': doc['id'], 'payload': {
        'billing_nature': 'contract', 'contract_id': contract.pk, 'expected_version': 1,
        'reason': 'Contrato recibido mediante MCP.',
    }}
    intent = _call(tools, context, 'associate_collection_account_context', assignment)
    completed = _call(tools, context, 'confirm_action', {'confirmation_id': intent['confirmation_id']})
    assert completed['result']['document_pending'] is False
    assert completed['result']['contract']['id'] == contract.pk
    assert _call(tools, context, 'list_collection_accounts', {'document_pending': True})['results'] == []
    assert BillingContextEvent.objects.filter(document_id=doc['id']).count() == 2


def test_mcp_rejects_partial_links_without_creating_a_document(runtime, project, income, contract):
    tools, context = runtime
    intent = _call(tools, context, 'create_collection_account', creation_payload(
        project, income, document_pending=True, contract_id=contract.pk,
    ))
    result = _call(tools, context, 'confirm_action', {'confirmation_id': intent['confirmation_id']})
    assert result['error']['code'] == 'VALIDATION_ERROR'
    assert not Document.objects.filter(income_record=income).exists()
    assert CollectionAccountContext.objects.count() == 0


def test_mcp_cannot_forge_deferral_audit_fields(runtime, project, income):
    tools, context = runtime
    result = _call(tools, context, 'create_collection_account', creation_payload(
        project, income, document_pending=True, pending_by=999, pending_at='2020-01-01T00:00:00Z',
    ))
    rejected = _call(tools, context, 'confirm_action', {'confirmation_id': result['confirmation_id']})
    assert rejected['error']['code'] == 'unknown_field'
    assert {error['field']: error['code'] for error in rejected['error']['details']['errors']} == {
        'pending_at': 'unknown_field',
        'pending_by': 'unknown_field',
    }
    assert not Document.objects.filter(income_record=income).exists()
    assert not CollectionAccountContext.objects.exists()
    assert not BillingContextEvent.objects.exists()


def test_mcp_completion_requires_current_version(runtime, account, contract):
    tools, context = runtime
    associate_account(account.pk, context.actor, {'document_pending': True}, creating=True)
    intent = _call(tools, context, 'associate_collection_account_context', {
        'project_id': account.project_id, 'account_id': account.pk, 'payload': {
            'billing_nature': 'contract', 'contract_id': contract.pk, 'expected_version': 0, 'reason': 'Versión antigua.',
        },
    })
    result = _call(tools, context, 'confirm_action', {'confirmation_id': intent['confirmation_id']})
    assert result['error']['code'] in ('CONFLICT', 'STALE_VERSION')
    assert CollectionAccountContext.objects.get(document=account).document_pending is True


def test_mcp_publishes_typed_deferral_and_filter_contracts(runtime):
    tools, _ = runtime
    by_name = {tool['name']: tool for tool in tools}
    create = by_name['create_collection_account']['input_schema']['properties']
    assert create['document_pending']['type'] == 'boolean'
    assert 'pending_by' not in create
    assert 'pending_at' not in create
    assert by_name['list_collection_accounts']['input_schema']['properties']['document_pending']['type'] == 'boolean'
