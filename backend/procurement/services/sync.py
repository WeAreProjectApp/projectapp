"""Resumable synchronization: one bounded source page per Huey job."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from procurement.models import Opportunity, Settings, SyncRun
from procurement.services.source import PAGE_SIZE, PublicClient, normalized_record


@transaction.atomic
def request_sync(actor=None):
    Settings.current()
    Settings.objects.select_for_update().get(pk=1)
    # A crashed worker leaves evidence, but must not block all later executions.
    SyncRun.objects.filter(status__in=['queued', 'running'], created_at__lt=timezone.now()-timedelta(hours=2)).update(
        status='failed', message='Sincronización interrumpida. Puede solicitarse otra.', finished_at=timezone.now())
    run = SyncRun.objects.filter(status__in=['queued', 'running']).first()
    if run is None:
        last = SyncRun.objects.filter(status='success').first()
        since = (last.started_at-timedelta(days=2)).date().isoformat() if last else None
        run = SyncRun.objects.create(requested_by=actor, cursor={'offset': 0, 'since': since, 'phase': 'source'})
        from procurement.tasks import sync_page
        transaction.on_commit(lambda: sync_page(run.pk))
    return run


def synchronize_page(run_id, client=None):
    run = SyncRun.objects.get(pk=run_id)
    if run.status not in ('queued', 'running'):
        return False
    client = client or PublicClient()
    run.status = 'running'
    run.started_at = run.started_at or timezone.now()
    cursor = run.cursor
    try:
        if cursor['phase'] == 'source':
            records = client.page(offset=cursor['offset'], since=cursor['since'], lookback=Settings.current().lookback_days)
        else:
            ids = list(Opportunity.objects.filter(classifications__isnull=False).order_by('source_id')
                       .values_list('source_id', flat=True).distinct()[cursor['offset']:cursor['offset']+100])
            records = client.page(ids=ids) if ids else []
        changed = []
        seen = set()
        for record in records:
            try:
                source_id, data = normalized_record(record)
                if source_id in seen:
                    continue
                seen.add(source_id)
                opportunity, created = Opportunity.objects.update_or_create(source_id=source_id, defaults=data)
                run.processed += 1
                run.created += int(created)
                changed.append(opportunity.pk)
            except (ValueError, TypeError, ArithmeticError):
                run.errors += 1
        if changed:
            from procurement.services.notifications import evaluate_opportunities
            evaluate_opportunities(changed)
        if cursor['phase'] == 'source' and len(records) == PAGE_SIZE:
            cursor['offset'] += PAGE_SIZE
        elif cursor['phase'] == 'source':
            cursor.update(phase='tracked', offset=0)
        elif records and len(ids) == 100:
            cursor['offset'] += 100
        else:
            run.status = 'partial' if run.errors else 'success'
            run.finished_at = timezone.now()
        cursor['failures'] = 0
        run.message = f'{run.errors} registros no procesados.' if run.errors else ''
    except Exception:
        cursor['failures'] = cursor.get('failures', 0) + 1
        run.message = 'No fue posible actualizar los datos públicos. Se conserva la información anterior.'
        if cursor['failures'] >= 3:
            run.status = 'failed'
            run.finished_at = timezone.now()
    run.cursor = cursor
    run.save()
    return run.status == 'running'
