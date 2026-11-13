"""Response-size and query-growth contracts for the monitoring dashboard."""

from datetime import timedelta

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from monitoring.models import Case, Delivery, Report, Resource, Source, TelemetrySample

MAX_DASHBOARD_DOMAIN_SELECTS = 6
MAX_DASHBOARD_RESPONSE_BYTES = 256 * 1024


def _dashboard_client():
    """Return a staff session with the profile middleware expects for dashboard access."""
    user = get_user_model().objects.create_user(
        username='monitoring-dashboard-budget',
        is_staff=True,
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
    )
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def dashboard_client(db):
    """Return an authenticated administration session for measured dashboard requests."""
    return _dashboard_client()


@pytest.fixture
def telemetry_server(db):
    """Return one server and telemetry source for direct series contracts."""
    server = Resource.objects.create(
        key='dashboard-budget-server',
        name='Dashboard budget server',
        kind='server',
    )
    source = Source.objects.create(
        resource=server,
        key='telemetry',
        name='Telemetry',
        last_seen_at=timezone.now(),
    )
    return server, source


def _monitoring_selects(queries):
    """Return reads scoped to monitoring tables while excluding session and profile middleware reads."""
    return [
        query['sql']
        for query in queries
        if query['sql'].lstrip().upper().startswith('SELECT')
        and 'monitoring_' in query['sql'].lower()
    ]


def _model_route(model):
    """Return the dashboard list route for the requested persisted monitoring model."""
    return {
        Case: '/api/monitoring/cases/',
        Report: '/api/monitoring/reports/',
    }[model]


def _create_list_rows(model, total, *, start=0):
    """Create rows under distinct project resources and sources so relationship loading cannot hide N+1 reads."""
    server = Resource.objects.create(
        key=f'budget-list-server-{start}',
        name=f'Budget list server {start}',
        kind='server',
    )
    resources = Resource.objects.bulk_create([
        Resource(
            key=f'budget-list-project-{start + number}',
            name=f'Budget list project {start + number}',
            kind='project',
            server=server,
        )
        for number in range(total)
    ])
    sources = Source.objects.bulk_create([
        Source(
            resource=resource,
            key='integrity',
            name='Integrity',
            last_seen_at=timezone.now(),
        )
        for resource in resources
    ])
    observed_at = timezone.now()
    if model is Case:
        return Case.objects.bulk_create([
            Case(
                source=source,
                fingerprint=f'dashboard-budget-case-{start + number}',
                fingerprint_hash=f'{start + number:064x}',
                title=f'Dashboard budget case {start + number}',
                severity='warning',
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                detections=1,
            )
            for number, source in enumerate(sources)
        ])
    return Report.objects.bulk_create([
        Report(
            source=source,
            title=f'Dashboard budget report {start + number}',
            observed_at=observed_at,
            text='Monitoring budget payload.',
        )
        for number, source in enumerate(sources)
    ])


def _create_sample_metrics(server, source, metrics):
    """Persist a batch of telemetry metrics belonging to one server and source."""
    deliveries = Delivery.objects.bulk_create([
        Delivery(
            source=source,
            external_id=f'dashboard-budget-metric-{stamp.isoformat()}-{value}',
            digest=f'{index + int(stamp.timestamp()):064x}',
            kind='metric',
            observed_at=stamp,
        )
        for index, (stamp, value) in enumerate(metrics)
    ])
    TelemetrySample.objects.bulk_create([
        TelemetrySample(
            delivery=delivery,
            resource=server,
            observed_at=stamp,
            cpu_percent=value,
            cpu_count=2,
            load_1m=1.0,
            ram_total_bytes=1000,
            ram_used_bytes=500,
            disk_total_bytes=2000,
            disk_used_bytes=1000,
        )
        for delivery, (stamp, value) in zip(deliveries, metrics, strict=True)
    ])


def _create_samples(server, source, observed_at, cpu_percent, *, peak=False):
    """Persist telemetry deliveries and samples with optional higher CPU peak in the same bucket."""
    metrics = [(observed_at, cpu_percent)]
    if peak:
        metrics.append((observed_at + timedelta(minutes=1), 90.0))
    _create_sample_metrics(server, source, metrics)


def _create_complete_series(server, source, start):
    """Persist one complete 24-hour five-minute series with a higher value in its first bucket."""
    metrics = [(start + timedelta(minutes=5 * number), 10.0) for number in range(289)]
    metrics.append((start + timedelta(minutes=1), 90.0))
    _create_sample_metrics(server, source, metrics)


def _create_host_samples(servers, sources, observed_at):
    """Persist one current telemetry sample for each distinct host and source pair."""
    rows = list(zip(servers, sources, strict=True))
    deliveries = Delivery.objects.bulk_create([
        Delivery(
            source=source,
            external_id=f'dashboard-budget-host-metric-{number}',
            digest=f'{number:064x}',
            kind='metric',
            observed_at=observed_at,
        )
        for number, (_, source) in enumerate(rows)
    ])
    TelemetrySample.objects.bulk_create([
        TelemetrySample(
            delivery=delivery,
            resource=server,
            observed_at=observed_at,
            cpu_percent=10.0,
            cpu_count=2,
            load_1m=1.0,
            ram_total_bytes=1000,
            ram_used_bytes=500,
            disk_total_bytes=2000,
            disk_used_bytes=1000,
        )
        for delivery, (server, _) in zip(deliveries, rows, strict=True)
    ])


@pytest.mark.django_db
@pytest.mark.parametrize('period', ['24h', '7d', '30d', '90d'])
@freeze_time('2026-11-12T12:00:00Z')
def test_empty_series_stays_compact_with_explicit_gaps(dashboard_client, telemetry_server, period):
    """Fails if an empty period returns interpolated metric values or exceeds the response size budget."""
    server, _ = telemetry_server

    response = dashboard_client.get(
        f'/api/monitoring/servers/{server.pk}/series/',
        {'period': period},
    )
    points = response.json()['points']

    assert response.status_code == 200
    assert len(response.content) <= MAX_DASHBOARD_RESPONSE_BYTES
    assert {point['count'] for point in points} == {0}
    assert all(value is None for point in points for value in point['average'].values())
    assert {tuple(point['max'].items()) for point in points} == {()}


@pytest.mark.django_db
@freeze_time('2026-11-12T12:00:00Z')
def test_twenty_four_hour_series_aggregates_peak_without_inventing_samples(dashboard_client, telemetry_server):
    """Fails if bucketed telemetry loses counts, averages, peaks, or its bounded response size."""
    server, source = telemetry_server
    start = timezone.now() - timedelta(days=1)
    _create_complete_series(server, source, start)

    response = dashboard_client.get(f'/api/monitoring/servers/{server.pk}/series/', {'period': '24h'})
    points = response.json()['points']
    first_bucket = next(point for point in points if point['timestamp'] == int(start.timestamp()) * 1000)

    assert response.status_code == 200
    assert len(response.content) <= MAX_DASHBOARD_RESPONSE_BYTES
    assert sum(point['count'] for point in points) == 290
    assert first_bucket['count'] == 2
    assert first_bucket['average']['cpu_percent'] == 50.0
    assert first_bucket['max']['cpu_percent'] == 90.0
    assert {point['count'] for point in points} == {1, 2}


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
def test_snapshot_selects_do_not_grow_with_distinct_resources(dashboard_client, model, record_property):
    """Fails if a snapshot list adds monitoring reads as its sources and resources grow from one to fifty."""
    route = _model_route(model)
    _create_list_rows(model, 1)
    dashboard_client.get(route, {'snapshot': 'new'})

    with CaptureQueriesContext(connection) as one_queries:
        one_response = dashboard_client.get(route, {'snapshot': 'new'})
    _create_list_rows(model, 49, start=1)
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = dashboard_client.get(route, {'snapshot': 'new'})

    one_domain = _monitoring_selects(one_queries)
    fifty_domain = _monitoring_selects(fifty_queries)
    label = model.__name__.lower()
    record_property(f'{label}_snapshot_queries_one', len(one_queries))
    record_property(f'{label}_snapshot_queries_fifty', len(fifty_queries))
    record_property(f'{label}_snapshot_domain_selects_one', len(one_domain))
    record_property(f'{label}_snapshot_domain_selects_fifty', len(fifty_domain))

    assert one_response.json()['count'] == 1
    assert fifty_response.json()['count'] == 50
    assert len(one_domain) == len(fifty_domain)
    assert len(fifty_domain) <= MAX_DASHBOARD_DOMAIN_SELECTS


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
def test_snapshot_page_two_reuses_cached_model_rows(dashboard_client, model, record_property):
    """Fails if page two rereads case or report rows after a snapshot captures them."""
    rows = _create_list_rows(model, 26)
    route = _model_route(model)
    first = dashboard_client.get(route, {'snapshot': 'new'}).json()

    with CaptureQueriesContext(connection) as page_two_queries:
        second = dashboard_client.get(route, {'snapshot': first['snapshot'], 'page': 2})

    table = model._meta.db_table.lower()
    model_selects = [
        query['sql']
        for query in page_two_queries
        if query['sql'].lstrip().upper().startswith('SELECT')
        and table in query['sql'].lower()
    ]
    record_property(f'{model.__name__.lower()}_snapshot_page_two_queries', len(page_two_queries))

    assert second.status_code == 200
    assert second.json()['count'] == 26
    assert second.json()['results'][0]['id'] in {row.pk for row in rows}
    assert second.json()['results'][0]['id'] not in {row['id'] for row in first['results']}
    assert model_selects == []


@pytest.mark.django_db
@freeze_time('2026-11-12T12:00:00Z')
def test_status_selects_do_not_grow_with_hosts_and_samples(dashboard_client, record_property):
    """Fails if the server status endpoint adds monitoring reads for every host and latest sample."""
    first_server = Resource.objects.create(key='status-budget-server-0', name='Status budget server 0', kind='server')
    first_source = Source.objects.create(resource=first_server, key='telemetry', name='Telemetry')
    _create_samples(first_server, first_source, timezone.now(), 10.0)
    dashboard_client.get('/api/monitoring/status/')

    with CaptureQueriesContext(connection) as one_queries:
        one_response = dashboard_client.get('/api/monitoring/status/')
    servers = Resource.objects.bulk_create([
        Resource(key=f'status-budget-server-{number}', name=f'Status budget server {number}', kind='server')
        for number in range(1, 50)
    ])
    sources = Source.objects.bulk_create([
        Source(resource=server, key='telemetry', name='Telemetry')
        for server in servers
    ])
    _create_host_samples(servers, sources, timezone.now())
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = dashboard_client.get('/api/monitoring/status/')

    one_domain = _monitoring_selects(one_queries)
    fifty_domain = _monitoring_selects(fifty_queries)
    record_property('status_queries_one', len(one_queries))
    record_property('status_queries_fifty', len(fifty_queries))
    record_property('status_domain_selects_one', len(one_domain))
    record_property('status_domain_selects_fifty', len(fifty_domain))

    assert len(one_response.json()['hosts']) == 1
    assert len(fifty_response.json()['hosts']) == 50
    assert len(one_domain) == len(fifty_domain)
    assert len(fifty_domain) <= MAX_DASHBOARD_DOMAIN_SELECTS
