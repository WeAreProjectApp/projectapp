"""Document-manager adapter rules shared by the two program contracts."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import reverse

from content.models import BuildingOnDemandContractMirror, BuildingWithUsContractMirror
from content.services import (
    building_on_demand_contract_service as cell_service,
    building_with_us_contract_service as alliance_service,
)
from content.services.contract_mirror_service import module_contract_mirror
from content.services.document_write_service import document_etag
from content.services.module_contract_document_service import (
    ModuleContractDocumentError,
    update_contract_document,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(params=('alliance', 'cell'))
def module_contract_context(
    request, building_with_us_contract, building_on_demand_contract,
    pinned_contracts_folder, superuser,
):
    if request.param == 'alliance':
        alliance_service.initialize_mirror(pinned_contracts_folder.pk, actor=superuser)
        mirror = BuildingWithUsContractMirror.objects.select_related(
            'contract__current_revision', 'document',
        ).get(contract=building_with_us_contract)
        writer = alliance_service
    else:
        cell_service.sync_mirror(actor=superuser)
        mirror = BuildingOnDemandContractMirror.objects.select_related(
            'contract__current_revision', 'document',
        ).get(contract=building_on_demand_contract)
        writer = cell_service
    return SimpleNamespace(document=mirror.document, writer=writer)


def test_adapter_requires_a_change_note(module_contract_context, superuser):
    """Fails if a contract revision can be created without an audit reason."""
    document = module_contract_context.document

    with pytest.raises(ModuleContractDocumentError) as rejected:
        update_contract_document(document, {'if_match': document_etag(document)}, actor=superuser)

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert module_contract_mirror(document)[0].contract.current_revision.version == 1


def test_adapter_rejects_an_empty_change_note(module_contract_context, superuser):
    """Fails if blank audit text is accepted by the document-manager adapter."""
    document = module_contract_context.document

    with pytest.raises(ModuleContractDocumentError) as rejected:
        update_contract_document(document, {
            'if_match': document_etag(document), 'change_note': ' ',
        }, actor=superuser)

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert module_contract_mirror(document)[0].contract.current_revision.version == 1


def test_adapter_rejects_invalid_contract_markdown(module_contract_context, superuser):
    """Fails if unsupported placeholders bypass each module contract's Markdown validation."""
    document = module_contract_context.document

    with pytest.raises(ModuleContractDocumentError) as rejected:
        update_contract_document(document, {
            'if_match': document_etag(document), 'change_note': 'Valida el formato.',
            'content_markdown': '# Contrato\n\n{party_name}',
        }, actor=superuser)

    assert rejected.value.code == 'PLACEHOLDER_NOT_SUPPORTED'
    assert module_contract_mirror(document)[0].contract.current_revision.version == 1


def test_adapter_persists_a_presentation_only_revision(module_contract_context, superuser):
    """Fails if changing PDF presentation does not create a synchronized contract revision."""
    document = module_contract_context.document
    original_markdown = module_contract_context.writer.read_contract()['markdown']

    updated = update_contract_document(document, {
        'if_match': document_etag(document), 'change_note': 'Actualiza la presentación.',
        'template_style': 'friendly',
    }, actor=superuser)
    mirror = module_contract_mirror(updated)[0]

    assert mirror.revision.version == 2
    assert mirror.revision.markdown == original_markdown
    assert updated.template_style == 'friendly'
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')


def test_rest_adapter_preserves_a_noop_revision(admin_client, module_contract_context):
    """Fails if re-saving unchanged contract text creates a redundant history entry."""
    document = module_contract_context.document
    mirror = module_contract_mirror(document)[0]
    before_revision_id = mirror.contract.current_revision_id
    before_pdf = bytes(mirror.pdf_content)

    response = admin_client.patch(reverse('update-document', args=[document.pk]), {
        'content_markdown': module_contract_context.writer.read_contract()['markdown'],
        'if_match': document_etag(document), 'change_note': 'Sin cambios de contenido.',
    }, format='json')
    mirror.refresh_from_db()

    assert response.status_code == 200
    assert mirror.contract.current_revision_id == before_revision_id
    assert bytes(mirror.pdf_content) == before_pdf


def test_adapter_rolls_back_the_revision_when_pdf_rendering_fails(module_contract_context, superuser, monkeypatch):
    """Fails if a PDF error commits contract text or presentation options partially."""
    document = module_contract_context.document
    mirror = module_contract_mirror(document)[0]
    before = (mirror.contract.current_revision_id, bytes(mirror.pdf_content), document.template_style)
    renderer = Mock(side_effect=RuntimeError('PDF renderer unavailable.'))
    monkeypatch.setattr(module_contract_context.writer, 'render_pdf', renderer)

    with pytest.raises(ModuleContractDocumentError) as rejected:
        update_contract_document(document, {
            'if_match': document_etag(document), 'change_note': 'Prueba de reversión.',
            'content_markdown': '# Contrato revisado\n\nEl PDF debe completar la escritura.',
            'template_style': 'friendly',
        }, actor=superuser)
    mirror.refresh_from_db()
    mirror.contract.refresh_from_db()
    document.refresh_from_db()

    renderer.assert_called_once()
    assert rejected.value.code == 'MIRROR_SYNC_FAILED'
    assert (mirror.contract.current_revision_id, bytes(mirror.pdf_content), document.template_style) == before
