"""Private, durable scan results; only complete scans reconcile observations."""
from datetime import timedelta
from time import monotonic

from django.conf import settings

from django.db import transaction
from django.utils import timezone

from content.models import DataIntegrityFinding, DataIntegrityReview, DataIntegrityScan, DataIntegrityScanLease
from content.services.data_integrity import catalog, engine
from content.services.data_integrity.hashing import digest, canonical
from content.services.data_integrity.scope import Scope, resolve_scope
from content.services.data_integrity.types import IntegrityConflict

LEASE_TIME = timedelta(minutes=30)


class ScanLimit(Exception):
    def __init__(self, code):
        self.code = code


def coverage(scope, **filters):
    selected = engine.select_rules(scope, **filters)
    wanted = [rule for rule in catalog.rules()
              if (not filters.get('domains') or rule.domain in filters['domains'])
              and (not filters.get('rule_ids') or rule.id in filters['rule_ids'])
              and (not filters.get('severity') or rule.severity in filters['severity'])]
    return {'evaluated_rules': [rule.id for rule in selected], 'skipped_rules': [
        {'rule_id': rule.id, 'reason': 'Requiere un barrido completo.'}
        for rule in wanted if rule not in selected
    ]}


def start_scan(scope, *, filters=None, actor=None, source='panel', request_id):
    filters = filters or {}
    values = {'scope': {'kind': scope.kind, 'id': scope.id}, 'filters': filters,
              'actor': actor, 'source': source, 'catalog_version': catalog.CATALOG_VERSION}
    with transaction.atomic():
        scan, created = DataIntegrityScan.objects.get_or_create(request_id=request_id, defaults=values)
        if scan.scope != values['scope'] or scan.filters != filters or scan.actor_id != getattr(actor, 'pk', None) or scan.source != source:
            raise IntegrityConflict('La solicitud ya existe con otros datos.', code='request_conflict')
        if created:
            from content.tasks import execute_data_integrity_scan
            transaction.on_commit(lambda: execute_data_integrity_scan(scan.pk), robust=True)
    return scan


@transaction.atomic
def _claim(scan_id):
    lease, _ = DataIntegrityScanLease.objects.select_for_update().get_or_create(key='scan')
    now = timezone.now()
    if lease.scan_id and lease.expires_at and lease.expires_at > now:
        return None
    if lease.scan_id:
        expired = DataIntegrityScan.objects.get(pk=lease.scan_id)
        DataIntegrityScan.objects.filter(pk=lease.scan_id, status='running').update(
            status='failed', error_code='worker_timeout', finished_at=now,
        )
        if expired.status == 'running' and not expired.request_id.startswith('integrity-recovery:'):
            start_scan(Scope(kind=expired.scope['kind'], id=expired.scope.get('id')),
                filters=expired.filters, actor=expired.actor, source=expired.source,
                request_id=f'integrity-recovery:{expired.pk}')
    scan = DataIntegrityScan.objects.select_for_update().get(pk=scan_id)
    if scan.status != 'queued':
        return None
    scan.status, scan.started_at = 'running', now
    scan.save(update_fields=['status', 'started_at'])
    lease.scan, lease.expires_at = scan, now + LEASE_TIME
    lease.save()
    return scan


@transaction.atomic
def _publish(scan, scope, results, evaluated):
    lease = DataIntegrityScanLease.objects.select_for_update().get(key='scan')
    if lease.scan_id != scan.pk or lease.expires_at <= timezone.now():
        return False  # A recovered worker cannot publish late.
    now = timezone.now()
    fingerprints = [payload['fingerprint'] for payload in results]
    existing = DataIntegrityFinding.objects.in_bulk(fingerprints, field_name='fingerprint')
    created, changed = [], []
    for payload in results:
        finding = existing.get(payload['fingerprint'])
        is_new = finding is None
        finding = finding or DataIntegrityFinding(fingerprint=payload['fingerprint'])
        finding.rule_id, finding.domain, finding.severity = payload['rule_id'], payload['domain'], payload['severity']
        finding.payload, finding.is_present, finding.last_seen_at = payload, True, now
        finding.resolved_at, finding.last_scan = None, scan
        (created if is_new else changed).append(finding)
    DataIntegrityFinding.objects.bulk_create(created, batch_size=100)
    DataIntegrityFinding.objects.bulk_update(changed, ['rule_id', 'domain', 'severity', 'payload', 'is_present',
        'last_seen_at', 'resolved_at', 'last_scan'], batch_size=100)
    if scope.is_all:
        # Scoped scans never resolve unrelated findings. Filtered sweeps only
        # reconcile their evaluated rules (including previous rule versions).
        DataIntegrityFinding.objects.filter(rule_id__in=evaluated['evaluated_rules'], is_present=True).exclude(
            fingerprint__in=fingerprints,
        ).update(is_present=False, resolved_at=now)
    scan.status, scan.finished_at, scan.results, scan.coverage = 'completed', now, results, evaluated
    scan.save(update_fields=['status', 'finished_at', 'results', 'coverage'])
    lease.scan, lease.expires_at = None, None
    lease.save()
    return True


def run_scan(scan_id):
    scan = _claim(scan_id)
    if scan is None:
        return
    try:
        scope = resolve_scope(scan.scope['kind'], scan.scope.get('id'))
        results, byte_count = [], 0
        started = monotonic()
        limit = getattr(settings, 'DATA_INTEGRITY_MAX_FINDINGS', 5000)
        for rule in engine.select_rules(scope, **scan.filters):
            for finding in engine.detect(rule, scope):
                payload = engine.finding_payload(rule, finding)
                results.append(payload)
                byte_count += len(canonical(payload).encode('utf-8'))
                if len(results) > limit or byte_count > 8 * 1024 * 1024:
                    raise ScanLimit('scan_result_limit')
            if monotonic() - started > 25:
                raise ScanLimit('scan_time_limit')
        _publish(scan, scope, results, coverage(scope, **scan.filters))
    except Exception as error:
        # Exceptions may contain private data. Persist a stable code only.
        with transaction.atomic():
            lease = DataIntegrityScanLease.objects.select_for_update().get(key='scan')
            if lease.scan_id == scan.pk:
                DataIntegrityScan.objects.filter(pk=scan.pk).update(
                    status='failed', error_code=error.code if isinstance(error, ScanLimit) else 'scan_failed', finished_at=timezone.now(),
                )
                lease.scan, lease.expires_at = None, None
                lease.save()


def scan_payload(scan):
    return {'id': scan.pk, 'status': scan.status, 'scope': scan.scope, 'filters': scan.filters,
            'catalog_version': scan.catalog_version, 'error_code': scan.error_code,
            'created_at': scan.created_at, 'started_at': scan.started_at,
            'finished_at': scan.finished_at, 'count': len(scan.results), 'coverage': scan.coverage}


def finding_payload(finding):
    return {**finding.payload, 'id': finding.pk, 'is_present': finding.is_present,
            'is_accepted': finding.is_accepted, 'first_seen_at': finding.first_seen_at,
            'last_seen_at': finding.last_seen_at, 'resolved_at': finding.resolved_at}


def list_findings(*, scan_id=None, status='pending', page=1, **filters):
    rows = DataIntegrityFinding.objects.all()
    if filters.get('fingerprint'):
        rows = rows.filter(fingerprint=filters['fingerprint'])
    if scan_id:
        scan = DataIntegrityScan.objects.get(pk=scan_id)
        rows = rows.filter(fingerprint__in=[item['fingerprint'] for item in scan.results])
    if status == 'pending':
        rows = rows.filter(is_present=True, is_accepted=False)
    elif status == 'accepted':
        rows = rows.filter(is_present=True, is_accepted=True)
    elif status == 'resolved':
        rows = rows.filter(is_present=False)
    for key, field in (('domains', 'domain'), ('rule_ids', 'rule_id'), ('severity', 'severity')):
        if filters.get(key):
            rows = rows.filter(**{field + '__in': filters[key]})
    count = rows.count()
    return {'count': count, 'page': page, 'pages': max(1, -(-count // 50)),
            'results': [finding_payload(row) for row in rows[(page - 1) * 50:page * 50]]}


@transaction.atomic
def review_finding(fingerprint, *, action, reason, request_id, actor, source):
    payload_hash = digest({'fingerprint': fingerprint, 'action': action, 'reason': reason,
                           'actor': actor.pk, 'source': source})
    previous = DataIntegrityReview.objects.filter(request_id=request_id).first()
    if previous:
        if previous.payload_hash != payload_hash:
            raise IntegrityConflict('La solicitud ya existe con otros datos.', code='request_conflict')
        return {'review_id': previous.pk, 'fingerprint': fingerprint, 'action': action}
    finding = DataIntegrityFinding.objects.select_for_update().get(fingerprint=fingerprint)
    # A concurrent retry may have waited on the finding lock above.
    previous = DataIntegrityReview.objects.filter(request_id=request_id).first()
    if previous:
        if previous.payload_hash != payload_hash:
            raise IntegrityConflict('La solicitud ya existe con otros datos.', code='request_conflict')
        return {'review_id': previous.pk, 'fingerprint': fingerprint, 'action': action}
    if not finding.is_present:
        raise IntegrityConflict('El hallazgo ya no está pendiente.', code='finding_resolved')
    finding.is_accepted = action == 'accept'
    finding.save(update_fields=['is_accepted'])
    review = DataIntegrityReview.objects.create(finding=finding, action=action, reason=reason,
        request_id=request_id, actor=actor, source=source, payload_hash=payload_hash)
    return {'review_id': review.pk, 'fingerprint': fingerprint, 'action': action}


def refresh_observed(scope, rule_ids):
    """After a fix/undo, recheck observed instances only; no broad reconciliation."""
    old = list(DataIntegrityFinding.objects.filter(rule_id__in=rule_ids))
    relevant = [row for row in old if any(scope.touches(ref['model'], {ref['id']})
                                        for ref in row.payload['subjects'])]
    current = {finding.fingerprint for rule, finding in engine.scan(scope, rule_ids=rule_ids)}
    DataIntegrityFinding.objects.filter(pk__in=[row.pk for row in relevant if row.fingerprint not in current]).update(
        is_present=False, resolved_at=timezone.now(),
    )

    DataIntegrityFinding.objects.filter(fingerprint__in=current).update(is_present=True, resolved_at=None, last_seen_at=timezone.now())
