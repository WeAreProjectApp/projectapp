"""MCP contract-modality changes share the panel confirmation and validation rules."""

import pytest
from django.core.files.base import ContentFile

from content.models import (
    McpActionIntent,
    McpConnector,
    ProposalContractSnapshot,
    ProposalDocument,
    ProposalSection,
)

pytestmark = pytest.mark.django_db

PARTY = {
    'client_full_name': 'MCP client', 'client_cedula': '1020304050', 'client_email': 'mcp@example.com',
    'contractor_full_name': 'Project App S.A.S.', 'contractor_nit': '900123456-7',
    'contractor_email': 'team@example.com', 'bank_name': 'Banco', 'bank_account_type': 'Ahorros',
    'bank_account_number': '123', 'contract_city': 'Medellín', 'contract_date': '2026-10-06',
}
TERMS = {
    'service_initial_term': 'doce meses', 'service_renewal_notice_days': 'treinta',
    'service_termination_notice_days': 'quince',
}


def _rpc(name, arguments):
    return {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}}


def _call(client, token, name, arguments):
    return client.post(f'/api/mcp/proposals/{token}/', _rpc(name, arguments), format='json').data['result']


def _pdf(_proposal, *, resolved_content, **_kwargs):
    return b'%PDF-1.4 mcp\n' + resolved_content['snapshot'].encode()


def _custom_combined(proposal, markdown, pdf):
    proposal.contract_params = {**PARTY, 'contract_source': 'custom', 'custom_contract_markdown': markdown}
    proposal.save(update_fields=['contract_params'])
    document = ProposalDocument.objects.create(
        proposal=proposal, document_type='contract', title='Signed', is_generated=True,
        content_markdown=markdown,
    )
    document.file.save('mcp-signed.pdf', ContentFile(pdf), save=True)
    return document


def _split_preview(client, token, proposal):
    return _call(client, token, 'update_proposal_contract_modality', {
        'proposal_id': proposal.pk, 'contract_modality': 'split',
        'change_note': 'Separate accepted agreement', 'contract_params': TERMS,
    })


@pytest.fixture
def mcp_access():
    connector, _ = McpConnector.objects.get_or_create(slug='proposals', defaults={'name': 'Proposals'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return token, connector.credential_for_token(token)


@pytest.fixture
def accepted_mcp_proposal(accepted_proposal, contract_template):
    contract_template.product_content_markdown = '# Product {client_full_name}'
    contract_template.save(update_fields=['product_content_markdown'])
    accepted_proposal.contract_params = dict(PARTY)
    accepted_proposal.save(update_fields=['contract_params'])
    ProposalSection.objects.create(
        proposal=accepted_proposal, section_type='investment', title='Investment', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Monthly', 'months': 1}]}},
    )
    return accepted_proposal


def test_modality_tool_schema_requires_flat_mode(api_client, mcp_access):
    """Fails if MCP discovery hides the required flat target mode behind an envelope or constraint."""
    token, _ = mcp_access
    tools = api_client.post(f'/api/mcp/proposals/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {},
    }, format='json').data['result']['tools']
    schema = next(row['inputSchema'] for row in tools if row['name'] == 'update_proposal_contract_modality')

    assert schema['properties']['change_note']['type'] == 'string'
    assert set(schema['properties']['contract_params']['properties']) == set(TERMS)
    assert schema['properties']['conflict_resolution']['enum'] == ['use_origin']
    assert schema['required'] == ['proposal_id', 'contract_modality']
    assert 'data' not in schema['properties']
    assert not {'anyOf', 'oneOf', 'allOf'} & schema.keys()
    assert schema['additionalProperties'] is False


def test_accepted_mcp_change_requires_confirmation_then_returns_variant_sources(
    api_client, mcp_access, accepted_mcp_proposal, monkeypatch,
):
    """Fails if MCP bypasses accepted-proposal confirmation or omits final source state per variant."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    token, _ = mcp_access
    markdown = '# MCP signed custom\n'
    pdf = b'%PDF-1.4 MCP signed bytes\x00'
    accepted_mcp_proposal.contract_params = {
        **PARTY, 'contract_source': 'custom', 'custom_contract_markdown': markdown,
    }
    accepted_mcp_proposal.save(update_fields=['contract_params'])
    combined = ProposalDocument.objects.create(
        proposal=accepted_mcp_proposal, document_type='contract', title='Signed', is_generated=True,
        content_markdown=markdown,
    )
    combined.file.save('mcp-signed.pdf', ContentFile(pdf), save=True)
    preview = _call(api_client, token, 'update_proposal_contract_modality', {
        'proposal_id': accepted_mcp_proposal.pk, 'contract_modality': 'split',
        'change_note': 'Separate accepted agreement', 'contract_params': TERMS,
    })

    confirmed = _call(api_client, token, 'confirm_action', {
        'confirmation_id': preview['structuredContent']['confirmation_id'],
    })

    contracts = confirmed['structuredContent']['result']['contract_change']['contracts']
    product = accepted_mcp_proposal.proposal_documents.get(document_type='contract_product', is_archived=False)
    assert preview['structuredContent']['confirmation_required'] is True
    assert {row['variant']: row['source'] for row in contracts} == {
        'combined': 'custom', 'product': 'custom', 'service': 'default',
    }
    assert product.content_markdown == markdown
    assert product.file.read() == pdf
    assert ProposalContractSnapshot.objects.filter(proposal=accepted_mcp_proposal).count() == 1


def test_reduced_mcp_scope_rejects_contract_modality_change(api_client, mcp_access, accepted_mcp_proposal):
    """Fails if a credential outside the proposal-change scope can alter contract modality through MCP."""
    token, credential = mcp_access
    credential.allowed_tools = ['list_proposals']
    credential.save(update_fields=['allowed_tools'])

    result = _call(api_client, token, 'update_proposal_contract_modality', {
        'proposal_id': accepted_mcp_proposal.pk, 'contract_modality': 'split',
        'change_note': 'Forbidden', 'contract_params': TERMS,
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'FORBIDDEN'


def test_mcp_lists_and_reads_immutable_snapshot_with_literal_markdown(
    api_client, mcp_access, accepted_mcp_proposal, monkeypatch,
):
    """Fails if MCP snapshot reads omit the exact custom contract evidence created by a confirmed change."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    token, _ = mcp_access
    markdown = '# Signed literal\n\nWhitespace stays  \n'
    _custom_combined(accepted_mcp_proposal, markdown, b'%PDF-1.4 signed')
    preview = _split_preview(api_client, token, accepted_mcp_proposal)
    _call(api_client, token, 'confirm_action', {'confirmation_id': preview['structuredContent']['confirmation_id']})
    snapshot = ProposalContractSnapshot.objects.get(proposal=accepted_mcp_proposal)

    listed = _call(api_client, token, 'list_proposal_contract_snapshots', {'proposal_id': accepted_mcp_proposal.pk})
    read = _call(api_client, token, 'read_proposal_contract_snapshot', {
        'proposal_id': accepted_mcp_proposal.pk, 'snapshot_id': str(snapshot.pk),
    })

    assert listed['isError'] is False
    assert listed['structuredContent']['total'] == 1
    assert listed['structuredContent']['snapshots'][0]['change_note'] == 'Separate accepted agreement'
    assert read['structuredContent']['payload']['documents'][0]['markdown'] == markdown
    assert read['structuredContent']['from_modality'] == 'single'


def test_mcp_restore_confirmation_recovers_signed_custom_contract(api_client, mcp_access, accepted_mcp_proposal, monkeypatch):
    """Fails if confirmed MCP restore cannot recover the custom signed contract preserved before splitting."""
    monkeypatch.setattr('content.services.contract_pdf_service.generate_contract_pdf', _pdf)
    token, _ = mcp_access
    markdown = '# Recover literally\n'
    pdf = b'%PDF-1.4 recover signed\x00'
    _custom_combined(accepted_mcp_proposal, markdown, pdf)
    split = _split_preview(api_client, token, accepted_mcp_proposal)
    _call(api_client, token, 'confirm_action', {'confirmation_id': split['structuredContent']['confirmation_id']})
    snapshot = ProposalContractSnapshot.objects.get(proposal=accepted_mcp_proposal, from_modality='single')

    preview = _call(api_client, token, 'restore_proposal_contract_snapshot', {
        'proposal_id': accepted_mcp_proposal.pk, 'snapshot_id': snapshot.pk, 'change_note': 'Restore signed text',
    })
    confirmed = _call(api_client, token, 'confirm_action', {
        'confirmation_id': preview['structuredContent']['confirmation_id'],
    })

    recovered = accepted_mcp_proposal.proposal_documents.get(document_type='contract', is_archived=False)
    assert preview['structuredContent']['confirmation_required'] is True
    assert confirmed['structuredContent']['result']['contract_change']['contract_modality'] == 'single'
    assert recovered.content_markdown == markdown
    assert recovered.file.read() == pdf
    assert ProposalContractSnapshot.objects.filter(proposal=accepted_mcp_proposal).count() == 2


def test_mcp_rejects_cross_proposal_snapshot_before_creating_an_intent(
    api_client, mcp_access, accepted_mcp_proposal, proposal,
):
    """Fails if MCP can preview a restore using another proposal's recovery evidence."""
    token, _ = mcp_access
    snapshot = ProposalContractSnapshot.objects.create(
        proposal=accepted_mcp_proposal, payload={}, actor_label='Admin', source='panel', change_note='original',
        from_modality='single', to_modality='split',
    )

    result = _call(api_client, token, 'restore_proposal_contract_snapshot', {
        'proposal_id': proposal.pk, 'snapshot_id': snapshot.pk, 'change_note': 'Wrong proposal',
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'NOT_FOUND'
    assert McpActionIntent.objects.count() == 0


@pytest.mark.parametrize('proposal_id', [True, -1])
def test_mcp_snapshot_list_rejects_invalid_proposal_identifier(api_client, mcp_access, proposal_id):
    """Fails if snapshot listing accepts a non-positive or boolean proposal identifier."""
    token, _ = mcp_access

    result = _call(api_client, token, 'list_proposal_contract_snapshots', {'proposal_id': proposal_id})

    assert result['isError'] is True


def test_mcp_snapshot_list_accepts_legacy_digit_string_identifier(api_client, mcp_access, accepted_mcp_proposal):
    """Fails if MCP rejects the digit-string proposal IDs supported by older connector clients."""
    token, _ = mcp_access

    result = _call(api_client, token, 'list_proposal_contract_snapshots', {
        'proposal_id': str(accepted_mcp_proposal.pk),
    })

    assert result['isError'] is False
