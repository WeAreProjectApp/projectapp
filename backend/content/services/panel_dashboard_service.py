"""Global panel dashboard: consolidated KPIs across modules.

Single payload for ``GET /api/panel/dashboard/`` combining finance
(accounting, superuser-gated by the caller), proposals (cheap core), the
additional-modules commercial summary and operations (tasks, documents,
diagnostics, emails, hour packages), plus the cross-module "attention" list
that powers the dashboard radar.
"""

from datetime import timedelta

from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from content.models import (
    AdditionalModule,
    AdditionalModuleShareLink,
    BusinessProposal,
    Document,
    EmailLog,
    HostingRecord,
    HourPackage,
    Task,
    WebAppDiagnostic,
)
from content.services import accounting_service
from content.services.proposal_analytics_service import build_dashboard_core
from content.utils import today_bogota

EMAIL_FAILED_STATUSES = (EmailLog.Status.FAILED, EmailLog.Status.BOUNCED)
EMAIL_OK_STATUSES = (EmailLog.Status.SENT, EmailLog.Status.DELIVERED)

# Proposals sent this long ago without a first view feed the attention radar.
STALE_PROPOSAL_DAYS = 7
# Recurring payments billed within this window feed the attention radar.
RECURRING_DUE_DAYS = 7

_SEVERITY_RANK = {'danger': 0, 'warning': 1, 'info': 2}


def _finance_block(year):
    hostings = HostingRecord.objects.aggregate(
        active_count=Count('id', filter=Q(is_active=True)),
        monthly_income=Sum('monthly_value', filter=Q(is_active=True)),
        total_paid=Sum('total_paid'),
    )
    return {
        'year': year,
        **accounting_service.year_totals(year),
        'pocket_balance': accounting_service.pocket_balance(),
        'expected_current_month': accounting_service.expected_current_month(),
        'card_debt': accounting_service.card_debt_total(),
        'recurring_monthly_cost': accounting_service.recurring_monthly_cost(),
        'hostings': {
            'active_count': hostings['active_count'] or 0,
            'monthly_income': hostings['monthly_income'] or 0,
            'total_paid': hostings['total_paid'] or 0,
        },
        'monthly': accounting_service.monthly_breakdown(year),
    }


def _tasks_summary(today):
    not_done = ~Q(status=Task.Status.DONE)
    return Task.objects.filter(is_archived=False).aggregate(
        open=Count('id', filter=not_done),
        overdue=Count('id', filter=Q(due_date__lt=today) & not_done),
        overdue_high=Count(
            'id',
            filter=Q(due_date__lt=today, priority=Task.Priority.HIGH) & not_done,
        ),
        blocked=Count('id', filter=Q(status=Task.Status.BLOCKED)),
        high_priority_open=Count(
            'id', filter=Q(priority=Task.Priority.HIGH) & not_done,
        ),
    )


def _status_counts(model, queryset=None):
    counts = dict(
        (queryset if queryset is not None else model.objects.all())
        .values_list('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    return {value: counts.get(value, 0) for value, _label in model.Status.choices}


def _documents_summary(today):
    collection = Document.objects.filter(
        commercial_status=Document.CommercialStatus.ISSUED,
    ).aggregate(
        issued_count=Count('id'),
        overdue_issued=Count('id', filter=Q(due_date__lt=today)),
        outstanding_total=Sum('total'),
    )
    return {
        # Lo archivado sale de circulación: no cuenta en el resumen del panel.
        'by_status': _status_counts(
            Document, queryset=Document.objects.filter(is_archived=False),
        ),
        'collection_accounts': {
            'issued_count': collection['issued_count'] or 0,
            'overdue_issued': collection['overdue_issued'] or 0,
            'outstanding_total': collection['outstanding_total'] or 0,
        },
    }


def _diagnostics_summary():
    by_status = _status_counts(WebAppDiagnostic)
    active_pipeline = (
        by_status.get('sent', 0)
        + by_status.get('viewed', 0)
        + by_status.get('negotiating', 0)
    )
    accepted_value = WebAppDiagnostic.objects.filter(
        status__in=(
            WebAppDiagnostic.Status.ACCEPTED,
            WebAppDiagnostic.Status.FINISHED,
        ),
    ).aggregate(total=Sum('investment_amount'))['total'] or 0
    return {
        'by_status': by_status,
        'active_pipeline': active_pipeline,
        'accepted_value': accepted_value,
    }


def _additional_modules_summary():
    """Small commercial snapshot for the global panel dashboard."""

    usable_link = Q(
        is_active=True,
        selected_modules__is_active=True,
        selected_modules__category__is_active=True,
    )
    link_metrics = AdditionalModuleShareLink.objects.aggregate(
        active_share_count=Count('id', filter=usable_link, distinct=True),
        unopened_active_share_count=Count(
            'id',
            filter=usable_link & Q(first_viewed_at__isnull=True),
            distinct=True,
        ),
        last_viewed_at=Max('last_viewed_at'),
    )
    return {
        'active_module_count': AdditionalModule.objects.filter(
            is_active=True,
            category__is_active=True,
        ).count(),
        **link_metrics,
    }


def _emails_summary(now):
    from content.services.email_log_service import representative_delivery_queryset

    last_30d = representative_delivery_queryset(EmailLog.objects.filter(
        sent_at__gte=now - timedelta(days=30),
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    ))
    totals = last_30d.aggregate(
        total=Count('id'),
        sent_count=Count('id', filter=Q(status__in=EMAIL_OK_STATUSES)),
        failed_count=Count('id', filter=Q(status__in=EMAIL_FAILED_STATUSES)),
    )
    success_rate = (
        round(totals['sent_count'] / totals['total'] * 100, 1)
        if totals['total'] else None
    )
    trend_rows = (
        representative_delivery_queryset(EmailLog.objects.filter(
            sent_at__gte=now - timedelta(days=14),
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
        ))
        .annotate(day=TruncDate('sent_at'))
        .values('day')
        .annotate(
            total=Count('id'),
            failed=Count('id', filter=Q(status__in=EMAIL_FAILED_STATUSES)),
        )
        .order_by('day')
    )
    return {
        'total_30d': totals['total'],
        'sent_count': totals['sent_count'],
        'failed_count': totals['failed_count'],
        'success_rate': success_rate,
        'daily_trend': [
            {
                'date': row['day'].isoformat() if row['day'] else '',
                'total': row['total'],
                'failed': row['failed'],
            }
            for row in trend_rows
        ],
    }


def _operations_block(today, now):
    return {
        'tasks': _tasks_summary(today),
        'documents': _documents_summary(today),
        'diagnostics': _diagnostics_summary(),
        'emails': _emails_summary(now),
        'hour_packages': {
            'active_count': HourPackage.objects.filter(is_active=True, pricing_model='requirements').count(),
        },
    }


def _attention_block(operations, today, now, *, include_finance):
    from content.services.dashboard_attention_service import TYPES, attention_records, record_count

    items = []
    for kind in TYPES:
        if kind == 'recurring_due' and not include_finance:
            continue
        records = attention_records(kind, today, now)
        count = record_count(records)
        if not count:
            continue
        severity, meta = 'danger', {}
        if kind == 'tasks_overdue':
            high = records.filter(priority=Task.Priority.HIGH).count()
            severity, meta = ('danger' if high else 'warning'), {'high_priority': high}
        elif kind == 'proposals_stale':
            severity, meta = 'warning', {'days': STALE_PROPOSAL_DAYS}
        elif kind == 'recurring_due':
            days = (records[0].radar_charge_date - today).days
            severity, meta = ('warning' if days <= 3 else 'info'), {'next_days': days}
        items.append({'type': kind, 'severity': severity, 'count': count, 'meta': meta})
    items.sort(key=lambda item: (_SEVERITY_RANK[item['severity']], -item['count']))
    return items


def build_panel_dashboard(*, include_finance):
    """Consolidated dashboard payload; finance only when the caller allows it."""
    today = today_bogota()
    now = timezone.now()
    operations = _operations_block(today, now)
    return {
        'generated_at': now.isoformat(),
        'finance': _finance_block(today.year) if include_finance else None,
        'proposals': build_dashboard_core(),
        'additional_modules': _additional_modules_summary(),
        'operations': operations,
        'attention': _attention_block(
            operations, today, now, include_finance=include_finance,
        ),
    }
