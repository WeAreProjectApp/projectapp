"""Service-contract economics are rendered from the negotiated proposal."""

import pytest

from content.models import ProposalSection
from content.services.contract_pdf_service import resolve_contract_content
from content.services.proposal_hosting_terms import (
    SERVICE_CONDITIONS_END,
    SERVICE_CONDITIONS_HEADING,
    ServiceConditionsError,
    service_conditions_markdown,
)

pytestmark = pytest.mark.django_db


SERVICE_PARAMS = {
    'contractor_full_name': 'ProjectApp S.A.S.',
    'contractor_nit': '900123456-7',
    'client_full_name': 'Acme Corp',
    'client_cedula': '1234567890',
    'contract_date': '2026-09-29',
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'treinta (30)',
}


@pytest.fixture
def service_proposal(negotiating_proposal):
    """A negotiated deal with the three current payment alternatives."""
    negotiating_proposal.contract_modality = 'split'
    negotiating_proposal.contract_params = SERVICE_PARAMS
    negotiating_proposal.hosting_percent = 12
    negotiating_proposal.hosting_discount_nine_month = 40
    negotiating_proposal.hosting_discount_semiannual = 20
    negotiating_proposal.hosting_discount_quarterly = 10
    negotiating_proposal.save()
    ProposalSection.objects.create(
        proposal=negotiating_proposal,
        section_type='investment',
        title='Inversión',
        order=1,
        content_json={
            'hostingPlan': {
                'title': 'Hosting administrado',
                'description': 'Infraestructura, mantenimiento y soporte.',
                'specs': [{'label': 'Almacenamiento', 'value': '120 GB SSD'}],
                'coverageNote': 'Incluye monitoreo continuo.',
                'freeMonthsVisible': True,
                'freeMonthNote': 'Primer mes sin costo.',
                'renewalNote': 'RENOVACION_SENTINEL',
                'billingTiers': [
                    {'frequency': 'nine_month', 'label': 'Cada 9 meses', 'months': 9},
                    {'frequency': 'semiannual', 'label': 'Semestral', 'months': 6},
                    {'frequency': 'quarterly', 'label': 'Trimestral', 'months': 3},
                ],
            },
        },
    )
    return negotiating_proposal


def test_service_conditions_render_hosting_metadata(service_proposal):
    """Fails if the service contract loses its configured hosting description or renewal terms."""
    markdown = service_conditions_markdown(service_proposal)

    assert 'Hosting administrado' in markdown
    assert 'Infraestructura, mantenimiento y soporte.' in markdown
    assert '120 GB SSD' in markdown
    assert 'Incluye monitoreo continuo.' in markdown
    assert 'Primer mes sin costo.' in markdown
    assert 'RENOVACION\\_SENTINEL' in markdown
    assert 'ninguna modalidad se considera seleccionada' in markdown


@pytest.mark.parametrize(
    ('cadence', 'discount', 'monthly_price', 'period_total'),
    [
        ('Cada 9 meses', '40%', '$108 COP + IVA', '$972 COP + IVA'),
        ('Semestral', '20%', '$144 COP + IVA', '$864 COP + IVA'),
        ('Trimestral', '10%', '$162 COP + IVA', '$486 COP + IVA'),
    ],
)
def test_service_conditions_render_configured_price_tier(
    service_proposal, cadence, discount, monthly_price, period_total,
):
    """Fails if a configured service cadence loses its exact discount or economic amount."""
    markdown = service_conditions_markdown(service_proposal)

    assert cadence in markdown
    assert discount in markdown
    assert monthly_price in markdown
    assert period_total in markdown


def test_service_conditions_reject_missing_hosting_price(service_proposal):
    """Fails if an incomplete proposal can create a service contract without any service price."""
    service_proposal.total_investment = 0
    service_proposal.save(update_fields=['total_investment'])

    with pytest.raises(ServiceConditionsError, match='Completa la inversión'):
        service_conditions_markdown(service_proposal)


def test_custom_service_contract_replaces_the_prior_generated_conditions_once(service_proposal, contract_template):
    """Fails if regenerating a custom service contract duplicates its automatic economic conditions."""
    service_proposal.contract_params = {
        **SERVICE_PARAMS,
        'service_contract_source': 'custom',
        'service_custom_contract_markdown': (
            '# Texto negociado\n\n'
            f'{SERVICE_CONDITIONS_HEADING}\n\nCondición antigua\n\n{SERVICE_CONDITIONS_END}'
        ),
    }
    service_proposal.save(update_fields=['contract_params'])

    content = resolve_contract_content(service_proposal, variant='service')

    assert content['source'] == 'custom'
    assert content['markdown'].count(SERVICE_CONDITIONS_HEADING) == 1
    assert 'Texto negociado' in content['markdown']
    assert 'Condición antigua' not in content['markdown']
    assert 'Cada 9 meses' in content['markdown']


def test_default_service_contract_inserts_automatic_conditions_once(service_proposal, contract_template):
    """Fails if a default service contract misses or repeats the negotiated economic block."""
    content = resolve_contract_content(service_proposal, variant='service')

    assert content['source'] == 'default'
    assert content['markdown'].count(SERVICE_CONDITIONS_HEADING) == 1
    assert content['markdown'].count(SERVICE_CONDITIONS_END) == 1
    assert 'Incluye monitoreo continuo.' in content['markdown']
    assert 'Primer mes sin costo.' in content['markdown']
