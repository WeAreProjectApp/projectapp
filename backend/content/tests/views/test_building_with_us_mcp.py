"""Real credential-bound MCP preview, confirmation, restoration and PDF transport."""
from urllib.parse import urlsplit

import pytest
from rest_framework.test import APIClient

from content.models import BuildingWithUsProgramRevision, McpActionIntent, McpUpload
from content.services import building_with_us_program_service as service
from content.tests.building_with_us_fixtures import confirm, hero_update, rpc_call

pytestmark = pytest.mark.django_db


def test_connector_catalog_requires_confirmation(api_client, building_with_us_mcp):
    """Fails if this connector gains uploads/videos or loses its mutation confirmation."""
    token, _ = building_with_us_mcp

    response = api_client.post(f'/api/mcp/building-with-us/{token}/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json')
    names = {tool['name'] for tool in response.data['result']['tools']}
    catalog = rpc_call(api_client, token, 'describe_capabilities', {})['structuredContent']
    tools = {tool['name']: tool for tool in catalog['tools']}

    assert len(names) == 16
    assert not any('video' in name or 'upload' in name for name in names)
    assert tools['update_building_with_us_program']['requires_confirmation'] is True
    assert tools['restore_building_with_us_program_version']['requires_confirmation'] is True
    assert tools['render_building_with_us_program_pdf']['risk'] == 'read'
    assert catalog['version'] == '1.0.0'


def test_confirmation_publishes_a_new_version(api_client, building_with_us_program, building_with_us_mcp, monkeypatch, django_capture_on_commit_callbacks):
    """Fails if preview writes early or confirmed publication omits its rebuild request."""
    token, credential = building_with_us_mcp
    original = rpc_call(api_client, token, 'get_building_with_us_program', {})['structuredContent']
    arguments = hero_update(original)
    calls = []
    monkeypatch.setattr(service, 'schedule_rebuild_after_publish', lambda **kwargs: calls.append(kwargs))
    preview = rpc_call(api_client, token, 'preview_building_with_us_program_update', {'sections': arguments['sections']})['structuredContent']
    intent = rpc_call(api_client, token, 'update_building_with_us_program', arguments)['structuredContent']
    assert service.read_program()['version'] == 1

    with django_capture_on_commit_callbacks(execute=True):
        confirmed = confirm(api_client, token, intent)
    public = APIClient().get('/api/building-with-us/public/').data

    assert preview['changed'] is True
    assert confirmed['structuredContent']['result']['version'] == 2
    assert public['hero']['title'] == arguments['sections']['hero']['es']['title']
    assert public['version'] == 2
    assert BuildingWithUsProgramRevision.objects.get(version=2).credential_id == credential.pk
    assert calls == [{'reason': 'building-with-us'}]


def test_confirmation_rejects_a_later_change(api_client, building_with_us_program, building_with_us_mcp, admin_user):
    """Fails if an outdated intent overwrites a publication made after its preview."""
    token, _ = building_with_us_mcp
    original = service.read_program()
    arguments = hero_update(original)
    intent = rpc_call(api_client, token, 'update_building_with_us_program', arguments)['structuredContent']
    service.apply_update(arguments, actor=admin_user)

    result = confirm(api_client, token, intent)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert BuildingWithUsProgramRevision.objects.count() == 2


def test_missing_change_note_creates_no_intent(api_client, building_with_us_program, building_with_us_mcp):
    """Fails if publication without an audit explanation reaches durable confirmation."""
    token, credential = building_with_us_mcp
    arguments = hero_update(service.read_program())
    arguments.pop('change_note')

    result = rpc_call(api_client, token, 'update_building_with_us_program', arguments)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert McpActionIntent.objects.filter(credential=credential).count() == 0
    assert BuildingWithUsProgramRevision.objects.count() == 1


def test_confirmed_restore_records_its_source(api_client, changed_building_with_us_program, building_with_us_mcp):
    """Fails if MCP restoration destroys history or fails to reinstate the chosen content."""
    token, _ = building_with_us_mcp
    versions = rpc_call(api_client, token, 'list_building_with_us_program_versions', {'include_content': True})['structuredContent']
    current = service.read_program()
    intent = rpc_call(api_client, token, 'restore_building_with_us_program_version', {
        'version_id': changed_building_with_us_program['version_id'], 'if_match': current['etag'], 'change_note': 'Restaurar la presentación inicial.',
    })['structuredContent']

    result = confirm(api_client, token, intent)['structuredContent']['result']
    revision = BuildingWithUsProgramRevision.objects.get(pk=result['version_id'])

    assert versions['total'] == 2
    assert versions['versions'][1]['content'] == changed_building_with_us_program['content']
    assert revision.version == 3
    assert revision.restored_from_id == changed_building_with_us_program['version_id']
    assert service.read_program()['content'] == changed_building_with_us_program['content']


def test_render_returns_a_downloadable_artifact(api_client, building_with_us_program, building_with_us_mcp):
    """Fails if the read-only PDF tool cannot issue a signed, usable download."""
    token, _ = building_with_us_mcp

    result = rpc_call(api_client, token, 'render_building_with_us_program_pdf', {'lang': 'en'})
    artifact = result['structuredContent']
    url = urlsplit(artifact['download_url'])
    response = APIClient().get(url.path + '?' + url.query)
    content = b''.join(response.streaming_content)

    assert result['isError'] is False
    assert artifact['filename'] == 'building-with-us-en.pdf'
    assert artifact['content_type'] == 'application/pdf'
    assert response.status_code == 200
    assert content.startswith(b'%PDF-')


@pytest.mark.parametrize('language', ['fr', ['es'], None, True])
def test_render_rejects_invalid_language_values(api_client, building_with_us_mcp, language):
    """Fails if the GET adapter coerces invalid input into a valid PDF request."""
    token, credential = building_with_us_mcp

    result = rpc_call(api_client, token, 'render_building_with_us_program_pdf', {'lang': language})

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'INVALID_LANGUAGE'
    assert result['structuredContent']['error']['message'] == 'Usa es o en.'
    assert result['structuredContent']['error']['details'] == {'path': 'lang'}
    assert McpUpload.objects.filter(credential=credential).count() == 0
