"""Detect stale service contracts without rewriting stored or signed files."""

from content.models import BusinessProposal, ProposalDocument
from content.services.contract_pdf_service import resolve_contract_content
from content.services.contract_variants import SERVICE
from content.services.proposal_hosting_terms import ServiceConditionsError


def current_service_snapshot(proposal):
    if (proposal.status != BusinessProposal.Status.NEGOTIATING
            or proposal.contract_modality != BusinessProposal.ContractModality.SPLIT):
        return None
    try:
        return resolve_contract_content(proposal, variant=SERVICE)['snapshot']
    except ServiceConditionsError:
        return ''


def service_contract_needs_regeneration(proposal, document, *, expected_snapshot=None):
    if (proposal.status != BusinessProposal.Status.NEGOTIATING
            or proposal.contract_modality != BusinessProposal.ContractModality.SPLIT
            or document.document_type != ProposalDocument.DOC_TYPE_CONTRACT_SERVICE
            or not document.is_generated):
        return False
    expected = current_service_snapshot(proposal) if expected_snapshot is None else expected_snapshot
    return not expected or document.content_markdown != expected
