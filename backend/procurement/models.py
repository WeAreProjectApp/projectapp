"""Independent procurement records; public source data never owns team decisions."""
from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone


class Settings(models.Model):
    sync_enabled = models.BooleanField(default=False)
    email_enabled = models.BooleanField(default=False)
    sync_time = models.TimeField(default=time(2))
    daily_time = models.TimeField(default=time(7))
    weekly_time = models.TimeField(default=time(7))
    weekly_day = models.PositiveSmallIntegerField(default=0)
    lookback_days = models.PositiveIntegerField(default=90)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Opportunity(models.Model):
    source_id = models.CharField(max_length=100, unique=True)
    reference = models.CharField(max_length=250, blank=True)
    title = models.CharField(max_length=1000, blank=True)
    description = models.TextField(blank=True)
    entity_name = models.CharField(max_length=500)
    entity_nit = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=120, blank=True, db_index=True)
    city = models.CharField(max_length=150, blank=True)
    method = models.CharField(max_length=250, blank=True, db_index=True)
    contract_type = models.CharField(max_length=150, blank=True)
    source_status = models.CharField(max_length=100, blank=True, db_index=True)
    budget = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True)
    unspsc_code = models.CharField(max_length=100, blank=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    closing_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source_url = models.URLField(max_length=1000, blank=True)
    source_data = models.JSONField(default=dict)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-pk']

    @property
    def is_open(self):
        return self.source_status in ('Abierto', 'Publicado') and (
            self.closing_at is None or self.closing_at > timezone.now()
        )

    @property
    def days_remaining(self):
        if self.closing_at is None:
            return None
        return max(0, (self.closing_at - timezone.now()).days)


class Classification(models.Model):
    STATES = [('interesting', 'Interesante'), ('reviewing', 'En revisión'),
              ('applied', 'Aplicado'), ('discarded', 'Descartado')]
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name='classifications')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=STATES, default='interesting')
    previous_state = models.CharField(max_length=20, default='interesting')
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['opportunity', 'owner'], name='procurement_class_owner')]


class Activity(models.Model):
    classification = models.ForeignKey(Classification, on_delete=models.PROTECT, related_name='activities')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    credential = models.ForeignKey('content.McpCredential', null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']


class SavedSearch(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    filters = models.JSONField(default=dict)
    is_favorite = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'name'], name='procurement_search_owner_name')]
        ordering = ['name', 'pk']


class Alert(models.Model):
    FREQUENCIES = [('immediate', 'Inmediata'), ('daily', 'Diaria'), ('weekly', 'Semanal')]
    name = models.CharField(max_length=150)
    filters = models.JSONField(default=dict)
    recipients = models.JSONField(default=list)
    frequency = models.CharField(max_length=20, choices=FREQUENCIES, default='daily')
    is_active = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'pk']


class SyncRun(models.Model):
    cursor = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='queued')
    processed = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']


class Delivery(models.Model):
    opportunity_count = models.PositiveSmallIntegerField(default=0)
    recipient = models.EmailField()
    frequency = models.CharField(max_length=20, choices=Alert.FREQUENCIES)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    attempted_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-pk']


class Notification(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.PROTECT, related_name='notifications')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT)
    recipient = models.EmailField()
    delivery = models.ForeignKey(Delivery, null=True, on_delete=models.PROTECT, related_name='notifications')
    filters_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['alert', 'opportunity', 'recipient'], name='procurement_notification_key')]


class ScheduleSlot(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    kind = models.CharField(max_length=20)
    day = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind', 'day'], name='procurement_schedule_slot')]
