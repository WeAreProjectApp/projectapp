"""Real MCP resource writes retain the Platform lifecycle and scoped assets."""
import base64
import hashlib
import io
import zipfile
from datetime import timedelta

import pytest
from accounts.models import (
    Deliverable,
    DeliverableVersion,
    Project,
    ProjectDataModelEntity,
)
from accounts.services import platform_resources
from accounts.services.delivery_access import DeliveryConflict
from django.core.files.base import ContentFile
from django.utils import timezone

from content.mcp.upload_tools import _validate_declared_content
from content.models import McpActionIntent, McpConnector, McpUpload
from content.tests.views.test_mcp_delivery import SIGNED_PDF, confirm
from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects,  # noqa: PLC0414
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def project(django_user_model):
    return Project.objects.create(name='Recursos', client=django_user_model.objects.create_user('resource-owner'))


@pytest.fixture
def asset(call_projects):
    connector = McpConnector.objects.get(slug='projects')
    return McpUpload.objects.create(connector=connector, credential=connector.credentials.get(label='Default'),
        filename='manual.pdf', content_type='application/pdf', expected_size=len(SIGNED_PDF),
        expected_sha256=hashlib.sha256(SIGNED_PDF).hexdigest(), received_size=len(SIGNED_PDF),
        status=McpUpload.STATUS_COMPLETE, file=ContentFile(SIGNED_PDF, name='manual.pdf'),
        expires_at=timezone.now() + timedelta(minutes=10))


def arguments(project, asset):
    return {'project_id': project.pk, 'asset_id': str(asset.pk), 'expected_version': 0,
            'request_id': 'resource-create', 'data': {'title': 'Manual', 'category': 'documents'}}


def test_resource_preview_preserves_the_database(call_projects, project, asset):
    preview = call_projects('create_project_resource', arguments(project, asset))
    assert preview['confirmation_required'] is True
    assert Deliverable.objects.filter(project=project).count() == 0
    asset.refresh_from_db()
    assert asset.status == McpUpload.STATUS_COMPLETE


def test_resource_confirmation_records_the_service_actor(call_projects, project, asset):
    result = confirm(call_projects, 'create_project_resource', arguments(project, asset))['result']['result']
    resource = Deliverable.objects.get(pk=result['id'])
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    assert resource.uploaded_by_id == credential.actor_id
    assert resource.current_version == 1
    assert resource.versions.count() == 1
    assert 'file_url' not in result


def test_resource_confirmation_replay_preserves_one_resource(call_projects, project, asset):
    preview = call_projects('create_project_resource', arguments(project, asset))
    payload = {'confirmation_id': preview['confirmation_id']}
    call_projects('confirm_action', payload)
    second = call_projects('confirm_action', payload)
    assert second['replayed'] is True
    assert Deliverable.objects.filter(project=project).count() == 1


def test_resource_version_preserves_the_previous_bytes(call_projects, project, asset, superuser):
    resource = Deliverable.objects.create(project=project, uploaded_by=superuser,
        title='Manual', category='documents', file=ContentFile(b'old bytes', name='old.pdf'))
    version = DeliverableVersion.objects.create(deliverable=resource, uploaded_by=superuser,
        version_number=1, file=ContentFile(b'old bytes', name='old.pdf'))
    result = confirm(call_projects, 'upload_project_resource_version', {
        'project_id': project.pk, 'resource_id': resource.pk, 'asset_id': str(asset.pk),
        'expected_version': 0, 'request_id': 'new-version'})
    resource.refresh_from_db()
    assert resource.current_version == 2
    with version.file.open('rb') as source:
        assert source.read() == b'old bytes'
    assert result['result']['version'] == 1


def test_resource_archive_preserves_the_file(call_projects, project, superuser):
    resource = Deliverable.objects.create(project=project, uploaded_by=superuser,
        title='Manual', file=ContentFile(SIGNED_PDF, name='manual.pdf'))
    confirm(call_projects, 'archive_project_resource', {'project_id': project.pk,
        'resource_id': resource.pk, 'expected_version': 0, 'request_id': 'archive'})
    resource.refresh_from_db()
    assert resource.is_archived is True
    with resource.file.open('rb') as source:
        assert source.read() == SIGNED_PDF


def test_resource_download_rejects_a_foreign_project(call_projects, project, superuser, django_user_model):
    other = Project.objects.create(name='Ajeno', client=django_user_model.objects.create_user('other-owner'))
    resource = Deliverable.objects.create(project=other, title='Ajeno', uploaded_by=superuser)
    error = call_projects('download_project_resource_file', {
        'project_id': project.pk, 'resource_id': resource.pk}, expect_error=True)
    assert error['code'] == 'NOT_FOUND'


def test_resource_download_returns_exact_bytes(call_projects, project, superuser, api_client):
    resource = Deliverable.objects.create(project=project, title='Manual', uploaded_by=superuser,
        file=ContentFile(SIGNED_PDF, name='manual.pdf'))
    artifact = call_projects('download_project_resource_file', {'project_id': project.pk, 'resource_id': resource.pk})
    response = api_client.get(artifact['download_url'])
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == SIGNED_PDF
    response.close()


def test_client_cannot_edit_a_resource(project, superuser):
    resource = Deliverable.objects.create(project=project, uploaded_by=superuser, title='Original')
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        platform_resources.update_resource(project.pk, project.client, resource.pk, {'title': 'Changed'})
    resource.refresh_from_db()
    assert resource.title == 'Original'


def test_resource_scope_rejects_an_ungranted_tool(call_projects, project):
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    credential.allowed_tools = ['list_project_resources']
    credential.save(update_fields=['allowed_tools'])
    error = call_projects('get_project_data_model', {'project_id': project.pk}, expect_error=True)
    assert error['code'] == 'FORBIDDEN'


def test_resource_create_rejects_a_read_only_field(call_projects, project, asset):
    payload = arguments(project, asset)
    payload['data']['uploaded_by'] = project.client_id
    error = call_projects('create_project_resource', payload, expect_error=True)
    assert error['code'] == 'VALIDATION_ERROR'
    assert not McpActionIntent.objects.filter(tool_name='create_project_resource').exists()


def test_data_model_preview_preserves_the_existing_entities(call_projects, project):
    original = ProjectDataModelEntity.objects.create(project=project, name='Original')
    preview = call_projects('preview_project_data_model', {'project_id': project.pk,
        'expected_version': 0, 'data': {'entities': [{'name': 'Replacement'}]}})
    assert preview['after'][0]['name'] == 'Replacement'
    assert ProjectDataModelEntity.objects.get(pk=original.pk).name == 'Original'


def test_data_model_import_replaces_the_reviewed_entities(call_projects, project):
    ProjectDataModelEntity.objects.create(project=project, name='Original')
    confirm(call_projects, 'import_project_data_model', {'project_id': project.pk,
        'expected_version': 0, 'request_id': 'model', 'data': {'entities': [{'name': 'Replacement'}]}})
    assert list(ProjectDataModelEntity.objects.filter(project=project).values_list('name', flat=True)) == ['Replacement']


def test_data_model_import_rejects_a_changed_workspace(call_projects, project, asset):
    preview = call_projects('import_project_data_model', {'project_id': project.pk,
        'expected_version': 0, 'request_id': 'model', 'data': {'entities': [{'name': 'Replacement'}]}})
    confirm(call_projects, 'create_project_resource', arguments(project, asset))
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert ProjectDataModelEntity.objects.filter(project=project).count() == 0


def test_resource_confirmation_rejects_a_changed_owner(call_projects, project, asset, django_user_model):
    preview = call_projects('create_project_resource', arguments(project, asset))
    project.client = django_user_model.objects.create_user('new-resource-owner')
    project.save(update_fields=['client'])
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert Deliverable.objects.filter(project=project).count() == 0


def test_resource_write_revalidates_owner_inside_the_lock(project, superuser):
    resource = Deliverable.objects.create(project=project, title='Original', uploaded_by=superuser)
    with pytest.raises(DeliveryConflict):
        platform_resources.update_resource(project.pk, superuser, resource.pk, {'title': 'Changed'},
            expected_version=0, expected_client_id=project.client_id + 1)
    resource.refresh_from_db()
    assert resource.title == 'Original'


def _zip_bytes(name):
    target = io.BytesIO()
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr(name, b'Illustration source')
    return target.getvalue()


def test_design_zip_is_accepted_by_projects(call_projects):
    body = _zip_bytes('design.svg')
    upload = call_projects('begin_upload', {'filename': 'design.zip', 'content_type': 'application/zip',
        'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
    call_projects('upload_asset_chunk', {'asset_id': upload['asset_id'], 'index': 0,
        'base64': base64.b64encode(body).decode(), 'chunk_sha256': hashlib.sha256(body).hexdigest()})
    completed = call_projects('complete_upload', {'asset_id': upload['asset_id']})
    assert completed['status'] == McpUpload.STATUS_COMPLETE


@pytest.mark.parametrize('name', ['../private.pdf', '/private.pdf'])
def test_design_zip_rejects_unsafe_paths(call_projects, asset, name):
    from content.mcp.protocol import ToolError
    asset.file.save('unsafe.zip', ContentFile(_zip_bytes(name)), save=False)
    asset.content_type = 'application/zip'
    with pytest.raises(ToolError, match='ZIP permitido'):
        _validate_declared_content(asset)
