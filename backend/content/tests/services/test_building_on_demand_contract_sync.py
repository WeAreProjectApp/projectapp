"""Pinned mirror destinations, explicit unpinned setup and artifact convergence."""
from unittest.mock import Mock

import pytest

from accounts.models import Project
from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision, Document, DocumentFolder
from content.services import building_on_demand_contract_service as service
from content.services.building_on_demand_content import BuildingOnDemandError

pytestmark = pytest.mark.django_db


def test_sync_preview_resolves_the_pin_without_writes(pinned_contracts_folder):
    """Fails if preparation creates a Gestor mirror or overlooks the configured pin."""
    before = service.read_contract()

    prepared = service.prepare_sync()

    assert prepared['outcome'] == 'create'
    assert prepared['folder_id'] == pinned_contracts_folder.pk
    assert prepared['mirror'] == before['mirror']
    assert prepared['resource_etags'] == service.resource_etags()
    assert 'folder_pin' in prepared['resource_etags']
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_repeated_sync_preserves_the_artifact(pinned_contracts_folder, admin_user, monkeypatch):
    """Fails if an already synchronized mirror renders another PDF or receives another note."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    before = service.mirror_status()
    stored_pdf = bytes(mirror.pdf_content)
    renderer = Mock(side_effect=RuntimeError('Unexpected PDF regeneration'))
    monkeypatch.setattr(service.DocumentPdfService, 'generate_from_markdown', renderer)

    result = service.sync_mirror(actor=admin_user)
    mirror.refresh_from_db()

    assert result == {'outcome': 'noop', 'mirror': before}
    assert bytes(mirror.pdf_content) == stored_pdf
    assert mirror.document.document_notes.count() == 2
    assert BuildingOnDemandContractMirror.objects.count() == 1
    renderer.assert_not_called()


def test_explicit_foreign_folder_cannot_override_the_pin(pinned_contracts_folder, admin_user):
    """Fails if a second internal Contratos folder diverts the document from its shared pin."""
    foreign = DocumentFolder.objects.create(name='Contratos')

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user, folder_id=foreign.pk)

    assert rejected.value.code == 'FOLDER_NOT_ALLOWED'
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert Document.objects.filter(title=service.CONTRACT_TITLE).count() == 0


def test_pin_survives_a_folder_rename(pinned_contracts_folder, admin_user):
    """Fails if renaming the configured destination strands the module mirror."""
    pinned_contracts_folder.name = 'Acuerdos contractuales'
    pinned_contracts_folder.save(update_fields=['name', 'updated_at'])

    result = service.sync_mirror(actor=admin_user)

    assert result['outcome'] == 'create'
    assert result['mirror']['status'] == 'synchronized'
    assert result['mirror']['folder_id'] == pinned_contracts_folder.pk
    assert result['mirror']['folder_path'] == 'ProjectApp › Acuerdos contractuales'


def test_unpinned_sync_requires_an_explicit_destination(unpinned_contracts_folder, admin_user):
    """Fails if an unpinned run guesses a destination from a coincidentally named folder."""
    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user)

    assert rejected.value.code == 'MIRROR_SYNC_FAILED'
    assert rejected.value.details['stage'] == 'folder_pin'
    assert rejected.value.details['applied'] is False
    assert 'sync_building_on_demand_contract_mirror --apply --folder-id N' in rejected.value.details['hint']
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_explicit_unpinned_folder_receives_the_mirror(unpinned_contracts_folder, admin_user):
    """Fails if safe explicit initialization cannot synchronize before a shared pin exists."""
    prepared = service.prepare_sync(unpinned_contracts_folder.pk)

    result = service.sync_mirror(actor=admin_user, folder_id=unpinned_contracts_folder.pk,
                                 expected_etags=prepared['resource_etags'])
    mirror = BuildingOnDemandContractMirror.objects.get()

    assert (result['outcome'], result['mirror']['status']) == ('create', 'synchronized')
    assert mirror.document.folder_id == unpinned_contracts_folder.pk
    assert mirror.document.is_client_visible is False
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.document_notes.count() == 2


@pytest.mark.parametrize('kind', ['name', 'archived', 'client', 'project', 'system'])
def test_unpinned_sync_rejects_noninternal_destinations(unpinned_contracts_folder, admin_user, kind):
    """Fails if synchronization accepts inactive, associated or system-managed folders."""
    project = Project.objects.create(name='Proyecto ajeno', client=admin_user)
    changes = {
        'name': {'name': 'Otros'}, 'archived': {'is_archived': True},
        'client': {'client_user': admin_user}, 'project': {'project': project},
        'system': {'system_key': 'test:reserved-contracts'},
    }
    DocumentFolder.objects.filter(pk=unpinned_contracts_folder.pk).update(**changes[kind])

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user, folder_id=unpinned_contracts_folder.pk)

    assert rejected.value.code == 'FOLDER_NOT_ALLOWED'
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert Document.objects.filter(title=service.CONTRACT_TITLE).count() == 0


@pytest.mark.parametrize('folder_id', [True, 0, '1'])
def test_sync_refuses_coerced_folder_ids(unpinned_contracts_folder, folder_id):
    """Fails if the synchronization preview coerces booleans or text into folder ids."""
    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_sync(folder_id)

    assert rejected.value.code == 'FOLDER_NOT_ALLOWED'
    assert rejected.value.message == 'folder_id debe ser un entero positivo.'
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_sync_refuses_a_missing_folder(unpinned_contracts_folder):
    """Fails if a nonexistent explicit destination reaches mirror initialization."""
    missing_id = unpinned_contracts_folder.pk + 1000

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_sync(missing_id)

    assert rejected.value.code == 'FOLDER_NOT_ALLOWED'
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert BuildingOnDemandContractMirror.objects.count() == 0


@pytest.mark.parametrize('state', ['moved', 'archived', 'empty_pdf', 'invalid_pdf'])
def test_sync_repairs_a_damaged_artifact(pinned_contracts_folder, admin_user, state):
    """Fails if explicit synchronization leaves a misplaced, archived or invalid artifact."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    other = DocumentFolder.objects.create(name='Archivo manual')
    document_updates = {
        'moved': {'folder': other}, 'archived': {'is_archived': True},
        'empty_pdf': {}, 'invalid_pdf': {},
    }
    Document.objects.filter(pk=mirror.document_id).update(**document_updates[state])
    pdfs = {'moved': bytes(mirror.pdf_content), 'archived': bytes(mirror.pdf_content),
            'empty_pdf': b'', 'invalid_pdf': b'not a PDF'}
    BuildingOnDemandContractMirror.objects.filter(pk=mirror.pk).update(pdf_content=pdfs[state])
    prepared = service.prepare_sync()

    result = service.sync_mirror(actor=admin_user, expected_etags=prepared['resource_etags'])
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert (prepared['outcome'], prepared['mirror']['status']) == ('resync', 'out_of_sync')
    assert (result['outcome'], result['mirror']['status']) == ('resync', 'synchronized')
    assert mirror.document.folder_id == pinned_contracts_folder.pk
    assert mirror.document.is_archived is False
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.document_notes.count() == 3
    assert BuildingOnDemandContractRevision.objects.count() == 1


def test_unchanged_write_repairs_a_damaged_pdf(pinned_contracts_folder, admin_user):
    """Fails if unchanged markdown leaves a corrupt mirror PDF because no revision is needed."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    BuildingOnDemandContractMirror.objects.filter(pk=mirror.pk).update(pdf_content=b'corrupt')
    before = service.read_contract()
    arguments = {'markdown': before['markdown'], 'if_match': before['etag'], 'change_note': 'Reparar el espejo vigente.'}

    result = service.apply_update(arguments, actor=admin_user)
    mirror.refresh_from_db()

    assert result == {'applied': True, 'changed': False}
    assert service.mirror_status()['status'] == 'synchronized'
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.document_notes.count() == 3
    assert BuildingOnDemandContractRevision.objects.count() == 1
