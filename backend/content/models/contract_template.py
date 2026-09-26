from django.db import models


class ContractTemplate(models.Model):
    """
    Stores a contract template as markdown with optional {placeholders}.

    The default template (is_default=True) is used when generating contracts
    from the ContractParamsModal. Placeholders like {client_full_name} are
    substituted with values from proposal.contract_params at PDF generation time.

    It is the one contract: the public legal view, the draft download,
    generated contracts and the Document-manager window (``mirror_document``)
    all read it. Its text changes only through versioned data migrations;
    Django admin shows it read-only.
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
