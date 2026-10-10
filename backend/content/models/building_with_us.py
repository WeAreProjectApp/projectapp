"""Append-only alliance revisions and the current presentation pointer."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class BuildingWithUsRevision(models.Model):
    """Shared provenance for presentation and future alliance contract revisions."""

    version = models.PositiveIntegerField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    credential = models.ForeignKey('content.McpCredential', null=True, on_delete=models.SET_NULL, related_name='+')
    author_label = models.CharField(max_length=255, default='Sistema')
    change_note = models.TextField()
    restored_from = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-version']
        constraints = [models.UniqueConstraint(fields=['version'], name='%(app_label)s_%(class)s_unique_version')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Las versiones de Building with Us son inmutables.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Las versiones de Building with Us no se eliminan.')


class BuildingWithUsProgramRevision(BuildingWithUsRevision):
    content = models.JSONField()


class BuildingWithUsProgram(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_revision = models.ForeignKey(BuildingWithUsProgramRevision, on_delete=models.PROTECT, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='building_with_us_program_singleton')]

    @classmethod
    def load(cls, lock=False):
        queryset = cls.objects.select_for_update() if lock else cls.objects
        return queryset.select_related('current_revision').get(pk=1)
