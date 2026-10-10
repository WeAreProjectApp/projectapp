"""Credential-bound initialization, editing, stale confirmation and PDF transport."""
from urllib.parse import urlsplit
from io import BytesIO

import pytest
from rest_framework.test import APIClient
from django.core.signals import request_finished
from django.http import FileResponse

from content.models import BuildingWithUsContractMirror, BuildingWithUsContractRevision, Document
from content.services import building_with_us_contract_service as service
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.panel_bridge import _artifact_payload
from content.tests.building_with_us_fixtures import confirm, contract_update, rpc_call

pytestmark = pytest.mark.django_db


def test_confirmed_initialization_creates_the_mirror(api_client, building_with_us_mcp, building_with_us_contract_folder):
    """Fails if initialization writes at preview or omits its folder dependency."""
    token, _ = building_with_us_mcp
    intent = rpc_call(api_client, token, 'initialize_building_with_us_contract_mirror',
                      {'folder_id': building_with_us_contract_folder.pk})['structuredContent']
    assert BuildingWithUsContractMirror.objects.count() == 0

    result = confirm(api_client, token, intent)['structuredContent']['result']

    assert intent['impact']['outcome'] == 'create'
    assert 'folder' in intent['impact']['resource_etags']
    assert result['outcome'] == 'create'
    assert result['mirror']['status'] == 'synchronized'
    assert Document.objects.get(pk=result['mirror']['document_id']).document_notes.count() == 2


def test_confirmed_update_synchronizes_the_mirror(api_client, building_with_us_mcp, initialized_building_with_us_mirror):
    """Fails if confirmation loses text, artifact, audit provenance or version note."""
    token, credential = building_with_us_mcp
    original = rpc_call(api_client, token, 'get_building_with_us_contract', {})['structuredContent']
    arguments = contract_update(original)
    preview = rpc_call(api_client, token, 'preview_building_with_us_contract_update', {'markdown': arguments['markdown']})['structuredContent']
    intent = rpc_call(api_client, token, 'update_building_with_us_contract', arguments)['structuredContent']
    assert service.read_contract()['version'] == 1

    result = confirm(api_client, token, intent)['structuredContent']['result']
    mirror = BuildingWithUsContractMirror.objects.get(pk=initialized_building_with_us_mirror.pk)

    assert preview['changed'] is True
    assert result['version'] == 2
    assert service.read_contract()['markdown'] == arguments['markdown']
    assert mirror.revision_id == result['version_id']
    assert BuildingWithUsContractRevision.objects.get(pk=result['version_id']).credential_id == credential.pk
    assert mirror.document.document_notes.last().title == 'Contrato Building with Us — versión 2'


@pytest.mark.parametrize('changed_resource', ['document', 'mirror'])
def test_confirmation_rejects_a_changed_mirror(api_client, building_with_us_mcp, initialized_building_with_us_mirror, changed_resource):
    """Fails if confirmation ignores the dependency state captured in its preview."""
    token, _ = building_with_us_mcp
    mirror = initialized_building_with_us_mirror
    before = service.read_contract()
    intent = rpc_call(api_client, token, 'update_building_with_us_contract', contract_update(before))['structuredContent']
    updates = {'document': lambda: Document.objects.filter(pk=mirror.document_id).update(folder=None),
               'mirror': lambda: BuildingWithUsContractMirror.objects.filter(pk=mirror.pk).update(synced_at=mirror.synced_at.replace(year=2000))}
    updates[changed_resource]()

    result = confirm(api_client, token, intent)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert service.read_contract()['version_id'] == before['version_id']
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_render_returns_a_downloadable_artifact(api_client, building_with_us_mcp, building_with_us_contract):
    """Fails if the contract PDF tool cannot issue a signed, usable private download."""
    token, _ = building_with_us_mcp

    result = rpc_call(api_client, token, 'render_building_with_us_contract_pdf', {})
    artifact = result['structuredContent']
    url = urlsplit(artifact['download_url'])
    response = APIClient().get(url.path + '?' + url.query)

    assert result['isError'] is False
    assert artifact['filename'] == 'contrato-building-with-us-v1.pdf'
    assert artifact['content_type'] == 'application/pdf'
    assert response.status_code == 200
    assert b''.join(response.streaming_content).startswith(b'%PDF-')


def test_initialization_confirmation_rejects_a_changed_folder(api_client, building_with_us_mcp, building_with_us_contract_folder):
    """Fails if an initialization preview can silently accept a renamed destination."""
    token, _ = building_with_us_mcp
    folder = building_with_us_contract_folder
    intent = rpc_call(api_client, token, 'initialize_building_with_us_contract_mirror', {'folder_id': folder.pk})['structuredContent']
    folder.name = 'Otro destino'
    folder.save(update_fields=['name', 'updated_at'])

    result = confirm(api_client, token, intent)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert BuildingWithUsContractMirror.objects.count() == 0


def test_confirmed_restore_records_the_source_version(api_client, building_with_us_mcp, initialized_building_with_us_mirror, admin_user):
    """Fails if the restore tool rewrites the original or omits its version number."""
    token, _ = building_with_us_mcp
    original = service.read_contract()
    service.apply_update(contract_update(original), actor=admin_user)
    intent = rpc_call(api_client, token, 'restore_building_with_us_contract_version', {
        'version_id': original['version_id'], 'if_match': service.read_contract()['etag'], 'change_note': 'Restaurar la versión inicial.',
    })['structuredContent']

    result = confirm(api_client, token, intent)['structuredContent']['result']
    versions = rpc_call(api_client, token, 'list_building_with_us_contract_versions', {'include_content': True})['structuredContent']

    assert result['version'] == 3
    assert versions['versions'][0]['restored_from_version'] == 1
    assert versions['versions'][0]['restored_from_version_id'] == original['version_id']
    assert versions['versions'][0]['markdown'] == original['markdown']
    assert result['mirror']['status'] == 'synchronized'


def test_artifact_adapter_preserves_the_request(building_with_us_mcp, initialized_building_with_us_mirror):
    """Fails if an internal file response finishes the enclosing MCP request."""
    _, credential = building_with_us_mcp
    stream = BytesIO(bytes(initialized_building_with_us_mirror.pdf_content))
    response = FileResponse(stream, content_type='application/pdf', filename='contract.pdf')
    finished = []
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='artifact-lifecycle-test', actor=credential.actor)

    def record_finished(sender, **kwargs):
        finished.append(sender)

    request_finished.connect(record_finished, weak=False)
    try:
        with use_mcp_context(context):
            artifact = _artifact_payload(response, {'name': 'render_building_with_us_contract_pdf'})
    finally:
        request_finished.disconnect(record_finished)

    assert finished == []
    assert stream.closed is True
    assert response.closed is True
    assert artifact['filename'] == 'contract.pdf'
