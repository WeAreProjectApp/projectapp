"""MCP ticket parity uses real connector transport and shared domain writes."""
import io

import pytest
from django.core.files.base import ContentFile
from pypdf import PdfWriter

from accounts.models import BugReport, IssueResponse, Project, RequirementReview
from accounts.services import issue_reports as issues
from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from content.models import Document, McpConnector, McpUpload

pytestmark = pytest.mark.django_db


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

    result = call('evaluate_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
                                          'payload': {'status': 'resolved', 'admin_response': 'Fixed.', 'expected_version': ticket['version']}})

    assert result['isError'] is False
    assert not RequirementReview.objects.exists()
    assert IssueResponse.objects.get().scope_result == 'indeterminate'


def test_mcp_reopen_preserves_response_history(call, project):
    ticket = create(call, project)
    fixed = call('evaluate_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
                                         'payload': {'status': 'resolved', 'admin_response': 'Fixed.', 'expected_version': ticket['version']}})['structuredContent']

    result = call('comment_issue_report', {'project_id': project.pk, 'kind': 'bug', 'ticket_id': ticket['id'],
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


def test_mcp_list_returns_origin_context(call, project):
    ticket = create(call, project)

    result = call('list_issue_reports', {'project_id': project.pk, 'kind': 'bug'})

    assert result['structuredContent']['tickets'][0]['id'] == ticket['id']
    assert result['structuredContent']['tickets'][0]['origin_context']['origin_kind'] == 'general'
