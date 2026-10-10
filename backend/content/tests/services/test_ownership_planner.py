"""Ownership policy matrices, protected records, exposure and stable previews."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from accounts.models import DeliveryDocumentLink, Project, ProjectContract

from content.models import (
    Document,
    DocumentFolder,
    DocumentType,
    ProjectRetentionContext,
)
from content.services.document_ownership_planner import (
    CLIENT_POLICIES,
    OwnershipPlanError,
    apply_ownership_plan,
    plan_ownership,
)
from content.tests.mcp_parity import assert_no_writes, ownership_state

pytestmark = pytest.mark.django_db


@pytest.fixture
def owners(make_client_profile, django_user_model):
    django_user_model.objects.create_user(username='profile-id-gap')
    owner = make_client_profile(company='Destination client')
    foreign = make_client_profile(company='Original client')
    project = Project.objects.create(name='Destination project', client=owner.user)
    other_project = Project.objects.create(name='Same client other project', client=owner.user)
    foreign_project = Project.objects.create(name='Foreign project', client=foreign.user)
    destination = DocumentFolder.objects.create(name='Ownership destination', client_user=owner.user, project=project)
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    return SimpleNamespace(owner=owner, foreign=foreign, project=project, other_project=other_project,
                           foreign_project=foreign_project, destination=destination, kind=kind)


def _matrix_records(context, factory):
    return {
        'unowned': factory('unowned', None, None),
        'client_only': factory('client only', context.owner.user, None),
        'same_project': factory('same project', context.owner.user, context.project),
        'other_project': factory('other project', context.owner.user, context.other_project),
        'foreign_client': factory('foreign client', context.foreign.user, None),
        'foreign_project': factory('foreign project', context.foreign.user, context.foreign_project),
    }


def _expectations(context, records, policy):
    target = (context.owner.pk, context.project.pk)
    before = {'unowned': (None, None), 'client_only': (context.owner.pk, None), 'same_project': target,
              'other_project': (context.owner.pk, context.other_project.pk),
              'foreign_client': (context.foreign.pk, None), 'foreign_project': (context.foreign.pk, context.foreign_project.pk)}
    owners_after = dict(before) if policy == 'keep' else {**before, 'unowned': target, 'client_only': target}
    conflicts = {}
    if policy == 'inherit':
        owners_after = dict.fromkeys(before, target)
    else:
        code = 'ownership_conflict_keep' if policy == 'keep' else 'ownership_conflict'
        conflicts = dict.fromkeys(('other_project', 'foreign_client', 'foreign_project'), code)
    return {record.pk: (*owners_after[name], conflicts.get(name)) for name, record in records.items()}


def _matrix_after(plan, records):
    ids = {obj.pk for obj in records.values()}
    return {row['id']: (row['after']['client_profile_id'], row['after']['project_id'], row['conflict'])
            for row in plan['rows'] if row['id'] in ids}


@pytest.fixture
def matrix_resource(owners, request):
    source = DocumentFolder.objects.create(name='Folder matrix source')
    factories = {
        'document': lambda title, user, project: Document.objects.create(
            title=title, folder=source, document_type=owners.kind, client_user=user, project=project,
        ),
        'folder': lambda name, user, project: DocumentFolder.objects.create(
            name=name, parent=source, client_user=user, project=project,
        ),
    }
    records = _matrix_records(owners, factories[request.param])
    scope = {'document': {'document_ids': [obj.pk for obj in records.values()]}, 'folder': {'folder_ids': [source.pk]}}[request.param]
    return SimpleNamespace(source=source, records=records, scope=scope)


@pytest.mark.parametrize('matrix_resource', ['document', 'folder'], indirect=True)
@pytest.mark.parametrize('policy', CLIENT_POLICIES)
def test_ownership_policy_matrix(owners, matrix_resource, policy):
    records = matrix_resource.records

    plan = assert_no_writes(plan_ownership, **matrix_resource.scope,
                           destination_folder_id=owners.destination.pk, client_policy=policy)

    assert _matrix_after(plan, records) == _expectations(owners, records, policy)
    assert plan['can_apply'] == (policy == 'inherit')
    assert plan['destination_owner'] == {'client_profile_id': owners.owner.pk, 'project_id': owners.project.pk}
    assert owners.owner.pk != owners.owner.user_id
    matrix_resource.source.refresh_from_db()
    assert matrix_resource.source.parent_id is None


@pytest.mark.parametrize('policy', CLIENT_POLICIES)
def test_unowned_destination_preserves_ownership(owners, policy, superuser):
    destination = DocumentFolder.objects.create(name='Unowned destination')
    source = DocumentFolder.objects.create(name='Owned source', client_user=owners.owner.user, project=owners.project)
    document = Document.objects.create(title='Owned visible', folder=source, document_type=owners.kind,
                                       client_user=owners.owner.user, project=owners.project, is_client_visible=True)
    args = {'folder_ids': [source.pk], 'destination_folder_id': destination.pk, 'client_policy': policy}

    plan = assert_no_writes(plan_ownership, **args)
    applied = apply_ownership_plan(args, actor=superuser, expected_plan_hash=plan['plan_hash'])

    source.refresh_from_db()
    document.refresh_from_db()
    assert applied == plan
    assert (source.parent_id, source.client_user_id, source.project_id) == (destination.pk, owners.owner.user_id, owners.project.pk)
    assert (document.folder_id, document.client_user_id, document.project_id, document.is_client_visible) == (source.pk, owners.owner.user_id, owners.project.pk, True)


@pytest.mark.parametrize(('portal_policy', 'can_apply', 'visible', 'audience'), [
    ('abort', False, True, 'owner'), ('allow', True, True, 'owner'), ('hide_new_exposure', True, False, None),
])
def test_new_portal_audience_policy(owners, portal_policy, can_apply, visible, audience, superuser):
    source = DocumentFolder.objects.create(name='Exposure source')
    active = Document.objects.create(title='Active exposure', folder=source, document_type=owners.kind, is_client_visible=True)
    archived = Document.objects.create(title='Latent exposure', folder=source, document_type=owners.kind, is_client_visible=True, is_archived=True)
    args = {'folder_ids': [source.pk], 'destination_folder_id': owners.destination.pk,
            'client_policy': 'inherit', 'portal_policy': portal_policy}

    plan = assert_no_writes(plan_ownership, **args)
    rows = {row['id']: row for row in plan['rows'] if row['resource_type'] == 'document'}

    assert plan['can_apply'] is can_apply
    assert rows[active.pk]['after']['portal_audience'] == {'owner': owners.owner.user_id, None: None}[audience]
    assert rows[active.pk]['after']['is_client_visible'] is visible
    assert rows[archived.pk]['after']['is_client_visible'] is visible
    assert rows[archived.pk]['latent_exposure'] is True
    assert rows[archived.pk]['after']['portal_audience'] is None
    assert [warning['resource_id'] for warning in plan['warnings']] == [archived.pk]
    _apply_exposure(args, plan, superuser, archived, visible)


def _apply_exposure(args, plan, actor, archived, visible):
    if plan['can_apply']:
        apply_ownership_plan(args, actor=actor, expected_plan_hash=plan['plan_hash'])
        archived.refresh_from_db()
        assert archived.is_client_visible is visible
        assert archived.is_archived is True
    else:
        before = ownership_state()
        with pytest.raises(OwnershipPlanError) as rejected:
            apply_ownership_plan(args, actor=actor, expected_plan_hash=plan['plan_hash'])
        assert [row['code'] for row in rejected.value.details['blockers']] == ['portal_exposure', 'portal_exposure_latent']
        assert ownership_state() == before


@pytest.mark.parametrize(('portal_policy', 'visible'), [('allow', True), ('hide_new_exposure', False)])
def test_archived_document_policy_controls_restored_audience(owners, superuser, portal_policy, visible):
    from accounts.document_views import _visible_docs_qs

    source = DocumentFolder.objects.create(name='Archived history source')
    archived = Document.objects.create(
        title='Archived private history', folder=source, document_type=owners.kind,
        client_user=owners.foreign.user, is_client_visible=True, is_archived=True,
    )
    args = {
        'folder_ids': [source.pk], 'destination_folder_id': owners.destination.pk,
        'client_policy': 'inherit', 'portal_policy': portal_policy,
    }
    plan = assert_no_writes(plan_ownership, **args)

    applied = apply_ownership_plan(args, actor=superuser, expected_plan_hash=plan['plan_hash'])

    archived.refresh_from_db()
    assert applied == plan
    document_row = next(row for row in plan['rows'] if row['resource_type'] == 'document')
    assert document_row['latent_exposure'] is True
    assert (archived.client_user_id, archived.project_id) == (owners.owner.user_id, owners.project.pk)
    assert (archived.is_archived, archived.is_client_visible) == (True, visible)
    assert not _visible_docs_qs(SimpleNamespace(user=owners.owner.user)).filter(pk=archived.pk).exists()
    Document.objects.filter(pk=archived.pk).update(is_archived=False)
    assert _visible_docs_qs(SimpleNamespace(user=owners.owner.user)).filter(pk=archived.pk).exists() is visible


@pytest.mark.parametrize('policy', CLIENT_POLICIES)
def test_pinned_subtree_preserves_ownership(initialized_contract_mirrors, owners, policy, superuser):
    source = DocumentFolder.objects.create(name='Pinned ancestor')
    pinned = initialized_contract_mirrors.mirror_folder
    pinned.parent = source
    pinned.save(update_fields=['parent'])
    child = DocumentFolder.objects.create(name='Pinned child', parent=pinned)
    document = Document.objects.create(title='Pinned descendant', folder=child, document_type=owners.kind, is_client_visible=True)
    args = {'folder_ids': [source.pk], 'destination_folder_id': owners.destination.pk, 'client_policy': policy}

    plan = assert_no_writes(plan_ownership, **args)
    apply_ownership_plan(args, actor=superuser, expected_plan_hash=plan['plan_hash'])

    pinned_rows = [row for row in plan['rows'] if row['id'] != source.pk or row['resource_type'] != 'folder']
    assert {row['status'] for row in pinned_rows} == {'pinned'}
    assert {(row['after']['client_profile_id'], row['after']['project_id']) for row in pinned_rows} == {(None, None)}
    source.refresh_from_db()
    document.refresh_from_db()
    assert source.parent_id == owners.destination.pk
    assert (document.client_user_id, document.project_id, document.is_client_visible) == (None, None, True)
    assert not Document.objects.filter(folder_id__in=[pinned.pk, child.pk], client_user__isnull=False).exists()


@pytest.mark.parametrize('policy', CLIENT_POLICIES)
def test_frozen_records_refuse_reassignment(owners, policy, superuser):
    source = DocumentFolder.objects.create(name='Frozen source')
    retention = ProjectRetentionContext.objects.create(client=owners.foreign.user, original_project_id=99991,
                                                       project_name='Retained project', created_by=superuser)
    retained_folder = DocumentFolder.objects.create(name='Retained child', parent=source, client_user=owners.foreign.user, retention_context=retention)
    account_kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Account'})
    Document.objects.create(title='Issued account', folder=source, document_type=account_kind,
                            client_user=owners.foreign.user, commercial_status='issued')
    Document.objects.create(title='Retained document', folder=source, document_type=owners.kind,
                            client_user=owners.foreign.user, retention_context=retention)
    Document.objects.create(title='Generated document', folder=source, document_type=owners.kind,
                            client_user=owners.foreign.user, generated_file='documents/generated/frozen.pdf')
    linked = Document.objects.create(title='Delivery source', folder=source, document_type=owners.kind,
                                     client_user=owners.foreign.user, project=owners.foreign_project)
    DeliveryDocumentLink.objects.create(project=owners.foreign_project, document=linked, level='project', created_by=superuser)
    contractual = Document.objects.create(title='Contract source', folder=source, document_type=owners.kind,
                                          client_user=owners.foreign.user, project=owners.foreign_project)
    ProjectContract.objects.create(project=owners.foreign_project, document=contractual, key='frozen', title='Contract')
    args = {'folder_ids': [source.pk], 'destination_folder_id': owners.destination.pk, 'client_policy': policy}
    before = ownership_state()

    plan = assert_no_writes(plan_ownership, **args)
    with pytest.raises(OwnershipPlanError) as rejected:
        apply_ownership_plan(args, actor=superuser)

    expected_code = {'inherit': 'ownership_frozen', 'keep': 'ownership_conflict_keep',
                     'abort_on_conflict': 'ownership_conflict'}[policy]
    assert {row['code'] for row in plan['blockers']} == {expected_code}
    assert len(plan['blockers']) == 6
    assert rejected.value.details['blockers'] == plan['blockers']
    assert ownership_state() == before
    retained_folder.refresh_from_db()
    assert retained_folder.client_user_id == owners.foreign.user_id


def test_document_decisions_resolve_subtree_conflicts(owners, superuser):
    source = DocumentFolder.objects.create(name='Decision source')
    foreign_folder = DocumentFolder.objects.create(name='Foreign destination', client_user=owners.foreign.user)
    redirected = Document.objects.create(title='Redirected', folder=source, document_type=owners.kind, client_user=owners.foreign.user)
    adopted = Document.objects.create(title='Explicitly adopted', folder=source, document_type=owners.kind, client_user=owners.foreign.user)
    inherited = Document.objects.create(title='Inherited', folder=source, document_type=owners.kind)
    args = {'folder_ids': [source.pk], 'destination_folder_id': owners.destination.pk, 'client_policy': 'abort_on_conflict',
            'document_decisions': [{'document_id': redirected.pk, 'action': 'move', 'destination_folder_id': foreign_folder.pk},
                                   {'document_id': adopted.pk, 'action': 'inherit'}]}

    plan = assert_no_writes(plan_ownership, **args)
    applied = apply_ownership_plan(args, actor=superuser, expected_plan_hash=plan['plan_hash'])

    assert applied == plan
    assert list(Document.objects.filter(pk__in=[redirected.pk, adopted.pk, inherited.pk]).order_by('pk').values_list('folder_id', 'client_user_id', 'project_id')) == [
        (foreign_folder.pk, owners.foreign.user_id, None),
        (source.pk, owners.owner.user_id, owners.project.pk),
        (source.pk, owners.owner.user_id, owners.project.pk),
    ]


def test_hash_detects_ownership_changes(owners, superuser):
    document = Document.objects.create(title='Hash document', document_type=owners.kind)
    args = {'document_ids': [document.pk], 'destination_folder_id': owners.destination.pk, 'client_policy': 'inherit'}
    original = assert_no_writes(plan_ownership, **args)
    locked = assert_no_writes(plan_ownership, **args, lock=True)
    Document.objects.filter(pk=document.pk).update(updated_at=datetime(2000, 1, 1, tzinfo=UTC))
    unchanged = assert_no_writes(plan_ownership, **args)
    DocumentFolder.objects.filter(pk=owners.destination.pk).update(client_user=owners.foreign.user, project=None)
    changed = assert_no_writes(plan_ownership, **args)
    before_apply = ownership_state()

    with pytest.raises(OwnershipPlanError) as rejected:
        apply_ownership_plan(args, actor=superuser, expected_plan_hash=original['plan_hash'])

    assert original['plan_hash'] == unchanged['plan_hash']
    assert original['plan_hash'] == locked['plan_hash']
    assert original['plan_hash'] != changed['plan_hash']
    assert rejected.value.code == 'stale_move_plan'
    assert rejected.value.status_code == 409
    assert ownership_state() == before_apply


@pytest.mark.parametrize('project_kind', ['existing', 'new'])
def test_destination_owner_override_plans_a_manual_root(owners, project_kind):
    source = DocumentFolder.objects.create(name='Future project root')
    visible = Document.objects.create(title='Future portal exposure', folder=source, is_client_visible=True)
    project_id = {'existing': owners.project.pk, 'new': 'new_project'}[project_kind]
    args = {'folder_ids': [source.pk], 'destination_folder_id': None, 'client_policy': 'abort_on_conflict',
            'destination_owner': {'client_user_id': owners.owner.user_id, 'project_id': project_id}}

    blocked = assert_no_writes(plan_ownership, **args)
    hidden = assert_no_writes(plan_ownership, **args, portal_policy='hide_new_exposure')

    document = next(row for row in hidden['rows'] if row['resource_type'] == 'document')
    assert blocked['blockers'][0]['code'] == 'portal_exposure'
    assert hidden['can_apply'] is True
    assert hidden['destination_owner'] == {'client_profile_id': owners.owner.pk, 'project_id': project_id}
    assert (document['after']['project_id'], document['after']['client_user_id']) == (project_id, owners.owner.user_id)
    assert document['after']['is_client_visible'] is False
    visible.refresh_from_db()
    assert visible.project_id is None
    assert visible.is_client_visible is True


def test_destination_owner_override_replaces_the_folder_owner(owners):
    document = Document.objects.create(title='Future destination ownership', document_type=owners.kind)
    target = {'client_user_id': owners.foreign.user_id, 'project_id': owners.foreign_project.pk}
    args = {'document_ids': [document.pk], 'destination_folder_id': owners.destination.pk, 'client_policy': 'inherit'}

    plan = assert_no_writes(plan_ownership, **args, destination_owner=target)
    normalized = assert_no_writes(plan_ownership, **args, destination_owner={**target, 'client_user_id': str(target['client_user_id'])})

    assert plan == normalized
    assert plan['can_apply'] is True
    assert plan['rows'][0]['after']['client_user_id'] == owners.foreign.user_id
    assert plan['rows'][0]['after']['project_id'] == owners.foreign_project.pk
    assert plan['rows'][0]['after']['folder_or_parent_id'] == owners.destination.pk
    owners.destination.refresh_from_db()
    assert owners.destination.client_user_id == owners.owner.user_id
