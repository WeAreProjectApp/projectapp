"""Atomicity and per-document authorization of the move endpoint."""
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.urls import reverse

from content.models import Document, DocumentFolder, DocumentType, McpConnector

pytestmark = pytest.mark.django_db


@pytest.fixture
def documents():
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    first = Document.objects.create(title='First', document_type=kind, content_markdown='# First')
    second = Document.objects.create(title='Second', document_type=kind, content_markdown='# Second')
    return first, second


def test_move_request_moves_every_document(admin_client, documents):
    first, second = documents
    target = DocumentFolder.objects.create(name='Target')
    response = admin_client.post(reverse('move-documents'), {'document_ids': [first.pk, second.pk], 'folder_id': target.pk}, format='json')
    assert response.status_code == 200
    assert {row['status'] for row in response.data['results']} == {'moved'}
    assert Document.objects.filter(pk__in=[first.pk, second.pk], folder=target).count() == 2
    assert 'markdown' not in response.data['results'][0]['document']


def test_move_request_reports_unchanged_destination(admin_client, documents):
    first, _ = documents
    response = admin_client.post(reverse('move-documents'), {'document_ids': [first.pk], 'folder_id': None}, format='json')
    assert response.status_code == 200
    assert response.data['results'][0]['status'] == 'unchanged'


def test_missing_document_aborts_valid_move(admin_client, documents):
    first, _ = documents
    target = DocumentFolder.objects.create(name='Target')
    response = admin_client.post(reverse('move-documents'), {'document_ids': [first.pk, 999999], 'folder_id': target.pk}, format='json')
    assert response.status_code == 409
    assert [row['status'] for row in response.data['results']] == ['aborted', 'failed']
    first.refresh_from_db()
    assert first.folder_id is None


def test_archived_document_aborts_move_request(admin_client, documents):
    first, second = documents
    second.is_archived = True
    second.save()
    target = DocumentFolder.objects.create(name='Target')
    response = admin_client.post(reverse('move-documents'), {'document_ids': [first.pk, second.pk], 'folder_id': target.pk}, format='json')
    assert response.status_code == 409
    assert response.data['results'][1]['reason'] == 'archived'
    assert not Document.objects.filter(folder=target).exists()


@pytest.mark.parametrize('attributes', [{'is_archived': True}, {'system_key': 'test:auto'}])
def test_protected_destination_aborts_move_request(admin_client, documents, attributes):
    first, second = documents
    target = DocumentFolder.objects.create(name='Target', **attributes)
    response = admin_client.post(reverse('move-documents'), {'document_ids': [first.pk, second.pk], 'folder_id': target.pk}, format='json')
    assert response.status_code == 409
    assert not Document.objects.filter(folder=target).exists()


@pytest.mark.parametrize('ids', [[], [1, 1], [0], ['wrong']])
def test_invalid_move_ids_are_rejected(admin_client, ids):
    response = admin_client.post(reverse('move-documents'), {'document_ids': ids, 'folder_id': None}, format='json')
    assert response.status_code == 400
    assert 'document_ids' in response.data


def test_move_request_requires_staff(api_client, documents):
    first, _ = documents
    response = api_client.post(reverse('move-documents'), {'document_ids': [first.pk], 'folder_id': None}, format='json')
    assert response.status_code in (401, 403)


def test_mcp_move_request_returns_per_id_error_details(api_client, superuser, documents):
    first, _ = documents
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documents'})
    connector.is_active = True
    connector.save()
    token = connector.generate_token()
    response = api_client.post(f'/api/mcp/documents/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'move_documents', 'arguments': {'document_ids': [first.pk, 999999], 'folder_id': None}},
    }, format='json')
    result = response.data['result']
    assert result['isError'] is True
    assert result['structuredContent']['error']['details']['results'][0]['status'] == 'aborted'


def _second_save_raises_integrity_error(original_save):
    calls = 0

    def save_then_fail(document, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IntegrityError('destination relation rejected')
        return original_save(document, *args, **kwargs)

    return save_then_fail


def test_move_request_rolls_back_when_the_second_write_fails(admin_client, documents):
    """Falla si un error de base de datos deja el primer documento movido parcialmente."""
    first, second = documents
    target = DocumentFolder.objects.create(name='Target')
    # Inject the database fault at the ORM write boundary, after one real save.
    guarded_save = _second_save_raises_integrity_error(Document.save)
    with patch.object(Document, 'save', guarded_save):
        response = admin_client.post(
            reverse('move-documents'),
            {'document_ids': [first.pk, second.pk], 'folder_id': target.pk},
            format='json',
        )
    first.refresh_from_db()
    second.refresh_from_db()

    assert response.status_code == 409
    assert [row['status'] for row in response.data['results']] == ['aborted', 'failed']
    assert first.folder_id is None
    assert second.folder_id is None
