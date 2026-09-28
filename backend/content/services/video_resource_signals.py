"""Delete unreferenced bytes only after the owning resource deletion commits."""
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from content.models import VideoResource
from content.services.video_resource_service import _delete_files


@receiver(post_delete, sender=VideoResource)
def delete_video_resource_files(sender, instance, **kwargs):
    names = [instance.file.name, instance.poster.name]
    transaction.on_commit(lambda: _delete_files(names))
