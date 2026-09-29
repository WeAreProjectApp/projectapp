"""Markdown mirrors the text of the actual PDF without another projection."""
from datetime import datetime, timezone

import pytest

from content.models import ProposalSection
from content.services.formalization_content import FormalContent, FormalizationError
from content.services.formalization_markdown import generate_formal_markdown

pytestmark = pytest.mark.django_db


@pytest.fixture
def formal_markdown_proposal(proposal):
    proposal.language = 'en'
    proposal.save(update_fields=['language'])
    sections = {
        'functional_requirements': {
            'groups': [{
                'id': 'operations',
                'title': 'Operations',
                'items': [
                    {'id': 'orders', 'name': 'Orders', 'description': 'Record orders.'},
                    {
                        'id': 'optional-sales', 'name': 'Optional sales module',
                        'description': 'UNSELECTED_SENTINEL', 'price': '5000', 'is_required': False,
                    },
                ],
            }],
        },
        'investment': {
            'paymentOptions': [{'label': '100% on delivery', 'description': ''}],
            'valueReasons': ['SALES_SENTINEL'],
        },
        'technical_document': {
            'purpose': 'Manage orders',
            'epics': [{
                'epicKey': 'OPS', 'title': 'Operations',
                'requirements': [{
                    'flowKey': 'OPS-01', 'title': 'Create order',
                    'description': 'Keep a date.', 'linked_item_ids': ['orders'],
                }],
            }],
            'growthReadiness': {
                'strategies': [{
                    'dimension': 'Load', 'preparation': 'Indexes', 'evolution': 'FUTURE_SENTINEL',
                }],
            },
        },
        'roi_projection': {'subtitle': 'ROI_SENTINEL'},
    }
    for order, (section_type, content_json) in enumerate(sections.items()):
        ProposalSection.objects.create(
            proposal=proposal,
            section_type=section_type,
            title=section_type,
            order=order,
            content_json=content_json,
        )
    return proposal


def _export(proposal, kind):
    return generate_formal_markdown(
        FormalContent(proposal), kind, datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc), 'PROP-12',
    )


def test_commercial_markdown_keeps_text_inside_retained_sections(formal_markdown_proposal):
    export = _export(formal_markdown_proposal, 'commercial')

    assert export['title'] == 'Formal commercial proposal'
    assert 'Orders' in export['markdown']
    assert 'SALES\\_SENTINEL' in export['markdown']
    assert 'UNSELECTED' not in export['markdown']
    assert 'ROI' not in export['markdown']
    assert 'Texto extraído del PDF' in export['warnings'][0]


def test_technical_markdown_keeps_original_growth_information(formal_markdown_proposal):
    export = _export(formal_markdown_proposal, 'technical')

    assert export['title'] == 'Formal technical specification'
    assert 'Create order' in export['markdown']
    assert 'FUTURE\\_SENTINEL' in export['markdown']
    assert 'Indexes' in export['markdown']


def test_formal_markdown_rejects_unknown_document_kind(formal_markdown_proposal):
    with pytest.raises(FormalizationError, match='Tipo de documento inválido') as error:
        _export(formal_markdown_proposal, 'unsupported')

    assert error.value.code == 'invalid_document'


def test_formal_markdown_preserves_pasted_scope(formal_markdown_proposal):
    requirements = formal_markdown_proposal.sections.get(section_type='functional_requirements')
    requirements.content_json = {'_editMode': 'paste', 'rawText': 'Pasted scope reviewed by client.'}
    requirements.save(update_fields=['content_json'])

    rendered = _export(formal_markdown_proposal, 'commercial')['markdown']

    assert 'Pasted scope reviewed by client.' in rendered


def test_technical_markdown_accepts_original_scope_without_epics(formal_markdown_proposal):
    technical = formal_markdown_proposal.sections.get(section_type='technical_document')
    technical.content_json = {'purpose': 'Manage orders', 'epics': []}
    technical.save(update_fields=['content_json'])

    rendered = _export(formal_markdown_proposal, 'technical')['markdown']

    assert 'Manage orders' in rendered


@pytest.mark.parametrize('is_enabled', [False, True])
def test_technical_markdown_requires_an_available_technical_section(formal_markdown_proposal, is_enabled):
    formal_markdown_proposal.sections.filter(section_type='technical_document').update(is_enabled=is_enabled)
    formal_markdown_proposal.sections.filter(section_type='technical_document', is_enabled=True).delete()

    with pytest.raises(FormalizationError) as error:
        _export(formal_markdown_proposal, 'technical')

    assert error.value.code == 'technical_missing'
    assert error.value.status == 404


def test_commercial_markdown_preserves_saved_section_order(formal_markdown_proposal):
    scope = formal_markdown_proposal.sections.get(section_type='functional_requirements')
    scope.order = 10
    scope.title = 'Scope last'
    scope.save(update_fields=['order', 'title'])
    investment = formal_markdown_proposal.sections.get(section_type='investment')
    investment.order = 0
    investment.title = 'Investment first'
    investment.save(update_fields=['order', 'title'])

    rendered = _export(formal_markdown_proposal, 'commercial')['markdown']

    assert 'Scope last' in rendered
    assert rendered.index('Investment first') < rendered.index('Scope last')


def test_technical_markdown_preserves_original_environment_columns(formal_markdown_proposal):
    technical = formal_markdown_proposal.sections.get(section_type='technical_document')
    technical.content_json['environments'] = [{
        'name': 'Staging', 'purpose': 'Validation', 'whoAccesses': 'QA team',
        'url': 'staging.example.test', 'database': 'Application database',
        'credentials': 'NeverPrintedSecret',
    }]
    technical.save(update_fields=['content_json'])

    rendered = _export(formal_markdown_proposal, 'technical')['markdown']

    assert 'staging.example.test' in rendered
    assert 'Application database' in rendered
    assert 'QA team' in rendered
    assert 'NeverPrintedSecret' not in rendered
