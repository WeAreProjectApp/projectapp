"""Bounded jobs and Bogotá-local schedules; no internal AI execution."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import lock_task, periodic_task, task

from procurement.models import Delivery, Opportunity, ScheduleSlot, Settings, SyncRun


@task()
@lock_task('procurement-sync-page')
def sync_page(run_id):
    from procurement.services.sync import synchronize_page
    if synchronize_page(run_id):
        sync_page.schedule(args=(run_id,), delay=2)


@task()
def evaluate_alert(alert_id, after=0):
    from procurement.services.notifications import evaluate_opportunities
    ids = list(Opportunity.objects.filter(pk__gt=after).order_by('pk').values_list('pk', flat=True)[:250])
    if ids:
        evaluate_opportunities(ids, alert_id=alert_id)
        evaluate_alert.schedule(args=(alert_id, ids[-1]), delay=1)


@task()
@lock_task('procurement-outbox')
def flush_notifications(frequency):
    from procurement.services.notifications import flush
    flush(frequency)


@task()
def deliver(delivery_id):
    from procurement.services.notifications import send_delivery
    send_delivery(delivery_id)


@periodic_task(crontab(minute='*'))
def procurement_clock():
    from procurement.services.sync import request_sync
    config = Settings.current()
    local = timezone.now().astimezone(ZoneInfo('America/Bogota'))
    day = local.date()
    clock = local.time().replace(tzinfo=None)
    schedules = [('sync', config.sync_time, config.sync_enabled),
                 ('daily', config.daily_time, config.email_enabled),
                 ('weekly', config.weekly_time, config.email_enabled and local.weekday() == config.weekly_day)]
    for kind, due, enabled in schedules:
        if not enabled or clock < due:
            continue
        # Daily/weekly envelopes wait for an in-flight synchronization to finish.
        if kind != 'sync' and SyncRun.objects.filter(status__in=['queued', 'running']).exists():
            continue
        with transaction.atomic():
            _, created = ScheduleSlot.objects.get_or_create(kind=kind, day=day)
            if created:
                if kind == 'sync':
                    request_sync()
                else:
                    transaction.on_commit(lambda frequency=kind: flush_notifications(frequency))
    if config.email_enabled:
        # Continue bounded chunks after the scheduled first digest.
        for frequency in ('immediate', 'daily', 'weekly'):
            if frequency == 'immediate' or ScheduleSlot.objects.filter(kind=frequency, day=day).exists():
                flush_notifications(frequency)
        for delivery_id in Delivery.objects.filter(status='pending').values_list('pk', flat=True)[:20]:
            deliver(delivery_id)
        retry_ids = Delivery.objects.filter(status='failed', attempts__lt=3,
            attempted_at__lt=timezone.now()-timedelta(minutes=5)).values_list('pk', flat=True)[:10]
        for pk in retry_ids:
            from procurement.services.notifications import retry_delivery
            retry_delivery(pk)
