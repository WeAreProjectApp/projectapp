"""Shared Platform AI configuration; provider secrets never appear in projections."""
import uuid

from django.conf import settings
from django.db import models


TEXT_MODELS = ('claude-haiku-5-5', 'gpt-6-luna')
PROVIDERS = ('anthropic', 'openai', 'jev')


class PlatformAISettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    chatbot_enabled = models.BooleanField(default=False)
    voice_reporting_enabled = models.BooleanField(default=False)
    chatbot_model = models.CharField(max_length=40, default=TEXT_MODELS[0])
    voice_report_model = models.CharField(max_length=40, default=TEXT_MODELS[0])
    monthly_audio_limit = models.PositiveIntegerField(default=1000)
    daily_user_audio_limit = models.PositiveIntegerField(default=20)
    ai_request_limit = models.PositiveIntegerField(default=20)
    ai_window_minutes = models.PositiveIntegerField(default=300)
    max_output_tokens = models.PositiveIntegerField(default=1000)
    report_cache_enabled = models.BooleanField(default=True)
    chatbot_cache_enabled = models.BooleanField(default=True)
    report_cache_hours = models.PositiveSmallIntegerField(default=24)
    chatbot_cache_hours = models.PositiveSmallIntegerField(default=24)
    cache_epoch = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class PlatformAICredential(models.Model):
    provider = models.CharField(max_length=20, unique=True)
    encrypted_value = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField(default=1)
    last_test_status = models.CharField(max_length=20, blank=True, default='')
    tested_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class PlatformAITemplate(models.Model):
    family = models.CharField(max_length=20)
    scenario = models.CharField(max_length=40)
    language = models.CharField(max_length=2)
    content = models.TextField()
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['family', 'scenario', 'language'], name='uniq_platform_ai_template')]


class PlatformAITemplateRevision(models.Model):
    template = models.ForeignKey(PlatformAITemplate, on_delete=models.CASCADE, related_name='revisions')
    version = models.PositiveIntegerField()
    content = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['template', 'version'], name='uniq_platform_ai_template_revision')]
        ordering = ['-version']


class PlatformAIJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey('accounts.Project', null=True, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=20)
    operation = models.CharField(max_length=20, default='transcription')
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default='pending')
    audio_name = models.CharField(max_length=250, blank=True, default='')
    audio_seconds = models.FloatField(default=0)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error_code = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'request_id'], name='uniq_platform_ai_job_request')]
        indexes = [models.Index(fields=['actor', 'status']), models.Index(fields=['expires_at']), models.Index(fields=['fingerprint', 'status'])]


class PlatformAIUsage(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    project = models.ForeignKey('accounts.Project', null=True, on_delete=models.SET_NULL)
    purpose = models.CharField(max_length=20)
    operation = models.CharField(max_length=20)
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=40)
    audio_seconds = models.FloatField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_read_tokens = models.PositiveIntegerField(default=0)
    cache_write_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=8, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class PlatformAIEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class PlatformAIQuotaReservation(models.Model):
    """One logical client request, shared by voice reporting and chatbot."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request_id = models.UUIDField()
    purpose = models.CharField(max_length=20)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default='reserved')
    redemption_request_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'request_id'], name='uniq_platform_ai_quota_request'),
                       models.UniqueConstraint(fields=['actor', 'redemption_request_id'], name='uniq_platform_ai_audio_redemption')]
        indexes = [models.Index(fields=['actor', 'created_at', 'status'])]
