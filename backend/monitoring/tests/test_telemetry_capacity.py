"""Measurements and informational allocations must never mutate incident counters or host limits."""
from copy import deepcopy
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from monitoring.models import CapacityAllocation, CapacityChange, Case, TelemetrySample
from monitoring.serializers import IngestSerializer
from monitoring.services import Conflict, ingest
from monitoring.tests.dashboard_fixtures import dashboard, measurement


def receive(dashboard, payload):
    serializer = IngestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return ingest(dashboard['credential'], serializer.validated_data)


def capacity_payload(**changes):
    return {'version': 0, 'cpu_mode': 'assigned', 'cpu_vcpu': '.4', 'ram_mode': 'assigned', 'ram_bytes': 1048576, 'storage_mode': 'shared', 'storage_bytes': None, **changes}


def test_identical_measurement_retry_keeps_one_sample(dashboard):
    payload = measurement(dashboard)
    receipt, _ = receive(dashboard, payload)
    repeated, created = receive(dashboard, payload)
    assert repeated.pk == receipt.pk
    assert created is False
    assert TelemetrySample.objects.count() == 1
    assert Case.objects.count() == 0


def test_reused_measurement_identity_rejects_changed_content(dashboard):
    payload = measurement(dashboard)
    receive(dashboard, payload)
    changed = deepcopy(payload)
    changed['metrics']['cpu_percent'] = 80
    with pytest.raises(Conflict):
        receive(dashboard, changed)
    assert TelemetrySample.objects.get().cpu_percent == 25


@pytest.mark.parametrize('metrics', [{'cpu_percent': float('nan')}, {'load_1m': float('inf')}, {'ram_used_bytes': 8192}, {'cpu_percent': -1}])
def test_invalid_measurement_is_rejected(dashboard, metrics):
    serializer = IngestSerializer(data=measurement(dashboard, **metrics))
    assert serializer.is_valid() is False
    assert TelemetrySample.objects.count() == 0


def test_project_resource_cannot_publish_host_measurements(dashboard):
    dashboard['credential'].resources.add(dashboard['project'])
    dashboard['source'].key = 'telemetry'
    dashboard['source'].save()
    payload = measurement(dashboard)
    payload['resource'] = dashboard['project'].key
    with pytest.raises(PermissionDenied):
        receive(dashboard, payload)
    assert TelemetrySample.objects.count() == 0


def test_series_contains_explicit_gaps(dashboard):
    receive(dashboard, measurement(dashboard))
    response = dashboard['client'].get(f"/api/monitoring/servers/{dashboard['server'].pk}/series/").json()
    assert sum(point['count'] for point in response['points']) == 1
    assert response['points'][0]['average']['cpu_percent'] is None
    assert response['capacity']['ram_total_bytes'] == 4096


def test_stale_measurement_does_not_claim_current_pressure(dashboard):
    payload = measurement(dashboard, ram_used_bytes=4096)
    payload['observed_at'] = timezone.now() - timedelta(minutes=10)
    receive(dashboard, payload)
    response = dashboard['client'].get('/api/monitoring/status/').json()['hosts'][0]
    assert response['health'] == 'stale'
    assert response['pressure'] == []


def test_current_pressure_uses_measured_capacity(dashboard):
    receive(dashboard, measurement(dashboard, ram_used_bytes=4096, load_1m=6))
    response = dashboard['client'].get('/api/monitoring/status/').json()['hosts'][0]
    assert response['pressure'] == ['ram', 'load']


def test_capacity_records_actor_without_creating_incidents(dashboard):
    response = dashboard['client'].put(f"/api/monitoring/resources/{dashboard['project'].pk}/capacity/", capacity_payload(), format='json')
    assert response.status_code == 200
    assert response.json()['allocation']['version'] == 1
    assert CapacityChange.objects.get().actor == dashboard['actor']
    assert Case.objects.count() == 0


def test_stale_capacity_version_preserves_latest_allocation(dashboard):
    url = f"/api/monitoring/resources/{dashboard['project'].pk}/capacity/"
    dashboard['client'].put(url, capacity_payload(), format='json')
    response = dashboard['client'].put(url, capacity_payload(ram_bytes=2097152), format='json')
    assert response.status_code == 409
    assert CapacityAllocation.objects.get().ram_bytes == 1048576
    assert CapacityChange.objects.count() == 1


def test_shared_capacity_rejects_a_fabricated_quantity(dashboard):
    response = dashboard['client'].put(f"/api/monitoring/resources/{dashboard['project'].pk}/capacity/", capacity_payload(storage_bytes=100), format='json')
    assert response.status_code == 400
    assert CapacityAllocation.objects.count() == 0


@pytest.mark.parametrize('route', ['status/', 'cases/?snapshot=new', 'servers/1/series/', 'resources/1/capacity/'])
def test_anonymous_cannot_consult_operational_data(dashboard, route):
    assert APIClient().get('/api/monitoring/' + route).status_code == 403


def test_server_id_cannot_be_used_to_configure_project_capacity(dashboard):
    response = dashboard['client'].put(f"/api/monitoring/resources/{dashboard['server'].pk}/capacity/", capacity_payload(), format='json')
    assert response.status_code == 404
    assert CapacityAllocation.objects.count() == 0
