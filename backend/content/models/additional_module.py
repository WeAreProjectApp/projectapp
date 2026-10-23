from content.models.editorial_text import EditorialTextModel
import uuid

from django.conf import settings
from django.db import models


class AdditionalModuleCategory(models.Model):
    """Administrable bilingual grouping for the additional-module catalog."""

    slug = models.SlugField(max_length=140, unique=True)
    name_es = models.CharField(max_length=160)
    name_en = models.CharField(max_length=160)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Additional module category'
        verbose_name_plural = 'Additional module categories'
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                name='uniq_additional_module_category_order',
            ),
        ]

    def __str__(self):
        return self.name_es


class AdditionalModule(EditorialTextModel, models.Model):
    """Generic client-facing capability that can be sold with any project."""

    category = models.ForeignKey(
        AdditionalModuleCategory,
        on_delete=models.PROTECT,
        related_name='modules',
    )
    slug = models.SlugField(max_length=160, unique=True)
    icon = models.CharField(max_length=40, blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    name_es = models.CharField(max_length=240)
    name_en = models.CharField(max_length=240)
    summary_es = models.TextField()
    summary_en = models.TextField()
    what_is_es = models.TextField()
    what_is_en = models.TextField()
    purpose_es = models.TextField()
    purpose_en = models.TextField()
    problems_solved_es = models.JSONField(default=list)
    problems_solved_en = models.JSONField(default=list)
    integrations_es = models.JSONField(default=list)
    integrations_en = models.JSONField(default=list)
    implementation_requirements_es = models.JSONField(default=list)
    implementation_requirements_en = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__order', 'order', 'id']
        verbose_name = 'Additional module'
        verbose_name_plural = 'Additional modules'
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'order'],
                name='uniq_additional_module_position',
            ),
        ]
        indexes = [
            models.Index(fields=['is_active', 'category', 'order']),
        ]

    def __str__(self):
        return self.name_es


class AdditionalModuleShareLink(models.Model):
    """Revocable public link with an immutable module selection and language."""

    class Language(models.TextChoices):
        SPANISH = 'es', 'Español'
        ENGLISH = 'en', 'English'

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    recipient_label = models.CharField(max_length=255)
    client = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        related_name='additional_module_share_links',
        null=True,
        blank=True,
    )
    language = models.CharField(
        max_length=2,
        choices=Language.choices,
        default=Language.SPANISH,
    )
    selected_modules = models.ManyToManyField(
        AdditionalModule,
        related_name='share_links',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_additional_module_share_links',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Per-link switch for the catalog explainer video. The catalog-wide switch
    # (ExplainerVideoSettings) governs: the link shows it only if both are on.
    show_explainer_video = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Additional module share link'
        verbose_name_plural = 'Additional module share links'

    def __str__(self):
        return f'{self.recipient_label} — {self.uuid}'


class AdditionalModuleShareView(models.Model):
    """One first-party view event per browser session for a shared catalog."""

    share_link = models.ForeignKey(
        AdditionalModuleShareLink,
        on_delete=models.CASCADE,
        related_name='view_events',
    )
    session_id = models.CharField(max_length=64)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at', '-id']
        verbose_name = 'Additional module share view'
        verbose_name_plural = 'Additional module share views'
        constraints = [
            models.UniqueConstraint(
                fields=['share_link', 'session_id'],
                name='uniq_additional_module_share_session',
            ),
        ]
        indexes = [
            models.Index(fields=['share_link', 'viewed_at']),
        ]

    def __str__(self):
        return f'{self.share_link.recipient_label} — {self.session_id[:8]}'
