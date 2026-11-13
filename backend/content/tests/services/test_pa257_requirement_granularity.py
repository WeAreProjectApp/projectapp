"""PA-257: focused bilingual two-step output, with opaque item ids."""
import copy
import json
from pathlib import Path

import pytest

from content.models import McpConnector
from content.services.module_requirements_catalog import seed_module_technical_requirements
from content.services.proposal_module_links import build_item_requirements_map
from content.services.proposal_service import build_proposal_from_json, apply_proposal_json_update
from content.services.section_content_schemas import validate_section_content


CORPUS = json.loads((Path(__file__).resolve().parents[4] / 'docs/fixtures/pa257-requirements.json').read_text())


@pytest.mark.parametrize('language', ['es', 'en'])
def test_lists_keep_independent_requirements_for_each_element(language):
    """Fails if an item loses any of its distinct requirements or its opaque id."""
    sample = CORPUS[language]
    original = copy.deepcopy(sample)
    sections = [{'section_type': 'functional_requirements', 'content_json': sample['functionalRequirements']}]

    document = seed_module_technical_requirements(sample['technicalDocument'], sections, language)
    mapped = build_item_requirements_map(document)

    expected = {'pa257-register': 2, 'pa257-login': 1, 'pa257-legal': 1, 'pa257-search': 2,
                'pa257-edit': 2, 'pa257-pwa-install': 2, 'pa257-pwa-splash': 1}
    assert {key: len(mapped[key]) for key in expected} == expected
    assert sample == original


@pytest.mark.parametrize('language', ['es', 'en'])
def test_existing_schemas_accept_multiple_requirements(language):
    sample = CORPUS[language]
    assert validate_section_content('functional_requirements', sample['functionalRequirements']) == []
    assert validate_section_content('technical_document', sample['technicalDocument']) == []


def test_projection_preserves_technical_format_without_aliasing_the_input():
    """Fails if the modal projection drops technical detail or shares mutable format data."""
    document = copy.deepcopy(CORPUS['es']['technicalDocument'])
    source = document['epics'][0]['requirements'][0]
    source['text_formats'] = {'/configuration': 'markdown_html_v1'}

    row = build_item_requirements_map(document)['pa257-register'][0]

    assert row['configuration'] == source['configuration']
    assert row['usageFlow'] == source['usageFlow']
    assert row['text_formats'] == source['text_formats']
    row['text_formats']['/configuration'] = 'plain'
    assert source['text_formats']['/configuration'] == 'markdown_html_v1'


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.django_db
def test_json_import_preserves_multiple_requirements_after_metadata_update(language):
    """Fails if import or an unrelated edit collapses a requirement list."""
    sample = copy.deepcopy(CORPUS[language])
    proposal, _ = build_proposal_from_json({
        'title': 'PA-257 corpus', 'client_name': 'Laboratorio ficticio',
        'language': language, 'sections': sample,
    })
    before = proposal.sections.get(section_type='technical_document').content_json

    apply_proposal_json_update(proposal, {'title': 'PA-257 renamed', 'sections': {}})

    persisted = proposal.sections.get(section_type='technical_document').content_json
    assert persisted == before
    assert len(build_item_requirements_map(persisted)['pa257-register']) == 2
    assert len(build_item_requirements_map(persisted)['pa257-pwa-install']) == 2


@pytest.mark.django_db
def test_commercial_mcp_reads_all_technical_requirements(api_client):
    """Exercise the canonical MCP transport, rather than infer it from the REST view."""
    proposal, _ = build_proposal_from_json({
        'title': 'PA-257 MCP', 'client_name': 'Laboratorio ficticio',
        'language': 'es', 'sections': copy.deepcopy(CORPUS['es']),
    })
    connector, _ = McpConnector.objects.update_or_create(
        slug='commercial', defaults={'name': 'Comercial', 'is_active': True, 'retired_at': None},
    )
    token = connector.generate_token()
    connector.credentials.filter(label='Default').update(catalog='canonical')

    response = api_client.post(f'/api/mcp/commercial/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'get_proposal', 'arguments': {'proposal_id': proposal.pk}},
    }, format='json')

    assert response.status_code == 200
    assert response.data['result']['isError'] is False
    result = json.loads(response.data['result']['content'][0]['text'])
    section = next(row for row in result['sections'] if row['section_type'] == 'technical_document')
    assert len(build_item_requirements_map(section['content_json'])['pa257-register']) == 2

