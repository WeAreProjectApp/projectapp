"""Formal annexes use the original PDF renderers without rewriting their inputs."""
from content.services.contract_variants import modality
from content.services.formalization_content import FormalizationError, formal_document_title
from content.services.proposal_pdf_service import ProposalPdfService
from content.services.proposal_pdf_sections import FORMAL_TECHNICAL_SECTIONS
from content.services.technical_document_pdf import generate_technical_document_pdf


def generate_formal_pdf(content, kind, issued_at, reference):
    # Keep the delivery adapter's interface; issuance/reference belong to the
    # frozen package. The printed sections remain the ones the client reviewed.
    formal_document_title(content, kind)
    if kind == 'commercial':
        result = ProposalPdfService.generate(
            content.proposal,
            selected_modules=content.selected,
            sections_override=content.commercial(),
            include_hosting=modality(content.proposal) != 'split',
            include_value_reasons=False,
        )
    else:
        content.technical()
        result = generate_technical_document_pdf(
            content.proposal, selected_modules=content.selected,
            included_sections=FORMAL_TECHNICAL_SECTIONS,
        )
    if not result:
        raise FormalizationError('No se pudo generar el documento formal. Intenta nuevamente.', 'pdf_generation_failed', 500)
    return result
