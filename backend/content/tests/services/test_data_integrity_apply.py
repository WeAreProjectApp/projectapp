"""Engine apply contract: hash-bound preview, blockers, idempotency and the append-only log."""

import pytest
from accounts.models import ProjectPhase

from content.models import DataIntegrityOperation
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope
from content.services.data_integrity.types import IntegrityConflict
from content.tests.data_integrity_helpers import (
    apply,
    make_phase,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gap(make_client_profile):
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    first = make_phase(project, make_proposal(profile, 'Fase uno'), 1)
    third = make_phase(project, make_proposal(profile, 'Fase dos'), 3)
    return {'profile': profile, 'project': project, 'first': first, 'third': third}


def _orders(project):
    return list(ProjectPhase.objects.filter(project=project).order_by('pk').values_list('order', flat=True))


def test_scan_reports_a_phase_order_gap_with_the_renumbering_suggestion(gap):
    """Fails if a 1,3 phase sequence goes unreported or the suggestion is not 1,2."""
    [finding] = only(scan(), 'PJ7')

    assert finding.suggestion == {'orders': {str(gap['first'].pk): 1, str(gap['third'].pk): 2}}
    assert finding.subjects[0].pk == gap['project'].pk


def test_consecutive_phase_orders_produce_no_finding(make_client_profile):
    """Fails if a healthy 1,2 sequence is flagged."""
    profile = make_client_profile()
    project = make_project(profile)
    make_phase(project, make_proposal(profile, 'A'), 1)
    make_phase(project, make_proposal(profile, 'B'), 2)

    assert only(scan(), 'PJ7') == []


def test_fingerprint_is_identical_in_full_client_and_project_scans(gap):
    """Fails if the scope leaks into the fingerprint, which would break previews across scopes."""
    full = only(scan(), 'PJ7')[0].fingerprint

    assert only(scan('client', gap['profile'].pk), 'PJ7')[0].fingerprint == full
    assert only(scan('project', gap['project'].pk), 'PJ7')[0].fingerprint == full


def test_preview_writes_nothing_and_repeats_the_same_hash(gap, superuser):
    """Fails if previewing changes data or if two identical previews disagree."""
    [finding] = only(scan(), 'PJ7')
    scope = resolve_scope('all')

    first = engine.preview_fixes(scope, [selection(finding)], actor=superuser)
    second = engine.preview_fixes(scope, [selection(finding)], actor=superuser)

    assert first['impact_hash'] == second['impact_hash']
    assert first['blocked'] is False
    assert _orders(gap['project']) == [1, 3]


def test_apply_renumbers_and_records_exact_items(gap, superuser):
    """Fails if the fix does not renumber or the log misses the before/after value."""
    [finding] = only(scan(), 'PJ7')

    _, result = apply(superuser, [selection(finding)])

    assert _orders(gap['project']) == [1, 2]
    operation = DataIntegrityOperation.objects.get(pk=result['operation_id'])
    [step] = operation.steps
    assert {'model': 'accounts.projectphase', 'pk': gap['third'].pk, 'field': 'order',
            'before': 3, 'after': 2, 'guard': False} in step['items']
    assert operation.source == 'service'
    assert operation.history_operation_id is not None
    assert only(scan(), 'PJ7') == []


def test_stale_preview_hash_is_refused_without_writing(gap, superuser):
    """Fails if data edited after the preview is overwritten by a stale confirmation."""
    [finding] = only(scan(), 'PJ7')
    scope = resolve_scope('all')
    preview = engine.preview_fixes(scope, [selection(finding)], actor=superuser)
    ProjectPhase.objects.filter(pk=gap['first'].pk).update(order=2)

    with pytest.raises(IntegrityConflict) as error:
        engine.apply_fixes(scope, [selection(finding)], actor=superuser, reason='x',
                           request_id='integrity-refusal', expected_impact_hash=preview['impact_hash'])

    assert error.value.detail['code'] == 'stale_impact'
    assert _orders(gap['project']) == [2, 3]
    assert not DataIntegrityOperation.objects.exists()


def test_a_finding_resolved_elsewhere_blocks_the_operation(gap, superuser):
    """Fails if a fix applies to a finding that disappeared after detection."""
    [finding] = only(scan(), 'PJ7')
    ProjectPhase.objects.filter(pk=gap['third'].pk).update(order=2)
    scope = resolve_scope('all')
    preview = engine.preview_fixes(scope, [selection(finding)], actor=superuser)

    assert preview['steps'][0]['blockers'][0]['code'] == 'finding_resolved'
    with pytest.raises(IntegrityConflict) as error:
        engine.apply_fixes(scope, [selection(finding)], actor=superuser, reason='x',
                           request_id='integrity-refusal', expected_impact_hash=preview['impact_hash'])
    assert error.value.detail['code'] == 'apply_blocked'


@pytest.mark.parametrize(('fix_kind', 'code'), [('report_only', 'report_only'), ('rename', 'fix_kind_unavailable')])
def test_kinds_the_finding_does_not_offer_are_blocked(gap, superuser, fix_kind, code):
    """Fails if a selection can force a fix kind the rule does not implement."""
    [finding] = only(scan(), 'PJ7')

    preview = engine.preview_fixes(resolve_scope('all'), [selection(finding, fix_kind)], actor=superuser)

    assert preview['steps'][0]['blockers'][0]['code'] == code
    assert preview['blocked'] is True


def test_same_request_id_replays_the_first_result(gap, superuser):
    """Fails if a retried confirmation applies twice or creates a second log entry."""
    [finding] = only(scan(), 'PJ7')
    request_id = 'integrity-replay'
    scope = resolve_scope('all')
    preview = engine.preview_fixes(scope, [selection(finding)], actor=superuser)
    first = engine.apply_fixes(scope, [selection(finding)], actor=superuser, reason='x',
                               request_id=request_id, expected_impact_hash=preview['impact_hash'])

    again = engine.apply_fixes(scope, [selection(finding)], actor=superuser, reason='x',
                               request_id=request_id, expected_impact_hash=preview['impact_hash'])

    assert again['idempotent'] is True
    assert again['operation_id'] == first['operation_id']
    assert DataIntegrityOperation.objects.count() == 1


def test_reusing_a_request_id_for_another_payload_conflicts(gap, superuser):
    """Fails if a request_id can silently cover a different selection or reason."""
    [finding] = only(scan(), 'PJ7')
    request_id = 'integrity-replay'
    apply(superuser, [selection(finding)], request_id=request_id)

    with pytest.raises(IntegrityConflict) as error:
        engine.apply_fixes(resolve_scope('all'), [selection(finding)], actor=superuser, reason='otro motivo',
                           request_id=request_id, expected_impact_hash='0' * 64)

    assert error.value.detail['code'] == 'request_conflict'


def test_two_independent_fixes_apply_in_one_operation(gap, make_client_profile, superuser):
    """Fails if a batch of disjoint fixes is refused or only partly applied."""
    other = make_client_profile(company='Otro')
    project = make_project(other, 'Otro')
    make_phase(project, make_proposal(other, 'X'), 2)
    findings = only(scan(), 'PJ7')

    _, result = apply(superuser, [selection(finding) for finding in findings])

    assert len(result['steps']) == 2
    assert _orders(gap['project']) == [1, 2]
    assert _orders(project) == [1]


def test_operation_log_is_append_only(gap, superuser):
    """Fails if a recorded operation can be edited, which would let undo restore forged values."""
    [finding] = only(scan(), 'PJ7')
    _, result = apply(superuser, [selection(finding)])
    operation = DataIntegrityOperation.objects.get(pk=result['operation_id'])

    with pytest.raises(TypeError):
        operation.save()
    with pytest.raises(TypeError):
        DataIntegrityOperation.objects.filter(pk=operation.pk).update(reason='editado')
