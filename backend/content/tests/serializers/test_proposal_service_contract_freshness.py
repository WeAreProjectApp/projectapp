"""Admin document rows expose service-contract regeneration state."""

import pytest
from django.core.files.base import ContentFile

from content.models import ProposalDocument, ProposalSection
from content.serializers.proposal import serialize_proposal_document
from content.services.contract_pdf_service import resolve_contract_content

pytestmark = pytest.mark.django_db


@pytest.fixture
def service_document(negotiating_proposal, contract_template):
    """A persisted service snapshot created from the same source the panel uses."""
    proposal = negotiating_proposal
    proposal.contract_modality = 'split'
    proposal.hosting_percent = 10
    proposal.hosting_discount_nine_month = 40
    proposal.contract_params = {
        'contractor_full_name': 'ProjectApp S.A.S.', 'contractor_nit': '900123456-7',
        'client_full_name': 'Acme Corp', 'client_cedula': '1234567890',
        'service_initial_term': 'doce (12) meses',
        'service_renewal_notice_days': 'treinta (30)',
        'service_termination_notice_days': 'treinta (30)',
    }
    proposal.save()
    ProposalSection.objects.create(
        proposal=proposal, section_type='investment', title='Inversión', order=1,
        content_json={'hostingPlan': {'billingTiers': [{'label': 'Cada 9 meses', 'months': 9}]}},
    )
    document = ProposalDocument.objects.create(
        proposal=proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT_SERVICE,
        title='Contrato de servicio',
        is_generated=True,
        content_markdown=resolve_contract_content(proposal, variant='service')['snapshot'],
    )
    document.file.save('service.pdf', ContentFile(b'%PDF-1.4 reviewed'), save=True)

    return proposal, document


def test_service_document_serializer_marks_current_snapshot_fresh(service_document):
    """Fails if a generated service document prompts regeneration before its terms change."""
    proposal, document = service_document

    data = serialize_proposal_document(document, proposal=proposal)

    assert data['needs_regeneration'] is False


def test_service_document_serializer_reports_stale_economic_conditions(service_document):
    """Fails if the documents tab hides that a changed service discount requires regeneration."""
    proposal, document = service_document
    proposal.hosting_discount_nine_month = 35
    proposal.save(update_fields=['hosting_discount_nine_month'])

    data = serialize_proposal_document(document, proposal=proposal)

    assert data['needs_regeneration'] is True


def test_non_service_document_serializer_never_sets_regeneration_flag(service_document):
    """Fails if unrelated proposal documents inherit the service-contract freshness warning."""
    proposal, _service = service_document
    other = ProposalDocument.objects.create(
        proposal=proposal,
        document_type=ProposalDocument.DOC_TYPE_LEGAL_ANNEX,
        title='Anexo legal',
        is_generated=True,
    )
    other.file.save('annex.pdf', ContentFile(b'%PDF-1.4 annex'), save=True)

    data = serialize_proposal_document(other, proposal=proposal)

    assert data['needs_regeneration'] is False
