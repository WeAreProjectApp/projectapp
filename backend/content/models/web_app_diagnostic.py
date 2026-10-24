from content.models.editorial_text import EditorialTextModel
import uuid

from django.conf import settings
from django.db import models

from content.utils import (
    render_slug_pattern,
    resolve_unique_slug,
    safe_slug,
)


class WebAppDiagnostic(EditorialTextModel, models.Model):
    """Diagnóstico técnico ofrecido a clientes que ya tienen una aplicación web.

    Cada diagnóstico se ata a un cliente (UserProfile, role='client') y
    se presenta al cliente como una secuencia de ``DiagnosticSection`` con
    ``content_json`` (paridad con propuestas). Comparte el vocabulario
    de estados con BusinessProposal; la distinción entre envío inicial y
    final se preserva en los timestamps `initial_sent_at` / `final_sent_at`.

        DRAFT
          → SENT            (Doc 1 enviado al cliente, sin precios todavía —
                             initial_sent_at se sella)
          → NEGOTIATING     (cliente aceptó, equipo está analizando el repo)
          → SENT            (Docs 1+2+3 con pricing completo — final_sent_at
                             se sella, estado vuelve a SENT)
          → ACCEPTED | REJECTED
          → FINISHED        (tras ACCEPTED, cuando el proyecto se cierra)
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        VIEWED = 'viewed', 'Viewed'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        NEGOTIATING = 'negotiating', 'Negotiating'
        EXPIRED = 'expired', 'Expired'
        FINISHED = 'finished', 'Finished'

    ALLOWED_TRANSITIONS = {
        Status.DRAFT:       frozenset({Status.SENT}),
        Status.SENT:        frozenset({Status.NEGOTIATING, Status.ACCEPTED, Status.REJECTED}),
        Status.VIEWED:      frozenset({Status.NEGOTIATING, Status.REJECTED}),
        Status.NEGOTIATING: frozenset({Status.SENT, Status.ACCEPTED, Status.REJECTED}),
        Status.ACCEPTED:    frozenset({Status.FINISHED}),
    }

    class Currency(models.TextChoices):
        COP = 'COP', 'COP'
        USD = 'USD', 'USD'

    class Language(models.TextChoices):
        ES = 'es', 'Español'
        EN = 'en', 'English'

    class SizeCategory(models.TextChoices):
        SMALL = 'small', 'Pequeña'
        MEDIUM = 'medium', 'Mediana'
        LARGE = 'large', 'Grande'

    # Identidad
    uuid = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True,
    )
    slug = models.SlugField(
        max_length=120, unique=True, blank=True, db_index=True,
        help_text='Personal, human-friendly handle used in the public URL /diagnostic/<slug>/.',
    )
    title = models.CharField(max_length=255)
    client = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.PROTECT,
        related_name='web_app_diagnostics',
        limit_choices_to={'role': 'client'},
    )

    # Client identity snapshot — kept in sync via update_client_profile() cascade;
    # survives profile renames without breaking historical records.
    client_name    = models.CharField(max_length=255, blank=True)
    client_email   = models.CharField(max_length=254, blank=True)
    client_phone   = models.CharField(max_length=50,  blank=True)
    client_company = models.CharField(max_length=255, blank=True)

    language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ES,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    # Pricing (rellenado tras el análisis preliminar)
    investment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.COP,
    )
    payment_terms = models.JSONField(
        default=dict, blank=True,
        help_text='Ej: {"initial_pct": 40, "final_pct": 60}',
    )
    duration_label = models.CharField(max_length=80, blank=True, default='')

    # Radiografía técnica (alimenta variables del Anexo / Doc 3)
    size_category = models.CharField(
        max_length=10, choices=SizeCategory.choices, blank=True, default='',
    )
    radiography = models.JSONField(default=dict, blank=True)

    # Acuerdo de Confidencialidad (NDA)
    confidentiality_params = models.JSONField(
        default=dict, blank=True,
        help_text='Datos para rellenar placeholders del NDA (NIT cliente, representante legal, valor SMMLV, ciudad, etc.).',
    )

    # Engagement
    view_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps de ciclo
    initial_sent_at = models.DateTimeField(null=True, blank=True)
    final_sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Set on the initial send from the language config; drives the UI expiration badge.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Web App Diagnostic'
        verbose_name_plural = 'Web App Diagnostics'

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'

    @property
    def public_url(self):
        base = getattr(settings, 'FRONTEND_BASE_URL', '').rstrip('/')
        identifier = self.slug or self.uuid
        return f'{base}/diagnostic/{identifier}/'

    @property
    def is_expired(self):
        """True once the status is EXPIRED or the expiry date has passed."""
        if self.status == self.Status.EXPIRED:
            return True
        if self.expires_at is None:
            return False
        from django.utils import timezone
        return self.expires_at < timezone.now()

    @property
    def days_remaining(self):
        """Whole days until expiry (0 if past), or None when no expiry set."""
        if self.expires_at is None:
            return None
        from django.utils import timezone
        delta = self.expires_at - timezone.now()
        return max(delta.days, 0)

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, frozenset())

    def save(self, *args, **kwargs):
        if not self.slug:
            from content.models.diagnostic_default_config import DiagnosticDefaultConfig

            cfg = DiagnosticDefaultConfig.objects.filter(language=self.language).first()
            pattern = cfg.default_slug_pattern if cfg else None

            if pattern:
                base = render_slug_pattern(pattern, self, fallback='diagnostico')
            else:
                slug_source = self.client_name
                if not slug_source and self.client_id:
                    slug_source = self.client.user.get_full_name() or self.client.user.email
                base = safe_slug(slug_source, 'diagnostico')

            self.slug = resolve_unique_slug(base, type(self), exclude_pk=self.pk)
        super().save(*args, **kwargs)
