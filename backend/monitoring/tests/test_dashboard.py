"""Behavioral contracts for filtered aggregates and a stable multi-page consultation."""
import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from monitoring.models import Case, CaseActivity, Delivery, Source
from monitoring.tests.dashboard_fixtures import create_cases

URL = '/api/monitoring/cases/'
pytest_plugins = ('monitoring.tests.dashboard_fixtures',)


@pytest.fixture(name='dashboard_fixture')
def _dashboard_fixture(dashboard):
    return dashboard


def test_summary_counts_cases_beyond_the_visible_page(dashboard_fixture):
    """Fails if dashboard summary only counts the first page of matching cases."""
    create_cases(dashboard_fixture['source'])
    response = dashboard_fixture['client'].get(URL, {'snapshot': 'new', 'kind': 'project'}).json()
    assert len(response['results']) == 25
    assert response['summary']['total'] == 53
    assert response['summary']['active']['critical'] == 53
    assert response['summary']['followup'] == 27


def test_snapshot_pagination_keeps_membership_after_new_detection(dashboard_fixture):
    """Fails if a consultation page incorporates later detections."""
    cases = create_cases(dashboard_fixture['source'], 26)
    first = dashboard_fixture['client'].get(URL, {'snapshot': 'new'}).json()
    Case.objects.filter(pk=cases[0].pk).update(title='Updated after consultation')
    create_cases(Source.objects.create(resource=dashboard_fixture['project'], key='another', name='Otra'), 1)
    second = dashboard_fixture['client'].get(URL, {'snapshot': first['snapshot'], 'page': 2}).json()
    assert second['count'] == 26
    assert len({row['id'] for row in first['results'] + second['results']}) == 26
    assert second['results'][0]['title'] == 'Caso 0'


def test_snapshot_is_bound_to_the_filter_set(dashboard_fixture):
    """Fails if a snapshot token accepts filters from another consultation."""
    create_cases(dashboard_fixture['source'], 1)
    first = dashboard_fixture['client'].get(URL, {'snapshot': 'new', 'severity': 'critical'}).json()
    response = dashboard_fixture['client'].get(URL, {'snapshot': first['snapshot'], 'severity': 'warning'})
    assert response.status_code == 409


def test_snapshot_is_bound_to_the_actor(dashboard_fixture):
    """Fails if one operator can reuse another operator's frozen consultation."""
    first = dashboard_fixture['client'].get(URL, {'snapshot': 'new'}).json()
    actor = get_user_model().objects.create_user(username='another-operator', is_staff=True)
    UserProfile.objects.create(
        user=actor,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
    )
    client = APIClient()
    client.force_login(actor)
    assert client.get(URL, {'snapshot': first['snapshot']}).status_code == 409


def test_expired_snapshot_requests_explicit_refresh(dashboard_fixture):
    """Fails if an expired consultation silently serves a partial page."""
    first = dashboard_fixture['client'].get(URL, {'snapshot': 'new'}).json()
    cache.delete(f"monitoring:snapshot:{first['snapshot']}")
    assert dashboard_fixture['client'].get(URL, {'snapshot': first['snapshot']}).status_code == 409


def test_inverted_dates_are_rejected(dashboard_fixture):
    """Fails if a case search accepts a final date before its initial date."""
    response = dashboard_fixture['client'].get(URL, {'since': '2026-11-12', 'until': '2026-11-10'})
    assert response.status_code == 400
    assert 'until' in response.json()


@pytest.mark.parametrize('day', ['bad-date', '2026-02-30'])
def test_invalid_date_is_rejected(dashboard_fixture, day):
    """Fails if malformed calendar dates reach the monitoring query."""
    assert dashboard_fixture['client'].get(URL, {'since': day}).status_code == 400


def test_combined_filters_match_summary_membership(dashboard_fixture):
    """Fails if filtered indicators count cases outside the displayed result set."""
    create_cases(dashboard_fixture['source'], 3)
    response = dashboard_fixture['client'].get(URL, {'snapshot': 'new', 'resource': dashboard_fixture['project'].pk, 'source': dashboard_fixture['source'].pk, 'severity': 'critical', 'state': 'pending', 'search': 'Caso 2'}).json()
    assert response['count'] == response['summary']['total'] == 1
    assert response['results'][0]['title'] == 'Caso 2'


def test_active_condition_filter_includes_a_resolved_case(dashboard_fixture):
    """Fails if technical condition filtering drops an active case marked resolved by an operator."""
    case = create_cases(dashboard_fixture['source'], 1)[0]
    Case.objects.filter(pk=case.pk).update(state='resolved', condition='active')

    response = dashboard_fixture['client'].get(URL, {'condition': 'active'}).json()

    assert response['count'] == 1
    assert response['results'][0]['id'] == case.pk
    assert response['results'][0]['state'] == 'resolved'


def test_followup_filter_excludes_resolved_cases(dashboard_fixture):
    """Fails if follow-up filtering omits pending work or includes a resolved case."""
    pending, reviewing, recovered, resolved = create_cases(dashboard_fixture['source'], 4)
    Case.objects.filter(pk=reviewing.pk).update(state='reviewing')
    Case.objects.filter(pk=recovered.pk).update(condition='recovered')
    Case.objects.filter(pk=resolved.pk).update(state='resolved', condition='active')

    response = dashboard_fixture['client'].get(URL, {'followup': 'true'}).json()

    assert response['count'] == 3
    assert {row['id'] for row in response['results']} == {pending.pk, reviewing.pk, recovered.pk}


def test_source_health_distinguishes_missing_data(dashboard_fixture):
    """Fails if a source without observations is reported as current."""
    Source.objects.create(resource=dashboard_fixture['project'], key='never', name='Nunca recibió')
    response = dashboard_fixture['client'].get(URL, {'snapshot': 'new', 'kind': 'project'}).json()
    assert response['summary']['total'] == 0
    assert response['summary']['sources'] == {'current': 1, 'no_data': 1}


def test_detail_paginates_notes_independently(dashboard_fixture):
    """Fails if detail note pagination changes its independent delivery page."""
    case = create_cases(dashboard_fixture['source'], 1)[0]
    CaseActivity.objects.bulk_create([CaseActivity(case=case, kind='note', text=f'Nota {index}') for index in range(30)])
    Delivery.objects.create(source=dashboard_fixture['source'], case=case, external_id='fixture-delivery', digest='a' * 64, kind='detection', observed_at=case.last_seen_at)
    response = dashboard_fixture['client'].get(f'{URL}{case.pk}/', {'activities_page': 2, 'deliveries_page': 1}).json()
    assert len(response['activities']['results']) == 5
    assert response['deliveries']['count'] == 1
    assert len(response['deliveries']['results']) == 1


def test_detail_snapshot_keeps_history_pages_unchanged_after_records_arrive(dashboard_fixture):
    """Fails if a later page includes notes or deliveries created after its history bound."""
    case = create_cases(dashboard_fixture['source'], 1)[0]
    activities = CaseActivity.objects.bulk_create([
        CaseActivity(case=case, kind='note', text=f'Nota {number}')
        for number in range(30)
    ])
    deliveries = Delivery.objects.bulk_create([
        Delivery(
            source=dashboard_fixture['source'], case=case, external_id=f'history-{number}',
            digest=f'{number:064x}', kind='detection', observed_at=case.last_seen_at,
        )
        for number in range(30)
    ])

    first = dashboard_fixture['client'].get(
        f'{URL}{case.pk}/',
        {'history_snapshot': 'true', 'activities_page': 1, 'deliveries_page': 1},
    ).json()
    new_activity = CaseActivity.objects.create(case=case, kind='note', text='Nota posterior')
    new_delivery = Delivery.objects.create(
        source=dashboard_fixture['source'], case=case, external_id='history-after-bound',
        digest='f' * 64, kind='detection', observed_at=case.last_seen_at,
    )
    second = dashboard_fixture['client'].get(
        f'{URL}{case.pk}/',
        {
            'history_snapshot': 'true',
            'activities_page': 2,
            'deliveries_page': 2,
            'activities_before': first['history_bounds']['activities'],
            'deliveries_before': first['history_bounds']['deliveries'],
        },
    ).json()

    activity_ids = {row['id'] for row in first['activities']['results'] + second['activities']['results']}
    delivery_ids = {row['id'] for row in first['deliveries']['results'] + second['deliveries']['results']}
    assert first['history_bounds'] == second['history_bounds']
    assert second['activities']['count'] == second['deliveries']['count'] == 30
    assert activity_ids == {activity.pk for activity in activities}
    assert delivery_ids == {delivery.pk for delivery in deliveries}
    assert new_activity.pk not in activity_ids
    assert new_delivery.pk not in delivery_ids


def test_unknown_project_does_not_fall_back_to_all_hosts(dashboard_fixture):
    """Fails if an unknown project query exposes every monitored server."""
    response = dashboard_fixture['client'].get('/api/monitoring/status/', {'kind': 'project', 'resource': 999999}).json()
    assert response['hosts'] == []


def test_out_of_range_snapshot_page_uses_last_page(dashboard_fixture):
    """Fails if an out-of-range snapshot page has no valid final result page."""
    create_cases(dashboard_fixture['source'], 26)
    response = dashboard_fixture['client'].get(URL, {'snapshot': 'new', 'page': 100}).json()
    assert response['page'] == 2
    assert len(response['results']) == 1
