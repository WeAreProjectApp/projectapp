"""Private project brand library, independent of public Linktree media."""
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from content.storage import get_private_storage


class ProjectBrandAsset(models.Model):
    class Category(models.TextChoices):
        BRANDING = 'branding', 'Branding'
        MANUAL = 'manual', 'Manual de marca'
        DESIGN_SYSTEM = 'design_system', 'Sistema de diseño'
        LOGO = 'logo', 'Logo'
        OTHER = 'other', 'Otro recurso'

    project = models.ForeignKey('accounts.Project', on_delete=models.CASCADE, related_name='brand_assets')
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices)
    file = models.FileField(storage=get_private_storage, upload_to='project-brand/%Y/%m/', max_length=500)
    filename = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


@receiver(post_delete, sender=ProjectBrandAsset)
def delete_brand_asset_file(sender, instance, **kwargs):
    from content.services.project_file_cleanup import project_cleanup_active
    if project_cleanup_active():
        return
    if instance.file:
        storage, name = instance.file.storage, instance.file.name
        transaction.on_commit(lambda: storage.delete(name))
