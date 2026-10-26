from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Project
from .folder_services import ensure_project_root


@receiver(post_save, sender=Project)
def synchronize_secure_link_root(sender, instance, raw=False, **kwargs):
    if not raw:
        ensure_project_root(instance)
