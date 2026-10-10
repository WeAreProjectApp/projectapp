"""Scope normalization, folder races and movement-specific ownership guards."""

from types import SimpleNamespace

import pytest
from accounts.models import Project
from django.urls import reverse

from content.models import Document, DocumentFolder, DocumentType
from content.serializers.document_folder import DocumentFolderSerializer
from content.services.document_ownership_planner import (
    OwnershipPlanError,
    apply_ownership_plan,
    plan_ownership,
)
from content.tests.mcp_parity import assert_no_writes, ownership_state

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(make_client_profile, superuser):
    owner = make_client_profile()
    project = Project.objects.create(name='Guard destination project', client=owner.user)
    target = DocumentFolder.objects.create(name='Guard target', client_user=owner.user, project=project)
    source = DocumentFolder.objects.create(name='Guard source')
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    return SimpleNamespace(owner=owner, project=project, target=target, source=source, kind=kind, actor=superuser)


def test_root_destination_only_accepts_folders(tree):
    folder = DocumentFolder.objects.create(name='Owned child', parent=tree.source,
                                           client_user=tree.owner.user, project=tree.project)
    args = {'folder_ids': [folder.pk], 'destination_folder_id': None, 'client_policy': 'inherit'}
    plan = assert_no_writes(plan_ownership, **args)
    apply_ownership_plan(args, actor=tree.actor, expected_plan_hash=plan['plan_hash'])
    folder.refresh_from_db()
    assert (folder.parent_id, folder.client_user_id, folder.project_id) == (None, tree.owner.user_id, tree.project.pk)
    document = Document.objects.create(title='Already at root', document_type=tree.kind)
    before = ownership_state()

    rejected = assert_no_writes(plan_ownership, document_ids=[document.pk], destination_folder_id=None, client_policy='keep')
    with pytest.raises(OwnershipPlanError) as error:
        apply_ownership_plan({'document_ids': [document.pk], 'destination_folder_id': None, 'client_policy': 'keep'}, actor=tree.actor)

    assert error.value.details['blockers'] == rejected['blockers']
    assert rejected['blockers'][0]['code'] == 'folder_required'
    assert ownership_state() == before


def test_nested_selections_preserve_the_subtree(tree):
    child = DocumentFolder.objects.create(name='Selected descendant', parent=tree.source)
    document = Document.objects.create(title='Nested document', folder=child, document_type=tree.kind)
    args = {'folder_ids': [child.pk, tree.source.pk], 'destination_folder_id': tree.target.pk,
            'client_policy': 'abort_on_conflict'}

    plan = assert_no_writes(plan_ownership, **args)
    apply_ownership_plan(args, actor=tree.actor, expected_plan_hash=plan['plan_hash'])

    child.refresh_from_db()
    tree.source.refresh_from_db()
    document.refresh_from_db()
    assert (tree.source.parent_id, child.parent_id, document.folder_id) == (tree.target.pk, tree.source.pk, child.pk)
    assert len(plan['rows']) == 3
    assert all(row['after']['client_profile_id'] == tree.owner.pk for row in plan['rows'])
    assert (document.client_user_id, document.project_id) == (tree.owner.user_id, tree.project.pk)


def test_planned_siblings_cannot_introduce_a_duplicate(tree):
    other_parent = DocumentFolder.objects.create(name='Other source parent')
    first = DocumentFolder.objects.create(name='Same name', parent=tree.source)
    second = DocumentFolder.objects.create(name=' SAME NAME ', parent=other_parent)
    args = {'folder_ids': [first.pk, second.pk], 'destination_folder_id': tree.target.pk, 'client_policy': 'inherit'}
    before = ownership_state()

    plan = assert_no_writes(plan_ownership, **args)
    with pytest.raises(OwnershipPlanError):
        apply_ownership_plan(args, actor=tree.actor, expected_plan_hash=plan['plan_hash'])

    assert {row['resource_id'] for row in plan['blockers']} == {first.pk, second.pk}
    assert {row['code'] for row in plan['blockers']} == {'duplicate_folder_name'}
    assert ownership_state() == before


def test_frozen_owner_can_follow_a_matching_folder_move(tree):
    document = Document.objects.create(title='Frozen matching owner', folder=tree.source, document_type=tree.kind,
                                        client_user=tree.owner.user, project=tree.project, generated_file='generated/matching.pdf')
    args = {'folder_ids': [tree.source.pk], 'destination_folder_id': tree.target.pk, 'client_policy': 'keep'}

    plan = assert_no_writes(plan_ownership, **args)
    apply_ownership_plan(args, actor=tree.actor, expected_plan_hash=plan['plan_hash'])

    tree.source.refresh_from_db()
    document.refresh_from_db()
    document_row = next(row for row in plan['rows'] if row['resource_type'] == 'document')
    assert document_row['status'] == 'frozen'
    assert document_row['before'] == document_row['after']
    assert tree.source.parent_id == tree.target.pk
    assert document.folder_id == tree.source.pk
    assert document.generated_file.name == 'generated/matching.pdf'


def test_policy_save_rechecks_a_previously_unchanged_parent(tree):
    tree.source.parent = tree.target
    tree.source.save(update_fields=['parent'])
    document = Document.objects.create(title='Validated before reparenting', document_type=tree.kind, folder=tree.source)
    serializer = DocumentFolderSerializer(tree.source, data={'parent_id': tree.target.pk, 'client_policy': 'inherit'},
                                          partial=True, context={'request': SimpleNamespace(user=tree.actor)})
    assert serializer.is_valid(), serializer.errors
    DocumentFolder.objects.filter(pk=tree.source.pk).update(parent=None)

    serializer.save()

    tree.source.refresh_from_db()
    document.refresh_from_db()
    assert tree.source.parent_id == tree.target.pk
    assert (tree.source.client_user_id, tree.source.project_id) == (tree.owner.user_id, tree.project.pk)
    assert (document.client_user_id, document.project_id) == (tree.owner.user_id, tree.project.pk)


def test_already_moved_folder_invalidates_the_preview(tree, admin_client):
    document = Document.objects.create(title='Concurrent destination', folder=tree.source, document_type=tree.kind)
    plan = assert_no_writes(plan_ownership, folder_ids=[tree.source.pk], destination_folder_id=tree.target.pk,
                           client_policy='inherit')
    DocumentFolder.objects.filter(pk=tree.source.pk).update(parent=tree.target)
    before = ownership_state()

    response = admin_client.patch(reverse('update-document-folder', args=[tree.source.pk]),
                                  {'parent_id': tree.target.pk, 'client_policy': 'inherit',
                                   'expected_plan_hash': plan['plan_hash']}, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'stale_move_plan'
    assert ownership_state() == before
    document.refresh_from_db()
    assert document.client_user_id is None
