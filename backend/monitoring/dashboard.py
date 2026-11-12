"""Read models for monitoring: bounded pages, stable consultation and host metrics."""
import hashlib
import json
import secrets
from collections import Counter
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.db.models import Max, OuterRef, Subquery
from django.utils import timezone
from rest_framework.exceptions import APIException

from .models import CapacityAllocation, CapacityChange, CaseActivity, Delivery, Resource, Source, TelemetrySample
from .serializers import CapacitySerializer, CaseSerializer, ReportSerializer, SourceSerializer
from .services import Conflict

PAGE_SIZE = 25
SNAPSHOT_TTL = 900
SAMPLE_FIELDS = ('cpu_percent', 'cpu_count', 'load_1m', 'ram_total_bytes', 'ram_used_bytes', 'disk_total_bytes', 'disk_used_bytes')
PERIODS = {'24h': (1, 60), '7d': (7, 900), '30d': (30, 3600), '90d': (90, 21600)}


class SnapshotExpired(APIException):
    status_code = 409
    default_code = 'snapshot_expired'
    default_detail = 'La consulta venció. Actualizá para continuar con los mismos filtros.'


def source_scope(data):
    query = Source.objects.select_related('resource')
    for parameter, field in [('resource', 'resource_id'), ('source', 'pk'), ('kind', 'resource__kind')]:
        if parameter in data:
            query = query.filter(**{field: data[parameter]})
    return query


def revision():
    # Primary-key maxima use indexes even as histories grow. Source observations
    # also cover compacted heartbeat receipts whose identity does not change.
    stamps = [Delivery.objects.aggregate(value=Max('pk'))['value'],
              CaseActivity.objects.aggregate(value=Max('pk'))['value'],
              CapacityChange.objects.aggregate(value=Max('pk'))['value']]
    sources = list(Source.objects.values_list('id', 'enabled', 'expected_interval', 'last_seen_at', 'last_error'))
    now = timezone.now()
    freshness = [bool(seen and (now - seen).total_seconds() > interval * 2) for _, _, interval, seen, _ in sources]
    return hashlib.sha256(json.dumps([stamps, sources, freshness], default=str).encode()).hexdigest()


def snapshot_signature(actor, data, reports):
    filters = {key: value for key, value in data.items() if key not in {'page', 'snapshot', 'activities_page', 'deliveries_page'}}
    return hashlib.sha256(json.dumps([actor.pk, reports, filters], sort_keys=True, default=str).encode()).hexdigest()


def frozen_page(query, data, actor, reports=False):
    """Cache projections in small pages; no incident text/evidence is copied into cache."""
    token = data['snapshot']
    signature = snapshot_signature(actor, data, reports)
    if token == 'new':
        token = secrets.token_hex(24)
        root = f'monitoring:snapshot:{token}'
        captured = timezone.now()
        mark = revision()
        serializer = ReportSerializer if reports else CaseSerializer
        active, states, count, batch, pages, attention = Counter(), Counter(), 0, [], {}, []
        latest_report = None
        for row in query.iterator(chunk_size=250):
            record = serializer(row).data
            batch.append(record)
            count += 1
            if reports and latest_report is None:
                latest_report = record['observed_at']
            if not reports:
                states[record['state']] += 1
                if record['condition'] == 'active':
                    active[record['severity']] += 1
                    # At most ten per severity; presentation sorts by severity then recency.
                    if sum(item['severity'] == record['severity'] for item in attention) < 10:
                        attention.append(record)
            if len(batch) == PAGE_SIZE:
                pages[f'{root}:{(count - 1) // PAGE_SIZE + 1}'] = batch
                batch = []
            if len(pages) == 10:
                cache.set_many(pages, SNAPSHOT_TTL)
                pages = {}
        if batch:
            pages[f'{root}:{(count - 1) // PAGE_SIZE + 1}'] = batch
        cache.set_many(pages, SNAPSHOT_TTL)
        sources = SourceSerializer(source_scope(data), many=True).data
        health = Counter(source['health'] for source in sources)
        metadata = {
            'signature': signature, 'count': count, 'revision': mark, 'captured_at': captured.isoformat(),
            'summary': {'total': count, 'active': dict(active), 'followup': states['pending'] + states['reviewing'],
                        'sources': dict(health), 'latest_report_at': latest_report},
            'attention': sorted(attention, key=lambda item: {'critical': 0, 'warning': 1, 'info': 2}[item['severity']]),
            'sources': sources,
        }
        cache.set(root, metadata, SNAPSHOT_TTL)
    else:
        root = f'monitoring:snapshot:{token}'
        metadata = cache.get(root)
        if not metadata or metadata['signature'] != signature:
            raise SnapshotExpired()
    page = min(data['page'], max(1, (metadata['count'] + PAGE_SIZE - 1) // PAGE_SIZE))
    rows = cache.get(f'{root}:{page}', [])
    if metadata['count'] and not rows:
        raise SnapshotExpired()
    return {key: value for key, value in metadata.items() if key != 'signature'} | {
        'snapshot': token, 'page': page, 'page_size': PAGE_SIZE, 'results': rows,
    }


def current_samples(resources):
    latest = TelemetrySample.objects.filter(resource_id=OuterRef('resource_id')).order_by('-observed_at', '-pk')
    return TelemetrySample.objects.filter(resource_id__in=resources, pk=Subquery(latest.values('pk')[:1]))


def host_status(data):
    resources = Resource.objects.filter(kind='server', enabled=True)
    if data.get('kind') == 'project':
        projects = Resource.objects.filter(kind='project', enabled=True)
        if data.get('resource'):
            projects = projects.filter(pk=data['resource'])
        if data.get('source'):
            projects = projects.filter(sources__pk=data['source'])
        resources = resources.filter(pk__in=projects.values('server_id'))
    elif data.get('resource'):
        resource = Resource.objects.filter(pk=data['resource']).first()
        resources = resources.filter(pk=resource.server_id if resource and resource.kind == 'project' else data['resource'])
    elif data.get('source'):
        resources = resources.filter(pk__in=source_scope(data).values('resource_id'))
    samples = {sample.resource_id: sample for sample in current_samples(resources.values('pk'))}
    result = []
    now = timezone.now()
    for resource in resources:
        sample = samples.get(resource.pk)
        metrics, pressure = None, []
        fresh = bool(sample and now - sample.observed_at <= timedelta(minutes=2))
        if sample:
            metrics = {key: getattr(sample, key) for key in SAMPLE_FIELDS}
            metrics['observed_at'] = sample.observed_at.isoformat()
            if fresh:
                if sample.ram_used_bytes / sample.ram_total_bytes >= .85:
                    pressure.append('ram')
                if sample.disk_used_bytes / sample.disk_total_bytes >= .85:
                    pressure.append('disk')
                if sample.load_1m >= 3 * sample.cpu_count:
                    pressure.append('load')
        result.append({'id': resource.pk, 'name': resource.name, 'metrics': metrics,
                       'health': 'current' if fresh else 'stale' if sample else 'no_data', 'pressure': pressure})
    return result


def series(resource, period):
    days, interval = PERIODS[period]
    now = timezone.now()
    rows = TelemetrySample.objects.filter(resource=resource, observed_at__gte=now - timedelta(days=days), observed_at__lte=now)
    buckets = {}
    for row in rows.values('observed_at', *SAMPLE_FIELDS).iterator(chunk_size=2000):
        stamp = int(row['observed_at'].timestamp()) // interval * interval
        bucket = buckets.setdefault(stamp, {'count': 0, 'sum': Counter(), 'max': {}, 'valid': Counter()})
        bucket['count'] += 1
        for field in SAMPLE_FIELDS:
            value = row[field]
            if value is not None:
                bucket['sum'][field] += value
                bucket['valid'][field] += 1
                bucket['max'][field] = max(bucket['max'].get(field, value), value)
    points = []
    # Missing buckets are explicit nulls; do not manufacture measurements.
    start = int((now - timedelta(days=days)).timestamp()) // interval * interval
    end = int(now.timestamp()) // interval * interval
    for stamp in range(start, end + 1, interval):
        bucket = buckets.get(stamp)
        averages = {field: bucket['sum'][field] / bucket['valid'][field] if bucket and bucket['valid'][field] else None for field in SAMPLE_FIELDS}
        points.append({'timestamp': stamp * 1000, 'count': bucket['count'] if bucket else 0,
                       'average': averages, 'max': bucket['max'] if bucket else {}})
    latest = rows.order_by('-observed_at', '-pk').first()
    return {'period': period, 'interval_seconds': interval, 'points': points,
            'last_observed_at': latest.observed_at if latest else None,
            'capacity': {key: getattr(latest, key) for key in SAMPLE_FIELDS if key.endswith('total_bytes') or key == 'cpu_count'} if latest else None}


@transaction.atomic
def save_capacity(resource, actor, data):
    resource = Resource.objects.select_for_update().get(pk=resource.pk, kind='project')
    allocation = CapacityAllocation.objects.filter(resource=resource).first()
    version = allocation.version if allocation else 0
    if data['version'] != version:
        raise Conflict()
    before = dict(CapacitySerializer(allocation).data) if allocation else {}
    if allocation is None:
        allocation = CapacityAllocation(resource=resource)
    for key, value in data.items():
        if key != 'version':
            setattr(allocation, key, value)
    allocation.version = version + 1
    allocation.save()
    after = dict(CapacitySerializer(allocation).data)
    CapacityChange.objects.create(allocation=allocation, actor=actor, actor_name=actor.get_username(), before=before, after=after)
    return allocation
