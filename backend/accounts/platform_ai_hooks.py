"""Private audio is removed if its job is cascaded by an authorized deletion."""
from django.core.files.storage import storages
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from accounts.models_ai import PlatformAIJob


@receiver(post_delete, sender=PlatformAIJob)
def remove_job_audio(sender, instance, **kwargs):
    if instance.audio_name:
        name = instance.audio_name
        transaction.on_commit(lambda: storages['private'].delete(name))
