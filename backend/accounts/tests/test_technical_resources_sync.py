"""Tests for proposal resource synchronization without client-review mutation."""

from decimal import Decimal

import pytest
from content.models import BusinessProposal, ProposalSection
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from accounts.models import (
    DataModelEntity,
    Deliverable,
    Project,
    ProjectPhase,
    Requirement,
    UserProfile,
)
from accounts.services.technical_resources_sync import (
    compute_sync_diff,
    sync_technical_resources_for_deliverable,
    sync_technical_resources_for_project,
)

User = get_user_model()

# Proposal synchronization preserves commercial phases, resources and data models.
# Client-review guides are authored independently.




@pytest.mark.django_db
def test_sync_returns_error_without_linked_proposal():
    """Reject technical synchronization when the project has no linked proposal."""
    admin = User.objects.create_user(username='a2@sync.com', email='a2@sync.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username='c2@sync.com', email='c2@sync.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name='P2', client=client)

    result = sync_technical_resources_for_project(project, admin)
    assert result['ok'] is False
    assert result['error'] == 'no_linked_proposal'


# =========================================================================
# Helpers shared by data model entity sync tests
# =========================================================================


def _make_sync_setup(admin_email, client_email, project_name, entities=None):
    """Create the minimal DB objects required to run a sync with data model entities.

    The content_json always includes a minimal epic so the sync creates at least one
    synced_deliverable — entity sync only runs against deliverables derived from epics.
    """
    admin = User.objects.create_user(username=admin_email, email=admin_email, password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username=client_email, email=client_email, password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)

    project = Project.objects.create(name=project_name, client=client)
    bp = BusinessProposal.objects.create(
        title='BP', client_name='C', total_investment=Decimal('1'),
        hosting_percent=30, status='accepted', client=project.client.profile,
    )
    d = Deliverable.objects.create(
        project=project, title='Prop',
        category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=client,
    )
    bp.deliverable = d
    bp.save(update_fields=['deliverable_id'])

    # Always include a minimal epic so synced_deliverables is populated.
    # Entity sync only runs against deliverables created from epics.
    content_json = {
        'epics': [
            {
                'epicKey': 'epic-test',
                'title': 'Test Epic',
                'requirements': [
                    {'flowKey': 'flow-test', 'title': 'Test Req', 'description': ''},
                ],
            },
        ],
    }
    if entities is not None:
        content_json['dataModel'] = {'entities': entities}

    ProposalSection.objects.create(
        proposal=bp,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        title='Técnico',
        order=1,
        content_json=content_json,
    )

    return project, admin, d


# =========================================================================
# 1C — Data model entity sync tests
# =========================================================================


@pytest.mark.django_db
def test_sync_creates_data_model_entities_from_proposal():
    """Persist proposal data-model entities on the synchronized project deliverables."""
    project, admin, _ = _make_sync_setup(
        'a3@sync.com', 'c3@sync.com', 'P3',
        entities=[
            {'name': 'User', 'description': 'A user', 'keyFields': 'id, email'},
            {'name': 'Order', 'description': 'An order', 'keyFields': 'id'},
        ],
    )

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert result['entities_created'] == 2
    # Entities are linked to the deliverable created from the epic, not the proposal deliverable
    assert DataModelEntity.objects.filter(
        deliverable__project=project, name='User',
    ).exists()
    assert DataModelEntity.objects.filter(
        deliverable__project=project, name='Order',
    ).exists()


@pytest.mark.django_db
def test_sync_sets_synced_from_proposal_flag_on_entities():
    """Record proposal provenance on synchronized data-model entities."""
    project, admin, _ = _make_sync_setup(
        'a4@sync.com', 'c4@sync.com', 'P4',
        entities=[{'name': 'Product', 'keyFields': 'id, sku'}],
    )

    sync_technical_resources_for_project(project, admin)

    entity = DataModelEntity.objects.get(
        deliverable__project=project, source_entity_name='Product',
    )
    assert entity.synced_from_proposal is True


@pytest.mark.django_db
def test_sync_is_idempotent_on_second_run_with_same_entities():
    """Preserve one entity when the same proposal is synchronized twice."""
    project, admin, _ = _make_sync_setup(
        'a5@sync.com', 'c5@sync.com', 'P5',
        entities=[{'name': 'Invoice', 'description': 'v1', 'keyFields': 'id'}],
    )
    sync_technical_resources_for_project(project, admin)

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    # No new entity created on second run (idempotent)
    assert DataModelEntity.objects.filter(
        deliverable__project=project, source_entity_name='Invoice',
    ).count() == 1


@pytest.mark.django_db
def test_sync_updates_entity_when_description_changes():
    """Persist an updated description on an existing synchronized entity."""
    project, admin, prop_deliverable = _make_sync_setup(
        'a6@sync.com', 'c6@sync.com', 'P6',
        entities=[{'name': 'Cart', 'description': 'original', 'keyFields': ''}],
    )
    sync_technical_resources_for_project(project, admin)

    # Change the proposal section's content_json in-place (simulate updated proposal)
    section = ProposalSection.objects.get(
        proposal__deliverable=prop_deliverable,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['dataModel'] = {'entities': [
        {'name': 'Cart', 'description': 'updated description', 'keyFields': ''},
    ]}
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert result['entities_updated'] == 1
    entity = DataModelEntity.objects.get(
        deliverable__project=project, source_entity_name='Cart',
    )
    assert entity.description == 'updated description'


@pytest.mark.django_db
def test_sync_archives_removed_entities_when_delete_removed_is_true():
    """Archive a removed entity when removal reconciliation is enabled."""
    project, admin, prop_deliverable = _make_sync_setup(
        'a7@sync.com', 'c7@sync.com', 'P7',
        entities=[
            {'name': 'Keep', 'description': '', 'keyFields': ''},
            {'name': 'Remove', 'description': '', 'keyFields': ''},
        ],
    )
    sync_technical_resources_for_project(project, admin, delete_removed=False)

    # Now remove 'Remove' from the proposal
    section = ProposalSection.objects.get(
        proposal__deliverable=prop_deliverable,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['dataModel'] = {'entities': [
        {'name': 'Keep', 'description': '', 'keyFields': ''},
    ]}
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin, delete_removed=True)

    assert result['ok'] is True
    assert result['entities_deleted'] == 1
    removed = DataModelEntity.objects.get(
        deliverable__project=project, source_entity_name='Remove',
    )
    assert removed.is_archived is True


@pytest.mark.django_db
def test_sync_does_not_archive_entities_when_delete_removed_is_false():
    """Keep a removed entity active when removal reconciliation is disabled."""
    project, admin, prop_deliverable = _make_sync_setup(
        'a8@sync.com', 'c8@sync.com', 'P8',
        entities=[
            {'name': 'Keep2', 'description': '', 'keyFields': ''},
            {'name': 'Remove2', 'description': '', 'keyFields': ''},
        ],
    )
    sync_technical_resources_for_project(project, admin, delete_removed=False)

    section = ProposalSection.objects.get(
        proposal__deliverable=prop_deliverable,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['dataModel'] = {'entities': [
        {'name': 'Keep2', 'description': '', 'keyFields': ''},
    ]}
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin, delete_removed=False)

    assert result['ok'] is True
    assert result['entities_deleted'] == 0
    removed = DataModelEntity.objects.get(
        deliverable__project=project, source_entity_name='Remove2',
    )
    assert removed.is_archived is False


@pytest.mark.django_db
def test_sync_handles_empty_entities_list_without_error():
    """Complete synchronization without creating entities from an empty entity list."""
    project, admin, _ = _make_sync_setup(
        'a9@sync.com', 'c9@sync.com', 'P9',
        entities=[],
    )

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert result['entities_created'] == 0


@pytest.mark.django_db
def test_sync_handles_missing_data_model_key_without_error():
    """Complete synchronization without creating entities when the data model is absent."""
    project, admin, _ = _make_sync_setup(
        'a10@sync.com', 'c10@sync.com', 'P10',
        entities=None,  # content_json has no 'dataModel' key
    )

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert result['entities_created'] == 0


# =========================================================================
# 1C — compute_sync_diff tests for data model entities
# =========================================================================


@pytest.mark.django_db
def test_compute_sync_diff_reports_entity_to_create():
    """Report a new proposal entity in the planned creation list."""
    admin = User.objects.create_user(username='d1@sync.com', email='d1@sync.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username='dc1@sync.com', email='dc1@sync.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name='Diff1', client=client)

    new_json = {'dataModel': {'entities': [{'name': 'NewEntity', 'description': 'x'}]}}
    diff = compute_sync_diff(project, new_json)

    assert any(e['name'] == 'NewEntity' for e in diff['data_model_entities']['to_create'])
    assert diff['data_model_entities']['to_update'] == []
    assert diff['data_model_entities']['to_delete'] == []


@pytest.mark.django_db
def test_compute_sync_diff_reports_entity_to_update_when_description_changed():
    """Report the changed description of an existing entity in the planned update list."""
    admin = User.objects.create_user(username='d2@sync.com', email='d2@sync.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username='dc2@sync.com', email='dc2@sync.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name='Diff2', client=client)

    d = Deliverable.objects.create(
        project=project, title='D',
        category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=admin,
    )
    DataModelEntity.objects.create(
        deliverable=d,
        name='Existing',
        description='old',
        key_fields='',
        source_entity_name='Existing',
    )

    new_json = {'dataModel': {'entities': [{'name': 'Existing', 'description': 'new'}]}}
    diff = compute_sync_diff(project, new_json)

    assert diff['data_model_entities']['to_create'] == []
    updates = diff['data_model_entities']['to_update']
    assert len(updates) == 1
    assert updates[0]['name'] == 'Existing'
    assert 'description' in updates[0]['changed_fields']


@pytest.mark.django_db
def test_compute_sync_diff_reports_entity_to_delete_when_removed():
    """Report an existing entity in the planned deletion list when the proposal removes it."""
    admin = User.objects.create_user(username='d3@sync.com', email='d3@sync.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username='dc3@sync.com', email='dc3@sync.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name='Diff3', client=client)

    d = Deliverable.objects.create(
        project=project, title='D',
        category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=admin,
    )
    DataModelEntity.objects.create(
        deliverable=d,
        name='GoneEntity',
        source_entity_name='GoneEntity',
    )

    new_json = {'dataModel': {'entities': []}}
    diff = compute_sync_diff(project, new_json)

    assert diff['data_model_entities']['to_create'] == []
    assert diff['data_model_entities']['to_update'] == []
    assert any(e['name'] == 'GoneEntity' for e in diff['data_model_entities']['to_delete'])


# =========================================================================
# compute_sync_diff — epic and requirement diff
# =========================================================================


def _make_project_with_deliverable(prefix):
    admin = User.objects.create_user(username=f'{prefix}adm@sync.com', email=f'{prefix}adm@sync.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username=f'{prefix}cli@sync.com', email=f'{prefix}cli@sync.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name=f'{prefix}P', client=client)
    return project, admin, client


@pytest.mark.django_db
def test_compute_sync_diff_reports_epic_to_create_when_no_deliverable_exists():
    """Epics not in DB appear in to_create."""
    project, _, _ = _make_project_with_deliverable('e1')
    new_json = {'epics': [{'epicKey': 'epic-new', 'title': 'New Epic', 'requirements': []}]}

    diff = compute_sync_diff(project, new_json)

    assert any(e['epicKey'] == 'epic-new' for e in diff['epics']['to_create'])
    assert diff['epics']['to_update'] == []
    assert diff['epics']['to_delete'] == []


@pytest.mark.django_db
def test_compute_sync_diff_reports_epic_to_update_when_title_changed():
    """Existing deliverable with changed title appears in to_update."""
    project, admin, client = _make_project_with_deliverable('e2')
    Deliverable.objects.create(
        project=project, title='Old Title', source_epic_key='epic-x',
        category=Deliverable.CATEGORY_DOCUMENTS, file=None, uploaded_by=admin,
    )
    new_json = {'epics': [{'epicKey': 'epic-x', 'title': 'New Title', 'requirements': []}]}

    diff = compute_sync_diff(project, new_json)

    assert diff['epics']['to_create'] == []
    assert any(e['epicKey'] == 'epic-x' for e in diff['epics']['to_update'])


@pytest.mark.django_db
def test_compute_sync_diff_reports_epics_to_delete_when_removed():
    """Deliverables in DB but absent from JSON appear in to_delete."""
    project, admin, client = _make_project_with_deliverable('e3')
    Deliverable.objects.create(
        project=project, title='Stale', source_epic_key='epic-stale',
        category=Deliverable.CATEGORY_DOCUMENTS, file=None, uploaded_by=admin,
    )
    new_json = {'epics': []}

    diff = compute_sync_diff(project, new_json)

    assert any(e['epicKey'] == 'epic-stale' for e in diff['epics']['to_delete'])








@pytest.mark.django_db
def test_compute_sync_diff_skips_non_dict_epic():
    """Non-dict items in the epics list are silently skipped."""
    project, _, _ = _make_project_with_deliverable('e7')
    new_json = {'epics': ['not-a-dict', 42, {'epicKey': 'ok-key', 'title': 'OK', 'requirements': []}]}

    diff = compute_sync_diff(project, new_json)

    assert len(diff['epics']['to_create']) == 1
    assert diff['epics']['to_create'][0]['epicKey'] == 'ok-key'


@pytest.mark.django_db
def test_compute_sync_diff_assigns_synthetic_key_to_keyless_epic_with_reqs():
    """Epic without epicKey but with requirements gets a synthetic _sync_epic_N key."""
    project, _, _ = _make_project_with_deliverable('e8')
    new_json = {'epics': [
        {'title': 'No Key', 'requirements': [
            {'flowKey': 'flow-nk', 'title': 'A Req'},
        ]},
    ]}

    diff = compute_sync_diff(project, new_json)

    # Should create an epic with synthetic key (not to_delete or empty)
    created_keys = [e['epicKey'] for e in diff['epics']['to_create']]
    assert any(k.startswith('_sync_epic_') for k in created_keys)


@pytest.mark.django_db
def test_compute_sync_diff_entity_key_fields_change_reported():
    """When only key_fields changes on an entity, it appears in to_update."""
    project, admin, _ = _make_project_with_deliverable('e9')
    d = Deliverable.objects.create(
        project=project, title='D', category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=admin,
    )
    DataModelEntity.objects.create(
        deliverable=d, name='E', description='', key_fields='id',
        source_entity_name='E',
    )
    new_json = {'dataModel': {'entities': [{'name': 'E', 'description': '', 'keyFields': 'id, name'}]}}

    diff = compute_sync_diff(project, new_json)

    updates = diff['data_model_entities']['to_update']
    assert len(updates) == 1
    assert 'key_fields' in updates[0]['changed_fields']


# =========================================================================
# _sync_technical_resources_core — update and delete paths
# =========================================================================


def _make_full_sync_setup(prefix, epics=None, entities=None):
    """Create full project+BP+ProposalSection fixture for sync tests."""
    admin = User.objects.create_user(username=f'{prefix}adm@s.com', email=f'{prefix}adm@s.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username=f'{prefix}cli@s.com', email=f'{prefix}cli@s.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name=f'{prefix}P', client=client)
    bp = BusinessProposal.objects.create(
        title='BP', client_name='C', total_investment=Decimal('1'),
        hosting_percent=30, status='accepted', client=project.client.profile,
    )
    prop_d = Deliverable.objects.create(
        project=project, title='Prop', category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=client,
    )
    bp.deliverable = prop_d
    bp.save(update_fields=['deliverable_id'])
    content_json = {'epics': epics or []}
    if entities is not None:
        content_json['dataModel'] = {'entities': entities}
    ProposalSection.objects.create(
        proposal=bp, section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        title='Técnico', order=1, content_json=content_json,
    )
    return project, admin, bp, prop_d


@pytest.mark.django_db
def test_syncing_one_proposal_preserves_a_neighbor_resource_with_the_same_epic_key():
    """Fails if syncing a phase overwrites or archives the other proposal's equally named technical resource."""
    project, admin, first, first_package = _make_full_sync_setup('owned-scope-first', epics=[
        {'epicKey': 'shared-epic', 'title': 'First scope', 'requirements': []},
    ])
    second = BusinessProposal.objects.create(
        title='Second phase', client_name='C', total_investment=Decimal('1'),
        hosting_percent=30, status='accepted', client=project.client.profile,
    )
    second_package = Deliverable.objects.create(
        project=project, title='Second package', category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=admin,
    )
    second.deliverable = second_package
    second.save(update_fields=['deliverable'])
    ProjectPhase.objects.create(project=project, business_proposal=first, order=1)
    ProjectPhase.objects.create(project=project, business_proposal=second, order=2)
    ProposalSection.objects.create(
        proposal=second, section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        title='Second technical scope', order=1,
        content_json={'epics': [{'epicKey': 'shared-epic', 'title': 'Second scope', 'requirements': []}]},
    )
    sync_technical_resources_for_project(project, admin)
    second_resource = Deliverable.objects.get(project=project, source_proposal=second, source_epic_key='shared-epic')
    second_resource.file.save('second-scope.txt', ContentFile(b'keep this file'), save=True)
    second_resource.is_archived = False
    second_resource.save(update_fields=['is_archived'])
    first_section = ProposalSection.objects.get(proposal=first, section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT)
    first_section.content_json['epics'][0]['title'] = 'First scope revised'
    first_section.save(update_fields=['content_json'])

    sync_technical_resources_for_deliverable(first_package, admin, delete_removed=True)

    first_resource = Deliverable.objects.get(project=project, source_proposal=first, source_epic_key='shared-epic')
    second_resource.refresh_from_db()
    assert first_resource.title == 'First scope revised'
    assert second_resource.title == 'Second scope'
    assert second_resource.file.name.endswith('second-scope.txt')
    assert second_resource.is_archived is False


@pytest.mark.django_db
def test_sync_updates_deliverable_title_when_changed():
    """When epic title changes on second sync, deliverable title is updated."""
    project, admin, _, _ = _make_full_sync_setup('u1', epics=[
        {'epicKey': 'eup1', 'title': 'Original', 'requirements': []},
    ])
    sync_technical_resources_for_project(project, admin)

    # Update epic title in the section
    section = ProposalSection.objects.get(
        proposal__deliverable__project=project,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['epics'][0]['title'] = 'Updated Title'
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['deliverables_updated'] == 1
    d = Deliverable.objects.get(project=project, source_epic_key='eup1')
    assert d.title == 'Updated Title'






@pytest.mark.django_db
def test_sync_archives_removed_deliverables_when_delete_removed_true():
    """With delete_removed=True, deliverables absent from JSON are archived."""
    project, admin, _, _ = _make_full_sync_setup('u4', epics=[
        {'epicKey': 'eup4', 'title': 'Keep', 'requirements': []},
        {'epicKey': 'eup4-gone', 'title': 'Gone', 'requirements': []},
    ])
    sync_technical_resources_for_project(project, admin, delete_removed=False)

    # Remove 'Gone' from the section
    section = ProposalSection.objects.get(
        proposal__deliverable__project=project,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['epics'] = [{'epicKey': 'eup4', 'title': 'Keep', 'requirements': []}]
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin, delete_removed=True)

    assert result['deliverables_deleted'] >= 1
    gone = Deliverable.objects.get(project=project, source_epic_key='eup4-gone')
    assert gone.is_archived is True






# =========================================================================
# sync_technical_resources_for_deliverable
# =========================================================================


@pytest.mark.django_db
def test_sync_for_deliverable_returns_ok_when_bp_exists():
    """sync_technical_resources_for_deliverable succeeds when deliverable has a BP."""
    project, admin, bp, prop_d = _make_full_sync_setup('del1', epics=[
        {'epicKey': 'del-epic', 'title': 'E', 'requirements': []},
    ])

    result = sync_technical_resources_for_deliverable(prop_d, admin)

    assert result['ok'] is True


@pytest.mark.django_db
def test_sync_for_deliverable_returns_error_when_no_bp():
    """sync_technical_resources_for_deliverable returns error when no BusinessProposal."""
    admin = User.objects.create_user(username='del2adm@s.com', email='del2adm@s.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username='del2cli@s.com', email='del2cli@s.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name='del2P', client=client)
    plain_d = Deliverable.objects.create(
        project=project, title='No BP', category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=admin,
    )

    result = sync_technical_resources_for_deliverable(plain_d, admin)

    assert result['ok'] is False
    assert result['error'] == 'no_business_proposal'


# =========================================================================
# compute_sync_diff — branch coverage gaps
# =========================================================================




@pytest.mark.django_db
def test_compute_sync_diff_skips_epic_with_no_key_and_no_reqs():
    """An epic with no epicKey and no requirements is silently skipped."""
    project, admin, _, _ = _make_full_sync_setup('diff2', epics=[
        {'title': 'No key, no reqs', 'requirements': []},
    ])
    result = sync_technical_resources_for_project(project, admin)
    assert result['ok'] is True
    assert result['deliverables_created'] == 0


@pytest.mark.django_db
def test_compute_sync_diff_detects_description_change_in_deliverable():
    """compute_sync_diff lists a deliverable in to_update when description changes."""
    from accounts.services.technical_resources_sync import compute_sync_diff

    project, admin, _, _ = _make_full_sync_setup('diff3', epics=[
        {'epicKey': 'e-diff3', 'title': 'E', 'description': 'v1', 'requirements': []},
    ])
    sync_technical_resources_for_project(project, admin)

    new_json = {'epics': [{'epicKey': 'e-diff3', 'title': 'E', 'description': 'v2 changed', 'requirements': []}]}
    diff = compute_sync_diff(project, new_json)
    assert any(e['epicKey'] == 'e-diff3' and 'description' in e['changed_fields'] for e in diff['epics']['to_update'])








@pytest.mark.django_db
def test_compute_sync_diff_skips_non_dict_entity():
    """A non-dict item in dataModel.entities is silently skipped."""
    from accounts.services.technical_resources_sync import compute_sync_diff

    project, admin, _, _ = _make_full_sync_setup('diff7', epics=[])
    new_json = {'epics': [], 'dataModel': {'entities': ['not-a-dict']}}
    diff = compute_sync_diff(project, new_json)
    assert diff['data_model_entities']['to_create'] == []


@pytest.mark.django_db
def test_compute_sync_diff_skips_entity_with_empty_name():
    """An entity with no name is silently skipped by compute_sync_diff."""
    from accounts.services.technical_resources_sync import compute_sync_diff

    project, admin, _, _ = _make_full_sync_setup('diff8', epics=[])
    new_json = {'epics': [], 'dataModel': {'entities': [{'name': '', 'description': 'no name'}]}}
    diff = compute_sync_diff(project, new_json)
    assert diff['data_model_entities']['to_create'] == []


# =========================================================================
# _sync_technical_resources_core — branch coverage gaps
# =========================================================================


@pytest.mark.django_db
def test_sync_returns_error_when_no_technical_section():
    """Returns ok=False when the proposal has no enabled TECHNICAL_DOCUMENT section."""
    admin = User.objects.create_user(username='ns1adm@s.com', email='ns1adm@s.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(username='ns1cli@s.com', email='ns1cli@s.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    project = Project.objects.create(name='ns1P', client=client)
    bp = BusinessProposal.objects.create(
        title='BP', client_name='C', total_investment=Decimal('1'),
        hosting_percent=30, status='accepted', client=project.client.profile,
    )
    prop_d = Deliverable.objects.create(
        project=project, title='Prop', category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=client,
    )
    bp.deliverable = prop_d
    bp.save(update_fields=['deliverable_id'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is False
    assert result['error'] == 'no_technical_section'


@pytest.mark.django_db
def test_sync_handles_epics_as_non_list_in_content_json():
    """When content_json.epics is not a list, sync treats it as empty and returns ok."""
    project, admin, _, _ = _make_full_sync_setup('ns2', epics=None)
    section = ProposalSection.objects.get(
        proposal__deliverable__project=project,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json = {'epics': 'not-a-list'}
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert result['deliverables_created'] == 0


@pytest.mark.django_db
def test_sync_skips_non_dict_epic_in_epics_list():
    """A non-dict item inside the epics array is silently skipped."""
    project, admin, _, _ = _make_full_sync_setup('ns3', epics=None)
    section = ProposalSection.objects.get(
        proposal__deliverable__project=project,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json = {'epics': ['bad-string', {'epicKey': 'e-ns3', 'title': 'Good', 'requirements': []}]}
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert result['deliverables_created'] == 1






@pytest.mark.django_db
def test_sync_updates_deliverable_description_when_changed():
    """When only description changes, deliverable is updated on second sync."""
    project, admin, _, _ = _make_full_sync_setup('ns6', epics=[
        {'epicKey': 'e-ns6', 'title': 'E', 'description': 'original desc', 'requirements': []},
    ])
    sync_technical_resources_for_project(project, admin)

    section = ProposalSection.objects.get(
        proposal__deliverable__project=project,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['epics'][0]['description'] = 'updated desc'
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['deliverables_updated'] == 1
    d = Deliverable.objects.get(project=project, source_epic_key='e-ns6')
    assert d.description == 'updated desc'


@pytest.mark.django_db
def test_sync_skips_non_dict_entity_in_entities_list():
    """A non-dict item in dataModel.entities is silently skipped during core sync."""
    project, admin, _, _ = _make_full_sync_setup('ns7',
        epics=[{'epicKey': 'e-ns7', 'title': 'E', 'requirements': []}],
        entities=['not-a-dict'],
    )
    result = sync_technical_resources_for_project(project, admin)
    assert result['ok'] is True
    assert result['entities_created'] == 0


@pytest.mark.django_db
def test_sync_skips_entity_with_empty_name_in_entities_list():
    """An entity with an empty name is silently skipped during core sync."""
    project, admin, _, _ = _make_full_sync_setup('ns8',
        epics=[{'epicKey': 'e-ns8', 'title': 'E', 'requirements': []}],
        entities=[{'name': '', 'description': 'nameless'}],
    )
    result = sync_technical_resources_for_project(project, admin)
    assert result['ok'] is True
    assert result['entities_created'] == 0


@pytest.mark.django_db
def test_sync_updates_entity_name_and_key_fields_when_changed():
    """When entity description or key_fields change, entities_updated increments."""
    project, admin, _, _ = _make_full_sync_setup('ns9',
        epics=[{'epicKey': 'e-ns9', 'title': 'E', 'requirements': []}],
        entities=[{'name': 'User', 'description': 'orig desc', 'keyFields': 'id'}],
    )
    sync_technical_resources_for_project(project, admin)

    section = ProposalSection.objects.get(
        proposal__deliverable__project=project,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
    )
    section.content_json['dataModel']['entities'][0]['description'] = 'new desc'
    section.content_json['dataModel']['entities'][0]['keyFields'] = 'id, email'
    section.save(update_fields=['content_json'])

    result = sync_technical_resources_for_project(project, admin)

    assert result['entities_updated'] >= 1


# =========================================================================
# Module-selection filtering — resources mirror the contracted selection
# =========================================================================


def _make_selection_setup(suffix, module_selected):
    """Project + proposal with one optional module and a module-linked epic."""
    admin = User.objects.create_user(
        username=f'a-{suffix}@sync.com', email=f'a-{suffix}@sync.com', password='p')
    UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    client = User.objects.create_user(
        username=f'c-{suffix}@sync.com', email=f'c-{suffix}@sync.com', password='p')
    UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)

    project = Project.objects.create(name=f'P-{suffix}', client=client)
    bp = BusinessProposal.objects.create(
        title='BP', client_name='C', total_investment=Decimal('1'),
        hosting_percent=30, status='accepted', client=project.client.profile,
    )
    d = Deliverable.objects.create(
        project=project, title='Prop', category=Deliverable.CATEGORY_DOCUMENTS,
        file=None, uploaded_by=client,
    )
    bp.deliverable = d
    bp.save(update_fields=['deliverable_id'])

    ProposalSection.objects.create(
        proposal=bp,
        section_type='functional_requirements',
        title='Requerimientos', order=0,
        content_json={
            'groups': [],
            'additionalModules': [{
                'id': 'pwa_module', 'title': 'PWA',
                'is_calculator_module': True, 'is_visible': True,
                'selected': module_selected, 'default_selected': module_selected,
                'price_percent': 40, 'items': [],
            }],
        },
    )
    ProposalSection.objects.create(
        proposal=bp,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        title='Técnico', order=1,
        content_json={
            'epics': [
                {
                    'epicKey': 'epic-base', 'title': 'Base',
                    'requirements': [{
                        'flowKey': 'flow-base', 'title': 'Req base', 'description': 'D',
                    }],
                },
                {
                    'epicKey': 'mod-pwa-module', 'title': 'Alcance ampliado: PWA',
                    'linked_module_ids': ['module-pwa_module'],
                    'requirements': [{
                        'flowKey': 'pwa-instalacion', 'title': 'Instalación PWA',
                        'description': 'D',
                        'linked_module_ids': ['module-pwa_module'],
                    }],
                },
            ],
        },
    )
    return admin, project






@pytest.mark.django_db
def test_technical_sync_creates_resources_without_client_review_cards():
    """Create selected technical resources without authoring client-review cards."""
    admin, project = _make_selection_setup('resource-only', module_selected=True)

    result = sync_technical_resources_for_project(project, admin)

    assert result['ok'] is True
    assert Deliverable.objects.filter(project=project, source_epic_key='mod-pwa-module').exists()
    assert not Requirement.objects.exists()
    assert ProjectPhase.objects.filter(project=project).count() == 1


@pytest.mark.django_db
def test_technical_sync_preserves_existing_delivery_approval():
    """Preserve the approval recorded on an existing client-review requirement."""
    from accounts.tests._delivery_fixtures import make_delivery_stage, make_requirement
    admin, project = _make_selection_setup('approved-review', module_selected=True)
    requirement = make_requirement(make_delivery_stage(project), title='Agreed guide')
    requirement.review_status = 'approved'
    requirement.save(update_fields=['review_status'])

    sync_technical_resources_for_project(project, admin, delete_removed=True)

    requirement.refresh_from_db()
    assert (requirement.title, requirement.review_status) == ('Agreed guide', 'approved')


@pytest.mark.django_db
def test_technical_sync_does_not_recalculate_commercial_progress():
    """Keep the recorded commercial progress unchanged during technical synchronization."""
    admin, project = _make_selection_setup('commercial-progress', module_selected=True)
    project.progress = 72
    project.save(update_fields=['progress'])

    sync_technical_resources_for_project(project, admin)

    project.refresh_from_db()
    assert project.progress == 72


@pytest.mark.django_db
@pytest.mark.parametrize(('selected', 'expected'), [(False, False), (True, True)])
def test_resources_follow_optional_module_selection(selected, expected):
    """Create the optional module resource only when that module is selected."""
    admin, project = _make_selection_setup('module-filter', module_selected=selected)

    sync_technical_resources_for_project(project, admin)

    assert Deliverable.objects.filter(project=project, source_epic_key='mod-pwa-module').exists() is expected


@pytest.mark.django_db
def test_preview_reports_resource_changes_without_review_cards():
    """Preview planned resource changes without creating resources or review cards."""
    admin, project = _make_selection_setup('preview-resources', module_selected=True)

    diff = compute_sync_diff(project, {'epics': [{'epicKey': 'resource-a', 'title': 'Resource A'}]})

    assert diff['epics']['to_create'] == [{'epicKey': 'resource-a', 'title': 'Resource A'}]
    assert set(diff) == {'epics', 'data_model_entities'}
    assert not Deliverable.objects.filter(project=project, source_epic_key='resource-a').exists()
