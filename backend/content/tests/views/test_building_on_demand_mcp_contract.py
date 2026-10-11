"""Private contract editing, folder pin guards and downloadable MCP artifacts."""
from urllib.parse import urlsplit

import pytest
from rest_framework.test import APIClient

from content.mcp.building_on_demand_contract_tools import BUILDING_ON_DEMAND_CONTRACT_TOOLS
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.models import (
    BuildingOnDemandContractMirror, BuildingOnDemandContractRevision, ContractTemplate,
    Document, DocumentFolder, McpActionIntent,
)
from content.services import building_on_demand_contract_service as service
from content.tests.building_on_demand_fixtures import confirm, contract_update, rpc_call

pytestmark = pytest.mark.django_db
WRITE_TOOLS = {tool['name']: tool for tool in BUILDING_ON_DEMAND_CONTRACT_TOOLS
               if tool.get('requires_confirmation')}
CLAUSE = 'Cada estimación aprobada queda registrada por escrito.'


@pytest.fixture
def initialized_mirror(pinned_contracts_folder, superuser):
    service.sync_mirror(actor=superuser)
    return BuildingOnDemandContractMirror.objects.select_related('document', 'revision').get()


@pytest.fixture
def edit_arguments(source):
    snapshot = service.read_contract()
    sources = {
        'markdown': {'markdown': contract_update(snapshot)['markdown']},
        'patches': {'patches': [{'operation': 'insert_after', 'text': snapshot['markdown'].splitlines()[0],
                                 'markdown': '\n\n' + CLAUSE}]},
    }
    return {**sources[source], 'if_match': snapshot['etag'], 'change_note': 'Aclara la aceptación escrita de estimaciones.'}


def test_contract_read_returns_uninitialized_mirror(api_client, building_on_demand_mcp, building_on_demand_contract):
    """Fails if contract provenance cannot be inspected before its mirror exists."""
    token, _ = building_on_demand_mcp

    snapshot = rpc_call(api_client, token, 'get_building_on_demand_contract', {})['structuredContent']

    assert snapshot['version'] == 1
    assert snapshot['version_id'] == building_on_demand_contract.current_revision_id
    assert snapshot['markdown'].startswith('# ')
    assert snapshot['author'] == 'Sistema'
    assert snapshot['mirror']['status'] == 'not_initialized'
    assert snapshot['mirror']['document_id'] is None


@pytest.mark.parametrize('source', ['markdown', 'patches'])
def test_confirmed_contract_edit_synchronizes_mirror(api_client, building_on_demand_mcp, pinned_contracts_folder,
                                                   source, edit_arguments):
    """Fails if either edit form publishes before confirmation or loses its mirror."""
    token, credential = building_on_demand_mcp
    public = {key: value for key, value in edit_arguments.items() if key not in ('if_match', 'change_note')}
    preview = rpc_call(api_client, token, 'preview_building_on_demand_contract_update', public)['structuredContent']
    intent = rpc_call(api_client, token, 'update_building_on_demand_contract', edit_arguments)['structuredContent']
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert not BuildingOnDemandContractMirror.objects.exists()

    result = confirm(api_client, token, intent)['structuredContent']['result']
    mirror = BuildingOnDemandContractMirror.objects.select_related('document').get()
    revision = BuildingOnDemandContractRevision.objects.get(pk=result['version_id'])

    assert preview['changed'] is True
    assert CLAUSE in preview['diff']
    assert result['version'] == 2
    assert result['mirror']['status'] == 'synchronized'
    assert CLAUSE in revision.markdown
    assert revision.credential_id == credential.pk
    assert revision.author_id == credential.actor_id
    assert mirror.revision_id == revision.pk
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.folder_id == pinned_contracts_folder.pk
    assert mirror.document.is_client_visible is False
    assert mirror.document.document_notes.filter(title='Contrato Building on Demand — versión 2').exists()


def test_confirmed_contract_restore_creates_revision(api_client, building_on_demand_mcp, initialized_mirror, superuser):
    """Fails if restore destroys history or leaves the PDF on a different revision."""
    token, credential = building_on_demand_mcp
    initial = service.read_contract()
    service.apply_update(contract_update(initial), actor=superuser)
    current = service.read_contract()
    intent = rpc_call(api_client, token, 'restore_building_on_demand_contract_version', {
        'version_id': initial['version_id'], 'if_match': current['etag'], 'change_note': 'Recupera el contrato inicial.',
    })['structuredContent']
    assert service.read_contract()['version'] == 2

    result = confirm(api_client, token, intent)['structuredContent']['result']
    versions = rpc_call(api_client, token, 'list_building_on_demand_contract_versions',
                        {'include_content': True})['structuredContent']
    initialized_mirror.refresh_from_db()

    assert result['version'] == 3
    assert versions['total'] == 3
    assert versions['versions'][0]['restored_from_version_id'] == initial['version_id']
    assert versions['versions'][0]['restored_from_version'] == 1
    assert versions['versions'][0]['markdown'] == initial['markdown']
    assert initialized_mirror.revision_id == result['version_id']
    assert result['mirror']['status'] == 'synchronized'
    assert BuildingOnDemandContractRevision.objects.get(pk=result['version_id']).credential_id == credential.pk


@pytest.mark.parametrize('explicit_folder', [False, True], ids=['pinned-default', 'explicit-pin'])
def test_confirmed_sync_creates_private_mirror(api_client, building_on_demand_mcp, pinned_contracts_folder, explicit_folder):
    """Fails if initial sync writes before confirmation or ignores the shared pin."""
    token, _ = building_on_demand_mcp
    arguments = {False: {}, True: {'folder_id': pinned_contracts_folder.pk}}[explicit_folder]
    intent = rpc_call(api_client, token, 'sync_building_on_demand_contract_mirror', arguments)['structuredContent']
    assert not BuildingOnDemandContractMirror.objects.exists()

    result = confirm(api_client, token, intent)['structuredContent']['result']
    document = Document.objects.get(pk=result['mirror']['document_id'])

    assert intent['impact']['outcome'] == 'create'
    assert 'folder_pin' in intent['impact']['resource_etags']
    assert result['outcome'] == 'create'
    assert result['mirror']['status'] == 'synchronized'
    assert document.folder_id == pinned_contracts_folder.pk
    assert document.document_notes.count() == 2
    assert document.document_notes.filter(title='Inventario de decisiones pendientes (v1)').exists()
    assert BuildingOnDemandContractRevision.objects.count() == 1


def test_confirmed_sync_is_noop_for_synchronized_mirror(api_client, building_on_demand_mcp, initialized_mirror):
    """Fails if repeating a synchronized sync duplicates its document or audit notes."""
    token, _ = building_on_demand_mcp
    initial_time = initialized_mirror.synced_at
    note_ids = list(initialized_mirror.document.document_notes.values_list('pk', flat=True))
    intent = rpc_call(api_client, token, 'sync_building_on_demand_contract_mirror', {})['structuredContent']

    result = confirm(api_client, token, intent)['structuredContent']['result']
    initialized_mirror.refresh_from_db()

    assert intent['impact']['outcome'] == 'noop'
    assert result['outcome'] == 'noop'
    assert result['mirror']['document_id'] == initialized_mirror.document_id
    assert initialized_mirror.synced_at == initial_time
    assert list(initialized_mirror.document.document_notes.values_list('pk', flat=True)) == note_ids


def test_sync_rejects_an_alternative_to_pinned_folder(api_client, building_on_demand_mcp, pinned_contracts_folder):
    """Fails if an explicit folder can override the configured contract destination."""
    token, credential = building_on_demand_mcp
    alternative = DocumentFolder.objects.create(name='Contratos', parent=pinned_contracts_folder.parent)

    result = rpc_call(api_client, token, 'sync_building_on_demand_contract_mirror', {'folder_id': alternative.pk})

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'FOLDER_NOT_ALLOWED'
    assert not McpActionIntent.objects.filter(credential=credential).exists()
    assert not BuildingOnDemandContractMirror.objects.exists()


def test_sync_without_pin_returns_configuration_hint(api_client, building_on_demand_mcp, unpinned_contracts_folder):
    """Fails if default sync guesses a destination rather than failing closed."""
    token, credential = building_on_demand_mcp

    result = rpc_call(api_client, token, 'sync_building_on_demand_contract_mirror', {})

    assert result['isError'] is True
    error = result['structuredContent']['error']
    assert error['code'] == 'MIRROR_SYNC_FAILED'
    assert error['details']['stage'] == 'folder_pin'
    assert error['details']['applied'] is False
    assert error['details']['hint'] == (
        'Ejecuta sync_building_on_demand_contract_mirror --apply --folder-id N con una carpeta interna Contratos válida.'
    )
    assert not McpActionIntent.objects.filter(credential=credential).exists()


def test_contract_edit_without_pin_creates_no_intent(api_client, building_on_demand_mcp, unpinned_contracts_folder):
    """Fails if an unpinned contract edit advertises a confirmation it cannot apply."""
    token, credential = building_on_demand_mcp
    arguments = contract_update(service.read_contract())

    result = rpc_call(api_client, token, 'update_building_on_demand_contract', arguments)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'MIRROR_SYNC_FAILED'
    assert result['structuredContent']['error']['details']['applied'] is False
    assert not McpActionIntent.objects.filter(credential=credential).exists()
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert not BuildingOnDemandContractMirror.objects.exists()


@pytest.fixture
def change_dependency(changed_resource, initialized_mirror, pinned_contracts_folder, superuser):
    """Apply a real independent resource change after a preview."""
    def change():
        mutations = {
            'document': lambda: Document.objects.filter(pk=initialized_mirror.document_id).update(folder=None),
            'mirror': lambda: BuildingOnDemandContractMirror.objects.filter(pk=initialized_mirror.pk).update(pdf_content=b'%PDF-changed'),
            'folder': lambda: DocumentFolder.objects.filter(pk=pinned_contracts_folder.pk).update(name='Otro destino'),
            'pin': lambda: ContractTemplate.objects.filter(is_default=True).update(mirror_folder=None),
            'contract': lambda: service.apply_update(contract_update(service.read_contract()), actor=superuser),
        }
        mutations[changed_resource]()
    return change


@pytest.mark.parametrize('changed_resource', ['document', 'mirror', 'folder', 'pin', 'contract'])
def test_confirmation_rejects_changed_contract_dependency(api_client, building_on_demand_mcp, change_dependency):
    """Fails if confirmation silently accepts changed contract or mirror dependencies."""
    token, _ = building_on_demand_mcp
    intent = rpc_call(api_client, token, 'update_building_on_demand_contract',
                      contract_update(service.read_contract()))['structuredContent']
    change_dependency()
    current_version = service.read_contract()['version_id']

    result = confirm(api_client, token, intent)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert service.read_contract()['version_id'] == current_version


@pytest.mark.parametrize(('name', 'arguments', 'filename'), [
    ('render_building_on_demand_program_pdf', {}, 'building-on-demand-es.pdf'),
    ('render_building_on_demand_program_pdf', {'lang': 'en'}, 'building-on-demand-en.pdf'),
    ('render_building_on_demand_contract_pdf', {}, 'contrato-building-on-demand-v1.pdf'),
])
def test_pdf_tool_returns_downloadable_artifact(api_client, building_on_demand_mcp, name, arguments, filename):
    """Fails if a PDF tool cannot deliver its current document by signed download."""
    token, credential = building_on_demand_mcp

    result = rpc_call(api_client, token, name, arguments)
    artifact = result['structuredContent']
    url = urlsplit(artifact['download_url'])
    response = APIClient().get(url.path + '?' + url.query)

    assert result['isError'] is False
    assert artifact['filename'] == filename
    assert artifact['content_type'] == 'application/pdf'
    assert response.status_code == 200
    assert b''.join(response.streaming_content).startswith(b'%PDF-')
    assert not McpActionIntent.objects.filter(credential=credential).exists()


@pytest.mark.parametrize('name', sorted(WRITE_TOOLS))
def test_direct_contract_write_requires_confirmation(building_on_demand_mcp, name):
    """Fails if a private contract handler can mutate without confirm_action."""
    _, credential = building_on_demand_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='unconfirmed-contract-write', actor=credential.actor)

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        WRITE_TOOLS[name]['handler']({})

    assert error.value.code == 'CONFIRMATION_REQUIRED'
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert not BuildingOnDemandContractMirror.objects.exists()


@pytest.mark.parametrize('name', sorted(WRITE_TOOLS))
def test_confirmed_contract_handler_requires_frozen_etags(building_on_demand_mcp, name):
    """Fails if contract execution lacks the preview's dependency snapshot."""
    _, credential = building_on_demand_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='missing-contract-preview', actor=credential.actor, confirmation_bypass=True)

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        WRITE_TOOLS[name]['handler']({})

    assert error.value.code == 'STALE_VERSION'
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert not BuildingOnDemandContractMirror.objects.exists()


@pytest.mark.parametrize('sources', [{}, {'markdown': '# Contrato', 'patches': []}], ids=['missing', 'both'])
def test_contract_preview_requires_exactly_one_source(api_client, building_on_demand_mcp, sources):
    """Fails if preview accepts neither edit source or ambiguous Markdown plus patches."""
    token, _ = building_on_demand_mcp

    result = rpc_call(api_client, token, 'preview_building_on_demand_contract_update', sources)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert result['structuredContent']['error']['message'] == 'Indica exactamente markdown o patches; para restaurar usa version_id.'
    assert BuildingOnDemandContractRevision.objects.count() == 1
