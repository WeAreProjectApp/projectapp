import hashlib
import hmac
import secrets

from django.db import models


class McpConnector(models.Model):
    """
    A remote MCP connector exposed by this backend (e.g. the Blog Publisher).

    The token embedded in the connector URL is the credential (capability
    URL, webhook-secret style). Only its SHA-256 hash is stored; the
    plaintext is shown once at generation time in /panel/mcps.
    """

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    token_hash = models.CharField(
        max_length=64, blank=True, default='',
        help_text='SHA-256 hex digest of the connector token. Plaintext is never stored.',
    )
    token_prefix = models.CharField(
        max_length=8, blank=True, default='',
        help_text='First 8 chars of the token, for masked display in the panel.',
    )
    is_active = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    migration_started_at = models.DateTimeField(null=True, blank=True)
    consumers_verified_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    aliases_retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'MCP Connector'
        verbose_name_plural = 'MCP Connectors'

    def __str__(self):
        return self.name

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def generate_token(self):
        """Rotate the compatibility token and its default scoped credential."""
        token = secrets.token_urlsafe(36)
        self.token_hash = self.hash_token(token)
        self.token_prefix = token[:8]
        self.save(update_fields=['token_hash', 'token_prefix', 'updated_at'])
        # Local import avoids a model-import cycle. Existing installations keep
        # the connector fields as an expand/contract compatibility surface.
        from content.models.mcp_credential import McpCredential

        credential, _ = McpCredential.objects.get_or_create(
            connector=self,
            label='Default',
            defaults={
                'token_hash': self.token_hash,
                'token_prefix': self.token_prefix,
                'catalog': 'legacy',
            },
        )
        credential.token_hash = self.token_hash
        credential.token_prefix = self.token_prefix
        credential.revoked_at = None
        credential.save(update_fields=[
            'token_hash', 'token_prefix', 'revoked_at', 'updated_at',
        ])
        return token

    def check_token(self, token):
        if not self.token_hash or not token:
            return False
        return hmac.compare_digest(self.token_hash, self.hash_token(token))

    def credential_for_token(self, token):
        """Return the usable scoped credential, falling back to legacy data."""
        if not token:
            return None
        token_hash = self.hash_token(token)
        credential = self.credentials.filter(token_hash=token_hash).first()
        if credential and credential.check_token(token):
            return credential
        return None
