"""Formal output retains editorial metadata without changing frozen packages."""

from datetime import datetime, timezone
from io import BytesIO

import pytest
from pypdf import PdfReader

from content.models import ProposalSection
from content.services.formalization_content import FormalContent, FormalizationError
from content.services.formalization_pdf import generate_formal_pdf
from content.services.proposal_formalization_service import check_current, prepare
from content.tests.services import test_proposal_formalization_service as fixtures


pytestmark = pytest.mark.django_db

formalization_proposal = fixtures.formalization_proposal
formalization_payload = fixtures.formalization_payload

ISSUED_AT = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
EDITORIAL_TABLE = (
    '| Hito | Estado |\n'
    '| --- | --- |\n'
    '| Formalización | Lista |'
)


def pdf_text(pdf_bytes):
    return '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(pdf_bytes)).pages)


def stored_bytes(formal_file):
    with formal_file.file.open('rb') as frozen_file:
        return frozen_file.read()


def test_formal_commercial_pdf_projects_editorial_table_from_section_metadata(
    formalization_proposal,
):
    """Falla si el PDF comercial formal pierde la tabla cuando el formato vive sólo en metadatos de sección."""
    ProposalSection.objects.create(
        proposal=formalization_proposal,
        section_type='executive_summary',
        title='Resumen ejecutivo',
        order=10,
        content_json={'paragraphs': [EDITORIAL_TABLE], 'highlights': []},
        text_formats={'/content_json/paragraphs/0': 'markdown'},
    )

    rendered = pdf_text(generate_formal_pdf(
        FormalContent(formalization_proposal), 'commercial', ISSUED_AT, 'PROP-EDITORIAL',
    ))

    assert 'Hito' in rendered
    assert 'Formalización' in rendered
    assert '| Hito | Estado |' not in rendered


def test_formal_technical_pdf_projects_editorial_table_from_section_metadata(
    formalization_proposal,
):
    """Falla si el detalle técnico formal trata una tabla editorial como texto plano pese a su metadato."""
    technical = formalization_proposal.sections.get(section_type='technical_document')
    technical.content_json['epics'][0]['description'] = EDITORIAL_TABLE
    technical.text_formats = {'/content_json/epics/0/description': 'markdown'}
    technical.save(update_fields=['content_json', 'text_formats'])

    rendered = pdf_text(generate_formal_pdf(
        FormalContent(formalization_proposal), 'technical', ISSUED_AT, 'PROP-EDITORIAL',
    ))

    assert 'Hito' in rendered
    assert 'Formalización' in rendered
    assert '| Hito | Estado |' not in rendered


def test_metadata_only_change_invalidates_preparation_without_changing_frozen_files(
    formalization_proposal, admin_user, formalization_payload,
):
    """Falla si cambiar sólo formato permite enviar una revisión vieja o reescribe sus bytes ya revisados."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)
    frozen_file = preparation.files.get(key='commercial')
    original_hash = preparation.source_hash
    original_bytes = stored_bytes(frozen_file)
    technical = formalization_proposal.sections.get(section_type='technical_document')
    technical.text_formats = {'/content_json/purpose': 'markdown'}
    technical.save(update_fields=['text_formats'])

    with pytest.raises(FormalizationError) as error:
        check_current(preparation)

    preparation.refresh_from_db()
    frozen_file.refresh_from_db()
    assert error.value.code == 'stale_preparation'
    assert preparation.source_hash == original_hash
    assert stored_bytes(frozen_file) == original_bytes
