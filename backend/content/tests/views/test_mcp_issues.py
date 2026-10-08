"""MCP ticket parity uses real connector transport and shared domain writes."""
import hashlib
import io
from datetime import timedelta

import pytest
from accounts.models import (
    BugReport,
    DeliveryPromptSource,
    DeliveryStage,
    IssueResponse,
    Project,
    Requirement,
    RequirementReview,
)
from accounts.services import issue_reports as issues
from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from accounts.tests.delivery_authoring_helpers import build_authoring_context
from accounts.tests.delivery_helpers import RECORDED_AT, publish, version
from accounts.tests.issue_browser_server import assert_memory_mailers, memory_mailers
from django.core.files.base import ContentFile
from django.test import override_settings
from freezegun import freeze_time
from PIL import Image
from pypdf import PdfWriter

from content.models import Document, McpActionIntent, McpConnector, McpUpload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def memory_only_mail(settings, mailoutbox):
    with override_settings(MAILERS=memory_mailers(settings)):
        assert_memory_mailers()
        yield
        assert_memory_mailers()
        assert mailoutbox == []


@pytest.fixture
def call(api_client, superuser):
    connector, _ = McpConnector.objects.get_or_create(slug='projects', defaults={'name': 'Projects'})
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()

    def invoke(name, arguments):
        response = api_client.post(f'/api/mcp/projects/{token}/', {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }, format='json')
        assert response.status_code == 200
        return response.data['result']
    return invoke


@pytest.fixture
def project(django_user_model):
    client = django_user_model.objects.create_user(username='mcp-issue-client')
    return Project.objects.create(name='MCP issue project', client=client)


def create(call, project):
    return call('create_bug_report', {'project_id': project.pk, 'payload': {'title': 'General failure'}})['structuredContent']


def confirmed_issue_call(call, tool, arguments):
    """Drive the owned preview before executing an explicitly public mutation."""
    preview = call(tool, arguments)
    if preview['isError']:
        return preview
    return call('confirm_action', {'confirmation_id': preview['structuredContent']['confirmation_id']})


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


def test_mcp_creates_a_general_report(call, project):
    result = create(call, project)

    assert result['origin_context']['origin_kind'] == 'general'
    assert BugReport.objects.get(pk=result['id']).source_requirement_id is None


def test_mcp_evaluation_preserves_guide_approvals(call, project):
    source = make_requirement(make_delivery_stage(project))
    ticket = call('create_bug_report', {'project_id': project.pk, 'payload': {'title': 'Failure', 'source_requirement_id': source.pk}})['structuredContent']

    result = confirmed_issue_call(call, 'evaluate_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
                                          'payload': {'status': 'resolved', 'admin_response': 'Fixed.', 'expected_version': ticket['version']}})

    assert result['isError'] is False
    assert not RequirementReview.objects.exists()
    assert IssueResponse.objects.get().scope_result == 'indeterminate'


def test_mcp_reopen_preserves_response_history(call, project):
    ticket = create(call, project)
    confirmed = confirmed_issue_call(call, 'evaluate_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
                                         'payload': {'status': 'resolved', 'admin_response': 'Fixed.', 'expected_version': ticket['version']}})['structuredContent']
    fixed = confirmed['result']

    result = confirmed_issue_call(call, 'comment_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
                                         'payload': {'content': 'Still fails.', 'reopen': True, 'expected_version': fixed['version']}})

    assert result['isError'] is False
    assert BugReport.objects.get(pk=ticket['id']).status == 'reported'
    assert IssueResponse.objects.get().message == 'Fixed.'


def test_mcp_stale_version_does_not_change_status(call, project):
    ticket = create(call, project)

    result = call('evaluate_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
                                          'payload': {'status': 'resolved', 'expected_version': ticket['version'] - 1}})

    assert result['isError'] is True
    assert BugReport.objects.get(pk=ticket['id']).status == 'reported'


def test_mcp_retries_creation_without_duplicates(call, project):
    arguments = {
        'project_id': project.pk,
        'payload': {'title': 'Failure', 'request_id': '20000000-0000-4000-8000-000000000001'},
    }
    call('create_bug_report', arguments)

    result = call('create_bug_report', arguments)

    assert result['isError'] is False
    assert BugReport.objects.count() == 1


def test_mcp_isolates_ticket_project(call, project, django_user_model):
    ticket = create(call, project)
    other = Project.objects.create(name='Other', client=django_user_model.objects.create_user('mcp-other'))

    result = call('get_issue_report', {'project_id': other.pk, 'kind': 'bug', 'ticket_id': ticket['id']})

    assert result['isError'] is True


def test_mcp_attachment_download_rejects_another_project(call, project, django_user_model, superuser):
    """Falla si el conector MCP convierte evidencia de otro proyecto en un artefacto descargable."""
    ticket = create(call, project)
    document = Document.objects.create(
        title='Diagnosis', project=project, client_user=project.client, created_by=superuser,
    )
    document.generated_file.save('evidence.pdf', ContentFile(pdf_bytes()))
    issues.evaluate_ticket(project.pk, superuser, 'bug', ticket['id'], {
        'admin_response': 'Investigated.', 'document_ids': [document.pk],
    })
    attachment_id = IssueResponse.objects.get().attachments.get().pk
    other = Project.objects.create(name='Other', client=django_user_model.objects.create_user('mcp-other-download'))

    result = call('download_issue_attachment', {
        'project_id': other.pk,
        'attachment_id': attachment_id,
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'NOT_FOUND'
    assert 'asset_id' not in result['structuredContent']
    assert not McpUpload.objects.exists()


def test_mcp_archive_requires_owned_confirmation(call, project):
    ticket = create(call, project)

    preview = call('archive_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'], 'expected_version': ticket['version']})

    assert preview['structuredContent']['confirmation_id']
    assert BugReport.objects.get(pk=ticket['id']).is_archived is False


def test_mcp_archive_confirmation_lists_the_archived_ticket(call, project):
    """Falla si confirmar un archivo borra historia o la lista archivada mezcla tickets distractores."""
    ticket = create(call, project)
    distractor = create(call, project)
    confirmed_issue_call(call, 'evaluate_issue_report', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': distractor['id'],
        'payload': {'status': 'resolved', 'admin_response': 'Otro caso resuelto.',
                    'expected_version': distractor['version']},
    })
    preview = call('archive_issue_report', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'], 'expected_version': ticket['version'],
    })
    confirmed = call('confirm_action', {'confirmation_id': preview['structuredContent']['confirmation_id']})

    listed = call('list_issue_reports', {
        'project_id': project.pk, 'kind': 'bug', 'include_archived': True, 'status': 'reported',
    })['structuredContent']
    archived = BugReport.objects.get(pk=ticket['id'])
    assert confirmed['structuredContent']['result']['archived'] is True
    assert (archived.is_archived, archived.version, archived.title) == (True, ticket['version'] + 1, 'General failure')
    assert [row['id'] for row in listed['tickets']] == [ticket['id']]
    assert McpActionIntent.objects.count() == 2


def _completed_png():
    stream = io.BytesIO()
    Image.new('RGB', (2, 2), color='white').save(stream, format='PNG')
    return stream.getvalue()


@freeze_time(RECORDED_AT)
def test_mcp_bug_report_preserves_completed_screenshot_asset(call, project):
    """Falla si un bug pierde la captura normalizada o modifica su asset PNG original."""
    body = _completed_png()
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    asset = McpUpload.objects.create(connector=credential.connector, credential=credential, filename='bug.png', content_type='image/png', expected_size=len(body), received_size=len(body), expected_sha256=hashlib.sha256(body).hexdigest(), status=McpUpload.STATUS_COMPLETE, expires_at=RECORDED_AT + timedelta(minutes=5))
    asset.file.save('bug.png', ContentFile(body), save=True)

    result = call('create_bug_report', {'project_id': project.pk, 'payload': {'title': 'PNG issue', 'screenshot_asset_id': str(asset.pk)}})['structuredContent']
    report = BugReport.objects.get(pk=result['id'])
    with report.screenshot.open('rb') as source:
        screenshot = Image.open(io.BytesIO(source.read()))
        assert (screenshot.format, screenshot.size, screenshot.mode) == ('JPEG', (2, 2), 'RGB')
        assert screenshot.getpixel((0, 0)) == (255, 255, 255)
    asset.refresh_from_db()
    with asset.file.open('rb') as source:
        assert source.read() == body
    assert (asset.status, RequirementReview.objects.count()) == (McpUpload.STATUS_COMPLETE, 0)


@freeze_time(RECORDED_AT)
def test_mcp_bug_report_rejects_a_completed_screenshot_over_five_megabytes(call, project):
    """Falla si una captura completada mayor de 5 MiB crea un ticket o consume el asset."""
    body = _completed_png() + b'x' * (5 * 1024 * 1024)
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    asset = McpUpload.objects.create(connector=credential.connector, credential=credential, filename='large.png', content_type='image/png', expected_size=len(body), received_size=len(body), expected_sha256=hashlib.sha256(body).hexdigest(), status=McpUpload.STATUS_COMPLETE, expires_at=RECORDED_AT + timedelta(minutes=5))
    asset.file.save('large.png', ContentFile(body), save=True)

    result = call('create_bug_report', {'project_id': project.pk, 'payload': {'title': 'Large PNG', 'screenshot_asset_id': str(asset.pk)}})
    asset.refresh_from_db()
    assert result['structuredContent']['error']['code'] == 'VALIDATION_ERROR'
    assert (BugReport.objects.count(), asset.status, bool(asset.file)) == (0, McpUpload.STATUS_COMPLETE, True)


def test_mcp_confirmed_change_conversion_creates_pending_requirement(call):
    """Falla si convertir una solicitud aprobada no crea una guía pendiente sin aprobación del cliente."""
    context = build_authoring_context()
    publish(context)
    source = context.first
    target = DeliveryStage.objects.create(phase=context.phase, key='ampliacion', title='Ampliación editable')
    request = issues.create_ticket(context.project.pk, context.client, 'change', {'title': 'Nueva guía', 'module_or_screen': 'Portal', 'source_requirement_id': source.pk})
    request.status = 'approved'
    request.save(update_fields=['status'])
    before = Requirement.objects.count()
    preview = call('convert_change_request', {'project_id': context.project.pk, 'ticket_id': request.pk, 'payload': {'expected_version': version(context), 'issue_version': request.version, 'stage_id': target.pk}})
    assert Requirement.objects.count() == before
    confirmed = call('confirm_action', {'confirmation_id': preview['structuredContent']['confirmation_id']})
    replay = call('confirm_action', {'confirmation_id': preview['structuredContent']['confirmation_id']})
    request.refresh_from_db()
    requirement = Requirement.objects.get(pk=confirmed['structuredContent']['result']['linked_requirement_id'])
    assert (requirement.review_status, request.linked_requirement_id) == ('pending', requirement.pk)
    assert replay['structuredContent']['result']['linked_requirement_id'] == requirement.pk
    assert Requirement.objects.count() == before + 1
    assert RequirementReview.objects.count() == 0


def test_mcp_downloads_historical_issue_attachment_after_source_edit(call, project, superuser):
    """Falla si descargar un adjunto histórico lee la fuente editada en vez de sus bytes congelados."""
    ticket = create(call, project)
    document = Document.objects.create(title='Historia PDF', project=project, client_user=project.client, created_by=superuser)
    original = pdf_bytes()
    document.generated_file.save('history.pdf', ContentFile(original), save=True)
    issues.evaluate_ticket(project.pk, superuser, 'bug', ticket['id'], {'admin_response': 'Adjunto histórico.', 'document_ids': [document.pk]})
    attachment = IssueResponse.objects.get().attachments.get()
    document.generated_file.save('edited.pdf', ContentFile(pdf_bytes() + b'changed'), save=True)
    result = call('download_issue_attachment', {'project_id': project.pk, 'attachment_id': attachment.pk})['structuredContent']
    artifact = McpUpload.objects.get(pk=result['asset_id'])
    with artifact.file.open('rb') as source:
        assert source.read() == original
    assert (artifact.expected_sha256, artifact.credential.connector.slug) == (hashlib.sha256(original).hexdigest(), 'projects')


def test_mcp_list_returns_origin_context(call, project):
    ticket = create(call, project)

    result = call('list_issue_reports', {'project_id': project.pk, 'kind': 'bug'})

    assert result['structuredContent']['tickets'][0]['id'] == ticket['id']
    assert result['structuredContent']['tickets'][0]['origin_context']['origin_kind'] == 'general'


def test_mcp_reply_pipeline_rejects_unreviewed_publish_without_writing(call, project):
    """Falla si MCP publica una respuesta contractual sin revisión humana explícita."""
    ticket = create(call, project)
    options = call('get_issue_reply_options', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
    })['structuredContent']
    prepared = call('prepare_issue_reply', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
        'payload': {
            'expected_version': options['version'], 'expected_ticket_version': ticket['version'],
            'request_id': '50000000-0000-4000-8000-000000000001', 'contract_id': None,
        },
    })['structuredContent']
    preview = call('preview_issue_reply', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
        'payload': {
            'expected_version': options['version'], 'expected_ticket_version': ticket['version'],
            'payload': prepared['template'],
        },
    })['structuredContent']

    rejected = call('evaluate_issue_report', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
        'payload': {
            'expected_version': ticket['version'], 'admin_response': prepared['template']['response_text'],
            'contract_id': None,
            'contract_reply': {
                'context_id': prepared['id'], 'expected_version': options['version'],
                'expected_ticket_version': ticket['version'], 'human_reviewed': False,
                'classifications': prepared['template']['classifications'],
                'source_references': preview['source_references'],
            },
        },
    })

    assert rejected['isError'] is True
    assert rejected['structuredContent']['error']['code'] == 'HUMAN_REVIEW_REQUIRED'
    assert BugReport.objects.get(pk=ticket['id']).version == ticket['version']
    assert not IssueResponse.objects.filter(bug_report_id=ticket['id']).exists()


def test_mcp_reply_context_rejects_a_different_ticket(call, project):
    """Falla si un contexto MCP preparado para un ticket puede leerse desde otro."""
    first = create(call, project)
    options = call('get_issue_reply_options', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': first['id'],
    })['structuredContent']
    prepared = call('prepare_issue_reply', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': first['id'],
        'payload': {
            'expected_version': options['version'], 'expected_ticket_version': first['version'],
            'request_id': '50000000-0000-4000-8000-000000000002', 'contract_id': None,
        },
    })['structuredContent']
    second = create(call, project)

    result = call('get_issue_reply_context', {
        'project_id': project.pk, 'kind': 'bug', 'ticket_id': second['id'], 'context_id': prepared['id'],
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'CONTEXT_DESTINATION'


def test_mcp_downloads_captured_reply_source_as_a_private_artifact(call, superuser):
    """Falla si MCP no entrega los bytes congelados de una fuente contractual propia."""
    context = build_authoring_context()
    report = issues.create_ticket(context.project.pk, context.client, 'bug', {
        'title': 'General contractual incident',
    })
    options = call('get_issue_reply_options', {
        'project_id': context.project.pk, 'kind': 'bug', 'ticket_id': report.pk,
    })['structuredContent']
    prepared = call('prepare_issue_reply', {
        'project_id': context.project.pk, 'kind': 'bug', 'ticket_id': report.pk,
        'payload': {
            'expected_version': options['version'], 'expected_ticket_version': report.version,
            'request_id': '50000000-0000-4000-8000-000000000003', 'contract_id': context.contract.pk,
        },
    })['structuredContent']
    source = DeliveryPromptSource.objects.get(context_id=prepared['id'], role='contract')

    result = call('download_issue_reply_source', {
        'project_id': context.project.pk, 'kind': 'bug', 'ticket_id': report.pk,
        'context_id': prepared['id'], 'source_key': source.source_key,
    })['structuredContent']

    artifact = McpUpload.objects.get(pk=result['asset_id'])
    with source.file.open('rb') as captured, artifact.file.open('rb') as downloaded:
        assert downloaded.read() == captured.read()
    assert artifact.expected_sha256 == source.sha256
    assert artifact.credential.connector.slug == 'projects'
