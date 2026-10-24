"""Formal annexes use the original PDF renderers without rewriting their inputs."""
from dataclasses import replace

from content.services.contract_variants import modality
from content.services.formalization_content import FormalizationError, formal_document_title
from content.services.editorial_format import render_source
from content.services.editorial_projection import EditorialSource, editorial_projection
from content.services.proposal_pdf_service import ProposalPdfService
from content.services.proposal_pdf_sections import FORMAL_TECHNICAL_SECTIONS
from content.services.technical_document_pdf import generate_technical_document_pdf


class _FrozenSections:
    """Small read-only queryset facade over a ``FormalContent`` snapshot."""

    def __init__(self, sections):
        self._sections = tuple(sections)

    def all(self):
        return list(self._sections)

    def filter(self, **criteria):
        def matches(section):
            for name, expected in criteria.items():
                if name == 'is_enabled':
                    if expected is not True:
                        return False
                elif getattr(section, name, None) != expected:
                    return False
            return True

        return _FrozenSections(
            section for section in self._sections if matches(section)
        )

    def first(self):
        return self._sections[0] if self._sections else None


class _FrozenProposal:
    """Delegate proposal fields while exposing only snapshotted sections."""

    def __init__(self, proposal, sections):
        self._proposal = proposal
        self.sections = _FrozenSections(sections)

    def __getattr__(self, name):
        return getattr(self._proposal, name)


def _materialize_editorial_html(value):
    """Keep formatting through legacy PDF helpers that call ``str.strip``."""
    if isinstance(value, EditorialSource):
        return render_source(value, format=value.format, strict=False)
    if isinstance(value, list):
        return [_materialize_editorial_html(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _materialize_editorial_html(item)
            for key, item in value.items()
        }
    return value


def _technical_snapshot(content):
    sections = []
    for section in content.sections:
        projected = editorial_projection(
            {'content_json': section.content_json},
            section.text_formats,
        )['content_json']
        sections.append(replace(
            section,
            content_json=_materialize_editorial_html(projected),
        ))
    return _FrozenProposal(content.proposal, sections)


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
            _technical_snapshot(content), selected_modules=content.selected,
            included_sections=FORMAL_TECHNICAL_SECTIONS,
        )
    if not result:
        raise FormalizationError('No se pudo generar el documento formal. Intenta nuevamente.', 'pdf_generation_failed', 500)
    return result
