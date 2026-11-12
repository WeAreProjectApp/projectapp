"""Measurements and informational allocations must never mutate incident counters or host limits."""
from copy import deepcopy
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from monitoring.models import CapacityAllocation, CapacityChange, Case, TelemetrySample
from monitoring.serializers import IngestSerializer
from monitoring.services import Conflict, ingest
from monitoring.tests.dashboard_fixtures import measurement

pytest_plugins = ('monitoring.tests.dashboard_fixtures',)


@pytest.fixture(name='dashboard_fixture')
def _dashboard_fixture(dashboard):
    return dashboard


def _receive(dashboard_fixture, payload):
    serializer = IngestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return ingest(dashboard_fixture['credential'], serializer.validated_data)


def _capacity_payload(**changes):
    return {'version': 0, 'cpu_mode': 'assigned', 'cpu_vcpu': '.4', 'ram_mode': 'assigned', 'ram_bytes': 1048576, 'storage_mode': 'shared', 'storage_bytes': None, **changes}


def test_identical_measurement_retry_keeps_one_sample(dashboard_fixture):
    """Fails if retrying an identical measurement stores a second host sample."""
    payload = measurement(dashboard_fixture)
    receipt, _ = _receive(dashboard_fixture, payload)
    repeated, created = _receive(dashboard_fixture, payload)
    assert repeated.pk == receipt.pk
    assert created is False
    assert TelemetrySample.objects.count() == 1
    assert Case.objects.count() == 0


def test_reused_measurement_identity_rejects_changed_content(dashboard_fixture):
    """Fails if a retried measurement identity accepts different metrics."""
    payload = measurement(dashboard_fixture)
    _receive(dashboard_fixture, payload)
    changed = deepcopy(payload)
    changed['metrics']['cpu_percent'] = 80
    with pytest.raises(Conflict):
        _receive(dashboard_fixture, changed)
    assert TelemetrySample.objects.get().cpu_percent == 25


@pytest.mark.parametrize('metrics', [{'cpu_percent': float('nan')}, {'load_1m': float('inf')}, {'ram_used_bytes': 8192}, {'cpu_percent': -1}])
def test_invalid_measurement_is_rejected(dashboard_fixture, metrics):
    """Fails if invalid telemetry values are accepted before persistence."""
    serializer = IngestSerializer(data=measurement(dashboard_fixture, **metrics))
    assert serializer.is_valid() is False
    assert TelemetrySample.objects.count() == 0


def test_project_resource_cannot_publish_host_measurements(dashboard_fixture):
    """Fails if a project credential can insert metrics attributed to a server."""
    dashboard_fixture['credential'].resources.add(dashboard_fixture['project'])
    dashboard_fixture['source'].key = 'telemetry'
    dashboard_fixture['source'].save()
    payload = measurement(dashboard_fixture)
    payload['resource'] = dashboard_fixture['project'].key
    with pytest.raises(PermissionDenied):
        _receive(dashboard_fixture, payload)
    assert TelemetrySample.objects.count() == 0


def test_series_contains_explicit_gaps(dashboard_fixture):
    """Fails if server telemetry manufactures a value for an empty time bucket."""
    _receive(dashboard_fixture, measurement(dashboard_fixture))
    response = dashboard_fixture['client'].get(f"/api/monitoring/servers/{dashboard_fixture['server'].pk}/series/").json()
    assert sum(point['count'] for point in response['points']) == 1
    assert response['points'][0]['average']['cpu_percent'] is None
    assert response['capacity']['ram_total_bytes'] == 4096


@freeze_time('2026-11-12T12:00:00Z')
def test_stale_measurement_does_not_claim_current_pressure(dashboard_fixture):
    """Fails if an old host measurement is reported as current pressure."""
    payload = measurement(dashboard_fixture, ram_used_bytes=4096)
    payload['observed_at'] = timezone.now() - timedelta(minutes=10)
    _receive(dashboard_fixture, payload)
    response = dashboard_fixture['client'].get('/api/monitoring/status/').json()['hosts'][0]
    assert response['health'] == 'stale'
    assert response['pressure'] == []


def test_current_pressure_uses_measured_capacity(dashboard_fixture):
    """Fails if fresh high RAM and load readings do not expose their pressure."""
    _receive(dashboard_fixture, measurement(dashboard_fixture, ram_used_bytes=4096, load_1m=6))
    response = dashboard_fixture['client'].get('/api/monitoring/status/').json()['hosts'][0]
    assert response['pressure'] == ['ram', 'load']


def test_capacity_records_actor_without_creating_incidents(dashboard_fixture):
    """Fails if recording informational capacity opens or alters an incident."""
    response = dashboard_fixture['client'].put(f"/api/monitoring/resources/{dashboard_fixture['project'].pk}/capacity/", _capacity_payload(), format='json')
    assert response.status_code == 200
    assert response.json()['allocation']['version'] == 1
    assert CapacityChange.objects.get().actor == dashboard_fixture['actor']
    assert Case.objects.count() == 0


def test_stale_capacity_version_preserves_latest_allocation(dashboard_fixture):
    """Fails if an outdated capacity edit overwrites the recorded allocation."""
    url = f"/api/monitoring/resources/{dashboard_fixture['project'].pk}/capacity/"
    dashboard_fixture['client'].put(url, _capacity_payload(), format='json')
    response = dashboard_fixture['client'].put(url, _capacity_payload(ram_bytes=2097152), format='json')
    assert response.status_code == 409
    assert CapacityAllocation.objects.get().ram_bytes == 1048576
    assert CapacityChange.objects.count() == 1


def test_shared_capacity_rejects_a_fabricated_quantity(dashboard_fixture):
    """Fails if shared storage accepts a quantity presented as an allocation."""
    response = dashboard_fixture['client'].put(f"/api/monitoring/resources/{dashboard_fixture['project'].pk}/capacity/", _capacity_payload(storage_bytes=100), format='json')
    assert response.status_code == 400
    assert CapacityAllocation.objects.count() == 0


@pytest.mark.parametrize('route', ['status/', 'cases/?snapshot=new', 'servers/1/series/', 'resources/1/capacity/'])
def test_anonymous_cannot_consult_operational_data(dashboard_fixture, route):
    """Fails if anonymous callers can read operational monitoring endpoints."""
    assert APIClient().get('/api/monitoring/' + route).status_code == 403


def test_server_id_cannot_be_used_to_configure_project_capacity(dashboard_fixture):
    """Fails if a server resource can be mistaken for a project allocation."""
    response = dashboard_fixture['client'].put(f"/api/monitoring/resources/{dashboard_fixture['server'].pk}/capacity/", _capacity_payload(), format='json')
    assert response.status_code == 404
    assert CapacityAllocation.objects.count() == 0


def test_capacity_history_second_page_returns_audited_changes(dashboard_fixture):
    """Fails if capacity history omits its remaining changes or their audit values after page one."""
    dashboard_fixture['client'].put(
        f"/api/monitoring/resources/{dashboard_fixture['project'].pk}/capacity/",
        _capacity_payload(),
        format='json',
    )
    allocation = CapacityAllocation.objects.get()
    CapacityChange.objects.bulk_create([
        CapacityChange(
            allocation=allocation,
            actor=dashboard_fixture['actor'],
            actor_name=dashboard_fixture['actor'].get_username(),
            before={'ram_bytes': number},
            after={'ram_bytes': number + 1},
        )
        for number in range(1, 30)
    ])

    history = dashboard_fixture['client'].get(
        f"/api/monitoring/resources/{dashboard_fixture['project'].pk}/capacity/history/",
        {'page': 2},
    )

    assert history.status_code == 200
    assert history.json()['count'] == 30
    assert history.json()['page'] == 2
    assert len(history.json()['results']) == 5
    assert history.json()['results'][0]['actor_name'] == 'dashboard-operator'
    assert history.json()['results'][0]['before'] == {'ram_bytes': 4}
    assert history.json()['results'][0]['after'] == {'ram_bytes': 5}


def test_project_source_status_includes_its_server(dashboard_fixture):
    """Fails if a report source on a project cannot reveal its measured host pressure."""
    _receive(dashboard_fixture, measurement(dashboard_fixture, ram_used_bytes=4096, load_1m=6))

    response = dashboard_fixture['client'].get(
        '/api/monitoring/status/',
        {'source': dashboard_fixture['source'].pk},
    )

    host = response.json()['hosts'][0]
    assert response.status_code == 200
    assert len(response.json()['hosts']) == 1
    assert host['id'] == dashboard_fixture['server'].pk
    assert host['health'] == 'current'
    assert host['pressure'] == ['ram', 'load']
    assert host['metrics']['ram_used_bytes'] == 4096
    assert host['metrics']['load_1m'] == 6.0
