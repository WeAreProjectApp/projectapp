from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Project, UserProfile
from content.models import Document, DocumentFolder, DocumentThread, DocumentThreadItem
from content.services.document_thread_service import create_document_thread


pytestmark = pytest.mark.django_db


@pytest.fixture
def documents():
    return [
        Document.objects.create(
            title=title,
            issue_date=date(2026, 8, index),
            content_markdown=f'# {title}',
        )
        for index, title in enumerate(
            ('Acta inicial', 'Corrección', 'Aprobación', 'Anexo archivado'),
            start=1,
        )
    ]


@pytest.fixture
def thread(documents, admin_user):
    return create_document_thread(
        title='Entrega del proyecto',
        items=[
            {'document_id': documents[0].pk},
            {'document_id': documents[1].pk},
        ],
        actor=admin_user,
    )


def test_thread_detail_requires_an_admin(api_client, documents):
    response = api_client.get(
        reverse('document-thread-detail', kwargs={'document_id': documents[0].pk}),
    )

    assert response.status_code in (401, 403)


def test_thread_detail_returns_null_for_a_standalone_document(admin_client, documents):
    response = admin_client.get(
        reverse('document-thread-detail', kwargs={'document_id': documents[0].pk}),
    )

    assert response.status_code == 200
    assert response.json() is None


def test_create_thread_returns_chronological_items(admin_client, documents):
    response = admin_client.post(
        reverse('create-document-thread'),
        {
            'title': 'Historia de aprobación',
            'items': [
                {'document_id': documents[1].pk, 'occurred_on': '2026-08-20'},
                {'document_id': documents[0].pk, 'occurred_on': '2026-08-01'},
            ],
        },
        format='json',
    )

    assert response.status_code == 201
    assert [row['document']['id'] for row in response.json()['items']] == [
        documents[0].pk, documents[1].pk,
    ]
    assert response.json()['document_count'] == 2


def test_create_thread_reports_a_membership_conflict(
    admin_client, documents, thread,
):
    response = admin_client.post(
        reverse('create-document-thread'),
        {
            'title': 'Otro hilo',
            'items': [
                {'document_id': documents[0].pk},
                {'document_id': documents[2].pk},
            ],
        },
        format='json',
    )

    assert response.status_code == 409
    assert response.json()['code'] == 'document_already_threaded'


def test_candidates_hide_archived_documents_by_default(admin_client, documents):
    Document.objects.filter(pk=documents[3].pk).update(is_archived=True)

    response = admin_client.get(
        reverse('document-thread-candidates'),
        {'document_id': documents[0].pk},
    )

    assert documents[3].pk not in {row['id'] for row in response.json()['results']}


def test_candidates_include_archived_documents_on_request(admin_client, documents):
    Document.objects.filter(pk=documents[3].pk).update(is_archived=True)

    response = admin_client.get(
        reverse('document-thread-candidates'),
        {'document_id': documents[0].pk, 'scope': 'all'},
    )

    archived = next(row for row in response.json()['results'] if row['id'] == documents[3].pk)
    assert archived['is_archived'] is True


def test_candidates_expose_other_thread_documents_as_unavailable(
    admin_client, documents, thread,
):
    response = admin_client.get(
        reverse('document-thread-candidates'),
        {'document_id': documents[2].pk},
    )

    candidate = next(row for row in response.json()['results'] if row['id'] == documents[0].pk)
    assert candidate['available'] is False
    assert candidate['thread_summary']['id'] == thread.pk


@pytest.mark.parametrize('field', ('title', 'folder', 'client', 'project'))
def test_candidates_searches_document_metadata(admin_client, documents, field):
    user = get_user_model().objects.create_user(username=f'{field}@example.com')
    profile = UserProfile.objects.create(
        user=user,
        company_name='Cliente Boreal',
    )
    project = Project.objects.create(name='Proyecto Boreal', client=user)
    folder = DocumentFolder.objects.create(name='Carpeta Boreal')
    target = documents[1]
    target.title = 'Informe Boreal'
    target.folder = folder
    target.client_user = user
    target.client_name = 'Cliente Boreal'
    target.project = project
    target.save()
    query = {
        'title': 'Informe Boreal',
        'folder': 'Carpeta Boreal',
        'client': profile.company_name,
        'project': project.name,
    }[field]

    response = admin_client.get(
        reverse('document-thread-candidates'),
        {'document_id': documents[0].pk, 'search': query},
    )

    assert [row['id'] for row in response.json()['results']] == [target.pk]


def test_document_delete_is_blocked_while_linked(admin_client, documents, thread):
    response = admin_client.delete(
        reverse('delete-document', kwargs={'document_id': documents[0].pk}),
    )

    assert response.status_code == 409
    assert response.json()['code'] == 'document_used_in_thread'
    assert Document.objects.filter(pk=documents[0].pk).exists()


def test_archive_keeps_linked_document_in_thread(admin_client, documents, thread):
    """Falla si archivar un documento elimina su pertenencia al hilo."""
    document = documents[0]

    archive_response = admin_client.patch(
        reverse('archive-document', kwargs={'document_id': document.pk}),
    )
    detail_response = admin_client.get(
        reverse('document-thread-detail', kwargs={'document_id': document.pk}),
    )

    assert archive_response.status_code == 200
    assert detail_response.status_code == 200
    assert DocumentThreadItem.objects.get(document=document).thread_id == thread.pk
    archived_item = next(
        item for item in detail_response.json()['items']
        if item['document']['id'] == document.pk
    )
    assert archived_item['document']['is_archived'] is True


def test_thread_patch_renames_without_replacing_members(admin_client, thread):
    response = admin_client.patch(
        reverse('update-or-delete-document-thread', kwargs={'thread_id': thread.pk}),
        {'title': 'Aprobación final'},
        format='json',
    )

    assert response.status_code == 200
    assert response.json()['title'] == 'Aprobación final'
    assert response.json()['document_count'] == 2


def test_thread_patch_dissolves_when_one_member_remains(
    admin_client, documents, thread,
):
    response = admin_client.patch(
        reverse('update-or-delete-document-thread', kwargs={'thread_id': thread.pk}),
        {'items': [{'document_id': documents[0].pk}]},
        format='json',
    )

    assert response.status_code == 200
    assert response.json() == {'thread': None, 'dissolved': True}
    assert not DocumentThread.objects.filter(pk=thread.pk).exists()


def test_document_list_exposes_thread_summary(admin_client, documents, thread):
    response = admin_client.get(reverse('list-documents'))

    row = next(item for item in response.json() if item['id'] == documents[0].pk)
    assert row['thread_summary'] == {
        'id': thread.pk,
        'title': 'Entrega del proyecto',
        'document_count': 2,
    }


def test_duplicate_does_not_inherit_thread_membership(admin_client, documents, thread):
    response = admin_client.post(
        reverse('duplicate-document', kwargs={'document_id': documents[0].pk}),
    )

    assert response.status_code == 201
    assert not DocumentThreadItem.objects.filter(document_id=response.json()['id']).exists()


# ── Índice de hilos ──────────────────────────────────────────────────────────

@pytest.fixture
def second_thread(documents, admin_user):
    return create_document_thread(
        title='Anexos del cierre',
        items=[
            {'document_id': documents[2].pk},
            {'document_id': documents[3].pk},
        ],
        actor=admin_user,
    )


def test_thread_index_requires_an_admin(api_client, thread):
    response = api_client.get(reverse('create-document-thread'))

    assert response.status_code in (401, 403)


def test_thread_index_lists_threads_with_their_span(admin_client, thread):
    response = admin_client.get(reverse('create-document-thread'))

    assert response.status_code == 200
    payload = response.json()
    assert payload['count'] == 1
    row = payload['results'][0]
    assert row['id'] == thread.pk
    assert row['title'] == 'Entrega del proyecto'
    assert row['document_count'] == 2
    assert row['first_occurred_on'] == '2026-08-01'
    assert row['last_occurred_on'] == '2026-08-02'
    assert row['latest_item']['title'] == 'Corrección'
    assert [member['title'] for member in row['documents']] == [
        'Acta inicial', 'Corrección',
    ]
    assert row['documents_truncated'] is False


def test_thread_index_orders_alphabetically_on_request(
    admin_client, thread, second_thread,
):
    response = admin_client.get(reverse('create-document-thread'), {'order': 'title'})

    assert response.status_code == 200
    assert [row['title'] for row in response.json()['results']] == [
        'Anexos del cierre', 'Entrega del proyecto',
    ]


def test_thread_index_rejects_an_unknown_order(admin_client, thread):
    response = admin_client.get(reverse('create-document-thread'), {'order': 'chaos'})

    assert response.status_code == 400
    assert 'order' in response.json()


def test_thread_index_rejects_a_malformed_client_id(admin_client, thread):
    response = admin_client.get(reverse('create-document-thread'), {'client_id': 'abc'})

    assert response.status_code == 400
    assert 'client_id' in response.json()


def test_thread_index_searches_by_member_document_title(
    admin_client, thread, second_thread,
):
    response = admin_client.get(
        reverse('create-document-thread'), {'search': 'Aprobación'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['count'] == 1
    assert payload['results'][0]['title'] == 'Anexos del cierre'
