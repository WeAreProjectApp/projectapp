"""Regressions for annexes that preserve the original PDF sections."""
from io import BytesIO

import pytest
from django.utils import timezone
from freezegun import freeze_time
from pypdf import PdfReader

from content.models import ProposalSection
from content.services.formalization_content import FormalContent
from content.services.formalization_pdf import generate_formal_pdf
from content.services.proposal_pdf_service import ProposalPdfService, default_selected_modules_from_content
from content.services.technical_document_pdf import generate_technical_document_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def formal_proposal(proposal):
    sections = {
        'greeting': {'proposalTitle': 'Propuesta original'},
        'functional_requirements': {'groups': [{'id': 'core', 'title': 'Operación', 'items': [{'id': 'orders', 'name': 'Pedidos', 'description': 'Registrar pedidos.'}]}]},
        'investment': {'paymentOptions': [{'label': '100% al entregar', 'description': ''}], 'valueReasons': ['SALES_SENTINEL']},
        'technical_document': {'purpose': 'Gestionar pedidos', 'epics': [{'epicKey': 'OP', 'title': 'Operación', 'requirements': [{'flowKey': 'OP-01', 'title': 'Crear pedido', 'description': 'Conservar fecha.', 'linked_item_ids': ['orders']}]}], 'growthReadiness': {'strategies': [{'dimension': 'Carga', 'preparation': 'Índices', 'evolution': 'FUTURE_SENTINEL'}]}},
        'roi_projection': {'subtitle': 'ROI_SENTINEL'},
    }
    for order, (key, data) in enumerate(sections.items()):
        ProposalSection.objects.create(proposal=proposal, section_type=key, title=key, order=order, content_json=data)
    return proposal


def pdf_text(raw):
    return '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(raw)).pages)


def original_commercial_text(proposal):
    # Independent reference: the normal PDF with precisely the agreed six sections disabled.
    excluded = proposal.sections.filter(is_enabled=True, section_type__in=[
        'executive_summary', 'context_diagnostic', 'conversion_strategy',
        'roi_projection', 'final_note', 'next_steps',
    ])
    ids = list(excluded.values_list('pk', flat=True))
    excluded.update(is_enabled=False)
    try:
        return pdf_text(ProposalPdfService.generate(
            proposal, selected_modules=default_selected_modules_from_content(proposal),
        ))
    finally:
        proposal.sections.filter(pk__in=ids).update(is_enabled=True)


def render(proposal, kind='commercial'):
    return pdf_text(generate_formal_pdf(FormalContent(proposal), kind, timezone.now(), 'PROP-TEST'))


@pytest.mark.parametrize('section_type', [
    'executive_summary', 'context_diagnostic', 'conversion_strategy',
    'roi_projection', 'final_note', 'next_steps',
])
def test_commercial_annex_excludes_only_the_agreed_whole_sections(formal_proposal, section_type):
    formal_proposal.sections.update_or_create(
        section_type=section_type,
        defaults={'title': section_type, 'order': 20, 'content_json': {
            '_editMode': 'paste', 'rawText': 'EXCLUDED_SALES_SECTION',
        }},
    )
    original = pdf_text(ProposalPdfService.generate(formal_proposal))

    rendered = render(formal_proposal)

    assert 'EXCLUDED_SALES_SECTION' in original
    assert 'EXCLUDED_SALES_SECTION' not in rendered
    assert 'SALES_SENTINEL' in rendered  # Part of investment: no field-level curation.
    assert rendered == original_commercial_text(formal_proposal)


def test_commercial_annex_inherits_unselected_item_pricing(formal_proposal):
    requirements = formal_proposal.sections.get(section_type='functional_requirements')
    requirements.content_json['groups'][0]['items'].append({
        'id': 'campaigns', 'name': 'Módulo opcional',
        'description': 'OPTIONAL_SALES_SCOPE', 'price': '5000', 'is_required': False,
    })
    requirements.save(update_fields=['content_json'])

    rendered = render(formal_proposal)

    assert 'OPTIONAL_SALES_SCOPE' not in rendered
    assert '10.000' in rendered
    assert rendered == original_commercial_text(formal_proposal)


def test_technical_annex_preserves_original_legacy_requirement_content(formal_proposal):
    requirements = formal_proposal.sections.get(section_type='functional_requirements')
    del requirements.content_json['groups'][0]['items'][0]['id']
    requirements.save(update_fields=['content_json'])
    technical = formal_proposal.sections.get(section_type='technical_document')
    technical.content_json['epics'][0]['requirements'][0]['linked_item_ids'] = ['item-core-pedidos']
    technical.save(update_fields=['content_json'])

    rendered = render(formal_proposal, 'technical')

    assert 'Crear pedido' in rendered
    assert 'Conservar fecha.' in rendered
    assert rendered == pdf_text(generate_technical_document_pdf(formal_proposal))


@pytest.fixture
def module_terms_proposal(formal_proposal):
    requirements = formal_proposal.sections.get(section_type='functional_requirements')
    requirements.content_json['groups'].extend([
        {
            'id': 'priority-support',
            'title': 'Soporte prioritario',
            'is_calculator_module': True,
            'selected': True,
            'price_percent': 10,
            'items': [{'id': 'priority-channel', 'name': 'Canal prioritario', 'description': 'Soporte incluido.'}],
        },
        {
            'id': 'catalog-support',
            'title': 'Soporte de catálogo',
            'is_calculator_module': True,
            'selected': False,
            'price_percent': 5,
            'items': [{'id': 'catalog-channel', 'name': 'Canal catálogo', 'description': 'No seleccionado.'}],
        },
        {
            'id': 'threshold-support',
            'title': 'Soporte condicionado',
            'is_calculator_module': True,
            'selected': True,
            'price_percent': 1,
            'items': [{'id': 'threshold-channel', 'name': 'Canal condicionado', 'description': 'Umbral no alcanzado.'}],
        },
    ])
    requirements.save(update_fields=['content_json'])
    ProposalSection.objects.create(
        proposal=formal_proposal,
        section_type='value_added_modules',
        title='Módulos incluidos',
        order=10,
        content_json={
            'module_ids': ['priority-support', 'catalog-support', 'threshold-support'],
            'conditions': {
                'priority-support': {
                    'min_price_cop': 10000,
                    'duration_months': 12,
                    'discretionary_note': 'NOTA_DISCRECIONAL_ELEGIBLE',
                    'terms_clauses': [{'label': 'Cobertura', 'text': 'CLÁUSULA_ELEGIBLE'}],
                },
                'catalog-support': {
                    'min_price_cop': 0,
                    'terms_clauses': [{'label': 'Cobertura', 'text': 'TERMINO_NO_SELECCIONADO'}],
                },
                'threshold-support': {
                    'min_price_cop': 20000,
                    'terms_clauses': [{'label': 'Cobertura', 'text': 'TERMINO_BAJO_UMBRAL'}],
                },
            },
        },
    )
    return formal_proposal


@freeze_time('2026-09-19 12:00:00')
def test_commercial_annex_preserves_original_module_terms(module_terms_proposal):
    """Do not apply an annex-specific eligibility or rewriting policy."""
    formal_proposal = module_terms_proposal

    raw = generate_formal_pdf(FormalContent(formal_proposal), 'commercial', timezone.now(), 'PROP-TEST')
    rendered = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(raw)).pages)

    assert 'CLÁUSULA_ELEGIBLE' in rendered
    assert 'NOTA_DISCRECIONAL_ELEGIBLE' in rendered
    assert rendered == original_commercial_text(formal_proposal)


@freeze_time('2026-09-19 12:00:00')
def test_commercial_pdf_preserves_saved_hosting_options(formal_proposal):
    """Fails if the formal annex changes saved hosting prices or presents one option as selected."""
    formal_proposal.hosting_percent = 24
    formal_proposal.save(update_fields=['hosting_percent'])
    investment = formal_proposal.sections.get(section_type='investment')
    investment.content_json['hostingPlan'] = {
        'title': 'Hosting administrado',
        'freeMonths': 2,
        'freeMonthsVisible': True,
        'billingTiers': [
            {'label': 'Mensual', 'months': 1, 'discountPercent': 0},
            {'label': 'Trimestral', 'months': 3, 'discountPercent': 10},
        ],
    }
    investment.save(update_fields=['content_json'])

    raw = generate_formal_pdf(FormalContent(formal_proposal), 'commercial', timezone.now(), 'PROP-TEST')
    rendered = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(raw)).pages)

    assert 'Hosting administrado' in rendered
    assert 'Trimestral' in rendered
    assert rendered == original_commercial_text(formal_proposal)


def test_technical_annex_preserves_future_scope_as_original(formal_proposal):
    rendered = render(formal_proposal, 'technical')

    assert 'Crear pedido' in rendered
    assert 'Índices' in rendered
    assert 'FUTURE_SENTINEL' in rendered
    assert rendered == pdf_text(generate_technical_document_pdf(formal_proposal))


def test_commercial_annex_omits_a_disabled_retained_section(formal_proposal):
    formal_proposal.sections.filter(section_type='investment').update(is_enabled=False)

    rendered = render(formal_proposal)

    assert 'SALES_SENTINEL' not in rendered
    assert 'Pedidos' in rendered
    assert rendered == original_commercial_text(formal_proposal)
