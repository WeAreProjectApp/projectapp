"""Ownership of read-only records retained after an explicit project deletion."""
from django.db import models
from rest_framework.exceptions import PermissionDenied


class RetainedProjectModel(models.Model):
    retention_context = models.ForeignKey(
        'content.ProjectRetentionContext', on_delete=models.PROTECT,
        null=True, blank=True, related_name='%(app_label)s_%(class)s_records',
    )

    class Meta:
        abstract = True

    @property
    def project_label(self):
        project = getattr(self, 'project', None)
        if project is not None:
            return project.name
        return self.retention_context.project_name if self.retention_context_id else 'Sin proyecto'

    def save(self, *args, **kwargs):
        if self.retention_context_id and not self._state.adding:
            raise PermissionDenied('Los datos conservados sin proyecto sólo permiten consulta.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.retention_context_id:
            raise PermissionDenied('Los datos conservados sin proyecto sólo permiten consulta.')
        return super().delete(*args, **kwargs)
