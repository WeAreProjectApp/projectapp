"""MCP preview/apply parity and the client portal's actual authorization gate."""

from copy import deepcopy
from itertools import product
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from accounts.document_views import _visible_docs_qs
from accounts.models import (
    ContractSignatureEvidence,
    DeliveryDocumentLink,
    Project,
    ProjectContract,
)
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from content.mcp.protocol import ToolError
from content.models import (
    AccountingChangeLog,
    Document,
    DocumentFolder,
    DocumentType,
    McpConnector,
    McpCredential,
)
from content.services.document_ownership_planner import (
    apply_ownership_plan,
    plan_ownership,
    portal_audience,
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
def move_case(make_client_profile, superuser):
    owner, foreign = make_client_profile(), make_client_profile()
    project = Project.objects.create(name='Parity destination project', client=owner.user)
    other_project = Project.objects.create(name='Parity foreign project', client=foreign.user)
    source = DocumentFolder.objects.create(name='Parity source')
    target = DocumentFolder.objects.create(name='Parity target', client_user=owner.user, project=project)
    kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Markdown'})
    doc = Document.objects.create(title='Parity document', document_type=kind, folder=source)
    connector, _ = McpConnector.objects.get_or_create(slug='documents', defaults={'name': 'Documents'})
    credential = McpCredential.objects.create(connector=connector, actor=superuser, label='Ownership parity')
    return SimpleNamespace(owner=owner, foreign=foreign, project=project, other_project=other_project,
                           source=source, target=target, kind=kind, doc=doc, credential=credential, actor=superuser)


def _call(case, name, arguments):
    payload = call_tool_inprocess('documents', name, arguments, credential=case.credential)
    if payload.get('ok') is False:
        error = payload['error']
        raise ToolError(error['message'], code=error['code'], details=error.get('details', {}))
    return payload


def _prediction(plan, before):
    expected = deepcopy(before)
    for row in plan['rows']:
        after = row['after']
        table = expected['documents'] if row['resource_type'] == 'document' else expected['folders']
        item = next(item for item in table if item['id'] == row['id'])
        item.update(client_user_id=after['client_user_id'], project_id=after['project_id'])
        if row['resource_type'] == 'folder':
            item['parent_id'] = after['folder_or_parent_id']
            continue
        item.update(folder_id=after['folder_or_parent_id'], is_client_visible=after['is_client_visible'])
        for user_id, ids in expected['portal'].items():
            expected['portal'][user_id] = sorted((set(ids) - {row['id']}) | ({row['id']} if str(after['portal_audience']) == user_id else set()))
        admin_ids = set(expected['admin']) - {row['id']}
        if after['is_client_visible'] and not after['is_archived'] and not after['is_collection_account']:
            admin_ids.add(row['id'])
        expected['admin'] = sorted(admin_ids)
    return expected


def _apply_move(case, tool, arguments, plan, *, mixed=False):
    policies = {key: arguments[key] for key in ('client_policy', 'portal_policy', 'document_decisions') if key in arguments}
    if tool == 'move_documents':
        return _call(case, tool, {'document_ids': arguments['document_ids'], 'folder_id': arguments['destination_folder_id'],
                                 'expected_plan_hash': plan['plan_hash'], **policies})
    if tool == 'update_folder':
        policies.pop('document_decisions', None)
        return _call(case, tool, {'folder_id': arguments['folder_ids'][0], 'parent_id': arguments['destination_folder_id'],
                                 'expected_plan_hash': plan['plan_hash'], **policies})
    return _call(case, tool, {'document_id': arguments['document_ids'][0], 'folder_id': arguments['destination_folder_id'],
                             **({'title': 'Updated during move'} if mixed else {}), **policies})


@pytest.mark.parametrize('tool', ['move_documents', 'update_folder', 'update_document'])
@pytest.mark.parametrize('blocked', [False, True], ids=['applied', 'blocked'])
def test_mcp_move_matches_preview(move_case, tool, blocked):
    case = move_case
    original_client = {False: None, True: case.foreign.user}[blocked]
    Document.objects.filter(pk=case.doc.pk).update(client_user=original_client)
    scope = {'update_folder': {'folder_ids': [case.source.pk]}}.get(tool, {'document_ids': [case.doc.pk]})
    arguments = {**scope, 'destination_folder_id': case.target.pk}
    pair = PreviewApplyPair(tool, lambda args: _call(case, 'preview_move', args),
                            lambda args, plan: _apply_move(case, tool, args, plan, mixed=True), predicted=_prediction)

    plan, result = check_pair(pair, arguments)

    assert plan['can_apply'] is not blocked
    _assert_pair_result(case, tool, plan, result, blocked)


def _assert_pair_result(case, tool, plan, result, blocked):
    if blocked:
        assert result.code == 'OWNERSHIP_PLAN_BLOCKED'
        assert {row['code'] for row in result.details['blockers']} == {'ownership_conflict'}
    else:
        assert isinstance(result, dict)
        case.doc.refresh_from_db()
        assert (case.doc.client_user_id, case.doc.project_id) == (case.owner.user_id, case.project.pk)
        audits = AccountingChangeLog.objects.filter(object_id=case.doc.pk, entity_type='document')
        assert audits.filter(actor=case.actor).exists()
        if tool == 'move_documents':
            assert result['results'][0]['after'] == plan['rows'][0]['after']
        if tool == 'update_document':
            assert case.doc.title == 'Updated during move'


def test_mcp_refuses_latent_portal_exposure(move_case):
    case = move_case
    Document.objects.filter(pk=case.doc.pk).update(is_client_visible=True, is_archived=True)
    arguments = {'folder_ids': [case.source.pk], 'destination_folder_id': case.target.pk}
    pair = PreviewApplyPair(
        'latent portal exposure', lambda args: _call(case, 'preview_move', args),
        lambda args, plan: _apply_move(case, 'update_folder', args, plan), predicted=_prediction,
    )

    plan, result = check_pair(pair, arguments)

    document_row = next(row for row in plan['rows'] if row['resource_type'] == 'document')
    assert document_row['latent_exposure'] is True
    assert document_row['after']['portal_audience'] is None
    assert result.code == 'OWNERSHIP_PLAN_BLOCKED'
    assert result.details['blockers'] == plan['blockers']
    assert [(row['code'], row['resource_id']) for row in plan['blockers']] == [('portal_exposure_latent', case.doc.pk)]
    assert [(row['code'], row['resource_id']) for row in plan['warnings']] == [('latent_exposure', case.doc.pk)]


def test_folder_only_document_patch_matches_preview(move_case):
    arguments = {'document_ids': [move_case.doc.pk], 'destination_folder_id': move_case.target.pk}
    pair = PreviewApplyPair('single folder patch', lambda args: _call(move_case, 'preview_move', args),
                            lambda args, plan: _apply_move(move_case, 'update_document', args, plan), predicted=_prediction)

    plan, result = check_pair(pair, arguments)

    move_case.doc.refresh_from_db()
    assert result['folder_id'] == move_case.target.pk
    assert move_case.doc.title == 'Parity document'
    assert move_case.doc.project_id == plan['rows'][0]['after']['project_id']


def _portal_matrix(case):
    account_kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Account'})
    ids = []
    for index, (client, project_row, visible, archived, account) in enumerate(product(
        (None, case.owner.user, case.foreign.user), (None, case.project, case.other_project), (False, True), (False, True), (False, True),
    )):
        doc = Document.objects.create(title=f'Portal matrix {index}', folder=case.source,
                                       client_user=client, project=project_row, is_client_visible=visible, is_archived=archived,
                                       document_type=account_kind if account else case.kind)
        ids.append(doc.pk)
    linked = Document.objects.create(title='Hidden published attachment', folder=case.source,
                                     client_user=case.owner.user, project=case.project, document_type=case.kind)
    DeliveryDocumentLink.objects.create(project=case.project, document=linked, level='project', created_by=case.actor)
    private = Document.objects.create(title='Visible private attachment', folder=case.source, document_type=case.kind,
                                      client_user=case.owner.user, project=case.project, is_client_visible=True)
    private_contract = ProjectContract.objects.create(project=case.project, document=private, key='private', title='Private contract')
    DeliveryDocumentLink.objects.create(project=case.project, document=private, level='contract', contract=private_contract, created_by=case.actor)
    signed = Document.objects.create(title='Archived signed source', folder=case.source, document_type=case.kind,
                                     client_user=case.owner.user, project=case.project, is_archived=True)
    signed_contract = ProjectContract.objects.create(project=case.project, document=signed, key='signed', title='Signed contract', client_visible=True)
    ContractSignatureEvidence.objects.create(contract=signed_contract, file='delivery/signatures/test.pdf', sha256='a' * 64,
                                             signer_name='Client', signed_at=timezone.now(), attestation='Test evidence', attested_by=case.actor)
    ids.extend([case.doc.pk, linked.pk, private.pk, signed.pk])
    return ids


@pytest.mark.parametrize('client_name', ['owner', 'foreign'])
def test_portal_audience_matches_real_queryset(move_case, client_name):
    ids = _portal_matrix(move_case)
    unowned = DocumentFolder.objects.create(name='Portal matrix unowned destination')
    plan = assert_no_writes(plan_ownership, folder_ids=[move_case.source.pk],
                           destination_folder_id=unowned.pk, client_policy='keep')
    client = getattr(move_case, client_name).user

    actual = set(_visible_docs_qs(SimpleNamespace(user=client)).filter(pk__in=ids).values_list('pk', flat=True))
    predicted = {row['id'] for row in plan['rows'] if row['resource_type'] == 'document' and portal_audience(row['before']) == client.pk}

    assert actual == predicted
    assert len(ids) == 76


@pytest.fixture
def invalid_folder_move(move_case, request):
    case = move_case
    scenario = request.param
    if scenario == 'cycle':
        case.target = DocumentFolder.objects.create(name='Descendant', parent=case.source)
    elif scenario == 'archived':
        case.target = DocumentFolder.objects.create(name='Archived target', is_archived=True)
    elif scenario == 'system':
        case.source = DocumentFolder.objects.create(name='System source', system_key='ownership:test')
    elif scenario == 'managed':
        case.source = case.project.document_root_folder
    else:
        DocumentFolder.objects.create(name=case.source.name, parent=case.target, is_archived=True)
    return case


@pytest.mark.parametrize('invalid_folder_move', ['cycle', 'archived', 'system', 'managed', 'duplicate'], indirect=True)
def test_folder_move_reuses_serializer_guards(invalid_folder_move):
    case = invalid_folder_move
    arguments = {'folder_ids': [case.source.pk], 'destination_folder_id': case.target.pk}
    pair = PreviewApplyPair('folder guard', lambda args: _call(case, 'preview_move', args),
                            lambda args, plan: _apply_move(case, 'update_folder', args, plan), predicted=_prediction)

    plan, result = check_pair(pair, arguments)

    assert plan['can_apply'] is False
    assert result.code == 'OWNERSHIP_PLAN_BLOCKED'
    assert {row['resource_type'] for row in plan['blockers']} == {'folder'}


def test_writer_rolls_back_a_partially_saved_plan(move_case):
    second = Document.objects.create(title='Second move', document_type=move_case.kind, folder=move_case.source)
    arguments = {'document_ids': [move_case.doc.pk, second.pk], 'destination_folder_id': move_case.target.pk, 'client_policy': 'inherit'}
    plan = assert_no_writes(plan_ownership, **arguments)
    before = ownership_state()
    original_save = Document.save
    log_count = AccountingChangeLog.objects.count()

    def reject_second(document, *args, **kwargs):
        if document.pk == second.pk:
            raise IntegrityError('Injected second-row failure')
        return original_save(document, *args, **kwargs)

    with patch.object(Document, 'save', reject_second), pytest.raises(IntegrityError):
        apply_ownership_plan(arguments, actor=move_case.actor, expected_plan_hash=plan['plan_hash'])

    assert ownership_state() == before
    assert AccountingChangeLog.objects.count() == log_count


@pytest.mark.parametrize('tool', ['move_documents', 'update_folder'])
def test_mcp_stale_move_requires_a_new_preview(move_case, tool):
    scope = {'update_folder': {'folder_ids': [move_case.source.pk]}}.get(tool, {'document_ids': [move_case.doc.pk]})
    arguments = {**scope, 'destination_folder_id': move_case.target.pk}
    plan = assert_no_writes(_call, move_case, 'preview_move', arguments)
    DocumentFolder.objects.filter(pk=move_case.target.pk).update(client_user=move_case.foreign.user, project=None)
    before = ownership_state()

    with pytest.raises(ToolError) as rejected:
        _apply_move(move_case, tool, arguments, plan)

    assert rejected.value.code == 'STALE_MOVE_PLAN'
    assert ownership_state() == before


def test_panel_parent_move_keeps_legacy_ownership(move_case, admin_client):
    Document.objects.filter(pk=move_case.doc.pk).update(client_user=move_case.foreign.user)

    response = admin_client.patch(reverse('update-document-folder', args=[move_case.source.pk]),
                                  {'parent_id': move_case.target.pk}, format='json')

    move_case.source.refresh_from_db()
    move_case.doc.refresh_from_db()
    assert response.status_code == 200
    assert (move_case.source.parent_id, move_case.source.client_user_id, move_case.source.project_id) == (move_case.target.pk, None, None)
    assert (move_case.doc.folder_id, move_case.doc.client_user_id, move_case.doc.project_id) == (move_case.source.pk, move_case.foreign.user_id, None)


def test_mixed_visibility_cannot_bypass_move_policy(move_case):
    before = ownership_state()

    with pytest.raises(ToolError) as rejected:
        _call(move_case, 'update_document', {'document_id': move_case.doc.pk, 'folder_id': move_case.target.pk,
                                           'title': 'Forbidden exposure', 'is_client_visible': True})

    assert rejected.value.details['blockers'][0]['code'] == 'portal_exposure'
    assert ownership_state() == before
    move_case.doc.refresh_from_db()
    assert move_case.doc.title == 'Parity document'
