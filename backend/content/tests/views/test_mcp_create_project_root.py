"""Project creation shares reviewed root migration rules across REST and MCP."""

from datetime import timedelta

import pytest
from accounts.models import Project
from django.utils import timezone

from content.mcp.confirmation import canonical_arguments_hash
from content.mcp.protocol import ToolError
from content.models import (
    Document,
    DocumentFolder,
    DocumentOwnershipOperation,
    McpActionIntent,
    McpConnector,
    McpCredential,
)
from content.services import folder_migration_service as migration
from content.tests.mcp_parity import (
    PreviewApplyPair,
    assert_no_writes,
    call_tool_inprocess,
    check_pair,
    ownership_state,
)
from content.tests.views.test_mcp_folder_migration import (
    documents_credential as documents_credential,  # noqa: PLC0414 -- Re-export the shared pytest fixture.
)
from content.tests.views.test_mcp_folder_migration import (
    invoke as invoke_documents,
)
from content.tests.views.test_mcp_folder_migration import (
    migration_pair,
)
from content.tests.views.test_mcp_folder_migration import (
    projectapp_tree as projectapp_tree,  # noqa: PLC0414 -- Re-export the shared pytest fixture.
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def projects_credential(superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Proyectos', 'is_active': True},
    )
    return McpCredential.objects.create(connector=connector, actor=superuser, label='Project root review')


def invoke(credential, name, args):
    result = call_tool_inprocess('projects', name, args, credential=credential)
    if 'error' in result:
        error = result['error']
        raise ToolError(error['message'], code=error['code'], details=error['details'])
    return result


def creation_pair(credential):
    def preview(args):
        return migration.preview_folder_migration({
            'source_folder_id': args['root_folder_id'], 'strategy': 'adopt_source',
            'target': {'create_project': {key: args[key] for key in ('name', 'client_profile_id')}},
            'client_policy': 'abort_on_conflict', 'portal_policy': 'abort',
        }, actor=credential.actor, credential=credential)

    def apply(args, plan):
        confirmation = invoke(credential, 'create_project', args)
        assert confirmation['impact']['plan_hash'] == plan['plan_hash']
        return invoke(credential, 'confirm_action', {'confirmation_id': confirmation['confirmation_id']})['result']

    return PreviewApplyPair('create project with reviewed root', preview, apply)


def test_plain_create_is_immediate_with_a_root_receipt(projects_credential, make_client_profile):
    owner = make_client_profile()

    result = invoke(projects_credential, 'create_project', {
        'name': 'New project', 'client_profile_id': owner.pk, 'description': 'Minimum create',
    })

    project = Project.objects.get(pk=result['id'])
    assert result['name'] == project.name == 'New project'
    assert result['description'] == project.description == 'Minimum create'
    assert result['document_root'] == {
        'folder_id': project.document_root_folder.pk, 'adopted': False, 'migration_id': None,
    }
    assert not McpActionIntent.objects.exists()
    assert not DocumentOwnershipOperation.objects.exists()


def test_explicit_root_confirmation_adopts_one_tree(projects_credential, make_client_profile):
    owner = make_client_profile()
    source = DocumentFolder.objects.create(name='Previous name')
    document = Document.objects.create(title='Original note', folder=source)
    args = {'name': 'ProjectApp', 'client_profile_id': owner.pk, 'root_folder_id': source.pk}

    plan, result = check_pair(creation_pair(projects_credential), args)

    project = Project.objects.get(pk=result['id'])
    source.refresh_from_db()
    document.refresh_from_db()
    receipt = result['document_root']
    assert receipt['folder_id'] == source.pk == project.document_root_folder.pk
    assert receipt['adopted'] is True
    assert DocumentFolder.objects.filter(parent__isnull=True, name='ProjectApp').count() == 1
    assert source.managed_project_id == project.pk
    assert document.project_id == project.pk
    intent = McpActionIntent.objects.get(tool_name='create_project')
    operation = DocumentOwnershipOperation.objects.get(pk=receipt['migration_id'])
    assert operation.request_id == f'project-create:{intent.pk}'
    assert operation.plan_hash == plan['plan_hash']
    assert (operation.origin, operation.actor_id, operation.credential_id) == (
        'mcp', projects_credential.actor_id, projects_credential.pk,
    )
    replay = invoke(projects_credential, 'confirm_action', {'confirmation_id': str(intent.pk)})
    assert replay['replayed'] is True
    assert replay['result'] == result
    assert DocumentOwnershipOperation.objects.count() == Project.objects.count() == 1


def test_adoptable_homonym_also_requires_confirmation(projects_credential, make_client_profile):
    owner = make_client_profile()
    source = DocumentFolder.objects.create(name=' ProjectApp ')

    preview = assert_no_writes(invoke, projects_credential, 'create_project', {
        'name': 'ProjectApp', 'client_profile_id': owner.pk,
    }, allow_tables=('content_mcpactionintent',))

    assert preview['confirmation_required'] is True
    assert preview['impact']['can_apply'] is True
    assert preview['impact']['final_tree']['root_id'] == source.pk
    assert not Project.objects.exists()
    result = invoke(projects_credential, 'confirm_action', {'confirmation_id': preview['confirmation_id']})['result']
    assert result['document_root']['folder_id'] == source.pk
    operation = DocumentOwnershipOperation.objects.get(pk=result['document_root']['migration_id'])
    assert operation.origin == 'auto'
    assert operation.actor_id == projects_credential.actor_id
    assert operation.credential_id == projects_credential.pk
    assert DocumentFolder.objects.filter(parent__isnull=True, name='ProjectApp').count() == 1


@pytest.mark.parametrize(('document_kind', 'blocker_code'), [
    ('foreign', 'ownership_conflict'), ('visible', 'portal_exposure'),
    ('archived_visible', 'portal_exposure_latent'),
])
def test_blocked_explicit_adoption_returns_conflict_without_an_intent(
    projects_credential, make_client_profile, document_kind, blocker_code,
):
    owner = make_client_profile()
    foreign = make_client_profile()
    projects_credential.allowed_tools = ['create_project']
    projects_credential.save(update_fields=['allowed_tools', 'updated_at'])
    source = DocumentFolder.objects.create(name='Legacy root')
    states = {
        'foreign': {'client_user': foreign.user},
        'visible': {'is_client_visible': True},
        'archived_visible': {'is_client_visible': True, 'is_archived': True},
    }
    document = Document.objects.create(title='Review required', folder=source, **states[document_kind])
    args = {'name': 'ProjectApp', 'client_profile_id': owner.pk, 'root_folder_id': source.pk}

    plan, error = check_pair(creation_pair(projects_credential), args)

    assert plan['can_apply'] is False
    assert error.code == 'CONFLICT'
    assert [(row['code'], row['resource_id']) for row in error.details['blockers']] == [(blocker_code, document.pk)]
    assert error.details['hint'] == (
        'Para decidir propietarios o exposición usa '
        'preview_folder_migration/apply_folder_migration del conector documents.'
    )
    assert not Project.objects.exists()
    assert not McpActionIntent.objects.exists()


@pytest.mark.parametrize('explicit', [True, False])
def test_confirmation_rejects_a_stale_root_plan(projects_credential, make_client_profile, explicit):
    owner = make_client_profile()
    source = DocumentFolder.objects.create(name='ProjectApp')
    variants = {True: {'root_folder_id': source.pk}, False: {}}
    preview = invoke(projects_credential, 'create_project', {
        'name': 'ProjectApp', 'client_profile_id': owner.pk, **variants[explicit],
    })
    Document.objects.create(title='Created after preview', folder=source)
    before = ownership_state()

    with pytest.raises(ToolError) as error:
        invoke(projects_credential, 'confirm_action', {'confirmation_id': preview['confirmation_id']})

    assert error.value.code == 'STALE_VERSION'
    assert ownership_state() == before
    assert not Project.objects.exists()
    assert not DocumentOwnershipOperation.objects.exists()
    assert McpActionIntent.objects.get(pk=preview['confirmation_id']).status == McpActionIntent.STATUS_PENDING


def test_real_tree_requires_documents_connector_adoption(projects_credential, documents_credential, projectapp_tree):
    case = projectapp_tree
    before = ownership_state()
    args = {'name': 'ProjectApp', 'client_profile_id': case.owner.pk}

    with pytest.raises(ToolError) as error:
        invoke(projects_credential, 'create_project', args)

    assert error.value.code == 'PROJECT_ROOT_NAME_CONFLICT'
    assert error.value.details['folder_ids'] == [case.source.pk]
    assert not Project.objects.exists()
    assert ownership_state() == before
    args['root_folder_id'] = case.source.pk
    _plan, rejected = check_pair(creation_pair(projects_credential), args)
    assert rejected.code == 'CONFLICT'
    assert {row['resource_id'] for row in rejected.details['blockers'] if row['code'] == 'ownership_conflict'} == {
        case.first.pk, case.second.pk,
    }
    assert {row['resource_id'] for row in rejected.details['blockers'] if row['code'] == 'portal_exposure'} == {case.estimate.pk}
    assert {row['resource_id'] for row in rejected.details['blockers'] if row['code'] == 'portal_exposure_latent'} == {case.archived_estimate.pk}
    assert 'conector documents' in rejected.details['hint']
    assert not McpActionIntent.objects.exists()
    migration_args = {
        'source_folder_id': case.source.pk, 'strategy': 'adopt_source',
        'target': {'create_project': {'name': 'ProjectApp', 'client_profile_id': case.owner.pk}},
        'portal_policy': 'hide_new_exposure',
        'document_decisions': [
            {'document_id': case.first.pk, 'action': 'inherit'},
            {'document_id': case.second.pk, 'action': 'move', 'destination_folder_id': case.foreign_folder.pk},
        ],
    }
    _, result = check_pair(migration_pair(documents_credential), migration_args)
    case.pinned.refresh_from_db()
    case.first.refresh_from_db()
    case.second.refresh_from_db()
    case.estimate.refresh_from_db()
    case.archived_estimate.refresh_from_db()
    assert (case.pinned.client_user_id, case.pinned.project_id, case.pinned.parent_id) == (None, None, case.source.pk)
    assert (case.first.client_user_id, case.first.project_id) == (case.owner.user_id, result['project_id'])
    assert (case.second.client_user_id, case.second.project_id, case.second.folder_id) == (case.foreign.user_id, None, case.foreign_folder.pk)
    assert case.estimate.is_client_visible is False
    assert (case.archived_estimate.is_archived, case.archived_estimate.is_client_visible) == (True, False)
    project = invoke(projects_credential, 'get_project', {'project_id': result['project_id']})
    assert project['id'] == result['project_id']
    mirrors = invoke_documents(documents_credential, 'list_contract_mirrors', {})
    assert [row['synchronized'] for row in mirrors['mirrors']] == [True, True, True]
    assert DocumentFolder.objects.filter(parent__isnull=True, name='ProjectApp').count() == 1
    assert not Document.objects.filter(folder=case.pinned, project__isnull=False).exists()
    assert not Document.objects.filter(folder=case.pinned, client_user__isnull=False).exists()


@pytest.mark.parametrize(('policy', 'foreign_owned', 'visible'), [
    ('inherit', True, False), ('allow', False, True), ('decision', True, False),
])
def test_confirmation_refuses_legacy_permissive_adoption(
    projects_credential, make_client_profile, policy, foreign_owned, visible,
):
    owner, foreign = make_client_profile(), make_client_profile()
    source = DocumentFolder.objects.create(name='Legacy root')
    document = Document.objects.create(
        title='Legacy reviewed content', folder=source,
        client_user={True: foreign.user, False: None}[foreign_owned], is_client_visible=visible,
    )
    policies = {
        'inherit': {'client_policy': 'inherit'}, 'allow': {'portal_policy': 'allow'},
        'decision': {'document_decisions': [{'document_id': document.pk, 'action': 'inherit'}]},
    }
    plan = migration.preview_folder_migration({
        'source_folder_id': source.pk, 'strategy': 'adopt_source',
        'target': {'create_project': {'name': 'ProjectApp', 'client_profile_id': owner.pk}},
        **policies[policy],
    }, actor=projects_credential.actor, credential=projects_credential)
    assert plan['can_apply'] is True
    arguments = {
        'name': 'ProjectApp', 'client_profile_id': owner.pk, 'root_folder_id': source.pk,
        **policies[policy], '_plan_token': plan['plan_token'], '_request_nonce': 'legacy-adoption',
    }
    intent = McpActionIntent.objects.create(
        connector=projects_credential.connector, credential=projects_credential,
        tool_name='create_project', arguments=arguments, arguments_hash=canonical_arguments_hash(arguments),
        impact=plan, resource_etags={'project_create': plan['plan_hash']},
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    before = ownership_state()

    with pytest.raises(ToolError) as error:
        invoke(projects_credential, 'confirm_action', {'confirmation_id': str(intent.pk)})

    assert error.value.code == 'STALE_VERSION'
    assert 'conector documents' in error.value.details['hint']
    intent.refresh_from_db()
    assert intent.status == McpActionIntent.STATUS_PENDING
    assert not Project.objects.exists()
    assert not DocumentOwnershipOperation.objects.exists()
    assert ownership_state() == before


@pytest.mark.parametrize(('unknown', 'value'), [
    ('data', {}), ('typo', {}), ('client_policy', 'inherit'), ('portal_policy', 'allow'),
    ('document_decisions', [{'document_id': 999, 'action': 'inherit'}]),
])
def test_create_schema_rejects_unknown_fields_before_writing(projects_credential, make_client_profile, unknown, value):
    owner = make_client_profile()
    source = DocumentFolder.objects.create(name='Manual root')
    before = ownership_state()

    with pytest.raises(ToolError) as error:
        invoke(projects_credential, 'create_project', {
            'name': 'ProjectApp', 'client_profile_id': owner.pk, 'root_folder_id': source.pk, unknown: value,
        })

    assert error.value.code == 'unknown_field'
    assert unknown in {row['field'] for row in error.value.details['errors']}
    assert not Project.objects.exists()
    assert not McpActionIntent.objects.exists()
    assert ownership_state() == before
