import uuid

from django.conf import settings
from django.db import models

from content.models.history_tracked import HistoryTrackedModel
from django.utils import timezone
from content.utils import (
    render_slug_pattern,
    resolve_unique_slug,
    safe_slug,
)

from .hour_packages import Nationality


class BusinessProposal(HistoryTrackedModel):
    """
    Core model for business proposals sent to prospective clients.

    Each proposal has a UUID for public access, an expiration date,
    and tracks client interactions (views, reminder emails).
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

    class FirstViewNotificationStatus(models.TextChoices):
        NOT_STARTED = 'not_started', 'Not started'
        PENDING = 'pending', 'Pending'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'
        LEGACY_UNVERIFIED = 'legacy_unverified', 'Legacy unverified'

    # Natural status transitions of the proposal lifecycle. Admins may force
    # ANY status from the panel (see proposal_status_service.change_status);
    # this map now gates side effects (emails, onboarding) and feeds
    # available_transitions so the UI can group "Flujo normal" vs "Forzar".
    # 'viewed' and 'expired' are system-set, never natural manual targets.
    ALLOWED_TRANSITIONS = {
        Status.DRAFT:       frozenset({Status.SENT}),
        Status.SENT:        frozenset({Status.NEGOTIATING, Status.REJECTED}),
        Status.VIEWED:      frozenset({Status.NEGOTIATING, Status.REJECTED}),
        Status.NEGOTIATING: frozenset({Status.ACCEPTED, Status.REJECTED}),
        Status.ACCEPTED:    frozenset({Status.FINISHED}),
        # FINISHED, REJECTED, EXPIRED → terminal (no outgoing transitions)
    }

    # Spanish, user-facing labels for statuses (the TextChoices labels are kept
    # in English for the Django admin). Used to build human error messages.
    STATUS_LABELS_ES = {
        Status.DRAFT: 'Borrador',
        Status.SENT: 'Enviada',
        Status.VIEWED: 'Vista',
        Status.ACCEPTED: 'Aceptada',
        Status.REJECTED: 'Rechazada',
        Status.NEGOTIATING: 'En negociación',
        Status.EXPIRED: 'Expirada',
        Status.FINISHED: 'Finalizada',
    }

    @classmethod
    def status_label_es(cls, value):
        """Return the Spanish label for a status value (falls back to the raw value)."""
        return cls.STATUS_LABELS_ES.get(value, value)

    class Currency(models.TextChoices):
        COP = 'COP', 'COP'
        USD = 'USD', 'USD'

    class Language(models.TextChoices):
        ES = 'es', 'Español'
        EN = 'en', 'English'

    # Identity
    uuid = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    title = models.CharField(max_length=255)
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField(blank=True)
    slug = models.SlugField(
        max_length=120, unique=True, blank=True, db_index=True,
        help_text='Personal, human-friendly handle used in the public URL /proposal/<slug>/.',
    )

    # Language
    language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ES
    )

    # Financial
    total_investment = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.COP
    )
    nationality = models.CharField(
        max_length=3,
        choices=Nationality.choices,
        default=Nationality.COL,
        help_text='Drives hour-package catalog seeding and suggested currency.',
    )
    hosting_percent = models.PositiveIntegerField(
        default=60,
        help_text=(
            'Percentage of total investment used as the hosting price '
            'reference before monthly proration.'
        ),
    )
    hosting_discount_nine_month = models.PositiveIntegerField(
        default=40,
        help_text='Default discount % for nine-month hosting payments.',
    )
    hosting_discount_semiannual = models.PositiveIntegerField(
        default=20,
        help_text='Default discount % for semiannual (6-month) hosting payments.',
    )
    hosting_discount_quarterly = models.PositiveIntegerField(
        default=10,
        help_text='Default discount % for quarterly (3-month) hosting payments.',
    )

    # Status & lifecycle
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    reminder_days = models.PositiveIntegerField(default=10)
    urgency_reminder_days = models.PositiveIntegerField(default=15)
    discount_percent = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_explainer_video = models.BooleanField(
        default=True,
        help_text="Show the welcome video when the four public options are available.",
    )
    show_contract_terms = models.BooleanField(
        default=True,
        help_text=(
            'Whether Spanish public proposals expose the generic contract '
            'terms module and its masked draft download.'
        ),
    )
    class ContractModality(models.TextChoices):
        SINGLE = 'single', 'Contrato único'
        SPLIT = 'split', 'Producto y servicio'

    contract_modality = models.CharField(
        max_length=10,
        choices=ContractModality.choices,
        default=ContractModality.SINGLE,
        help_text=(
            'How the deal closes: one contract, or a product contract plus a '
            'separate hosting, maintenance and support contract. Chosen during '
            'negotiation from the Documents tab.'
        ),
    )
    automations_paused = models.BooleanField(
        default=False,
        help_text='When true, no automatic emails (reminder, urgency, inactivity) are sent for this proposal. '
                  'New proposals default to automations enabled (not paused).',
    )
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    urgency_email_sent_at = models.DateTimeField(null=True, blank=True)

    # Classification
    PROJECT_TYPE_CHOICES = [
        ('website', 'Sitio Web'),
        ('ecommerce', 'E-commerce'),
        ('webapp', 'Aplicación Web'),
        ('landing', 'Landing Page'),
        ('redesign', 'Rediseño'),
        ('mobile_app', 'App Móvil'),
        ('branding', 'Branding / Identidad Visual'),
        ('cms', 'Sistema CMS'),
        ('portal', 'Portal / Intranet'),
        ('api_integration', 'Integración de APIs'),
        ('marketplace', 'Marketplace'),
        ('erp', 'Sistema ERP / Administrativo'),
        ('booking', 'Sistema de Reservas'),
        ('dashboard', 'Dashboard / Reportes'),
        ('crm', 'Sistema CRM'),
        ('saas', 'SaaS / Plataforma'),
        ('chatbot', 'Chatbot / Asistente Virtual'),
        ('ai_tool', 'Herramienta con IA'),
        ('automation', 'Automatización / RPA'),
        ('data_analytics', 'Analítica de Datos / BI'),
        ('plugin_extension', 'Plugin / Extensión'),
        ('other', 'Otro'),
    ]
    MARKET_TYPE_CHOICES = [
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
        ('saas', 'SaaS'),
        ('retail', 'Retail'),
        ('services', 'Servicios profesionales'),
        ('health', 'Salud'),
        ('education', 'Educación'),
        ('real_estate', 'Inmobiliaria'),
        ('fintech', 'Fintech / Finanzas'),
        ('restaurant', 'Restaurantes / F&B'),
        ('tourism', 'Turismo / Hospitalidad'),
        ('logistics', 'Logística / Transporte'),
        ('sports', 'Deportes / Fitness'),
        ('legal', 'Servicios Legales / Jurídico'),
        ('construction', 'Construcción / Arquitectura'),
        ('media', 'Medios / Entretenimiento'),
        ('ngo', 'ONG / Sector Público'),
        ('agriculture', 'Agro / Tecnología Agrícola'),
        ('tech', 'Tecnología / Software'),
        ('consulting', 'Consultoría / Asesoría'),
        ('automotive', 'Automotriz'),
        ('fashion', 'Moda / Textil'),
        ('beauty', 'Belleza / Cuidado Personal'),
        ('manufacturing', 'Manufactura / Industrial'),
        ('energy', 'Energía / Utilities'),
        ('gaming', 'Videojuegos / Gaming'),
        ('other', 'Otro'),
    ]
    project_type = models.CharField(
        max_length=20, choices=PROJECT_TYPE_CHOICES, blank=True, default=''
    )
    market_type = models.CharField(
        max_length=20, choices=MARKET_TYPE_CHOICES, blank=True, default=''
    )
    project_type_custom = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Free-text description when project_type is "other".'
    )
    market_type_custom = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Free-text description when market_type is "other".'
    )
    client_phone = models.CharField(max_length=30, blank=True, default='')

    # Rejection feedback
    rejection_reason = models.CharField(max_length=100, blank=True, default='')
    rejection_comment = models.TextField(blank=True, default='')

    email_intro = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Párrafo descriptivo del alcance de la propuesta usado en el '
            'correo inicial enviado al cliente. Si queda vacío se usa un '
            'texto por defecto derivado del título.'
        ),
    )

    class EmailSigner(models.TextChoices):
        GUSTAVO = 'gustavo', 'Gustavo Pérez'
        CARLOS = 'carlos', 'Carlos Blanco'

    email_features = models.JSONField(
        default=list, blank=True,
        help_text=(
            'Lista de bullets que se renderizan en el bloque "Qué incluye" del '
            'correo de envío. Ejemplo: ["Dashboard tiempo real...", "App móvil...", "Integración ERP..."]. '
            'Si queda vacío el bloque se omite.'
        ),
    )
    email_method_phases = models.JSONField(
        default=list, blank=True,
        help_text=(
            'Lista de 3 fases para el card "Método en 3 fases". Cada item: '
            '{"number":"01","title":"Diagnóstico","duration":"5 días","description":"..."}. '
            'Si queda vacío se usa el método estándar de marca.'
        ),
    )
    email_signed_by = models.CharField(
        max_length=20,
        choices=EmailSigner.choices,
        default=EmailSigner.GUSTAVO,
        help_text='Firmante del correo (nombre + rol se resuelven desde settings.EMAIL_SIGNATURES).',
    )

    # Tracking
    last_activity_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    first_view_notification_status = models.CharField(
        max_length=20,
        choices=FirstViewNotificationStatus.choices,
        default=FirstViewNotificationStatus.NOT_STARTED,
        help_text='Durable delivery state for the internal first-view email.',
    )
    first_view_notification_attempts = models.PositiveSmallIntegerField(default=0)
    first_view_notification_attempted_at = models.DateTimeField(null=True, blank=True)
    first_view_notification_sent_at = models.DateTimeField(null=True, blank=True)
    first_view_notification_last_error = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    revisit_alert_sent_at = models.DateTimeField(null=True, blank=True)
    abandonment_email_sent_at = models.DateTimeField(null=True, blank=True)
    investment_interest_email_sent_at = models.DateTimeField(null=True, blank=True)
    followup_scheduled_at = models.DateTimeField(null=True, blank=True)
    stakeholder_alert_sent_at = models.DateTimeField(null=True, blank=True)
    post_expiration_alert_sent_at = models.DateTimeField(null=True, blank=True)
    calculator_followup_sent_at = models.DateTimeField(null=True, blank=True)

    # Engagement signals
    engagement_declining = models.BooleanField(
        default=False,
        help_text='Set when engagement decay is detected; reset on normal session.',
    )
    cached_heat_score = models.PositiveSmallIntegerField(
        default=0,
        help_text='Pre-computed heat score (1-10), updated by tracking endpoint and periodic task.',
    )
    last_automated_email_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp of the last automated email sent to the client. Used for 24h cooldown.',
    )

    # Calculator selections (persisted from client browser)
    selected_modules = models.JSONField(
        default=list, blank=True,
        help_text='List of module IDs selected by the client in the calculator (e.g. ["module-payments", "module-reservations"]).',
    )

    # Contract parameters for PDF generation (populated when status → negotiating)
    contract_params = models.JSONField(
        default=dict, blank=True,
        help_text='Parameters for contract PDF generation (party names, cédulas, bank details, etc.).',
    )

    # Client (UserProfile with role=client) — single source of truth for client identity.
    # Legacy client_name/client_email/client_phone fields above are write-through snapshots
    # synced from this profile by ProposalClientService.sync_snapshot().
    client = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.PROTECT,
        related_name='proposals',
        null=True,
        blank=True,
        limit_choices_to={'role': 'client'},
        help_text='UserProfile (rol=cliente) propietario de esta propuesta.',
    )

    # Platform: commercial proposal lives on a project deliverable (OneToOne)
    deliverable = models.OneToOneField(
        'accounts.Deliverable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_proposal',
        help_text='Platform deliverable that owns this proposal (PDFs, technical document).',
    )
    platform_onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set when acceptance onboarding (sync + welcome email) completed; prevents duplicate runs.',
    )

    ONBOARDING_PENDING = 'pending'
    ONBOARDING_COMPLETED = 'completed'
    ONBOARDING_FAILED = 'failed'
    ONBOARDING_STATUS_CHOICES = [
        (ONBOARDING_PENDING, 'Pending'),
        (ONBOARDING_COMPLETED, 'Completed'),
        (ONBOARDING_FAILED, 'Failed'),
    ]
    platform_onboarding_status = models.CharField(
        max_length=20,
        choices=ONBOARDING_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text='Tracks async onboarding: pending (in progress), completed, failed.',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Business Proposal'
        verbose_name_plural = 'Business Proposals'

    def __str__(self):
        return f'{self.title} — {self.client_name}'

    @property
    def available_transitions(self):
        """Return sorted list of valid manual status transitions from current status."""
        return sorted(self.ALLOWED_TRANSITIONS.get(self.status, frozenset()))

    @property
    def has_confirmed_module_selection(self):
        return self.change_logs.filter(
            change_type='calc_confirmed',
        ).exists()

    def save(self, *args, **kwargs):
        if not self.slug:
            from content.models.proposal_default_config import ProposalDefaultConfig

            cfg = ProposalDefaultConfig.objects.filter(language=self.language).first()
            pattern = cfg.default_slug_pattern if cfg else None

            if pattern:
                base = render_slug_pattern(pattern, self, fallback='propuesta')
            else:
                slug_source = self.client_name
                if not slug_source and self.client_id:
                    slug_source = self.client.user.get_full_name() or self.client.user.email
                base = safe_slug(slug_source, 'propuesta')

            self.slug = resolve_unique_slug(base, type(self), exclude_pk=self.pk)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if the proposal has expired by status or date."""
        if self.status == self.Status.EXPIRED:
            return True
        if self.expires_at and self.expires_at < timezone.now():
            return True
        return False

    @property
    def days_remaining(self):
        """Return the number of days until expiration, or None if no expiry."""
        if not self.expires_at:
            return None
        delta = (self.expires_at - timezone.now()).days
        return max(delta, 0)

    @property
    def public_url(self):
        """Build the client-facing URL for viewing this proposal."""
        base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
        identifier = self.slug or self.uuid
        return f'{base}/proposal/{identifier}'


class ProposalAlert(models.Model):
    """
    Manual alert/reminder created by sellers for a specific proposal.

    Complements the automatic alerts (not_viewed, not_responded, expiring_soon)
    with seller-defined reminders that appear in the proposals dashboard.
    """

    ALERT_TYPE_CHOICES = [
        ('reminder', 'Recordatorio'),
        ('followup', 'Seguimiento'),
        ('call', 'Llamada'),
        ('meeting', 'Reunión'),
        ('custom', 'Personalizado'),
        ('discount_suggestion', 'Sugerencia de descuento'),
        ('post_expiration_visit', 'Visita post-expiración'),
        ('high_engagement_today', 'Alta actividad hoy'),
        ('whatsapp_suggestion', 'Sugerencia de WhatsApp'),
        ('calculator_followup', 'Seguimiento calculadora'),
        ('engagement_decay', 'Pérdida de engagement'),
        ('post_rejection_revisit', 'Revisita post-rechazo'),
        ('first_view', 'Primera vista confirmada'),
    ]

    proposal = models.ForeignKey(
        BusinessProposal,
        on_delete=models.CASCADE,
        related_name='manual_alerts',
    )
    alert_type = models.CharField(
        max_length=30, choices=ALERT_TYPE_CHOICES, default='reminder'
    )
    message = models.CharField(max_length=500)
    alert_date = models.DateTimeField(
        help_text='When this alert should become visible.'
    )
    PRIORITY_CHOICES = [
        ('critical', 'Alta urgencia'),
        ('high', 'Alta'),
        ('normal', 'Normal'),
    ]
    PRIORITY_BY_TYPE = {
        'engagement_decay': 'critical',
        'post_expiration_visit': 'critical',
        'post_rejection_revisit': 'critical',
        'first_view': 'high',
        'discount_suggestion': 'high',
        'high_engagement_today': 'high',
        'calculator_followup': 'high',
        'whatsapp_suggestion': 'high',
    }
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default='normal',
        help_text='Auto-computed priority based on alert type.',
    )
    is_dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.priority or self.priority == 'normal':
            self.priority = self.PRIORITY_BY_TYPE.get(self.alert_type, 'normal')
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Proposal Alert'
        verbose_name_plural = 'Proposal Alerts'

    def __str__(self):
        return f'Alert: {self.proposal.client_name} — {self.message[:50]}'
