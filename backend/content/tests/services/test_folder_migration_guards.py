"""Exceptional destinations retain the same rules in preview and apply."""

import pytest

from content.models import Document, DocumentOwnershipOperation
from content.services import folder_migration_service as service
from content.tests.mcp_parity import assert_no_writes, ownership_state
from content.tests.services.test_folder_migration import (
    apply,
    migration_input,
)
from content.tests.services.test_folder_migration import (
    migration_case as migration_case,  # noqa: PLC0414 -- Re-export the shared pytest fixture.
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('strategy', ['adopt_source', 'move_contents'])
def test_archived_portal_exposure_requires_an_explicit_migration_policy(migration_case, strategy):
    case = migration_case
    archived = Document.objects.create(
        title='Archived visible history', folder=case.child, is_client_visible=True, is_archived=True,
    )
    before = ownership_state()
    args = migration_input(case, strategy)
    blocked = assert_no_writes(service.preview_folder_migration, args, actor=case.actor)

    with pytest.raises(service.FolderMigrationError) as error:
        service.apply_folder_migration(blocked['plan_token'], 'No permitir exposición latente', 'latent-blocked', actor=case.actor)

    assert blocked['can_apply'] is False
    assert error.value.details['blockers'] == blocked['blockers']
    assert [(row['code'], row['resource_id']) for row in blocked['blockers']] == [('portal_exposure_latent', archived.pk)]
    assert ownership_state() == before
    assert not DocumentOwnershipOperation.objects.exists()
    _plan, report = apply(case, {**args, 'portal_policy': 'hide_new_exposure'})
    archived.refresh_from_db()
    assert (archived.client_user_id, archived.project_id) == (case.owner.user_id, report['project_id'])
    assert (archived.is_archived, archived.is_client_visible) == (True, False)
    undo = service.preview_undo_migration(report['migration_id'])
    service.undo_migration(report['migration_id'], undo['impact_hash'], 'Restaurar exposición original', 'undo-latent', actor=case.actor)
    assert ownership_state() == before


def test_adoption_decision_to_source_uses_future_owner(migration_case):
    case = migration_case
    before = ownership_state()
    args = migration_input(case, document_decisions=[
        {'document_id': case.loose.pk, 'action': 'move', 'destination_folder_id': case.source.pk},
    ])

    plan, report = apply(case, args)

    expected = next(row['after'] for row in plan['rows'] if row['resource_type'] == 'document' and row['id'] == case.loose.pk)
    case.loose.refresh_from_db()
    assert expected['project_id'] == 'new_project'
    assert (case.loose.folder_id, case.loose.project_id, case.loose.client_user_id) == (case.source.pk, report['project_id'], case.owner.user_id)
    undo = service.preview_undo_migration(report['migration_id'])
    service.undo_migration(report['migration_id'], undo['impact_hash'], 'Restaurar decisión interna', 'undo-internal', actor=case.actor)
    assert ownership_state() == before


def test_pinned_folder_cannot_become_project_root(migration_case, initialized_contract_mirrors):
    case = migration_case
    pinned = initialized_contract_mirrors.mirror_folder
    args = {**migration_input(case), 'source_folder_id': pinned.pk}
    before = ownership_state()
    plan = assert_no_writes(service.preview_folder_migration, args, actor=case.actor)

    with pytest.raises(service.FolderMigrationError) as error:
        service.apply_folder_migration(plan['plan_token'], 'Conservar los espejos sin dueño', 'pinned-root', actor=case.actor)

    assert 'contract_mirror_folder_pinned' in {row['code'] for row in error.value.details['blockers']}
    assert ownership_state() == before
