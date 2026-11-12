"""Authentication state; secrets never belong in history or task arguments."""
import uuid

from django.conf import settings
from django.db import models


class LoginChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    surface = models.CharField(max_length=8)
    browser_digest = models.CharField(max_length=64)
    identity_digest = models.CharField(max_length=64)
    code_digest = models.CharField(max_length=64, blank=True)
    access_version = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    closed = models.BooleanField(default=False)
    device = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'closed'])]


class GoogleIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='google_identity')
    subject = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AccessEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    action = models.CharField(max_length=32)
    method = models.CharField(max_length=16, blank=True)
    surface = models.CharField(max_length=8, blank=True)
    ip = models.GenericIPAddressField(null=True)
    device = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['user', '-created_at'])]


class AccessRateBucket(models.Model):
    key = models.CharField(max_length=80, primary_key=True)
    requests = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)
