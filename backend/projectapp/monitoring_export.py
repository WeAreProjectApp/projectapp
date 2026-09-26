"""Bounded Silk sampling and a local, non-secret monitoring export."""
import hashlib
import json
import logging
import os
import random
from pathlib import Path


def should_profile(request):
    from django.conf import settings

    path = request.path.lower()
    if not path.startswith('/api/'):
        return False
    if any(part in path for part in ('/auth', '/login', '/token', '/credential', '/access', '/monitoring', '/health', '/mcp', '/secure-links')):
        return False
    return random.random() < getattr(settings, 'MONITORING_SILK_SAMPLE_PERCENT', 5) / 100


def route_label(path):
    from django.urls import Resolver404, resolve

    try:
        route = str(resolve(path.split('?', 1)[0]).route)
    except Resolver404:
        route = '/unresolved'
    # The route pattern has placeholders; URL arguments and SQL never leave the host.
    return route[:160]


def export_report(slow_queries, suspects, *, count_attribute='query_count'):
    from django.conf import settings
    from django.utils import timezone

    findings = {}
    for query in slow_queries:
        route = route_label(query.request.path)
        identity = 'slow:' + route
        previous = findings.get(identity)
        duration = round(query.time_taken or 0, 2)
        if previous and previous['evidence']['duration_ms'] >= duration:
            continue
        findings[identity] = {
            'fingerprint': hashlib.sha256(identity.encode()).hexdigest(),
            'title': ('Consulta lenta: ' + route)[:240],
            'evidence': {'route': route, 'duration_ms': duration, 'threshold': getattr(settings, 'SLOW_QUERY_THRESHOLD_MS', 500)},
        }
    for request in suspects:
        route = route_label(request.path)
        identity = 'n1:' + route
        count = getattr(request, count_attribute)
        previous = findings.get(identity)
        if previous and previous['evidence']['query_count'] >= count:
            continue
        findings[identity] = {
            'fingerprint': hashlib.sha256(identity.encode()).hexdigest(),
            'title': ('Posible N+1: ' + route)[:240],
            'evidence': {'route': route, 'query_count': count, 'threshold': getattr(settings, 'N_PLUS_ONE_THRESHOLD', 10)},
        }
    sample = getattr(settings, 'MONITORING_SILK_SAMPLE_PERCENT', 5)
    now = timezone.now()
    document = {
        'observed_at': now.isoformat(),
        'summary': f'Muestra Silk: {sample}% de solicitudes elegibles; {len(findings)} hallazgos agrupados. Un conteo alto es indicio de N+1, no confirmación.',
        'findings': list(findings.values()),
    }
    directory = Path(settings.BASE_DIR) / 'logs' / 'monitoring'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'silk-{now:%Y-%m-%d-%H%M%S}.json'
    temporary = target.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(target)


def export_report_safely(*args, **kwargs):
    try:
        export_report(*args, **kwargs)
    except (OSError, ValueError):
        # An outbox/filesystem failure must not suppress the existing report.
        logging.getLogger('backups').exception('Local monitoring export failed; continuing legacy report')
