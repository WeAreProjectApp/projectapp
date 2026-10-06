import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from rest_framework.test import APIClient

from accounts.models import Project, ProjectAdminAccess
from accounts.services.credential_cipher import encrypt_secret
from content.models import Document, EntityHistory, EntityRevision, ExpenseRecord
from content.services.entity_history import history_operation
from content.services.project_force_deletion import (
    force_delete_project,
    forced_deletion_preview,
)

pytestmark = pytest.mark.django_db


def document_history(document):
    return EntityHistory.objects.get(entity_type='document', object_id=document.pk)


def test_content_change_preserves_previous_content():
    doc = Document.objects.create(title='Contrato', content_markdown='Primero')
    doc.content_markdown = 'Segundo'
    doc.save()
    versions = document_history(doc).entries.order_by('number')
    assert [row.snapshot['content_markdown'] for row in versions] == ['Primero', 'Segundo']


def test_noop_save_does_not_create_revision():
    doc = Document.objects.create(title='Contrato')
    count = document_history(doc).entries.count()
    doc.save()
    assert document_history(doc).entries.count() == count


def test_bulk_update_preserves_each_previous_title():
    first = Document.objects.create(title='Uno')
    second = Document.objects.create(title='Dos')
    Document.objects.filter(pk__in=[first.pk, second.pk]).update(title='Nuevo')
    assert document_history(first).entries.first().changes == [
        {'field': 'title', 'label': 'Título', 'old': 'Uno', 'new': 'Nuevo'},
    ]
    assert document_history(second).entries.first().changes[0]['old'] == 'Dos'


def test_operation_groups_related_changes_with_actor():
    actor = get_user_model().objects.create_user(username='editor')
    doc = Document.objects.create(title='Contrato')
    before = document_history(doc).entries.count()
    with history_operation(actor=actor, source='test'):
        doc.title = 'Contrato nuevo'
        doc.save()
        doc.document_notes.create(title='Nota', content='Revisar')
    row = document_history(doc).entries.first()
    assert document_history(doc).entries.count() == before + 1
    assert row.actor_label == 'editor'
    assert row.snapshot['title'] == 'Contrato nuevo'
    assert next(iter(row.snapshot['document_notes'].values()))['content'] == 'Revisar'


def test_failed_operation_leaves_no_revision():
    doc = Document.objects.create(title='Original')
    count = document_history(doc).entries.count()
    with pytest.raises(ValueError):
        with history_operation():
            doc.title = 'No debe persistir'
            doc.save()
            raise ValueError('cancelled')
    doc.refresh_from_db()
    assert doc.title == 'Original'
    assert document_history(doc).entries.count() == count


def test_delete_keeps_content_snapshot():
    doc = Document.objects.create(title='Contrato', content_markdown='Valioso')
    head = document_history(doc)
    doc.delete()
    row = head.entries.first()
    assert row.action == 'deleted'
    assert row.snapshot['content_markdown'] == 'Valioso'


def test_admin_can_compare_versions():
    user = get_user_model().objects.create_user(username='staff', is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    doc = Document.objects.create(title='Contrato', content_markdown='Antes')
    first = document_history(doc).entries.first()
    doc.content_markdown = 'Después'
    doc.save()
    last = document_history(doc).entries.first()
    response = client.get(f'/api/entity-history/document/{doc.pk}/compare/', {'from': first.pk, 'to': last.pk})
    assert response.status_code == 200
    assert response.data['changes'][0]['new'] == 'Después'


def test_client_cannot_read_internal_history():
    user = get_user_model().objects.create_user(username='customer')
    client = APIClient()
    client.force_authenticate(user)
    doc = Document.objects.create(title='Privado')
    response = client.get(f'/api/entity-history/document/{doc.pk}/')
    assert response.status_code == 403


def test_compare_rejects_legacy_event_without_complete_version():
    """Fails if a legacy event with no snapshot becomes comparable."""
    user = get_user_model().objects.create_user(username='staff', is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    doc = Document.objects.create(title='Contrato')
    head = document_history(doc)
    legacy = EntityRevision.objects.create(
        history=head, action='updated', snapshot=None, source='legacy:test',
    )
    complete = head.entries.exclude(pk=legacy.pk).first()

    response = client.get(
        f'/api/entity-history/document/{doc.pk}/compare/',
        {'from': legacy.pk, 'to': complete.pk},
    )

    assert response.status_code == 400
    assert response.data['version'] == 'Este evento antiguo no contiene una versión completa.'


def test_compare_hides_revision_from_another_document():
    """Fails if a revision id can expose another document's history."""
    user = get_user_model().objects.create_user(username='staff', is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    first = Document.objects.create(title='Primero')
    second = Document.objects.create(title='Segundo')
    first_version = document_history(first).entries.first()
    second_version = document_history(second).entries.first()

    response = client.get(
        f'/api/entity-history/document/{first.pk}/compare/',
        {'from': first_version.pk, 'to': second_version.pk},
    )

    assert response.status_code == 404


def test_project_history_keeps_secret_out_of_normal_payloads():
    """Fails if an encrypted project password leaks from list, version, or comparison."""
    user = get_user_model().objects.create_user(username='staff', is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    project = Project.objects.create(name='Portal', client=user)
    first_token = encrypt_secret('first-password')
    ProjectAdminAccess.objects.create(
        project=project,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_password_encrypted=first_token,
    )
    access = project.admin_accesses.get()
    second_token = encrypt_secret('second-password')
    access.admin_password_encrypted = second_token
    access.save(update_fields=['admin_password_encrypted'])
    versions = EntityHistory.objects.get(entity_type='project', object_id=project.pk).entries
    newer, older = versions.order_by('-id')[:2]

    listing = client.get(f'/api/entity-history/project/{project.pk}/')
    version = client.get(f'/api/entity-history/project/{project.pk}/versions/{newer.pk}/')
    comparison = client.get(
        f'/api/entity-history/project/{project.pk}/compare/',
        {'from': older.pk, 'to': newer.pk},
    )

    assert listing.status_code == version.status_code == comparison.status_code == 200
    assert 'first-password' not in str(listing.data)
    assert 'second-password' not in str(listing.data)
    assert first_token not in str(listing.data)
    assert second_token not in str(listing.data)
    assert 'first-password' not in str(version.data)
    assert 'second-password' not in str(version.data)
    assert first_token not in str(version.data)
    assert second_token not in str(version.data)
    assert 'first-password' not in str(comparison.data)
    assert 'second-password' not in str(comparison.data)
    assert first_token not in str(comparison.data)
    assert second_token not in str(comparison.data)
    assert comparison.data['changes'][-1]['new'] == {'protected': True, 'present': True}


def project_reveal_context():
    user = get_user_model().objects.create_user(username='staff', is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    project = Project.objects.create(name='Portal', client=user)
    ProjectAdminAccess.objects.create(
        project=project,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_password_encrypted=encrypt_secret('revealed-password'),
    )
    version = EntityHistory.objects.get(entity_type='project', object_id=project.pk).entries.first()
    return client, project, version


def test_project_history_reveal_returns_secret_with_no_store():
    """Fails if a valid protected reveal omits the browser cache guard."""
    client, project, version = project_reveal_context()
    base = f'/api/entity-history/project/{project.pk}/versions/{version.pk}/reveal/'

    reveal = client.post(base, {'field': 'access.production.password'}, format='json')

    assert reveal.status_code == 200
    assert reveal.data['secret'] == 'revealed-password'
    assert reveal['Cache-Control'] == 'no-store, max-age=0'


def test_project_history_reveal_rejects_unknown_protected_field():
    """Fails if a protected reveal accepts a field absent from that revision."""
    client, project, version = project_reveal_context()
    base = f'/api/entity-history/project/{project.pk}/versions/{version.pk}/reveal/'

    invalid = client.post(base, {'field': 'access.production.username'}, format='json')

    assert invalid.status_code == 400
    assert invalid.data['field'] == 'Campo protegido no disponible en esta versión.'


def test_project_history_reveal_rejects_session_post_without_csrf():
    """Fails if the secret endpoint accepts a session write without CSRF validation."""
    user = get_user_model().objects.create_user(
        username='session-staff', password='secret-pass', is_staff=True,
    )
    project = Project.objects.create(name='Portal', client=user)
    ProjectAdminAccess.objects.create(
        project=project,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_password_encrypted=encrypt_secret('csrf-password'),
    )
    version = EntityHistory.objects.get(entity_type='project', object_id=project.pk).entries.first()
    client = Client(enforce_csrf_checks=True)
    assert client.login(username='session-staff', password='secret-pass')

    response = client.post(
        f'/api/entity-history/project/{project.pk}/versions/{version.pk}/reveal/',
        {'field': 'access.production.password'},
    )

    assert response.status_code == 403


def test_expense_queryset_update_keeps_previous_value_in_history(make_expense):
    """Fails if the custom expense manager bypasses bulk-update history capture."""
    expense = make_expense(concept='Costo anterior')
    head = EntityHistory.objects.get(entity_type='expense', object_id=expense.pk)
    before = head.entries.count()

    ExpenseRecord.objects.filter(pk=expense.pk).update(concept='Costo posterior')

    row = head.entries.first()
    assert head.entries.count() == before + 1
    assert row.changes == [
        {'field': 'concept', 'label': 'Concepto', 'old': 'Costo anterior', 'new': 'Costo posterior'},
    ]


def test_failed_expense_history_operation_rolls_back_atomically(make_expense):
    """Fails if a failed aggregate write persists either the expense or its revision."""
    expense = make_expense(concept='Costo original')
    head = EntityHistory.objects.get(entity_type='expense', object_id=expense.pk)
    before = head.entries.count()

    with pytest.raises(ValueError, match='cancelled'):
        with history_operation():
            expense.concept = 'Costo rechazado'
            expense.save(update_fields=['concept'])
            raise ValueError('cancelled')

    expense.refresh_from_db()
    assert expense.concept == 'Costo original'
    assert head.entries.count() == before


def test_bulk_create_keeps_history_when_database_does_not_return_ids(monkeypatch):
    """Fails if the MySQL bulk-insert fallback loses IDs or created document histories."""
    monkeypatch.setattr(
        type(connection.features), 'can_return_rows_from_bulk_insert', property(lambda _features: False),
    )
    documents = Document.objects.bulk_create([
        Document(title='Importado uno'),
        Document(title='Importado dos'),
    ])

    assert len({document.pk for document in documents if document.pk is not None}) == 2
    assert list(EntityHistory.objects.filter(
        entity_type='document', object_id__in=[document.pk for document in documents],
    ).values_list('revision', flat=True).order_by('object_id')) == [1, 1]


def test_deleting_project_records_document_project_removal_in_same_operation(superuser):
    """Fails if retaining a document loses its project-removal audit trail."""
    client = get_user_model().objects.create_user(username='project-client')
    project = Project.objects.create(name='Proyecto retirado', client=client)
    document = Document.objects.create(title='Contrato ligado', project=project)
    project_id = project.pk
    preview = forced_deletion_preview(project, actor=superuser, delete_keys=[])

    force_delete_project(
        project_id, actor=superuser, confirmation='DELETE',
        impact_token=preview['impact_token'], delete_keys=[],
    )

    document_change = document_history(document).entries.first()
    project_deletion = EntityHistory.objects.get(
        entity_type='project', object_id=project_id,
    ).entries.first()
    assert document_change.snapshot['project'] is None
    assert document_change.changes == [{
        'field': 'project', 'label': 'Proyecto',
        'old': {'id': project_id, 'label': 'Proyecto retirado'}, 'new': None,
    }]
    assert document_change.operation_id == project_deletion.operation_id
