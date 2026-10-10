"""Panel API of the data-integrity engine: access, validation, no-store reads and 409 contracts."""
import pytest
from accounts.models import ProjectPhase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from content.models import DataIntegrityOperation
from content.tests.data_integrity_helpers import (
    make_phase,
    make_project,
    make_proposal,
    only,
    scan,
    selection,
)

pytestmark = pytest.mark.django_db

RULES = reverse('panel-data-integrity-rules')
FINDINGS = reverse('panel-data-integrity-findings')
PREVIEW = reverse('panel-data-integrity-fix-preview')
APPLY = reverse('panel-data-integrity-fix-apply')
OPERATIONS = reverse('panel-data-integrity-operations')


@pytest.fixture
def gap(make_client_profile):
    profile = make_client_profile(company='Kore SAS')
    project = make_project(profile, 'Kore')
    make_phase(project, make_proposal(profile, 'Uno'), 1)
    make_phase(project, make_proposal(profile, 'Dos'), 4)
    [finding] = only(scan(), 'PJ7')
    return {'profile': profile, 'project': project, 'finding': finding}


def _batch(gap, **extra):
    return {'scope': {'kind': 'project', 'id': gap['project'].pk}, 'fixes': [selection(gap['finding'])], **extra}


def _apply(admin_client, gap, request_id='panel-1'):
    preview = admin_client.post(PREVIEW, _batch(gap), format='json').data
    return admin_client.post(APPLY, _batch(gap, reason='Prueba', request_id=request_id,
                                           expected_impact_hash=preview['impact_hash']), format='json')


@pytest.mark.parametrize(('method', 'url'), [
    ('get', RULES), ('get', FINDINGS), ('post', PREVIEW), ('post', APPLY), ('get', OPERATIONS),
    ('get', '/api/projects/data-integrity/operations/1/undo/'),
])
def test_non_staff_users_are_refused_on_every_route(method, url):
    """Fails if a client or anonymous session can read findings or apply fixes."""
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user(username='plain', password='x'))

    assert getattr(client, method)(url, {}, format='json').status_code == 403


def test_reads_are_private_and_list_the_catalog(admin_client):
    """Fails if findings or the catalog can be cached, or the catalog misses a registered rule."""
    response = admin_client.get(RULES)

    assert response['Cache-Control'] == 'no-store'
    assert 'PJ7' in {rule['id'] for rule in response.data['rules']}


def test_findings_are_filtered_by_project_scope(admin_client, gap, make_client_profile):
    """Fails if a project scope leaks another project's findings."""
    other = make_client_profile(company='Otra')
    make_phase(make_project(other, 'Otra'), make_proposal(other, 'X'), 3)

    response = admin_client.get(FINDINGS, {'scope_kind': 'project', 'scope_id': gap['project'].pk, 'rule_ids': 'PJ7'})

    assert [row['fingerprint'] for row in response.data['results']] == [gap['finding'].fingerprint]
    assert response.data['scope']['label'] == 'Kore'


def test_scope_query_returns_candidates_unless_exactly_one_matches(admin_client, gap, make_client_profile):
    """Fails if a free-text client search guesses between several clients."""
    make_client_profile(company='Kore Labs')

    ambiguous = admin_client.get(FINDINGS, {'scope_kind': 'client', 'scope_query': 'kore'})
    exact = admin_client.get(FINDINGS, {'scope_kind': 'client', 'scope_query': 'Kore SAS', 'rule_ids': 'PJ7'})

    assert len(ambiguous.data['scope_candidates']) == 2
    assert ambiguous.data['results'] == []
    assert exact.data['scope']['id'] == gap['profile'].pk
    assert exact.data['count'] == 1


@pytest.mark.parametrize('params', [
    {'scope_kind': 'client'},
    {'scope_kind': 'document', 'scope_query': 'contrato'},
    {'scope_kind': 'all', 'domains': 'facturas'},
])
def test_invalid_finding_queries_are_rejected(admin_client, params):
    """Fails if an incomplete or misspelled query silently scans everything."""
    assert admin_client.get(FINDINGS, params).status_code == 400


def test_unknown_scope_record_is_not_found(admin_client):
    """Fails if a scan on a missing client answers as if it were clean."""
    assert admin_client.get(FINDINGS, {'scope_kind': 'client', 'scope_id': 999999}).status_code == 404


def test_preview_is_private_and_writes_nothing(admin_client, gap):
    """Fails if previewing a batch changes data or can be cached."""
    response = admin_client.post(PREVIEW, _batch(gap), format='json')

    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert sorted(ProjectPhase.objects.values_list('order', flat=True)) == [1, 4]


@pytest.mark.parametrize('fixes', [[], 'duplicate'])
def test_empty_or_repeated_selections_are_rejected(admin_client, gap, fixes):
    """Fails if a batch with nothing to do, or the same finding twice, reaches the engine."""
    if fixes == 'duplicate':
        fixes = [selection(gap['finding'])] * 2

    response = admin_client.post(PREVIEW, {'scope': {'kind': 'all'}, 'fixes': fixes}, format='json')

    assert response.status_code == 400


def test_apply_with_a_stale_hash_answers_409(admin_client, gap):
    """Fails if a confirmation against an outdated preview is accepted or answered as a 400."""
    response = admin_client.post(APPLY, _batch(gap, reason='Prueba', request_id='stale',
                                               expected_impact_hash='0' * 64), format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'stale_impact'
    assert not DataIntegrityOperation.objects.exists()


def test_apply_records_a_panel_operation_and_undo_restores_it(admin_client, gap):
    """Fails if the panel cannot apply and then undo a fix, or the log loses its origin."""
    applied = _apply(admin_client, gap)
    undo_url = reverse('panel-data-integrity-operation-undo', args=[applied.data['operation_id']])
    undo_preview = admin_client.get(undo_url).data

    undone = admin_client.post(undo_url, {'reason': 'Volver', 'request_id': 'panel-undo',
                                          'expected_impact_hash': undo_preview['impact_hash']}, format='json')

    assert applied.status_code == 200
    assert DataIntegrityOperation.objects.get(pk=applied.data['operation_id']).source == 'panel'
    assert undone.status_code == 200
    assert sorted(ProjectPhase.objects.values_list('order', flat=True)) == [1, 4]


def test_operation_log_lists_newest_first(admin_client, gap):
    """Fails if the log hides an applied fix."""
    applied = _apply(admin_client, gap)

    response = admin_client.get(OPERATIONS)

    assert response['Cache-Control'] == 'no-store'
    assert response.data['results'][0]['operation_id'] == applied.data['operation_id']


def test_undo_of_a_missing_operation_is_not_found(admin_client):
    """Fails if an unknown operation id answers with a preview."""
    assert admin_client.get(reverse('panel-data-integrity-operation-undo', args=[999999])).status_code == 404
