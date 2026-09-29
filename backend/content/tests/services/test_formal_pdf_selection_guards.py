"""Guards for the formal PDF's frozen scope and preparation lifecycle."""
import hashlib
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time
from pypdf import PdfReader

from content.models import (
    ProposalFormalization,
    ProposalFormalizationFile,
    ProposalSection,
)
from content.services.formalization_content import FormalizationError
from content.services.proposal_pdf_service import ProposalPdfService, default_selected_modules_from_content
from content.services.technical_document_pdf import generate_technical_document_pdf
from content.services.proposal_email_service import ProposalEmailService
from content.services.proposal_formalization_service import (
    document_bytes,
    prepare,
    send_preparation,
    source_hash,
)
from content.tests.services import (
    test_proposal_formalization_service as service_fixtures,
)

pytestmark = pytest.mark.django_db
formalization_payload = service_fixtures.formalization_payload
formalization_proposal = service_fixtures.formalization_proposal


def _pdf_text(raw):
    return '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(raw)).pages)


@freeze_time('2026-09-24 12:00:00')
def test_formal_commercial_pdf_inherits_original_commercial_conditions(formalization_proposal):
    ProposalSection.objects.create(
        proposal=formalization_proposal, section_type='commercial_conditions',
        title='Condiciones comerciales', order=4,
        content_json={'hourPackagesMode': 'auto', 'scopeParagraphs': ['SAVED_SCOPE_CONDITION']},
    )
    original = _pdf_text(ProposalPdfService.generate(
        formalization_proposal,
        selected_modules=default_selected_modules_from_content(formalization_proposal),
    ))

    rendered = _pdf_text(document_bytes(formalization_proposal, 'commercial'))

    assert 'SAVED_SCOPE_CONDITION' in rendered
    assert rendered == original


@freeze_time('2026-09-24 12:00:00')
def test_formal_technical_pdf_excludes_unselected_module_requirement(
    formalization_proposal,
):
    """Fails if an optional module's technical requirement leaks into the formal PDF."""
    requirements = formalization_proposal.sections.get(section_type='functional_requirements')
    requirements.content_json['additionalModules'] = [{
        'id': 'priority-support',
        'title': 'Soporte prioritario',
        'is_calculator_module': True,
        'selected': False,
        'default_selected': False,
        'price_percent': 10,
        'items': [{
            'id': 'priority-channel',
            'name': 'Canal prioritario',
            'description': 'Soporte adicional.',
        }],
    }]
    requirements.save(update_fields=['content_json'])
    technical = formalization_proposal.sections.get(section_type='technical_document')
    technical.content_json['epics'][0]['requirements'].append({
        'flowKey': 'OPTIONAL_FLOW_99',
        'title': 'OPTIONAL_REQUIREMENT',
        'description': 'No pertenece al alcance confirmado.',
        'linked_module_ids': ['module-priority-support'],
    })
    technical.save(update_fields=['content_json'])

    rendered = _pdf_text(document_bytes(formalization_proposal, 'technical'))

    assert 'Crear pedido' in rendered
    assert 'Registra la orden.' in rendered
    assert rendered == _pdf_text(generate_technical_document_pdf(formalization_proposal))
    assert 'OPTIONAL_FLOW_99' not in rendered
    assert 'OPTIONAL_REQUIREMENT' not in rendered


@freeze_time('2026-09-24 12:00:00')
def test_send_rejects_a_preparation_after_its_section_title_changes(
    mailoutbox, formalization_proposal, admin_user, formalization_payload,
):
    """Fails if an edited formal section title can bypass stale-preparation review."""
    preparation = prepare(formalization_proposal, admin_user, formalization_payload)
    section = formalization_proposal.sections.get(section_type='investment')
    section.title = 'Inversión actualizada'
    section.save(update_fields=['title'])

    with pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    assert error.value.code == 'stale_preparation'
    assert error.value.status == 409
    assert len(mailoutbox) == 0


@freeze_time('2026-09-24 12:00:00')
def test_send_legacy_annex_requires_review_of_the_new_content(
    mailoutbox, formalization_proposal, admin_user, formalization_payload,
):
    """An old curated attachment must be reviewed again, never silently overwritten."""
    legacy_payload = {
        **formalization_payload,
        'documents': ['commercial'],
        'from_email': ProposalEmailService._get_from_email(),
    }
    preparation = ProposalFormalization.objects.create(
        proposal=formalization_proposal,
        created_by=admin_user,
        payload=legacy_payload,
        source_hash=source_hash(formalization_proposal, legacy_payload),
        html_body='<p>Legacy preview</p>',
        text_body='Legacy preview',
        expires_at=timezone.now() + timedelta(hours=1),
    )
    frozen_bytes = b'%PDF-legacy-frozen-commercial-bytes'
    attachment = ProposalFormalizationFile.objects.create(
        preparation=preparation,
        key='commercial',
        filename='legacy-commercial.pdf',
        description='Propuesta comercial formal',
        mime_type='application/pdf',
        sha256=hashlib.sha256(frozen_bytes).hexdigest(),
        size=len(frozen_bytes),
    )
    attachment.file.save(attachment.filename, ContentFile(frozen_bytes), save=True)
    with pytest.raises(FormalizationError) as error:
        send_preparation(preparation)

    assert error.value.code == 'stale_preparation'
    assert error.value.status == 409
    assert len(mailoutbox) == 0
    with attachment.file.open('rb') as stored:
        assert stored.read() == frozen_bytes
