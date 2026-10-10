"""The ProjectApp tree migrates and reverses through actual MCP confirmations."""

from types import SimpleNamespace

import pytest
from accounts.models import Project

from content.mcp.protocol import ToolError
from content.models import (
    Document,
    DocumentFolder,
    DocumentOwnershipOperation,
    McpConnector,
    McpCredential,
)
from content.tests.mcp_parity import (
    PreviewApplyPair,
    assert_no_writes,
    call_tool_inprocess,
    check_pair,
    ownership_state,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def documents_credential(superuser):
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documentos', 'is_active': True})
    return McpCredential.objects.create(connector=connector, actor=superuser, label='Reviewed migration')


@pytest.fixture
def projectapp_tree(make_client_profile, initialized_contract_mirrors, superuser):
    owner = make_client_profile(company='Client A')
    foreign = make_client_profile(company='Client B')
    source = DocumentFolder.objects.create(name='ProjectApp', creation_source='panel', created_by=superuser)
    folders = {
        name: DocumentFolder.objects.create(name=name, parent=source, creation_source='panel')
        for name in ['Plantillas', 'Estándares técnicos', 'Metodología', 'Skills', 'Requirement Estimates', 'temp']
    }
    pinned = initialized_contract_mirrors.mirror_folder
    pinned.parent = source
    pinned.save(update_fields=['parent'])
    estimate = Document.objects.create(title='Visible estimate', folder=folders['Requirement Estimates'], is_client_visible=True)
    archived_estimate = Document.objects.create(
        title='Archived visible estimate', folder=folders['Requirement Estimates'],
        is_client_visible=True, is_archived=True,
    )
    first = Document.objects.create(title='Foreign 235', folder=source, client_user=foreign.user)
    second = Document.objects.create(title='Foreign 241', folder=source, client_user=foreign.user)
    foreign_folder = DocumentFolder.objects.create(name='Client B documents', client_user=foreign.user, creation_source='panel')
    return SimpleNamespace(owner=owner, foreign=foreign, source=source, pinned=pinned,
                           estimate=estimate, archived_estimate=archived_estimate,
                           first=first, second=second, foreign_folder=foreign_folder)


def invoke(credential, tool, args):
    payload = call_tool_inprocess('documents', tool, args, credential=credential)
    if 'error' in payload:
        error = payload['error']
        raise ToolError(error['message'], code=error['code'], details=error['details'])
    return payload


def migration_pair(credential):
    def apply(args, preview):
        confirmation = invoke(credential, 'apply_folder_migration', {
            'plan_token': preview['plan_token'], 'reason': 'Migrar ProjectApp en un solo flujo', 'request_id': 'real-case',
        })
        return invoke(credential, 'confirm_action', {'confirmation_id': confirmation['confirmation_id']})['result']
    return PreviewApplyPair('folder migration', lambda args: invoke(credential, 'preview_folder_migration', args), apply)


def undo_pair(credential):
    def apply(args, preview):
        confirmation = invoke(credential, 'undo_folder_migration', {
            **args, 'expected_impact_hash': preview['impact_hash'], 'reason': 'Restaurar el árbol original', 'request_id': 'real-case-undo',
        })
        return invoke(credential, 'confirm_action', {'confirmation_id': confirmation['confirmation_id']})['result']
    return PreviewApplyPair('folder migration undo', lambda args: invoke(credential, 'preview_folder_migration_undo', args), apply)


@pytest.mark.parametrize('strategy', ['adopt_source', 'move_contents'])
def test_real_projectapp_migration_preserves_contracts(projectapp_tree, documents_credential, strategy):
    case, credential = projectapp_tree, documents_credential
    initial = ownership_state()
    args = {'source_folder_id': case.source.pk, 'strategy': strategy,
            'target': {'create_project': {'name': 'ProjectApp', 'client_profile_id': case.owner.pk}}}
    blocked, _error = check_pair(migration_pair(credential), args)
    assert {row['resource_id'] for row in blocked['blockers'] if row['code'] == 'ownership_conflict'} == {case.first.pk, case.second.pk}
    assert {row['resource_id'] for row in blocked['blockers'] if row['code'] == 'portal_exposure'} == {case.estimate.pk}
    assert {row['resource_id'] for row in blocked['blockers'] if row['code'] == 'portal_exposure_latent'} == {case.archived_estimate.pk}
    args.update(portal_policy='hide_new_exposure', document_decisions=[
        {'document_id': case.first.pk, 'action': 'move', 'destination_folder_id': case.foreign_folder.pk},
        {'document_id': case.second.pk, 'action': 'move', 'destination_folder_id': case.foreign_folder.pk},
    ])
    variants = {'adopt_source': {}, 'move_contents': {'source_rename_to': 'ProjectApp anterior', 'archive_source_when_empty': True}}
    args.update(variants[strategy])

    preview, report = check_pair(migration_pair(credential), args)

    assert preview['can_apply'] is True
    assert DocumentFolder.objects.filter(name='ProjectApp', parent__isnull=True).count() == 1
    assert Project.objects.get(pk=report['project_id']).document_root_folder.pk == report['root_folder_id']
    case.pinned.refresh_from_db()
    case.estimate.refresh_from_db()
    case.archived_estimate.refresh_from_db()
    assert (case.pinned.client_user_id, case.pinned.project_id, case.pinned.is_archived) == (None, None, False)
    assert case.estimate.is_client_visible is False
    assert (case.archived_estimate.is_archived, case.archived_estimate.is_client_visible) == (True, False)
    mirrors = assert_no_writes(invoke, credential, 'list_contract_mirrors', {})
    assert [row['synchronized'] for row in mirrors['mirrors']] == [True, True, True]
    assert not Document.objects.filter(folder=case.pinned).filter(project__isnull=False).exists()
    assert not Document.objects.filter(folder=case.pinned).filter(client_user__isnull=False).exists()
    readiness = invoke(credential, 'get_project_folder_readiness', {})
    assert readiness['status'] == 'ready'
    assert invoke(credential, 'get_folder_migration', {'migration_id': report['migration_id']}) == report
    assert report['pending'] == []
    assert report['archived_folder_ids'] == {'adopt_source': [], 'move_contents': [case.source.pk]}[strategy]
    _, undo = check_pair(undo_pair(credential), {'migration_id': report['migration_id']})
    assert undo['deleted_project_id'] == report['created_project_id']
    assert ownership_state() == initial
    assert not Project.objects.filter(pk=report['created_project_id']).exists()


def test_mcp_apply_rejects_stale_confirmation(projectapp_tree, documents_credential):
    case, credential = projectapp_tree, documents_credential
    args = {'source_folder_id': case.source.pk, 'strategy': 'adopt_source',
            'target': {'create_project': {'name': 'ProjectApp', 'client_profile_id': case.owner.pk}},
            'client_policy': 'inherit', 'portal_policy': 'hide_new_exposure'}
    preview = invoke(credential, 'preview_folder_migration', args)
    confirmation = invoke(credential, 'apply_folder_migration', {
        'plan_token': preview['plan_token'], 'reason': 'Plan confirmado', 'request_id': 'stale-confirmation',
    })
    Document.objects.create(title='Content after confirmation', folder=case.source)
    before = ownership_state()

    with pytest.raises(ToolError) as error:
        invoke(credential, 'confirm_action', {'confirmation_id': confirmation['confirmation_id']})

    assert error.value.code == 'STALE_VERSION'
    assert ownership_state() == before
    assert not DocumentOwnershipOperation.objects.exists()


def test_mcp_token_is_bound_to_credential(projectapp_tree, documents_credential):
    case, credential = projectapp_tree, documents_credential
    other = McpCredential.objects.create(connector=credential.connector, actor=credential.actor, label='Other credential')
    preview = invoke(credential, 'preview_folder_migration', {
        'source_folder_id': case.source.pk, 'strategy': 'adopt_source',
        'target': {'create_project': {'name': 'ProjectApp', 'client_profile_id': case.owner.pk}},
        'client_policy': 'inherit', 'portal_policy': 'hide_new_exposure',
    })

    with pytest.raises(ToolError) as error:
        invoke(other, 'apply_folder_migration', {'plan_token': preview['plan_token'], 'reason': 'Otra credencial', 'request_id': 'wrong-credential'})

    assert error.value.code == 'FORBIDDEN'
    assert not DocumentOwnershipOperation.objects.exists()


def test_convenience_adoption_uses_reviewed_engine(documents_credential, make_client_profile):
    owner = make_client_profile()
    project = Project.objects.create(name='Existing project', client=owner.user)
    source = DocumentFolder.objects.create(name='Manual source', creation_source='panel')
    document = Document.objects.create(title='Adopted evidence', folder=source)
    initial = ownership_state()

    confirmation = invoke(documents_credential, 'adopt_folder_as_project_root', {
        'folder_id': source.pk, 'project_id': project.pk, 'reason': 'Reusar la carpeta histórica', 'request_id': 'adopt-existing',
    })
    report = invoke(documents_credential, 'confirm_action', {'confirmation_id': confirmation['confirmation_id']})['result']

    document.refresh_from_db()
    assert report['root_folder_id'] == source.pk
    assert confirmation['impact']['strategy'] == 'adopt_source'
    assert document.project_id == project.pk
    replay_confirmation = invoke(documents_credential, 'adopt_folder_as_project_root', {
        'folder_id': source.pk, 'project_id': project.pk, 'reason': 'Repetir solicitud', 'request_id': 'adopt-existing',
    })
    replay = invoke(documents_credential, 'confirm_action', {'confirmation_id': replay_confirmation['confirmation_id']})['result']
    assert replay == report
    assert DocumentOwnershipOperation.objects.count() == 1
    check_pair(undo_pair(documents_credential), {'migration_id': report['migration_id']})
    assert ownership_state() == initial


def test_migration_preview_rejects_unknown_nested_input(documents_credential):
    with pytest.raises(ToolError) as error:
        invoke(documents_credential, 'preview_folder_migration', {
            'source_folder_id': 999, 'strategy': 'adopt_source', 'target': {'project_id': 999, 'client': 1},
        })
    assert error.value.code == 'unknown_field'
    assert 'target.client' in {row['field'] for row in error.value.details['errors']}
