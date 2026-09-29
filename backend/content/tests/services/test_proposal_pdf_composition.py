"""Printed chapter order, numbering and navigation for proposal PDFs."""
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import re

import pytest
from pypdf import PdfReader

from content.models import ProposalSection
from content.services.formalization_content import FormalContent
from content.services.formalization_pdf import generate_formal_pdf
from content.services.proposal_pdf_service import ProposalPdfService
from content.services.technical_document_pdf import generate_technical_document_pdf

pytestmark = pytest.mark.django_db
ISSUED_AT = datetime(2026, 9, 29, tzinfo=timezone.utc)

PUBLIC_CHAPTERS = (
    'executive_summary', 'context_diagnostic', 'conversion_strategy',
    'roi_projection', 'design_ux', 'creative_support', 'process_methodology',
    'timeline', 'investment', 'functional_requirements', 'value_added_modules',
    'development_stages', 'final_note', 'next_steps', 'commercial_conditions',
)
FORMAL_CHAPTERS = (
    'executive_summary', 'conversion_strategy', 'design_ux', 'creative_support',
    'process_methodology', 'timeline', 'investment', 'functional_requirements',
    'value_added_modules', 'commercial_conditions',
)


@pytest.fixture
def all_chapters(proposal):
    for order, kind in enumerate(reversed(PUBLIC_CHAPTERS)):
        ProposalSection.objects.create(
            proposal=proposal, section_type=kind, title=kind, order=order,
            content_json={'index': '88', 'title': kind, '_editMode': 'paste',
                          'rawText': f'Original content for {kind}.'},
        )
    ProposalSection.objects.create(
        proposal=proposal, section_type='greeting', title='Presentation', order=50,
        content_json={'proposalTitle': 'Proposal under review'},
    )
    return proposal


def render_commercial(proposal, edition):
    if edition == 'public':
        return ProposalPdfService.generate(proposal, selected_modules=[])
    return generate_formal_pdf(FormalContent(proposal), 'commercial', ISSUED_AT, 'ORDER-TEST')


def toc_text(reader):
    return '\n'.join(page.extract_text() for page in reader.pages if page.get('/Annots'))


def printed_text(reader):
    return '\n'.join(page.extract_text() for page in reader.pages)


def numbered_titles(text):
    return re.findall(r'(?m)^(\d{2})\n([a-z_]+)\n', text)


@pytest.mark.parametrize(('edition', 'chapters'), [('public', PUBLIC_CHAPTERS), ('formal', FORMAL_CHAPTERS)])
def test_commercial_pdf_prints_agreed_chapter_sequence(all_chapters, edition, chapters):
    reader = PdfReader(BytesIO(render_commercial(all_chapters, edition)))

    headings = numbered_titles(printed_text(reader))

    expected = [(f'{index:02}', kind) for index, kind in enumerate(chapters, 1)]
    assert headings == expected + expected  # Index followed by the actual chapters.
    assert '88' not in toc_text(reader)


@pytest.mark.parametrize('edition', ['public', 'formal'])
def test_pdf_generation_leaves_web_section_data_untouched(all_chapters, edition):
    original = list(all_chapters.sections.values('order', 'title', 'content_json', 'is_enabled'))

    render_commercial(all_chapters, edition)

    assert list(all_chapters.sections.values('order', 'title', 'content_json', 'is_enabled')) == original


@pytest.mark.parametrize('edition', ['public', 'formal'])
def test_omitted_chapters_do_not_consume_numbers(all_chapters, edition):
    all_chapters.sections.filter(section_type='executive_summary').update(is_enabled=False)
    all_chapters.sections.filter(section_type='roi_projection').update(content_json={})
    all_chapters.sections.filter(section_type='value_added_modules').update(content_json={'module_ids': ['missing']})

    reader = PdfReader(BytesIO(render_commercial(all_chapters, edition)))

    titles = numbered_titles(toc_text(reader))
    assert [number for number, _ in titles] == [f'{index:02}' for index in range(1, len(titles) + 1)]
    assert {'executive_summary', 'roi_projection', 'value_added_modules'}.isdisjoint(kind for _, kind in titles)
    assert titles[-1][1] == 'commercial_conditions'


@pytest.mark.parametrize('with_greeting', [True, False])
def test_toc_links_reach_printed_chapters(all_chapters, with_greeting):
    all_chapters.sections.filter(section_type='greeting').update(is_enabled=with_greeting)
    reader = PdfReader(BytesIO(render_commercial(all_chapters, 'public')))

    destinations = [
        next(page for page in reader.pages if page.indirect_reference == annotation.get_object()['/Dest'][0])
        for source in reader.pages for annotation in source.get('/Annots', [])
    ]

    assert len(destinations) == 15
    assert all(f'Original content for {kind}.' in page.extract_text()
               for kind, page in zip(PUBLIC_CHAPTERS, destinations, strict=True))


def test_requirement_subsections_use_visible_group_numbers(proposal):
    ProposalSection.objects.create(
        proposal=proposal, section_type='functional_requirements', title='Requirements', order=15,
        content_json={'index': '99', 'groups': [
            {'id': 'empty', 'title': 'Empty', 'items': []},
            {'id': 'hidden', 'title': 'Hidden', 'is_visible': False, 'items': [{'name': 'Hidden item'}]},
            {'id': 'orders', 'title': 'Orders', 'items': [{'name': 'Record order', 'description': 'Keep the original date.'}]},
        ]},
    )

    reader = PdfReader(BytesIO(ProposalPdfService.generate(proposal)))

    text = printed_text(reader)
    assert '01.1\nOrders' in text
    assert '01.2' not in text
    assert '99.' not in text


@pytest.fixture
def technical_chapters(proposal):
    ProposalSection.objects.create(
        proposal=proposal, section_type='technical_document', title='Technical', order=17,
        content_json={
            'purpose': 'PURPOSE_SENTINEL',
            'stack': [{'layer': 'Backend', 'technology': 'Django', 'rationale': 'STACK_SENTINEL'}],
            'architecture': {'summary': 'ARCHITECTURE_SENTINEL'},
            'dataModel': {'summary': 'MODEL_SENTINEL', 'relationships': 'RELATIONSHIPS_SENTINEL',
                          'entities': [{'name': 'Order', 'description': 'ENTITY_SENTINEL', 'keyFields': 'order_date'}]},
            'growthReadiness': {'summary': 'GROWTH_SENTINEL'},
            'epics': [{'epicKey': 'ORD', 'title': 'Orders', 'requirements': [{
                'flowKey': 'ORD-01', 'title': 'Create order', 'description': 'DESCRIPTION_SENTINEL',
                'configuration': 'CONFIGURATION_SENTINEL', 'usageFlow': 'FLOW_SENTINEL',
            }]}],
            'apiSummary': 'API_SENTINEL',
            'integrations': {'included': [{'service': 'PAYMENTS_SENTINEL'}]},
            'environmentsNote': 'ENVIRONMENTS_SENTINEL',
            'security': [{'aspect': 'SECURITY_SENTINEL'}],
            'performanceQuality': {'practices': [{'strategy': 'PERFORMANCE_SENTINEL'}]},
            'backupsNote': 'BACKUPS_SENTINEL',
            'quality': {'criticalFlowsNote': 'QUALITY_SENTINEL'},
            'decisions': [{'decision': 'DECISIONS_SENTINEL'}],
        },
    )
    return proposal


@pytest.mark.parametrize('language', ['es', 'en'])
def test_formal_technical_pdf_keeps_only_three_original_chapters(technical_chapters, language):
    technical_chapters.language = language
    content = FormalContent(technical_chapters)
    original = deepcopy(content.sections)

    raw = generate_formal_pdf(content, 'technical', ISSUED_AT, 'TECH-TEST')

    reader = PdfReader(BytesIO(raw))
    text = printed_text(reader)
    assert re.findall(r'(?m)^(\d{2})\n([^\n]+)\n', toc_text(reader)) == [
        ('01', 'Stack tecnológico'), ('02', 'Modelo de datos'), ('03', 'Módulos del producto'),
    ]
    assert set(re.findall(r'[A-Z]+_SENTINEL', text)) == {
        'STACK_SENTINEL', 'MODEL_SENTINEL', 'RELATIONSHIPS_SENTINEL', 'ENTITY_SENTINEL',
        'DESCRIPTION_SENTINEL', 'CONFIGURATION_SENTINEL', 'FLOW_SENTINEL',
    }
    assert 'Integraciones' not in text
    assert content.sections == original


def test_public_technical_pdf_keeps_all_chapters(technical_chapters):
    reader = PdfReader(BytesIO(generate_technical_document_pdf(technical_chapters)))

    text = printed_text(reader)

    assert set(re.findall(r'[A-Z]+_SENTINEL', text)) == {
        'PURPOSE_SENTINEL', 'STACK_SENTINEL', 'ARCHITECTURE_SENTINEL', 'MODEL_SENTINEL',
        'RELATIONSHIPS_SENTINEL', 'ENTITY_SENTINEL', 'GROWTH_SENTINEL', 'DESCRIPTION_SENTINEL',
        'CONFIGURATION_SENTINEL', 'FLOW_SENTINEL', 'API_SENTINEL', 'PAYMENTS_SENTINEL',
        'ENVIRONMENTS_SENTINEL', 'SECURITY_SENTINEL', 'PERFORMANCE_SENTINEL', 'BACKUPS_SENTINEL',
        'QUALITY_SENTINEL', 'DECISIONS_SENTINEL',
    }
