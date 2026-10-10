from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ContractTemplate(models.Model):
    """Default combined, product and service texts, changed through one service.

    MCP confirms edits; the console uses the same transactional writer.
    Generated/signed proposal documents retain their stored snapshots.
    """

    name = models.CharField(max_length=255)
    content_markdown = models.TextField(
        help_text=(
            'Markdown text. Use {client_full_name}, {contractor_id_type}, '
            '{contractor_id_number}, etc. for placeholders. Prefer the '
            '{contractor_id_*} pair over {contractor_nit}: it resolves to the '
            'NIT when there is one and to the cédula otherwise, and carries '
            'the matching label.'
        ),
    )
    service_content_markdown = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Standalone hosting, maintenance and support contract used when the '
            'deal closes with two documents. Same placeholders as the main text '
            'plus {service_initial_term}, {service_renewal_notice_days} and '
            '{service_termination_notice_days}.'
        ),
    )
    product_content_markdown = models.TextField(blank=True, default='')
    is_default = models.BooleanField(default=False)
    mirror_document = models.OneToOneField(
        'content.Document',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contract_template',
        help_text=(
            'Documento del Gestor que muestra este contrato en vivo y en solo '
            'lectura (PDF y Markdown). No guarda una copia del texto.'
        ),
    )
    # Pin the mirror location by ID so folder renames and moves stay valid.
    mirror_folder = models.ForeignKey(
        'content.DocumentFolder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name = 'Contract template'
        verbose_name_plural = 'Contract templates'

    def __str__(self):
        default_label = ' (default)' if self.is_default else ''
        return f'{self.name}{default_label}'

    def save(self, *args, **kwargs):
        if self.is_default:
            ContractTemplate.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        """Return the default template, or None if not configured."""
        return cls.objects.filter(is_default=True).first()


class ContractTemplateVersion(models.Model):
    """Append-only text revision; restoring creates a new revision."""

    template = models.ForeignKey(ContractTemplate, on_delete=models.PROTECT, related_name='versions')
    variant = models.CharField(max_length=8, choices=[(key, key) for key in ('combined', 'product', 'service')])
    version = models.PositiveIntegerField()
    markdown = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    credential = models.ForeignKey('content.McpCredential', null=True, on_delete=models.SET_NULL, related_name='+')
    author_label = models.CharField(max_length=255, default='Sistema')
    change_note = models.TextField()
    restored_from = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        constraints = [models.UniqueConstraint(fields=['template', 'variant', 'version'], name='unique_contract_template_revision')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Las versiones contractuales son inmutables.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Las versiones contractuales no se eliminan.')


class ContractTemplateMirror(models.Model):
    """Current draft PDF lives in the DB, so synchronization can roll back."""

    template = models.ForeignKey(ContractTemplate, on_delete=models.PROTECT, related_name='mirrors')
    variant = models.CharField(max_length=8, choices=[(key, key) for key in ('combined', 'product', 'service')])
    document = models.OneToOneField('content.Document', on_delete=models.PROTECT, related_name='contract_mirror')
    revision = models.ForeignKey(ContractTemplateVersion, on_delete=models.PROTECT, related_name='+')
    pdf_content = models.BinaryField()
    synced_at = models.DateTimeField()
    imported_markdown = models.TextField(blank=True, default='')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['template', 'variant'], name='unique_contract_template_mirror')]
