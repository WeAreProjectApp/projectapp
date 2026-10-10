"""Mirror folder pins preserve synchronization across document-tree changes."""
import importlib
from io import StringIO

import pytest
from accounts.models import Project
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from content.models import (
    ContractTemplateMirror,
    Document,
    DocumentFolder,
    McpConnector,
)
from content.serializers.document_folder import DocumentFolderSerializer
from content.services import (
    contract_mirror_service,
    contract_template_service,
    document_folder_service,
)
from content.services.contract_template_validation import ContractTemplateError
from content.services.project_force_deletion import (
    ProjectForceDeleteError,
    force_delete_project,
    forced_deletion_preview,
)
from content.tests.mcp_parity import (
    assert_no_writes,
    call_tool_inprocess,
    ownership_state,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def mirror_tree(initialized_contract_mirrors):
    root = DocumentFolder.objects.create(name='ProjectApp')
    folder = initialized_contract_mirrors.mirror_folder
    folder.parent = root
    folder.save(update_fields=['parent'])
    return root, folder


@pytest.fixture
def documents_credential(superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documentos'},
    )
    token = connector.generate_token()
    credential = connector.credential_for_token(token)
    credential.actor = superuser
    credential.save(update_fields=['actor', 'updated_at'])
    return credential


def _mirror_ids(template):
    return sorted(template.mirrors.values_list('document_id', flat=True))


def _update_arguments():
    current = contract_template_service.read_template('combined')
    return {
        'variant': 'combined', 'markdown': current['markdown'] + '\n',
        'if_match': current['etag'], 'change_note': 'Sincronizar tras reorganizar carpetas.',
    }


@pytest.mark.parametrize('location', ['shared', 'split'])
def test_backfill_pins_only_an_unambiguous_folder(coherent_template, location):
    folder = DocumentFolder.objects.create(name='Textos contractuales')
    other = DocumentFolder.objects.create(name='Otra ubicación')
    legacy = Document.objects.create(title='Espejo legado', folder=folder)
    product = Document.objects.create(
        title='Espejo de producto', folder={'shared': folder, 'split': other}[location],
    )
    unfiled = Document.objects.create(title='Espejo sin ubicación')
    coherent_template.mirror_document = legacy
    coherent_template.save(update_fields=['mirror_document'])
    ContractTemplateMirror.objects.create(
        template=coherent_template, variant='product', document=product,
        revision=coherent_template.versions.get(variant='product'),
        pdf_content=b'%PDF-test', synced_at=timezone.now(),
    )
    ContractTemplateMirror.objects.create(
        template=coherent_template, variant='service', document=unfiled,
        revision=coherent_template.versions.get(variant='service'),
        pdf_content=b'%PDF-test', synced_at=timezone.now(),
    )
    migration = importlib.import_module('content.migrations.0286_contracttemplate_mirror_folder')

    migration.backfill_mirror_folder(apps, connection.schema_editor())

    coherent_template.refresh_from_db()
    assert coherent_template.mirror_folder_id == {'shared': folder.pk, 'split': None}[location]
    assert coherent_template.mirror_document_id == legacy.pk
    assert list(coherent_template.mirrors.order_by('variant').values_list('document_id', flat=True)) == [product.pk, unfiled.pk]


def test_legacy_binding_derives_the_folder_without_persisting_a_pin(coherent_template):
    folder = DocumentFolder.objects.create(name='Plantilla histórica')
    legacy = Document.objects.create(title='Legado', folder=folder)
    coherent_template.mirror_document = legacy
    coherent_template.save(update_fields=['mirror_document'])

    pinned, source = assert_no_writes(contract_mirror_service.pinned_mirror_folder)

    assert (pinned.pk, source) == (folder.pk, 'derived')
    assert contract_mirror_service.is_pinned_mirror_folder(folder) is True
    coherent_template.refresh_from_db()
    assert coherent_template.mirror_folder_id is None


def test_derived_pin_synchronizes_mirrors_after_a_rename(initialized_contract_mirrors, superuser):
    template = initialized_contract_mirrors
    folder = template.mirror_folder
    folder.name = 'Plantillas vigentes'
    folder.save(update_fields=['name'])
    template.mirror_folder = None
    template.save(update_fields=['mirror_folder'])

    listing = assert_no_writes(contract_template_service.list_mirrors)
    result = contract_template_service.apply_update(_update_arguments(), actor=superuser)

    assert listing['pinned_folder']['pin_source'] == 'derived'
    assert listing['pinned_folder']['pinned_folder_id'] == folder.pk
    assert [row['synchronized'] for row in listing['mirrors']] == [True, True, True]
    assert result['results'][0]['synchronized'] is True
    template.refresh_from_db()
    assert template.mirror_folder_id is None


def test_ambiguous_bindings_require_an_explicit_folder_pin(initialized_contract_mirrors, superuser):
    template = initialized_contract_mirrors
    configured = template.mirror_folder
    other = DocumentFolder.objects.create(name='Espejo desubicado')
    mirror = template.mirrors.get(variant='service')
    Document.objects.filter(pk=mirror.document_id).update(folder=other)
    assert contract_mirror_service.pinned_mirror_folder(template) == (configured, 'field')
    assert contract_template_service.list_mirrors()['mirrors'][2]['synchronized'] is False
    template.mirror_folder = None
    template.save(update_fields=['mirror_folder'])
    before = ownership_state()

    with pytest.raises(ContractTemplateError) as error:
        contract_template_service.apply_update(_update_arguments(), actor=superuser)

    assert contract_mirror_service.pinned_mirror_folder(template) == (None, 'unpinned')
    assert error.value.code == 'MIRROR_SYNC_FAILED'
    assert error.value.details['stage'] == 'folder_pin'
    assert '--folder-id' in error.value.details['hint']
    assert ownership_state() == before
    assert contract_template_service.read_template('combined')['version'] == 1


def test_an_unfiled_mirror_prevents_deriving_a_folder(initialized_contract_mirrors, superuser):
    template = initialized_contract_mirrors
    template.mirror_folder = None
    template.save(update_fields=['mirror_folder'])
    Document.objects.filter(pk=template.mirrors.get(variant='product').document_id).update(folder=None)

    state = assert_no_writes(contract_mirror_service.pinned_folder_state)
    with pytest.raises(ContractTemplateError) as error:
        contract_template_service.apply_update(_update_arguments(), actor=superuser)

    assert state == {
        'pinned_folder_id': None, 'pin_source': 'unpinned', 'folder_path': None,
        'folder_movable': False, 'archive_blocked': False, 'archive_block_reason': None,
    }
    assert error.value.details['stage'] == 'folder_pin'
    assert contract_template_service.read_template('combined')['version'] == 1


@pytest.mark.parametrize('target', ['pinned', 'ancestor'])
def test_tree_reorganization_preserves_mirror_synchronization(
    admin_client, mirror_tree, initialized_contract_mirrors, superuser, target,
):
    root, pinned = mirror_tree
    folder = {'pinned': pinned, 'ancestor': root}[target]
    destination = DocumentFolder.objects.create(name='Destino')
    arguments = _update_arguments()

    moved = admin_client.patch(reverse('update-document-folder', args=[folder.pk]), {
        'name': 'Carpeta reorganizada', 'parent_id': destination.pk, 'order': 7,
    }, format='json')
    listing = contract_template_service.list_mirrors()
    updated = contract_template_service.apply_update(arguments, actor=superuser)

    assert moved.status_code == 200
    folder.refresh_from_db()
    assert (folder.name, folder.parent_id, folder.order) == ('Carpeta reorganizada', destination.pk, 7)
    assert listing['pinned_folder']['pinned_folder_id'] == pinned.pk
    assert listing['pinned_folder']['folder_path'].startswith('Destino / ')
    assert [row['synchronized'] for row in listing['mirrors']] == [True, True, True]
    assert updated['results'][0]['synchronized'] is True
    mirror = initialized_contract_mirrors.mirrors.get(variant='combined')
    assert mirror.revision.markdown == arguments['markdown']
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert set(initialized_contract_mirrors.mirrors.values_list('document__folder_id', flat=True)) == {pinned.pk}


@pytest.mark.parametrize('target', ['pinned', 'ancestor'])
def test_panel_archive_explains_the_contract_mirror_blocker(
    admin_client, mirror_tree, initialized_contract_mirrors, target,
):
    root, pinned = mirror_tree
    folder = {'pinned': pinned, 'ancestor': root}[target]
    messages = {
        'pinned': 'Contratos guarda los espejos contractuales y no se puede archivar.',
        'ancestor': 'La carpeta «ProjectApp» contiene Contratos con los espejos contractuales; mueve Contratos a otra carpeta primero.',
    }
    before = ownership_state()

    response = admin_client.patch(reverse('archive-document-folder', args=[folder.pk]), {}, format='json')

    assert response.status_code == 409
    assert response.json() == {
        'detail': messages[target], 'code': 'contract_mirror_folder_archive_blocked',
        'contracts_folder_id': pinned.pk, 'contracts_folder_path': 'ProjectApp / Contratos',
        'mirror_document_ids': _mirror_ids(initialized_contract_mirrors),
    }
    assert ownership_state() == before


def test_mcp_archive_preserves_the_folder_blocker_details(
    mirror_tree, initialized_contract_mirrors, documents_credential,
):
    root, pinned = mirror_tree
    before = ownership_state()

    preview = call_tool_inprocess('documents', 'archive_folder', {'folder_id': root.pk}, credential=documents_credential)
    result = call_tool_inprocess('documents', 'confirm_action', {
        'confirmation_id': preview['confirmation_id'],
    }, credential=documents_credential)

    assert result['error']['code'] == 'CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED'
    details = result['error']['details']
    assert details['contracts_folder_id'] == pinned.pk
    assert details['contracts_folder_path'] == 'ProjectApp / Contratos'
    assert details['mirror_document_ids'] == _mirror_ids(initialized_contract_mirrors)
    assert 'mueve Contratos a otra carpeta primero' in result['error']['message']
    assert ownership_state() == before


@pytest.mark.parametrize('association', ['client', 'project'])
def test_panel_rejects_assigning_the_pinned_folder(
    admin_client, initialized_contract_mirrors, make_client_profile, association,
):
    profile = make_client_profile()
    project = Project.objects.create(name='Dueño nuevo', client=profile.user)
    pinned = initialized_contract_mirrors.mirror_folder

    response = admin_client.patch(reverse('update-document-folder', args=[pinned.pk]), {
        association: {'client': profile.pk, 'project': project.pk}[association],
    }, format='json')

    assert response.status_code == 409
    assert response.json()['code'] == 'contract_mirror_folder_pinned'
    pinned.refresh_from_db()
    assert (pinned.client_user_id, pinned.project_id) == (None, None)


def test_serializer_defends_the_pinned_association(initialized_contract_mirrors, make_client_profile):
    profile = make_client_profile()
    pinned = initialized_contract_mirrors.mirror_folder
    serializer = DocumentFolderSerializer(pinned, data={'client': profile.pk}, partial=True)

    with pytest.raises(ValidationError) as error:
        serializer.is_valid(raise_exception=True)

    assert error.value.detail['code'] == ['contract_mirror_folder_pinned']
    assert error.value.get_codes()['detail'] == ['contract_mirror_folder_pinned']
    pinned.refresh_from_db()
    assert pinned.client_user_id is None


def test_ancestor_client_change_preserves_the_whole_pinned_branch(
    admin_client, mirror_tree, initialized_contract_mirrors, make_client_profile,
):
    root, pinned = mirror_tree
    profile = make_client_profile()
    nested = DocumentFolder.objects.create(name='Anexos internos', parent=pinned)
    protected = Document.objects.create(title='Anexo interno', folder=nested)
    movable_folder = DocumentFolder.objects.create(name='Trabajo', parent=root)
    movable = Document.objects.create(title='Trabajo nuevo', folder=movable_folder)

    preview_response = assert_no_writes(admin_client.get, reverse(
        'preview-document-folder-client-change', args=[root.pk],
    ), {'client_profile_id': profile.pk})
    preview = preview_response.json()
    applied = admin_client.post(reverse('change-document-folder-client', args=[root.pk]), {
        'client_profile_id': profile.pk, 'mode': 'propagate',
        'folder_ids': preview['folder_ids'], 'document_ids': preview['document_ids'],
    }, format='json')

    assert preview_response.status_code == 200
    assert {row['id'] for row in preview['folders_pinned']} == {pinned.pk, nested.pk}
    protected_ids = set(_mirror_ids(initialized_contract_mirrors)) | {protected.pk}
    assert {row['id'] for row in preview['documents_pinned']} == protected_ids
    assert (preview['totals']['pinned'], preview['totals']['pinned_folders']) == (4, 2)
    assert (preview['folder_ids'], preview['document_ids']) == ([movable_folder.pk], [movable.pk])
    assert applied.status_code == 200
    assert applied.json()['moved'] == {'folders': 1, 'documents': 1}
    assert applied.json()['skipped']['pinned'] == 4
    assert set(DocumentFolder.objects.filter(pk__in=[pinned.pk, nested.pk]).values_list('client_user_id', 'project_id')) == {(None, None)}
    assert set(Document.objects.filter(pk__in=protected_ids).values_list('client_user_id', 'project_id')) == {(None, None)}
    movable.refresh_from_db()
    root.refresh_from_db()
    assert (root.client_user_id, movable.client_user_id) == (profile.user_id, profile.user_id)


def test_direct_client_change_cannot_reassign_the_pinned_branch(
    initialized_contract_mirrors, make_client_profile, superuser,
):
    folder = initialized_contract_mirrors.mirror_folder
    nested = DocumentFolder.objects.create(name='Rama interna protegida', parent=folder)
    profile = make_client_profile()
    before = ownership_state()

    with pytest.raises(ValidationError) as preview_error:
        assert_no_writes(document_folder_service.change_client_preview, folder, profile)
    with pytest.raises(ValidationError) as apply_error:
        document_folder_service.change_client_apply(folder, profile, 'propagate', superuser)
    with pytest.raises(ValidationError) as nested_preview_error:
        assert_no_writes(document_folder_service.change_client_preview, nested, profile)
    with pytest.raises(ValidationError) as nested_apply_error:
        document_folder_service.change_client_apply(nested, profile, 'propagate', superuser)

    assert preview_error.value.detail['code'] == 'contract_mirror_folder_pinned'
    assert apply_error.value.detail == preview_error.value.detail
    assert nested_preview_error.value.detail == preview_error.value.detail
    assert nested_apply_error.value.detail == preview_error.value.detail
    assert ownership_state() == before


def test_initializer_pins_by_id_idempotently(coherent_template, superuser):
    folder = DocumentFolder.objects.create(name='Plantillas vigentes')

    call_command('initialize_contract_template_mirrors', apply=True, folder_id=folder.pk, actor_id=superuser.pk, stdout=StringIO())
    before = list(coherent_template.mirrors.order_by('pk').values_list('document_id', 'synced_at', 'revision_id'))
    call_command('initialize_contract_template_mirrors', apply=True, folder_id=folder.pk, actor_id=superuser.pk, stdout=StringIO())

    coherent_template.refresh_from_db()
    assert coherent_template.mirror_folder_id == folder.pk
    assert coherent_template.mirrors.count() == 3
    assert list(coherent_template.mirrors.order_by('pk').values_list('document_id', 'synced_at', 'revision_id')) == before
    assert [row['synchronized'] for row in contract_template_service.list_mirrors()['mirrors']] == [True, True, True]


def test_initializer_refuses_repinning(initialized_contract_mirrors, superuser):
    folder = DocumentFolder.objects.create(name='Destino de re-fijación')
    before = ownership_state()
    pinned_id = initialized_contract_mirrors.mirror_folder_id

    with pytest.raises(CommandError, match=f'Los espejos ya están fijados a la carpeta {pinned_id}; no se re-fijan.'):
        call_command('initialize_contract_template_mirrors', apply=True, folder_id=folder.pk, actor_id=superuser.pk, stdout=StringIO())

    initialized_contract_mirrors.refresh_from_db()
    assert initialized_contract_mirrors.mirror_folder_id == pinned_id
    assert ownership_state() == before


def test_mcp_folder_flags_match_available_operations(admin_client, mirror_tree, documents_credential):
    _root, pinned = mirror_tree
    destination = DocumentFolder.objects.create(name='Nueva raíz')

    listed = assert_no_writes(call_tool_inprocess, 'documents', 'list_contract_mirrors', {}, credential=documents_credential)
    moved = admin_client.patch(reverse('update-document-folder', args=[pinned.pk]), {
        'parent_id': destination.pk,
    }, format='json')
    refreshed = call_tool_inprocess('documents', 'list_contract_mirrors', {}, credential=documents_credential)
    archived = admin_client.patch(reverse('archive-document-folder', args=[pinned.pk]), {}, format='json')

    assert listed['pinned_folder']['folder_movable'] is True
    assert listed['pinned_folder']['archive_blocked'] is True
    assert listed['pinned_folder']['pin_source'] == 'field'
    assert [row['folder_movable'] for row in listed['mirrors']] == [True, True, True]
    assert moved.status_code == 200
    assert refreshed['pinned_folder']['folder_path'] == 'Nueva raíz / Contratos'
    assert {row['folder_path'] for row in refreshed['mirrors']} == {'Nueva raíz / Contratos'}
    assert archived.status_code == 409
    assert archived.json()['detail'] == listed['pinned_folder']['archive_block_reason']


def test_force_delete_requires_moving_the_pinned_folder_out(
    initialized_contract_mirrors, make_client_profile, superuser, admin_client,
):
    profile = make_client_profile()
    project = Project.objects.create(name='Proyecto con espejos', client=profile.user)
    folder = initialized_contract_mirrors.mirror_folder
    folder.parent = project.document_root_folder
    folder.save(update_fields=['parent'])

    archived = admin_client.patch(reverse('archive-document-folder', args=[project.document_root_folder.pk]), {}, format='json')
    preview = forced_deletion_preview(project, actor=superuser)
    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(project.pk, actor=superuser, confirmation='DELETE',
            impact_token=preview['impact_token'], delete_keys=preview['delete_keys'])
    moved = admin_client.patch(reverse('update-document-folder', args=[folder.pk]), {'parent_id': None}, format='json')
    released = forced_deletion_preview(project, actor=superuser)

    assert archived.status_code == 409
    assert archived.json()['code'] == 'contract_mirror_folder_archive_blocked'
    assert archived.json()['contracts_folder_id'] == folder.pk
    assert archived.json()['contracts_folder_path'] == 'Proyecto con espejos / Contratos'
    assert preview['can_delete'] is False
    assert {'key': 'content.documentfolder', 'id': str(folder.pk),
        'message': 'Mueve Contratos fuera del proyecto antes de eliminarlo: guarda los espejos contractuales que deben conservarse.'} in preview['blockers']
    assert error.value.code == 'project_force_delete_blocked'
    assert moved.status_code == 200
    assert released['can_delete'] is True
    assert Project.objects.filter(pk=project.pk).exists()
    assert [row['synchronized'] for row in contract_template_service.list_mirrors()['mirrors']] == [True, True, True]
