"""The panel deletes unused projects, never their business dependencies."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Project, UserProfile
from content.models import (
    AccountingChangeLog, CommunicationMessage, CommunicationThread, Document,
    DocumentFolder, DocumentStateEpisode, DocumentStateEpisodeEvent,
    DocumentType, EntityHistory, HostingRecord, IncomeRecord,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def unused_project():
    user = get_user_model().objects.create_user(
        username='project-owner', email='owner@example.test', password='password123',
    )
    UserProfile.objects.create(user=user)
    return Project.objects.create(client=user, name='Unused project')


def preview_url(project):
    return f'/api/projects/{project.pk}/delete-preview/'


def delete_url(project):
    return f'/api/projects/{project.pk}/delete/'


def add_income(project):
    return IncomeRecord.objects.create(
        project=project, client=project.client.profile, concept='Development',
        period_date='2026-09-01', total_amount=Decimal('100000'),
        gustavo_amount=Decimal('50000'), carlos_amount=Decimal('50000'),
    )


def add_document(project, **kwargs):
    kind, _ = DocumentType.objects.get_or_create(code='deletion-test', defaults={'name': 'Documento'})
    return Document.objects.create(
        project=project, document_type=kind, title='Contract', **kwargs,
    )


def test_preview_ignores_empty_automatic_structure(admin_client, unused_project):
    response = admin_client.get(preview_url(unused_project))

    assert response.status_code == 200
    assert response.data['can_delete'] is True
    assert response.data['blockers'] == []
    assert unused_project.document_folders.count() == 5


def test_delete_removes_empty_automatic_structure(admin_client, unused_project):
    project_id = unused_project.pk
    folder_ids = list(unused_project.document_folders.values_list('pk', flat=True))
    thread_id = unused_project.communication_root_thread.pk

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 204
    assert not Project.objects.filter(pk=project_id).exists()
    assert not DocumentFolder.objects.filter(pk__in=folder_ids).exists()
    assert not CommunicationThread.objects.filter(pk=thread_id).exists()
    assert not DocumentStateEpisode.objects.filter(project_id=project_id).exists()


def test_delete_keeps_durable_audit(admin_client, unused_project):
    project_id = unused_project.pk

    admin_client.delete(delete_url(unused_project))

    audit = AccountingChangeLog.objects.get(
        entity_type='project', object_id=project_id, action='deleted',
    )
    assert 'Unused project' in audit.object_repr
    history = EntityHistory.objects.get(entity_type='project', object_id=project_id)
    assert history.entries.order_by('-number').first().action == 'deleted'


def test_preview_lists_multiple_dependency_counts(admin_client, unused_project):
    add_income(unused_project)
    add_income(unused_project)
    HostingRecord.objects.create(project=unused_project, monthly_value=Decimal('10000'))

    response = admin_client.get(preview_url(unused_project))

    assert response.data['can_delete'] is False
    blockers = {item['key']: item for item in response.data['blockers']}
    assert blockers['incomes'] == {'key': 'incomes', 'label': 'Ingresos', 'count': 2}
    assert blockers['hostings']['count'] == 1


def test_delete_preserves_linked_income(admin_client, unused_project):
    income = add_income(unused_project)

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['code'] == 'project_delete_blocked'
    assert response.data['blockers'][0]['key'] == 'incomes'
    income.refresh_from_db()
    assert income.project_id == unused_project.pk
    assert Project.objects.filter(pk=unused_project.pk).exists()


def test_confirmation_rechecks_new_dependencies(admin_client, unused_project):
    preview = admin_client.get(preview_url(unused_project))
    document = add_document(unused_project)

    response = admin_client.delete(delete_url(unused_project))

    assert preview.data['can_delete'] is True
    assert response.status_code == 409
    assert response.data['blockers'] == [{'key': 'documents', 'label': 'Documentos', 'count': 1}]
    document.refresh_from_db()
    assert document.project_id == unused_project.pk


def test_archived_documents_block_deletion(admin_client, unused_project):
    add_document(unused_project, is_archived=True)

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'][0]['key'] == 'documents'


def test_folder_content_blocks_without_its_own_project_link(admin_client, unused_project):
    folder = unused_project.document_folders.get(name='QA')
    document = add_document(unused_project, folder=folder)
    Document.objects.filter(pk=document.pk).update(project=None)

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    document.refresh_from_db()
    assert document.folder_id == folder.pk


def test_custom_folder_blocks_deletion(admin_client, unused_project):
    folder = DocumentFolder.objects.create(name='Manual folder', project=unused_project)

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert {'key': 'document_folders', 'label': 'Carpetas documentales personalizadas', 'count': 1} in response.data['blockers']
    assert DocumentFolder.objects.filter(pk=folder.pk).exists()


def test_custom_descendant_blocks_without_project_link(admin_client, unused_project):
    root = unused_project.document_folders.get(managed_project=unused_project)
    DocumentFolder.objects.create(name='Custom child', parent=root)

    response = admin_client.get(preview_url(unused_project))

    assert response.data['can_delete'] is False
    assert response.data['blockers'][0]['key'] == 'document_folders'


def test_messages_block_deletion(admin_client, unused_project):
    thread = unused_project.communication_root_thread
    message = CommunicationMessage.objects.create(
        thread=thread, content='Keep this message', channel='whatsapp', direction='incoming',
        status='received', occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    blockers = {item['key']: item['count'] for item in response.data['blockers']}
    assert blockers['messages'] == 1
    assert blockers['communication_threads'] == 1
    assert CommunicationMessage.objects.filter(pk=message.pk).exists()


def test_renamed_automatic_folder_is_preserved(admin_client, unused_project):
    folder = unused_project.document_folders.get(name='QA')
    folder.name = 'Client QA'
    folder.save()

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert DocumentFolder.objects.filter(pk=folder.pk, name='Client QA').exists()


def test_corrected_initial_state_history_blocks_deletion(admin_client, unused_project):
    episode = unused_project.state_episodes.get()
    DocumentStateEpisodeEvent.objects.create(
        episode=episode, event_type='opened_at_corrected', details={'reason': 'Correction'},
    )

    response = admin_client.get(preview_url(unused_project))

    assert response.data['blockers'] == [{'key': 'state_history', 'label': 'Historial de estados añadido', 'count': 1}]


@pytest.mark.parametrize(('method', 'suffix'), [('get', 'delete-preview'), ('delete', 'delete')])
def test_anonymous_cannot_access_deletion(api_client, unused_project, method, suffix):
    url = f'/api/projects/{unused_project.pk}/{suffix}/'

    response = getattr(api_client, method)(url)

    assert response.status_code == 403
    assert Project.objects.filter(pk=unused_project.pk).exists()


@pytest.mark.parametrize(('method', 'suffix'), [('get', 'delete-preview'), ('delete', 'delete')])
def test_client_cannot_access_deletion(api_client, unused_project, method, suffix):
    api_client.force_authenticate(unused_project.client)
    url = f'/api/projects/{unused_project.pk}/{suffix}/'

    response = getattr(api_client, method)(url)

    assert response.status_code == 403
    assert Project.objects.filter(pk=unused_project.pk).exists()


@pytest.mark.parametrize(('method', 'url_factory'), [
    ('get', preview_url),
    ('delete', delete_url),
])
def test_staff_jwt_cannot_access_panel_project_deletion(
    api_client, admin_user, unused_project, method, url_factory,
):
    """Fails if a complete Platform JWT is accepted by a session-only Panel endpoint."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin_user)}')

    response = getattr(api_client, method)(url_factory(unused_project))

    assert (response.status_code, Project.objects.filter(pk=unused_project.pk).exists()) == (403, True)


def test_session_delete_without_csrf_keeps_panel_project(admin_user, unused_project):
    """Fails if a session-authenticated destructive Panel request bypasses CSRF."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)

    response = client.delete(delete_url(unused_project))

    assert (response.status_code, Project.objects.filter(pk=unused_project.pk).exists()) == (403, True)


def test_missing_project_returns_not_found(admin_client):
    response = admin_client.delete('/api/projects/999999/delete/')

    assert response.status_code == 404
