"""Frozen preview dependencies and repair guarantees of contract application."""
import pytest

from accounts.models import Project
from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision, ContractTemplate, Document, DocumentFolder, DocumentNote
from content.services import building_on_demand_contract_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.tests.building_on_demand_fixtures import contract_update

pytestmark = pytest.mark.django_db


def test_unpinned_first_write_fails_closed(unpinned_contracts_folder, admin_user):
    """Fails if the first contract change guesses a folder instead of requiring a shared pin."""
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(contract_update(before), actor=admin_user)

    assert rejected.value.code == 'MIRROR_SYNC_FAILED'
    assert rejected.value.details['stage'] == 'folder_pin'
    assert rejected.value.details['applied'] is False
    assert 'sync_building_on_demand_contract_mirror --apply --folder-id N' in rejected.value.details['hint']
    assert service.read_contract() == before
    assert (BuildingOnDemandContractRevision.objects.count(), BuildingOnDemandContractMirror.objects.count()) == (1, 0)


def test_first_write_rechecks_a_newly_created_mirror(pinned_contracts_folder, admin_user):
    """Fails if a missing-mirror preview still applies after another writer initializes it."""
    arguments = contract_update(service.read_contract())
    expected = service.prepare_update(arguments)['resource_etags']
    service.sync_mirror(actor=admin_user)
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(arguments, actor=admin_user, expected_etags=expected)

    assert rejected.value.code == 'STALE_VERSION'
    assert service.read_contract() == before
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert BuildingOnDemandContractMirror.objects.get().document.document_notes.count() == 2


@pytest.mark.parametrize('kind', ['title', 'pdf', 'visibility'])
def test_write_rechecks_the_confirmed_mirror(pinned_contracts_folder, admin_user, kind):
    """Fails if document metadata or PDF corruption after preview is silently overwritten."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    arguments = contract_update(service.read_contract())
    expected = service.prepare_update(arguments)['resource_etags']
    document_updates = {'title': {'title': 'Cambio externo'}, 'pdf': {}, 'visibility': {'is_client_visible': True}}
    Document.objects.filter(pk=mirror.document_id).update(**document_updates[kind])
    pdfs = {'title': bytes(mirror.pdf_content), 'pdf': b'corrupted', 'visibility': bytes(mirror.pdf_content)}
    BuildingOnDemandContractMirror.objects.filter(pk=mirror.pk).update(pdf_content=pdfs[kind])
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(arguments, actor=admin_user, expected_etags=expected)

    assert rejected.value.code == 'STALE_VERSION'
    assert service.read_contract() == before
    assert service.resource_etags()['mirror'] != expected['mirror']
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert mirror.document.document_notes.count() == 2


def test_first_write_rechecks_the_folder_pin(pinned_contracts_folder, admin_user):
    """Fails if an edit confirmed for one shared destination applies after the pin changes."""
    arguments = contract_update(service.read_contract())
    expected = service.prepare_update(arguments)['resource_etags']
    replacement = DocumentFolder.objects.create(name='Contratos')
    template = ContractTemplate.get_default()
    template.mirror_folder = replacement
    template.save(update_fields=['mirror_folder', 'updated_at'])
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(arguments, actor=admin_user, expected_etags=expected)

    assert rejected.value.code == 'STALE_VERSION'
    assert service.read_contract() == before
    assert service.resource_etags()['folder_pin'] != expected['folder_pin']
    assert BuildingOnDemandContractMirror.objects.count() == 0


@pytest.mark.parametrize('change', [{'name': 'Nuevo nombre'}, {'is_archived': True}])
def test_implicit_sync_rechecks_pinned_folder_state(pinned_contracts_folder, admin_user, change):
    """Fails if synchronization accepts a renamed or archived pin from an older preview."""
    expected = service.prepare_sync()['resource_etags']
    DocumentFolder.objects.filter(pk=pinned_contracts_folder.pk).update(**change)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user, expected_etags=expected)

    assert rejected.value.code == 'STALE_VERSION'
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert Document.objects.filter(title=service.CONTRACT_TITLE).count() == 0


@pytest.mark.parametrize('change', ['name', 'system', 'deleted'])
def test_explicit_sync_rechecks_its_destination(unpinned_contracts_folder, admin_user, change):
    """Fails if explicit setup uses a destination changed or removed after confirmation."""
    folder_id = unpinned_contracts_folder.pk
    expected = service.prepare_sync(folder_id)['resource_etags']
    changes = {'name': {'name': 'Otro destino'}, 'system': {'system_key': 'test:managed'}, 'deleted': {}}
    DocumentFolder.objects.filter(pk=folder_id).update(**changes[change])
    remove = {'name': [], 'system': [], 'deleted': [folder_id]}
    DocumentFolder.objects.filter(pk__in=remove[change]).delete()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user, folder_id=folder_id, expected_etags=expected)

    assert rejected.value.code == 'STALE_VERSION'
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert Document.objects.filter(title=service.CONTRACT_TITLE).count() == 0


def test_resource_snapshot_identifies_a_deleted_folder(unpinned_contracts_folder):
    """Fails if missing explicit dependencies lose their distinguishable folder etag."""
    folder_id = unpinned_contracts_folder.pk
    before = service.resource_etags({'folder_id': folder_id})
    unpinned_contracts_folder.delete()

    after = service.resource_etags({'folder_id': folder_id})

    assert after == {**before, 'folder': 'none'}
    assert before['folder'] != 'none'


def test_explicit_unpinned_sync_changes_its_destination(unpinned_contracts_folder, admin_user):
    """Fails if a synchronized mirror stays in the old unpinned folder despite an explicit target."""
    first = service.sync_mirror(actor=admin_user, folder_id=unpinned_contracts_folder.pk)
    destination = DocumentFolder.objects.create(name='Contratos')
    prepared = service.prepare_sync(destination.pk)

    result = service.sync_mirror(actor=admin_user, folder_id=destination.pk,
                                 expected_etags=prepared['resource_etags'])
    mirror = BuildingOnDemandContractMirror.objects.get()

    assert prepared['outcome'] == 'resync'
    assert (result['outcome'], result['mirror']['status']) == ('resync', 'synchronized')
    assert result['mirror']['document_id'] == first['mirror']['document_id']
    assert mirror.document.folder_id == destination.pk
    assert mirror.document.document_notes.count() == 3
    assert BuildingOnDemandContractMirror.objects.count() == 1


@pytest.mark.parametrize('kind', ['title', 'visibility', 'pointer', 'language', 'client', 'project'])
def test_write_repairs_the_private_mirror_identity(pinned_contracts_folder, admin_user, kind):
    """Fails if a contract edit leaves its module document public, associated or mislabeled."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    project = Project.objects.create(name='Asociación incorrecta', client=admin_user)
    changes = {
        'title': {'title': 'Título ajeno'}, 'visibility': {'is_client_visible': True},
        'pointer': {'content_markdown': '# Texto ajeno'}, 'language': {'language': 'en'},
        'client': {'client_user': admin_user}, 'project': {'project': project},
    }
    Document.objects.filter(pk=mirror.document_id).update(**changes[kind])

    result = service.apply_update(contract_update(service.read_contract()), actor=admin_user)
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert (result['version'], result['mirror']['status']) == (2, 'synchronized')
    assert (mirror.document.title, mirror.document.content_markdown, mirror.document.language) == (
        service.CONTRACT_TITLE, service.MIRROR_POINTER, 'es',
    )
    assert (mirror.document.client_user_id, mirror.document.project_id, mirror.document.is_client_visible) == (None, None, False)
    assert mirror.document.folder_id == pinned_contracts_folder.pk
    assert mirror.revision_id == result['version_id']
    assert mirror.document.document_notes.count() == 3


def test_first_write_refuses_an_archived_shared_pin(pinned_contracts_folder, admin_user):
    """Fails if an already archived shared destination permits a partial contract write."""
    before = service.read_contract()
    counts = (Document.objects.count(), DocumentNote.objects.count())
    DocumentFolder.objects.filter(pk=pinned_contracts_folder.pk).update(is_archived=True)

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(contract_update(before), actor=admin_user)

    assert rejected.value.code == 'MIRROR_SYNC_FAILED'
    assert (rejected.value.details['stage'], rejected.value.details['applied']) == ('folder_pin', False)
    assert service.read_contract() == before
    assert (BuildingOnDemandContractRevision.objects.count(), BuildingOnDemandContractMirror.objects.count()) == (1, 0)
    assert (Document.objects.count(), DocumentNote.objects.count()) == counts
