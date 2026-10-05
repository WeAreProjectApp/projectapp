"""Atomic contract synchronization preserves accepted proposal snapshots."""
import pytest
from django.core.files.base import ContentFile
from content.models import ContractTemplateVersion, ProposalDocument
from content.services import contract_mirror_service, contract_template_service
from content.services.contract_template_service import read_template
from content.services.contract_template_validation import ContractTemplateError

pytestmark = pytest.mark.django_db

def _stored_file_bytes(document):
    document.file.open('rb')
    try:
        return document.file.read()
    finally:
        document.file.close()


def _mirror_snapshot(template):
    mirrors = {row.variant: row for row in template.mirrors.select_related('document')}
    return {
        key: {
            'markdown': read_template(key)['markdown'],
            'pdf': bytes(mirrors[key].pdf_content),
            'notes': mirrors[key].document.document_notes.count(),
        }
        for key in ('combined', 'product', 'service')
    }


def _fail_only_service(renderer):
    def render(template, variant):
        if variant == 'service':
            raise RuntimeError('El último PDF no se pudo generar.')
        return renderer(template, variant)

    return render


def test_last_variant_failure_reverts_all_three_template_changes(
    monkeypatch, initialized_contract_mirrors, superuser,
):
    """Falla si un PDF fallido en service deja versiones, PDFs o notas parciales en combined o product."""
    combined = read_template('combined')
    product = read_template('product')
    service = read_template('service')
    before = _mirror_snapshot(initialized_contract_mirrors)

    monkeypatch.setattr(
        contract_mirror_service, 'render_mirror_pdf',
        _fail_only_service(contract_mirror_service.render_mirror_pdf),
    )
    with pytest.raises(ContractTemplateError) as exc_info:
        contract_template_service.apply_update(
            {
                'variant': 'combined', 'markdown': combined['markdown'] + '\n',
                'if_match': combined['etag'], 'change_note': 'El lote debe revertirse completo.',
                'related_updates': [
                    {'variant': 'product', 'markdown': product['markdown'] + '\n', 'if_match': product['etag']},
                    {'variant': 'service', 'markdown': service['markdown'] + '\n', 'if_match': service['etag']},
                ],
            },
            actor=superuser,
        )

    assert exc_info.value.code == 'MIRROR_SYNC_FAILED'
    assert [
        read_template('combined')['markdown'],
        read_template('product')['markdown'],
        read_template('service')['markdown'],
    ] == [combined['markdown'], product['markdown'], service['markdown']]
    assert ContractTemplateVersion.objects.filter(template=initialized_contract_mirrors).count() == 3
    assert _mirror_snapshot(initialized_contract_mirrors) == before


def test_template_update_preserves_the_accepted_contract_artifact(
    initialized_contract_mirrors, superuser, accepted_proposal,
):
    """Falla si actualizar defaults reescribe el contrato, archivo o estado de una propuesta aceptada."""
    document = ProposalDocument.objects.create(
        proposal=accepted_proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        title='Contrato aceptado original',
        is_generated=True,
        content_markdown='# Contrato aceptado\n\nTexto contractual ya acordado.',
    )
    document.file.save('contrato-aceptado.pdf', ContentFile(b'%PDF-1.4 original contract bytes'), save=True)
    saved_markdown = document.content_markdown
    saved_bytes = _stored_file_bytes(document)
    combined = read_template('combined')

    contract_template_service.apply_update(
        {
            'variant': 'combined', 'markdown': combined['markdown'] + '\n',
            'if_match': combined['etag'], 'change_note': 'Sólo afecta contratos futuros.',
        },
        actor=superuser,
    )

    accepted_proposal.refresh_from_db()
    document.refresh_from_db()
    assert accepted_proposal.status == 'accepted'
    assert document.content_markdown == saved_markdown
    assert _stored_file_bytes(document) == saved_bytes
