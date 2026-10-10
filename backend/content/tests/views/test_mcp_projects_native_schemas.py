"""Native projects contracts retain their services after resource arguments flatten."""

import hashlib
import io
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from accounts.models import (
    Deliverable,
    DeliverableClientFolder,
    DeliverableClientUpload,
    DeliverableFile,
    Project,
    ProjectDataModelEntity,
)
from django.core.files.base import ContentFile
from django.utils import timezone
from pypdf import PdfWriter

from content.mcp.hosting_subscription_tools import HOSTING_SUBSCRIPTION_TOOLS
from content.mcp.issue_tools import ISSUE_TOOLS
from content.mcp.platform_billing_tools import PLATFORM_BILLING_TOOLS
from content.mcp.platform_resource_tools import PLATFORM_RESOURCE_TOOLS
from content.mcp.project_create_tools import CREATE_PROJECT
from content.models import McpActionIntent, McpConnector, McpCredential, McpUpload
from content.tests.mcp_parity import assert_no_writes, call_tool_inprocess
from content.tests.mcp_schema_rules import schema_problems
from content.views.mcp_blog import TOOLS_BY_SLUG


@pytest.mark.parametrize(('family', 'native_tools', 'count'), [
    ('resources', PLATFORM_RESOURCE_TOOLS, 20),
    ('issues', ISSUE_TOOLS, 16),
    ('billing', PLATFORM_BILLING_TOOLS, 10),
    ('hosting', HOSTING_SUBSCRIPTION_TOOLS, 2),
    ('create', [CREATE_PROJECT], 1),
], ids=['resources', 'issues', 'billing', 'hosting', 'create'])
def test_native_policy_covers_the_registered_family(family, native_tools, count):
    registered = {tool['name']: tool for tool in TOOLS_BY_SLUG['projects']}
    native_names = {tool['name'] for tool in native_tools}

    violations = {name: problems for name in native_names
                  if (problems := schema_problems(registered[name]))}

    assert len(native_names) == count, family
    assert violations == {}, violations


@pytest.fixture
def resource_case(superuser, django_user_model):
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={
        'name': 'Proyectos', 'is_active': True,
    })
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    credential = McpCredential.objects.create(connector=connector, actor=superuser, label='Native schema review')
    client = django_user_model.objects.create_user('native-resource-owner')
    project = Project.objects.create(name='Native schemas', client=client)
    stream = io.BytesIO()
    pdf = PdfWriter()
    pdf.add_blank_page(width=200, height=200)
    pdf.write(stream)
    body = stream.getvalue()
    asset = McpUpload.objects.create(
        connector=connector, credential=credential, filename='reviewed.pdf', content_type='application/pdf',
        expected_size=len(body), received_size=len(body), expected_sha256=hashlib.sha256(body).hexdigest(),
        status=McpUpload.STATUS_COMPLETE, file=ContentFile(body, name='reviewed.pdf'),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    resource = Deliverable.objects.create(
        project=project, uploaded_by=superuser, title='Original resource', category='documents',
        description='Original description', file=ContentFile(body, name='original.pdf'),
    )
    folder = DeliverableClientFolder.objects.create(deliverable=resource, created_by=superuser, name='Original folder')
    return SimpleNamespace(project=project, credential=credential, asset=asset, resource=resource, folder=folder)


def _invoke(case, name, arguments):
    result = call_tool_inprocess('projects', name, arguments, credential=case.credential)
    assert 'error' not in result, result
    return result


def _write_arguments(case, **fields):
    return {'project_id': case.project.pk, 'expected_version': 0, 'request_id': 'flat-resource-write', **fields}


def _confirm_flat_write(case, name, arguments):
    preview = _invoke(case, name, arguments)
    assert preview['confirmation_required'] is True
    intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
    assert intent.arguments == {**arguments, 'expected_client_id': case.project.client_id}
    return _invoke(case, 'confirm_action', {'confirmation_id': preview['confirmation_id']})['result']


@pytest.mark.django_db
def test_flat_resource_creation_saves_reviewed_metadata(resource_case):
    case = resource_case
    arguments = _write_arguments(case, asset_id=str(case.asset.pk), title='Client manual',
                                 description='Reviewed description', category='documents')

    result = _confirm_flat_write(case, 'create_project_resource', arguments)

    created = Deliverable.objects.get(pk=result['result']['id'])
    assert (created.title, created.description, created.category) == ('Client manual', 'Reviewed description', 'documents')
    case.asset.refresh_from_db()
    assert case.asset.status == McpUpload.STATUS_CONSUMED


@pytest.mark.django_db
def test_flat_resource_update_preserves_its_file(resource_case):
    case = resource_case
    original_file = case.resource.file.name
    arguments = _write_arguments(case, resource_id=case.resource.pk, title='Revised manual',
                                 description='New description', category='other')

    result = _confirm_flat_write(case, 'update_project_resource', arguments)

    case.resource.refresh_from_db()
    assert (case.resource.title, case.resource.description, case.resource.category) == ('Revised manual', 'New description', 'other')
    assert (case.resource.file.name, case.resource.current_version, result['version']) == (original_file, 1, 1)


@pytest.mark.django_db
def test_flat_attachment_upload_keeps_the_selected_category(resource_case):
    case = resource_case
    arguments = _write_arguments(case, resource_id=case.resource.pk, asset_id=str(case.asset.pk),
                                 title='Appendix', category='documents')

    result = _confirm_flat_write(case, 'upload_project_resource_attachment', arguments)

    attachment = DeliverableFile.objects.get(pk=result['result']['id'])
    assert (attachment.deliverable_id, attachment.title, attachment.category) == (case.resource.pk, 'Appendix', 'documents')
    with attachment.file.open('rb') as stored:
        assert hashlib.sha256(stored.read()).hexdigest() == case.asset.expected_sha256


@pytest.mark.django_db
def test_flat_folder_creation_saves_the_requested_order(resource_case):
    case = resource_case
    arguments = _write_arguments(case, resource_id=case.resource.pk, name='Review documents', order=7)

    result = _confirm_flat_write(case, 'create_project_resource_folder', arguments)

    folder = DeliverableClientFolder.objects.get(pk=result['result']['id'])
    assert (folder.deliverable_id, folder.name, folder.order) == (case.resource.pk, 'Review documents', 7)


@pytest.mark.django_db
def test_flat_folder_update_preserves_unselected_metadata(resource_case):
    case = resource_case
    arguments = _write_arguments(case, resource_id=case.resource.pk, folder_id=case.folder.pk, order=9)

    _confirm_flat_write(case, 'update_project_resource_folder', arguments)

    case.folder.refresh_from_db()
    assert (case.folder.name, case.folder.order) == ('Original folder', 9)


@pytest.mark.django_db
@pytest.mark.parametrize('destination', ['folder', 'unfiled'])
def test_flat_client_pdf_upload_uses_its_requested_folder(resource_case, destination):
    case = resource_case
    folder_id = {'folder': case.folder.pk, 'unfiled': None}[destination]
    arguments = _write_arguments(case, resource_id=case.resource.pk, asset_id=str(case.asset.pk),
                                 title='Client input', folder_id=folder_id)

    result = _confirm_flat_write(case, 'upload_project_resource_client_file', arguments)

    upload = DeliverableClientUpload.objects.get(pk=result['result']['id'])
    assert (upload.deliverable_id, upload.folder_id, upload.title) == (case.resource.pk, folder_id, 'Client input')
    assert upload.uploaded_by_id == case.credential.actor_id


@pytest.mark.django_db
def test_flat_model_preview_returns_nested_fields_without_writes(resource_case):
    case = resource_case
    original = ProjectDataModelEntity.objects.create(project=case.project, name='Preserved entity')
    entity = {'name': 'Order', 'description': 'Sales order', 'keyFields': 'id, total', 'relationship': 'N:1 Customer'}

    preview = assert_no_writes(_invoke, case, 'preview_project_data_model', {
        'project_id': case.project.pk, 'expected_version': 0, 'entities': [entity],
    })

    assert preview['after'] == [entity]
    assert preview['before'][0]['id'] == original.pk


@pytest.mark.django_db
def test_flat_model_import_maps_the_entity_fields(resource_case):
    case = resource_case
    ProjectDataModelEntity.objects.create(project=case.project, name='Replace this entity')
    entity = {'name': 'Invoice', 'description': 'Issued invoice', 'keyFields': 'id, number', 'relationship': 'N:1 Account'}

    _confirm_flat_write(case, 'import_project_data_model', _write_arguments(case, entities=[entity]))

    assert list(ProjectDataModelEntity.objects.filter(project=case.project).values(
        'name', 'description', 'key_fields', 'relationship',
    )) == [{'name': 'Invoice', 'description': 'Issued invoice', 'key_fields': 'id, number', 'relationship': 'N:1 Account'}]


def _block_execution(monkeypatch, tool):
    spies = []
    for callback in ('handler', 'prepare_arguments', 'confirmation_predicate', 'impact_builder', 'etag_resolver'):
        if callback in tool:
            spy = Mock(side_effect=AssertionError('Legacy envelopes must fail before execution.'))
            monkeypatch.setitem(tool, callback, spy)
            spies.append(spy)
    return spies


def _legacy_arguments(case, tool, fields):
    arguments = _write_arguments(case, **fields)
    return {**{key: value for key, value in arguments.items() if key in tool['input_schema']['properties']}, 'data': {}}


@pytest.mark.django_db
@pytest.mark.parametrize(('name', 'fields'), [
    ('create_project_resource', {'title': 'Manual', 'asset_id': '10000000-0000-4000-8000-000000000001'}),
    ('update_project_resource', {'resource_id': 1, 'title': 'Revised'}),
    ('upload_project_resource_attachment', {'resource_id': 1, 'asset_id': '10000000-0000-4000-8000-000000000001'}),
    ('create_project_resource_folder', {'resource_id': 1, 'name': 'Manuals'}),
    ('update_project_resource_folder', {'resource_id': 1, 'folder_id': 1}),
    ('upload_project_resource_client_file', {'resource_id': 1, 'asset_id': '10000000-0000-4000-8000-000000000001'}),
    ('preview_project_data_model', {'entities': []}),
    ('import_project_data_model', {'entities': []}),
])
def test_legacy_data_is_rejected_before_resource_execution(resource_case, monkeypatch, name, fields):
    case = resource_case
    tool = next(tool for tool in TOOLS_BY_SLUG['projects'] if tool['name'] == name)
    spies = _block_execution(monkeypatch, tool)
    arguments = _legacy_arguments(case, tool, fields)

    result = assert_no_writes(call_tool_inprocess, 'projects', name, arguments, credential=case.credential)

    assert result['error']['code'] == 'unknown_field'
    assert 'data' in {row['field'] for row in result['error']['details']['errors']}
    assert [spy.call_count for spy in spies] == [0] * len(spies)
