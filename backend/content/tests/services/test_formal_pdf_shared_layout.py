"""Annex parity with the original PDF layout, content and validation rules."""
from copy import deepcopy
from decimal import Decimal
from datetime import datetime, timezone
from io import BytesIO

import pytest
from freezegun import freeze_time
from pypdf import PdfReader

from content.models import ProposalSection
from content.services.formalization_content import FormalContent
from content.services.formalization_pdf import generate_formal_pdf
from content.services.proposal_pdf_service import ProposalPdfService
from content.services.technical_document_pdf import generate_technical_document_pdf
from content.tests.services import test_formalization_pdf as formal_fixtures

formal_proposal = formal_fixtures.formal_proposal
original_commercial_text = formal_fixtures.original_commercial_text
pytestmark = pytest.mark.django_db
ISSUED_AT = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed_issue_time():
    with freeze_time('2026-09-24 12:00:00'):
        yield


def pdf_text(raw):
    return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(raw)).pages)


def render(proposal, kind):
    return generate_formal_pdf(FormalContent(proposal), kind, ISSUED_AT, 'PROP-LAYOUT')


@pytest.mark.parametrize(('kind', 'public_renderer'), [
    ('commercial', ProposalPdfService.generate),
    ('technical', generate_technical_document_pdf),
])
def test_formal_pdf_reuses_public_booklet_covers(formal_proposal, kind, public_renderer):
    """Catches a return to an unrelated formal cover or missing branded back page."""
    public = PdfReader(BytesIO(public_renderer(formal_proposal)))

    formal = PdfReader(BytesIO(render(formal_proposal, kind)))

    assert formal.pages[0].get_contents().get_data() == public.pages[0].get_contents().get_data()
    assert formal.pages[-1].get_contents().get_data() == public.pages[-1].get_contents().get_data()
    assert 'PROP-LAYOUT' not in pdf_text(render(formal_proposal, kind))


def test_commercial_pdf_preserves_saved_section_order(formal_proposal):
    section = formal_proposal.sections.get(section_type='investment')
    scope = formal_proposal.sections.get(section_type='functional_requirements')
    scope.order = 10
    scope.save(update_fields=['order'])
    section.order = 0
    section.title = 'INVESTMENT_FIRST'
    section.save(update_fields=['order', 'title'])

    reader = PdfReader(BytesIO(render(formal_proposal, 'commercial')))
    toc = reader.pages[2].extract_text()

    assert toc.index('INVESTMENT_FIRST') < toc.index('functional_requirements')
    assert '01' in toc


def test_technical_annex_preserves_all_original_columns(formal_proposal):
    """Every column already visible in the original remains in the annex."""
    section = formal_proposal.sections.get(section_type='technical_document')
    section.content_json['environments'] = [{
        'name': 'Staging', 'purpose': 'Validación', 'whoAccesses': 'Equipo QA',
        'url': 'INTERNAL_URL', 'database': 'INTERNAL_DATABASE', 'credentials': 'SECRET_FIELD',
    }]
    section.content_json['integrations'] = {'excluded': [{
        'service': 'Servicio excluido', 'reason': 'Fuera de alcance', 'availability': 'FUTURE_AVAILABILITY',
    }]}
    section.save(update_fields=['content_json'])

    rendered = pdf_text(render(formal_proposal, 'technical'))

    assert 'Equipo QA' in rendered
    assert 'Fuera de alcance' in rendered
    assert 'INTERNAL_URL' in rendered
    assert 'INTERNAL_DATABASE' in rendered
    assert 'FUTURE_AVAILABILITY' in rendered
    assert 'SECRET_FIELD' not in rendered  # Not a printable field in the original either.
    assert rendered == pdf_text(generate_technical_document_pdf(formal_proposal))



def test_commercial_annex_uses_original_hosting_rules(formal_proposal):
    section = formal_proposal.sections.get(section_type='investment')
    section.content_json['hostingPlan'] = {'title': 'Hosting', 'monthlyPrice': 'SAVED_PRICE'}
    section.save(update_fields=['content_json'])

    rendered = pdf_text(render(formal_proposal, 'commercial'))

    assert 'Hosting' in rendered
    assert rendered == original_commercial_text(formal_proposal)


def test_commercial_annex_uses_original_payment_calculation(formal_proposal):
    """The annex cannot apply a separate rounding or payment interpretation."""
    formal_proposal.currency = 'USD'
    formal_proposal.language = 'en'
    formal_proposal.total_investment = Decimal('1000.25')
    formal_proposal.save(update_fields=['currency', 'language', 'total_investment'])
    section = formal_proposal.sections.get(section_type='investment')
    section.content_json['paymentOptions'] = [{'label': '12.5% upon kickoff', 'description': 'OLD_AMOUNT'}]
    section.save(update_fields=['content_json'])

    rendered = pdf_text(render(formal_proposal, 'commercial'))

    assert '12.5% upon kickoff' in rendered
    assert rendered == original_commercial_text(formal_proposal)


def test_technical_annex_uses_original_language_labels(formal_proposal):
    formal_proposal.language = 'en'
    formal_proposal.save(update_fields=['language'])

    rendered = pdf_text(render(formal_proposal, 'technical'))

    assert 'Crear pedido' in rendered
    assert rendered == pdf_text(generate_technical_document_pdf(formal_proposal))


@pytest.mark.parametrize('kind', ['commercial', 'technical'])
def test_formal_pdf_does_not_mutate_captured_sections(formal_proposal, kind):
    content = FormalContent(formal_proposal)
    original = deepcopy(content.sections)
    saved = list(formal_proposal.sections.values('content_json', 'title', 'order'))

    generate_formal_pdf(content, kind, ISSUED_AT, 'PROP-LAYOUT')

    assert content.sections == original
    assert list(formal_proposal.sections.values('content_json', 'title', 'order')) == saved


@pytest.mark.parametrize('kind', ['commercial', 'technical'])
def test_formal_pdf_inherits_original_long_requirement_layout(formal_proposal, kind):
    requirements = formal_proposal.sections.get(section_type='functional_requirements')
    requirements.content_json['groups'][0]['items'][0]['description'] = 'LONG_SCOPE ' * 1800 + 'END_OF_SCOPE'
    requirements.save(update_fields=['content_json'])
    technical = formal_proposal.sections.get(section_type='technical_document')
    technical.content_json['epics'][0]['requirements'][0]['description'] = 'LONG_SCOPE ' * 1800 + 'END_OF_SCOPE'
    technical.save(update_fields=['content_json'])

    original = {
        'commercial': lambda: original_commercial_text(formal_proposal),
        'technical': lambda: pdf_text(generate_technical_document_pdf(formal_proposal)),
    }[kind]()

    rendered = pdf_text(render(formal_proposal, kind))

    assert 'LONG_SCOPE' in rendered
    assert rendered == original


def test_formal_pdf_preserves_original_pasted_scope(formal_proposal):
    section = formal_proposal.sections.get(section_type='functional_requirements')
    section.content_json.update({'_editMode': 'paste', 'rawText': 'UNREVIEWED_CONTRACT'})
    section.save(update_fields=['content_json'])

    rendered = pdf_text(render(formal_proposal, 'commercial'))

    assert 'UNREVIEWED_CONTRACT' in rendered
    assert rendered == original_commercial_text(formal_proposal)


def test_formal_pdf_retains_concrete_design_services(formal_proposal):
    ProposalSection.objects.create(proposal=formal_proposal, section_type='design_ux', title='Design', order=6,
        content_json={'focusItems': ['INCLUDED_DESIGN'], 'objective': 'SALES_OBJECTIVE'})
    ProposalSection.objects.create(proposal=formal_proposal, section_type='creative_support', title='Support', order=7,
        content_json={'includes': ['INCLUDED_SUPPORT'], 'closing': 'SALES_CLOSING'})

    rendered = pdf_text(render(formal_proposal, 'commercial'))

    assert 'INCLUDED_DESIGN' in rendered
    assert 'INCLUDED_SUPPORT' in rendered
    assert 'SALES_OBJECTIVE' in rendered
    assert 'SALES_CLOSING' in rendered
    assert rendered == original_commercial_text(formal_proposal)


@pytest.fixture
def long_index_proposal(formal_proposal):
    extra = {
        'design_ux': {'focusItems': ['Diseño incluido']},
        'creative_support': {'includes': ['Soporte incluido']},
        'timeline': {'phases': [{'title': 'Entrega', 'description': 'Implementación'}]},
        'process_methodology': {'steps': [{'title': 'Revisión', 'description': 'Validación'}]},
        'commercial_conditions': {'scopeParagraphs': ['Control de cambios']},
    }
    for order, (kind, data) in enumerate(extra.items(), 4):
        ProposalSection.objects.create(proposal=formal_proposal, section_type=kind, title=kind, order=order, content_json=data)
    included = formal_proposal.sections.exclude(section_type__in=['technical_document', 'roi_projection', 'greeting']).order_by('order')
    for index, section in enumerate(included):
        section.title = f'Section{index} ' + 'W' * 240
        section.save(update_fields=['title'])
    return formal_proposal


def toc_destinations(reader):
    result = []
    for index, page in enumerate(reader.pages):
        for annotation in page.get('/Annots', []):
            destination = annotation.get_object().get('/Dest')
            if destination:
                target = next(p for p in reader.pages if p.indirect_reference == destination[0])
                result.append((index, target.extract_text()))
    return result


def test_formal_pdf_toc_links_follow_original_title_layout(long_index_proposal):
    reader = PdfReader(BytesIO(render(long_index_proposal, 'commercial')))

    destinations = toc_destinations(reader)

    assert {index for index, _ in destinations} == {2}
    assert len(destinations) == 7
    assert all(f'Section{index}' in text for index, (_, text) in enumerate(destinations))
