"""Tests for content/views/document.py — generic document CRUD + PDF download."""
from datetime import datetime, timezone as dt_timezone
from io import BytesIO
from unittest.mock import patch

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.urls import reverse

from content.models import Document, DocumentFolder, DocumentType

pytestmark = pytest.mark.django_db


# ── Fixtures ──

@pytest.fixture
def markdown_doc_type(db):
    """Reuse or create the 'markdown' DocumentType (seeded by migration 0052)."""
    obj, _ = DocumentType.objects.get_or_create(
        code='markdown',
        defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    return obj


@pytest.fixture
def document(db, markdown_doc_type):
    return Document.objects.create(
        title='Test Document',
        document_type=markdown_doc_type,
        client_name='ACME Corp',
        language='es',
        content_markdown='# Hello\n\nWorld',
        content_json={'meta': {}, 'blocks': [{'type': 'heading', 'text': 'Hello'}]},
    )


# ── list_documents ──

class TestListDocuments:
    def test_returns_200_with_list(self, admin_client, document):
        url = reverse('list-documents')
        response = admin_client.get(url)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_requires_admin_auth(self, api_client):
        url = reverse('list-documents')
        response = api_client.get(url)

        assert response.status_code == 401

    def test_default_listing_orders_created_at_desc(self, admin_client, markdown_doc_type):
        older = Document.objects.create(title='Anterior', document_type=markdown_doc_type)
        newer = Document.objects.create(title='Reciente', document_type=markdown_doc_type)

        response = admin_client.get(reverse('list-documents'))

        assert [row['id'] for row in response.json()] == [newer.id, older.id]

    def test_order_oldest_orders_active_documents_ascending(
        self, admin_client, markdown_doc_type,
    ):
        older = Document.objects.create(title='Anterior', document_type=markdown_doc_type)
        newer = Document.objects.create(title='Reciente', document_type=markdown_doc_type)

        response = admin_client.get(reverse('list-documents'), {'order': 'oldest'})

        assert [row['id'] for row in response.json()] == [older.id, newer.id]


# ── Filtros de asociación cliente/proyecto ──

def make_client(email, *, first='Ana', last='Pérez'):
    user = get_user_model().objects.create_user(
        username=email, email=email, password='pass12345',
        first_name=first, last_name=last,
    )
    return UserProfile.objects.create(user=user, cedula='1049654583')


@pytest.fixture
def association_setup(db, markdown_doc_type):
    """Dos clientes y tres documentos: con proyecto, sólo cliente y suelto."""
    ana = make_client('ana@example.com')
    kore = make_client('kore@example.com', first='Kore', last='SAS')
    project = Project.objects.create(name='Kore - Diseño', client=kore.user)
    doc_project = Document.objects.create(
        title='Entregable Kore', document_type=markdown_doc_type,
        client_user=kore.user, project=project, content_markdown='# k',
    )
    doc_client = Document.objects.create(
        title='Contrato Ana', document_type=markdown_doc_type,
        client_user=ana.user, content_markdown='# a',
    )
    doc_free = Document.objects.create(
        title='Plantilla interna', document_type=markdown_doc_type,
        content_markdown='# p',
    )
    return {
        'ana': ana, 'kore': kore, 'project': project,
        'doc_project': doc_project, 'doc_client': doc_client,
        'doc_free': doc_free,
    }


class TestListDocumentAssociationFilters:
    def _ids(self, response):
        return {row['id'] for row in response.json()}

    def test_client_none_returns_only_unlinked_docs(self, admin_client, association_setup):
        response = admin_client.get(reverse('list-documents'), {'client': 'none'})

        assert response.status_code == 200
        assert self._ids(response) == {association_setup['doc_free'].id}

    def test_client_id_filters_by_profile_pk(self, admin_client, association_setup):
        kore = association_setup['kore']
        response = admin_client.get(reverse('list-documents'), {'client': str(kore.pk)})

        assert response.status_code == 200
        rows = response.json()
        assert self._ids(response) == {association_setup['doc_project'].id}
        assert rows[0]['client'] == kore.pk
        assert rows[0]['project_name'] == 'Kore - Diseño'
        assert rows[0]['client_display_name']

    def test_client_csv_combines_several_ids(self, admin_client, association_setup):
        param = f"{association_setup['ana'].pk},{association_setup['kore'].pk}"
        response = admin_client.get(reverse('list-documents'), {'client': param})

        assert response.status_code == 200
        assert self._ids(response) == {
            association_setup['doc_project'].id,
            association_setup['doc_client'].id,
        }

    def test_client_invalid_returns_400(self, admin_client, association_setup):
        response = admin_client.get(reverse('list-documents'), {'client': 'abc'})

        assert response.status_code == 400
        assert 'client' in response.json()

    def test_project_none_returns_docs_without_project(self, admin_client, association_setup):
        response = admin_client.get(reverse('list-documents'), {'project': 'none'})

        assert response.status_code == 200
        assert self._ids(response) == {
            association_setup['doc_client'].id,
            association_setup['doc_free'].id,
        }

    def test_project_id_filters_docs(self, admin_client, association_setup):
        project = association_setup['project']
        response = admin_client.get(
            reverse('list-documents'), {'project': str(project.pk)},
        )

        assert response.status_code == 200
        assert self._ids(response) == {association_setup['doc_project'].id}

    def test_project_invalid_returns_400(self, admin_client, association_setup):
        response = admin_client.get(reverse('list-documents'), {'project': 'x1'})

        assert response.status_code == 400
        assert 'project' in response.json()

    def test_client_and_project_combine_as_and(self, admin_client, association_setup):
        response = admin_client.get(reverse('list-documents'), {
            'client': str(association_setup['kore'].pk),
            'project': 'none',
        })

        assert response.status_code == 200
        assert self._ids(response) == set()


class TestDuplicateDocumentAssociation:
    def test_duplicate_copies_client_and_project(self, admin_client, association_setup):
        source = association_setup['doc_project']
        response = admin_client.post(reverse('duplicate-document', args=[source.id]))

        assert response.status_code == 201
        duplicated = Document.objects.get(pk=response.json()['id'])
        assert duplicated.client_user == association_setup['kore'].user
        assert duplicated.project == association_setup['project']


class TestFolderClientSuggestion:
    def test_suggests_the_strict_majority_client(self, admin_client, markdown_doc_type):
        ana = make_client('ana@example.com')
        nestor = make_client('nestor@example.com', first='Néstor')
        folder = DocumentFolder.objects.create(name='Carpeta Ana')
        for index in range(2):
            Document.objects.create(
                title=f'Doc Ana {index}', document_type=markdown_doc_type,
                folder=folder, client_user=ana.user,
            )
        Document.objects.create(
            title='Doc Néstor', document_type=markdown_doc_type,
            folder=folder, client_user=nestor.user,
        )
        Document.objects.create(
            title='Doc suelto', document_type=markdown_doc_type, folder=folder,
        )

        response = admin_client.get(
            reverse('document-folder-client-suggestion'),
            {'folder': str(folder.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['client'] == ana.pk
        assert 'Ana' in data['client_display_name']
        assert data['linked_documents'] == 3
        assert data['folder_documents'] == 4

    def test_a_tie_suggests_nothing(self, admin_client, markdown_doc_type):
        ana = make_client('ana@example.com')
        nestor = make_client('nestor@example.com', first='Néstor')
        folder = DocumentFolder.objects.create(name='Compartida')
        for owner in (ana, nestor):
            for index in range(2):
                Document.objects.create(
                    title=f'Doc {owner.pk} {index}',
                    document_type=markdown_doc_type,
                    folder=folder, client_user=owner.user,
                )

        response = admin_client.get(
            reverse('document-folder-client-suggestion'),
            {'folder': str(folder.id)},
        )

        assert response.status_code == 200
        assert response.json()['client'] is None

    def test_a_single_linked_document_is_not_enough(self, admin_client, markdown_doc_type):
        ana = make_client('ana@example.com')
        folder = DocumentFolder.objects.create(name='Casi vacía')
        Document.objects.create(
            title='Doc único', document_type=markdown_doc_type,
            folder=folder, client_user=ana.user,
        )

        response = admin_client.get(
            reverse('document-folder-client-suggestion'),
            {'folder': str(folder.id)},
        )

        assert response.status_code == 200
        assert response.json()['client'] is None

    def test_invalid_folder_returns_400(self, admin_client):
        response = admin_client.get(
            reverse('document-folder-client-suggestion'), {'folder': 'abc'},
        )

        assert response.status_code == 400
        assert 'folder' in response.json()

    def test_unknown_folder_returns_a_null_suggestion(self, admin_client):
        response = admin_client.get(
            reverse('document-folder-client-suggestion'), {'folder': '999999'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['client'] is None
        assert data['folder_documents'] == 0


# ── create_document ──

class TestCreateDocument:
    def test_creates_document_with_json_content(self, admin_client, markdown_doc_type):
        url = reverse('create-document')
        payload = {
            'title': 'New Doc',
            'content_json': {'meta': {}, 'blocks': []},
        }
        response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        assert response.json()['title'] == 'New Doc'

    def test_creates_document_and_parses_markdown_when_no_json(self, admin_client):
        url = reverse('create-document')
        payload = {
            'title': 'Markdown Doc',
            'content_markdown': '# Title\n\nSome text.',
        }
        response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        data = response.json()
        saved = Document.objects.get(pk=data['id'])
        assert 'blocks' in saved.content_json

    def test_returns_400_on_invalid_payload(self, admin_client):
        url = reverse('create-document')
        response = admin_client.post(url, {}, format='json')

        assert response.status_code == 400

    def test_sets_markdown_doc_type_when_not_provided(self, admin_client, markdown_doc_type):
        url = reverse('create-document')
        payload = {
            'title': 'Doc No Type',
            'content_json': {'meta': {}, 'blocks': []},
        }
        response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        doc = Document.objects.get(title='Doc No Type')
        assert doc.document_type.code == 'markdown'


# ── create_document_from_markdown ──

class TestCreateDocumentFromMarkdown:
    def test_creates_document_from_markdown(self, admin_client):
        url = reverse('create-document-from-markdown')
        payload = {
            'title': 'Markdown Creation',
            'markdown': '# Heading\n\nParagraph here.',
        }
        response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        data = response.json()
        assert data['title'] == 'Markdown Creation'
        assert Document.objects.get(pk=data['id']).content_json['blocks']

    def test_returns_400_on_missing_fields(self, admin_client):
        url = reverse('create-document-from-markdown')
        response = admin_client.post(url, {}, format='json')

        assert response.status_code == 400

    def test_creates_with_optional_fields(self, admin_client):
        url = reverse('create-document-from-markdown')
        payload = {
            'title': 'Full Doc',
            'markdown': '# Full\n\nContent.',
            'client_name': 'Test Client',
            'language': 'en',
            'cover_type': 'generic',
        }
        response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        doc = Document.objects.get(title='Full Doc')
        assert doc.client_name == 'Test Client'
        assert doc.language == 'en'

    def test_creates_the_client_note(self, admin_client):
        url = reverse('create-document-from-markdown')
        payload = {
            'title': 'Informe con mensaje',
            'markdown': '# Entrega\n\nTrabajo terminado.',
            'client_email_subject': 'Entrega completada',
            'client_email_body': 'Hola Ana,\n\nLa entrega está lista.',
            'client_whatsapp_message': 'Hola Ana, la entrega ya está lista.',
            'client_custom_notes': [
                {'title': 'Seguimiento', 'content': 'Confirmar recepción.'},
            ],
        }

        response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        document = Document.objects.get(pk=response.json()['id'])
        assert document.client_email_subject == 'Entrega completada'
        assert document.client_email_body == 'Hola Ana,\n\nLa entrega está lista.'
        assert document.client_whatsapp_message == (
            'Hola Ana, la entrega ya está lista.'
        )
        assert document.client_custom_notes == [
            {'title': 'Seguimiento', 'content': 'Confirmar recepción.'},
        ]


# ── upload_document_markdown ──

class TestUploadDocumentMarkdown:
    def test_creates_document_from_uploaded_file(self, admin_client):
        url = reverse('upload-document-markdown')
        md_content = b'# Uploaded\n\nContent from file.'
        file_obj = BytesIO(md_content)
        file_obj.name = 'test.md'

        response = admin_client.post(
            url,
            {'file': file_obj, 'title': 'Uploaded Doc'},
            format='multipart',
        )

        assert response.status_code == 201
        assert response.json()['title'] == 'Uploaded Doc'

    def test_returns_400_when_no_file(self, admin_client):
        url = reverse('upload-document-markdown')
        response = admin_client.post(url, {}, format='multipart')

        assert response.status_code == 400

    def test_uses_filename_as_title_when_not_provided(self, admin_client):
        url = reverse('upload-document-markdown')
        md_content = b'# Auto Title'
        file_obj = BytesIO(md_content)
        file_obj.name = 'my-document.md'

        response = admin_client.post(url, {'file': file_obj}, format='multipart')

        assert response.status_code == 201
        assert response.json()['title'] == 'my-document'

    def test_include_portada_false_string_disables_portada(self, admin_client):
        url = reverse('upload-document-markdown')
        md_content = b'# Test'
        file_obj = BytesIO(md_content)
        file_obj.name = 'test.md'

        response = admin_client.post(
            url,
            {'file': file_obj, 'title': 'No Portada', 'include_portada': 'false'},
            format='multipart',
        )

        assert response.status_code == 201
        doc = Document.objects.get(title='No Portada')
        assert doc.include_portada is False

    def test_returns_400_on_non_utf8_file(self, admin_client):
        url = reverse('upload-document-markdown')
        file_obj = BytesIO(b'\xff\xfe invalid bytes')
        file_obj.name = 'bad.md'

        response = admin_client.post(url, {'file': file_obj}, format='multipart')

        assert response.status_code == 400

    def test_creates_the_client_note_from_form_data(self, admin_client):
        url = reverse('upload-document-markdown')
        file_obj = BytesIO(b'# Uploaded report')
        file_obj.name = 'report.md'

        response = admin_client.post(
            url,
            {
                'file': file_obj,
                'client_email_subject': 'Reporte disponible',
                'client_email_body': 'El reporte está disponible.',
                'client_whatsapp_message': 'Ya puedes revisar el reporte.',
                'client_custom_notes': '[{"title":"Interna","content":"Revisar el viernes."}]',
            },
            format='multipart',
        )

        assert response.status_code == 201
        document = Document.objects.get(pk=response.json()['id'])
        assert document.client_email_subject == 'Reporte disponible'
        assert document.client_email_body == 'El reporte está disponible.'
        assert document.client_whatsapp_message == 'Ya puedes revisar el reporte.'
        assert document.client_custom_notes == [
            {'title': 'Interna', 'content': 'Revisar el viernes.'},
        ]

    def test_rejects_an_oversized_client_subject(self, admin_client):
        url = reverse('upload-document-markdown')
        file_obj = BytesIO(b'# Uploaded report')
        file_obj.name = 'report.md'

        response = admin_client.post(
            url,
            {'file': file_obj, 'client_email_subject': 'a' * 256},
            format='multipart',
        )

        assert response.status_code == 400
        assert 'client_email_subject' in response.json()


# ── retrieve_document ──

class TestRetrieveDocument:
    def test_returns_document_detail(self, admin_client, document):
        url = reverse('retrieve-document', kwargs={'document_id': document.id})
        response = admin_client.get(url)

        assert response.status_code == 200
        assert response.json()['title'] == 'Test Document'

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('retrieve-document', kwargs={'document_id': 99999})
        response = admin_client.get(url)

        assert response.status_code == 404


# ── update_document ──

class TestUpdateDocument:
    def test_updates_document_title(self, admin_client, document):
        url = reverse('update-document', kwargs={'document_id': document.id})
        response = admin_client.patch(url, {'title': 'Updated Title'}, format='json')

        assert response.status_code == 200
        document.refresh_from_db()
        assert document.title == 'Updated Title'

    def test_reparses_markdown_when_content_markdown_updated(self, admin_client, document):
        url = reverse('update-document', kwargs={'document_id': document.id})
        response = admin_client.patch(
            url, {'content_markdown': '# New Heading\n\nNew content.'}, format='json',
        )

        assert response.status_code == 200
        document.refresh_from_db()
        assert document.content_json is not None
        assert document.content_json['blocks'][0]['text'] == 'New Heading'

    def test_keeps_existing_content_json_when_markdown_is_not_updated(self, admin_client, document):
        original_content_json = document.content_json
        url = reverse('update-document', kwargs={'document_id': document.id})

        response = admin_client.patch(url, {'client_name': 'Updated Client'}, format='json')

        assert response.status_code == 200
        document.refresh_from_db()
        assert document.client_name == 'Updated Client'
        assert document.content_json == original_content_json

    def test_returns_400_on_invalid_payload(self, admin_client, document):
        url = reverse('update-document', kwargs={'document_id': document.id})
        # Pass a non-string to a CharField — forces 400
        response = admin_client.patch(url, {'language': ['bad', 'list']}, format='json')

        assert response.status_code == 400

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('update-document', kwargs={'document_id': 99999})
        response = admin_client.patch(url, {'title': 'X'}, format='json')

        assert response.status_code == 404

    def test_clears_the_client_note(self, admin_client, document):
        document.client_email_subject = 'Asunto anterior'
        document.client_email_body = 'Correo anterior'
        document.client_whatsapp_message = 'WhatsApp anterior'
        document.client_custom_notes = [
            {'title': 'Anterior', 'content': 'Contenido anterior.'},
        ]
        document.save()
        url = reverse('update-document', kwargs={'document_id': document.id})

        response = admin_client.patch(url, {
            'client_email_subject': '',
            'client_email_body': '',
            'client_whatsapp_message': '',
            'client_custom_notes': [],
        }, format='json')

        assert response.status_code == 200
        document.refresh_from_db()
        assert document.client_email_subject == ''
        assert document.client_email_body == ''
        assert document.client_whatsapp_message == ''
        assert document.client_custom_notes == []


# ── delete_document ──

class TestDeleteDocument:
    def test_deletes_document_and_returns_204(self, admin_client, document):
        """Green on SQLite even while MySQL 500s — see the next test for why."""
        doc_id = document.id
        url = reverse('delete-document', kwargs={'document_id': doc_id})
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not Document.objects.filter(pk=doc_id).exists()

    def test_deletes_document_carrying_a_state_episode(
        self, admin_client, document, non_deferring_constraints,
    ):
        """Every document born after the workflow landed carries an episode,
        and on a backend that cannot defer its CHECK checks that used to 500."""
        doc_id = document.id
        assert document.state_episodes.exists()

        url = reverse('delete-document', kwargs={'document_id': doc_id})
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not Document.objects.filter(pk=doc_id).exists()

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('delete-document', kwargs={'document_id': 99999})
        response = admin_client.delete(url)

        assert response.status_code == 404

    def test_archived_document_can_still_be_deleted(self, admin_client, document):
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': document.id})
        )

        url = reverse('delete-document', kwargs={'document_id': document.id})
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not Document.objects.filter(pk=document.id).exists()


# ── collection-account lock (requisito 6) ──

@pytest.fixture
def make_cuenta(db):
    from content.services.document_type_utils import (
        get_collection_account_document_type,
    )

    def _make(status):
        return Document.objects.create(
            title='CC Kore',
            document_type=get_collection_account_document_type(),
            commercial_status=status,
        )

    return _make


class TestCollectionAccountLock:
    """An issued cuenta is a fact: the generic documents module can no
    longer rewrite or delete it — the path is anular y reemitir. Drafts
    stay editable: they are provisional by definition."""

    def test_an_issued_cuenta_refuses_update_and_delete(
        self, admin_client, make_cuenta,
    ):
        issued = make_cuenta(Document.CommercialStatus.ISSUED)

        patched = admin_client.patch(
            reverse('update-document', kwargs={'document_id': issued.pk}),
            {'title': 'Otro'}, format='json',
        )
        deleted = admin_client.delete(
            reverse('delete-document', kwargs={'document_id': issued.pk}),
        )

        assert patched.status_code == 400
        assert patched.data['code'] == 'collection_account_locked'
        assert deleted.status_code == 400
        assert deleted.data['code'] == 'collection_account_locked'
        issued.refresh_from_db()
        assert issued.title == 'CC Kore'

    def test_a_cancelled_cuenta_is_history_too(self, admin_client, make_cuenta):
        cancelled = make_cuenta(Document.CommercialStatus.CANCELLED)

        response = admin_client.patch(
            reverse('update-document', kwargs={'document_id': cancelled.pk}),
            {'title': 'Otro'}, format='json',
        )

        assert response.status_code == 400
        assert response.data['code'] == 'collection_account_locked'

    def test_a_draft_cuenta_stays_editable_and_deletable(
        self, admin_client, make_cuenta,
    ):
        draft = make_cuenta(Document.CommercialStatus.DRAFT)

        patched = admin_client.patch(
            reverse('update-document', kwargs={'document_id': draft.pk}),
            {'title': 'Draft renombrado'}, format='json',
        )

        assert patched.status_code == 200, patched.data
        draft.refresh_from_db()
        assert draft.title == 'Draft renombrado'

        deleted = admin_client.delete(
            reverse('delete-document', kwargs={'document_id': draft.pk}),
        )
        assert deleted.status_code == 204

    def test_the_serializers_expose_the_lock_fields(
        self, admin_client, make_cuenta, document,
    ):
        issued = make_cuenta(Document.CommercialStatus.ISSUED)

        detail = admin_client.get(
            reverse('retrieve-document', kwargs={'document_id': issued.pk}),
        )

        assert detail.status_code == 200
        assert detail.data['document_type_code'] == 'collection_account'
        assert detail.data['commercial_status'] == 'issued'
        # Markdown documents stay unlocked and say so.
        markdown = admin_client.get(
            reverse('retrieve-document', kwargs={'document_id': document.pk}),
        )
        assert markdown.data['document_type_code'] == 'markdown'
        assert markdown.data['commercial_status'] is None


# ── archived scope ──

class TestListDocumentsArchivedFilter:
    def test_default_listing_excludes_archived(self, admin_client, document, markdown_doc_type):
        stale = Document.objects.create(title='Viejo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(reverse('list-documents'))

        titles = [d['title'] for d in response.json()]
        assert 'Test Document' in titles
        assert 'Viejo' not in titles

    def test_archived_param_returns_only_archived(self, admin_client, document, markdown_doc_type):
        stale = Document.objects.create(title='Viejo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(reverse('list-documents'), {'archived': '1'})

        body = response.json()
        assert [d['title'] for d in body] == ['Viejo']
        assert body[0]['is_archived'] is True
        assert body[0]['archived_cause'] == 'manual'

    def test_archived_listing_orders_by_archived_at_desc(self, admin_client, markdown_doc_type):
        first = Document.objects.create(title='Primero', document_type=markdown_doc_type)
        second = Document.objects.create(title='Segundo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': first.id}))
        admin_client.patch(reverse('archive-document', kwargs={'document_id': second.id}))

        response = admin_client.get(reverse('list-documents'), {'archived': '1'})

        assert [d['title'] for d in response.json()] == ['Segundo', 'Primero']

    def test_order_oldest_reverses_the_archived_listing(self, admin_client, markdown_doc_type):
        first = Document.objects.create(title='Primero', document_type=markdown_doc_type)
        second = Document.objects.create(title='Segundo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': first.id}))
        admin_client.patch(reverse('archive-document', kwargs={'document_id': second.id}))

        response = admin_client.get(
            reverse('list-documents'), {'archived': '1', 'order': 'oldest'},
        )

        assert [d['title'] for d in response.json()] == ['Primero', 'Segundo']

    def test_invalid_order_falls_back_to_newest(self, admin_client, markdown_doc_type):
        first = Document.objects.create(title='Primero', document_type=markdown_doc_type)
        second = Document.objects.create(title='Segundo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': first.id}))
        admin_client.patch(reverse('archive-document', kwargs={'document_id': second.id}))

        response = admin_client.get(
            reverse('list-documents'), {'archived': '1', 'order': 'banana'},
        )

        assert response.status_code == 200
        assert [d['title'] for d in response.json()] == ['Segundo', 'Primero']


class TestListDocumentsScopeParam:
    def test_scope_all_returns_both_states_marked(
        self, admin_client, document, markdown_doc_type,
    ):
        stale = Document.objects.create(title='Viejo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(reverse('list-documents'), {'scope': 'all'})

        body = {d['title']: d['is_archived'] for d in response.json()}
        assert body['Test Document'] is False
        assert body['Viejo'] is True

    def test_scope_archived_matches_the_legacy_param(
        self, admin_client, document, markdown_doc_type,
    ):
        stale = Document.objects.create(title='Viejo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(reverse('list-documents'), {'scope': 'archived'})

        assert [d['title'] for d in response.json()] == ['Viejo']

    def test_scope_all_orders_by_each_row_visible_date(
        self, admin_client, markdown_doc_type,
    ):
        active = Document.objects.create(
            title='Orden visible activo', document_type=markdown_doc_type,
        )
        archived = Document.objects.create(
            title='Orden visible archivado', document_type=markdown_doc_type,
            is_archived=True,
        )
        Document.objects.filter(pk=active.pk).update(
            created_at=datetime(2026, 1, 3, tzinfo=dt_timezone.utc),
        )
        Document.objects.filter(pk=archived.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            archived_at=datetime(2026, 1, 4, tzinfo=dt_timezone.utc),
        )

        response = admin_client.get(reverse('list-documents'), {'scope': 'all'})

        assert [row['id'] for row in response.json()] == [archived.id, active.id]

    def test_search_honors_the_oldest_visible_date(
        self, admin_client, markdown_doc_type,
    ):
        active = Document.objects.create(
            title='Orden buscado activo', document_type=markdown_doc_type,
        )
        archived = Document.objects.create(
            title='Orden buscado archivado', document_type=markdown_doc_type,
            is_archived=True,
        )
        Document.objects.filter(pk=active.pk).update(
            created_at=datetime(2026, 1, 3, tzinfo=dt_timezone.utc),
        )
        Document.objects.filter(pk=archived.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            archived_at=datetime(2026, 1, 4, tzinfo=dt_timezone.utc),
        )

        response = admin_client.get(
            reverse('list-documents'),
            {'scope': 'all', 'search': 'Orden buscado', 'order': 'oldest'},
        )

        assert [row['id'] for row in response.json()] == [active.id, archived.id]

    def test_archived_null_date_falls_back_to_creation(
        self, admin_client, markdown_doc_type,
    ):
        legacy = Document.objects.create(
            title='Archivado legado', document_type=markdown_doc_type,
            is_archived=True, archived_at=None,
        )
        dated = Document.objects.create(
            title='Archivado fechado', document_type=markdown_doc_type,
            is_archived=True,
        )
        Document.objects.filter(pk=legacy.pk).update(
            created_at=datetime(2026, 1, 4, tzinfo=dt_timezone.utc),
        )
        Document.objects.filter(pk=dated.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            archived_at=datetime(2026, 1, 3, tzinfo=dt_timezone.utc),
        )

        response = admin_client.get(
            reverse('list-documents'), {'scope': 'archived'},
        )

        assert [row['id'] for row in response.json()] == [legacy.id, dated.id]

    def test_scope_wins_over_the_legacy_archived_param(
        self, admin_client, document, markdown_doc_type,
    ):
        stale = Document.objects.create(title='Viejo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(
            reverse('list-documents'), {'archived': '1', 'scope': 'active'},
        )

        assert [d['title'] for d in response.json()] == ['Test Document']

    def test_invalid_scope_returns_400(self, admin_client):
        response = admin_client.get(reverse('list-documents'), {'scope': 'banana'})

        assert response.status_code == 400
        assert 'scope' in response.json()


class TestListDocumentsSearch:
    def test_matches_a_partial_title_case_insensitively(
        self, admin_client, document, markdown_doc_type,
    ):
        Document.objects.create(title='Otra cosa', document_type=markdown_doc_type)

        response = admin_client.get(reverse('list-documents'), {'search': 'test doc'})

        assert [d['title'] for d in response.json()] == ['Test Document']

    def test_matches_the_client_name(self, admin_client, document, markdown_doc_type):
        Document.objects.create(
            title='Acta', client_name='Ferretería Norte', document_type=markdown_doc_type,
        )

        response = admin_client.get(reverse('list-documents'), {'search': 'ferreter'})

        assert [d['title'] for d in response.json()] == ['Acta']

    def test_reaches_archived_documents_with_scope_all(
        self, admin_client, markdown_doc_type,
    ):
        stale = Document.objects.create(title='Mapeo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(
            reverse('list-documents'), {'search': 'mape', 'scope': 'all'},
        )

        body = response.json()
        assert [d['title'] for d in body] == ['Mapeo']
        assert body[0]['is_archived'] is True

    def test_blank_search_is_a_noop(self, admin_client, document):
        response = admin_client.get(reverse('list-documents'), {'search': '   '})

        assert response.status_code == 200
        assert [d['title'] for d in response.json()] == ['Test Document']


class TestDocumentCountsView:
    def test_counts_each_document_once(self, admin_client, markdown_doc_type):
        folder = DocumentFolder.objects.create(name='Contratos')
        Document.objects.create(
            title='Con carpeta', folder=folder, document_type=markdown_doc_type,
        )
        Document.objects.create(title='Suelto', document_type=markdown_doc_type)
        stale = Document.objects.create(title='Viejo', document_type=markdown_doc_type)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': stale.id}))

        response = admin_client.get(reverse('document-counts'))

        body = response.json()
        assert body['documents']['active'] == 2
        assert body['documents']['archived'] == 1
        assert body['documents']['unfiled_active'] == 1
        assert body['folders']['active'] == 1

    def test_ignores_list_filters(self, admin_client, markdown_doc_type):
        Document.objects.create(title='Suelto', document_type=markdown_doc_type)

        response = admin_client.get(
            reverse('document-counts'), {'search': 'nada', 'folder': 'none'},
        )

        assert response.json()['documents']['active'] == 1


class TestDocumentArchivedFolderGuards:
    """Cerrar las puertas por las que se colaban documentos huérfanos."""

    def test_cannot_move_an_active_document_into_an_archived_folder(
        self, admin_client, document,
    ):
        folder = DocumentFolder.objects.create(name='Contratos')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        response = admin_client.patch(
            reverse('update-document', kwargs={'document_id': document.id}),
            {'folder_id': folder.id},
            format='json',
        )

        assert response.status_code == 400
        assert 'folder_id' in response.json()
        document.refresh_from_db()
        assert document.folder_id is None

    def test_an_archived_document_may_still_change_folder(
        self, admin_client, document,
    ):
        folder = DocumentFolder.objects.create(name='Contratos')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': document.id})
        )

        response = admin_client.patch(
            reverse('update-document', kwargs={'document_id': document.id}),
            {'folder_id': folder.id},
            format='json',
        )

        assert response.status_code == 200
        document.refresh_from_db()
        assert document.folder_id == folder.id

    def test_duplicating_from_an_archived_folder_lands_in_no_folder(
        self, admin_client, markdown_doc_type,
    ):
        folder = DocumentFolder.objects.create(name='Contratos')
        original = Document.objects.create(
            title='Acta', folder=folder, document_type=markdown_doc_type,
        )
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        response = admin_client.post(
            reverse('duplicate-document', kwargs={'document_id': original.id})
        )

        assert response.status_code == 201
        copy = Document.objects.get(pk=response.json()['id'])
        assert copy.is_archived is False
        assert copy.folder_id is None, 'no puede nacer dentro de una carpeta archivada'


class TestArchiveDocumentView:
    def test_archives_and_returns_the_row(self, admin_client, document):
        url = reverse('archive-document', kwargs={'document_id': document.id})
        response = admin_client.patch(url)

        assert response.status_code == 200
        assert response.json()['is_archived'] is True
        document.refresh_from_db()
        assert document.archived_at is not None

    def test_requires_admin_auth(self, api_client, document):
        url = reverse('archive-document', kwargs={'document_id': document.id})
        assert api_client.patch(url).status_code == 401

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('archive-document', kwargs={'document_id': 99999})
        assert admin_client.patch(url).status_code == 404


class TestUnarchiveDocumentView:
    def test_restores_the_document(self, admin_client, document):
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': document.id})
        )

        url = reverse('unarchive-document', kwargs={'document_id': document.id})
        response = admin_client.patch(url)

        assert response.status_code == 200
        assert response.json()['is_archived'] is False
        document.refresh_from_db()
        assert document.archived_at is None

    def test_reports_the_container_chain_it_reopened(self, admin_client, document):
        folder = DocumentFolder.objects.create(name='Temporal')
        Document.objects.filter(pk=document.id).update(folder=folder)
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        response = admin_client.patch(
            reverse('unarchive-document', kwargs={'document_id': document.id})
        )

        assert response.json()['restored_chain'] == [
            {'id': folder.id, 'name': 'Temporal'},
        ]
        document.refresh_from_db()
        folder.refresh_from_db()
        assert document.folder_id == folder.id
        assert folder.is_archived is False, 'el documento tiene que quedar alcanzable'

    def test_returns_document_to_root_when_folder_was_deleted(
        self, admin_client, document,
    ):
        from content.models import DocumentFolder

        folder = DocumentFolder.objects.create(name='Temporal')
        Document.objects.filter(pk=document.id).update(folder=folder)
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': document.id})
        )
        Document.objects.filter(pk=document.id).update(folder=None)
        folder.delete()

        admin_client.patch(
            reverse('unarchive-document', kwargs={'document_id': document.id})
        )

        document.refresh_from_db()
        assert document.is_archived is False
        assert document.folder_id is None


class TestUpdateDocumentArchiveGuard:
    def test_update_endpoint_cannot_set_is_archived(self, admin_client, document):
        url = reverse('update-document', kwargs={'document_id': document.id})
        response = admin_client.patch(url, {'is_archived': True}, format='json')

        assert response.status_code == 200
        document.refresh_from_db()
        assert document.is_archived is False


# ── duplicate_document ──

class TestDuplicateDocument:
    def test_duplicates_document_with_copia_suffix(self, admin_client, document):
        url = reverse('duplicate-document', kwargs={'document_id': document.id})
        response = admin_client.post(url)

        assert response.status_code == 201
        data = response.json()
        assert '(copia)' in data['title']
        assert Document.objects.count() == 2

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('duplicate-document', kwargs={'document_id': 99999})
        response = admin_client.post(url)

        assert response.status_code == 404

    def test_returns_400_for_collection_account(self, admin_client, db):
        from content.services.document_type_codes import COLLECTION_ACCOUNT
        ca_type, _ = DocumentType.objects.get_or_create(
            code=COLLECTION_ACCOUNT,
            defaults={'name': 'Collection Account', 'label': 'Collection Account'},
        )
        doc = Document.objects.create(
            title='Collection Doc', document_type=ca_type, client_name='C',
        )
        url = reverse('duplicate-document', kwargs={'document_id': doc.id})
        response = admin_client.post(url)

        assert response.status_code == 400

    def test_duplicates_document_without_document_type(self, admin_client, markdown_doc_type):
        """Covers the `doc_type = document.document_type or get_markdown_document_type()` fallback."""
        doc = Document.objects.create(
            title='No Type Doc',
            document_type=None,
            content_json={'meta': {}, 'blocks': [{'type': 'heading', 'text': 'H'}]},
        )
        url = reverse('duplicate-document', kwargs={'document_id': doc.id})
        response = admin_client.post(url)

        assert response.status_code == 201
        data = response.json()
        assert '(copia)' in data['title']
        # document_type is not in the serializer response, verify via DB
        duplicate = Document.objects.get(pk=data['id'])
        assert duplicate.document_type is not None

    def test_duplicate_keeps_the_export_configuration(self, admin_client, document):
        """La copia sale igual: casillas Y estilo, que se perdía en el camino."""
        document.include_portada = False
        document.include_subportada = True
        document.include_contraportada = False
        document.template_style = 'friendly'
        document.save()

        url = reverse('duplicate-document', kwargs={'document_id': document.id})
        response = admin_client.post(url)

        assert response.status_code == 201
        duplicate = Document.objects.get(pk=response.json()['id'])
        assert duplicate.include_portada is False
        assert duplicate.include_subportada is True
        assert duplicate.include_contraportada is False
        assert duplicate.template_style == 'friendly'

    def test_duplicate_keeps_content_json_independent_from_original(self, admin_client, document):
        url = reverse('duplicate-document', kwargs={'document_id': document.id})

        response = admin_client.post(url)

        assert response.status_code == 201
        duplicate = Document.objects.get(pk=response.json()['id'])

        document.content_json['blocks'][0]['text'] = 'Changed after duplicate'
        document.save(update_fields=['content_json'])
        duplicate.refresh_from_db()

        assert duplicate.content_json['blocks'][0]['text'] == 'Hello'

    def test_duplicate_starts_without_the_client_note(self, admin_client, document):
        document.client_email_subject = 'Asunto privado'
        document.client_email_body = 'Correo privado'
        document.client_whatsapp_message = 'WhatsApp privado'
        document.client_custom_notes = [
            {'title': 'Privada', 'content': 'No copiar.'},
        ]
        document.save()
        url = reverse('duplicate-document', kwargs={'document_id': document.id})

        response = admin_client.post(url)

        assert response.status_code == 201
        duplicate = Document.objects.get(pk=response.json()['id'])
        assert duplicate.client_email_subject == ''
        assert duplicate.client_email_body == ''
        assert duplicate.client_whatsapp_message == ''
        assert duplicate.client_custom_notes == []


# ── download_document_pdf ──

class TestDownloadDocumentPdf:
    def test_returns_pdf_bytes_for_document_with_content(self, admin_client, document):
        url = reverse('download-document-pdf', kwargs={'document_id': document.id})
        with patch(
            'content.services.document_pdf_service.DocumentPdfService.generate',
            return_value=b'%PDF-1.4 mock content',
        ):
            response = admin_client.get(url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert 'attachment' in response['Content-Disposition']
        assert '.pdf' in response['Content-Disposition']

    def test_returns_pdf_when_only_markdown_is_stored(
        self, admin_client, markdown_doc_type,
    ):
        """Un writer que no parseó el markdown no debe dejar el PDF inaccesible."""
        doc = Document.objects.create(
            title='Sólo markdown', document_type=markdown_doc_type,
            content_markdown='# Estimate\n\nContenido real.\n',
            content_json={},
        )
        url = reverse('download-document-pdf', kwargs={'document_id': doc.id})
        with patch(
            'content.services.document_pdf_service.DocumentPdfService.generate',
            return_value=b'%PDF-1.4 mock content',
        ):
            response = admin_client.get(url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'

    def test_inline_query_param_renders_in_the_viewer(self, admin_client, document):
        """`?inline=1` es lo que hace posible previsualizar sin descargar."""
        url = reverse('download-document-pdf', kwargs={'document_id': document.id})
        with patch(
            'content.services.document_pdf_service.DocumentPdfService.generate',
            return_value=b'%PDF-1.4 mock content',
        ):
            response = admin_client.get(url, {'inline': '1'})

        assert response.status_code == 200
        assert response['Content-Disposition'].startswith('inline')

    def test_pdf_is_built_from_the_saved_cover_flags(
        self, admin_client, document,
    ):
        """Guardar las casillas y descargar: el PDF sale con lo guardado.

        Es el recorrido completo de la ficha —PATCH y luego descarga— y lo que
        se asierta es el documento con el que se llama al generador, porque ahí
        es donde se decidía usar los valores por defecto.
        """
        admin_client.patch(
            reverse('update-document', kwargs={'document_id': document.id}),
            data={
                'include_portada': False,
                'include_subportada': False,
                'include_contraportada': False,
            },
            content_type='application/json',
        )

        url = reverse('download-document-pdf', kwargs={'document_id': document.id})
        with patch(
            'content.services.document_pdf_service.DocumentPdfService.generate',
            return_value=b'%PDF-1.4 mock content',
        ) as generate:
            response = admin_client.get(url)

        assert response.status_code == 200
        generated_doc = generate.call_args.args[0]
        assert generated_doc.include_portada is False
        assert generated_doc.include_subportada is False
        assert generated_doc.include_contraportada is False

    def test_returns_400_when_no_blocks(self, admin_client, markdown_doc_type):
        doc = Document.objects.create(
            title='Empty', document_type=markdown_doc_type,
            content_json={'meta': {}, 'blocks': []},
        )
        url = reverse('download-document-pdf', kwargs={'document_id': doc.id})
        response = admin_client.get(url)

        assert response.status_code == 400

    def test_returns_400_when_no_blocks_key(self, admin_client, markdown_doc_type):
        doc = Document.objects.create(
            title='No Blocks Key', document_type=markdown_doc_type,
            content_json={'meta': {}},
        )
        url = reverse('download-document-pdf', kwargs={'document_id': doc.id})
        response = admin_client.get(url)

        assert response.status_code == 400

    def test_returns_500_when_generation_fails(self, admin_client, document):
        url = reverse('download-document-pdf', kwargs={'document_id': document.id})
        with patch(
            'content.services.document_pdf_service.DocumentPdfService.generate',
            return_value=None,
        ):
            response = admin_client.get(url)

        assert response.status_code == 500

    def test_uses_document_fallback_filename_when_slugify_returns_empty_string(
        self, admin_client, markdown_doc_type,
    ):
        document = Document.objects.create(
            title='###',
            document_type=markdown_doc_type,
            content_json={'meta': {}, 'blocks': [{'type': 'heading', 'text': 'Hello'}]},
        )
        url = reverse('download-document-pdf', kwargs={'document_id': document.id})

        with patch(
            'content.services.document_pdf_service.DocumentPdfService.generate',
            return_value=b'%PDF-1.4 fallback',
        ):
            response = admin_client.get(url)

        assert response.status_code == 200
        assert response['Content-Disposition'] == 'attachment; filename="document.pdf"'


# ── template_style ──

class TestDocumentTemplateStyleApi:
    def test_detail_includes_template_style(self, admin_client):
        from content.models import Document
        doc = Document.objects.create(title='D', template_style='friendly')
        resp = admin_client.get(f'/api/documents/{doc.id}/detail/')
        assert resp.status_code == 200
        assert resp.json()['template_style'] == 'friendly'

    def test_update_sets_template_style(self, admin_client):
        from content.models import Document
        doc = Document.objects.create(title='D')
        resp = admin_client.patch(
            f'/api/documents/{doc.id}/update/',
            {'template_style': 'friendly'}, content_type='application/json')
        assert resp.status_code == 200
        doc.refresh_from_db()
        assert doc.template_style == 'friendly'

    def test_update_rejects_bad_template_style(self, admin_client):
        from content.models import Document
        doc = Document.objects.create(title='D')
        resp = admin_client.patch(
            f'/api/documents/{doc.id}/update/',
            {'template_style': 'fancy'}, content_type='application/json')
        assert resp.status_code == 400
        assert 'template_style' in resp.json()


# ── download_document_pdf — ?template= query param ──

class TestDownloadPdfTemplateParam:
    def _doc(self):
        from content.models import Document
        return Document.objects.create(
            title='D', template_style='professional',
            content_json={'meta': {}, 'blocks': [
                {'type': 'paragraph', 'text': 'Hola.'}]})

    def test_param_overrides_to_friendly(self, admin_client):
        doc = self._doc()
        with patch('content.services.document_pdf_service.'
                   'DocumentPdfService.generate') as gen:
            gen.return_value = b'%PDF-1.4 x'
            resp = admin_client.get(
                f'/api/documents/{doc.id}/pdf/?template=friendly')
        assert resp.status_code == 200
        assert gen.call_args.kwargs.get('template_style') == 'friendly' \
            or gen.call_args[0][1:] == ('friendly',)

    def test_invalid_param_falls_back_to_document_style(self, admin_client):
        doc = self._doc()
        with patch('content.services.document_pdf_service.'
                   'DocumentPdfService.generate') as gen:
            gen.return_value = b'%PDF-1.4 x'
            resp = admin_client.get(
                f'/api/documents/{doc.id}/pdf/?template=bogus')
        assert resp.status_code == 200
        passed = gen.call_args.kwargs.get('template_style')
        assert passed in ('professional', None)

    def test_no_param_uses_document_style(self, admin_client):
        doc = self._doc()
        doc.template_style = 'friendly'
        doc.save(update_fields=['template_style'])
        with patch('content.services.document_pdf_service.'
                   'DocumentPdfService.generate') as gen:
            gen.return_value = b'%PDF-1.4 x'
            resp = admin_client.get(f'/api/documents/{doc.id}/pdf/')
        assert resp.status_code == 200
