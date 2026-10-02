"""Signed MCP upload and download URLs remain bound to one live credential and asset."""
import hashlib
from urllib.parse import urlsplit

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIRequestFactory

from content.mcp.context import McpExecutionContext, use_mcp_context
from accounts.tests.delivery_helpers import RECORDED_AT
from content.mcp.upload_tools import begin_upload, store_artifact
from content.models import McpConnector, McpUpload


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fixed_business_clock():
    with freeze_time(RECORDED_AT):
        yield


@pytest.fixture
def transfer_context():
    connector, _ = McpConnector.objects.get_or_create(
        slug='signed-transfer-tests', defaults={'name': 'Signed transfers'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    connector.generate_token()
    return McpExecutionContext(
        connector=connector, credential=connector.credentials.get(label='Default'),
        request_id='signed-transfer-request',
        request=APIRequestFactory().get('/', HTTP_HOST='testserver'),
    )


def reserve(context, body=b'asset body'):
    with use_mcp_context(context):
        return begin_upload({
            'filename': 'evidence.txt', 'content_type': 'text/plain', 'size': len(body),
            'sha256': hashlib.sha256(body).hexdigest(),
        })


def invalid_signature_path(url):
    head, _signature, _empty = urlsplit(url).path.rsplit('/', 2)
    return f'{head}/invalid-signature/'


def _tampered_upload(api_client, context, body):
    reserved = reserve(context, body)
    asset = McpUpload.objects.get(pk=reserved['asset_id'])
    return api_client.put(invalid_signature_path(reserved['upload_url']), body, content_type='text/plain'), asset, (McpUpload.STATUS_PENDING, 0, False)


def _tampered_download(api_client, context, body):
    with use_mcp_context(context):
        artifact = store_artifact(connector=context.connector, credential=context.credential, filename='evidence.txt', content_type='text/plain', content=body, request=context.request)
    asset = McpUpload.objects.get(pk=artifact['asset_id'])
    return api_client.get(invalid_signature_path(artifact['download_url'])), asset, (McpUpload.STATUS_COMPLETE, len(body), True)


@pytest.mark.parametrize('scenario', [_tampered_upload, _tampered_download], ids=['upload', 'download'])
def test_tampered_signed_transfer_rejects_without_changing_asset(api_client, transfer_context, scenario):
    """Fails if changing a signed URL can write or read an asset belonging to the credential."""
    body = b'captured evidence'
    response, asset, expected = scenario(api_client, transfer_context, body)

    asset.refresh_from_db()
    assert response.status_code == 404
    assert (asset.status, asset.received_size, bool(asset.file)) == expected


def _retargeted_upload(api_client, context, first_body, second_body):
    first, second = reserve(context, first_body), reserve(context, second_body)
    target = McpUpload.objects.get(pk=second['asset_id'])
    response = api_client.put(urlsplit(first['upload_url']).path.replace(first['asset_id'], second['asset_id']), first_body, content_type='text/plain')
    return response, target, (McpUpload.STATUS_PENDING, 0, False)


def _retargeted_download(api_client, context, first_body, second_body):
    with use_mcp_context(context):
        first = store_artifact(connector=context.connector, credential=context.credential, filename='first.txt', content_type='text/plain', content=first_body, request=context.request)
        second = store_artifact(connector=context.connector, credential=context.credential, filename='second.txt', content_type='text/plain', content=second_body, request=context.request)
    target = McpUpload.objects.get(pk=second['asset_id'])
    response = api_client.get(urlsplit(first['download_url']).path.replace(first['asset_id'], second['asset_id']))
    return response, target, (McpUpload.STATUS_COMPLETE, len(second_body), True)


@pytest.mark.parametrize('scenario', [_retargeted_upload, _retargeted_download], ids=['upload', 'download'])
def test_signed_transfer_cannot_be_retargeted_to_another_asset(api_client, transfer_context, scenario):
    """Fails if a valid signed URL for asset A can access or replace asset B."""
    first_body, second_body = b'first evidence', b'second evidence'
    response, target, expected = scenario(api_client, transfer_context, first_body, second_body)

    target.refresh_from_db()
    assert response.status_code == 404
    assert (target.status, target.received_size, bool(target.file)) == expected


def _revoked_upload(api_client, context, body):
    item = reserve(context, body)
    asset = McpUpload.objects.get(pk=item['asset_id'])
    context.credential.revoked_at = timezone.now()
    context.credential.save(update_fields=['revoked_at'])
    return api_client.put(urlsplit(item['upload_url']).path, body, content_type='text/plain'), asset, (409, McpUpload.STATUS_PENDING, 0)


def _revoked_download(api_client, context, body):
    with use_mcp_context(context):
        item = store_artifact(connector=context.connector, credential=context.credential, filename='artifact.txt', content_type='text/plain', content=body, request=context.request)
    asset = McpUpload.objects.get(pk=item['asset_id'])
    context.credential.revoked_at = timezone.now()
    context.credential.save(update_fields=['revoked_at'])
    return api_client.get(urlsplit(item['download_url']).path), asset, (410, McpUpload.STATUS_COMPLETE, len(body))


@pytest.mark.parametrize('scenario', [_revoked_upload, _revoked_download], ids=['upload', 'download'])
def test_revoked_credential_invalidates_live_signed_transfer(api_client, transfer_context, scenario):
    """Fails if revoking a credential leaves an unexpired signed upload or download usable."""
    body = b'credential-bound artifact'
    response, asset, expected = scenario(api_client, transfer_context, body)

    asset.refresh_from_db()
    assert (response.status_code, asset.status, asset.received_size) == expected


def test_second_signed_put_preserves_the_first_uploaded_bytes(api_client, transfer_context):
    """Fails if a second signed PUT can replace bytes before the upload is completed."""
    original, replacement = b'original evidence', b'changedx evidence'
    reserved = reserve(transfer_context, original)
    url = urlsplit(reserved['upload_url']).path

    first = api_client.put(url, original, content_type='text/plain')
    second = api_client.put(url, replacement, content_type='text/plain')

    asset = McpUpload.objects.get(pk=reserved['asset_id'])
    with asset.file.open('rb') as source:
        stored = source.read()
    assert (first.status_code, second.status_code) == (200, 409)
    assert (stored, asset.expected_sha256, asset.next_chunk_index) == (
        original, hashlib.sha256(original).hexdigest(), 1,
    )
