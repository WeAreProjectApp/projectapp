"""Tests for the Documents MCP connector HTTP endpoint."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Project, UserProfile
from content.models import (
    Document,
    DocumentFolder,
    DocumentNote,
    DocumentState,
    DocumentStateEpisode,
    DocumentType,
    McpConnector,
)


@pytest.fixture
def markdown_doc_type(db):
    """Reuse or create the 'markdown' DocumentType (seeded by migration 0052)."""
    obj, _ = DocumentType.objects.get_or_create(
        code='markdown',
        defaults={'name': 'Markdown', 'label': 'Markdown'},
    )
    return obj


@pytest.fixture
def collection_account_type(db):
    obj, _ = DocumentType.objects.get_or_create(
        code='collection_account',
        defaults={'name': 'Cuenta de cobro', 'label': 'Cuenta de cobro'},
    )
    return obj


@pytest.fixture
def documents_connector(db, superuser):
    """Active connector with an actor available for audited MCP mutations."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Gestor Documental'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return connector, token


def _url(token):
    return f'/api/mcp/documents/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(
        _url(token),
        _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def _call_confirmed(api_client, token, name, arguments):
    preview = _call(api_client, token, name, arguments)
    confirmation_id = preview.data['result']['structuredContent']['confirmation_id']
    return _call(
        api_client,
        token,
        'confirm_action',
        {'confirmation_id': confirmation_id},
    )


def _make_doc(doc_type, **kwargs):
    defaults = {
        'title': 'Doc',
        'document_type': doc_type,
        'language': 'es',
        'content_markdown': '# Hola\n\nMundo.',
        'content_json': {'meta': {}, 'blocks': []},
    }
    defaults.update(kwargs)
    return Document.objects.create(**defaults)


@pytest.mark.django_db
class TestDocumentsMcpToolList:
    def test_exposes_document_workflow_tools(self, api_client, documents_connector):
        _, token = documents_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = {t['name'] for t in response.data['result']['tools']}
        assert {
            'list_folders', 'create_folder', 'rename_folder', 'list_documents',
            'read_document', 'create_document', 'update_document',
            'append_document', 'delete_document', 'list_document_states',
            'set_document_state', 'close_document_state', 'add_document_note',
            'finish_document_note', 'delete_document_notes',
            'list_deleted_document_notes', 'restore_document_note',
            'get_document_thread', 'list_document_threads',
            'create_document_thread', 'update_document_thread',
            'dissolve_document_thread',
            'browse_documents', 'render_document_pdf', 'describe_capabilities',
            'confirm_action', 'begin_upload', 'complete_upload',
        } <= names

    def test_serverinfo_handshake_works_on_shared_endpoint(self, api_client, documents_connector):
        _, token = documents_connector
        response = api_client.post(
            _url(token), _rpc('initialize', {'protocolVersion': '2025-06-18'}),
            format='json',
        )
        assert response.status_code == 200
        assert response.data['result']['capabilities']['tools'] == {}


@pytest.mark.django_db
class TestDocumentsMcpFolders:
    def test_list_folders_returns_path_and_counts(self, api_client, documents_connector, markdown_doc_type):
        parent = DocumentFolder.objects.create(name='Clientes')
        child = DocumentFolder.objects.create(name='ACME', parent=parent)
        _make_doc(markdown_doc_type, folder=child)
        _, token = documents_connector

        response = _call(api_client, token, 'list_folders', {})
        folders = response.data['result']['content'][0]['text']
        assert 'Clientes / ACME' in folders

    def test_create_folder_under_parent(self, api_client, documents_connector):
        parent = DocumentFolder.objects.create(name='Raíz')
        _, token = documents_connector
        response = _call(api_client, token, 'create_folder', {'name': 'Sub', 'parent_id': parent.id})
        assert response.data['result']['isError'] is False
        created = DocumentFolder.objects.get(name='Sub')
        assert created.parent_id == parent.id

    def test_create_folder_requires_name(self, api_client, documents_connector):
        _, token = documents_connector
        response = _call(api_client, token, 'create_folder', {'name': '   '})
        assert response.data['result']['isError'] is True

    def test_create_folder_rejects_system_managed_parent(
        self, api_client, documents_connector,
    ):
        parent = DocumentFolder.objects.create(
            name='Proyectos', system_key='generated:test:projects',
        )
        _, token = documents_connector

        response = _call(
            api_client,
            token,
            'create_folder',
            {'name': 'Manual', 'parent_id': parent.pk},
        )

        assert response.data['result']['isError'] is True
        assert not DocumentFolder.objects.filter(name='Manual').exists()

    def test_rename_folder_changes_name_keeps_slug(self, api_client, documents_connector):
        folder = DocumentFolder.objects.create(name='Viejo')
        original_slug = folder.slug
        _, token = documents_connector
        response = _call(api_client, token, 'rename_folder', {'folder_id': folder.id, 'name': 'Nuevo'})
        assert response.data['result']['isError'] is False
        folder.refresh_from_db()
        assert folder.name == 'Nuevo'
        assert folder.slug == original_slug

    def test_rename_folder_requires_folder_id(self, api_client, documents_connector):
        _, token = documents_connector
        response = _call(api_client, token, 'rename_folder', {'name': 'Nuevo'})
        assert response.data['result']['isError'] is True

    def test_create_folder_inherits_managed_project(self, api_client, documents_connector):
        user = get_user_model().objects.create_user(
            username='mcp-project@example.com', email='mcp-project@example.com',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='MCP Project', client=user)
        _, token = documents_connector

        response = _call(api_client, token, 'create_folder', {
            'name': 'QA extra', 'parent_id': project.document_root_folder.id,
        })

        assert response.data['result']['isError'] is False
        folder = DocumentFolder.objects.get(name='QA extra')
        assert folder.project_id == project.id
        assert folder.client_user_id == user.id

    def test_rename_folder_rejects_managed_project_root(
        self, api_client, documents_connector,
    ):
        """Falla si MCP permite desincronizar el nombre de una raíz automática."""
        user = get_user_model().objects.create_user(
            username='mcp-root@example.com', email='mcp-root@example.com',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        project = Project.objects.create(name='MCP Root', client=user)
        _, token = documents_connector

        response = _call(api_client, token, 'rename_folder', {
            'folder_id': project.document_root_folder.id,
            'name': 'Bypass',
        })

        assert response.data['result']['isError'] is True
        assert response.data['result']['content'][0]['text'] == (
            'La raíz del proyecto se administra desde el proyecto, '
            'no desde el Gestor Documental.'
        )
        project.document_root_folder.refresh_from_db()
        assert project.document_root_folder.name == 'MCP Root'

    def test_create_folder_explains_duplicate_name_in_text(self, api_client, documents_connector):
        DocumentFolder.objects.create(name='Littigio')
        _, token = documents_connector

        response = _call(api_client, token, 'create_folder', {'name': 'Littigio'})

        assert response.data['result']['isError'] is True
        assert 'Ya existe una carpeta con ese nombre aquí' in response.data['result']['content'][0]['text']
        assert DocumentFolder.objects.filter(name='Littigio').count() == 1


@pytest.mark.django_db
class TestDocumentsMcpCrud:
    def test_read_document_exposes_markdown_editability_and_etag(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type, status='draft')
        _, token = documents_connector

        response = _call(api_client, token, 'read_document', {'document_id': doc.id})

        payload = response.data['result']['structuredContent']
        assert payload['markdown'] == '# Hola\n\nMundo.'
        assert payload['editable'] is True
        assert len(payload['etag']) == 64

    def test_update_document_accepts_the_content_markdown_alias(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type, status='draft')
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'content_markdown': '# Borrador corregido',
        })

        doc.refresh_from_db()
        assert response.data['result']['isError'] is False
        assert doc.content_markdown == '# Borrador corregido'

    def test_update_document_rejects_a_stale_etag(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type, status='draft')
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'markdown': '# No aplicar',
            'if_match': 'stale-etag',
        })

        error = response.data['result']['structuredContent']['error']
        assert error['code'] == 'STALE_VERSION'

    def test_create_document_parses_markdown_and_builds_json(self, api_client, documents_connector, markdown_doc_type):
        _, token = documents_connector
        response = _call(api_client, token, 'create_document', {
            'title': 'Guía',
            'markdown': '# Título\n\nUn párrafo.',
        })
        assert response.data['result']['isError'] is False
        doc = Document.objects.get(title='Guía')
        assert doc.document_type.code == 'markdown'
        assert doc.content_json['blocks']  # parser produced blocks
        assert doc.content_json['meta']['title'] == 'Guía'

    def test_create_document_honors_the_cover_flags(self, api_client, documents_connector, markdown_doc_type):
        """Un documento creado por MCP nacía siempre con las tres portadas."""
        _, token = documents_connector
        response = _call(api_client, token, 'create_document', {
            'title': 'Sin portadas',
            'markdown': '# Título\n\nUn párrafo.',
            'include_portada': False,
            'include_contraportada': False,
        })
        assert response.data['result']['isError'] is False
        doc = Document.objects.get(title='Sin portadas')
        assert doc.include_portada is False
        assert doc.include_contraportada is False
        # La que no se envió conserva el default.
        assert doc.include_subportada is True

    def test_create_document_stores_the_client_note(self, api_client, documents_connector, markdown_doc_type):
        _, token = documents_connector

        response = _call(api_client, token, 'create_document', {
            'title': 'Informe de soporte',
            'markdown': '# Informe\n\nCaso resuelto.',
            'client_email_subject': 'Caso resuelto',
            'client_email_body': 'Hola Ana,\n\nEl caso fue resuelto.',
            'client_whatsapp_message': 'Hola Ana, el caso ya fue resuelto.',
            'client_custom_notes': [
                {'title': 'Seguimiento', 'content': 'Confirmar recepción.'},
            ],
        })

        assert response.data['result']['isError'] is False
        document = Document.objects.get(title='Informe de soporte')
        assert document.client_email_subject == 'Caso resuelto'
        assert document.client_email_body == 'Hola Ana,\n\nEl caso fue resuelto.'
        assert document.client_whatsapp_message == 'Hola Ana, el caso ya fue resuelto.'
        assert document.client_custom_notes == [
            {'title': 'Seguimiento', 'content': 'Confirmar recepción.'},
        ]

    def test_update_document_changes_the_cover_flags(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'include_subportada': False,
        })
        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.include_subportada is False

    def test_cover_flag_rejects_a_string(self, api_client, documents_connector, markdown_doc_type):
        """"false" de texto sería True: mejor un error que un PDF equivocado."""
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'include_portada': 'false',
        })
        assert response.data['result']['isError'] is True
        doc.refresh_from_db()
        assert doc.include_portada is True

    def test_read_document_returns_markdown(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, title='Leer', content_markdown='# X\n\nY.')
        _, token = documents_connector
        response = _call(api_client, token, 'read_document', {'document_id': doc.id})
        text = response.data['result']['content'][0]['text']
        assert '# X' in text

    def test_read_document_returns_the_client_note(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(
            markdown_doc_type,
            client_email_subject='Reporte listo',
            client_email_body='El reporte está listo.',
            client_whatsapp_message='Ya está listo el reporte.',
            client_custom_notes=[
                {'title': 'Seguimiento', 'content': 'Confirmar recepción.'},
            ],
        )
        _, token = documents_connector

        response = _call(api_client, token, 'read_document', {'document_id': doc.id})

        payload = json.loads(response.data['result']['content'][0]['text'])
        assert payload['client_email_subject'] == 'Reporte listo'
        assert payload['client_email_body'] == 'El reporte está listo.'
        assert payload['client_whatsapp_message'] == 'Ya está listo el reporte.'
        assert payload['client_custom_notes'] == [
            {'title': 'Seguimiento', 'content': 'Confirmar recepción.'},
        ]
        assert payload['notes'][0] == {
            'id': payload['notes'][0]['id'],
            'title': 'Seguimiento',
            'content': 'Confirmar recepción.',
            'status': 'open',
            'episode_id': None,
            'resolution_note': '',
        }

    def test_update_document_replaces_custom_notes(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(
            markdown_doc_type,
            client_custom_notes=[{'title': 'Anterior', 'content': 'Contenido anterior.'}],
        )
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'client_custom_notes': [
                {'title': '  Nueva  ', 'content': '  Contenido nuevo.  '},
            ],
        })

        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.client_custom_notes == [
            {'title': 'Nueva', 'content': 'Contenido nuevo.'},
        ]

    def test_update_document_rejects_an_incomplete_custom_note(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'client_custom_notes': [{'title': 'Sin contenido', 'content': ''}],
        })

        assert response.data['result']['isError'] is True
        doc.refresh_from_db()
        assert doc.client_custom_notes == []

    def test_update_document_reparses_markdown(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, title='Old')
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'title': 'New',
            'markdown': '# Nuevo\n\nContenido.',
        })
        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.title == 'New'
        assert doc.content_json['meta']['title'] == 'New'
        assert doc.content_markdown.startswith('# Nuevo')

    def test_update_document_preserves_an_omitted_client_note_field(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(
            markdown_doc_type,
            client_email_subject='Asunto original',
            client_email_body='Correo original',
        )
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'client_email_body': 'Correo actualizado',
        })

        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.client_email_subject == 'Asunto original'
        assert doc.client_email_body == 'Correo actualizado'

    def test_update_document_clears_a_client_note_field(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, client_whatsapp_message='Mensaje anterior')
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'client_whatsapp_message': '',
        })

        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.client_whatsapp_message == ''

    def test_update_document_rejects_an_oversized_client_subject(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector

        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id,
            'client_email_subject': 'a' * 256,
        })

        assert response.data['result']['isError'] is True
        doc.refresh_from_db()
        assert doc.client_email_subject == ''

    def test_update_document_requires_at_least_one_field(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {'document_id': doc.id})
        assert response.data['result']['isError'] is True

    def test_delete_hidden_document(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, is_client_visible=False)
        _, token = documents_connector
        response = _call_confirmed(
            api_client, token, 'delete_document', {'document_id': doc.id},
        )
        assert response.data['result']['isError'] is False
        assert not Document.objects.filter(pk=doc.id).exists()

    def test_cannot_delete_visible_document(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, is_client_visible=True)
        _, token = documents_connector
        response = _call_confirmed(
            api_client, token, 'delete_document', {'document_id': doc.id},
        )
        assert response.data['result']['isError'] is True
        assert Document.objects.filter(pk=doc.id).exists()


@pytest.mark.django_db
class TestDocumentsMcpAppend:
    def test_append_concatenates_and_reparses_full_markdown(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, title='Largo', content_markdown='# Parte 1\n\nInicio.')
        _, token = documents_connector

        response = _call(api_client, token, 'append_document', {
            'document_id': doc.id,
            'markdown': '## Parte 2\n\nFinal.',
        })

        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.content_markdown == '# Parte 1\n\nInicio.\n\n## Parte 2\n\nFinal.'
        block_types = [b['type'] for b in doc.content_json['blocks']]
        assert block_types == ['heading', 'paragraph', 'heading', 'paragraph']

    def test_append_honors_custom_separator(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type, content_markdown='línea uno')
        _, token = documents_connector

        response = _call(api_client, token, 'append_document', {
            'document_id': doc.id,
            'markdown': 'línea dos',
            'separator': '\n',
        })

        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.content_markdown == 'línea uno\nlínea dos'

    def test_append_requires_markdown(self, api_client, documents_connector, markdown_doc_type):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector

        response = _call(api_client, token, 'append_document', {
            'document_id': doc.id,
            'markdown': '   ',
        })

        assert response.data['result']['isError'] is True

    def test_append_to_missing_document_is_an_error(self, api_client, documents_connector, markdown_doc_type):
        _, token = documents_connector

        response = _call(api_client, token, 'append_document', {
            'document_id': 999999,
            'markdown': 'contenido',
        })

        assert response.data['result']['isError'] is True


@pytest.mark.django_db
class TestDocumentsMcpMarkdownGuardrail:
    def test_list_documents_marks_a_custom_note(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        _make_doc(
            markdown_doc_type,
            title='Con nota',
            client_custom_notes=[{'title': 'Interna', 'content': 'Seguimiento.'}],
        )
        _, token = documents_connector

        response = _call(api_client, token, 'list_documents', {})

        payload = json.loads(response.data['result']['content'][0]['text'])
        assert payload['results'][0]['has_client_note'] is True

    def test_list_documents_excludes_collection_accounts(self, api_client, documents_connector, markdown_doc_type, collection_account_type):
        _make_doc(markdown_doc_type, title='Markdown doc')
        _make_doc(collection_account_type, title='Cuenta de cobro')
        _, token = documents_connector
        response = _call(api_client, token, 'list_documents', {})
        text = response.data['result']['content'][0]['text']
        assert 'Markdown doc' in text
        assert 'Cuenta de cobro' not in text

    def test_cannot_read_collection_account(self, api_client, documents_connector, collection_account_type):
        doc = _make_doc(collection_account_type, title='Cuenta')
        _, token = documents_connector
        response = _call(api_client, token, 'read_document', {'document_id': doc.id})
        assert response.data['result']['isError'] is True

    def test_cannot_delete_collection_account(self, api_client, documents_connector, collection_account_type):
        doc = _make_doc(collection_account_type, title='Cuenta', status='draft')
        _, token = documents_connector
        response = _call_confirmed(
            api_client, token, 'delete_document', {'document_id': doc.id},
        )
        assert response.data['result']['isError'] is True
        assert Document.objects.filter(pk=doc.id).exists()


@pytest.fixture
def superuser_client(api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='root_docs_test', password='x', is_staff=True, is_superuser=True,
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestDocumentsConnectorPanel:
    def test_panel_lists_documents_connector_with_tools(self, superuser_client, documents_connector):
        response = superuser_client.get('/api/mcp-connectors/')
        docs = next(c for c in response.data if c['slug'] == 'documents')
        assert docs['name'] == 'Gestor Documental'
        tool_names = [t['name'] for t in docs['tools']]
        assert 'create_document' in tool_names
        assert 'list_folders' in tool_names


@pytest.mark.django_db
class TestDocumentsMcpHandlerBranches:
    def test_list_documents_unknown_folder_errors(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        _, token = documents_connector
        response = _call(api_client, token, 'list_documents', {'folder_id': 999999})
        assert response.data['result']['isError'] is True

    def test_rename_folder_requires_name(self, api_client, documents_connector):
        folder = DocumentFolder.objects.create(name='Vieja')
        _, token = documents_connector
        response = _call(api_client, token, 'rename_folder', {
            'folder_id': folder.id, 'name': '  ',
        })
        assert response.data['result']['isError'] is True

    def test_list_documents_invalid_page_errors(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        _, token = documents_connector
        response = _call(api_client, token, 'list_documents', {'page': 'xx'})
        assert response.data['result']['isError'] is True

    def test_list_documents_filters_root_only(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        folder = DocumentFolder.objects.create(name='Contratos')
        _make_doc(markdown_doc_type, title='Raíz')
        _make_doc(markdown_doc_type, title='Guardado', folder=folder)
        _, token = documents_connector
        response = _call(api_client, token, 'list_documents', {'folder_id': 'none'})
        text = response.data['result']['content'][0]['text']
        assert 'Raíz' in text
        assert 'Guardado' not in text

    def test_list_documents_filters_by_folder(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        folder = DocumentFolder.objects.create(name='Contratos')
        _make_doc(markdown_doc_type, title='Raíz')
        _make_doc(markdown_doc_type, title='Guardado', folder=folder)
        _, token = documents_connector
        response = _call(api_client, token, 'list_documents', {'folder_id': folder.id})
        text = response.data['result']['content'][0]['text']
        assert 'Guardado' in text
        assert 'Raíz' not in text

    def test_create_document_invalid_language_errors(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        _, token = documents_connector
        response = _call(api_client, token, 'create_document', {
            'title': 'Doc', 'markdown': '# Hola', 'language': 'fr',
        })
        assert response.data['result']['isError'] is True

    def test_update_document_rejects_empty_title(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'title': '  ',
        })
        assert response.data['result']['isError'] is True

    def test_update_document_changes_client_name(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'client_name': 'ACME Corp',
        })
        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.client_name == 'ACME Corp'

    def test_update_document_changes_language(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'language': 'en',
        })
        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.language == 'en'

    def test_update_document_invalid_language_errors(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'language': 'fr',
        })
        assert response.data['result']['isError'] is True

    def test_update_document_changes_visibility(
        self, api_client, documents_connector, markdown_doc_type, superuser,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'is_client_visible': True,
        })
        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.is_client_visible is True

    def test_update_document_invalid_visibility_errors(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'is_client_visible': 'yes',
        })
        assert response.data['result']['isError'] is True


    def test_update_document_moves_to_folder(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        folder = DocumentFolder.objects.create(name='Destino')
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'update_document', {
            'document_id': doc.id, 'folder_id': folder.id,
        })
        assert response.data['result']['isError'] is False
        doc.refresh_from_db()
        assert doc.folder_id == folder.id

    def test_append_rejects_non_string_separator(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        response = _call(api_client, token, 'append_document', {
            'document_id': doc.id, 'markdown': 'Más texto', 'separator': 7,
        })
        assert response.data['result']['isError'] is True


@pytest.mark.django_db
class TestDocumentsMcpWorkflow:
    def test_state_tool_opens_an_mcp_episode(
        self, api_client, documents_connector, markdown_doc_type, superuser,
    ):
        doc = _make_doc(markdown_doc_type)
        sent = DocumentState.objects.get(system_key='sent')
        _, token = documents_connector

        response = _call(api_client, token, 'set_document_state', {
            'document_id': doc.id,
            'state_id': sent.id,
        })

        assert response.data['result']['isError'] is False
        episode = doc.state_episodes.get(state=sent, closed_at__isnull=True)
        assert episode.origin == DocumentStateEpisode.Origin.MCP

    def test_note_tools_close_the_linked_signal(
        self, api_client, documents_connector, markdown_doc_type, superuser,
    ):
        doc = _make_doc(markdown_doc_type)
        _, token = documents_connector
        created = _call(api_client, token, 'add_document_note', {
            'document_id': doc.id,
            'title': 'Total incorrecto',
            'content': 'Corregir el total.',
            'mark_needs_fix': True,
        })
        created_payload = json.loads(created.data['result']['content'][0]['text'])

        response = _call(api_client, token, 'finish_document_note', {
            'document_id': doc.id,
            'note_id': created_payload['id'],
            'resolution_note': 'Total corregido.',
            'close_linked_state': True,
            'move_cycle_to_bug_attended': True,
        })

        payload = json.loads(response.data['result']['content'][0]['text'])
        assert response.data['result']['isError'] is False
        assert payload['note']['status'] == 'resolved'
        assert payload['state_closed'] is True
        assert payload['cycle_moved'] is True

    def test_delete_note_tool_soft_deletes_note(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        note = DocumentNote.objects.create(document=doc, content='Ruido')
        _, token = documents_connector

        response = _call_confirmed(api_client, token, 'delete_document_notes', {
            'document_id': doc.id,
            'note_ids': [note.id],
        })

        note.refresh_from_db()
        assert response.data['result']['isError'] is False
        assert note.deleted_at is not None

    def test_read_document_hides_deleted_note(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        note = DocumentNote.objects.create(document=doc, content='No mostrar')
        note.deleted_at = timezone.now()
        note.save(update_fields=('deleted_at', 'updated_at'))
        _, token = documents_connector

        response = _call(api_client, token, 'read_document', {'document_id': doc.id})

        payload = json.loads(response.data['result']['content'][0]['text'])
        assert payload['notes'] == []

    def test_list_deleted_notes_returns_recoverable_content(
        self, api_client, documents_connector, markdown_doc_type, superuser,
    ):
        doc = _make_doc(markdown_doc_type)
        note = DocumentNote.objects.create(
            document=doc,
            content='Recuperable',
            deleted_at=timezone.now(),
            deleted_by=superuser,
        )
        _, token = documents_connector

        response = _call(api_client, token, 'list_deleted_document_notes', {
            'document_id': doc.id,
        })

        payload = json.loads(response.data['result']['content'][0]['text'])
        assert payload['notes'][0]['id'] == note.id
        assert payload['notes'][0]['content'] == 'Recuperable'

    def test_restore_note_tool_returns_note_to_active_scope(
        self, api_client, documents_connector, markdown_doc_type, superuser,
    ):
        doc = _make_doc(markdown_doc_type)
        note = DocumentNote.objects.create(
            document=doc,
            content='Restaurar',
            deleted_at=timezone.now(),
            deleted_by=superuser,
        )
        _, token = documents_connector

        response = _call(api_client, token, 'restore_document_note', {
            'document_id': doc.id,
            'note_id': note.id,
        })

        note.refresh_from_db()
        assert response.data['result']['isError'] is False
        assert note.deleted_at is None

    def test_bulk_delete_tool_rejects_foreign_note_atomically(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type)
        other = _make_doc(markdown_doc_type, title='Otro')
        local = DocumentNote.objects.create(document=doc, content='Local')
        foreign = DocumentNote.objects.create(document=other, content='Ajena')
        _, token = documents_connector

        response = _call_confirmed(api_client, token, 'delete_document_notes', {
            'document_id': doc.id,
            'note_ids': [local.id, foreign.id],
        })

        local.refresh_from_db()
        assert response.data['result']['isError'] is True
        assert local.deleted_at is None


@pytest.mark.django_db
class TestDocumentsMcpArchiveAwareness:
    """Lo archivado sale de circulación también para el MCP, no sólo el panel."""

    def test_list_documents_hides_archived(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        _make_doc(markdown_doc_type, title='Activo')
        _make_doc(markdown_doc_type, title='Viejo', is_archived=True)
        _, token = documents_connector

        response = _call(api_client, token, 'list_documents', {})

        text = response.data['result']['content'][0]['text']
        assert 'Activo' in text
        assert 'Viejo' not in text

    def test_list_folders_hides_archived_folders(
        self, api_client, documents_connector,
    ):
        DocumentFolder.objects.create(name='Activa')
        DocumentFolder.objects.create(name='Vieja', is_archived=True)
        _, token = documents_connector

        response = _call(api_client, token, 'list_folders', {})

        text = response.data['result']['content'][0]['text']
        assert 'Activa' in text
        assert 'Vieja' not in text

    def test_folder_document_count_excludes_archived(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        folder = DocumentFolder.objects.create(name='Contratos')
        _make_doc(markdown_doc_type, title='Activo', folder=folder)
        _make_doc(markdown_doc_type, title='Viejo', folder=folder, is_archived=True)
        _, token = documents_connector

        response = _call(api_client, token, 'list_folders', {})

        payload = json.loads(response.data['result']['content'][0]['text'])
        entry = next(f for f in payload['folders'] if f['id'] == folder.id)
        assert entry['document_count'] == 1

    def test_read_document_rejects_an_archived_document(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        doc = _make_doc(markdown_doc_type, is_archived=True)
        _, token = documents_connector

        response = _call(api_client, token, 'read_document', {'document_id': doc.id})

        assert response.data['result']['isError'] is True

    def test_create_document_rejects_an_archived_folder(
        self, api_client, documents_connector, markdown_doc_type,
    ):
        folder = DocumentFolder.objects.create(name='Vieja', is_archived=True)
        _, token = documents_connector

        response = _call(api_client, token, 'create_document', {
            'title': 'Nuevo', 'markdown': '# Hola', 'folder_id': folder.id,
        })

        assert response.data['result']['isError'] is True
