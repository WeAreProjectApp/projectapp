"""Operational observations are separate from administrator follow-up."""

from accounts.retention import RetainedProjectModel

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class Resource(RetainedProjectModel, models.Model):
    key = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=10, choices=[('server', 'Servidor'), ('project', 'Proyecto')])
    server = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    project = models.OneToOneField('accounts.Project', null=True, blank=True, on_delete=models.PROTECT)
    environment = models.CharField(max_length=20, default='production')
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']


class Source(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name='sources')
    key = models.SlugField(max_length=80)
    name = models.CharField(max_length=120)
    expected_interval = models.PositiveIntegerField(default=300)
    enabled = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_received_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource', 'key'], name='monitor_source_resource_key')]
        ordering = ['resource__name', 'name']

    @property
    def health(self):
        if not self.enabled:
            return 'disabled'
        if not self.last_seen_at:
            return 'no_data'
        if self.last_error or (timezone.now() - self.last_seen_at).total_seconds() > self.expected_interval * 2:
            return 'stale'
        return 'current'


class Credential(models.Model):
    label = models.CharField(max_length=120)
    token_hash = models.CharField(max_length=64, unique=True)
    resources = models.ManyToManyField(Resource)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def issue(cls, label):
        token = secrets.token_urlsafe(48)
        return cls.objects.create(label=label, token_hash=cls.hash_token(token)), token


class Case(models.Model):
    STATES = [('pending', 'Pendiente'), ('reviewing', 'En revisión'), ('resolved', 'Resuelto')]
    SEVERITIES = [('info', 'Informativo'), ('warning', 'Advertencia'), ('critical', 'Crítico')]
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='cases')
    fingerprint = models.CharField(max_length=200)
    fingerprint_hash = models.CharField(max_length=64)
    title = models.CharField(max_length=240)
    severity = models.CharField(max_length=10, choices=SEVERITIES)
    state = models.CharField(max_length=10, choices=STATES, default='pending')
    condition = models.CharField(max_length=12, default='active')
    resource_snapshot = models.JSONField(default=dict)
    evidence = models.JSONField(default=dict)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    detections = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'fingerprint_hash'], name='monitor_case_fingerprint')]
        indexes = [models.Index(fields=['state', '-last_seen_at']), models.Index(fields=['severity', '-last_seen_at']), models.Index(fields=['-last_seen_at', '-id'])]
        ordering = ['-last_seen_at', '-pk']


class Report(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='reports')
    title = models.CharField(max_length=240)
    observed_at = models.DateTimeField(db_index=True)
    text = models.TextField()
    resource_snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ['-observed_at', '-pk']


class Delivery(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    external_id = models.CharField(max_length=128)
    digest = models.CharField(max_length=64)
    kind = models.CharField(max_length=12)
    observed_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    case = models.ForeignKey(Case, null=True, on_delete=models.PROTECT, related_name='deliveries')
    report = models.ForeignKey(Report, null=True, on_delete=models.SET_NULL, related_name='deliveries')
    evidence = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'external_id'], name='monitor_delivery_identity')]
        indexes = [models.Index(fields=['case', '-observed_at']), models.Index(fields=['kind', 'received_at'])]
        ordering = ['-observed_at', '-pk']


class CaseActivity(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name='activities')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150, blank=True)
    kind = models.CharField(max_length=16)
    text = models.TextField(blank=True)
    from_state = models.CharField(max_length=10, blank=True)
    to_state = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['case', '-created_at'])]
        ordering = ['-created_at', '-pk']
