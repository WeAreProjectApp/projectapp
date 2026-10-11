from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task

from .models import Delivery, Report

CLEANUP_BATCH_SIZE = 500
MAX_CLEANUP_BATCHES = 4
REPORT_RETENTION = timedelta(days=90)


def delete_in_batches(queryset):
    """Bound each transaction and the work done in one periodic invocation."""
    for _ in range(MAX_CLEANUP_BATCHES):
        ids = list(queryset.order_by('pk').values_list('pk', flat=True)[:CLEANUP_BATCH_SIZE])
        if not ids:
            break
        queryset.filter(pk__in=ids).delete()


def retention(setting):
    """A horizon under one day would delete receipts that retries and case history still need."""
    days = getattr(settings, setting)
    if not isinstance(days, int) or days < 1:
        raise ImproperlyConfigured(f'{setting} debe ser un número entero de días mayor o igual a 1.')
    return timedelta(days=days)


def prunable_detections(cutoff):
    """Repeated detections older than the retry horizon that no case history depends on."""
    return Delivery.objects.filter(
        kind='detection', case__isnull=False, report__isnull=True, milestone=False, received_at__lt=cutoff,
    ).exclude(observed_at=F('case__first_seen_at')).exclude(observed_at=F('case__last_seen_at'))


@periodic_task(crontab(minute='45'))
def cleanup_monitoring_reports():
    now = timezone.now()
    heartbeat_cutoff = now - retention('MONITORING_HEARTBEAT_RETENTION_DAYS')
    detection_cutoff = now - retention('MONITORING_DETECTION_RETRY_HORIZON_DAYS')
    delete_in_batches(Report.objects.filter(observed_at__lt=now - REPORT_RETENTION))
    delete_in_batches(Delivery.objects.filter(kind='heartbeat', received_at__lt=heartbeat_cutoff))
    # Recoveries, report receipts and anything received inside the retry horizon stay idempotent.
    delete_in_batches(prunable_detections(detection_cutoff))
