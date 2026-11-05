"""Canonical MCP access for the cross-module data-integrity service."""
import json

import pytest
from django.utils import timezone

from content.models import DataIntegrityFinding, DataIntegrityScan, McpConnector

pytestmark = pytest.mark.django_db


def _rpc(name, arguments):
    return {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }


def _call(api_client, slug, token, name, arguments):
    response = api_client.post(f'/api/mcp/{slug}/{token}/', _rpc(name, arguments), format='json')
    return json.loads(response.data['result']['content'][0]['text'])


@pytest.fixture
def integrity_token():
    connector, _ = McpConnector.objects.update_or_create(
        slug='data-integrity', defaults={'name': 'Integridad de datos', 'is_active': True},
    )
    connector.credentials.all().delete()
    return connector.generate_token()


def _stored_finding():
    scan = DataIntegrityScan.objects.create(
        request_id='mcp-review-scan', scope={'kind': 'all', 'id': None}, filters={},
        source='panel', catalog_version='1.2.0', status='completed',
    )
    return DataIntegrityFinding.objects.create(
        fingerprint='e' * 64, rule_id='DC11', domain='documents', severity='medium',
        payload={'title': 'Documento sin carpeta'}, last_seen_at=timezone.now(), last_scan=scan,
    )


def test_integrity_connector_exposes_durable_review_tools(api_client, integrity_token):
    """Fails if the standalone integrity connector omits durable scans or the protected review operation."""
    response = api_client.post(
        f'/api/mcp/data-integrity/{integrity_token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json',
    )
    tools = {tool['name']: tool for tool in response.data['result']['tools']}

    assert {'start_integrity_scan', 'get_integrity_scan', 'review_integrity_finding'} <= set(tools)
    assert (tools['review_integrity_finding']['annotations']['readOnlyHint'],
            tools['review_integrity_finding']['annotations']['destructiveHint']) == (False, False)


def test_integrity_review_waits_for_mcp_confirmation(api_client, integrity_token):
    """Fails if MCP accepts an integrity finding before the user confirms its recorded reason."""
    finding = _stored_finding()
    pending = _call(api_client, 'data-integrity', integrity_token, 'review_integrity_finding', {
        'fingerprint': finding.fingerprint, 'action': 'accept',
        'reason': 'Caso intencional', 'request_id': 'mcp-review',
    })

    confirmed = _call(api_client, 'data-integrity', integrity_token, 'confirm_action', {
        'confirmation_id': pending['confirmation_id'],
    })

    finding.refresh_from_db()
    assert pending['confirmation_required'] is True
    assert finding.is_accepted is True
    assert confirmed['result']['action'] == 'accept'


def test_new_projects_primary_credential_hides_integrity_tools(api_client):
    """Fails if a new Projects primary credential still discovers data-integrity operations after the split."""
    connector, _ = McpConnector.objects.update_or_create(
        slug='projects', defaults={'name': 'Proyectos', 'is_active': True},
    )
    connector.credentials.all().delete()
    token = connector.generate_token()

    listed = api_client.post(
        f'/api/mcp/projects/{token}/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json',
    )
    rejected = api_client.post(
        f'/api/mcp/projects/{token}/', _rpc('list_integrity_findings', {}), format='json',
    )

    assert 'list_integrity_findings' not in {tool['name'] for tool in listed.data['result']['tools']}
    assert rejected.data['error']['code'] == -32602
