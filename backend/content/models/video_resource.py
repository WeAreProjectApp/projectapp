"""Managed commercial videos; bytes always live outside public MEDIA_ROOT."""
import uuid

from django.conf import settings
from django.core.files.storage import storages
from django.db import models


def video_storage():
    return storages['private']


def video_resource_path(instance, filename):
    return f'commercial-videos/{instance.pk}/{uuid.uuid4().hex}/{filename}'


class VideoResource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=80, unique=True)
    module = models.CharField(max_length=30)
    language = models.CharField(max_length=2, choices=[('es', 'Español'), ('en', 'English')])
    proposal = models.OneToOneField(
        'content.BusinessProposal', null=True, blank=True,
        on_delete=models.CASCADE, related_name='personalized_video_resource',
    )
    mode = models.CharField(max_length=12, default='default', choices=[
        ('default', 'Predeterminado'), ('uploaded', 'Cargado'), ('none', 'Sin video'),
    ])
    file = models.FileField(storage=video_storage, upload_to=video_resource_path, blank=True)
    poster = models.FileField(storage=video_storage, upload_to=video_resource_path, blank=True)
    filename = models.CharField(max_length=255, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    duration_seconds = models.FloatField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    revision = models.PositiveBigIntegerField(default=0)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
