"""Behavioral contracts for filtered aggregates and a stable multi-page consultation."""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from monitoring.models import Case, CaseActivity, Delivery, Source
from monitoring.tests.dashboard_fixtures import dashboard, create_cases

URL = '/api/monitoring/cases/'


def test_summary_counts_cases_beyond_the_visible_page(dashboard):
    create_cases(dashboard['source'])
    response = dashboard['client'].get(URL, {'snapshot': 'new', 'kind': 'project'}).json()
    assert len(response['results']) == 25
    assert response['summary']['total'] == 53
    assert response['summary']['active']['critical'] == 53
    assert response['summary']['followup'] == 27


def test_snapshot_pagination_keeps_membership_after_new_detection(dashboard):
    cases = create_cases(dashboard['source'], 26)
    first = dashboard['client'].get(URL, {'snapshot': 'new'}).json()
    Case.objects.filter(pk=cases[0].pk).update(title='Updated after consultation')
    create_cases(Source.objects.create(resource=dashboard['project'], key='another', name='Otra'), 1)
    second = dashboard['client'].get(URL, {'snapshot': first['snapshot'], 'page': 2}).json()
    assert second['count'] == 26
    assert len({row['id'] for row in first['results'] + second['results']}) == 26
    assert second['results'][0]['title'] == 'Caso 0'


def test_snapshot_is_bound_to_the_filter_set(dashboard):
    create_cases(dashboard['source'], 1)
    first = dashboard['client'].get(URL, {'snapshot': 'new', 'severity': 'critical'}).json()
    response = dashboard['client'].get(URL, {'snapshot': first['snapshot'], 'severity': 'warning'})
    assert response.status_code == 409


def test_snapshot_is_bound_to_the_actor(dashboard):
    first = dashboard['client'].get(URL, {'snapshot': 'new'}).json()
    actor = get_user_model().objects.create_user(username='another-operator', is_staff=True)
    client = APIClient()
    client.force_login(actor)
    assert client.get(URL, {'snapshot': first['snapshot']}).status_code == 409


def test_expired_snapshot_requests_explicit_refresh(dashboard):
    first = dashboard['client'].get(URL, {'snapshot': 'new'}).json()
    cache.delete(f"monitoring:snapshot:{first['snapshot']}")
    assert dashboard['client'].get(URL, {'snapshot': first['snapshot']}).status_code == 409


def test_inverted_dates_are_rejected(dashboard):
    response = dashboard['client'].get(URL, {'since': '2026-11-12', 'until': '2026-11-10'})
    assert response.status_code == 400
    assert 'until' in response.json()


@pytest.mark.parametrize('day', ['bad-date', '2026-02-30'])
def test_invalid_date_is_rejected(dashboard, day):
    assert dashboard['client'].get(URL, {'since': day}).status_code == 400


def test_combined_filters_match_summary_membership(dashboard):
    create_cases(dashboard['source'], 3)
    response = dashboard['client'].get(URL, {'snapshot': 'new', 'resource': dashboard['project'].pk, 'source': dashboard['source'].pk, 'severity': 'critical', 'state': 'pending', 'search': 'Caso 2'}).json()
    assert response['count'] == response['summary']['total'] == 1
    assert response['results'][0]['title'] == 'Caso 2'


def test_source_coverage_distinguishes_missing_data(dashboard):
    Source.objects.create(resource=dashboard['project'], key='never', name='Nunca recibió')
    response = dashboard['client'].get(URL, {'snapshot': 'new', 'kind': 'project'}).json()
    assert response['summary']['total'] == 0
    assert response['summary']['sources'] == {'current': 1, 'no_data': 1}


def test_detail_paginates_notes_independently(dashboard):
    case = create_cases(dashboard['source'], 1)[0]
    CaseActivity.objects.bulk_create([CaseActivity(case=case, kind='note', text=f'Nota {index}') for index in range(30)])
    Delivery.objects.create(source=dashboard['source'], case=case, external_id='fixture-delivery', digest='a' * 64, kind='detection', observed_at=case.last_seen_at)
    response = dashboard['client'].get(f'{URL}{case.pk}/', {'activities_page': 2, 'deliveries_page': 1}).json()
    assert len(response['activities']['results']) == 5
    assert response['deliveries']['count'] == 1
    assert len(response['deliveries']['results']) == 1


def test_unknown_project_does_not_fall_back_to_all_hosts(dashboard):
    response = dashboard['client'].get('/api/monitoring/status/', {'kind': 'project', 'resource': 999999}).json()
    assert response['hosts'] == []


def test_out_of_range_snapshot_page_uses_last_page(dashboard):
    create_cases(dashboard['source'], 26)
    response = dashboard['client'].get(URL, {'snapshot': 'new', 'page': 100}).json()
    assert response['page'] == 2
    assert len(response['results']) == 1
