"""Client merge decisions, read-only plans, and foreseeable refusals."""
from datetime import timedelta

import pytest
from accounts.billing_models import CollectionAccountContext, ProjectHosting
from accounts.models import BugReport, UserProfile
from accounts.models_project_client_access import ProjectClientAccessPolicy
from django.contrib.auth.models import Group
from django.utils import timezone

from content.models import (
    ClientDocumentNumberSequence,
    DataIntegrityOperation,
    Document,
    LinktreeTemplate,
    ProjectRetentionContext,
)
from content.services import client_merge
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.tests.data_integrity_helpers import undo
from content.tests.data_integrity_merge_factories import (
    client_pair,
    make_client,
    make_client_project,
    make_collection_account,
    make_document,
    make_folder,
    make_income,
    make_pending_intent,
    make_user,
    merge_selection,
    merge_state,
    run_client_merge,
)

pytestmark = pytest.mark.django_db


def codes(plan):
    return {item['code'] for item in plan['preview']['blockers']}


def test_preview_leaves_rows_unchanged(superuser):
    """Fails if planning retires an identity or reassigns a document."""
    survivor, duplicate = client_pair()
    document = make_document('Sólo lectura', client_user=duplicate.user)
    before = list(UserProfile.objects.order_by('pk').values())

    first = client_merge.plan_client_merge(survivor, duplicate, actor=superuser)
    second = client_merge.plan_client_merge(survivor, duplicate, actor=superuser)

    assert first['fingerprint'] == second['fingerprint']
    assert codes(first) == set()
    assert list(UserProfile.objects.order_by('pk').values()) == before
    assert Document.objects.get(pk=document.pk).client_user_id == duplicate.user_id


def test_conflict_decisions_change_the_engine_hash(superuser):
    """Fails if two choices for conflicting contact data bind the same confirmation."""
    survivor, duplicate = client_pair(address='Dirección nueva')
    UserProfile.objects.filter(pk=survivor.pk).update(address='Dirección anterior')
    selection = merge_selection(survivor, duplicate, resolutions={'address': 'survivor'})
    other = {**selection, 'params': {**selection['params'], 'resolutions': {'address': 'duplicate'}}}

    first = engine.preview_fixes(resolve_scope('all'), [selection], actor=superuser)
    second = engine.preview_fixes(resolve_scope('all'), [other], actor=superuser)

    assert first['blocked'] is False
    assert second['blocked'] is False
    assert first['impact_hash'] != second['impact_hash']


def test_missing_conflict_decision_blocks_apply():
    """Fails if conflicting nonblank fields are overwritten without a choice."""
    survivor, duplicate = client_pair(phone='111')
    UserProfile.objects.filter(pk=survivor.pk).update(phone='222')
    from django.contrib.auth import get_user_model
    get_user_model().objects.filter(pk__in=[survivor.user_id, duplicate.user_id]).update(email='')
    make_user('unrelated-no-email')

    plan = client_merge.plan_client_merge(survivor, duplicate)

    assert 'identity_conflict' in codes(plan)
    assert 'identity_collision' not in codes(plan)


def test_placeholder_identity_adopts_real_email():
    """Fails if a provisional survivor keeps its placeholder instead of adopting the real identity."""
    survivor = make_client('placeholder')
    duplicate = make_client('real', email='real@example.com')

    plan = client_merge.plan_client_merge(survivor, duplicate)

    assert plan['user_values'] == {'email': 'real@example.com', 'username': 'real@example.com'}
    assert plan['preview']['identity']['retired']['username'] == f'merged_{duplicate.pk}'


def test_relation_samples_are_bounded():
    """Fails if a large relation leaks an unbounded list of records in the preview."""
    survivor, duplicate = client_pair()
    Document.objects.bulk_create([Document(title=f'Doc {i}', client_user=duplicate.user) for i in range(23)])

    plan = client_merge.plan_client_merge(survivor, duplicate)

    relation = next(row for row in plan['preview']['relations'] if row['relation'] == 'content.Document.client_user')
    assert relation['count'] == 23
    assert len(relation['sample_ids']) == 20


def test_hidden_uuid_relation_returns_to_its_exact_pre_merge_state(superuser):
    """Fails if a UUID relation cannot be recorded and restored through stored JSON steps."""
    survivor, duplicate = client_pair()
    template = LinktreeTemplate.objects.create(client=duplicate.user, name='Página', html='<main></main>')
    plan = client_merge.plan_client_merge(survivor, duplicate)
    before = merge_state(plan['closure'])

    preview, result = run_client_merge(superuser, survivor, duplicate)

    assert preview['blocked'] is False
    assert LinktreeTemplate.objects.get(pk=template.pk).client_id == survivor.user_id
    step = DataIntegrityOperation.objects.get(pk=result['operation_id']).steps[0]
    assert {'model': 'content.linktreetemplate', 'pk': str(template.pk), 'field': 'client_id',
            'before': duplicate.user_id, 'after': survivor.user_id, 'guard': False} in step['items']
    assert engine.preview_undo(result['operation_id'])['blocked'] is False

    undo(superuser, result['operation_id'])

    assert merge_state(plan['closure']) == before


def _platform(survivor, duplicate):
    duplicate.user.set_password('test-only-password')
    duplicate.user.is_active = True
    duplicate.user.save(update_fields=['password', 'is_active'])


def _staff(survivor, duplicate):
    duplicate.user.is_staff = True
    duplicate.user.save(update_fields=['is_staff'])


def _archived(survivor, duplicate):
    UserProfile.objects.filter(pk=survivor.pk).update(archived_at=timezone.now())


def _retained(survivor, duplicate):
    ProjectRetentionContext.objects.create(client=duplicate.user, original_project_id=876543,
                                           project_name='Conservado', created_by=duplicate.user)


def _grants(survivor, duplicate):
    project = make_client_project(duplicate)
    ProjectClientAccessPolicy.objects.create(project=project, recipient=duplicate.user, permissions={})


def _billing(survivor, duplicate):
    ClientDocumentNumberSequence.objects.create(client_profile=survivor, last_value=3)


def _identity_taken(survivor, duplicate):
    make_user('third', email=survivor.user.email.upper())


def _groups(survivor, duplicate):
    duplicate.user.groups.add(Group.objects.create(name='Privilegio'))


def _root_blocked(survivor, duplicate):
    make_folder('Raíz A', managed_client=survivor.user, client_user=survivor.user)
    root = make_folder('Raíz B', managed_client=duplicate.user, client_user=duplicate.user)
    make_document('Ajeno', folder=root, client_user=make_user('unrelated-owner'))


def _frozen(survivor, duplicate):
    project = make_client_project(duplicate)
    BugReport.objects.create(project=project, reported_by=duplicate.user, title='Historia de tickets')


def _financial(survivor, duplicate):
    other = make_client('other-owner', email='other@example.com')
    project = make_client_project(other)
    income = make_income(duplicate, project=project)
    document = make_collection_account('Asociada', other.user, 'issued', project=project, income_record=income)
    hosting = ProjectHosting.objects.create(project=project)
    CollectionAccountContext.objects.create(document=document, nature='hosting', hosting=hosting)


def _pending(survivor, duplicate):
    make_pending_intent(duplicate, expires_at=timezone.now() + timedelta(hours=1))


UNSAFE_MERGES = [
    (_platform, 'duplicate_has_platform_access'), (_staff, 'staff_or_admin'), (_archived, 'survivor_archived'),
    (_retained, 'retained_context'), (_grants, 'client_access_grants'), (_billing, 'billing_sequence_conflict'),
    (_identity_taken, 'identity_collision'), (_groups, 'duplicate_has_privileges'),
    (_root_blocked, 'document_root_merge_blocked'),
    (_frozen, 'project_transfer_frozen'), (_financial, 'financial_reassignment_invalid'),
    (_pending, 'pending_mcp_actions'),
]


@pytest.mark.parametrize(('setup', 'code'), UNSAFE_MERGES)
def test_unsafe_client_merges_explain_their_blocker(setup, code):
    """Fails if a foreseeable unsafe merge is offered without its domain blocker."""
    survivor, duplicate = client_pair()
    setup(survivor, duplicate)

    assert code in codes(client_merge.plan_client_merge(survivor, duplicate))


def test_non_superuser_actor_is_blocked(admin_user):
    """Fails if a staff actor can apply a client merge without active-superuser authority."""
    survivor, duplicate = client_pair()

    assert 'actor_not_superuser' in codes(client_merge.plan_client_merge(survivor, duplicate, actor=admin_user))


def test_merge_over_item_limit_is_blocked(monkeypatch):
    """Fails if the client merge item cap is silently exceeded."""
    survivor, duplicate = client_pair()
    monkeypatch.setattr(client_merge, 'MAX_ITEMS', 3)

    assert 'merge_too_large' in codes(client_merge.plan_client_merge(survivor, duplicate))
