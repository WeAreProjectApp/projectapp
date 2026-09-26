"""Single write boundary for secure links (panel, public page and MCP).

Security contract:
- the URL token is random, travels in the URL fragment and is only stored as
  a SHA-256 lookup hash plus a Fernet copy that lets staff copy the link again;
- the payload is Fernet-encrypted JSON and is only decrypted by an explicit
  reveal (recipient) or an audited panel view (staff);
- a recipient reveal is atomic: the row is locked, the status re-checked and
  the consumption stored in the same transaction.
"""

import json
import secrets
from dataclasses import dataclass
from datetime import timedelta

from accounts.services.credential_cipher import decrypt_secret, encrypt_secret
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .catalog import clean_fields, labelled_fields, type_label
from .models import SecureLink, SecureLinkEvent

VALIDITY_CHOICES = (1, 3, 7, 30)
PUBLIC_VALIDITY_CHOICES = (1, 3, 7)
DEFAULT_VALIDITY_DAYS = 7
USER_AGENT_MAX = 300


class SecureLinkError(Exception):
    def __init__(self, message, *, code, status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


_UNAVAILABLE = {
    'consumed': ('Este enlace ya fue utilizado.', 'link_consumed'),
    'expired': ('Este enlace venció.', 'link_expired'),
    'revoked': ('Este enlace fue desactivado.', 'link_revoked'),
}


@dataclass
class RequestMeta:
    ip: str | None = None
    user_agent: str = ''

    @classmethod
    def from_request(cls, request):
        from content.utils import get_client_ip

        return cls(
            ip=get_client_ip(request) or None,
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:USER_AGENT_MAX],
        )


def _locale(language):
    return 'en-us' if language == SecureLink.Language.EN else 'es-co'


def _base_url():
    return getattr(settings, 'FRONTEND_BASE_URL', '').rstrip('/')


def build_url(language, token):
    return f'{_base_url()}/{_locale(language)}/secure-link/view#{token}'


def public_create_url(language='es'):
    return f'{_base_url()}/{_locale(language)}/secure-link'


def panel_url(link):
    return f'{_base_url()}/panel/secure-links?link={link.pk}'


def _decrypt_strict(ciphertext):
    plain = decrypt_secret(ciphertext)
    if ciphertext and not plain:
        # decrypt_secret hides key/ciphertext problems as ''. For a secret link
        # that would show an empty secret, so fail loudly instead.
        raise SecureLinkError(
            'No pudimos descifrar este contenido. Avísale al equipo de ProjectApp.',
            code='content_unavailable', status=500,
        )
    return plain


def _encrypt_payload(payload):
    return encrypt_secret(json.dumps(payload, ensure_ascii=False))


def _decrypt_payload(link):
    return json.loads(_decrypt_strict(link.payload_encrypted))


def _new_token():
    token = secrets.token_urlsafe(32)
    return token, SecureLink.hash_token(token), encrypt_secret(token)


def _validity(days, *, allowed=VALIDITY_CHOICES):
    if days in (None, ''):
        return DEFAULT_VALIDITY_DAYS
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = None
    if days not in allowed:
        choices = ', '.join(str(value) for value in allowed)
        raise SecureLinkError(
            f'La vigencia debe ser una de estas opciones (días): {choices}.',
            code='invalid_validity',
        )
    return days


def log_event(link, kind, *, actor=None, meta=None, **details):
    meta = meta or RequestMeta()
    return SecureLinkEvent.objects.create(
        link=link, kind=kind, actor=actor if getattr(actor, 'pk', None) else None,
        ip_address=meta.ip, user_agent=meta.user_agent, details=details,
    )


def link_url(link):
    return build_url(link.language, _decrypt_strict(link.token_encrypted))


def content_for(link, language=None):
    return {
        'secret_type': link.secret_type,
        'type_label': type_label(link.secret_type, language or link.language),
        'title': link.title,
        'fields': labelled_fields(link.secret_type, _decrypt_payload(link), language or link.language),
    }


@transaction.atomic
def create_link(*, secret_type, title, fields, origin, actor=None, client=None,
                project=None, language=SecureLink.Language.ES, validity_days=None,
                creator_name='', creator_email='', meta=None):
    allowed = PUBLIC_VALIDITY_CHOICES if origin == SecureLink.Origin.PUBLIC else VALIDITY_CHOICES
    days = _validity(validity_days, allowed=allowed)
    payload = clean_fields(secret_type, fields)
    if project is not None and client is not None and project.client_id != client.user_id:
        raise SecureLinkError('El proyecto no pertenece a ese cliente.', code='project_client_mismatch')
    if project is not None and client is None:
        client = getattr(project.client, 'profile', None)
    token, token_hash, token_encrypted = _new_token()
    link = SecureLink.objects.create(
        token_hash=token_hash,
        token_encrypted=token_encrypted,
        secret_type=secret_type,
        title=title.strip(),
        payload_encrypted=_encrypt_payload(payload),
        language=language,
        origin=origin,
        created_by=actor if getattr(actor, 'pk', None) else None,
        creator_name=creator_name.strip(),
        creator_email=creator_email.strip(),
        creator_ip=(meta.ip if meta and origin == SecureLink.Origin.PUBLIC else None),
        client=client,
        project=project,
        validity_days=days,
        expires_at=timezone.now() + timedelta(days=days),
    )
    log_event(link, SecureLinkEvent.Kind.CREATED, actor=actor, meta=meta, origin=origin, validity_days=days)
    return link, build_url(link.language, token)


def _link_for_token(token, *, lock=False):
    if not isinstance(token, str) or not 20 <= len(token) <= 128:
        return None
    queryset = SecureLink.objects.select_related('client__user', 'project')
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(token_hash=SecureLink.hash_token(token)).first()


def _not_found():
    return SecureLinkError('Este enlace no existe o fue eliminado.', code='link_not_found', status=404)


def sender_label(link):
    if link.origin == SecureLink.Origin.PUBLIC:
        return link.creator_name or 'Cliente'
    return 'ProjectApp'


def public_status(token, *, staff=False):
    link = _link_for_token(token)
    if link is None:
        raise _not_found()
    return {
        'status': link.status,
        'secret_type': link.secret_type,
        'type_label': type_label(link.secret_type, link.language),
        'sender': sender_label(link),
        'language': link.language,
        'expires_at': link.expires_at,
        'team_only': link.team_only,
        'can_reveal': link.status == 'active' and (staff or not link.team_only),
    }


def reveal(token, *, staff=False, actor=None, meta=None):
    """Consume an active link and return its content, or raise SecureLinkError."""
    blocked = None
    with transaction.atomic():
        link = _link_for_token(token, lock=True)
        if link is None:
            raise _not_found()
        status = link.status
        if link.team_only and not staff:
            blocked = ('staff_only', SecureLinkError(
                'Este enlace es para el equipo de ProjectApp. Inicia sesión en el panel para abrirlo.',
                code='staff_only', status=403,
            ))
        elif status != 'active':
            message, code = _UNAVAILABLE[status]
            blocked = (status, SecureLinkError(message, code=code, status=410))
        if blocked:
            # Recorded inside the transaction that reads the state, but the
            # error is raised afterwards so the audit row is committed.
            log_event(link, SecureLinkEvent.Kind.REVEAL_BLOCKED, actor=actor, meta=meta, reason=blocked[0])
        else:
            content = content_for(link)
            meta = meta or RequestMeta()
            link.consumed_at = timezone.now()
            link.consumed_ip = meta.ip
            link.consumed_user_agent = meta.user_agent
            link.save(update_fields=['consumed_at', 'consumed_ip', 'consumed_user_agent', 'updated_at'])
            log_event(link, SecureLinkEvent.Kind.REVEALED, actor=actor, meta=meta, staff=staff)
    if blocked:
        raise blocked[1]
    return link, content


def panel_content(link, *, actor, meta=None):
    content = content_for(link)
    log_event(link, SecureLinkEvent.Kind.PANEL_VIEWED, actor=actor, meta=meta)
    return content


@transaction.atomic
def reactivate(link, *, actor, validity_days=None, rotate=False, meta=None):
    link = SecureLink.objects.select_for_update().get(pk=link.pk)
    days = _validity(validity_days)
    url = None
    if rotate:
        token, link.token_hash, link.token_encrypted = _new_token()
        url = build_url(link.language, token)
    link.consumed_at = None
    link.consumed_ip = None
    link.consumed_user_agent = ''
    link.revoked_at = None
    link.validity_days = days
    link.expires_at = timezone.now() + timedelta(days=days)
    link.activation_count += 1
    link.save()
    log_event(link, SecureLinkEvent.Kind.REACTIVATED, actor=actor, meta=meta, validity_days=days, rotated=rotate)
    if rotate:
        log_event(link, SecureLinkEvent.Kind.ROTATED, actor=actor, meta=meta)
    return link, url or link_url(link)


@transaction.atomic
def revoke(link, *, actor, meta=None):
    link = SecureLink.objects.select_for_update().get(pk=link.pk)
    if link.revoked_at is None:
        link.revoked_at = timezone.now()
        link.save(update_fields=['revoked_at', 'updated_at'])
        log_event(link, SecureLinkEvent.Kind.REVOKED, actor=actor, meta=meta)
    return link


@transaction.atomic
def update_link(link, *, actor, meta=None, **changes):
    """Edit title, association and/or content. Never changes the link state."""
    link = SecureLink.objects.select_for_update().get(pk=link.pk)
    changed = []
    if 'title' in changes:
        link.title = changes['title'].strip()
        changed.append('title')
    if 'client' in changes or 'project' in changes:
        client = changes.get('client', link.client)
        project = changes.get('project', link.project)
        if project is not None and client is not None and project.client_id != client.user_id:
            raise SecureLinkError('El proyecto no pertenece a ese cliente.', code='project_client_mismatch')
        link.client, link.project = client, project
        changed += ['client', 'project']
    if 'fields' in changes:
        secret_type = changes.get('secret_type', link.secret_type)
        link.payload_encrypted = _encrypt_payload(clean_fields(secret_type, changes['fields']))
        link.secret_type = secret_type
        changed += ['secret_type', 'content']
    if changed:
        link.save()
        # Only field names are audited: values may be sensitive.
        log_event(link, SecureLinkEvent.Kind.UPDATED, actor=actor, meta=meta, fields=sorted(set(changed)))
    return link


def unopened_received_count():
    return SecureLink.objects.filter(
        origin=SecureLink.Origin.PUBLIC, consumed_at__isnull=True, revoked_at__isnull=True,
    ).count()
