"""Exact reversals, guard refusals, and rows created after a client merge."""
import uuid
from datetime import date

import pytest
from accounts.models import Project, UserProfile
from accounts.models_project_client_access import ProjectClientAccessPolicy
from rest_framework.exceptions import PermissionDenied

from content.models import (
    AccountingChangeLog,
    BuildingWithUsContractRevision,
    BuildingWithUsProgramRevision,
    BusinessProposal,
    ClientDocumentNumberSequence,
    CommunicationThread,
    DataIntegrityOperation,
    Document,
    DocumentCollectionAccount,
)
from content.services import client_merge
from content.services.data_integrity import catalog, engine
from content.tests.data_integrity_helpers import only, scan, undo
from content.tests.data_integrity_merge_factories import (
    client_pair,
    make_client,
    make_client_project,
    make_collection_account,
    make_document,
    make_folder,
    make_hosting,
    make_secure_link,
    make_user,
    merge_state,
    run_client_merge,
)

pytestmark = pytest.mark.django_db


def _step(result):
    return DataIntegrityOperation.objects.get(pk=result['operation_id']).steps[0]


def _codes(blockers):
    return {row['code'] for row in blockers}


@pytest.mark.parametrize('revision_model,content', [
    (BuildingWithUsProgramRevision, {'content': {}}),
    (BuildingWithUsContractRevision, {'markdown': '# Alianza'}),
], ids=['program', 'contract'])
def test_undo_preserves_alliance_revision_author(superuser, revision_model, content):
    survivor, duplicate = client_pair()
    revision = revision_model.objects.create(
        version=revision_model.objects.count() + 1, author=duplicate.user,
        change_note='Autoría original', **content,
    )
    _, result = run_client_merge(superuser, survivor, duplicate)

    undo(superuser, result['operation_id'])

    revision.refresh_from_db()
    assert revision.author_id == duplicate.user_id


def test_engine_undo_restores_every_live_column_in_the_merge_closure(superuser):
    """Fails if an identity, managed root, customer fact, sequence or signal snapshot fails its exact round trip."""
    survivor, duplicate = client_pair(billing_code='DUP', phone='300123', date_of_birth=date(1990, 1, 2))
    project = make_client_project(duplicate)
    kept = make_folder('Clientes', managed_client=survivor.user, client_user=survivor.user)
    source = make_folder('Clientes', managed_client=duplicate.user, client_user=duplicate.user)
    make_folder('Anexos', parent=kept, client_user=survivor.user)
    nested = make_folder('Anexos', parent=source, client_user=duplicate.user)
    make_document('Documento', folder=nested, client_user=duplicate.user, created_by=duplicate.user)
    draft = make_collection_account('Borrador', duplicate.user, 'draft')
    DocumentCollectionAccount.objects.create(document=draft, customer_name='Provisional')
    ClientDocumentNumberSequence.objects.create(client_profile=duplicate, last_value=42)
    BusinessProposal.objects.create(title='Existente', client=survivor, client_phone='Hecho anterior')
    make_hosting(duplicate, client_email='old@example.com')
    catalog.get_fixer('CL1', 'merge_clients')
    plan = client_merge.plan_client_merge(survivor, duplicate, actor=superuser)
    before = merge_state(plan['closure'])

    _, result = run_client_merge(superuser, survivor, duplicate)
    undo(superuser, result['operation_id'])

    assert merge_state(plan['closure']) == before
    assert Project.objects.get(pk=project.pk).client_id == duplicate.user_id


def test_rows_created_after_the_merge_stay_with_the_survivor(superuser):
    """Fails if undo claims newly created survivor documents that were never part of the merge."""
    survivor, duplicate = client_pair()
    old = make_document('Anterior', client_user=duplicate.user)
    _, result = run_client_merge(superuser, survivor, duplicate)
    new = make_document('Posterior', client_user=survivor.user)

    undo(superuser, result['operation_id'])

    assert Document.objects.get(pk=old.pk).client_user_id == duplicate.user_id
    assert Document.objects.get(pk=new.pk).client_user_id == survivor.user_id


def test_later_document_edit_blocks_undo(superuser):
    """Fails if undo overwrites a document edited after the merge."""
    survivor, duplicate = client_pair()
    document = make_document('Anterior', client_user=duplicate.user)
    _, result = run_client_merge(superuser, survivor, duplicate)
    document.refresh_from_db()
    document.title = 'Cambio posterior'
    document.save(update_fields=['title', 'updated_at'])

    preview = engine.preview_undo(result['operation_id'])

    assert 'changed_since' in _codes(preview['blockers'])
    assert Document.objects.get(pk=document.pk).title == 'Cambio posterior'


def test_identity_claimed_by_another_user_blocks_undo(superuser):
    """Fails if undo restores D's original username over a third user's identity."""
    survivor, duplicate = client_pair()
    original = duplicate.user.username
    _, result = run_client_merge(superuser, survivor, duplicate)
    make_user(original.upper(), email='third@example.com')

    assert 'identity_taken' in _codes(client_merge.client_merge_undo_blockers(_step(result)))
    assert {'code': 'identity_taken', 'message': 'Otro usuario tomó una identidad necesaria para deshacer.',
            'rule_id': 'CL1'} in engine.preview_undo(result['operation_id'])['blockers']


def test_new_access_grant_blocks_undo(superuser):
    """Fails if undo moves a project with a new grant without preserving its access-owner boundary."""
    survivor, duplicate = client_pair()
    project = make_client_project(duplicate)
    _, result = run_client_merge(superuser, survivor, duplicate)
    ProjectClientAccessPolicy.objects.create(project=project, recipient=survivor.user,
                                             permissions={'production': {'admin_password': True}})

    assert 'client_access_grants' in _codes(client_merge.client_merge_undo_blockers(_step(result)))
    assert engine.preview_undo(result['operation_id'])['blocked'] is True


def test_empty_recipient_policy_blocks_undo(superuser):
    """Fails if even an empty new recipient policy is silently orphaned by moving its project back."""
    survivor, duplicate = client_pair()
    project = make_client_project(duplicate)
    _, result = run_client_merge(superuser, survivor, duplicate)
    ProjectClientAccessPolicy.objects.create(project=project, recipient=survivor.user, permissions={})

    assert 'client_access_grants' in _codes(client_merge.client_merge_undo_blockers(_step(result)))


def test_billing_code_transfer_is_reversed_without_resetting_the_counter(superuser):
    """Fails if reversing the reserved code transfer collides with S or loses D's counter."""
    survivor, duplicate = client_pair(billing_code='DUP')
    sequence = ClientDocumentNumberSequence.objects.create(client_profile=duplicate, last_value=42)
    _, result = run_client_merge(superuser, survivor, duplicate)

    undo(superuser, result['operation_id'])

    assert UserProfile.objects.get(pk=survivor.pk).billing_code is None
    assert UserProfile.objects.get(pk=duplicate.pk).billing_code == 'DUP'
    sequence.refresh_from_db()
    assert (sequence.client_profile_id, sequence.last_value) == (duplicate.pk, 42)


def test_transferred_document_root_returns_to_its_original_client(superuser):
    """Fails if undo restores a root in multiple constraint-violating UPDATEs."""
    survivor, duplicate = client_pair()
    root = make_folder('Cliente', managed_client=duplicate.user, client_user=duplicate.user)
    _, result = run_client_merge(superuser, survivor, duplicate)

    undo(superuser, result['operation_id'])

    root.refresh_from_db()
    assert (root.client_user_id, root.managed_client_id, root.is_archived) == (duplicate.user_id, duplicate.user_id, False)


def test_demoted_communication_root_regains_its_managed_pointer(superuser):
    """Fails if undo cannot restore D's managed communication root alongside S's root."""
    survivor, duplicate = client_pair()
    CommunicationThread.objects.create(title='Principal', client=survivor, managed_client=survivor)
    root = CommunicationThread.objects.create(title='Anterior', client=duplicate, managed_client=duplicate)
    _, result = run_client_merge(superuser, survivor, duplicate)

    undo(superuser, result['operation_id'])

    root.refresh_from_db()
    assert (root.client_id, root.managed_client_id) == (duplicate.pk, duplicate.pk)


def test_existing_survivor_proposal_snapshot_returns_to_its_previous_values(superuser):
    """Fails if undo re-runs identity signals and overwrites the recorded pre-merge snapshot."""
    survivor, duplicate = client_pair(phone='300123')
    proposal = BusinessProposal.objects.create(title='Existente', client=survivor, client_phone='Snapshot anterior')
    _, result = run_client_merge(superuser, survivor, duplicate)

    undo(superuser, result['operation_id'])

    assert BusinessProposal.objects.get(pk=proposal.pk).client_phone == 'Snapshot anterior'


def test_adopted_email_returns_to_the_duplicate_in_safe_unique_order(superuser):
    """Fails if S releases D's adopted username too late for the reverse identity transfer."""
    survivor = make_client('provisional')
    duplicate = make_client('real@example.com', email='real@example.com')
    _, result = run_client_merge(superuser, survivor, duplicate, rule_id='CL2')

    undo(superuser, result['operation_id'])

    survivor.user.refresh_from_db()
    duplicate.user.refresh_from_db()
    assert (survivor.user.email, survivor.user.username) == ('provisional@temp.example.com', 'provisional')
    assert (duplicate.user.email, duplicate.user.username) == ('real@example.com', 'real@example.com')


def test_audit_receipts_survive_undo(superuser):
    """Fails if undo removes durable merge receipts instead of restoring only live columns."""
    survivor, duplicate = client_pair()
    _, result = run_client_merge(superuser, survivor, duplicate)
    receipt_ids = set(AccountingChangeLog.objects.filter(entity_type='client').values_list('pk', flat=True))

    undo(superuser, result['operation_id'])

    assert receipt_ids <= set(AccountingChangeLog.objects.values_list('pk', flat=True))
    assert DataIntegrityOperation.objects.filter(reverts_id=result['operation_id']).count() == 1


def test_new_duplicate_root_blocks_undo(superuser):
    """Fails if undo overwrites a new managed root created for the retired duplicate."""
    survivor, duplicate = client_pair()
    make_folder('Anterior', managed_client=duplicate.user, client_user=duplicate.user)
    _, result = run_client_merge(superuser, survivor, duplicate)
    make_folder('Nueva', managed_client=duplicate.user, client_user=duplicate.user)

    assert 'container_taken' in _codes(client_merge.client_merge_undo_blockers(_step(result)))


def test_changed_duplicate_password_blocks_undo(superuser):
    """Fails if restoring D's account activation would also revive a password added after the merge."""
    survivor, duplicate = client_pair()
    _, result = run_client_merge(superuser, survivor, duplicate)
    duplicate.user.set_password('test-only-password')
    duplicate.user.save(update_fields=['password'])

    assert 'duplicate_access_changed' in _codes(client_merge.client_merge_undo_blockers(_step(result)))


def test_reactivated_duplicate_blocks_undo(superuser):
    """Fails if undo restores a retired login identity into a newly activated duplicate account."""
    survivor, duplicate = client_pair()
    duplicate.user.set_password('test-only-password')
    duplicate.user.save(update_fields=['password'])
    _, result = run_client_merge(superuser, survivor, duplicate)
    duplicate.user.is_active = True
    duplicate.user.save(update_fields=['is_active'])

    assert 'duplicate_access_changed' in _codes(client_merge.client_merge_undo_blockers(_step(result)))
    assert engine.preview_undo(result['operation_id'])['blocked'] is True


def test_newly_onboarded_duplicate_blocks_undo(superuser):
    """Fails if restoring D's original active flag would also enable newly added platform onboarding."""
    survivor, duplicate = client_pair()
    duplicate.user.is_active = True
    duplicate.user.save(update_fields=['is_active'])
    _, result = run_client_merge(superuser, survivor, duplicate)
    UserProfile.objects.filter(pk=duplicate.pk).update(is_onboarded=True)

    assert 'duplicate_access_changed' in _codes(client_merge.client_merge_undo_blockers(_step(result)))
    assert engine.preview_undo(result['operation_id'])['blocked'] is True


def test_staff_actor_cannot_undo_a_client_merge(superuser, admin_user):
    """Fails if the engine's exact-restore fallback bypasses a merge's superuser requirement."""
    survivor, duplicate = client_pair()
    _, result = run_client_merge(superuser, survivor, duplicate)
    preview = engine.preview_undo(result['operation_id'])

    with pytest.raises(PermissionDenied):
        engine.undo_operation(result['operation_id'], actor=admin_user, reason='No autorizado',
                              request_id='staff-undo-refusal', expected_impact_hash=preview['impact_hash'])

    assert UserProfile.objects.get(pk=duplicate.pk).archived_at is not None
    assert not DataIntegrityOperation.objects.filter(reverts_id=result['operation_id']).exists()


def test_missing_duplicate_profile_blocks_undo_without_a_preview_error(superuser):
    """Fails if a deleted profile raises an unhandled lookup error instead of a blocked undo preview."""
    survivor, duplicate = client_pair()
    _, result = run_client_merge(superuser, survivor, duplicate)
    duplicate.user.delete()

    preview = engine.preview_undo(result['operation_id'])

    assert 'changed_since' in _codes(preview['blockers'])
    assert preview['blocked'] is True


def test_new_secure_link_receipt_for_duplicate_blocks_undo(superuser):
    """Fails if undo collides with a new D-owned secure-link idempotency receipt."""
    survivor, duplicate = client_pair()
    request = uuid.UUID('12345678-1234-5678-1234-567812345678')
    make_secure_link(duplicate, '1' * 64, request)
    _, result = run_client_merge(superuser, survivor, duplicate)
    make_secure_link(duplicate, '2' * 64, request)

    assert 'association_collision' in _codes(client_merge.client_merge_undo_blockers(_step(result)))
    assert engine.preview_undo(result['operation_id'])['blocked'] is True


def test_cedula_duplicate_undo_restores_the_original_finding(superuser):
    """Fails if a CL3 merge cannot be undone through the engine with its original identity evidence."""
    survivor, duplicate = client_pair(cedula='12345')
    UserProfile.objects.filter(pk=survivor.pk).update(cedula='12.345')
    [finding] = only(scan(rule_ids=['CL3']), 'CL3')
    _, result = run_client_merge(superuser, survivor, duplicate, rule_id='CL3')

    undo(superuser, result['operation_id'])

    [restored] = only(scan(rule_ids=['CL3']), 'CL3')
    assert restored.fingerprint == finding.fingerprint
