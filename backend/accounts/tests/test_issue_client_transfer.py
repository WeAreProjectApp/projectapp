"""Ticket-history safety checks when a project is reassigned to another client."""
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from pypdf import PdfWriter
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient

from accounts.models import ChangeRequest, Project, ProjectAccessNote, UserProfile
from accounts.services import issue_reports as issues
from accounts.services.credential_cipher import encrypt_secret
from accounts.services.issue_client_transfer import assert_issue_client_transfer_safe
from accounts.services.issue_evidence import attachment_for_actor
from content.models import AccountingChangeLog, Document
from content.services import project_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def people():
    user = get_user_model()
    owner = user.objects.create_user(username='transfer-owner', email='transfer-owner@example.test')
    target = user.objects.create_user(username='transfer-target', email='transfer-target@example.test')
    staff = user.objects.create_user(
        username='transfer-staff', email='transfer-staff@example.test', is_staff=True,
    )
    owner_profile = UserProfile.objects.create(user=owner, role='client')
    target_profile = UserProfile.objects.create(user=target, role='client')
    UserProfile.objects.create(user=staff, role='admin')
    return owner, owner_profile, target, target_profile, staff


@pytest.fixture
def project(people):
    return Project.objects.create(name='Transfer history project', client=people[0])


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


def general_bug(project, reporter):
    return issues.create_ticket(project.pk, reporter, 'bug', {'title': 'General incident'})


def transfer_conflict(project, new_client):
    with pytest.raises(APIException) as error:
        assert_issue_client_transfer_safe(project, new_client)
    return error.value


def test_general_ticket_history_blocks_client_transfer_without_mutating_history(project, people):
    """Falla si cambiar de cliente expone un bug general con evidencia histórica."""
    owner, owner_profile, target, target_profile, staff = people
    ticket = general_bug(project, staff)
    document = Document.objects.create(
        title='Staff diagnosis', project=project, client_user=owner, created_by=staff,
    )
    document.generated_file.save('staff-diagnosis.pdf', ContentFile(pdf_bytes()))
    issues.evaluate_ticket(project.pk, staff, 'bug', ticket.pk, {
        'admin_response': 'Staff found the fault.', 'document_ids': [document.pk],
    })
    attachment = ticket.issue_responses.get().attachments.get()
    note = ProjectAccessNote.objects.create(
        project=project, title='Operational note', content_encrypted=encrypt_secret('operational-note'),
        created_by=staff, updated_by=staff,
    )
    audit = AccountingChangeLog.objects.create(
        entity_type=AccountingChangeLog.EntityType.PROJECT, object_id=project.pk,
        object_repr=project.name, action=AccountingChangeLog.Action.UPDATED,
        actor=staff, actor_username=staff.username,
    )
    root_id = project.communication_root_thread.pk
    history_count = ticket.issue_events.count()
    audit_count = AccountingChangeLog.objects.filter(
        entity_type=AccountingChangeLog.EntityType.PROJECT, object_id=project.pk,
    ).count()

    with pytest.raises(APIException) as raised:
        project_service.change_client_apply(
            project, target_profile, project_service.MODE_MOVE, staff,
        )
    error = raised.value
    client = APIClient()
    client.force_authenticate(target)
    denied_ticket = client.get(f'/api/accounts/projects/{project.pk}/bug-reports/{ticket.pk}/')
    client.force_authenticate(owner)
    owner_ticket = client.get(f'/api/accounts/projects/{project.pk}/bug-reports/{ticket.pk}/')

    assert error.status_code == 409
    assert str(error.detail['code']) == 'issue_client_transfer_history'
    project.refresh_from_db()
    ticket.refresh_from_db()
    assert project.client_id == owner.pk
    assert ticket.reported_by_id == staff.pk
    assert ticket.issue_responses.get().message == 'Staff found the fault.'
    assert attachment_for_actor(attachment.pk, owner).pk == attachment.pk
    with pytest.raises(APIException) as attachment_error:
        attachment_for_actor(attachment.pk, target)
    assert attachment_error.value.status_code == 404
    assert denied_ticket.status_code == 403
    assert owner_ticket.status_code == 200
    assert ProjectAccessNote.objects.get(pk=note.pk).project_id == project.pk
    assert project.communication_root_thread.pk == root_id
    assert AccountingChangeLog.objects.get(pk=audit.pk).object_id == project.pk
    assert ticket.issue_events.count() == history_count
    assert AccountingChangeLog.objects.filter(
        entity_type=AccountingChangeLog.EntityType.PROJECT, object_id=project.pk,
    ).count() == audit_count
    assert owner_profile.user_id == owner.pk


def test_archived_bug_history_blocks_client_transfer(project, people):
    """Falla si archivar un bug permite transferir su historia a otro cliente."""
    owner, _, target, _, staff = people
    ticket = general_bug(project, owner)
    issues.archive_ticket(project.pk, staff, 'bug', ticket.pk, {'expected_version': ticket.version})

    error = transfer_conflict(project, target)

    assert error.status_code == 409
    assert str(error.detail['code']) == 'issue_client_transfer_history'


def test_legacy_change_request_blocks_client_transfer(project, people):
    """Falla si una solicitud legacy sin guía deja de proteger al cliente original."""
    owner, _, target, _, _ = people
    ChangeRequest.objects.create(project=project, created_by=owner, title='Legacy request')

    error = transfer_conflict(project, target)

    assert error.status_code == 409
    assert str(error.detail['code']) == 'issue_client_transfer_history'


def test_same_owner_transfer_allows_a_project_rename(project, people):
    """Falla si el guard bloquea una edición que conserva el mismo dueño."""
    owner, _, _, _, _ = people
    ticket = general_bug(project, owner)
    project.name = 'Renamed project'

    assert_issue_client_transfer_safe(project, owner)
    project.save(update_fields=['name', 'updated_at'])

    project.refresh_from_db()
    ticket.refresh_from_db()
    assert project.name == 'Renamed project'
    assert project.client_id == owner.pk
    assert ticket.project_id == project.pk


def test_empty_project_transfer_uses_the_project_service_bridge(project, people):
    """Falla si el puente bloquea una transferencia sin historia de tickets."""
    _, _, target, target_profile, staff = people

    project_service.change_client_apply(project, target_profile, project_service.MODE_MOVE, staff)

    project.refresh_from_db()
    assert project.client_id == target.pk


def test_history_on_another_project_does_not_block_transfer(project, people):
    """Falla si el guard confunde la historia de dos proyectos distintos."""
    owner, _, target, target_profile, staff = people
    other = Project.objects.create(name='Other history project', client=owner)
    general_bug(other, owner)

    project_service.change_client_apply(project, target_profile, project_service.MODE_MOVE, staff)

    project.refresh_from_db()
    assert project.client_id == target.pk


def test_guard_uses_the_stored_owner_after_an_in_memory_client_change(project, people):
    """Falla si alterar la instancia en memoria evita la protección de historia."""
    owner, _, target, _, _ = people
    general_bug(project, owner)
    project.client = target

    error = transfer_conflict(project, target)

    assert error.status_code == 409
    assert str(error.detail['code']) == 'issue_client_transfer_history'
