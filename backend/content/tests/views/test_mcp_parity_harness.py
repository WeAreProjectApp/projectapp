"""The parity harness detects writes, blocker drift and ownership changes."""

import json
from copy import deepcopy

import pytest
from accounts.models import Project, UserProfile
from django.db import transaction

from content.mcp.protocol import ToolError
from content.models import (
    Document,
    DocumentFolder,
    DocumentType,
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


def test_blocked_pair_keeps_ownership_intact():
    folder = DocumentFolder.objects.create(name='Blocked')
    blockers = [{'code': 'ownership_conflict'}, {'code': 'pinned_folder'}]

    def preview(args):
        selected = DocumentFolder.objects.get(pk=args['folder_id'])
        return {'can_apply': False, 'blockers': blockers, 'folder_id': selected.pk}

    def apply(args, plan):
        raise ToolError('Bloqueado.', code='FOLDER_BLOCKED', details={'blockers': list(reversed(plan['blockers']))})

    before = ownership_state()
    plan, result = check_pair(PreviewApplyPair('blocked folder', preview, apply), {'folder_id': folder.pk})

    assert plan['can_apply'] is False
    assert isinstance(result, ToolError)
    assert result.code == 'FOLDER_BLOCKED'
    assert ownership_state() == before


def test_applied_pair_matches_its_prediction():
    folder = DocumentFolder.objects.create(name='Before')

    def preview(args):
        return {'can_apply': True, 'folder_id': args['folder_id'], 'name': args['name']}

    def apply(args, plan):
        DocumentFolder.objects.filter(pk=args['folder_id']).update(name=plan['name'])
        return {'renamed': args['folder_id']}

    def predicted(plan, before):
        expected = deepcopy(before)
        for row in expected['folders']:
            if row['id'] == plan['folder_id']:
                row['name'] = plan['name']
        return expected

    plan, result = check_pair(
        PreviewApplyPair('rename folder', preview, apply, predicted=predicted),
        {'folder_id': folder.pk, 'name': 'After'},
    )

    assert result == {'renamed': folder.pk}
    folder.refresh_from_db()
    assert folder.name == plan['name'] == 'After'


@pytest.mark.parametrize('mutation', [
    lambda folder: DocumentFolder.objects.create(name='Inserted'),
    lambda folder: DocumentFolder.objects.filter(pk=folder.pk).update(name='Updated'),
    lambda folder: DocumentFolder.objects.filter(pk=folder.pk).delete(),
], ids=['insert', 'update', 'delete'])
def test_no_writes_detects_a_model_mutation(mutation):
    folder = DocumentFolder.objects.create(name='Original')

    with pytest.raises(AssertionError, match='Unexpected SQL writes:') as rejected:
        assert_no_writes(mutation, folder)

    assert 'content_documentfolder' in str(rejected.value)


def test_no_writes_allows_only_selected_tables():
    folder = DocumentFolder.objects.create(name='Original')

    changed = assert_no_writes(
        DocumentFolder.objects.filter(pk=folder.pk).update,
        name='Allowed', allow_tables=('content_documentfolder',),
    )

    assert changed == 1
    folder.refresh_from_db()
    assert folder.name == 'Allowed'
    with pytest.raises(AssertionError, match='content_documenttype'):
        assert_no_writes(
            DocumentType.objects.create, code='unexpected-write', name='Unexpected',
            allow_tables=('content_documentfolder',),
        )


def test_no_writes_ignores_savepoints():
    folder = DocumentFolder.objects.create(name='Read only')

    def read():
        with transaction.atomic():
            return DocumentFolder.objects.get(pk=folder.pk).name

    assert assert_no_writes(read) == 'Read only'


def test_pair_rejects_mismatched_blockers():
    DocumentFolder.objects.create(name='Unchanged')

    def apply(args, preview):
        raise ToolError('Bloqueado.', details={'blockers': [{'code': 'different_guard'}]})

    pair = PreviewApplyPair('blocker drift', lambda args: {
        'can_apply': False, 'blockers': [{'code': 'original_guard'}],
    }, apply)

    with pytest.raises(AssertionError, match='blocker drift'):
        check_pair(pair, {})


def test_pair_rejects_an_incorrect_prediction():
    folder = DocumentFolder.objects.create(name='Before')
    pair = PreviewApplyPair(
        'prediction drift', lambda args: {'can_apply': True},
        lambda args, preview: DocumentFolder.objects.filter(pk=args['folder_id']).update(name='After'),
        predicted=lambda preview, before: before,
    )

    with pytest.raises(AssertionError, match='differs from its prediction'):
        check_pair(pair, {'folder_id': folder.pk})


def test_ownership_snapshot_uses_the_real_portal_audience(django_user_model):
    doc_owner = django_user_model.objects.create_user(username='document-owner')
    folder_owner = django_user_model.objects.create_user(username='folder-owner')
    project_owner = django_user_model.objects.create_user(username='project-owner')
    project = Project.objects.create(name='Ownership project', client=project_owner)
    folder = DocumentFolder.objects.create(name='Owned folder', client_user=folder_owner, order=7)
    kind = DocumentType.objects.create(code='parity-document', name='Parity')
    account_kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Account'})
    visible = Document.objects.create(title='Visible', document_type=kind, client_user=doc_owner, is_client_visible=True)
    project_doc = Document.objects.create(title='Inherited', document_type=kind, project=project, is_client_visible=True)
    Document.objects.create(title='Hidden', document_type=kind, client_user=doc_owner, is_client_visible=False)
    Document.objects.create(title='Archived', document_type=kind, client_user=doc_owner, is_client_visible=True, is_archived=True)
    Document.objects.create(title='Account', document_type=account_kind, client_user=doc_owner, is_client_visible=True)

    state = assert_no_writes(ownership_state)

    assert state == json.loads(json.dumps(state))
    assert state['portal'] == {
        str(doc_owner.pk): [visible.pk], str(folder_owner.pk): [], str(project_owner.pk): [project_doc.pk],
    }
    assert state['admin'] == [visible.pk, project_doc.pk]
    folder_row = next(row for row in state['folders'] if row['id'] == folder.pk)
    assert folder_row == {
        'id': folder.pk, 'name': 'Owned folder', 'parent_id': None, 'order': 7,
        'project_id': None, 'client_user_id': folder_owner.pk, 'managed_project_id': None,
        'managed_client_id': None, 'is_archived': False, 'archived_via_folder_id': None,
    }


def test_real_folder_preview_does_not_write(django_user_model, superuser):
    target = django_user_model.objects.create_user(username='preview-target')
    profile = UserProfile.objects.create(user=target)
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documents'})
    credential = McpCredential.objects.create(connector=connector, label='Read only parity', actor=superuser)
    folder = DocumentFolder.objects.create(name='Manual folder')
    before = ownership_state()

    preview = assert_no_writes(
        call_tool_inprocess, 'documents', 'preview_folder_client_change',
        {'folder_id': folder.pk, 'query': {'client_profile_id': profile.pk}}, credential=credential,
    )

    assert 'error' not in preview
    assert preview['folder']['id'] == folder.pk
    assert ownership_state() == before
