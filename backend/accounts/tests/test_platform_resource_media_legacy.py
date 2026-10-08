"""Legacy bytes remain authorized during conversion, including retained files."""
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test import Client, override_settings

from accounts.services.platform_media_migration import privatize, write_inventory
from accounts.tests.platform_media_helpers import (
    KINDS,
    api_for,
    download_url,
    legacy_files,
    manifest_path,
    response_bytes,
    retain_files,
    retained_url,
)
from accounts.tests.platform_media_helpers import media_context as media_context

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('kind', KINDS)
def test_legacy_file_download_preserves_its_original_bytes(media_context, kind):
    """Fails if switching storage reinterprets any historical persisted name."""
    legacy_files(media_context)
    response = api_for(media_context['owner']).get(download_url(media_context, kind))
    assert response.status_code == 200
    assert response_bytes(response) == media_context['bodies'][kind]


def test_legacy_file_never_reads_a_private_shadow(media_context):
    """Fails if a same-named private file replaces the public historical source."""
    legacy_files(media_context)
    storages['private'].save(media_context['resource'].file.name, ContentFile(b'wrong private shadow'))
    response = api_for(media_context['owner']).get(download_url(media_context, 'current'))
    assert response_bytes(response) == media_context['bodies']['current']


@pytest.mark.parametrize('kind', KINDS)
def test_retained_session_download_reads_the_legacy_original(media_context, kind):
    """Fails if detached parents or descendants become unreadable before conversion."""
    retain_files(legacy_files(media_context))
    client = Client()
    client.force_login(media_context['admin'])
    response = client.get(retained_url(media_context, kind))
    assert response.status_code == 200
    assert response_bytes(response) == media_context['bodies'][kind]


@pytest.mark.parametrize('kind', KINDS)
def test_retained_session_download_reads_the_verified_private_copy(media_context, kind, tmp_path):
    """Fails if conversion skips retained children or breaks their session route."""
    retain_files(legacy_files(media_context))
    path = manifest_path(tmp_path.name)
    inventory = write_inventory(path)
    result = privatize(path, inventory['manifest_sha256'], apply=True)
    client = Client()
    client.force_login(media_context['admin'])
    response = client.get(retained_url(media_context, kind))
    assert result['converted'] == 4
    assert response.status_code == 200
    assert response_bytes(response) == media_context['bodies'][kind]


def test_retained_file_keeps_its_existing_session_permission(media_context):
    """Fails if the neutral reader replaces the Panel staff guard with Platform role."""
    retain_files(legacy_files(media_context))
    profile = media_context['foreign'].profile
    profile.role = 'admin'
    profile.save(update_fields=['role'])
    client = Client()
    client.force_login(media_context['foreign'])
    response = client.get(retained_url(media_context, 'current'))
    assert response.status_code == 403


def test_debug_media_server_denies_the_original_public_path(media_context):
    """Fails if Django DEBUG serves legacy bytes despite the nginx deployment rule."""
    legacy_files(media_context)
    with override_settings(DEBUG=True):
        response = Client().get(f'/media/{media_context["resource"].file.name}')
    assert response.status_code == 404
    assert response.content == b''
