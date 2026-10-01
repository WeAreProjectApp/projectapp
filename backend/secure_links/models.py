"""One-time links for sharing sensitive information.

The content is kept encrypted on ProjectApp's side; a link is only a
capability to reveal it once. Status is derived from timestamps so expiry
needs no scheduled job, and reactivation simply clears the consumption.
"""

import hashlib

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SecureLinkQuerySet(models.QuerySet):
    @staticmethod
    def status_conditions(now=None):
        now = now or timezone.now()
        available = Q(revoked_at__isnull=True, consumed_at__isnull=True)
        return {
            'revoked': Q(revoked_at__isnull=False),
            'consumed': Q(revoked_at__isnull=True, consumed_at__isnull=False),
            'expired': available & Q(expires_at__lte=now),
            'active': available & Q(expires_at__gt=now),
        }

    @classmethod
    def lifecycle_conditions(cls, now=None):
        conditions = cls.status_conditions(now)
        return {
            'ready': conditions['active'] & Q(sent_at__isnull=True),
            'sent': conditions['active'] & Q(sent_at__isnull=False),
            'opened': conditions['consumed'],
            'expired': conditions['expired'],
            'revoked': conditions['revoked'],
        }

    def with_lifecycle_status(self, status, now=None):
        return self.filter(self.lifecycle_conditions(now)[status])

    def with_status(self, status, now=None):
        return self.filter(self.status_conditions(now)[status])


class SecureLink(models.Model):
    class Origin(models.TextChoices):
        PANEL = 'panel', 'Equipo (panel)'
        MCP = 'mcp', 'Asistente (MCP)'
        PUBLIC = 'public', 'Cliente (página pública)'
        PLATFORM = 'platform', 'Cliente (Platform)'

    class Audience(models.TextChoices):
        TEAM = 'team', 'Equipo de ProjectApp'
        BEARER = 'bearer', 'Destinatario del enlace'

    class Language(models.TextChoices):
        ES = 'es', 'Español'
        EN = 'en', 'English'

    STATUSES = ('active', 'consumed', 'expired', 'revoked')
    LIFECYCLE_STATUSES = ('ready', 'sent', 'opened', 'expired', 'revoked')

    token_hash = models.CharField(max_length=64, unique=True)
    token_encrypted = models.TextField()
    secret_type = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    payload_encrypted = models.TextField()
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ES)
    origin = models.CharField(max_length=10, choices=Origin.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='secure_links_created',
    )
    creator_name = models.CharField(max_length=120, blank=True)
    creator_email = models.EmailField(blank=True)
    creator_ip = models.GenericIPAddressField(null=True, blank=True)
    client = models.ForeignKey(
        'accounts.UserProfile', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='secure_links',
    )
    project = models.ForeignKey(
        'accounts.Project', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='secure_links',
    )
    owner = models.ForeignKey(
        'accounts.UserProfile', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_secure_links',
    )
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.TEAM)
    replaces = models.OneToOneField(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replaced_by',
    )
    creation_request_id = models.UUIDField(null=True, blank=True)
    creation_request_fingerprint = models.CharField(max_length=64, blank=True)
    validity_days = models.PositiveSmallIntegerField(default=7)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_ip = models.GenericIPAddressField(null=True, blank=True)
    consumed_user_agent = models.CharField(max_length=300, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='secure_links_marked_sent',
    )
    activation_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SecureLinkQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['origin', 'consumed_at'], name='secure_link_origin_consumed'),
            models.Index(fields=['expires_at'], name='secure_link_expires'),
            models.Index(fields=['owner', 'project', 'created_at'], name='secure_link_owner_project'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'creation_request_id'], name='secure_link_owner_request'),
        ]

    def __str__(self):
        return self.title

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @property
    def status(self):
        if self.revoked_at:
            return 'revoked'
        if self.consumed_at:
            return 'consumed'
        if self.expires_at <= timezone.now():
            return 'expired'
        return 'active'

    @property
    def lifecycle_status(self):
        status = self.status
        if status == 'active':
            return 'sent' if self.sent_at else 'ready'
        return 'opened' if status == 'consumed' else status

    @property
    def team_only(self):
        """Links created by clients are addressed to the team only."""
        return self.audience == self.Audience.TEAM or self.origin in (self.Origin.PUBLIC, self.Origin.PLATFORM)


class SecureLinkEvent(models.Model):
    class Kind(models.TextChoices):
        CREATED = 'created', 'Creado'
        REVEALED = 'revealed', 'Abierto por el destinatario'
        REVEAL_BLOCKED = 'reveal_blocked', 'Intento de apertura rechazado'
        REACTIVATED = 'reactivated', 'Reactivado'
        ROTATED = 'rotated', 'Enlace regenerado'
        REVOKED = 'revoked', 'Revocado'
        UPDATED = 'updated', 'Editado'
        MARKED_SENT = 'marked_sent', 'Marcado como enviado por el equipo'
        PANEL_VIEWED = 'panel_viewed', 'Contenido visto en el panel'
        MCP_VIEWED = 'mcp_viewed', 'Contenido consultado desde MCP'
        REPLACED = 'replaced', 'Sustituido por otro enlace'
        URL_ACCESSED = 'url_accessed', 'URL consultada explícitamente'

    link = models.ForeignKey(SecureLink, on_delete=models.CASCADE, related_name='events')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
