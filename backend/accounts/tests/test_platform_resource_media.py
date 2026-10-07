"""JWT resource downloads preserve exact bytes and real project authority."""
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from rest_framework.test import APIClient

from accounts.tests.platform_media_helpers import (
    KINDS,
    api_for,
    download_url,
    response_bytes,
)
from accounts.tests.platform_media_helpers import large_resource as large_resource
from accounts.tests.platform_media_helpers import media_context as media_context

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('kind', KINDS)
def test_new_resource_file_is_written_only_to_private_storage(media_context, kind):
    """Fails if any of the four families writes its new bytes into public media."""
    row = media_context['rows'][kind]
    assert row.file.name.startswith('platform-resources/')
    assert Path(row.file.path).read_bytes() == media_context['bodies'][kind]
    assert not (Path(settings.MEDIA_ROOT) / row.file.name).exists()


@pytest.mark.parametrize('kind', KINDS)
def test_resource_file_rejects_anonymous_download(media_context, kind):
    """Fails if any file family streams bytes before JWT authentication."""
    response = APIClient().get(download_url(media_context, kind))
    assert response.status_code == 401


@pytest.mark.parametrize('kind', KINDS)
def test_resource_owner_downloads_the_original_private_bytes(media_context, kind):
    """Fails if JWT downloads transform bytes or expose cacheable files."""
    response = api_for(media_context['owner']).get(download_url(media_context, kind))
    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert response['Content-Type'] == 'application/pdf'
    assert response_bytes(response) == media_context['bodies'][kind]


@pytest.mark.parametrize('kind', KINDS)
def test_resource_file_rejects_a_foreign_project_owner(media_context, kind):
    """Fails if a valid JWT bypasses the selected resource's project owner."""
    response = api_for(media_context['foreign']).get(download_url(media_context, kind))
    assert response.status_code == 404


def test_staff_client_cannot_download_an_archived_resource(media_context):
    """Fails if a Django staff flag widens a Platform client's archive access."""
    resource = media_context['resource']
    resource.is_archived = True
    resource.save(update_fields=['is_archived'])
    response = api_for(media_context['owner']).get(download_url(media_context, 'current'))
    assert response.status_code == 404


def test_platform_admin_can_download_an_archived_resource(media_context):
    """Fails if private storage removes an administrator's archived-file access."""
    resource = media_context['resource']
    resource.is_archived = True
    resource.save(update_fields=['is_archived'])
    response = api_for(media_context['admin']).get(download_url(media_context, 'current'))
    assert response_bytes(response) == media_context['bodies']['current']


def test_missing_private_file_never_reads_a_public_shadow(media_context):
    """Fails if a missing private pointer is reinterpreted as public media."""
    row = media_context['resource']
    storages['default'].save(row.file.name, ContentFile(b'public shadow'))
    storages['private'].delete(row.file.name)
    response = api_for(media_context['owner']).get(download_url(media_context, 'current'))
    assert response.status_code == 404


def test_jwt_download_streams_a_large_existing_resource(large_resource):
    """Fails if the MCP materialization limit is imposed on an authorized stream."""
    response = api_for(large_resource['owner']).get(download_url(large_resource, 'current'))
    assert response.status_code == 200
    assert int(response['Content-Length']) == 26 * 1024 * 1024 + 1
    assert next(response.streaming_content).startswith(large_resource['bodies']['current'])
    response.close()
