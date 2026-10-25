"""Private client conversations; provider configuration and quotas live in models_ai."""
import uuid

from django.conf import settings
from django.db import models


class AppiConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.CASCADE)
    language = models.CharField(max_length=2, default='es')
    title = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['actor', 'created_at'], name='appi_conv_actor_created')]


class AppiTurn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AppiConversation, on_delete=models.CASCADE, related_name='turns')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request_id = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    question = models.TextField()
    language = models.CharField(max_length=2, default='es')
    status = models.CharField(max_length=12, default='pending')
    query = models.JSONField(default=dict)
    answer = models.JSONField(default=dict)
    dependencies = models.CharField(max_length=64, blank=True, default='')
    context_key = models.CharField(max_length=64, blank=True, default='', db_index=True)
    exact_key = models.CharField(max_length=64, blank=True, default='', db_index=True)
    quota_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [models.UniqueConstraint(fields=['actor', 'request_id'], name='uniq_appi_actor_request')]
        indexes = [models.Index(fields=['actor', 'exact_key', 'status'], name='appi_turn_exact_lookup')]
