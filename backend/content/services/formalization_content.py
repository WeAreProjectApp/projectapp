"""Capture original proposal sections; the PDF renderers apply annex exclusions."""
from copy import deepcopy
from dataclasses import dataclass

from content.services.proposal_pdf_service import default_selected_modules_from_content
from content.services.proposal_pdf_sections import FORMAL_COMMERCIAL_SECTIONS


class FormalizationError(ValueError):
    def __init__(self, message, code='invalid_formalization', status=400):
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class PdfSection:
    section_type: str
    title: str
    order: int
    content_json: dict


class FormalContent:
    """Snapshot of the enabled source, without a second content/pricing policy."""

    def __init__(self, proposal):
        self.proposal = proposal
        self.sections = [
            PdfSection(sec.section_type, sec.title, sec.order, deepcopy(sec.content_json or {}))
            for sec in sorted(proposal.sections.all(), key=lambda section: section.order)
            if sec.is_enabled
        ]
        self.selected = default_selected_modules_from_content(proposal)

    def label(self, es, en):
        return en if self.proposal.language == 'en' else es

    def commercial(self):
        # Greeting and technical data support the shared cover/detail renderers;
        # they are not numbered commercial chapters.
        return [section for section in self.sections
                if section.section_type in FORMAL_COMMERCIAL_SECTIONS
                or section.section_type in ('greeting', 'technical_document')]

    def technical(self):
        # Match the public PDF's availability: an enabled technical section.
        for section in self.sections:
            if section.section_type == 'technical_document':
                return section.content_json
        raise FormalizationError('Completa y habilita el detalle técnico.', 'technical_missing', 404)


def formal_document_title(content, kind):
    if kind == 'commercial':
        return content.label('Propuesta comercial formal', 'Formal commercial proposal')
    if kind == 'technical':
        return content.label('Detalle técnico formal', 'Formal technical specification')
    raise FormalizationError('Tipo de documento inválido.', 'invalid_document')
