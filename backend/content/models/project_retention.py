"""Durable client ownership without keeping an operational project alive."""
from django.conf import settings
from django.db import models


class ProjectRetentionContext(models.Model):
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    original_project_id = models.PositiveBigIntegerField(unique=True)
    project_name = models.CharField(max_length=200)
    retained_records = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.project_name
