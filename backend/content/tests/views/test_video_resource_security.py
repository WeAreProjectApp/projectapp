"""Security boundaries for the commercial-video MCP and HTTP delivery."""
import base64
import hashlib

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.test import APIClient

from content.models import McpConnector, McpCredential, McpUpload, VideoResource


pytestmark = pytest.mark.django_db


def _rpc(method, params=None):
    message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, slug, token, name, arguments):
    response = api_client.post(
        f'/api/mcp/{slug}/{token}/',
        _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )
    assert response.status_code == 200
    return response.data['result']


@pytest.fixture
def partnership_connector():
    connector, _ = McpConnector.objects.get_or_create(
        slug='partnership-program',
        defaults={'name': 'Programa de Alianza'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


def _uploaded_financing_resource(revision=3):
    resource = VideoResource(
        key='financing:es', module='financing', language='es', mode='uploaded',
        filename='previous.mp4', size=8, sha256='a' * 64, revision=revision,
    )
    resource.file.save('previous.mp4', ContentFile(b'previous'), save=False)
    resource.save()
    return resource


@pytest.mark.parametrize(
    ('slug', 'tool_name', 'target'),
    [
        ('partnership-program', 'set_partnership_program_video', 'language'),
        ('additional-modules', 'set_additional_modules_video', 'language'),
        ('proposals', 'set_proposal_generic_video', 'language'),
        ('proposals', 'set_proposal_personalized_video', 'proposal_id'),
    ],
)
def test_video_tools_list_assignable_target_and_revision(api_client, slug, tool_name, target):
    """Fails if a published video tool cannot identify both its target and revision."""
    connector, _ = McpConnector.objects.get_or_create(
        slug=slug, defaults={'name': slug},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()

    response = api_client.post(
        f'/api/mcp/{slug}/{token}/', _rpc('tools/list'), format='json',
    )

    tools = {tool['name']: tool for tool in response.data['result']['tools']}
    properties = tools[tool_name]['inputSchema']['properties']
    assert set(('asset_id', 'revision', target)) <= set(properties)


def test_mcp_rejects_foreign_video_asset_without_changing_resource(
    api_client, partnership_connector,
):
    """Fails if another credential can replace a published video with its private asset."""
    connector, owner_token = partnership_connector
    foreign_credential = McpCredential.objects.create(
        connector=connector,
        label='Foreign video owner',
        token_hash=McpCredential.hash_token('foreign-video-token'),
    )
    foreign_token = foreign_credential.generate_token()
    resource = _uploaded_financing_resource()
    previous_file = resource.file.name
    pending = _call(api_client, 'partnership-program', owner_token, 'begin_upload', {
        'filename': 'pending.mp4', 'content_type': 'video/mp4', 'size': 1,
        'sha256': hashlib.sha256(b'x').hexdigest(),
    })['structuredContent']

    foreign = _call(
        api_client, 'partnership-program', foreign_token,
        'set_partnership_program_video', {
            'language': 'es', 'asset_id': pending['asset_id'], 'revision': 3,
        },
    )
    resource.refresh_from_db()
    assert foreign['structuredContent']['error']['code'] == 'NOT_FOUND'
    assert resource.revision == 3
    assert resource.file.name == previous_file
    assert VideoResource.objects.filter(key='financing:es').count() == 1


def test_mcp_rejects_pending_video_asset_without_changing_resource(
    api_client, partnership_connector,
):
    """Fails if an incomplete upload can replace a published video."""
    _, token = partnership_connector
    resource = _uploaded_financing_resource()
    previous_file = resource.file.name
    pending = _call(api_client, 'partnership-program', token, 'begin_upload', {
        'filename': 'pending.mp4', 'content_type': 'video/mp4', 'size': 1,
        'sha256': hashlib.sha256(b'x').hexdigest(),
    })['structuredContent']

    incomplete = _call(
        api_client, 'partnership-program', token,
        'set_partnership_program_video', {
            'language': 'es', 'asset_id': pending['asset_id'], 'revision': 3,
        },
    )

    resource.refresh_from_db()
    assert incomplete['structuredContent']['error']['code'] == 'CONFLICT'
    assert resource.revision == 3
    assert resource.file.name == previous_file


def test_mcp_rejects_invalid_video_completion_without_replacing_resource(
    api_client, partnership_connector,
):
    """Fails if corrupt MP4 bytes can replace an already published video through MCP."""
    _, token = partnership_connector
    resource = _uploaded_financing_resource(revision=4)
    previous_file = resource.file.name
    invalid_bytes = b'not an MP4 stream'
    upload = _call(api_client, 'partnership-program', token, 'begin_upload', {
        'filename': 'corrupt.mp4', 'content_type': 'video/mp4',
        'size': len(invalid_bytes),
        'sha256': hashlib.sha256(invalid_bytes).hexdigest(),
    })['structuredContent']
    chunk = _call(api_client, 'partnership-program', token, 'upload_asset_chunk', {
        'asset_id': upload['asset_id'], 'index': 0,
        'base64': base64.b64encode(invalid_bytes).decode('ascii'),
        'chunk_sha256': hashlib.sha256(invalid_bytes).hexdigest(),
    })
    completion = _call(
        api_client, 'partnership-program', token, 'complete_upload',
        {'asset_id': upload['asset_id']},
    )
    assignment = _call(
        api_client, 'partnership-program', token,
        'set_partnership_program_video', {
            'language': 'es', 'asset_id': upload['asset_id'], 'revision': 4,
        },
    )

    resource.refresh_from_db()
    upload_row = McpUpload.objects.get(pk=upload['asset_id'])
    assert chunk['structuredContent']['received_size'] == len(invalid_bytes)
    assert completion['structuredContent']['error']['code'] == 'INVALID_FILE_CONTENT'
    assert assignment['structuredContent']['error']['code'] == 'CONFLICT'
    assert upload_row.status == McpUpload.STATUS_PENDING
    assert resource.revision == 4
    assert resource.file.name == previous_file
    assert resource.sha256 == 'a' * 64


@pytest.mark.parametrize('method, payload', [
    ('get', None),
    ('post', {'action': 'remove', 'revision': 0}),
])
def test_non_staff_cannot_read_or_write_module_videos(django_user_model, method, payload):
    """Fails if an authenticated non-admin can inspect or alter module videos."""
    user = django_user_model.objects.create_user('video-reader', password='test-only')
    client = APIClient()
    client.force_authenticate(user)

    response = getattr(client, method)(
        '/api/video-resources/admin/modules/financing/es/', payload, format='json',
    )

    assert response.status_code == 403


@pytest.mark.parametrize('range_header', ['bytes=0-1,3-4', 'bytes=99-100'])
def test_video_delivery_rejects_invalid_ranges(range_header):
    """Fails if malformed or unsatisfiable ranges produce a playable partial response."""
    resource = _uploaded_financing_resource(revision=1)
    response = APIClient().get(
        f'/api/video-resources/{resource.pk}/1/video/', HTTP_RANGE=range_header,
    )

    assert response.status_code == 416
    assert response['Content-Range'] == 'bytes */8'
