"""Rollback of contract revisions and their Gestor artifacts on storage failures."""
from unittest.mock import DEFAULT, Mock

import pytest

from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision, Document, DocumentNote
from content.services import building_on_demand_contract_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.tests.building_on_demand_fixtures import contract_update

pytestmark = pytest.mark.django_db


def _fail_storage(monkeypatch, stage):
    """Fail the actual PDF or ORM storage boundary, leaving orchestration real."""
    owners = {'pdf': service.DocumentPdfService, 'document': Document.objects, 'private_note': DocumentNote.objects}
    methods = {'pdf': 'generate_from_markdown', 'document': 'create', 'private_note': 'create'}
    failure = Mock(side_effect=RuntimeError('Unavailable artifact storage'))
    monkeypatch.setattr(owners[stage], methods[stage], failure)
    return failure


@pytest.mark.parametrize('stage', ['pdf', 'document', 'private_note'])
def test_first_write_failure_leaves_no_partial_artifacts(pinned_contracts_folder, admin_user, monkeypatch, stage):
    """Fails if a failed first write commits contract text, a document or a private note."""
    before = service.read_contract()
    counts = (Document.objects.count(), DocumentNote.objects.count())
    failure = _fail_storage(monkeypatch, stage)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(contract_update(before), actor=admin_user)

    assert rejected.value.code == 'MIRROR_SYNC_FAILED'
    assert rejected.value.details['applied'] is False
    assert service.read_contract() == before
    assert (BuildingOnDemandContractRevision.objects.count(), BuildingOnDemandContractMirror.objects.count()) == (1, 0)
    assert (Document.objects.count(), DocumentNote.objects.count()) == counts
    failure.assert_called_once()


@pytest.mark.parametrize('stage', ['pdf', 'private_note'])
def test_existing_write_failure_preserves_the_previous_version(pinned_contracts_folder, admin_user, monkeypatch, stage):
    """Fails if a failed PDF or note write leaves a new contract version partly applied."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    before = service.read_contract()
    stored_pdf = bytes(mirror.pdf_content)
    failure = _fail_storage(monkeypatch, stage)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(contract_update(before), actor=admin_user)
    mirror.refresh_from_db()

    assert (rejected.value.code, rejected.value.details) == ('MIRROR_SYNC_FAILED', {'stage': stage, 'applied': False})
    assert service.read_contract() == before
    assert bytes(mirror.pdf_content) == stored_pdf
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert mirror.document.document_notes.count() == 2
    failure.assert_called_once()


def test_pending_inventory_failure_rolls_back_the_first_write(pinned_contracts_folder, admin_user, monkeypatch):
    """Fails if failure of the second private note commits the initial edit or its mirror."""
    before = service.read_contract()
    counts = (Document.objects.count(), DocumentNote.objects.count())
    note_writer = Mock(wraps=DocumentNote.objects.create, side_effect=[DEFAULT, RuntimeError('Inventory store unavailable')])
    monkeypatch.setattr(DocumentNote.objects, 'create', note_writer)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(contract_update(before), actor=admin_user)

    assert rejected.value.details == {'stage': 'private_note', 'applied': False}
    assert service.read_contract() == before
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert (Document.objects.count(), DocumentNote.objects.count()) == counts
    note_writer.assert_called()


@pytest.mark.parametrize('stage', ['pdf', 'document', 'private_note'])
def test_initial_sync_failure_leaves_no_document(pinned_contracts_folder, admin_user, monkeypatch, stage):
    """Fails if an initialization failure leaves an incomplete module document or note."""
    before = service.read_contract()
    counts = (Document.objects.count(), DocumentNote.objects.count())
    failure = _fail_storage(monkeypatch, stage)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user)

    assert rejected.value.code == 'MIRROR_SYNC_FAILED'
    assert rejected.value.details['applied'] is False
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert (Document.objects.count(), DocumentNote.objects.count()) == counts
    failure.assert_called_once()


def test_initial_inventory_failure_rolls_back_the_sync(pinned_contracts_folder, admin_user, monkeypatch):
    """Fails if the pending-decision note fails after the version note but leaves a mirror."""
    counts = (Document.objects.count(), DocumentNote.objects.count())
    note_writer = Mock(wraps=DocumentNote.objects.create, side_effect=[DEFAULT, RuntimeError('Inventory store unavailable')])
    monkeypatch.setattr(DocumentNote.objects, 'create', note_writer)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user)

    assert (rejected.value.code, rejected.value.details) == ('MIRROR_SYNC_FAILED', {'stage': 'private_note', 'applied': False})
    assert service.mirror_status()['status'] == 'not_initialized'
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert (Document.objects.count(), DocumentNote.objects.count()) == counts
    note_writer.assert_called()


def test_failed_resync_keeps_the_damaged_state_unchanged(pinned_contracts_folder, admin_user, monkeypatch):
    """Fails if a failed repair changes the mirror document before its private note is saved."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    Document.objects.filter(pk=mirror.document_id).update(title='Título dañado', is_client_visible=True)
    before = service.read_contract()
    stored_pdf = bytes(mirror.pdf_content)
    failure = _fail_storage(monkeypatch, 'private_note')

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user)
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert rejected.value.details == {'stage': 'private_note', 'applied': False}
    assert service.read_contract() == before
    assert (mirror.document.title, mirror.document.is_client_visible) == ('Título dañado', True)
    assert bytes(mirror.pdf_content) == stored_pdf
    assert mirror.document.document_notes.count() == 2
    failure.assert_called_once()


@pytest.mark.parametrize(('boundary', 'pdf'), [
    ('renderer', None), ('renderer', b'not a PDF'),
    ('watermark', None), ('watermark', b'not a PDF'),
])
def test_current_pdf_rejects_invalid_boundary_output(building_on_demand_contract, monkeypatch, boundary, pdf):
    """Fails if a bad renderer or watermark result is offered as a private contract PDF."""
    owners = {'renderer': service.DocumentPdfService, 'watermark': service}
    methods = {'renderer': 'generate_from_markdown', 'watermark': 'add_watermark_to_pdf'}
    failure = Mock(return_value=pdf)
    monkeypatch.setattr(owners[boundary], methods[boundary], failure)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.current_pdf()

    assert (rejected.value.code, rejected.value.message) == ('PDF_RENDER_FAILED', 'El PDF vigente no está disponible.')
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert BuildingOnDemandContractRevision.objects.count() == 1
    failure.assert_called_once()
