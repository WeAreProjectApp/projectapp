"""Exact file selection stays parent-bound and exposes only relative API URLs."""
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.forms.widgets import ClearableFileInput
from rest_framework.test import APIRequestFactory

from accounts.models import Deliverable
from accounts.serializers import (
    DeliverableClientUploadSerializer,
    DeliverableFileSerializer,
    DeliverableListSerializer,
    DeliverableVersionSerializer,
)
from accounts.services.platform_media_migration import privatize, write_inventory
from accounts.tests.platform_media_helpers import (
    KINDS,
    api_for,
    download_url,
    legacy_files,
    manifest_path,
    other_resource_child,
    response_bytes,
    retain_files,
    retained_url,
)
from accounts.tests.platform_media_helpers import media_context as media_context

pytestmark = pytest.mark.django_db
SERIALIZERS = {'current': DeliverableListSerializer, 'version': DeliverableVersionSerializer,
              'attachment': DeliverableFileSerializer, 'client_upload': DeliverableClientUploadSerializer}


@pytest.mark.parametrize('file_id', ['', '0', '-1', 'bad', '１２', '9' * 19])
def test_resource_child_download_rejects_an_invalid_file_id(media_context, file_id):
    """Fails if malformed ids reach an unbounded or coercing ORM lookup."""
    url = download_url(media_context, 'version').split('?')[0] + f'?file_id={file_id}'
    response = api_for(media_context['owner']).get(url)
    assert response.status_code == 400


@pytest.mark.parametrize('kind', ['version', 'attachment', 'client_upload'])
def test_resource_download_rejects_a_child_of_another_resource(media_context, kind):
    """Fails if a same-project child id bypasses its actual parent resource."""
    child = other_resource_child(media_context, kind)
    url = download_url(media_context, kind).split('?')[0] + f'?file_id={child.pk}'
    response = api_for(media_context['owner']).get(url)
    assert response.status_code == 404


@pytest.mark.parametrize('kind', KINDS)
def test_resource_file_url_remains_relative_to_the_authenticated_api(media_context, kind):
    """Fails if a host or storage URL is introduced into a bearer download DTO."""
    request = APIRequestFactory().get('/', HTTP_HOST='unrelated-origin.example.test')
    data = SERIALIZERS[kind](media_context['rows'][kind], context={'request': request}).data
    assert data['file_url'] == download_url(media_context, kind)
    assert data['file_url'].startswith('/api/accounts/')


def test_current_resource_download_rejects_a_child_selection(media_context):
    """Fails if a current-file request silently accepts an unrelated child id."""
    response = api_for(media_context['owner']).get(download_url(media_context, 'current') + '?file_id=1')
    assert response.status_code == 400


def test_resource_download_rejects_an_unknown_file_kind(media_context):
    """Fails if a kind becomes an arbitrary relation or storage selector."""
    url = download_url(media_context, 'current').replace('/current/', '/unknown/')
    response = api_for(media_context['owner']).get(url)
    assert response.status_code == 400


def test_inventory_converts_retained_children_without_a_parent_file(media_context, tmp_path):
    """Fails if inventory only walks live projects or parents with current files."""
    retain_files(legacy_files(media_context))
    Deliverable._base_manager.filter(pk=media_context['resource'].pk).update(file=None)
    path = manifest_path(tmp_path.name)
    inventory = write_inventory(path)
    result = privatize(path, inventory['manifest_sha256'], apply=True)
    from django.test import Client
    client = Client()
    client.force_login(media_context['admin'])
    response = client.get(retained_url(media_context, 'version'))
    assert inventory['files'] == 3
    assert result['converted'] == 3
    assert response_bytes(response) == media_context['bodies']['version']


def test_resource_download_rechecks_the_current_project_owner(media_context):
    """Fails if a previously issued JWT retains access after project reassignment."""
    api = api_for(media_context['owner'])
    project = media_context['project']
    project.client = media_context['foreign']
    project.save(update_fields=['client'])
    response = api.get(download_url(media_context, 'current'))
    assert response.status_code == 404


def test_resource_download_rejects_an_unrelated_storage_namespace(media_context):
    """Fails if resource pointers can read a different model's public directory."""
    name = storages['default'].save('avatars/unrelated.pdf', ContentFile(b'not a resource'))
    Deliverable._base_manager.filter(pk=media_context['resource'].pk).update(file=name)
    response = api_for(media_context['owner']).get(download_url(media_context, 'current'))
    assert response.status_code == 404


def test_admin_file_widget_renders_without_a_storage_download_link(media_context):
    """Fails if registered ModelAdmin widgets crash or publish private file names."""
    html = ClearableFileInput().render('file', media_context['resource'].file)
    assert 'type="file"' in html
    assert 'platform-resources/' not in html
    assert '/media/' not in html
