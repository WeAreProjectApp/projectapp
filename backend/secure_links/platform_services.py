"""Platform administration reuses the secure-link cipher and lifecycle services.

No decrypted content is read here. Request fingerprints are keyed MACs of the
normalized input, never plaintext or an unkeyed digest of a password.
"""

import json
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.crypto import constant_time_compare, salted_hmac

from . import services
from .catalog import clean_fields
from .models import SecureLink, SecureLinkEvent
from .platform_access import owned_link, owned_project

FINGERPRINT_SALT = 'secure_links.platform.creation.v1'


def _fingerprint(data, *, key=None):
    encoded = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return salted_hmac(FINGERPRINT_SALT, encoded, secret=key, algorithm='sha256').hexdigest()


def _same_request(link, normalized):
    keys = [settings.SECRET_KEY, *getattr(settings, 'SECRET_KEY_FALLBACKS', [])]
    return any(constant_time_compare(link.creation_request_fingerprint, _fingerprint(normalized, key=key)) for key in keys)


def _replay(link, normalized, owner, project):
    if not _same_request(link, normalized):
        raise services.SecureLinkError(
            'Este identificador ya se usó con otros datos. Inicia una nueva creación.',
            code='request_id_conflict', status=409,
        )
    # A replay must still pass today's object ownership, never reveal its URL.
    return owned_link(owner, project, link.pk), None, True


@transaction.atomic
def create_owned_link(*, owner_id, project_id, request_id, title, secret_type, fields,
                      actor, language='es', validity_days=7, replaces=None, meta=None):
    owner, project = owned_project(owner_id, project_id, lock=True)
    try:
        request_id = uuid.UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise services.SecureLinkError('El identificador de solicitud no es válido.', code='invalid_request_id') from exc
    days = services._validity(validity_days, allowed=services.PUBLIC_VALIDITY_CHOICES)
    title = services._title(title)
    fields = clean_fields(secret_type, fields)
    if language not in SecureLink.Language.values:
        raise services.SecureLinkError('El idioma no es válido.', code='invalid_language')
    normalized = {
        'owner_id': owner.pk, 'project_id': project.pk, 'title': title,
        'secret_type': secret_type, 'fields': fields, 'language': language,
        'validity_days': days, 'replaces': replaces,
    }
    existing = SecureLink.objects.filter(owner=owner, creation_request_id=request_id).first()
    if existing:
        return _replay(existing, normalized, owner, project)
    previous = None
    if replaces is not None:
        previous = owned_link(owner, project, replaces, lock=True)
        if previous.revoked_at is None or SecureLink.objects.filter(replaces=previous).exists():
            raise services.SecureLinkError(
                'Revoca el enlace anterior antes de sustituirlo. Sólo admite una sustitución.',
                code='invalid_replacement', status=409,
            )
    try:
        # Savepoint allows a competing unique request to be looked up safely.
        with transaction.atomic():
            link, url = services.create_link(
                secret_type=secret_type, title=title, fields=fields,
                origin=SecureLink.Origin.PLATFORM, audience=SecureLink.Audience.TEAM,
                owner=owner, client=owner, project=project, actor=actor,
                language=language, validity_days=days, meta=meta,
                creator_name=owner.user.get_full_name() or owner.company_name or 'Cliente',
                creation_request_id=request_id, creation_request_fingerprint=_fingerprint(normalized),
                replaces=previous,
            )
            if previous:
                services.log_event(previous, SecureLinkEvent.Kind.REPLACED, actor=actor, meta=meta, replacement_id=link.pk)
    except IntegrityError:
        existing = SecureLink.objects.filter(owner=owner, creation_request_id=request_id).first()
        if existing:
            return _replay(existing, normalized, owner, project)
        raise services.SecureLinkError('El enlace ya tiene una sustitución.', code='invalid_replacement', status=409) from None
    return link, url, False


def _revision(link, expected_updated_at):
    if expected_updated_at != link.updated_at:
        raise services.SecureLinkError(
            'El enlace cambió. Actualiza los datos antes de continuar.', code='version_conflict', status=409,
        )


@transaction.atomic
def update_owned_title(*, owner_id, project_id, link_id, title, expected_updated_at, actor, meta=None):
    owner, project = owned_project(owner_id, project_id, lock=True)
    link = owned_link(owner, project, link_id, lock=True)
    _revision(link, expected_updated_at)
    return services.update_link(link, actor=actor, title=title, meta=meta)


@transaction.atomic
def revoke_owned_link(*, owner_id, project_id, link_id, actor, meta=None):
    owner, project = owned_project(owner_id, project_id, lock=True)
    return services.revoke(owned_link(owner, project, link_id, lock=True), actor=actor, meta=meta)


@transaction.atomic
def reactivate_owned_link(*, owner_id, project_id, link_id, validity_days, expected_updated_at, actor, meta=None):
    owner, project = owned_project(owner_id, project_id, lock=True)
    link = owned_link(owner, project, link_id, lock=True)
    _revision(link, expected_updated_at)
    return services.reactivate(link, actor=actor, validity_days=validity_days, rotate=True, meta=meta)


@transaction.atomic
def owned_link_url(*, owner_id, project_id, link_id, actor, meta=None):
    owner, project = owned_project(owner_id, project_id, lock=True)
    link = owned_link(owner, project, link_id, lock=True)
    return services.audited_link_url(link, actor=actor, meta=meta, channel='platform')
