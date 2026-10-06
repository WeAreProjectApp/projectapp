"""Explicit grants and value-free audit for client project access."""

from accounts.retention import RetainedProjectModel
from django.conf import settings
from django.db import models


class ProjectClientAccessPolicy(RetainedProjectModel, models.Model):
    project = models.OneToOneField('accounts.Project', on_delete=models.PROTECT, related_name='client_access_policy', null=True, blank=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    version = models.PositiveIntegerField(default=0)
    permissions = models.JSONField(default=dict)
    bindings = models.JSONField(default=dict)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProjectClientAccessEvent(RetainedProjectModel, models.Model):
    project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='client_access_events', null=True, blank=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    action = models.CharField(max_length=30, choices=[('policy_updated', 'Visibilidad actualizada'), ('grants_revoked', 'Accesos revocados'), ('credential_revealed', 'Dato consultado')])
    fields = models.JSONField(default=list)
    policy_version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
