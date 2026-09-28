"""Normalized and legacy service terms at the contract-update boundary."""
from importlib import import_module

import pytest
from django.urls import reverse

from content.models import ProposalDocument

pytestmark = pytest.mark.django_db

PARTY_PARAMS = {
    'contract_source': 'default',
    'client_full_name': 'Cliente de prueba',
    'client_cedula': '1020304050',
    'client_email': 'cliente@example.com',
    'contractor_full_name': 'Project App S.A.S.',
    'contractor_nit': '900123456-7',
    'contractor_email': 'legal@example.com',
    'bank_name': 'Banco de Prueba',
    'bank_account_type': 'Ahorros',
    'bank_account_number': '123456789',
    'contract_city': 'Medellín',
    'contract_date': '2026-09-27',
}
LEGACY_TERMS = {
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'quince (15)',
    'service_termination_notice_days': 'treinta (30)',
}


@pytest.fixture
def service_proposal(negotiating_proposal, contract_template):
    negotiating_proposal.contract_modality = 'split'
    negotiating_proposal.contract_params = {**PARTY_PARAMS, **LEGACY_TERMS}
    negotiating_proposal.save(update_fields=['contract_modality', 'contract_params'])
    return negotiating_proposal


def _update_url(proposal):
    return reverse('update-contract-params', kwargs={'proposal_id': proposal.pk})


def _service_payload(terms):
    return {'contract_params': terms, 'variant': 'service'}


@pytest.mark.parametrize(
    ('numeric_terms', 'stored_terms', 'rendered_duration'),
    [
        (
            {
                'service_initial_term': 1,
                'service_renewal_notice_days': 21,
                'service_termination_notice_days': 100,
            },
            {
                'service_initial_term': 'un (1) mes',
                'service_renewal_notice_days': 'veintiún (21)',
                'service_termination_notice_days': 'cien (100)',
            },
            'un (1) mes',
        ),
        (
            {
                'service_initial_term': 999,
                'service_renewal_notice_days': 30,
                'service_termination_notice_days': 90,
            },
            {
                'service_initial_term': 'novecientos noventa y nueve (999) meses',
                'service_renewal_notice_days': 'treinta (30)',
                'service_termination_notice_days': 'noventa (90)',
            },
            'novecientos noventa y nueve (999) meses',
        ),
    ],
)
def test_numeric_terms_render_contractual_spanish_in_document(
    admin_client, service_proposal, numeric_terms, stored_terms, rendered_duration,
):
    """Fails if numeric selections reach the service contract as bare numbers or wrong Spanish."""
    response = admin_client.patch(
        _update_url(service_proposal), _service_payload(numeric_terms), format='json',
    )
    service_proposal.refresh_from_db()
    document = ProposalDocument.objects.get(
        proposal=service_proposal, document_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
    )

    assert response.status_code == 200
    for key, value in stored_terms.items():
        assert service_proposal.contract_params[key] == value
    assert f'por {rendered_duration}.' in document.content_markdown


def test_legacy_service_term_text_is_preserved_exactly_when_editing_the_contract(
    admin_client, service_proposal,
):
    """Fails if the rollout rewrites historical contractual wording during an edit."""
    legacy_terms = {
        'service_initial_term': 'doce (12) meses',
        'service_renewal_notice_days': '  quince (15)  ',
        'service_termination_notice_days': 'treinta (30) días calendario',
    }

    response = admin_client.patch(
        _update_url(service_proposal), _service_payload(legacy_terms), format='json',
    )
    service_proposal.refresh_from_db()

    assert response.status_code == 200
    for key, value in legacy_terms.items():
        assert service_proposal.contract_params[key] == value


@pytest.mark.parametrize('term_key', sorted(LEGACY_TERMS))
@pytest.mark.parametrize('invalid_value', [-1, 0, 1000, 1.5, True])
def test_invalid_numeric_service_term_is_rejected_without_changing_proposal(
    admin_client, service_proposal, term_key, invalid_value,
):
    """Fails if invalid numeric service-term input corrupts a proposal before a contract is generated."""
    before = dict(service_proposal.contract_params)
    payload_terms = {**LEGACY_TERMS, term_key: invalid_value}

    response = admin_client.patch(
        _update_url(service_proposal), _service_payload(payload_terms), format='json',
    )
    service_proposal.refresh_from_db()

    assert response.status_code == 400
    assert term_key in response.data
    assert service_proposal.contract_params == before


@pytest.mark.parametrize(
    ('term_key', 'wording'),
    [
        ('service_initial_term', 'dieciocho (18) meses iniciales'),
        ('service_renewal_notice_days', 'cuarenta y cinco (45)'),
        ('service_termination_notice_days', 'setenta y cinco (75)'),
    ],
)
def test_custom_wording_round_trips_through_contract_detail(
    admin_client, service_proposal, contract_template, term_key, wording,
):
    """Fails if free text is lost between saving, reloading and generating the contract."""
    # The shared minimal fixture omits both notices; use the shipped template
    # to exercise their actual insertion into the generated document.
    contract_template.service_content_markdown = import_module(
        'content.migrations.0266_seed_service_contract_text',
    ).SERVICE_CONTRACT_MARKDOWN
    contract_template.save(update_fields=['service_content_markdown'])
    response = admin_client.patch(
        _update_url(service_proposal),
        _service_payload({term_key: wording}), format='json',
    )

    detail = admin_client.get(
        reverse('retrieve-proposal', kwargs={'proposal_id': service_proposal.pk}),
    )
    document = ProposalDocument.objects.get(
        proposal=service_proposal, document_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
    )

    assert response.status_code == 200
    assert detail.data['contract_params'][term_key] == wording
    assert wording in document.content_markdown


@pytest.mark.parametrize('term_key', sorted(LEGACY_TERMS))
@pytest.mark.parametrize('invalid_text', ['   ', 'a' * 101])
def test_invalid_text_is_rejected_without_overwriting_saved_terms(
    admin_client, service_proposal, term_key, invalid_text,
):
    """Fails if a blank or overlong custom draft replaces the last saved contract."""
    before = dict(service_proposal.contract_params)

    response = admin_client.patch(
        _update_url(service_proposal),
        _service_payload({term_key: invalid_text}), format='json',
    )
    service_proposal.refresh_from_db()

    assert response.status_code == 400
    assert term_key in response.data
    assert service_proposal.contract_params == before
