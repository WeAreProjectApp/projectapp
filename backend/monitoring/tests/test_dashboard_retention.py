"""Retention contracts for the telemetry displayed by the monitoring dashboard."""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from monitoring.models import Delivery, TelemetrySample
from monitoring.serializers import IngestSerializer
from monitoring.services import ingest
from monitoring.tasks import cleanup_monitoring_reports
from monitoring.tests.dashboard_fixtures import measurement

pytest_plugins = ('monitoring.tests.dashboard_fixtures',)


@pytest.fixture(name='dashboard_fixture')
def _dashboard_fixture(dashboard):
    return dashboard


def _receive_measurement(dashboard_fixture, payload):
    serializer = IngestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return ingest(dashboard_fixture['credential'], serializer.validated_data)[0]


@freeze_time('2026-11-12T12:00:00Z')
def test_metric_cleanup_cascades_expired_sample_after_retry_horizon(dashboard_fixture):
    """Fails if 90-day metric cleanup leaves its sample or deletes the current measurement."""
    expired = measurement(dashboard_fixture, cpu_percent=10)
    expired['external_id'] = 'expired-dashboard-measurement'
    expired['observed_at'] = timezone.now() - timedelta(days=91)
    expired_receipt = _receive_measurement(dashboard_fixture, expired)
    Delivery.objects.filter(pk=expired_receipt.pk).update(received_at=timezone.now() - timedelta(days=31))
    current = measurement(dashboard_fixture, cpu_percent=20)
    current['external_id'] = 'current-dashboard-measurement'
    current_receipt = _receive_measurement(dashboard_fixture, current)

    cleanup_monitoring_reports.call_local()

    assert Delivery.objects.filter(pk=expired_receipt.pk).exists() is False
    assert TelemetrySample.objects.filter(delivery_id=expired_receipt.pk).exists() is False
    assert Delivery.objects.filter(pk=current_receipt.pk, kind='metric').exists() is True
    assert TelemetrySample.objects.get(delivery_id=current_receipt.pk).cpu_percent == 20
