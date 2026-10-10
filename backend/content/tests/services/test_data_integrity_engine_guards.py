"""Snapshot identities, shared lock order and undo guard compatibility."""
import json
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from unittest.mock import Mock
from uuid import UUID

import pytest
from django.db.models import QuerySet

from content.models import (
    DataIntegrityOperation,
    Document,
    DocumentFolder,
    LinktreeTemplate,
)
from content.services import client_merge, client_merge_policy
from content.services.data_integrity import catalog, engine
from content.services.data_integrity.snapshots import (
    diff_items,
    json_value,
    snapshot_many,
)
from content.services.entity_history import history_operation
from content.tests.data_integrity_helpers import apply, only, scan, selection, undo
from content.tests.data_integrity_merge_factories import (
    client_pair,
    make_client,
    make_document,
    make_folder,
    make_pending_intent,
    merge_state,
    run_client_merge,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(params=['DC4', 'NM1'])
def folder_fix(request):
    parent = make_folder('Raíz')
    if request.param == 'DC4':
        survivor = make_folder('Facturas', parent=parent)
        duplicate = make_folder('facturas', parent=parent)
        make_document('Factura', folder=duplicate)
        [finding] = only(scan(rule_ids=['DC4']), 'DC4')
        chosen = selection(finding, 'merge_folders', survivor=survivor.pk, duplicate=duplicate.pk)
    else:
        duplicate = make_folder(' Facturas  2026 ', parent=parent)
        [finding] = only(scan(rule_ids=['NM1']), 'NM1')
        chosen = selection(finding, 'rename')
    return chosen


@pytest.fixture
def row_locks(monkeypatch):
    locks = []
    original = QuerySet.select_for_update

    def observe(queryset, *args, **kwargs):
        locks.append(queryset.model._meta.label_lower)
        return original(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', observe)
    return locks


@pytest.fixture
def clients():
    return client_pair()


@pytest.fixture
def folder_operation(superuser):
    survivor, duplicate = make_folder('Facturas'), make_folder('facturas')
    make_document('Factura', folder=duplicate)
    [finding] = only(scan(rule_ids=['DC4']), 'DC4')
    _, result = apply(superuser, [selection(finding, 'merge_folders',
                                           survivor=survivor.pk, duplicate=duplicate.pk)])
    return result['operation_id']


@pytest.mark.parametrize('requested_key', [lambda pk: pk, str, lambda pk: pk.hex])
def test_snapshot_preserves_the_requested_uuid_key(requested_key):
    """Fails if a UUID read from JSON is mistaken for a missing row or returned under another key."""
    _, duplicate = client_pair()
    template = LinktreeTemplate.objects.create(client=duplicate.user, name='Página', html='<main></main>')
    catalog.get_fixer('CL1', 'merge_clients')
    key = ('content.linktreetemplate', requested_key(template.pk))
    missing = ('content.linktreetemplate', '00000000-0000-0000-0000-000000000000')

    rows = snapshot_many([key, missing])

    assert set(rows) == {key, missing}
    assert rows[key]['client_id'] == duplicate.user_id
    assert rows[missing] is None


def test_uuid_diff_items_can_be_stored_as_json():
    """Fails if a diff still contains a UUID object rather than its JSON identity."""
    pk = UUID('12345678-1234-5678-1234-567812345678')
    key = ('content.linktreetemplate', pk)

    items = diff_items({key: {'client_id': 1}}, {key: {'client_id': 2}})

    assert json_value(pk) == str(pk)
    assert json.loads(json.dumps(items)) == [
        {'model': key[0], 'pk': str(pk), 'field': 'client_id', 'before': 1, 'after': 2, 'guard': False},
    ]


def test_folder_apply_takes_the_mutex_before_any_row_lock(folder_fix, superuser, row_locks):
    """Fails if a merge or serializer rename takes a row before the shared folder-tree mutex."""
    _, result = apply(superuser, [folder_fix])

    assert row_locks[0] == 'content.documentfoldermutationlock'
    assert 'content.documentfolder' in row_locks
    assert DataIntegrityOperation.objects.filter(pk=result['operation_id']).exists()


def test_folder_undo_takes_the_mutex_before_any_row_lock(folder_fix, superuser, row_locks):
    """Fails if undo takes even its operation row before the shared folder-tree mutex."""
    _, result = apply(superuser, [folder_fix])
    row_locks.clear()

    undo(superuser, result['operation_id'])

    assert row_locks[0] == 'content.documentfoldermutationlock'
    assert row_locks.index('content.dataintegrityoperation') > 0
    assert 'content.documentfolder' in row_locks


def test_client_apply_takes_the_mutex_without_recorded_folders(clients, superuser, row_locks):
    """Fails if a client writer's unconditional mutex comes after the engine's user locks."""
    survivor, duplicate = clients

    _, result = run_client_merge(superuser, survivor, duplicate)

    step = DataIntegrityOperation.objects.get(pk=result['operation_id']).steps[0]
    assert 'content.documentfolder' not in {item['model'] for item in step['items']}
    assert row_locks[0] == 'content.documentfoldermutationlock'


def test_client_undo_takes_the_mutex_without_recorded_folders(clients, superuser, row_locks):
    """Fails if a client revert takes its unconditional mutex after the operation row lock."""
    survivor, duplicate = clients
    _, result = run_client_merge(superuser, survivor, duplicate)
    row_locks.clear()

    undo(superuser, result['operation_id'])

    assert row_locks[0] == 'content.documentfoldermutationlock'
    assert row_locks.index('content.dataintegrityoperation') > 0


def test_boolean_undo_guard_keeps_the_generic_reason(folder_operation, monkeypatch):
    """Fails if existing bool hooks lose their generic blocker or are called more than once."""
    step = DataIntegrityOperation.objects.get(pk=folder_operation).steps[0]
    hook = Mock(return_value=True)
    monkeypatch.setattr(catalog.get_fixer('DC4', 'merge_folders'), 'guards_changed', hook)

    preview = engine.preview_undo(folder_operation)

    assert preview['blocked'] is True
    assert preview['blockers'][0]['code'] == 'guard_changed'
    assert preview['blockers'][0]['rule_id'] == 'DC4'
    hook.assert_called_once_with(step)


@pytest.mark.parametrize('shape', [list, tuple])
def test_structured_undo_guard_preserves_the_reason(folder_operation, monkeypatch, shape):
    """Fails if blocker dictionaries lose detail, mutate, or become a generic guard failure."""
    step = DataIntegrityOperation.objects.get(pk=folder_operation).steps[0]
    reason = {'code': 'parent_archived', 'message': 'La carpeta contenedora se archivó.',
              'records': [{'model': 'content.documentfolder', 'id': 123}], 'detail': 'Dato conservado'}
    hook = Mock(return_value=shape([reason]))
    monkeypatch.setattr(catalog.get_fixer('DC4', 'merge_folders'), 'guards_changed', hook)

    preview = engine.preview_undo(folder_operation)

    assert preview['blockers'] == [{**reason, 'rule_id': 'DC4'}]
    assert 'rule_id' not in reason
    hook.assert_called_once_with(step)


def test_differently_named_client_roots_return_to_their_exact_state(superuser):
    """Fails if client names prevent root content moves or any live column fails its round trip."""
    survivor = make_client('accented', email='jose@example.com',
                           user_values={'first_name': 'José', 'last_name': 'Pérez'})
    duplicate = make_client('plain', email='jose@example.com',
                            user_values={'first_name': 'Jose', 'last_name': 'Perez'})
    kept = make_folder('José Pérez', managed_client=survivor.user, client_user=survivor.user)
    source = make_folder('Jose Perez', managed_client=duplicate.user, client_user=duplicate.user)
    twin = make_folder('Anexos', parent=kept, client_user=survivor.user)
    child = make_folder('anexos', parent=source, client_user=duplicate.user)
    moved = make_folder('Reportes', parent=source, client_user=duplicate.user)
    direct = make_document('Contrato', folder=source, client_user=duplicate.user)
    nested = make_document('Anexo', folder=child, client_user=duplicate.user)
    resolutions = {'first_name': 'survivor', 'last_name': 'survivor'}
    plan = client_merge.plan_client_merge(survivor, duplicate, resolutions=resolutions, actor=superuser)
    before = merge_state(plan['closure'])

    _, result = run_client_merge(superuser, survivor, duplicate, resolutions=resolutions)

    assert Document.objects.get(pk=direct.pk).folder_id == kept.pk
    assert Document.objects.get(pk=nested.pk).folder_id == twin.pk
    assert DocumentFolder.objects.get(pk=moved.pk).parent_id == kept.pk
    assert DocumentFolder.objects.get(pk=source.pk).is_archived is True

    undo(superuser, result['operation_id'])

    assert merge_state(plan['closure']) == before


@pytest.mark.parametrize(('hours', 'blocked'), [(-1, False), (0, False), (1, True)])
def test_only_live_pending_intents_block_the_client_merge(monkeypatch, hours, blocked):
    """Fails if an expired confirmation blocks a merge or a live one stops guarding its client."""
    survivor, duplicate = client_pair()
    now = datetime(2026, 10, 9, tzinfo=datetime_timezone.utc)
    monkeypatch.setattr(client_merge.timezone, 'now', lambda: now)
    intent = make_pending_intent(duplicate, expires_at=now + timedelta(hours=hours))

    plan = client_merge.plan_client_merge(survivor, duplicate)

    assert ('pending_mcp_actions' in {row['code'] for row in plan['preview']['blockers']}) is blocked
    intent.refresh_from_db()
    assert intent.status == intent.STATUS_PENDING


def test_client_preview_discovers_relations_once(monkeypatch):
    """Fails if policy drift rebuilds the relation inventory during the same preview."""
    survivor, duplicate = client_pair()
    discover = Mock(wraps=client_merge_policy.discover_relations)
    monkeypatch.setattr(client_merge, 'discover_relations', discover)
    monkeypatch.setattr(client_merge_policy, 'discover_relations', discover)

    plan = client_merge.plan_client_merge(survivor, duplicate)

    discover.assert_called_once_with()
    assert plan['preview']['blockers'] == []


def test_client_apply_reuses_one_relation_inventory(superuser, monkeypatch):
    """Fails if locked revalidation or per-row relinking rebuilds the relation inventory."""
    survivor, duplicate = client_pair()
    first = LinktreeTemplate.objects.create(client=duplicate.user, name='Uno', html='<main></main>')
    second = LinktreeTemplate.objects.create(client=duplicate.user, name='Dos', html='<main></main>')
    plan = client_merge.plan_client_merge(survivor, duplicate, actor=superuser)
    discover = Mock(wraps=client_merge_policy.discover_relations)
    monkeypatch.setattr(client_merge, 'discover_relations', discover)
    monkeypatch.setattr(client_merge_policy, 'discover_relations', discover)

    with history_operation(actor=superuser, source='http'):
        client_merge.apply_client_merge(plan, actor=superuser)

    discover.assert_called_once_with()
    assert set(LinktreeTemplate.objects.filter(pk__in=[first.pk, second.pk])
               .values_list('client_id', flat=True)) == {survivor.user_id}


def test_exact_restore_handles_uuid_items_without_a_fixer_revert(superuser, monkeypatch):
    """Fails if the engine fallback cannot restore a UUID row from stored string keys."""
    survivor, duplicate = client_pair()
    template = LinktreeTemplate.objects.create(client=duplicate.user, name='Página', html='<main></main>')
    plan = client_merge.plan_client_merge(survivor, duplicate)
    before = merge_state(plan['closure'])
    _, result = run_client_merge(superuser, survivor, duplicate)
    monkeypatch.setattr(catalog.get_fixer('CL1', 'merge_clients'), 'revert', None)

    _, reversal = undo(superuser, result['operation_id'])

    assert merge_state(plan['closure']) == before
    step = DataIntegrityOperation.objects.get(pk=reversal['operation_id']).steps[0]
    assert {'model': 'content.linktreetemplate', 'pk': str(template.pk), 'field': 'client_id',
            'before': survivor.user_id, 'after': duplicate.user_id, 'guard': False} in step['items']
