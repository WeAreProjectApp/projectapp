"""Independent filing hierarchy for complete client conversations."""

from accounts.retention import RetainedProjectModel
from django.core.exceptions import ValidationError
from django.db import models


class CommunicationFolder(RetainedProjectModel, models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='children',
    )
    client = models.ForeignKey(
        'accounts.UserProfile', on_delete=models.PROTECT,
        related_name='communication_folders',
    )
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='communication_folders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name

    def clean(self):
        if not self.name.strip():
            raise ValidationError({'name': 'El nombre es obligatorio.'})
        if self.client_id and self.client.role != self.client.ROLE_CLIENT:
            raise ValidationError({'client': 'Selecciona un cliente.'})
        if self.project_id and self.project.client_id != self.client.user_id:
            raise ValidationError({'project': 'El proyecto no pertenece al cliente.'})
        if not self.parent_id:
            return
        if (self.parent.client_id, self.parent.project_id) != (self.client_id, self.project_id):
            raise ValidationError({'parent': 'La carpeta debe pertenecer al mismo contexto.'})
        from content.services.folder_tree import descendant_ids
        scope = CommunicationFolder.objects.filter(client_id=self.client_id).values_list('id', 'parent_id')
        if self.pk and self.parent_id in ({self.pk} | descendant_ids(scope, self.pk)):
            raise ValidationError({'parent': 'Una carpeta no puede contenerse a sí misma.'})
