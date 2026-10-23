from content.models.editorial_text import EditorialTextModel
from django.db import models


class EmailTemplateConfig(EditorialTextModel, models.Model):
    """
    Stores admin-editable overrides for email template text content.

    Each row maps a ``template_key`` (matching a key in
    ``EMAIL_TEMPLATE_REGISTRY``) to a JSON dict of content overrides
    and an ``is_active`` flag that can disable the email entirely.
    """

    template_key = models.CharField(
        max_length=80,
        unique=True,
        help_text='Registry key (e.g. proposal_sent_client)',
    )
    content_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON dict of {field_key: custom_value} overrides.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='When False the email is silently skipped.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Email Template Config'
        verbose_name_plural = 'Email Template Configs'
        ordering = ['template_key']

    def __str__(self):
        return f'EmailTemplateConfig({self.template_key})'
