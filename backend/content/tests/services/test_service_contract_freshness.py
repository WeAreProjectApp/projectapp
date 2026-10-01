"""Freshness protects a reviewed service contract from changed service economics."""

import pytest
from django.core.files.base import ContentFile

from content.models import ProposalDocument, ProposalSection
from content.services.contract_pdf_service import resolve_contract_content
from content.services.formalization_content import FormalizationError
from content.services.proposal_formalization_service import contract_attachments
from content.services.service_contract_freshness import (
    service_contract_needs_regeneration,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def generated_service_contract(negotiating_proposal, contract_template):
    """Persist the real generated snapshot, as the production generator does."""
    proposal = negotiating_proposal
    proposal.contract_modality = 'split'
    proposal.hosting_percent = 10
    proposal.hosting_discount_nine_month = 40
    proposal.hosting_discount_semiannual = 20
    proposal.hosting_discount_quarterly = 10
    proposal.contract_params = {
        'contractor_full_name': 'ProjectApp S.A.S.',
        'contractor_nit': '900123456-7',
        'contractor_email': 'legal@projectapp.co',
        'contract_city': 'Medellín',
        'bank_name': 'Banco de Prueba',
        'bank_account_number': '123456789',
        'client_full_name': 'Acme Corp',
        'client_cedula': '1234567890',
        'client_email': 'contact@acme.com',
        'contract_date': '2026-09-29',
        'service_initial_term': 'doce (12) meses',
        'service_renewal_notice_days': 'treinta (30)',
        'service_termination_notice_days': 'treinta (30)',
    }
    proposal.save()
    ProposalSection.objects.create(
        proposal=proposal,
        section_type='investment',
        title='Inversión',
        order=1,
        content_json={'hostingPlan': {
            'title': 'Hosting administrado',
            'billingTiers': [
                {'frequency': 'nine_month', 'label': 'Cada 9 meses', 'months': 9},
                {'frequency': 'semiannual', 'label': 'Semestral', 'months': 6},
                {'frequency': 'quarterly', 'label': 'Trimestral', 'months': 3},
            ],
        }},
    )
    snapshot = resolve_contract_content(proposal, variant='service')['snapshot']
    document = ProposalDocument.objects.create(
        proposal=proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
        title='Contrato de servicio',
        is_generated=True,
        content_markdown=snapshot,
    )
    document.file.save('service.pdf', ContentFile(b'%PDF-1.4 reviewed'), save=True)
    return proposal, document


def test_generated_service_contract_is_current_for_its_real_snapshot(generated_service_contract):
    """Fails if an unmodified generated service contract is incorrectly marked for regeneration."""
    proposal, document = generated_service_contract

    assert service_contract_needs_regeneration(proposal, document) is False


def test_discount_change_makes_the_reviewed_service_contract_stale(generated_service_contract):
    """Fails if a changed hosting discount can be sent through a reviewed service contract."""
    proposal, document = generated_service_contract
    proposal.hosting_discount_semiannual = 25
    proposal.save(update_fields=['hosting_discount_semiannual'])

    assert service_contract_needs_regeneration(proposal, document) is True


def test_stale_service_contract_is_rejected_before_formalization_attachment(generated_service_contract):
    """Fails if a service contract with changed discount reaches a formalization package."""
    proposal, _document = generated_service_contract
    proposal.hosting_discount_quarterly = 15
    proposal.save(update_fields=['hosting_discount_quarterly'])

    with pytest.raises(FormalizationError) as error:
        contract_attachments(proposal, ['contract_service'])

    assert error.value.code == 'contract_stale'
    assert error.value.status == 409


def test_closed_proposal_keeps_its_historical_service_contract(generated_service_contract):
    """Fails if closing a deal marks its frozen service contract stale and rewrites history."""
    proposal, document = generated_service_contract
    proposal.status = 'accepted'
    proposal.save(update_fields=['status'])

    assert service_contract_needs_regeneration(proposal, document) is False
