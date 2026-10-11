"""The Gestor reads cell-contract revisions without providing another writer."""
from io import StringIO

import pytest
from accounts.models import Project
from django.core.management import call_command
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from content.models import (
    BuildingOnDemandContractMirror,
    BuildingOnDemandContractRevision,
    Document,
    DocumentFolder,
    DocumentNote,
    McpConnector,
)
from content.serializers.document_folder import DocumentFolderSerializer
from content.services import (
    building_on_demand_contract_service as service,
    building_with_us_contract_service,
    contract_mirror_service,
    contract_template_service,
    document_ownership_planner,
)
from content.tests.building_on_demand_fixtures import contract_update
from content.tests.mcp_parity import assert_no_writes, call_tool_inprocess

pytestmark = pytest.mark.django_db


@pytest.fixture
def cell_mirror(building_on_demand_contract, pinned_contracts_folder, superuser):
    """Create the document through the real contract synchronization writer."""
    service.sync_mirror(actor=superuser)
    return BuildingOnDemandContractMirror.objects.select_related(
        'contract__current_revision', 'revision', 'document__folder',
    ).get(contract=building_on_demand_contract)


@pytest.fixture
def documents_credential(superuser):
    """Bind the documents connector to a real administrative author."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documentos'},
    )
    token = connector.generate_token()
    credential = connector.credential_for_token(token)
    credential.actor = superuser
    credential.save(update_fields=['actor', 'updated_at'])
    return credential


@pytest.mark.parametrize('document', [None, Document(title='Borrador sin guardar')], ids=['missing', 'unsaved'])
def test_module_lookup_ignores_missing_document_identity(document):
    """Fails if a missing document is mistaken for a persisted module mirror."""
    binding = contract_mirror_service.module_contract_mirror(document)

    assert binding is None
    assert contract_mirror_service.is_contract_mirror(document) is False


def test_lookup_distinguishes_the_cell_contract(cell_mirror):
    """Fails if the cell mirror receives another module's identity or writer instructions."""
    mirror, variant, message = contract_mirror_service.module_contract_mirror(cell_mirror.document)

    assert (mirror.pk, variant) == (cell_mirror.pk, 'building_on_demand')
    assert message == (
        'Este contrato es de sólo lectura y permanece en Contratos. '
        'Su contenido se actualiza mediante el MCP de Building on Demand.'
    )
    assert contract_mirror_service.building_with_us_mirror(cell_mirror.document) is None
    assert contract_mirror_service.mirror_read_only_message(cell_mirror.document) == message


def test_mirror_selection_includes_the_cell_contract(building_on_demand_contract, initialized_contract_mirrors, superuser):
    """Fails if the shared folder protections omit the cell document from the mirror inventory."""
    service.sync_mirror(actor=superuser)
    cell = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    building_with_us_contract_service.initialize_mirror(initialized_contract_mirrors.mirror_folder_id, actor=superuser)
    alliance_id = building_with_us_contract_service.mirror_status()['document_id']
    ordinary = Document.objects.create(title='Documento editable', folder=cell.document.folder)
    proposal_ids = set(initialized_contract_mirrors.mirrors.values_list('document_id', flat=True))

    mirrors = contract_mirror_service.mirror_documents(Document.objects.all())

    assert set(mirrors.values_list('pk', flat=True)) == proposal_ids | {alliance_id, cell.document_id}
    assert ordinary.pk not in mirrors.values_list('pk', flat=True)
    assert contract_mirror_service.folder_contains_mirror(cell.document.folder) is True


def test_gestor_detail_tracks_a_synchronized_revision(admin_client, cell_mirror, superuser):
    """Fails if a module update leaves the Gestor reading a pointer or earlier revision."""
    arguments = contract_update(service.read_contract())
    updated = service.apply_update(arguments, actor=superuser)
    cell_mirror.refresh_from_db()

    response = admin_client.get(reverse('retrieve-document', args=[cell_mirror.document_id]))

    assert response.status_code == 200
    assert response.data['content_markdown'] == arguments['markdown']
    assert response.data['contract_variant'] == 'building_on_demand'
    assert response.data['contract_version'] == updated['version'] == 2
    assert response.data['contract_synced_at'] == cell_mirror.synced_at.isoformat()
    assert response.data['is_contract_mirror'] is True


def test_gestor_download_uses_the_current_cell_artifact(admin_client, cell_mirror, superuser):
    """Fails if the Gestor renders a proposal contract instead of the synchronized cell PDF."""
    service.apply_update(contract_update(service.read_contract()), actor=superuser)
    cell_mirror.refresh_from_db()

    response = admin_client.get(reverse('download-document-pdf', args=[cell_mirror.document_id]))

    assert response.status_code == 200
    assert response.content == bytes(cell_mirror.pdf_content)
    assert response['Content-Type'] == 'application/pdf'
    assert contract_template_service.mirror_metadata(cell_mirror.document)['contract_version'] == 2


@pytest.mark.parametrize('artifact', ['outdated', 'empty'])
def test_gestor_download_rejects_an_unavailable_cell_artifact(admin_client, cell_mirror, artifact):
    """Fails if a stale or empty cell artifact is downloaded as the current contract."""
    revision = BuildingOnDemandContractRevision.objects.create(
        version=2, markdown='# Contrato posterior', change_note='Cambio directo no sincronizado.',
    )
    cell_mirror.contract.current_revision = {'outdated': revision, 'empty': cell_mirror.revision}[artifact]
    cell_mirror.contract.save(update_fields=['current_revision', 'updated_at'])
    cell_mirror.pdf_content = {'outdated': cell_mirror.pdf_content, 'empty': b''}[artifact]
    cell_mirror.save(update_fields=['pdf_content'])

    response = admin_client.get(reverse('download-document-pdf', args=[cell_mirror.document_id]))

    assert response.status_code == 503
    assert response.data['detail'] == 'El contrato vigente no está disponible en este momento.'
    assert service.mirror_status()['status'] == 'out_of_sync'


@pytest.mark.parametrize('method,route,payload', [
    ('patch', 'update-document', {'content_markdown': '# Cambio desde el Gestor'}),
    ('delete', 'delete-document', {}),
    ('patch', 'archive-document', {}),
    ('post', 'duplicate-document', {}),
])
def test_gestor_writes_preserve_the_synchronized_contract(admin_client, cell_mirror, method, route, payload):
    """Fails if a document write can bypass the transactional cell-contract writer."""
    before = service.read_contract()
    document_count = Document.objects.count()
    note_count = DocumentNote.objects.filter(document=cell_mirror.document).count()

    response = getattr(admin_client, method)(reverse(route, args=[cell_mirror.document_id]), payload, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'contract_mirror_read_only'
    assert response.data['detail'] == contract_mirror_service.BUILDING_ON_DEMAND_MIRROR_MESSAGE
    assert service.read_contract() == before
    assert Document.objects.count() == document_count
    assert DocumentNote.objects.filter(document=cell_mirror.document).count() == note_count


def test_documents_connector_reads_the_live_cell_revision(cell_mirror, documents_credential, superuser):
    """Fails if the documents connector supplies stale text after a cell-contract update."""
    arguments = contract_update(service.read_contract())
    current = service.apply_update(arguments, actor=superuser)

    result = assert_no_writes(call_tool_inprocess, 'documents', 'read_document', {
        'document_id': cell_mirror.document_id,
    }, credential=documents_credential)

    assert result['markdown'] == arguments['markdown']
    assert result['contract_variant'] == 'building_on_demand'
    assert result['contract_version'] == current['version']
    assert result['editable'] is False
    assert result['movable'] is False
    assert result['edit_blockers'] == ['contract_mirror']


@pytest.mark.parametrize('tool,arguments', [
    ('update_document', {'markdown': '# Cambio conversacional'}),
    ('append_document', {'markdown': 'Texto añadido al contrato'}),
])
def test_documents_connector_refuses_cell_contract_mutations(cell_mirror, documents_credential, tool, arguments):
    """Fails if the general documents connector becomes an alternate cell-contract writer."""
    before = service.resource_etags()

    result = call_tool_inprocess('documents', tool, {
        'document_id': cell_mirror.document_id, **arguments,
    }, credential=documents_credential)

    assert result['error']['code'] == 'NOT_EDITABLE'
    assert result['error']['message'] == contract_mirror_service.BUILDING_ON_DEMAND_MIRROR_MESSAGE
    assert result['error']['details']['edit_blockers'] == ['contract_mirror']
    assert service.resource_etags() == before
    assert BuildingOnDemandContractMirror.objects.get(pk=cell_mirror.pk).document_id == cell_mirror.document_id


def test_confirmed_documents_deletion_preserves_the_cell_contract(cell_mirror, documents_credential):
    """Fails if confirming a sensitive document deletion removes the cell-contract mirror."""
    before = service.resource_etags()
    preview = call_tool_inprocess('documents', 'delete_document', {
        'document_id': cell_mirror.document_id,
    }, credential=documents_credential)

    result = call_tool_inprocess('documents', 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    }, credential=documents_credential)

    assert result['error']['code'] == 'NOT_EDITABLE'
    assert result['error']['message'] == contract_mirror_service.BUILDING_ON_DEMAND_MIRROR_MESSAGE
    assert result['error']['details']['edit_blockers'] == ['contract_mirror']
    assert service.resource_etags() == before
    assert Document.objects.filter(pk=cell_mirror.document_id).exists()


@pytest.mark.parametrize('field', ['name', 'parent', 'client', 'project'])
def test_unpinned_cell_folder_keeps_its_contractual_location(
    building_on_demand_contract, unpinned_contracts_folder, superuser, make_client_profile, field,
):
    """Fails if an unpinned module folder can be renamed, moved or given a commercial owner."""
    service.sync_mirror(actor=superuser, folder_id=unpinned_contracts_folder.pk)
    destination = DocumentFolder.objects.create(name='Otro destino')
    client = make_client_profile()
    project = Project.objects.create(name='Producto del cliente', client=client.user)
    values = {'name': 'Otro nombre', 'parent': destination.pk, 'client': client.pk, 'project': project.pk}
    before = service.mirror_status()
    serializer = DocumentFolderSerializer(unpinned_contracts_folder, data={field: values[field]}, partial=True)

    with pytest.raises(ValidationError) as error:
        serializer.is_valid(raise_exception=True)

    assert str(error.value.detail['code'][0]) == 'contract_mirror_folder_pinned'
    assert service.mirror_status() == before
    assert service.mirror_status()['status'] == 'synchronized'


def test_pinned_cell_folder_can_be_reorganized(cell_mirror, superuser):
    """Fails if the shared pin loses the cell mirror when its folder moves or changes name."""
    destination = DocumentFolder.objects.create(name='Nueva ubicación interna')
    folder = cell_mirror.document.folder
    serializer = DocumentFolderSerializer(folder, data={'name': 'Plantillas vigentes', 'parent': destination.pk}, partial=True)
    serializer.is_valid(raise_exception=True)

    serializer.save()
    service.sync_mirror(actor=superuser)

    assert service.mirror_status()['status'] == 'synchronized'
    assert service.mirror_status()['folder_id'] == folder.pk
    assert service.mirror_status()['folder_path'] == 'Nueva ubicación interna › Plantillas vigentes'
    assert BuildingOnDemandContractMirror.objects.get(pk=cell_mirror.pk).document_id == cell_mirror.document_id


@pytest.mark.parametrize('association', ['client', 'project'])
def test_pinned_cell_folder_refuses_commercial_ownership(cell_mirror, make_client_profile, association):
    """Fails if the contract folder becomes owned by a client or project through its serializer."""
    client = make_client_profile()
    project = Project.objects.create(name='Producto', client=client.user)
    folder = cell_mirror.document.folder
    serializer = DocumentFolderSerializer(folder, data={
        association: {'client': client.pk, 'project': project.pk}[association],
    }, partial=True)

    with pytest.raises(ValidationError) as error:
        serializer.is_valid(raise_exception=True)

    assert str(error.value.detail['code'][0]) == 'contract_mirror_folder_pinned'
    folder.refresh_from_db()
    assert (folder.client_user_id, folder.project_id) == (None, None)
    assert service.mirror_status()['status'] == 'synchronized'


@pytest.mark.parametrize('target', ['folder', 'ancestor'])
def test_cell_mirror_prevents_contract_tree_archival(admin_client, cell_mirror, target):
    """Fails if archiving a folder or ancestor removes the only active cell-contract document."""
    folder = cell_mirror.document.folder
    target_folder = {'folder': folder, 'ancestor': folder.parent}[target]

    response = admin_client.patch(reverse('archive-document-folder', args=[target_folder.pk]), {}, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'contract_mirror_folder_archive_blocked'
    assert response.data['mirror_document_ids'] == [cell_mirror.document_id]
    target_folder.refresh_from_db()
    assert target_folder.is_archived is False
    assert service.mirror_status()['status'] == 'synchronized'


def test_ownership_planner_preserves_the_cell_mirror(cell_mirror, superuser):
    """Fails if the shared movement writer relocates a module mirror independently of its pin."""
    destination = DocumentFolder.objects.create(name='Destino de movimiento')
    arguments = {'document_ids': [cell_mirror.document_id], 'destination_folder_id': destination.pk, 'client_policy': 'keep'}
    before = service.resource_etags()

    plan = document_ownership_planner.plan_ownership(**arguments)
    with pytest.raises(document_ownership_planner.OwnershipPlanError) as error:
        document_ownership_planner.apply_ownership_plan(arguments, actor=superuser)

    assert plan['can_apply'] is False
    assert plan['rows'][0]['status'] == 'blocked'
    assert plan['rows'][0]['blockers'][0]['code'] == 'contract_mirror'
    assert error.value.code == 'ownership_plan_blocked'
    assert service.resource_etags() == before


def test_fake_reset_releases_the_cell_mirror(building_on_demand_contract, initialized_contract_mirrors, superuser):
    """Fails if a fake reset hits the document's protected mirror or removes its catalog contract."""
    service.sync_mirror(actor=superuser)
    current = service.read_contract()
    document_id = current['mirror']['document_id']

    call_command('delete_fake_data', '--confirm', verbosity=0, stdout=StringIO())

    assert not BuildingOnDemandContractMirror.objects.exists()
    assert not Document.objects.filter(pk=document_id).exists()
    assert initialized_contract_mirrors.mirrors.count() == 0
    initialized_contract_mirrors.refresh_from_db()
    assert initialized_contract_mirrors.mirror_folder_id is None
    assert service.read_contract()['version_id'] == current['version_id']
    assert service.mirror_status()['status'] == 'not_initialized'
