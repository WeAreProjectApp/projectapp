"""Scheduled integrity work uses Bogotá business time and recovers fenced scans."""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from content import tasks
from content.models import DataIntegrityScan, DataIntegrityScanLease

pytestmark = pytest.mark.django_db


@override_settings(DATA_INTEGRITY_DAILY_ENABLED=True, DATA_INTEGRITY_DAILY_HOUR=3)
@freeze_time('2026-11-05 08:00:00+00:00')
def test_daily_scan_starts_at_configured_bogota_hour():
    """Fails if the daily sweep misses 03:00 Bogotá because the worker clock is UTC."""
    tasks.daily_data_integrity_scan.call_local()

    scan = DataIntegrityScan.objects.get()
    assert (scan.source, scan.scope, scan.request_id) == (
        'scheduled', {'kind': 'all', 'id': None}, 'integrity-daily:2026-11-05',
    )


@override_settings(DATA_INTEGRITY_DAILY_ENABLED=True, DATA_INTEGRITY_DAILY_HOUR=3)
@freeze_time('2026-11-05 07:00:00+00:00')
def test_daily_scan_skips_other_bogota_hours():
    """Fails if the hourly scheduler starts repeated full scans outside its configured local hour."""
    tasks.daily_data_integrity_scan.call_local()

    assert DataIntegrityScan.objects.count() == 0


@freeze_time('2026-11-05 08:00:00+00:00')
def test_recovery_task_finishes_queued_scan_after_worker_lease_expires():
    """Fails if an expired worker lease leaves later queued integrity scans permanently blocked."""
    expired = DataIntegrityScan.objects.create(
        request_id='expired-worker', scope={'kind': 'all', 'id': None}, filters={},
        source='panel', catalog_version='1.2.0', status='running', started_at=timezone.now(),
    )
    queued = DataIntegrityScan.objects.create(
        request_id='recover-me', scope={'kind': 'all', 'id': None}, filters={},
        source='panel', catalog_version='1.2.0', status='queued',
    )
    DataIntegrityScanLease.objects.update_or_create(
        key='scan', defaults={'scan': expired, 'expires_at': timezone.now() - timedelta(seconds=1)},
    )

    tasks.recover_data_integrity_scans.call_local()

    expired.refresh_from_db()
    queued.refresh_from_db()
    assert (expired.status, expired.error_code) == ('failed', 'worker_timeout')
    assert queued.status == 'completed'


@freeze_time('2026-11-05 08:00:00+00:00')
def test_expired_running_scan_gets_one_completed_recovery():
    """A crashed scan is retried once without giving its old worker publication rights."""
    original = DataIntegrityScan.objects.create(
        request_id='crashed', scope={'kind': 'all', 'id': None}, filters={'rule_ids': ['DC11']},
        source='panel', catalog_version='1.2.0', status='running', started_at=timezone.now())
    DataIntegrityScanLease.objects.create(key='scan', scan=original,
        expires_at=timezone.now() - timedelta(seconds=1))

    tasks.recover_data_integrity_scans.call_local()
    tasks.recover_data_integrity_scans.call_local()

    original.refresh_from_db()
    recovered = DataIntegrityScan.objects.get(request_id=f'integrity-recovery:{original.pk}')
    assert original.status == 'failed'
    assert recovered.status == 'completed'


@override_settings(DATA_INTEGRITY_DAILY_ENABLED=False)
@freeze_time('2026-11-05 08:00:00+00:00')
def test_daily_scan_respects_disabled_switch():
    tasks.daily_data_integrity_scan.call_local()

    assert DataIntegrityScan.objects.count() == 0


@override_settings(DATA_INTEGRITY_DAILY_ENABLED=True, DATA_INTEGRITY_DAILY_HOUR=3)
@freeze_time('2026-11-05 08:00:00+00:00')
def test_daily_scan_reuses_one_request_for_the_date():
    tasks.daily_data_integrity_scan.call_local()
    tasks.daily_data_integrity_scan.call_local()

    assert DataIntegrityScan.objects.count() == 1
