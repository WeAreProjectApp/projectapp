"""Bounded retention contracts for monitoring receipts and reports."""

from datetime import timedelta
from math import ceil

import pytest
from django.db import connection
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time

from monitoring.models import Case, Delivery, Report, Resource, Source
from monitoring.tasks import cleanup_monitoring_reports

RETENTION_BATCH_SIZE = 500
MAX_RETENTION_BATCHES = 4
MAX_DELETE_QUERIES = MAX_RETENTION_BATCHES * ceil(RETENTION_BATCH_SIZE / GET_ITERATOR_CHUNK_SIZE)


@pytest.fixture
def monitored_source(db):
    """Create the Silk source under its project resource and monitoring server."""
    server = Resource.objects.create(
        key="srv1681495", name="Retention server", kind="server"
    )
    resource = Resource.objects.create(
        key="projectapp", name="ProjectApp", kind="project", server=server
    )
    return Source.objects.create(resource=resource, key="silk", name="Silk")


def create_expired_reports(source, total):
    """Create reports whose observed timestamp exceeds the retention period."""
    observed_at = timezone.now() - timedelta(days=91)
    reports = [
        Report(
            source=source,
            title=f'Reporte vencido {number}',
            observed_at=observed_at,
            text='contenido de informe vencido',
        )
        for number in range(total)
    ]
    return Report.objects.bulk_create(reports)


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_report_cleanup_uses_four_delete_batches(monitored_source):
    """Falla si una corrida borra más de cuatro lotes de informes vencidos."""
    create_expired_reports(monitored_source, RETENTION_BATCH_SIZE * MAX_RETENTION_BATCHES + 1)

    with CaptureQueriesContext(connection) as queries:
        cleanup_monitoring_reports.call_local()

    report_deletes = [query for query in queries if 'DELETE FROM "monitoring_report"' in query['sql']]
    assert len(report_deletes) <= MAX_DELETE_QUERIES
    assert Report.objects.filter(source=monitored_source).count() == 1


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_report_cleanup_preserves_linked_case_receipt(monitored_source):
    """Falla si retener informes elimina el recibo que mantiene idempotente el caso."""
    report = create_expired_reports(monitored_source, 1)[0]
    case = Case.objects.create(
        source=monitored_source,
        fingerprint='integrity:backup',
        fingerprint_hash='b' * 64,
        title='Backup atrasado',
        severity='critical',
        first_seen_at=timezone.now(),
        last_seen_at=timezone.now(),
        detections=1,
    )
    delivery = Delivery.objects.create(
        source=monitored_source,
        external_id='integrity:backup:delivery',
        digest='c' * 64,
        kind='detection',
        observed_at=timezone.now() - timedelta(days=91),
        case=case,
        report=report,
    )

    cleanup_monitoring_reports.call_local()

    delivery.refresh_from_db()
    assert Report.objects.filter(source=monitored_source).count() == 0
    assert delivery.case_id == case.pk
    assert delivery.report_id is None


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_heartbeat_cleanup_uses_four_delete_batches(monitored_source):
    """Falla si una corrida de retención elimina más de cuatro lotes de heartbeats."""
    received_at = timezone.now() - timedelta(days=91)
    deliveries = [
        Delivery(
            source=monitored_source,
            external_id=f'heartbeat:{number}',
            digest=f'{number:064x}',
            kind='heartbeat',
            observed_at=received_at,
        )
        for number in range(RETENTION_BATCH_SIZE * MAX_RETENTION_BATCHES + 1)
    ]
    Delivery.objects.bulk_create(deliveries)
    Delivery.objects.filter(source=monitored_source).update(received_at=received_at)

    with CaptureQueriesContext(connection) as queries:
        cleanup_monitoring_reports.call_local()

    heartbeat_deletes = [query for query in queries if 'DELETE FROM "monitoring_delivery"' in query['sql']]
    assert len(heartbeat_deletes) <= MAX_DELETE_QUERIES
    assert Delivery.objects.filter(source=monitored_source, kind='heartbeat').count() == 1
