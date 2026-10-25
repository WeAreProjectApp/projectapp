"""Platform help configuration and durable, account-scoped guided tours."""
from django.conf import settings
from django.db import models


class PlatformHelpSettings(models.Model):
    tour_enabled = models.BooleanField(default=True)
    video_enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=0)


class ClientPlatformHelpSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='platform_help_settings')
    tour_enabled = models.BooleanField(default=True)
    video_enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=0)


class PlatformGuidedTour(models.Model):
    slug = models.SlugField(unique=True, max_length=80)
    context = models.CharField(max_length=20, choices=[(x, x) for x in ('general', 'project', 'voice')])
    kind = models.CharField(max_length=20, choices=[(x, x) for x in ('onboarding', 'novelty')], default='novelty')
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    draft = models.JSONField(default=dict)
    published_revision = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class PlatformGuidedTourRevision(models.Model):
    tour = models.ForeignKey(PlatformGuidedTour, on_delete=models.CASCADE, related_name='revisions')
    number = models.PositiveIntegerField()
    content = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tour', 'number'], name='unique_platform_tour_revision')]


class PlatformTourProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tour = models.ForeignKey(PlatformGuidedTour, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ('in_progress', 'paused', 'completed', 'skipped')])
    revision = models.PositiveIntegerField()
    last_step = models.CharField(max_length=80, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'tour'], name='unique_platform_tour_user')]


class PlatformHelpEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    subject = models.CharField(max_length=100)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
