"""Explicit, revocable client grants over the existing project_access source."""
import json
from urllib.parse import urlsplit

from django.core import signing
from django.db import transaction
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import ProjectAdminAccess
from accounts.models_project_client_access import ProjectClientAccessEvent, ProjectClientAccessPolicy
from accounts.serializers_project_client_access import ACCESS_FIELDS, ENVIRONMENTS, ClientAccessPolicySerializer, EmptyAccessSerializer
from accounts.serializers_project_ideas import validated
from accounts.services.credential_cipher import decrypt_secret
from accounts.services.project_collaboration_access import CollaborationConflict, check_version, paginate, project_for_actor

TOKEN_SALT = 'project-client-access-preview-v1'


def empty_matrix():
    return {environment: {field: False for field in ACCESS_FIELDS} for environment in ENVIRONMENTS}


def _sources(project):
    accesses = {access.environment: access for access in project.admin_accesses.all()}
    result = {}
    for environment in ENVIRONMENTS:
        access = accesses.get(environment)
        result[environment] = {
            'site_url': project.production_url if environment == 'production' else project.staging_url,
            'admin_url': access.admin_url if access else '',
            'admin_username': access.admin_username if access else '',
            'admin_password': access.admin_password_encrypted if access else '',
        }
    return result


def _clean_url(value):
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme in ('http', 'https') and parsed.hostname and not (
            parsed.username or parsed.password or parsed.query or parsed.fragment))
    except ValueError:
        return False


def _binding(project, environment, field, value):
    return salted_hmac(TOKEN_SALT, json.dumps([project.pk, project.client_id, environment, field, value]), algorithm='sha256').hexdigest()


def _source_digest(project, sources):
    return salted_hmac(TOKEN_SALT, json.dumps([project.pk, project.client_id, sources], sort_keys=True), algorithm='sha256').hexdigest()


def _availability(sources):
    return {environment: {field: bool(value) and (field not in ('site_url', 'admin_url') or _clean_url(value))
                          for field, value in fields.items()} for environment, fields in sources.items()}


def _effective(project, policy, sources):
    result = empty_matrix()
    if policy is None or policy.recipient_id != project.client_id:
        return result
    available = _availability(sources)
    for environment in ENVIRONMENTS:
        for field in ACCESS_FIELDS:
            result[environment][field] = bool(
                policy.permissions.get(environment, {}).get(field) is True
                and available[environment][field]
                and policy.bindings.get(f'{environment}.{field}') == _binding(project, environment, field, sources[environment][field]))
    return result


def _policy(project):
    return ProjectClientAccessPolicy.objects.filter(project_id=project.pk).first()


def _admin_payload(project, policy, sources):
    permissions = empty_matrix()
    if policy:
        for environment in ENVIRONMENTS:
            for field in ACCESS_FIELDS:
                permissions[environment][field] = policy.permissions.get(environment, {}).get(field) is True
    return {'project_id': project.pk, 'version': policy.version if policy else 0,
            'permissions': permissions,
            'effective_permissions': _effective(project, policy, sources),
            'available_fields': _availability(sources),
            'source_token': signing.dumps({'project_id': project.pk, 'recipient_id': project.client_id,
                                          'digest': _source_digest(project, sources)}, salt=TOKEN_SALT)}


def get_policy(project_id, actor, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, admin=True)
    return _admin_payload(project, _policy(project), _sources(project))


def policy_etag(project_id, actor, *, channel='panel'):
    project = project_for_actor(project_id, actor, channel=channel, admin=True)
    policy = _policy(project)
    return f'{policy.version if policy else 0}:{_source_digest(project, _sources(project))}'


def _event(project, actor, action, fields, version):
    ProjectClientAccessEvent.objects.create(project=project, recipient_id=project.client_id,
                                           actor=actor, action=action, fields=fields, policy_version=version)


@transaction.atomic
def update_policy(project_id, actor, data, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, admin=True, lock=True)
    values = validated(ClientAccessPolicySerializer, data)
    # Writers also lock Project first; the token protects a stale editor/confirmation.
    list(ProjectAdminAccess.objects.select_for_update().filter(project=project))
    sources = _sources(project)
    try:
        token = signing.loads(values['source_token'], salt=TOKEN_SALT, max_age=1800)
    except signing.BadSignature:
        raise CollaborationConflict('Actualiza la vista previa de los datos antes de compartirlos.')
    expected = {'project_id': project.pk, 'recipient_id': project.client_id, 'digest': _source_digest(project, sources)}
    if token != expected:
        raise CollaborationConflict('Los datos de acceso o el cliente cambiaron. Actualiza antes de compartir.')
    policy, _ = ProjectClientAccessPolicy.objects.select_for_update().get_or_create(project=project)
    check_version(policy, values['expected_version'])
    available = _availability(sources)
    bindings, fields = {}, []
    for environment in ENVIRONMENTS:
        for field in ACCESS_FIELDS:
            if values['permissions'][environment][field]:
                if not available[environment][field]:
                    raise ValidationError({'permissions': f'El dato {environment}.{field} no está disponible para compartir.'})
                bindings[f'{environment}.{field}'] = _binding(project, environment, field, sources[environment][field])
                fields.append(f'{environment}.{field}')
    previous = policy.permissions or empty_matrix()
    changed = [f'{environment}.{field}' for environment in ENVIRONMENTS for field in ACCESS_FIELDS
               if previous.get(environment, {}).get(field, False) != values['permissions'][environment][field]]
    policy.permissions = values['permissions']
    policy.bindings = bindings
    policy.recipient_id = project.client_id
    policy.updated_by = actor
    policy.version += 1
    policy.save()
    _event(project, actor, 'policy_updated', sorted(set(changed + fields)), policy.version)
    return _admin_payload(project, policy, sources)


@transaction.atomic
def revoke_grants(project, *, actor=None, fields=None):
    """Explicit revocation; fingerprints additionally cover bypassing bulk writers."""
    policy = ProjectClientAccessPolicy.objects.select_for_update().filter(project_id=project.pk).first()
    if policy is None:
        return
    targets = fields if fields is not None else [f'{environment}.{field}' for environment in ENVIRONMENTS for field in ACCESS_FIELDS]
    removed = []
    permissions = {environment: dict(policy.permissions.get(environment, {})) for environment in ENVIRONMENTS}
    for target in targets:
        environment, field = target.split('.')
        if permissions[environment].get(field):
            removed.append(target)
        permissions[environment][field] = False
        policy.bindings.pop(target, None)
    if not removed and (fields is not None or policy.recipient_id is None):
        return
    policy.permissions = permissions
    if fields is None:
        policy.recipient_id = None
    policy.updated_by = actor
    policy.version += 1
    policy.save()
    _event(project, actor, 'grants_revoked', removed, policy.version)


def _client_projection(project):
    sources = _sources(project)
    effective = _effective(project, _policy(project), sources)
    environments = []
    for environment in ENVIRONMENTS:
        fields = effective[environment]
        item = {'environment': environment}
        for field in ('site_url', 'admin_url'):
            if fields[field]:
                item[field] = sources[environment][field]
        actions = [field for field in ('admin_username', 'admin_password') if fields[field]]
        if actions:
            item['credential_actions'] = actions
        if len(item) > 1:
            environments.append(item)
    return {'project_id': project.pk, 'environments': environments}


def can_view_client_access(project):
    policy = _policy(project)
    if not policy or policy.recipient_id != project.client_id or not policy.bindings:
        return False
    return any(any(fields.values()) for fields in _effective(project, policy, _sources(project)).values())


def client_access(project_id, actor):
    project = project_for_actor(project_id, actor)
    if project.client_id != actor.pk:
        raise PermissionDenied('Esta vista requiere la cuenta del cliente propietario.')
    return _client_projection(project)


def preview_access(project_id, actor, *, channel='platform'):
    return _client_projection(project_for_actor(project_id, actor, channel=channel, admin=True))


@transaction.atomic
def reveal_credential(project_id, actor, environment, field, data):
    project = project_for_actor(project_id, actor, lock=True)
    if project.client_id != actor.pk:
        raise PermissionDenied('Se requiere la cuenta del cliente propietario.')
    validated(EmptyAccessSerializer, data)
    if environment not in ENVIRONMENTS or field not in ('admin_username', 'admin_password'):
        raise NotFound('Dato de acceso no encontrado.')
    sources = _sources(project)
    policy = _policy(project)
    if not _effective(project, policy, sources)[environment][field]:
        raise PermissionDenied('Este dato de acceso no está habilitado.')
    value = sources[environment][field]
    secret = decrypt_secret(value) if field == 'admin_password' else value
    _event(project, actor, 'credential_revealed', [f'{environment}.{field}'], policy.version)
    return {'secret': secret}


def list_events(project_id, actor, *, channel='platform', page=1):
    project = project_for_actor(project_id, actor, channel=channel, admin=True)
    return paginate(project.client_access_events.all(), page, lambda event: {
        'id': event.pk, 'action': event.action, 'fields': event.fields,
        'policy_version': event.policy_version, 'actor_id': event.actor_id, 'created_at': event.created_at})
