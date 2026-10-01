"""Ticket regressions: general reporting, original rounds and team resolution."""
import hashlib
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from pypdf import PdfWriter
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient

from accounts.models import (
    BugReport, DeliveryPublication, IssueAttachment, IssueEvent, IssueResponse,
    Project, RequirementReview, UserProfile,
)
from accounts.services import issue_reports as issues
from accounts.services.issue_evidence import attachment_for_actor
from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
from content.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def actors():
    user = get_user_model()
    client = user.objects.create_user(username='issue-client', email='issue-client@example.test')
    admin = user.objects.create_user(username='issue-admin', email='issue-admin@example.test', is_staff=True)
    outsider = user.objects.create_user(username='issue-other', email='issue-other@example.test')
    UserProfile.objects.create(user=client, role='client')
    UserProfile.objects.create(user=admin, role='admin')
    UserProfile.objects.create(user=outsider, role='client')
    return client, admin, outsider


@pytest.fixture
def project(actors):
    return Project.objects.create(name='Issue project', client=actors[0])


@pytest.fixture
def source(project):
    stage = make_delivery_stage(project)
    return make_requirement(stage, title='Original guide', guide={
        'steps': ['Open the screen'], 'expected_result': 'Saved', 'data': 'Original data',
    })


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


def bug(project, actor, **values):
    return issues.create_ticket(project.pk, actor, 'bug', {'title': 'Cannot save', **values})


def test_client_reports_general_bug_without_a_published_guide(project, actors):
    api = APIClient()
    api.force_authenticate(actors[0])

    response = api.post(f'/api/accounts/projects/{project.pk}/bug-reports/', {'title': 'Screen fails'}, format='json')

    assert response.status_code == 201
    assert response.data['origin_context']['origin_kind'] == 'general'
    assert BugReport.objects.get(pk=response.data['id']).source_requirement_id is None


def test_original_publication_survives_a_new_round(project, actors, source):
    publication = source.stage.publications.get()
    ticket = bug(project, actors[0], source_requirement_id=source.pk)
    DeliveryPublication.objects.create(stage=source.stage, round=2, published_by=actors[1], payload={
        'title': 'Changed stage', 'requirements': [{'id': source.pk, 'title': 'Changed guide', 'version': source.version + 1}],
    })

    ticket.refresh_from_db()

    assert ticket.issue_context.publication_id == publication.pk
    assert ticket.issue_context.snapshot['requirement']['guide']['data'] == 'Original data'


def test_change_request_keeps_its_original_publication_after_a_later_round(project, actors, source):
    """Falla si una ampliación pasa a apuntar a la guía publicada posteriormente."""
    original = source.stage.publications.get()
    ticket = issues.create_ticket(
        project.pk,
        actors[0],
        'change',
        {'title': 'Add export', 'source_requirement_id': source.pk},
    )
    DeliveryPublication.objects.create(stage=source.stage, round=2, published_by=actors[1], payload={
        'title': 'Changed stage',
        'requirements': [{'id': source.pk, 'title': 'Later guide', 'version': source.version + 1}],
    })

    ticket.refresh_from_db()

    assert ticket.issue_context.publication_id == original.pk
    assert ticket.issue_context.snapshot['requirement_title'] == 'Original guide'


def test_explicit_older_round_is_captured(project, actors, source):
    original = source.stage.publications.get()
    DeliveryPublication.objects.create(stage=source.stage, round=2, published_by=actors[1], payload={
        'requirements': [{'id': source.pk, 'title': 'Later guide', 'version': source.version + 1}],
    })

    ticket = bug(project, actors[0], source_requirement_id=source.pk,
                 source_publication_id=original.pk, source_requirement_version=source.version)

    assert ticket.issue_context.publication_id == original.pk
    assert ticket.issue_context.snapshot['requirement_title'] == 'Original guide'


def test_source_version_mismatch_returns_conflict(project, actors, source):
    with pytest.raises(APIException) as error:
        bug(project, actors[0], source_requirement_id=source.pk, source_requirement_version=source.version + 1)

    assert error.value.status_code == 409
    assert not BugReport.objects.exists()


def test_source_from_another_project_is_rejected(project, actors):
    other = Project.objects.create(name='Another project', client=actors[0])
    source = make_requirement(make_delivery_stage(other))

    with pytest.raises(APIException) as error:
        bug(project, actors[0], source_requirement_id=source.pk)

    assert error.value.status_code == 400
    assert not BugReport.objects.exists()


def test_creation_retry_does_not_duplicate_a_ticket(project, actors):
    payload = {'title': 'Cannot save', 'request_id': '10000000-0000-4000-8000-000000000001'}
    first = issues.create_ticket(project.pk, actors[0], 'bug', payload)

    retried = issues.create_ticket(project.pk, actors[0], 'bug', payload)

    assert first.pk == retried.pk
    assert BugReport.objects.count() == 1
    assert IssueEvent.objects.count() == 1


def test_retry_id_cannot_change_the_payload(project, actors):
    request_id = '10000000-0000-4000-8000-000000000002'
    bug(project, actors[0], request_id=request_id)

    with pytest.raises(APIException) as error:
        bug(project, actors[0], request_id=request_id, description='Different report')

    assert error.value.status_code == 409


def test_team_resolution_leaves_guide_approvals_unchanged(project, actors, source):
    ticket = bug(project, actors[0], source_requirement_id=source.pk)
    before = source.review_status

    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'status': 'resolved', 'admin_response': 'Fixed the save button.',
    })

    source.refresh_from_db()
    assert source.review_status == before
    assert not RequirementReview.objects.exists()
    assert IssueResponse.objects.get().scope_result == 'indeterminate'


def test_client_reopens_with_a_response(project, actors):
    ticket = bug(project, actors[0])
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'resolved', 'admin_response': 'Fixed.'})

    comment = issues.comment_ticket(project.pk, actors[0], 'bug', ticket.pk, {'content': 'Still fails in Safari.', 'reopen': True})

    ticket.refresh_from_db()
    assert ticket.status == 'reported'
    assert comment.content == 'Still fails in Safari.'
    assert ticket.admin_response == 'Fixed.'
    assert ticket.issue_events.last().action == 'reopened'


def test_reopen_requires_a_nonblank_response(project, actors):
    ticket = bug(project, actors[0])
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'resolved'})

    with pytest.raises(APIException):
        issues.comment_ticket(project.pk, actors[0], 'bug', ticket.pk, {'content': ' ', 'reopen': True})

    ticket.refresh_from_db()
    assert ticket.status == 'resolved'
    assert not ticket.comments.exists()


def test_stale_version_does_not_overwrite_a_response(project, actors):
    ticket = bug(project, actors[0])
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'confirmed', 'expected_version': ticket.version})

    with pytest.raises(APIException) as error:
        issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'resolved', 'expected_version': ticket.version})

    assert error.value.status_code == 409
    ticket.refresh_from_db()
    assert ticket.status == 'confirmed'


def test_status_only_change_preserves_latest_public_response(project, actors):
    ticket = bug(project, actors[0])
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'confirmed', 'admin_response': 'Investigating.'})

    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'fixing'})

    ticket.refresh_from_db()
    assert ticket.admin_response == 'Investigating.'
    assert ticket.issue_responses.count() == 1


def test_response_pdf_preserves_original_bytes(project, actors):
    ticket = bug(project, actors[0])
    content = pdf_bytes()
    doc = Document.objects.create(title='Response evidence', project=project, client_user=actors[0], created_by=actors[1], is_client_visible=True)
    doc.generated_file.save('original.pdf', ContentFile(content))

    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'admin_response': 'See the diagnosis.', 'document_ids': [doc.pk]})
    doc.generated_file.save('updated.pdf', ContentFile(b'new draft'))

    attachment = IssueAttachment.objects.get()
    assert attachment.sha256 == hashlib.sha256(content).hexdigest()
    assert attachment.file.read() == content


def test_foreign_document_rolls_back_response(project, actors):
    ticket = bug(project, actors[0])
    other = Project.objects.create(name='Other project', client=actors[2])
    doc = Document.objects.create(title='Foreign', project=other, client_user=actors[2], created_by=actors[1])

    with pytest.raises(APIException):
        issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'status': 'resolved', 'admin_response': 'Evidence', 'document_ids': [doc.pk]})

    ticket.refresh_from_db()
    assert ticket.status == 'reported'
    assert not ticket.issue_responses.exists()


def test_client_cannot_download_internal_evidence(project, actors):
    ticket = bug(project, actors[0])
    doc = Document.objects.create(title='Internal diagnosis', project=project, client_user=actors[0], created_by=actors[1])
    doc.generated_file.save('evidence.pdf', ContentFile(pdf_bytes()))
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {'admin_response': 'Private note', 'is_internal': True, 'document_ids': [doc.pk]})
    attachment = IssueAttachment.objects.get()

    with pytest.raises(APIException) as error:
        attachment_for_actor(attachment.pk, actors[0])

    assert error.value.status_code == 404
    ticket.refresh_from_db()
    assert ticket.admin_response == ''


def test_client_detail_redacts_internal_evidence(project, actors):
    """Falla si el detalle del cliente filtra los adjuntos pero expone el diagnóstico interno."""
    ticket = bug(project, actors[0])
    document = Document.objects.create(
        title='Internal diagnosis', project=project, client_user=actors[0], created_by=actors[1],
    )
    document.generated_file.save('evidence.pdf', ContentFile(pdf_bytes()))
    issues.evaluate_ticket(project.pk, actors[1], 'bug', ticket.pk, {
        'status': 'resolved', 'admin_response': 'Internal stack trace.',
        'is_internal': True, 'document_ids': [document.pk],
    })
    attachment = IssueAttachment.objects.get()
    api = APIClient()
    api.force_authenticate(actors[0])

    response = api.get(f'/api/accounts/projects/{project.pk}/bug-reports/{ticket.pk}/')

    assert response.status_code == 200
    assert response.data['status'] == 'resolved'
    assert response.data['responses'] == []
    payload = str(response.data)
    assert 'Internal stack trace.' not in payload
    assert f'/api/accounts/issue-reports/attachments/{attachment.pk}/' not in payload
    assert attachment.sha256 not in payload


def test_other_client_cannot_read_ticket(project, actors):
    ticket = bug(project, actors[0])

    with pytest.raises(APIException) as error:
        issues.get_ticket(project.pk, actors[2], 'bug', ticket.pk)

    assert error.value.status_code == 404
