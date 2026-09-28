"""Tests for content/views/document_folder.py — folder CRUD + document filter."""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.urls import reverse

from content.models import Document, DocumentFolder

pytestmark = pytest.mark.django_db


@pytest.fixture
def folder(db):
    return DocumentFolder.objects.create(name='Cuentas de cobro')


def make_client(email, *, first='Ana', last='Pérez'):
    user = get_user_model().objects.create_user(
        username=email, email=email, password='pass12345',
        first_name=first, last_name=last,
    )
    return UserProfile.objects.create(user=user, cedula='1049654583')


class TestListDocumentFolders:
    def test_returns_200_with_list(self, admin_client, folder):
        url = reverse('list-document-folders')
        response = admin_client.get(url)

        assert response.status_code == 200
        names = [f['name'] for f in response.json()]
        assert 'Cuentas de cobro' in names

    def test_requires_admin_auth(self, api_client):
        url = reverse('list-document-folders')
        response = api_client.get(url)

        assert response.status_code == 401

    def test_listing_associated_folders_does_not_query_per_row(
        self, admin_client, django_assert_max_num_queries,
    ):
        """El panel lateral lista todas las carpetas raíz de una sola pasada.

        Sin `select_related` cada fila cuesta tres consultas extra (el usuario,
        su perfil y el proyecto), así que el costo crece con el número de
        carpetas: diez carpetas ya son treinta consultas de más.
        """
        for index in range(5):
            profile = make_client(f'cliente{index}@example.com')
            project = Project.objects.create(
                name=f'Proyecto {index}', client=profile.user,
            )
            DocumentFolder.objects.create(
                name=f'Carpeta {index}',
                client_user=profile.user,
                project=project,
            )

        url = reverse('list-document-folders')
        with django_assert_max_num_queries(10):
            response = admin_client.get(url)

        assert response.status_code == 200
        assert all(entry['client_display_name'] for entry in response.json())

    def test_document_count_reflects_assigned_documents(self, admin_client, folder):
        Document.objects.create(title='A', folder=folder)
        Document.objects.create(title='B', folder=folder)
        Document.objects.create(title='Orphan')

        url = reverse('list-document-folders')
        response = admin_client.get(url)

        assert response.status_code == 200
        entry = next(f for f in response.json() if f['id'] == folder.id)
        assert entry['document_count'] == 2


class TestCreateDocumentFolder:
    def test_creates_folder_and_auto_slug(self, admin_client):
        url = reverse('create-document-folder')
        response = admin_client.post(url, {'name': 'Contratos'}, format='json')

        assert response.status_code == 201
        data = response.json()
        assert data['name'] == 'Contratos'
        assert data['slug'] == 'contratos'

    def test_returns_400_on_missing_name(self, admin_client):
        url = reverse('create-document-folder')
        response = admin_client.post(url, {}, format='json')

        assert response.status_code == 400

    def test_auto_slug_handles_duplicate_names(self, admin_client):
        DocumentFolder.objects.create(name='Contratos')
        url = reverse('create-document-folder')
        response = admin_client.post(url, {'name': 'Contratos'}, format='json')

        assert response.status_code == 201
        assert response.json()['slug'] == 'contratos-2'


class TestUpdateDocumentFolder:
    def test_renames_folder(self, admin_client, folder):
        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'name': 'Facturas'}, format='json')

        assert response.status_code == 200
        folder.refresh_from_db()
        assert folder.name == 'Facturas'

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('update-document-folder', kwargs={'folder_id': 99999})
        response = admin_client.patch(url, {'name': 'x'}, format='json')

        assert response.status_code == 404


class TestUpdateDocumentFolderAssociation:
    """El PATCH plano asocia una carpeta vacía; con contenido remite a la cascada.

    Una carpeta con contenido que cambia de cliente arrastra la pregunta de qué
    pasa con lo que guarda, y esa pregunta sólo la responde el endpoint de
    cambio de cliente (preview + modo). El PATCH plano se planta con 409 en vez
    de reasignar la carpeta a espaldas de su contenido.
    """

    def test_associates_an_empty_folder(self, admin_client, folder):
        profile = make_client('ana@example.com')
        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'client': profile.pk}, format='json')

        assert response.status_code == 200
        assert response.json()['client'] == profile.pk
        folder.refresh_from_db()
        assert folder.client_user == profile.user

    def test_client_change_with_documents_returns_409(self, admin_client, folder):
        ana = make_client('ana@example.com')
        nestor = make_client('nestor@example.com', first='Néstor')
        folder.client_user = ana.user
        folder.save(update_fields=['client_user'])
        Document.objects.create(title='Contrato', folder=folder)

        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'client': nestor.pk}, format='json')

        assert response.status_code == 409
        assert response.json()['code'] == 'folder_has_content'
        folder.refresh_from_db()
        assert folder.client_user == ana.user

    def test_first_association_with_documents_also_returns_409(
        self, admin_client, folder,
    ):
        """Poner cliente por primera vez es justo cuando la propagación importa."""
        profile = make_client('ana@example.com')
        Document.objects.create(title='Contrato', folder=folder)

        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'client': profile.pk}, format='json')

        assert response.status_code == 409
        assert response.json()['code'] == 'folder_has_content'

    def test_client_change_with_subfolders_returns_409(self, admin_client, folder):
        profile = make_client('ana@example.com')
        DocumentFolder.objects.create(name='Sub', parent=folder)

        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'client': profile.pk}, format='json')

        assert response.status_code == 409

    def test_clearing_the_client_of_a_folder_with_content_is_a_plain_patch(
        self, admin_client, folder,
    ):
        """Desasignar no reasigna nada: no hay a quién propagarle el contenido.

        La cascada existe para decidir a quién pasa lo que la carpeta guarda, y
        "a nadie" no es un destino — el endpoint de cambio de cliente exige uno.
        Quitarle el dueño a la carpeta deja su contenido como está.
        """
        profile = make_client('ana@example.com')
        folder.client_user = profile.user
        folder.save(update_fields=['client_user'])
        document = Document.objects.create(
            title='Contrato', folder=folder, client_user=profile.user,
        )

        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'client': None}, format='json')

        assert response.status_code == 200
        folder.refresh_from_db()
        document.refresh_from_db()
        assert folder.client_user is None
        assert document.client_user == profile.user

    def test_renaming_a_folder_with_content_still_works(self, admin_client, folder):
        """El guard mira el cliente, no el resto del formulario."""
        profile = make_client('ana@example.com')
        folder.client_user = profile.user
        folder.save(update_fields=['client_user'])
        Document.objects.create(title='Contrato', folder=folder)

        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(
            url, {'name': 'Facturas', 'client': profile.pk}, format='json',
        )

        assert response.status_code == 200
        folder.refresh_from_db()
        assert folder.name == 'Facturas'


class TestDeleteDocumentFolder:
    def test_deletes_empty_folder(self, admin_client, folder):
        url = reverse('delete-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not DocumentFolder.objects.filter(pk=folder.id).exists()

    def test_blocks_deletion_when_folder_has_documents(self, admin_client, folder):
        doc = Document.objects.create(title='Inside', folder=folder)

        url = reverse('delete-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.delete(url)

        assert response.status_code == 409
        body = response.json()
        assert body['document_count'] == 1
        assert 'detail' in body

        assert DocumentFolder.objects.filter(pk=folder.id).exists()
        doc.refresh_from_db()
        assert doc.folder_id == folder.id

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('delete-document-folder', kwargs={'folder_id': 99999})
        response = admin_client.delete(url)

        assert response.status_code == 404

    def test_archived_folder_with_archived_documents_still_returns_409(
        self, admin_client, folder,
    ):
        """Contenido es contenido: archivarlo no lo hace borrable."""
        Document.objects.create(title='Inside', folder=folder)
        archive_url = reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        admin_client.patch(archive_url)

        url = reverse('delete-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.delete(url)

        assert response.status_code == 409
        assert response.json()['document_count'] == 1

    def test_archived_empty_folder_can_be_deleted(self, admin_client, folder):
        archive_url = reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        admin_client.patch(archive_url)

        url = reverse('delete-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not DocumentFolder.objects.filter(pk=folder.id).exists()


class TestListDocumentFoldersArchived:
    def test_default_listing_excludes_archived_folders(self, admin_client, folder):
        archived = DocumentFolder.objects.create(name='Vieja')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': archived.id})
        )

        response = admin_client.get(reverse('list-document-folders'))

        names = [f['name'] for f in response.json()]
        assert 'Cuentas de cobro' in names
        assert 'Vieja' not in names

    def test_archived_param_returns_only_archived_folders(self, admin_client, folder):
        archived = DocumentFolder.objects.create(name='Vieja')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': archived.id})
        )

        response = admin_client.get(reverse('list-document-folders'), {'archived': '1'})

        body = response.json()
        assert [f['name'] for f in body] == ['Vieja']
        assert body[0]['is_archived'] is True
        assert body[0]['archived_at'] is not None
        assert body[0]['archived_cause'] == 'manual'

    def test_document_count_excludes_archived_documents(self, admin_client, folder):
        Document.objects.create(title='Activo', folder=folder)
        stale = Document.objects.create(title='Viejo', folder=folder)
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': stale.id})
        )

        response = admin_client.get(reverse('list-document-folders'))

        entry = next(f for f in response.json() if f['id'] == folder.id)
        assert entry['document_count'] == 1

    def test_children_count_excludes_archived_subfolders(self, admin_client, folder):
        DocumentFolder.objects.create(name='Activa', parent=folder)
        stale = DocumentFolder.objects.create(name='Vieja', parent=folder)
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': stale.id})
        )

        response = admin_client.get(reverse('list-document-folders'))

        entry = next(f for f in response.json() if f['id'] == folder.id)
        assert entry['children_count'] == 1


class TestArchiveDocumentFolderView:
    def test_archives_folder_with_content_and_reports_counts(self, admin_client, folder):
        Document.objects.create(title='Inside', folder=folder)
        DocumentFolder.objects.create(name='Sub', parent=folder)

        url = reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url)

        assert response.status_code == 200
        body = response.json()
        assert body['archived_documents'] == 1
        assert body['archived_folders'] == 1
        assert body['folder']['is_archived'] is True

    def test_requires_admin_auth(self, api_client, folder):
        url = reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        assert api_client.patch(url).status_code == 401

    def test_returns_404_for_nonexistent(self, admin_client):
        url = reverse('archive-document-folder', kwargs={'folder_id': 99999})
        assert admin_client.patch(url).status_code == 404


class TestUnarchiveDocumentFolderView:
    def test_restores_folder_and_cascaded_content(self, admin_client, folder):
        doc = Document.objects.create(title='Inside', folder=folder)
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        url = reverse('unarchive-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url)

        assert response.status_code == 200
        assert response.json()['restored_documents'] == 1
        doc.refresh_from_db()
        assert doc.is_archived is False

    def test_keeps_individually_archived_document_archived(self, admin_client, folder):
        loose = Document.objects.create(title='Viejo', folder=folder)
        admin_client.patch(reverse('archive-document', kwargs={'document_id': loose.id}))
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        admin_client.patch(
            reverse('unarchive-document-folder', kwargs={'folder_id': folder.id})
        )

        loose.refresh_from_db()
        assert loose.is_archived is True

    def test_reopens_the_parent_chain_and_reports_it(self, admin_client, folder):
        child = DocumentFolder.objects.create(name='Sub', parent=folder)
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        url = reverse('unarchive-document-folder', kwargs={'folder_id': child.id})
        response = admin_client.patch(url)

        assert response.status_code == 200
        assert response.json()['restored_chain'] == [
            {'id': folder.id, 'name': folder.name},
        ]
        child.refresh_from_db()
        folder.refresh_from_db()
        assert child.is_archived is False
        assert folder.is_archived is False


class TestFolderArchivedContentCounters:
    """Una carpeta activa tiene que poder avisar que guarda archivados."""

    def test_active_folder_reports_its_archived_documents(self, admin_client, folder):
        Document.objects.create(title='Activo', folder=folder)
        archived = Document.objects.create(title='Archivado', folder=folder)
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': archived.id})
        )

        response = admin_client.get(reverse('list-document-folders'))

        payload = next(f for f in response.json() if f['id'] == folder.id)
        assert payload['document_count'] == 1, 'el contador visible sigue siendo el activo'
        assert payload['archived_document_count'] == 1

    def test_active_folder_reports_its_archived_subfolders(self, admin_client, folder):
        child = DocumentFolder.objects.create(name='Sub', parent=folder)
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': child.id})
        )

        response = admin_client.get(reverse('list-document-folders'))

        payload = next(f for f in response.json() if f['id'] == folder.id)
        assert payload['children_count'] == 0
        assert payload['archived_children_count'] == 1


class TestListDocumentFoldersScope:
    def test_scope_all_returns_both_states(self, admin_client, folder):
        archived = DocumentFolder.objects.create(name='Vieja')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': archived.id})
        )

        response = admin_client.get(reverse('list-document-folders'), {'scope': 'all'})

        ids = [f['id'] for f in response.json()]
        assert folder.id in ids
        assert archived.id in ids

    def test_invalid_scope_returns_400(self, admin_client):
        response = admin_client.get(
            reverse('list-document-folders'), {'scope': 'banana'},
        )

        assert response.status_code == 400
        assert 'scope' in response.json()

    def test_search_filters_by_name(self, admin_client, folder):
        DocumentFolder.objects.create(name='Propuestas')

        response = admin_client.get(
            reverse('list-document-folders'), {'search': 'cuenta'},
        )

        names = [f['name'] for f in response.json()]
        assert names == [folder.name]

    def test_search_reaches_archived_folders(self, admin_client):
        archived = DocumentFolder.objects.create(name='Temporal')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': archived.id})
        )

        response = admin_client.get(
            reverse('list-document-folders'), {'search': 'tempo', 'scope': 'all'},
        )

        payload = response.json()
        assert [f['id'] for f in payload] == [archived.id]
        assert payload[0]['is_archived'] is True


class TestFolderParentArchiveGuard:
    def test_cannot_create_a_folder_inside_an_archived_one(self, admin_client, folder):
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        response = admin_client.post(
            reverse('create-document-folder'),
            {'name': 'Nueva', 'parent': folder.id},
            format='json',
        )

        assert response.status_code == 400
        assert 'parent' in response.json()

    def test_cannot_move_an_active_folder_under_an_archived_one(
        self, admin_client, folder,
    ):
        other = DocumentFolder.objects.create(name='Otra')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': folder.id})
        )

        response = admin_client.patch(
            reverse('update-document-folder', kwargs={'folder_id': other.id}),
            {'parent': folder.id},
            format='json',
        )

        assert response.status_code == 400
        other.refresh_from_db()
        assert other.parent_id is None


class TestUpdateDocumentFolderArchiveGuard:
    def test_update_endpoint_cannot_set_is_archived(self, admin_client, folder):
        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'is_archived': True}, format='json')

        assert response.status_code == 400
        assert response.json()['is_archived'] == ['Campo desconocido o de solo lectura.']
        folder.refresh_from_db()
        assert folder.is_archived is False


class TestListDocumentsFolderFilter:
    def test_filter_by_folder_id_returns_only_matching(self, admin_client, folder):
        inside = Document.objects.create(title='Inside', folder=folder)
        Document.objects.create(title='Outside')

        url = reverse('list-documents')
        response = admin_client.get(url, {'folder': folder.id})

        assert response.status_code == 200
        titles = [d['title'] for d in response.json()]
        assert 'Inside' in titles
        assert 'Outside' not in titles
        assert response.json()[0]['id'] == inside.id

    def test_filter_by_folder_none_returns_uncategorized(self, admin_client, folder):
        Document.objects.create(title='Inside', folder=folder)
        Document.objects.create(title='Orphan')

        url = reverse('list-documents')
        response = admin_client.get(url, {'folder': 'none'})

        assert response.status_code == 200
        titles = [d['title'] for d in response.json()]
        assert titles == ['Orphan']

    def test_invalid_folder_param_returns_400(self, admin_client):
        url = reverse('list-documents')
        response = admin_client.get(url, {'folder': 'abc'})

        assert response.status_code == 400


class TestFolderHierarchy:
    def test_creates_folder_with_parent(self, admin_client, folder):
        url = reverse('create-document-folder')
        response = admin_client.post(
            url, {'name': 'Sub', 'parent': folder.id}, format='json',
        )

        assert response.status_code == 201
        assert response.json()['parent'] == folder.id

    def test_updates_parent(self, admin_client, folder):
        child = DocumentFolder.objects.create(name='Sub')

        url = reverse('update-document-folder', kwargs={'folder_id': child.id})
        response = admin_client.patch(url, {'parent': folder.id}, format='json')

        assert response.status_code == 200
        child.refresh_from_db()
        assert child.parent_id == folder.id

    def test_rejects_self_as_parent(self, admin_client, folder):
        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(url, {'parent': folder.id}, format='json')

        assert response.status_code == 400
        assert 'parent' in response.json()

    def test_rejects_descendant_as_parent(self, admin_client, folder):
        # folder -> child -> grandchild; mover folder bajo grandchild = ciclo.
        child = DocumentFolder.objects.create(name='Child', parent=folder)
        grandchild = DocumentFolder.objects.create(name='Grandchild', parent=child)

        url = reverse('update-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.patch(
            url, {'parent': grandchild.id}, format='json',
        )

        assert response.status_code == 400
        assert 'parent' in response.json()

    def test_blocks_deletion_when_folder_has_children(self, admin_client, folder):
        DocumentFolder.objects.create(name='Sub', parent=folder)

        url = reverse('delete-document-folder', kwargs={'folder_id': folder.id})
        response = admin_client.delete(url)

        assert response.status_code == 409
        assert response.json()['children_count'] == 1
        assert DocumentFolder.objects.filter(pk=folder.id).exists()

    def test_allows_deletion_of_empty_leaf_folder(self, admin_client, folder):
        child = DocumentFolder.objects.create(name='Sub', parent=folder)

        url = reverse('delete-document-folder', kwargs={'folder_id': child.id})
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not DocumentFolder.objects.filter(pk=child.id).exists()

    def test_list_includes_parent_and_children_count_without_multiplying(
        self, admin_client, folder,
    ):
        DocumentFolder.objects.create(name='Sub A', parent=folder)
        archived_child = DocumentFolder.objects.create(name='Sub B', parent=folder)
        Document.objects.create(title='Doc 1', folder=folder)
        archived_doc = Document.objects.create(title='Doc 2', folder=folder)
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': archived_child.id})
        )
        admin_client.patch(
            reverse('archive-document', kwargs={'document_id': archived_doc.id})
        )

        url = reverse('list-document-folders')
        response = admin_client.get(url)

        assert response.status_code == 200
        entry = next(f for f in response.json() if f['id'] == folder.id)
        assert entry['parent'] is None
        # Sin distinct=True el JOIN cruzado multiplicaría los cuatro contadores
        # entre sí; los cuatro agregados reusan los mismos dos JOINs.
        assert entry['document_count'] == 1
        assert entry['children_count'] == 1
        assert entry['archived_document_count'] == 1
        assert entry['archived_children_count'] == 1

    def test_scope_all_returns_the_whole_tree_unpaginated(self, admin_client, folder):
        """El panel suma el subárbol de cada carpeta con esta lista y nada más.

        Los contadores recursivos de la fila (los documentos que una carpeta
        guarda a cualquier profundidad) se derivan en el frontend a partir de
        esta respuesta, y eso sólo es correcto mientras siga trayendo el árbol
        COMPLETO de los dos estados en un solo pedido. Paginarla, o devolver un
        sobre `{results: [...]}`, dejaría a las carpetas de las páginas que no se
        pidieron fuera de la suma — sin error y sin test rojo. Este es ese test.
        """
        child = DocumentFolder.objects.create(name='Sub', parent=folder)
        DocumentFolder.objects.create(name='Nieta', parent=child)
        archived = DocumentFolder.objects.create(name='Vieja')
        admin_client.patch(
            reverse('archive-document-folder', kwargs={'folder_id': archived.id})
        )

        response = admin_client.get(reverse('list-document-folders'), {'scope': 'all'})

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert {f['id'] for f in body} == set(
            DocumentFolder.objects.values_list('id', flat=True)
        )
        # El vínculo padre-hijo viaja en la propia fila: sin él no hay árbol que
        # recorrer, por más completa que venga la lista.
        assert next(f for f in body if f['id'] == child.id)['parent'] == folder.id
