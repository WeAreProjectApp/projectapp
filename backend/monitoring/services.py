import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied

from .models import Case, CaseActivity, Delivery, Report, Resource, Source


class Conflict(APIException):
    status_code = 409
    default_detail = 'El registro cambió. Actualizá la vista e intentá nuevamente.'


def snapshot(resource):
    return {'key': resource.key, 'name': resource.name, 'server': resource.server.key if resource.server_id else resource.key, 'environment': resource.environment}


@transaction.atomic
def ingest(credential, data):
    # Serializing one source also prevents simultaneous first deliveries from
    # racing the unique case/receipt constraints on both MySQL and SQLite.
    source = get_object_or_404(Source.objects.select_for_update().select_related('resource__server'), resource__key=data['resource'], key=data['source'])
    resource = source.resource
    server_key = resource.server.key if resource.server_id else resource.key
    if resource.retention_context_id or server_key != data['server'] or not resource.enabled or not credential.resources.filter(pk=resource.pk).exists():
        raise PermissionDenied('Recurso fuera del alcance de la credencial.')
    digest = hashlib.sha256(json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    previous = Delivery.objects.filter(source=source, external_id=data['external_id']).first()
    if previous:
        if previous.digest != digest:
            raise Conflict('El identificador ya fue usado con otro contenido.')
        return previous, False
    receipt = Delivery.objects.create(source=source, external_id=data['external_id'], digest=digest, kind=data['kind'], observed_at=data['observed_at'], evidence=data.get('evidence', {}))
    observed = data['observed_at']
    source.last_received_at = timezone.now()
    if not source.last_seen_at or observed >= source.last_seen_at:
        source.last_seen_at = observed
        if data['kind'] == 'heartbeat':
            source.enabled = data['enabled']
            source.last_error = data.get('error', '')
    source.save()
    if data['kind'] == 'report':
        receipt.report = Report.objects.create(source=source, title=data['title'], text=data['text'], observed_at=observed, resource_snapshot=snapshot(resource))
    elif data['kind'] in ('detection', 'recovery'):
        _observe_case(source, data, receipt)
    receipt.save(update_fields=['case', 'report'])
    return receipt, True


def _observe_case(source, data, receipt):
    fingerprint_hash = hashlib.sha256(data['fingerprint'].encode()).hexdigest()
    case = Case.objects.select_for_update().filter(source=source, fingerprint_hash=fingerprint_hash).first()
    if case is None and data['kind'] == 'recovery':
        return  # An orphan recovery is auditable, but is not an open problem.
    if case is None:
        case = Case.objects.create(source=source, fingerprint=data['fingerprint'], fingerprint_hash=fingerprint_hash, title=data['title'], severity=data['severity'], first_seen_at=data['observed_at'], last_seen_at=data['observed_at'], resource_snapshot=snapshot(source.resource))
    receipt.case = case
    if data.get('report_id'):
        receipt.report_id = get_object_or_404(
            Delivery.objects.only('report_id'),
            source=source, external_id=data['report_id'], kind='report',
        ).report_id
    observed = data['observed_at']
    case.first_seen_at = min(case.first_seen_at, observed)
    if data['kind'] == 'detection':
        case.detections += 1
        if case.state == 'resolved' and observed > case.closed_at:
            CaseActivity.objects.create(case=case, kind='reopened', from_state='resolved', to_state='pending')
            case.state = 'pending'
            case.closed_at = None
    if observed >= case.last_seen_at:
        case.last_seen_at = observed
        case.condition = 'recovered' if data['kind'] == 'recovery' else 'active'
        case.evidence = data.get('evidence', {})
        if data['kind'] == 'detection':
            case.title = data['title']
            case.severity = data['severity']
    case.version += 1
    case.save()


@transaction.atomic
def change_state(case_id, actor, data):
    case = get_object_or_404(
        Case.objects.select_related('source__resource').select_for_update(of=('self',)),
        pk=case_id,
    )
    if case.version != data['version']:
        raise Conflict()
    if case.state != data['state']:
        CaseActivity.objects.create(case=case, actor=actor, actor_name=actor.get_username(), kind='state', from_state=case.state, to_state=data['state'], text=data.get('note', ''))
        case.state = data['state']
        case.closed_at = max(timezone.now(), case.last_seen_at) if case.state == 'resolved' else None
        case.version += 1
        case.save(update_fields=['state', 'closed_at', 'version'])
    return case


def link_resource(resource_id, project):
    try:
        with transaction.atomic():
            resource = get_object_or_404(Resource.objects.select_for_update(), pk=resource_id, kind='project')
            resource.project = project
            resource.save(update_fields=['project'])
            return resource
    except IntegrityError as exc:
        raise Conflict('El proyecto ya está vinculado a otro recurso.') from exc
