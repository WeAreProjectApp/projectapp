"""Requirement pricing and editorial notes coexist after catalog integration."""
from io import BytesIO
import re

import pytest
from pypdf import PdfReader

from content.models import HourPackage, ProposalSection
from content.services.requirement_package_service import seed_requirement_packages
from content.services.proposal_pdf_service import ProposalPdfService

pytestmark = pytest.mark.django_db
SOURCE = '<p><span style="color: #cc0000"><strong>EDITORIALNOTE</strong></span></p>'


@pytest.fixture
def rich_package():
    return HourPackage.objects.create(
        nationality='COL', pricing_model='requirements', name_es='Paquete', name_en='Package',
        xs_count=30, s_count=20, m_count=10, discount_percent=25,
        note_es=SOURCE, note_en=SOURCE,
        text_formats={'/note_es': 'markdown_html_v1', '/note_en': 'markdown_html_v1'},
    )


@pytest.mark.parametrize('language', ['es', 'en'])
def test_catalog_seed_retains_the_localized_note_format(rich_package, language):
    """Fails if seeding requirement commitments discards the catalog note's interpretation."""
    content = seed_requirement_packages({}, nationality='COL', language=language)

    assert content['packages'][0]['note'] == SOURCE
    assert content['packages'][0]['text_formats'] == {'/note': 'markdown_html_v1'}
    assert content['packages'][0]['totalPrice'] == '5700000'


def test_requirement_pdf_paints_the_catalog_note_color(proposal, rich_package):
    """Fails if the requirement table flattens a rich note during catalog reseeding."""
    ProposalSection.objects.create(
        proposal=proposal, section_type='commercial_conditions', title='Condiciones', order=1,
        content_json={'pricingModel': 'requirements', 'hourPackagesMode': 'auto'},
    )

    pdf = PdfReader(BytesIO(ProposalPdfService.generate(proposal)))
    text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    operations = b'\n'.join(page.get_contents().get_data() for page in pdf.pages)

    assert 'EDITORIALNOTE' in text
    assert re.search(rb'(?:0?\.8) 0 0 rg', operations)
