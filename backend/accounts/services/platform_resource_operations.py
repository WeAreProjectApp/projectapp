"""Project-locked resource writes using the existing delivery version and receipts."""
import hashlib
import json

from django.db import transaction

from accounts.models import DeliveryOperation, DeliveryWorkspace
from accounts.services.delivery_access import DeliveryConflict, fail, project_for_actor


def _fingerprint(value):
    if hasattr(value, 'chunks'):
        position = value.tell()
        value.seek(0)
        digest = hashlib.sha256()
        for chunk in value.chunks():
            digest.update(chunk)
        value.seek(position)
        return {'filename': value.name, 'size': value.size, 'sha256': digest.hexdigest()}
    if isinstance(value, dict):
        return {name: _fingerprint(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_fingerprint(item) for item in value]
    return value


def workspace_version(project):
    return DeliveryWorkspace.objects.filter(project=project).values_list('version', flat=True).first() or 0


@transaction.atomic
def perform(project_id, actor, operation, payload, change, *, expected_version=None,
            request_id=None, credential=None, expected_client_id=None):
    project = project_for_actor(project_id, actor, lock=True)
    if expected_client_id is not None and expected_client_id != project.client_id:
        raise DeliveryConflict('El destinatario del proyecto cambió. Revisa de nuevo la operación.')
    workspace, _ = DeliveryWorkspace.objects.get_or_create(project=project)
    if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()
                                   or len(request_id) > 100):
        fail('Usa un identificador de petición de hasta cien caracteres.')
    digest = hashlib.sha256(json.dumps({
        'operation': operation, 'payload': _fingerprint(payload),
        'client_id': project.client_id, 'credential_id': getattr(credential, 'pk', None),
    }, sort_keys=True, default=str).encode()).hexdigest()
    if request_id:
        receipt = DeliveryOperation.objects.filter(project=project, request_id=request_id).first()
        if receipt:
            if receipt.actor_id != actor.pk or receipt.fingerprint != digest:
                raise DeliveryConflict('El identificador ya corresponde a otra operación.')
            return receipt.response
    if expected_version is not None and (
        type(expected_version) is not int or expected_version != workspace.version
    ):
        raise DeliveryConflict()
    response = change(project)
    workspace.version += 1
    workspace.save(update_fields=['version'])
    if request_id:
        DeliveryOperation.objects.create(project=project, request_id=request_id, actor=actor,
                                         fingerprint=digest, response=response)
    return response
