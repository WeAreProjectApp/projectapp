"""Availability settings are separate from authorization and technical readiness."""
from django.conf import settings
from django.db import models


class PlatformFeatureSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    values = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class ClientPlatformFeatureSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='platform_feature_settings')
    values = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class PlatformFeatureEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name='+')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name='+')
    scope = models.CharField(max_length=10)
    changes = models.JSONField(default=dict)
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

