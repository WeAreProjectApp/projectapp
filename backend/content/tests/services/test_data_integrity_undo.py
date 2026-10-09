"""Engine undo contract: exact restore, stale and changed-since guards, one undo per operation."""
from datetime import timedelta

import pytest
from accounts.models import Project, ProjectPhase

from content.models import DataIntegrityOperation
from content.services.data_integrity import engine
from content.services.data_integrity.types import IntegrityConflict
from content.tests.data_integrity_helpers import (
    apply,
    make_phase,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
    undo,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def applied(make_client_profile, superuser):
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    first = make_phase(project, make_proposal(profile, 'Uno'), 2)
    second = make_phase(project, make_proposal(profile, 'Dos'), 5)
    [finding] = only(scan(), 'PJ7')
    _, result = apply(superuser, [selection(finding)])
    return {'project': project, 'first': first, 'second': second, 'operation_id': result['operation_id']}


def _orders(project):
    return list(ProjectPhase.objects.filter(project=project).order_by('pk').values_list('order', flat=True))


def test_undo_restores_the_previous_values_exactly(applied, superuser):
    """Fails if undo leaves any renumbered phase at its fixed value."""
    assert _orders(applied['project']) == [1, 2]

    undo(superuser, applied['operation_id'])

    assert _orders(applied['project']) == [2, 5]


def test_undo_is_logged_as_an_operation_that_reverts_the_original(applied, superuser):
    """Fails if the reversal is not auditable or not linked to what it reverted."""
    _, result = undo(superuser, applied['operation_id'])

    reversal = DataIntegrityOperation.objects.get(pk=result['operation_id'])
    assert reversal.kind == DataIntegrityOperation.Kind.UNDO
    assert reversal.reverts_id == applied['operation_id']
    assert engine.operation_summary(DataIntegrityOperation.objects.get(pk=applied['operation_id']))['reverted_by'] == reversal.pk


def test_preview_undo_is_stable_and_lists_the_steps(applied):
    """Fails if two undo previews disagree or hide which rule they revert."""
    first = engine.preview_undo(applied['operation_id'])
    second = engine.preview_undo(applied['operation_id'])

    assert first['impact_hash'] == second['impact_hash']
    assert first['steps'][0]['rule_id'] == 'PJ7'
    assert first['blocked'] is False


def test_a_later_edit_blocks_the_undo_as_changed_since(applied, superuser):
    """Fails if undo would overwrite a value someone changed after the fix."""
    ProjectPhase.objects.filter(pk=applied['first'].pk).update(order=7)

    preview = engine.preview_undo(applied['operation_id'])

    assert [entry['code'] for entry in preview['blockers']] == ['changed_since']
    with pytest.raises(IntegrityConflict) as error:
        engine.undo_operation(applied['operation_id'], actor=superuser, reason='x',
                              request_id='undo-refusal', expected_impact_hash=preview['impact_hash'])
    assert error.value.detail['code'] == 'undo_blocked'
    assert _orders(applied['project']) == [7, 2]


def test_later_save_blocks_undo_after_a_queryset_fix(make_client_profile, superuser, monkeypatch):
    """A mirror fix leaves updated_at unchanged, but a later save still makes undo stale."""
    project = make_project(make_client_profile())
    Project.objects.filter(pk=project.pk).update(status=Project.STATUS_SUSPENDED)
    [finding] = only(scan(rule_ids=['PJ6']), 'PJ6')
    timestamp = project.updated_at
    _, result = apply(superuser, [selection(finding)])
    project.refresh_from_db()
    assert project.updated_at == timestamp
    monkeypatch.setattr('django.db.models.fields.timezone.now', lambda: timestamp + timedelta(seconds=1))
    project.save(update_fields=['updated_at'])

    preview = engine.preview_undo(result['operation_id'])

    assert [entry['code'] for entry in preview['blockers']] == ['changed_since']
    assert preview['blockers'][0]['records'] == [
        {'model': 'accounts.project', 'id': project.pk, 'field': 'updated_at'},
    ]
    with pytest.raises(IntegrityConflict) as error:
        undo(superuser, result['operation_id'])
    assert error.value.detail['code'] == 'undo_blocked'
    project.refresh_from_db()
    assert project.status == Project.STATUS_DEVELOPMENT


def test_an_operation_can_be_undone_only_once(applied, superuser):
    """Fails if a second undo is offered once the first one restored the data."""
    undo(superuser, applied['operation_id'])

    codes = {entry['code'] for entry in engine.preview_undo(applied['operation_id'])['blockers']}

    assert 'already_reverted' in codes


def test_an_undo_is_not_itself_undoable(applied, superuser):
    """Fails if the reversal log entry offers its own undo."""
    _, result = undo(superuser, applied['operation_id'])

    codes = {entry['code'] for entry in engine.preview_undo(result['operation_id'])['blockers']}

    assert 'not_undoable' in codes


def test_undo_replays_for_the_same_request_id(applied, superuser):
    """Fails if a retried undo writes twice or creates a second reversal."""
    request_id = 'undo-replay'
    _, first = undo(superuser, applied['operation_id'], request_id=request_id)

    again = engine.undo_operation(applied['operation_id'], actor=superuser, reason='x',
                                  request_id=request_id, expected_impact_hash='0' * 64)

    assert again['idempotent'] is True
    assert again['operation_id'] == first['operation_id']
    assert DataIntegrityOperation.objects.filter(kind='undo').count() == 1


def test_undo_with_a_stale_hash_is_refused(applied, superuser):
    """Fails if an undo confirmed against an outdated preview still runs."""
    with pytest.raises(IntegrityConflict) as error:
        engine.undo_operation(applied['operation_id'], actor=superuser, reason='x',
                              request_id='undo-refusal', expected_impact_hash='0' * 64)

    assert error.value.detail['code'] == 'stale_impact'
    assert _orders(applied['project']) == [1, 2]
