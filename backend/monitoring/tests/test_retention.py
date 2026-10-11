"""Bounded retention contracts for monitoring receipts and reports."""

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from math import ceil

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from freezegun import freeze_time

from monitoring.models import Case, Credential, Delivery, Report, Resource, Source
from monitoring.services import change_state, ingest
from monitoring.tasks import cleanup_monitoring_reports
from monitoring.tests.test_followup_api import staff_client, staff_user
from monitoring.tests.test_ingest import (
    INGEST_URL,
    SERVER_KEY,
    detection_payload,
    machine_client,
    machine_credential,
    monitored_resource,
    monitored_source,
)

RETENTION_BATCH_SIZE = 500
MAX_RETENTION_BATCHES = 4
MAX_DELETE_QUERIES = MAX_RETENTION_BATCHES * ceil(RETENTION_BATCH_SIZE / GET_ITERATOR_CHUNK_SIZE)
COLLECTOR_PROJECTS = ['projectapp', 'mimittos-project', 'tenndalux-project']


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


def create_receipts(source, prefix, total, received_at, **fields):
    """Persist receipts with distinct identities, backdated as if they arrived at ``received_at``."""
    Delivery.objects.bulk_create(
        Delivery(source=source, external_id=f'{prefix}:{number}', digest=f'{number:064x}', **fields)
        for number in range(total)
    )
    Delivery.objects.filter(source=source, external_id__startswith=f'{prefix}:').update(received_at=received_at)


def deliver(client, received_at, payload):
    """Send one observation and backdate its receipt to when the collector delivered it."""
    response = client.post(INGEST_URL, payload, format='json')
    assert response.status_code == 201
    Delivery.objects.filter(pk=response.json()['id']).update(received_at=parse_datetime(received_at))
    return response


def scheduled_runs(task, day):
    """Count the minutes of one day at which Huey enqueues the periodic task."""
    periodic = task.task_class()
    return sum(1 for minute in range(24 * 60) if periodic.validate_datetime(day + timedelta(minutes=minute)))


@pytest.fixture
def collector_sources(db):
    """Recreate the 13 heartbeat sources of the production collector."""
    server = Resource.objects.create(key=SERVER_KEY, name='VPS de producción', kind='server')
    resources = [server] + [
        Resource.objects.create(key=key, name=key, kind='project', server=server)
        for key in COLLECTOR_PROJECTS
    ]
    credential, _ = Credential.issue('collector')
    credential.resources.add(*resources)
    sources = [Source.objects.create(resource=server, key='monitoring', name='Colector')]
    sources += [
        Source.objects.create(resource=resource, key=key, name=key)
        for resource in resources
        for key in ('integrity', 'server-alerts', 'healthcheck')
    ]
    return credential, sources


def heartbeat(source, observed_at):
    """Build the validated envelope the collector sends: a new uuid4 per heartbeat."""
    return {
        'schema_version': 1,
        'external_id': uuid.uuid4().hex,
        'server': SERVER_KEY,
        'resource': source.resource.key,
        'source': source.key,
        'observed_at': observed_at,
        'kind': 'heartbeat',
        'enabled': True,
        'error': '',
    }


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


@pytest.mark.django_db
@freeze_time('2024-01-03T00:30:00Z')
def test_a_collector_day_keeps_one_heartbeat_receipt_per_source_and_hour(collector_sources):
    """Falla si la tabla de latidos vuelve a crecer con cada latido en vez de una fila por fuente y hora."""
    credential, sources = collector_sources
    now = timezone.now()
    day = (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    expired, retained = now - timedelta(days=91), now - timedelta(days=88)
    for source in sources:
        create_receipts(source, 'expired', 24, expired, kind='heartbeat', observed_at=expired)
        create_receipts(source, 'retained', 24, retained, kind='heartbeat', observed_at=retained)
    # Two heartbeats per source and hour already reach the bound: the production cadence of up to
    # 60 per hour (9,504 a day across these 13 sources) goes through the same ingest path.
    for hour in range(24):
        for minute in (0, 30):
            for source in sources:
                ingest(credential, heartbeat(source, day + timedelta(hours=hour, minutes=minute)))

    cleanup_monitoring_reports.call_local()

    rows_per_source = Counter(Delivery.objects.filter(kind='heartbeat').values_list('source_id', flat=True))
    assert len(rows_per_source) == 13
    assert set(rows_per_source.values()) == {48}


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_one_day_of_scheduled_cleanups_drains_a_day_of_expired_heartbeats(monitored_source):
    """Falla si la limpieza vuelve a un ritmo que no alcanza a borrar en un día lo que vence en un día."""
    expired_at = datetime(2023, 11, 30, 12, tzinfo=dt_timezone.utc)
    create_receipts(monitored_source, 'heartbeat', 9504, expired_at, kind='heartbeat', observed_at=expired_at)

    for _ in range(scheduled_runs(cleanup_monitoring_reports, datetime(2024, 3, 1, tzinfo=dt_timezone.utc))):
        cleanup_monitoring_reports.call_local()

    assert Delivery.objects.filter(source=monitored_source, kind='heartbeat').count() == 0


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_detection_cleanup_uses_four_delete_batches(monitored_source):
    """Falla si una corrida poda más de cuatro lotes de detecciones repetidas o toca el contador del caso."""
    observed_at = timezone.now() - timedelta(days=40)
    case = Case.objects.create(
        source=monitored_source,
        fingerprint='server-alerts:disk',
        fingerprint_hash='d' * 64,
        title='Disco alto',
        severity='warning',
        first_seen_at=observed_at - timedelta(days=1),
        last_seen_at=timezone.now(),
        detections=RETENTION_BATCH_SIZE * MAX_RETENTION_BATCHES + 1,
    )
    create_receipts(
        monitored_source, 'detection', RETENTION_BATCH_SIZE * MAX_RETENTION_BATCHES + 1, observed_at,
        kind='detection', observed_at=observed_at, case=case,
    )

    with CaptureQueriesContext(connection) as queries:
        cleanup_monitoring_reports.call_local()

    detection_deletes = [query for query in queries if 'DELETE FROM "monitoring_delivery"' in query['sql']]
    case.refresh_from_db()
    assert len(detection_deletes) <= MAX_DELETE_QUERIES
    assert Delivery.objects.filter(case=case).count() == 1
    assert case.detections == 2001


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_detection_cleanup_keeps_the_history_each_case_depends_on(
    machine_client, staff_client, staff_user, monitored_source, detection_payload,
):
    """Falla si la limpieza poda la apertura, la primera o la última observación, una recuperación, un informe, una reapertura, un regreso o una detección todavía reintentable."""
    def observation(name, observed_at, **fields):
        return detection_payload(external_id=f'silk:{name}', observed_at=observed_at, **fields)

    deliver(machine_client, '2024-01-01T00:00:00Z', observation('opened', '2024-01-01T00:00:00Z'))
    deliver(machine_client, '2024-01-01T06:00:00Z', observation('earliest', '2023-12-31T12:00:00Z'))
    deliver(machine_client, '2024-01-02T00:00:00Z', observation('repeat-1', '2024-01-02T00:00:00Z'))
    deliver(machine_client, '2024-01-03T00:00:00Z', observation('repeat-2', '2024-01-03T00:00:00Z'))
    deliver(machine_client, '2024-01-04T00:00:00Z', observation('recovered', '2024-01-04T00:00:00Z', kind='recovery', omit=('title',)))
    deliver(machine_client, '2024-01-05T00:00:00Z', observation('came-back', '2024-01-05T00:00:00Z'))
    deliver(machine_client, '2024-01-06T00:00:00Z', observation(
        'weekly', '2024-01-06T00:00:00Z', kind='report', title='Informe semanal',
        text='Una consulta lenta.', omit=('fingerprint',),
    ))
    deliver(machine_client, '2024-01-06T01:00:00Z', observation('reported', '2024-01-06T01:00:00Z', report_id='silk:weekly'))
    deliver(machine_client, '2024-01-07T00:00:00Z', observation('repeat-3', '2024-01-07T00:00:00Z'))
    case = Case.objects.get(source=monitored_source)
    change_state(case.pk, staff_user, {'state': 'resolved', 'version': case.version})
    Case.objects.filter(pk=case.pk).update(closed_at=parse_datetime('2024-01-08T00:00:00Z'))
    deliver(machine_client, '2024-01-09T00:00:00Z', observation('reopened', '2024-01-09T00:00:00Z'))
    deliver(machine_client, '2024-01-10T00:00:00Z', observation('repeat-4', '2024-01-10T00:00:00Z'))
    deliver(machine_client, '2024-01-11T00:00:00Z', observation('latest', '2024-01-11T00:00:00Z'))
    deliver(machine_client, '2024-02-15T00:00:00Z', observation('late-arrival', '2024-01-02T12:00:00Z'))

    cleanup_monitoring_reports.call_local()
    detail = staff_client.get(f'/api/monitoring/cases/{case.pk}/')

    case.refresh_from_db()
    assert set(Delivery.objects.filter(case=case).values_list('external_id', flat=True)) == {
        'silk:opened', 'silk:earliest', 'silk:recovered', 'silk:came-back',
        'silk:reported', 'silk:reopened', 'silk:latest', 'silk:late-arrival',
    }
    assert case.detections == 11
    assert detail.status_code == 200
    assert detail.json()['deliveries']['count'] == 8


@pytest.mark.django_db
@freeze_time('2024-01-31T00:00:00Z')
def test_detection_retried_inside_the_retry_horizon_is_still_a_duplicate(machine_client, monitored_source, detection_payload):
    """Falla si la limpieza poda una detección que el colector todavía puede reintentar y el reintento se cuenta dos veces."""
    delayed = detection_payload(external_id='silk:retry:delayed', observed_at='2023-12-01T00:00:00Z')
    deliver(machine_client, '2023-11-01T00:00:00Z', detection_payload(external_id='silk:retry:opened', observed_at='2023-11-01T00:00:00Z'))
    deliver(machine_client, '2024-01-02T00:00:00Z', delayed)
    deliver(machine_client, '2024-01-03T00:00:00Z', detection_payload(external_id='silk:retry:latest', observed_at='2024-01-03T00:00:00Z'))

    cleanup_monitoring_reports.call_local()
    retry = machine_client.post(INGEST_URL, delayed, format='json')

    assert retry.status_code == 200
    assert retry.json()['duplicate'] is True
    assert Case.objects.get(source=monitored_source).detections == 3


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
@override_settings(MONITORING_HEARTBEAT_RETENTION_DAYS=10, MONITORING_DETECTION_RETRY_HORIZON_DAYS=5)
def test_configured_horizons_decide_what_the_cleanup_removes(monitored_source):
    """Falla si la limpieza ignora los horizontes configurados y conserva o borra con valores fijos."""
    now = timezone.now()
    case = Case.objects.create(
        source=monitored_source,
        fingerprint='server-alerts:load',
        fingerprint_hash='e' * 64,
        title='Carga alta',
        severity='warning',
        first_seen_at=now - timedelta(days=60),
        last_seen_at=now,
        detections=2,
    )
    create_receipts(monitored_source, 'heartbeat-old', 1, now - timedelta(days=11), kind='heartbeat', observed_at=now - timedelta(days=11))
    create_receipts(monitored_source, 'heartbeat-recent', 1, now - timedelta(days=9), kind='heartbeat', observed_at=now - timedelta(days=9))
    create_receipts(monitored_source, 'detection-old', 1, now - timedelta(days=6), kind='detection', observed_at=now - timedelta(days=30), case=case)
    create_receipts(monitored_source, 'detection-recent', 1, now - timedelta(days=4), kind='detection', observed_at=now - timedelta(days=29), case=case)

    cleanup_monitoring_reports.call_local()

    assert set(Delivery.objects.filter(source=monitored_source).values_list('external_id', flat=True)) == {
        'heartbeat-recent:0', 'detection-recent:0',
    }


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
@pytest.mark.parametrize('setting', ['MONITORING_HEARTBEAT_RETENTION_DAYS', 'MONITORING_DETECTION_RETRY_HORIZON_DAYS'])
def test_a_horizon_below_one_day_stops_the_cleanup_without_deleting(monitored_source, setting):
    """Falla si un horizonte en cero hace que la limpieza borre recibos recientes que debía conservar."""
    now = timezone.now()
    case = Case.objects.create(
        source=monitored_source,
        fingerprint='server-alerts:memory',
        fingerprint_hash='f' * 64,
        title='Memoria alta',
        severity='warning',
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now,
        detections=1,
    )
    create_receipts(monitored_source, 'heartbeat', 1, now - timedelta(hours=1), kind='heartbeat', observed_at=now - timedelta(hours=1))
    create_receipts(monitored_source, 'detection', 1, now - timedelta(hours=1), kind='detection', observed_at=now - timedelta(days=1), case=case)

    with override_settings(**{setting: 0}), pytest.raises(ImproperlyConfigured):
        cleanup_monitoring_reports.call_local()

    assert Delivery.objects.filter(source=monitored_source).count() == 2
