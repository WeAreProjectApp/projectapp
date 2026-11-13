import hashlib
import json
from datetime import timedelta

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied

from .models import Control, Event, Target


class Conflict(APIException):
    status_code = 409
    default_detail = 'La configuración cambió. Recarga antes de guardar.'


def require_admin(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied('Se requiere acceso administrativo al Panel.')


def snapshot(control):
    return {key: getattr(control, key) for key in (
        'mode', 'suspension_title', 'suspension_text', 'banner_title', 'banner_text',
    )}


def runtime_payload(target):
    control = target.control
    prefix = 'suspension' if control.mode == 'suspended' else 'banner'
    message = {'title': '', 'text': ''} if control.mode == 'normal' else {
        'title': getattr(control, prefix + '_title'), 'text': getattr(control, prefix + '_text'),
    }
    payload = {'schema': 1, 'target_key': target.key, 'environment': 'production',
               'origins': target.origins, 'version': control.version, 'mode': control.mode, 'message': message}
    payload['digest'] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return payload


def target_payload(target):
    expected = runtime_payload(target)
    connected = target.last_seen_at is not None and target.last_seen_at >= timezone.now() - timedelta(seconds=45)
    matches = target.acknowledged_version == target.control.version and target.acknowledged_digest == expected['digest']
    if target.lifecycle != 'active':
        state = target.lifecycle
    elif target.last_error:
        state = 'error'
    elif target.last_seen_at is None:
        state = 'unintegrated'
    elif not connected:
        state = 'disconnected'
    else:
        state = 'confirmed' if matches else 'pending'
    return {'key': target.key, 'origins': target.origins, 'adapter': target.adapter,
            'lifecycle': target.lifecycle, 'state': state, 'acknowledged_version': target.acknowledged_version,
            'acknowledged_digest': target.acknowledged_digest, 'acknowledged_at': target.acknowledged_at,
            'acknowledged': target.acknowledged_payload,
            'last_seen_at': target.last_seen_at, 'error': target.last_error}


def control_payload(control):
    resource = control.resource
    return {'id': control.pk, 'name': resource.name, 'project_id': resource.project_id,
            'client': resource.project.client.get_full_name() if resource.project_id else '',
            'server': resource.server.name if resource.server_id else '', 'environment': resource.environment,
            'version': control.version, **snapshot(control),
            'targets': [target_payload(target) for target in control.targets.all()]}


def controls():
    return Control.objects.select_related('resource__server', 'resource__project__client').prefetch_related('targets__control')


def listing(actor, query):
    require_admin(actor)
    rows = controls().filter(resource__kind='project', resource__environment='production')
    if query.get('project_id'):
        rows = rows.filter(resource__project_id=query['project_id'])
    if query.get('search'):
        rows = rows.filter(Q(resource__name__icontains=query['search']) | Q(targets__origins__icontains=query['search'])).distinct()
    page = Paginator(rows.order_by('resource__name'), 20).get_page(query.get('page', 1))
    return {'results': [control_payload(row) for row in page], 'count': page.paginator.count,
            'page': page.number, 'pages': page.paginator.num_pages}


def detail(actor, control_id):
    require_admin(actor)
    return control_payload(get_object_or_404(controls(), pk=control_id))


@transaction.atomic
def update(actor, control_id, data, source):
    require_admin(actor)
    control = get_object_or_404(Control.objects.select_for_update().select_related('resource'), pk=control_id)
    if control.resource.environment != 'production' or control.resource.kind != 'project':
        raise PermissionDenied('El destino no es un proyecto de producción.')
    if control.version != data['expected_version']:
        raise Conflict()
    before = snapshot(control)
    if 'mode' in data:
        control.mode = data['mode']
    else:
        prefix = 'suspension' if data['message_mode'] == 'suspended' else 'banner'
        setattr(control, prefix + '_title', data['title'])
        setattr(control, prefix + '_text', data['text'])
    after = snapshot(control)
    if before != after:
        control.version += 1
        control.save()
        Event.objects.create(control=control, actor=actor, actor_name=actor.get_username(), source=source,
                             before=before, after=after, version=control.version)
    return detail(actor, control_id)


def events(actor, control_id, page_number=1):
    require_admin(actor)
    get_object_or_404(Control, pk=control_id)
    page = Paginator(Event.objects.filter(control_id=control_id), 20).get_page(page_number)
    return {'results': [{'id': row.pk, 'actor': row.actor_name, 'source': row.source, 'before': row.before,
                         'after': row.after, 'version': row.version, 'at': row.created_at} for row in page],
            'page': page.number, 'pages': page.paginator.num_pages}


@transaction.atomic
def receive(credential, data):
    target = get_object_or_404(Target.objects.select_for_update().select_related('control__resource'),
                              key=data['target_key'], runtimecredential=credential, lifecycle='active',
                              control__resource__environment='production')
    current = runtime_payload(target)
    if data['version'] != current['version'] or data['digest'] != current['digest']:
        raise Conflict('El recibo no corresponde a la configuración vigente.')
    target.last_seen_at = timezone.now()
    target.last_error = '' if data['applied'] else 'El sitio aún no sirve la configuración recibida.'
    if data['applied']:
        target.acknowledged_version = data['version']
        target.acknowledged_digest = data['digest']
        target.acknowledged_payload = {'mode': current['mode'], 'message': current['message'], 'version': current['version']}
        target.acknowledged_at = target.last_seen_at
    target.save()
    return {'accepted': True, 'applied': data['applied']}
