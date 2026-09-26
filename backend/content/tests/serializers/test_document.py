"""Tests for Document serializers.

Covers: DocumentListSerializer, DocumentDetailSerializer,
DocumentCreateUpdateSerializer, DocumentFromMarkdownSerializer.
"""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model

from content.models import Document, DocumentCollectionAccount, DocumentFolder
from content.serializers.document import (
    DocumentCreateUpdateSerializer,
    DocumentDetailSerializer,
    DocumentFromMarkdownSerializer,
    DocumentListSerializer,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def document(db):
    """A minimal Document instance."""
    return Document.objects.create(
        title='Test Document',
        client_name='ACME Corp',
        language='es',
        cover_type='generic',
        content_markdown='# Hello',
        content_json={'sections': []},
    )


# ── DocumentListSerializer ─────────────────────────────────────────────────────

class TestDocumentListSerializer:
    def test_serializes_expected_fields(self, document):
        data = DocumentListSerializer(document).data
        expected = {
            'id', 'uuid', 'title', 'slug', 'status', 'is_client_visible',
            'client_name',
            'client', 'client_display_name', 'project', 'project_name',
            'document_type_code', 'commercial_status',
            'display_state', 'is_generated_snapshot', 'is_contract_mirror',
            'source_proposal_id', 'source_version',
            'issue_date',
            'language', 'cover_type', 'template_style',
            'include_portada', 'include_subportada',
            'include_contraportada', 'folder', 'folder_name', 'tag_details',
            'active_states',
            'content_excerpt', 'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_cause',
            'thread_summary',
        }
        assert set(data.keys()) == expected

    def test_ordinary_document_is_not_the_contract_window(self, document):
        data = DocumentListSerializer(document).data
        assert data['is_contract_mirror'] is False

    def test_excludes_content_markdown(self, document):
        data = DocumentListSerializer(document).data
        assert 'content_markdown' not in data

    def test_content_excerpt_returns_short_markdown_whole(self, document):
        data = DocumentListSerializer(document).data
        assert data['content_excerpt'] == '# Hello'

    def test_content_excerpt_cuts_long_markdown_at_line_boundary(self, document):
        line = 'x' * 80
        document.content_markdown = '\n'.join([line] * 10)  # 809 chars
        document.save()

        data = DocumentListSerializer(document).data

        assert len(data['content_excerpt']) <= 500
        # Cut lands on a line boundary: only whole 80-char lines survive.
        assert all(part == line for part in data['content_excerpt'].split('\n'))

    def test_content_excerpt_empty_when_no_markdown(self, document):
        document.content_markdown = ''
        document.save()
        data = DocumentListSerializer(document).data
        assert data['content_excerpt'] == ''

    def test_excludes_content_json(self, document):
        data = DocumentListSerializer(document).data
        assert 'content_json' not in data

    def test_title_value_matches_instance(self, document):
        data = DocumentListSerializer(document).data
        assert data['title'] == 'Test Document'


# ── DocumentDetailSerializer ───────────────────────────────────────────────────

class TestDocumentDetailSerializer:
    def test_includes_content_markdown(self, document):
        data = DocumentDetailSerializer(document).data
        assert 'content_markdown' in data
        assert data['content_markdown'] == '# Hello'

    def test_includes_content_json(self, document):
        data = DocumentDetailSerializer(document).data
        assert 'content_json' in data
        assert data['content_json'] == {'sections': []}

    def test_serializes_all_expected_fields(self, document):
        data = DocumentDetailSerializer(document).data
        expected = {
            'id', 'uuid', 'title', 'slug', 'status', 'is_client_visible',
            'content_markdown', 'content_json', 'client_name',
            'client', 'client_display_name', 'project', 'project_name',
            'client_email_subject', 'client_email_body',
            'client_whatsapp_message', 'client_custom_notes',
            'document_type_code', 'commercial_status',
            'display_state', 'is_generated_snapshot', 'is_contract_mirror',
            'source_proposal_id', 'source_version',
            'public_number', 'issue_date', 'due_date', 'currency', 'total',
            'billing_notes', 'collection_account_observations',
            'language', 'cover_type', 'template_style',
            'include_portada', 'include_subportada',
            'include_contraportada', 'folder', 'folder_name',
            'tag_ids', 'tag_details', 'active_states', 'notes',
            'created_at', 'updated_at',
            'is_archived', 'archived_at', 'archived_cause',
            'thread_summary',
        }
        assert set(data.keys()) == expected

    def test_includes_collection_account_annotations(self):
        document = Document.objects.create(
            title='Cuenta de cobro', notes='Pago por transferencia.',
        )
        DocumentCollectionAccount.objects.create(
            document=document, observations='Emitida desde ingreso mensual.',
        )

        data = DocumentDetailSerializer(document).data

        assert data['billing_notes'] == 'Pago por transferencia.'
        assert (
            data['collection_account_observations']
            == 'Emitida desde ingreso mensual.'
        )


# ── DocumentCreateUpdateSerializer ────────────────────────────────────────────

class TestDocumentCreateUpdateSerializer:
    def test_valid_with_required_title(self):
        serializer = DocumentCreateUpdateSerializer(data={'title': 'New Doc'})
        assert serializer.is_valid(), serializer.errors

    def test_invalid_without_title(self):
        serializer = DocumentCreateUpdateSerializer(data={})
        assert not serializer.is_valid()
        assert 'title' in serializer.errors

    def test_content_markdown_is_optional(self):
        serializer = DocumentCreateUpdateSerializer(data={'title': 'Doc A'})
        assert serializer.is_valid(), serializer.errors
        assert 'content_markdown' not in serializer.errors

    def test_content_json_is_optional(self):
        serializer = DocumentCreateUpdateSerializer(data={'title': 'Doc B'})
        assert serializer.is_valid(), serializer.errors
        assert 'content_json' not in serializer.errors

    def test_invalid_language_choice(self):
        serializer = DocumentCreateUpdateSerializer(
            data={'title': 'Doc', 'language': 'xx'},
        )
        assert not serializer.is_valid()
        assert 'language' in serializer.errors

    def test_invalid_status_choice(self):
        serializer = DocumentCreateUpdateSerializer(
            data={'title': 'Doc', 'status': 'invalid'},
        )
        assert not serializer.is_valid()
        assert 'status' in serializer.errors

    def test_persists_the_client_note(self):
        serializer = DocumentCreateUpdateSerializer(data={
            'title': 'Informe mensual',
            'client_email_subject': 'Informe listo',
            'client_email_body': 'Hola Ana,\n\nAdjunto el informe.',
            'client_whatsapp_message': 'Hola Ana, ya quedó listo el informe.',
        })

        assert serializer.is_valid(), serializer.errors
        document = serializer.save()

        assert document.client_email_subject == 'Informe listo'
        assert document.client_email_body == 'Hola Ana,\n\nAdjunto el informe.'
        assert document.client_whatsapp_message == 'Hola Ana, ya quedó listo el informe.'

    def test_rejects_an_oversized_client_email_subject(self):
        serializer = DocumentCreateUpdateSerializer(data={
            'title': 'Informe mensual',
            'client_email_subject': 'a' * 256,
        })

        assert not serializer.is_valid()
        assert 'client_email_subject' in serializer.errors

    def test_persists_trimmed_custom_notes_in_order(self):
        serializer = DocumentCreateUpdateSerializer(data={
            'title': 'Informe mensual',
            'client_custom_notes': [
                {'title': '  Seguimiento  ', 'content': '  Llamar el viernes.  '},
                {'title': 'Pago', 'content': 'Confirmar la transferencia.'},
            ],
        })

        assert serializer.is_valid(), serializer.errors
        document = serializer.save()

        assert document.client_custom_notes == [
            {'title': 'Seguimiento', 'content': 'Llamar el viernes.'},
            {'title': 'Pago', 'content': 'Confirmar la transferencia.'},
        ]

    def test_rejects_an_incomplete_custom_note(self):
        serializer = DocumentCreateUpdateSerializer(data={
            'title': 'Informe mensual',
            'client_custom_notes': [{'title': 'Seguimiento', 'content': '  '}],
        })

        assert not serializer.is_valid()
        assert 'client_custom_notes' in serializer.errors

    def test_rejects_an_oversized_custom_note_title(self):
        serializer = DocumentCreateUpdateSerializer(data={
            'title': 'Informe mensual',
            'client_custom_notes': [{'title': 'a' * 256, 'content': 'Contenido.'}],
        })

        assert not serializer.is_valid()
        assert 'client_custom_notes' in serializer.errors


# ── DocumentFromMarkdownSerializer ────────────────────────────────────────────

class TestDocumentFromMarkdownSerializer:
    def test_valid_with_title_and_markdown(self):
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'My Doc', 'markdown': '# Content'},
        )
        assert serializer.is_valid(), serializer.errors

    def test_invalid_without_markdown(self):
        serializer = DocumentFromMarkdownSerializer(data={'title': 'My Doc'})
        assert not serializer.is_valid()
        assert 'markdown' in serializer.errors

    def test_invalid_without_title(self):
        serializer = DocumentFromMarkdownSerializer(data={'markdown': '# Content'})
        assert not serializer.is_valid()
        assert 'title' in serializer.errors

    def test_invalid_language_choice(self):
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'Doc', 'markdown': '# x', 'language': 'zz'},
        )
        assert not serializer.is_valid()
        assert 'language' in serializer.errors

    def test_defaults_language_to_es(self):
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'Doc', 'markdown': '# x'},
        )
        assert serializer.is_valid()
        assert serializer.validated_data['language'] == 'es'

    def test_defaults_include_portada_to_true(self):
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'Doc', 'markdown': '# x'},
        )
        assert serializer.is_valid()
        assert serializer.validated_data['include_portada'] is True

    def test_defaults_client_name_to_empty_string(self):
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'Doc', 'markdown': '# x'},
        )
        assert serializer.is_valid()
        assert serializer.validated_data['client_name'] == ''

    def test_defaults_the_client_note_to_empty_values(self):
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'Doc', 'markdown': '# x'},
        )

        assert serializer.is_valid()
        assert serializer.validated_data['client_email_subject'] == ''
        assert serializer.validated_data['client_email_body'] == ''
        assert serializer.validated_data['client_whatsapp_message'] == ''
        assert serializer.validated_data['client_custom_notes'] == []


# ── Asociación cliente/proyecto ───────────────────────────────────────────────

def make_client(email, *, first='Ana', last='Pérez'):
    user = get_user_model().objects.create_user(
        username=email, email=email, password='pass12345',
        first_name=first, last_name=last,
    )
    return UserProfile.objects.create(user=user, cedula='1049654583')


class TestDocumentAssociation:
    def test_client_writes_client_user_and_autofills_client_name(self):
        profile = make_client('ana@example.com')
        serializer = DocumentCreateUpdateSerializer(
            data={'title': 'Contrato', 'client': profile.pk},
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.client_user == profile.user
        assert 'Ana' in document.client_name

    def test_project_alone_derives_the_client(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        serializer = DocumentCreateUpdateSerializer(
            data={'title': 'Entregable', 'project': project.pk},
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.project == project
        assert document.client_user == profile.user

    def test_project_of_another_client_is_rejected(self):
        mine = make_client('ana@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        project = Project.objects.create(name='MIMITTOS', client=other.user)
        serializer = DocumentCreateUpdateSerializer(
            data={'title': 'Contrato', 'client': mine.pk, 'project': project.pk},
        )
        assert not serializer.is_valid()
        assert 'pertenece a otro cliente' in str(serializer.errors['project'])

    def test_changing_client_without_project_clears_the_project(self):
        kore = make_client('kore@example.com', first='Kore', last='SAS')
        ana = make_client('ana@example.com')
        project = Project.objects.create(name='Kore - Diseño', client=kore.user)
        document = Document.objects.create(
            title='Entregable', client_user=kore.user, project=project,
        )
        serializer = DocumentCreateUpdateSerializer(
            document, data={'client': ana.pk}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.client_user == ana.user
        assert document.project is None

    def test_client_null_unlinks_but_keeps_client_name(self):
        profile = make_client('ana@example.com')
        document = Document.objects.create(
            title='Contrato', client_user=profile.user, client_name='ACME Corp',
        )
        serializer = DocumentCreateUpdateSerializer(
            document, data={'client': None}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.client_user is None
        assert document.client_name == 'ACME Corp'

    def test_project_null_keeps_the_client(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        document = Document.objects.create(
            title='Entregable', client_user=profile.user, project=project,
        )
        serializer = DocumentCreateUpdateSerializer(
            document, data={'project': None}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.project is None
        assert document.client_user == profile.user

    def test_explicit_client_name_wins_over_the_autofill(self):
        profile = make_client('ana@example.com')
        serializer = DocumentCreateUpdateSerializer(
            data={
                'title': 'Doc', 'client': profile.pk,
                'client_name': 'Nombre propio',
            },
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.save().client_name == 'Nombre propio'

    def test_resending_the_same_client_preserves_a_custom_client_name(self):
        profile = make_client('ana@example.com')
        document = Document.objects.create(
            title='Doc', client_user=profile.user, client_name='Nombre propio',
        )
        serializer = DocumentCreateUpdateSerializer(
            document, data={'title': 'Doc v2', 'client': profile.pk}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.title == 'Doc v2'
        assert document.client_name == 'Nombre propio'

    def test_from_markdown_rejects_a_foreign_project(self):
        mine = make_client('ana@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        project = Project.objects.create(name='MIMITTOS', client=other.user)
        serializer = DocumentFromMarkdownSerializer(
            data={
                'title': 'Doc', 'markdown': '# x',
                'client': mine.pk, 'project': project.pk,
            },
        )
        assert not serializer.is_valid()
        assert 'pertenece a otro cliente' in str(serializer.errors['project'])

    def test_from_markdown_derives_client_user_from_the_project(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        serializer = DocumentFromMarkdownSerializer(
            data={'title': 'Doc', 'markdown': '# x', 'project': project.pk},
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['client_user'] == profile.user
        assert serializer.validated_data['client_name'] != ''

    def test_read_serializers_expose_profile_pk_and_project_name(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        document = Document.objects.create(
            title='Entregable', client_user=profile.user, project=project,
        )
        data = DocumentListSerializer(document).data
        assert data['client'] == profile.pk
        assert data['project'] == project.pk
        assert data['project_name'] == 'Kore - Diseño'
        assert data['client_display_name']


class TestMoveIntoAnAssociatedFolder:
    """Mover a una carpeta con dueño: hereda si está suelto, conserva si no.

    La carpeta organiza, no es dueña: un documento puede pertenecer a un
    cliente distinto al de su carpeta (mover una cuenta de cobro emitida a
    cualquier carpeta tiene que seguir siendo posible, y su cliente es
    inmutable). Por eso el default al mover es CONSERVAR, y adoptar es una
    decisión explícita — salvo cuando el documento no tiene cliente, donde
    adoptar no pisa nada.
    """

    def test_a_clientless_document_adopts_the_folder_association(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        project = Project.objects.create(name='Kore - Diseño', client=profile.user)
        folder = DocumentFolder.objects.create(
            name='Kore', client_user=profile.user, project=project,
        )
        document = Document.objects.create(title='Suelto')

        serializer = DocumentCreateUpdateSerializer(
            document, data={'folder_id': folder.pk}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.client_user == profile.user
        assert document.project == project

    def test_a_document_of_another_client_keeps_its_own(self):
        kore = make_client('kore@example.com', first='Kore', last='SAS')
        ana = make_client('ana@example.com')
        folder = DocumentFolder.objects.create(name='Kore', client_user=kore.user)
        document = Document.objects.create(title='Contrato', client_user=ana.user)

        serializer = DocumentCreateUpdateSerializer(
            document, data={'folder_id': folder.pk}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.client_user == ana.user
        assert document.folder == folder

    def test_adopt_folder_client_takes_the_folder_association(self):
        kore = make_client('kore@example.com', first='Kore', last='SAS')
        ana = make_client('ana@example.com')
        project = Project.objects.create(name='Kore - Diseño', client=kore.user)
        folder = DocumentFolder.objects.create(
            name='Kore', client_user=kore.user, project=project,
        )
        document = Document.objects.create(title='Contrato', client_user=ana.user)

        serializer = DocumentCreateUpdateSerializer(
            document,
            data={'folder_id': folder.pk, 'adopt_folder_client': True},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        document = serializer.save()
        assert document.client_user == kore.user
        assert document.project == project

    def test_moving_into_a_folder_without_client_changes_nothing(self):
        ana = make_client('ana@example.com')
        folder = DocumentFolder.objects.create(name='Varios')
        document = Document.objects.create(title='Contrato', client_user=ana.user)

        serializer = DocumentCreateUpdateSerializer(
            document, data={'folder_id': folder.pk}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.save().client_user == ana.user

    def test_an_explicit_client_in_the_same_request_wins_over_the_folder(self):
        """Elegir cliente y carpeta a la vez no es una herencia: es una decisión."""
        kore = make_client('kore@example.com', first='Kore', last='SAS')
        ana = make_client('ana@example.com')
        folder = DocumentFolder.objects.create(name='Kore', client_user=kore.user)
        document = Document.objects.create(title='Suelto')

        serializer = DocumentCreateUpdateSerializer(
            document,
            data={'folder_id': folder.pk, 'client': ana.pk},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.save().client_user == ana.user

    def test_an_explicit_null_client_survives_the_folder(self):
        """Lo heredado es un default, no una atadura: vaciarlo tiene que pegar."""
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        folder = DocumentFolder.objects.create(name='Kore', client_user=profile.user)

        serializer = DocumentCreateUpdateSerializer(
            data={'title': 'Suelto', 'folder_id': folder.pk, 'client': None},
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.save().client_user is None

    def test_adopt_folder_client_is_not_persisted_as_a_field(self):
        profile = make_client('kore@example.com', first='Kore', last='SAS')
        folder = DocumentFolder.objects.create(name='Kore', client_user=profile.user)
        document = Document.objects.create(title='Suelto')

        serializer = DocumentCreateUpdateSerializer(
            document,
            data={'folder_id': folder.pk, 'adopt_folder_client': True},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        assert not hasattr(Document, 'adopt_folder_client')
