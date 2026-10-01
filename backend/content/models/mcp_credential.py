import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class McpCredential(models.Model):
    """A revocable, scoped credential for one MCP connector."""

    connector = models.ForeignKey(
        'content.McpConnector',
        on_delete=models.CASCADE,
        related_name='credentials',
    )
    label = models.CharField(max_length=100, default='Default')
    token_hash = models.CharField(max_length=64, db_index=True)
    token_prefix = models.CharField(max_length=8, blank=True, default='')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mcp_credentials',
    )
    allowed_tools = models.JSONField(
        default=list,
        blank=True,
        help_text='Empty means every tool exposed by the connector.',
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['connector_id', 'created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['connector', 'label'],
                name='uniq_mcp_credential_label',
            ),
        ]

    def __str__(self):
        return f'{self.connector.slug}:{self.label}'

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @property
    def is_usable(self):
        return (
            self.revoked_at is None
            and (self.expires_at is None or self.expires_at > timezone.now())
        )

    def generate_token(self):
        token = secrets.token_urlsafe(36)
        self.token_hash = self.hash_token(token)
        self.token_prefix = token[:8]
        self.revoked_at = None
        self.save()
        return token

    def check_token(self, token):
        if not token or not self.token_hash or not self.is_usable:
            return False
        return hmac.compare_digest(self.token_hash, self.hash_token(token))

    def allows(self, tool_name):
        # General connector access must never silently acquire secret reads.
        if tool_name in {'reveal_secure_link_content', 'get_secure_link_url'}:
            return tool_name in self.allowed_tools
        control_tools = {'describe_capabilities', 'confirm_action', 'cancel_action'}
        return (
            not self.allowed_tools
            or tool_name in self.allowed_tools
            or tool_name in control_tools
        )
