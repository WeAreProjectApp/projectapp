"""Internal filing hierarchy. Location never determines a link's audience."""
from accounts.retention import RetainedProjectModel
from django.conf import settings
from django.db import models
from django.db.models import Q, F


class SecureLinkFolder(RetainedProjectModel, models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    order = models.PositiveIntegerField(default=0)
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='secure_link_folders')
    client = models.ForeignKey('accounts.UserProfile', null=True, blank=True, on_delete=models.SET_NULL, related_name='secure_link_folders')
    managed_project = models.OneToOneField('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='secure_link_root_folder')
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_via_folder = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='cascade_archived_folders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(managed_project__isnull=True) | Q(parent__isnull=True), name='secure_root_has_no_parent'),
            models.CheckConstraint(condition=Q(managed_project__isnull=True) | Q(project=F('managed_project')), name='secure_root_matches_project'),
            models.CheckConstraint(condition=Q(managed_project__isnull=True) | Q(is_archived=False), name='secure_root_is_active'),
        ]

    def __str__(self):
        return self.name


class SecureLinkFolderLock(models.Model):
    """Serializes root writes, recursive moves, filing and archive cascades."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
