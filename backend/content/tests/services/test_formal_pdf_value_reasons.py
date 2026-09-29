"""The formal commercial annex omits the investment rationale subsection."""
from datetime import datetime, timezone
from io import BytesIO

import pytest
from pypdf import PdfReader

from content.services.formalization_content import FormalContent
from content.services.formalization_pdf import generate_formal_pdf
from content.services.proposal_pdf_service import ProposalPdfService
from content.tests.services import test_formal_pdf_shared_layout as layout_fixtures
from content.tests.services import test_formalization_pdf as formal_fixtures

pytestmark = pytest.mark.django_db
formal_proposal = formal_fixtures.formal_proposal
long_index_proposal = layout_fixtures.long_index_proposal
ISSUED_AT = datetime(2026, 9, 29, tzinfo=timezone.utc)


def formal_pdf(proposal):
    return generate_formal_pdf(FormalContent(proposal), 'commercial', ISSUED_AT, 'VALUE-TEST')


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('contract_modality', ['single', 'split'])
def test_formal_commercial_pdf_omits_investment_rationale(formal_proposal, language, contract_modality):
    formal_proposal.language = language
    formal_proposal.contract_modality = contract_modality
    formal_proposal.save(update_fields=['language', 'contract_modality'])

    text = formal_fixtures.pdf_text(formal_pdf(formal_proposal))

    assert '¿Por qué esta inversión?' not in text
    assert 'Why this investment?' not in text
    assert 'SALES_SENTINEL' not in text
    assert '$15.000' in text
    assert '100% al entregar' in text


@pytest.mark.parametrize(('language', 'title'), [
    ('es', '¿Por qué esta inversión?'),
    ('en', 'Why this investment?'),
])
def test_public_pdf_keeps_investment_rationale(formal_proposal, language, title):
    formal_proposal.language = language
    formal_proposal.save(update_fields=['language'])

    text = formal_fixtures.pdf_text(ProposalPdfService.generate(formal_proposal))

    assert title in text
    assert 'SALES_SENTINEL' in text


def test_formal_pdf_omits_investment_rationale_after_index_repagination(long_index_proposal):
    reader = PdfReader(BytesIO(formal_pdf(long_index_proposal)))

    index_pages = [page for page in reader.pages if page.get('/Annots')]
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)

    assert len(index_pages) > 1
    assert '¿Por qué esta inversión?' not in text
    assert 'SALES_SENTINEL' not in text
    assert '100% al entregar' in text
