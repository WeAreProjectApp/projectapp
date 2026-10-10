"""Project creation shares reviewed root migration rules across REST and MCP."""

import pytest
from accounts.models import Project

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
            **{key: args[key] for key in ('client_policy', 'portal_policy', 'document_decisions') if key in args},
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


def test_blocked_explicit_adoption_returns_conflict_without_an_intent(projects_credential, make_client_profile):
    owner = make_client_profile()
    foreign = make_client_profile()
    source = DocumentFolder.objects.create(name='Legacy root')
    document = Document.objects.create(title='Foreign note', folder=source, client_user=foreign.user)
    args = {'name': 'ProjectApp', 'client_profile_id': owner.pk, 'root_folder_id': source.pk}

    plan, error = check_pair(creation_pair(projects_credential), args)

    assert plan['can_apply'] is False
    assert error.code == 'CONFLICT'
    assert {row['resource_id'] for row in error.details['blockers']} == {document.pk}
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


def test_projectapp_with_pinned_contracts_only_adopts_with_explicit_policies(
    projects_credential, make_client_profile, initialized_contract_mirrors,
):
    owner = make_client_profile()
    foreign = make_client_profile()
    source = DocumentFolder.objects.create(name='ProjectApp')
    pinned = initialized_contract_mirrors.mirror_folder
    pinned.parent = source
    pinned.save(update_fields=['parent'])
    foreign_note = Document.objects.create(title='Foreign note', folder=source, client_user=foreign.user)
    visible = Document.objects.create(title='Public estimate', folder=source, is_client_visible=True)
    before = ownership_state()
    args = {'name': 'ProjectApp', 'client_profile_id': owner.pk}

    with pytest.raises(ToolError) as error:
        invoke(projects_credential, 'create_project', args)

    assert error.value.code == 'PROJECT_ROOT_NAME_CONFLICT'
    assert error.value.details['folder_ids'] == [source.pk]
    assert not Project.objects.exists()
    assert ownership_state() == before
    args.update(root_folder_id=source.pk, client_policy='inherit', portal_policy='hide_new_exposure')
    _, result = check_pair(creation_pair(projects_credential), args)
    pinned.refresh_from_db()
    foreign_note.refresh_from_db()
    visible.refresh_from_db()
    assert (pinned.client_user_id, pinned.project_id, pinned.parent_id) == (None, None, source.pk)
    assert foreign_note.client_user_id == owner.user_id
    assert foreign_note.project_id == result['id']
    assert visible.is_client_visible is False
    mirrors = invoke(projects_credential, 'get_project', {'project_id': result['id']})
    assert mirrors['id'] == result['id']
    assert DocumentFolder.objects.filter(parent__isnull=True, name='ProjectApp').count() == 1
    assert not Document.objects.filter(folder=pinned, project__isnull=False).exists()
    assert not Document.objects.filter(folder=pinned, client_user__isnull=False).exists()


@pytest.mark.parametrize('unknown', ['data', 'typo'])
def test_create_schema_rejects_unknown_fields_before_writing(projects_credential, make_client_profile, unknown):
    owner = make_client_profile()

    with pytest.raises(ToolError) as error:
        invoke(projects_credential, 'create_project', {'name': 'ProjectApp', 'client_profile_id': owner.pk, unknown: {}})

    assert error.value.code == 'unknown_field'
    assert not Project.objects.exists()
    assert not McpActionIntent.objects.exists()
