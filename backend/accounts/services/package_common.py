"""Shared locks, authority and operation receipts for requirement packages."""
import hashlib
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import Project
from accounts.models_requirement_packages import PackageOperation
from accounts.services.delivery_access import DeliveryConflict, project_for_actor, require_admin


def check_version(record, expected):
    if record.version != expected:
        raise DeliveryConflict('El registro cambió. Actualiza antes de continuar.')


def owned(queryset, project, **lookup):
    row = queryset.filter(project=project, client_id=project.client_id, **lookup).first()
    if row is None:
        raise NotFound('Registro no encontrado en este proyecto.')
    return row


def mutate(project_id, actor, action, data, change, *, admin=False,
           allow_inactive_settlement=False, trusted_settlement=False):
    """A project serializes balance writes, including requests against different orders."""
    if admin:
        require_admin(actor)
    normalized = json.loads(json.dumps(data, default=str))
    fingerprint = hashlib.sha256(json.dumps([project_id, action, normalized], sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        if trusted_settlement and allow_inactive_settlement:
            project = Project.objects.select_for_update().select_related('client').filter(pk=project_id).first()
            if project is None:
                raise NotFound('Proyecto no encontrado.')
        else:
            project = project_for_actor(project_id, actor, lock=True)
        if not allow_inactive_settlement:
            if project.status in ('archived', 'decommissioned', 'suspended'):
                raise ValidationError('El proyecto no permite nuevas operaciones de paquetes.')
            profile = getattr(project.client, 'profile', None)
            if profile and profile.archived_at:
                raise ValidationError('El cliente está archivado.')
        # Actor lock covers request_id collisions across two different projects.
        get_user_model().objects.select_for_update().get(pk=actor.pk)
        previous = PackageOperation.objects.filter(actor=actor, request_id=data['request_id']).first()
        if previous:
            if previous.fingerprint != fingerprint:
                raise DeliveryConflict('El identificador corresponde a otra operación.')
            return previous.receipt
        result = change(project)
        result = json.loads(json.dumps(result, default=str))
        PackageOperation.objects.create(project=project, actor=actor, request_id=data['request_id'],
                                        fingerprint=fingerprint, receipt=result)
        return result


def notify_team(project, title, *, request_id=None):
    from accounts.services.notifications import notify_project_admins
    notify_project_admins(project, 'general', title, related_object_type='package_request' if request_id else 'package_order',
                          related_object_id=request_id or project.pk)


def notify_client(project, title, *, request_id=None):
    from accounts.services.notifications import notify_project_client
    notify_project_client(project, 'general', title, related_object_type='package_request' if request_id else 'package_order',
                          related_object_id=request_id or project.pk)
