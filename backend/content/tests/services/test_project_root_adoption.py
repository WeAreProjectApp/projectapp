"""Manual project-name collisions never create a competing document root."""

from datetime import date

import pytest
from accounts.models import Notification, Project, UserProfile
from django.db import transaction

from content.models import Document, DocumentFolder, DocumentOwnershipOperation
from content.services import folder_migration_service as migration
from content.services import project_document_folder_service as roots
from content.tests.mcp_parity import assert_no_writes, ownership_state

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('managed_kind', ['client', 'project'])
def test_nonmanual_homonyms_allow_independent_project_roots(make_client_profile, managed_kind):
    owner = make_client_profile()
    project = Project.objects.create(name='Existing project', client=owner.user)
    client_root = DocumentFolder.objects.create(
        name='Client root', managed_client=owner.user, client_user=owner.user,
    )
    candidates = {'none': None, 'client': client_root, 'project': roots.require_project_folder(project)}
    candidate = candidates[managed_kind]
    DocumentFolder.objects.filter(pk=getattr(candidate, 'pk', None)).update(name=' Shared name ')

    decision = assert_no_writes(roots.project_root_name_decision, 'shared name')
    second = Project.objects.create(name='shared name', client=owner.user)

    assert decision == {'decision': 'create'}
    assert roots.require_project_folder(second).name == 'shared name'
    assert roots.require_project_folder(project).pk != roots.require_project_folder(second).pk


def test_trimmed_case_insensitive_manual_root_is_adoptable_without_a_client():
    assert roots.project_root_name_decision('projectapp') == {'decision': 'create'}
    source = DocumentFolder.objects.create(name=' ProjectApp ')
    child = DocumentFolder.objects.create(name='Notes', parent=source)
    document = Document.objects.create(title='Private note', folder=child)

    decision = assert_no_writes(roots.project_root_name_decision, 'projectapp')

    assert decision['decision'] == 'adopt'
    assert decision['folder_id'] == source.pk
    assert decision['plan']['can_apply'] is True
    assert (decision['plan']['strategy'], decision['plan']['client_policy'], decision['plan']['portal_policy']) == (
        'adopt_source', 'abort_on_conflict', 'abort',
    )
    assert {row['id'] for row in decision['plan']['rows'] if row['resource_type'] == 'document'} == {document.pk}
    assert roots.project_root_name_decision('PROJECTAPP', exclude_folder_id=source.pk) == {'decision': 'create'}


def test_root_holding_contract_mirrors_requires_explicit_review(initialized_contract_mirrors):
    source = DocumentFolder.objects.create(name='ProjectApp')
    pinned = initialized_contract_mirrors.mirror_folder
    pinned.parent = source
    pinned.save(update_fields=['parent'])
    before = ownership_state()

    with pytest.raises(roots.ProjectRootNameConflict) as error:
        assert_no_writes(roots.project_root_name_decision, ' ProjectApp ')

    assert error.value.code == 'project_root_name_conflict'
    assert error.value.details['folder_ids'] == [source.pk]
    assert any(row['code'] == 'pinned' for row in error.value.details['reasons'])
    assert error.value.details['hint'] == roots.ROOT_NAME_HINT
    assert ownership_state() == before


@pytest.mark.parametrize('owned_kind', ['folder', 'document'])
def test_owned_content_needs_an_explicit_client_policy(make_client_profile, owned_kind):
    foreign = make_client_profile()
    source = DocumentFolder.objects.create(name='ProjectApp')
    child = DocumentFolder.objects.create(name='Foreign folder', parent=source)
    document = Document.objects.create(title='Foreign note', folder=source)
    models = {'folder': DocumentFolder, 'document': Document}
    records = {'folder': child, 'document': document}
    models[owned_kind].objects.filter(pk=records[owned_kind].pk).update(client_user=foreign.user)

    with pytest.raises(roots.ProjectRootNameConflict) as error:
        roots.project_root_name_decision('ProjectApp')

    assert error.value.details['reasons'] == [{
        'code': 'ownership_conflict', 'resource_type': owned_kind, 'resource_id': records[owned_kind].pk,
    }]
    assert not Project.objects.exists()


def test_archived_manual_homonym_still_blocks_creation():
    source = DocumentFolder.objects.create(name='ProjectApp', is_archived=True)

    with pytest.raises(roots.ProjectRootNameConflict) as error:
        roots.project_root_name_decision('ProjectApp')

    assert error.value.details['folder_ids'] == [source.pk]
    assert error.value.details['reasons'] == [{'code': 'migration_blocked', 'folder_id': source.pk}]
    assert DocumentFolder.objects.get(pk=source.pk).is_archived is True


def test_generated_snapshot_prevents_automatic_adoption():
    source = DocumentFolder.objects.create(name='ProjectApp')
    document = Document.objects.create(title='Frozen evidence', folder=source, generated_file='snapshots/evidence.pdf')

    with pytest.raises(roots.ProjectRootNameConflict) as error:
        roots.project_root_name_decision('ProjectApp')

    assert {'code': 'frozen', 'resource_type': 'document', 'resource_id': document.pk} in error.value.details['reasons']
    assert Document.objects.get(pk=document.pk).project_id is None


def test_visible_unassigned_document_prevents_automatic_portal_exposure():
    source = DocumentFolder.objects.create(name='ProjectApp')
    document = Document.objects.create(title='Visible estimate', folder=source, is_client_visible=True)

    with pytest.raises(roots.ProjectRootNameConflict) as error:
        roots.project_root_name_decision('ProjectApp')

    assert error.value.details['reasons'] == [{
        'code': 'portal_exposure', 'resource_type': 'document', 'resource_id': document.pk,
    }]
    assert Document.objects.get(pk=document.pk).is_client_visible is True


def test_multiple_manual_homonyms_are_reported_in_stable_order():
    first = DocumentFolder.objects.create(name=' ProjectApp ')
    second = DocumentFolder.objects.create(name='projectapp')

    with pytest.raises(roots.ProjectRootNameConflict) as error:
        roots.project_root_name_decision('PROJECTAPP')

    assert error.value.details['folder_ids'] == [first.pk, second.pk]
    assert error.value.details['paths'] == [first.name, second.name]
    assert error.value.details['reasons'] == [{'code': 'multiple_manual_roots'}]


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_create_auto_adopts_an_audited_reversible_root(super_client, superuser, make_client_profile, surface):
    owner = make_client_profile()
    UserProfile.objects.get_or_create(user=superuser, defaults={'role': UserProfile.ROLE_ADMIN})
    source = DocumentFolder.objects.create(name=' ProjectApp ')
    document = Document.objects.create(title='Original note', folder=source)
    before = ownership_state()
    payloads = {
        'panel': {'client_profile_id': owner.pk},
        'platform': {'client_id': owner.user_id, 'progress': 23, 'start_date': '2026-10-01'},
    }
    urls = {'panel': '/api/projects/create/', 'platform': '/api/accounts/projects/'}

    response = super_client.post(urls[surface], {'name': 'ProjectApp', **payloads[surface]}, format='json')

    assert response.status_code == 201, response.data
    project = Project.objects.get(pk=response.data['id'])
    receipt = response.data['document_root']
    assert receipt['folder_id'] == source.pk
    assert receipt['adopted'] is True
    assert DocumentFolder.objects.filter(parent__isnull=True, name='ProjectApp').count() == 1
    assert roots.require_project_folder(project).pk == source.pk
    document.refresh_from_db()
    assert (document.client_user_id, document.project_id) == (owner.user_id, project.pk)
    operation = DocumentOwnershipOperation.objects.get(pk=receipt['migration_id'])
    assert (operation.kind, operation.origin, operation.actor_id) == ('adoption', 'auto', superuser.pk)
    assert project.progress == {'panel': 0, 'platform': 23}[surface]
    assert project.start_date == {'panel': None, 'platform': date(2026, 10, 1)}[surface]
    undo = migration.preview_undo_migration(operation.pk)
    assert undo['can_apply'], undo['blockers']
    migration.undo_migration(operation.pk, undo['impact_hash'], 'Restaurar la carpeta anterior', f'undo-{surface}', actor=superuser)
    assert not Project.objects.filter(pk=project.pk).exists()
    assert ownership_state() == before


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_rename_rejects_a_manual_homonym_before_saving(super_client, superuser, make_client_profile, surface):
    owner = make_client_profile()
    UserProfile.objects.get_or_create(user=superuser, defaults={'role': UserProfile.ROLE_ADMIN})
    project = Project.objects.create(name='Old name', client=owner.user)
    manual = DocumentFolder.objects.create(name=' New name ')
    urls = {'panel': f'/api/projects/{project.pk}/update/', 'platform': f'/api/accounts/projects/{project.pk}/'}

    response = super_client.patch(urls[surface], {'name': 'new name'}, format='json')

    assert response.status_code == 400, response.data
    assert response.data['code'] == 'project_root_name_conflict'
    assert response.data['folder_ids'] == [manual.pk]
    project.refresh_from_db()
    assert project.name == roots.require_project_folder(project).name == 'Old name'
    assert not DocumentOwnershipOperation.objects.exists()


def test_existing_same_name_project_save_preserves_old_root_name(make_client_profile, caplog):
    owner = make_client_profile()
    project = Project.objects.create(name='Old name', client=owner.user)
    manual = DocumentFolder.objects.create(name='New name')
    Project.objects.filter(pk=project.pk).update(name='New name')
    project.refresh_from_db()

    project.description = 'Save unrelated historical data'
    project.save(update_fields=['description', 'updated_at'])

    root = roots.require_project_folder(project)
    assert root.name == 'Old name'
    assert root.project_id == root.managed_project_id == project.pk
    assert str(manual.pk) in caplog.text
    assert 'manual root conflict' in caplog.text


def test_ensure_root_defence_rolls_back_a_project_created_without_prevalidation(make_client_profile):
    owner = make_client_profile()
    source = DocumentFolder.objects.create(name='ProjectApp')
    before = ownership_state()

    with pytest.raises(roots.ProjectRootNameConflict), transaction.atomic():
        Project.objects.create(name='ProjectApp', client=owner.user)

    assert not Project.objects.exists()
    assert ownership_state() == before
    assert DocumentFolder.objects.get(pk=source.pk).managed_project_id is None


@pytest.mark.parametrize('surface', ['panel', 'platform'])
def test_blocked_create_keeps_the_manual_tree_unchanged(super_client, superuser, make_client_profile, surface):
    owner = make_client_profile()
    UserProfile.objects.get_or_create(user=superuser, defaults={'role': UserProfile.ROLE_ADMIN})
    source = DocumentFolder.objects.create(name='ProjectApp', is_archived=True)
    before = ownership_state()
    urls = {'panel': '/api/projects/create/', 'platform': '/api/accounts/projects/'}
    client_fields = {'panel': 'client_profile_id', 'platform': 'client_id'}
    client_ids = {'panel': owner.pk, 'platform': owner.user_id}

    response = super_client.post(urls[surface], {
        'name': 'ProjectApp', client_fields[surface]: client_ids[surface],
    }, format='json')

    assert response.status_code == 400, response.data
    assert response.data['code'] == 'project_root_name_conflict'
    assert response.data['folder_ids'] == [source.pk]
    assert not Project.objects.exists()
    assert ownership_state() == before


@pytest.mark.parametrize('added_information', ['configuration', 'notification'])
def test_platform_creation_undo_refuses_changed_startup_facts(
    super_client, superuser, make_client_profile, added_information,
):
    owner = make_client_profile()
    UserProfile.objects.get_or_create(user=superuser, defaults={'role': UserProfile.ROLE_ADMIN})
    DocumentFolder.objects.create(name='ProjectApp')
    response = super_client.post('/api/accounts/projects/', {
        'name': 'ProjectApp', 'client_id': owner.user_id, 'progress': 23,
    }, format='json')
    assert response.status_code == 201, response.data
    project = Project.objects.get(pk=response.data['id'])
    migration_id = response.data['document_root']['migration_id']
    notification = Notification.objects.get(project=project)
    queries = {
        'configuration': Project.objects.filter(pk=project.pk),
        'notification': Notification.objects.filter(pk=notification.pk),
    }
    changes = {'configuration': {'production_url': 'https://new.example.com'}, 'notification': {'message': 'New information'}}
    queries[added_information].update(**changes[added_information])
    before = ownership_state()

    preview = migration.preview_undo_migration(migration_id)
    with pytest.raises(migration.FolderMigrationError) as error:
        migration.undo_migration(migration_id, preview['impact_hash'], 'No borrar datos nuevos', 'blocked-startup-undo', actor=superuser)

    assert preview['can_apply'] is False
    assert error.value.code == 'undo_blocked'
    assert any(row['key'] == {'configuration': 'configuration', 'notification': 'notifications'}[added_information]
               for blocker in preview['blockers'] for row in blocker.get('dependencies', []))
    assert Project.objects.filter(pk=project.pk).exists()
    assert Notification.objects.filter(pk=notification.pk).exists()
    assert ownership_state() == before
