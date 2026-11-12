"""Durable observations and append-only human reviews of integrity findings."""
from django.conf import settings
from django.db import models

from .data_integrity import DataIntegrityOperationQuerySet


class DataIntegrityScan(models.Model):
    request_id = models.CharField(max_length=100, unique=True)
    scope = models.JSONField(default=dict)
    filters = models.JSONField(default=dict)
    source = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    catalog_version = models.CharField(max_length=20)
    status = models.CharField(max_length=12, default='queued')
    error_code = models.CharField(max_length=40, blank=True)
    results = models.JSONField(default=list)
    coverage = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-id']


class DataIntegrityFinding(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    rule_id = models.CharField(max_length=8)
    domain = models.CharField(max_length=24)
    severity = models.CharField(max_length=8)
    payload = models.JSONField(default=dict)
    is_present = models.BooleanField(default=True, db_index=True)
    is_accepted = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True)
    last_scan = models.ForeignKey(DataIntegrityScan, on_delete=models.PROTECT, related_name='+')

    class Meta:
        ordering = ['-last_seen_at', '-id']


class DataIntegrityReview(models.Model):
    finding = models.ForeignKey(DataIntegrityFinding, on_delete=models.PROTECT, related_name='reviews')
    action = models.CharField(max_length=8)
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    source = models.CharField(max_length=64)
    request_id = models.CharField(max_length=100, unique=True)
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DataIntegrityOperationQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError('Data integrity reviews are append-only.')
        return super().save(*args, **kwargs)


class DataIntegrityScanLease(models.Model):
    """Singleton row serializes publication and fences workers after recovery."""
    key = models.CharField(max_length=16, primary_key=True, default='scan')
    scan = models.ForeignKey(DataIntegrityScan, on_delete=models.PROTECT, null=True, related_name='+')
    expires_at = models.DateTimeField(null=True)
