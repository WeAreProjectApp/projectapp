"""Transactional synchronization and generation invariants for contract templates."""
import pytest

from content.models import BusinessProposal, ContractTemplateVersion
from content.services import contract_template_service
from content.services.contract_template_service import read_template
from content.services.contract_template_validation import ContractTemplateError

pytestmark = pytest.mark.django_db


def test_invalid_pdf_reverts_the_template_update(monkeypatch, initialized_contract_mirrors, superuser):
    """Falla si un PDF fallido deja texto, historial o espejo actualizados a medias."""
    before = read_template('service')
    mirror = initialized_contract_mirrors.mirrors.get(variant='service')
    old_pdf = bytes(mirror.pdf_content)
    old_versions = ContractTemplateVersion.objects.filter(template=initialized_contract_mirrors, variant='service').count()

    def broken_pdf(*_args, **_kwargs):
        return b'El renderizador no produjo un PDF.'

    monkeypatch.setattr('content.services.contract_mirror_service.render_mirror_pdf', broken_pdf)
    with pytest.raises(ContractTemplateError) as exc_info:
        contract_template_service.apply_update(
            {
                'variant': 'service', 'markdown': before['markdown'] + '\n',
                'if_match': before['etag'], 'change_note': 'No debe persistir.',
            },
            actor=superuser,
        )

    initialized_contract_mirrors.refresh_from_db()
    mirror.refresh_from_db()
    assert exc_info.value.code == 'MIRROR_SYNC_FAILED'
    assert read_template('service')['markdown'] == before['markdown']
    assert ContractTemplateVersion.objects.filter(template=initialized_contract_mirrors, variant='service').count() == old_versions
    assert bytes(mirror.pdf_content) == old_pdf
    assert mirror.document.document_notes.filter(title__contains='Plantilla de servicio — versión 2').count() == 0


def test_template_update_keeps_existing_proposal_contract_params_unchanged(
    initialized_contract_mirrors, superuser,
):
    """Falla si editar una plantilla predeterminada reescribe contratos ya guardados en propuestas."""
    proposal = BusinessProposal.objects.create(
        title='Contrato ya negociado', client_name='Cliente existente',
        contract_params={'contract_source': 'custom', 'custom_contract_markdown': '# Contrato guardado'},
    )
    before = read_template('combined')

    contract_template_service.apply_update(
        {
            'variant': 'combined', 'markdown': before['markdown'] + '\n',
            'if_match': before['etag'], 'change_note': 'Sólo para contratos nuevos.',
        },
        actor=superuser,
    )

    proposal.refresh_from_db()
    assert proposal.contract_params == {
        'contract_source': 'custom', 'custom_contract_markdown': '# Contrato guardado',
    }
    assert read_template('combined')['version'] == 2


def test_private_note_failure_reverts_the_template_update(monkeypatch, initialized_contract_mirrors, superuser):
    """Falla si una nota privada rechazada conserva la revisión o el PDF nuevos."""
    before = read_template('service')
    mirror = initialized_contract_mirrors.mirrors.get(variant='service')
    old_pdf = bytes(mirror.pdf_content)

    def rejected_note(*args, **kwargs):
        raise RuntimeError('La nota no se pudo guardar.')

    monkeypatch.setattr('content.services.document_note_service.create_note', rejected_note)
    with pytest.raises(ContractTemplateError) as exc_info:
        contract_template_service.apply_update(
            {'variant': 'service', 'markdown': before['markdown'] + '\n',
             'if_match': before['etag'], 'change_note': 'Debe revertirse si falta la nota.'},
            actor=superuser,
        )

    mirror.refresh_from_db()
    assert exc_info.value.details == {
        'variant': 'service', 'document_id': mirror.document_id, 'stage': 'private_note', 'applied': False,
    }
    assert read_template('service')['version'] == 1
    assert read_template('service')['markdown'] == before['markdown']
    assert bytes(mirror.pdf_content) == old_pdf
