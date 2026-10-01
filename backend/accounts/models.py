import secrets
import string
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from content.models.history_tracked import HistoryTrackedModel, HistoryQuerySet
from django.db.models.functions import NullIf
from django.utils import timezone

from accounts.services.image_utils import optimize_avatar, optimize_image
from content.storage import get_private_storage


class UserProfileQuerySet(HistoryQuerySet):
    def clients(self):
        return self.filter(role=UserProfile.ROLE_CLIENT).select_related('user')

    def admins(self):
        return self.filter(role=UserProfile.ROLE_ADMIN).select_related('user')


class UserProfileManager(models.Manager.from_queryset(UserProfileQuerySet)):
    pass


class UserProfile(HistoryTrackedModel):
    """
    Extends auth.User with platform-specific fields.
    One-to-one relationship to avoid changing AUTH_USER_MODEL.
    """

    ROLE_ADMIN = 'admin'
    ROLE_CLIENT = 'client'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_CLIENT, 'Client'),
    ]

    DOCUMENT_NAVIGATION_PROJECT = 'project'
    DOCUMENT_NAVIGATION_CLIENT = 'client'
    DOCUMENT_NAVIGATION_CHOICES = [
        (DOCUMENT_NAVIGATION_PROJECT, 'Proyectos'),
        (DOCUMENT_NAVIGATION_CLIENT, 'Clientes'),
    ]

    PLACEHOLDER_EMAIL_DOMAIN = '@temp.example.com'

    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_OTHER = 'other'
    GENDER_PREFER_NOT = 'prefer_not_to_say'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Masculino'),
        (GENDER_FEMALE, 'Femenino'),
        (GENDER_OTHER, 'Otro'),
        (GENDER_PREFER_NOT, 'Prefiero no decir'),
    ]

    EDUCATION_PRIMARY = 'primaria'
    EDUCATION_SECONDARY = 'secundaria'
    EDUCATION_TECHNICAL = 'tecnico'
    EDUCATION_UNIVERSITY = 'universitario'
    EDUCATION_POSTGRADUATE = 'posgrado'
    EDUCATION_OTHER = 'otro'
    EDUCATION_CHOICES = [
        (EDUCATION_PRIMARY, 'Primaria'),
        (EDUCATION_SECONDARY, 'Secundaria'),
        (EDUCATION_TECHNICAL, 'Técnico'),
        (EDUCATION_UNIVERSITY, 'Universitario'),
        (EDUCATION_POSTGRADUATE, 'Posgrado'),
        (EDUCATION_OTHER, 'Otro'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_CLIENT)
    document_navigation_mode = models.CharField(
        max_length=10,
        choices=DOCUMENT_NAVIGATION_CHOICES,
        default=DOCUMENT_NAVIGATION_PROJECT,
        help_text='Grouping last selected by this account in the document manager.',
    )
    is_onboarded = models.BooleanField(
        default=False,
        help_text='True after the client sets their own password.',
    )
    email_verified = models.BooleanField(
        default=False,
        help_text='True after the client confirms ownership of their email via an OTP code.',
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    company_name = models.CharField(max_length=200, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    cedula = models.CharField(max_length=20, blank=True, default='')
    nit = models.CharField(
        max_length=32, blank=True, default='',
        help_text='Tax id for company clients; preferred over cedula on billing documents.',
    )
    billing_code = models.CharField(
        max_length=12, null=True, blank=True, unique=True,
        help_text='Short code for per-client collection-account numbering '
                  '(PA-{CODE}-{NNN}). Auto-derived on first use; store None, never "".',
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, blank=True, default='',
    )
    education_level = models.CharField(
        max_length=20, choices=EDUCATION_CHOICES, blank=True, default='',
    )
    avatar = models.ImageField(
        upload_to='avatars/', null=True, blank=True,
        help_text='Optimized automatically on upload.',
    )
    avatar_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='Deprecated — use avatar ImageField instead.',
    )
    theme_color = models.CharField(
        max_length=7, blank=True, default='',
        help_text='Hex color for UI theme (e.g. #002921).',
    )
    cover_image = models.CharField(
        max_length=300, blank=True, default='',
        help_text='Path to cover gallery image (e.g. NASA Archive/imgi_21_nasa_the_blue_marble.jpg).',
    )
    custom_cover_image = models.ImageField(
        upload_to='covers/', null=True, blank=True,
        help_text='User-uploaded custom cover image.',
    )
    profile_completed = models.BooleanField(
        default=False,
        help_text='True after the client fills in their profile details.',
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text='When set, this client is archived and hidden from the '
                  'default panel client lists. Archiving is the client-side '
                  'twin of a project moving out of an active state, and it '
                  'cascades its projects to "suspended". Independent from '
                  'auth.User.is_active, which is False for client shells.',
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='archived_client_profiles',
        help_text='Who archived this client last. Cleared on unarchive; the '
                  'durable trail is the AccountingChangeLog row.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_profiles',
        help_text='Admin who created this client account.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserProfileManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} ({self.get_role_display()})'

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_client(self):
        return self.role == self.ROLE_CLIENT

    @property
    def is_email_placeholder(self):
        """True when the linked user's email is a generated temp placeholder."""
        return (self.user.email or '').endswith(self.PLACEHOLDER_EMAIL_DOMAIN)

    @property
    def is_archived_client(self):
        """True when the client was archived from the panel."""
        return self.archived_at is not None

    @property
    def avatar_display_url(self):
        """Return the best available avatar URL."""
        if self.avatar:
            return self.avatar.url
        return self.avatar_url or ''

    def save(self, *args, **kwargs):
        if self.avatar and hasattr(self.avatar.file, 'content_type'):
            content_type = getattr(self.avatar.file, 'content_type', '')
            if content_type and content_type.startswith('image/'):
                try:
                    self.avatar = optimize_avatar(self.avatar)
                except Exception:
                    pass
        super().save(*args, **kwargs)


def _user_role(self):
    profile = getattr(self, 'profile', None)
    return profile.role if profile else None


def _user_is_client_role(self):
    profile = getattr(self, 'profile', None)
    return bool(profile and profile.is_client)


def _user_is_admin_role(self):
    profile = getattr(self, 'profile', None)
    return bool(profile and profile.is_admin)


_AuthUser = get_user_model()
_AuthUser.add_to_class('role', property(_user_role))
_AuthUser.add_to_class('is_client_role', property(_user_is_client_role))
_AuthUser.add_to_class('is_admin_role', property(_user_is_admin_role))


class CommunicationPanelPreference(models.Model):
    """Per-account defaults for the Communications panel."""

    NAVIGATION_PROJECT = 'project'
    NAVIGATION_CLIENT = 'client'
    NAVIGATION_CHOICES = [
        (NAVIGATION_PROJECT, 'Proyectos'),
        (NAVIGATION_CLIENT, 'Clientes'),
    ]

    ORDER_RECENT = 'recent'
    ORDER_OLDEST = 'oldest'
    ORDER_TITLE = 'title'
    ORDER_CHOICES = [
        (ORDER_RECENT, 'Recientes'),
        (ORDER_OLDEST, 'Antiguos'),
        (ORDER_TITLE, 'Título'),
    ]

    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_EMAIL = 'email'
    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_EMAIL, 'Correo'),
    ]

    PAGE_SIZE_CHOICES = [(10, '10'), (20, '20'), (50, '50')]
    NAVIGATION_WIDTH_MIN = 240
    NAVIGATION_WIDTH_MAX = 400
    NAVIGATION_WIDTH_DEFAULT = 288

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='communication_panel_preference',
    )
    navigation_mode = models.CharField(
        max_length=10,
        choices=NAVIGATION_CHOICES,
        default=NAVIGATION_PROJECT,
    )
    thread_order = models.CharField(
        max_length=10,
        choices=ORDER_CHOICES,
        default=ORDER_RECENT,
    )
    page_size = models.PositiveSmallIntegerField(
        choices=PAGE_SIZE_CHOICES,
        default=20,
    )
    default_channel = models.CharField(
        max_length=10,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_WHATSAPP,
    )
    show_manual_help = models.BooleanField(default=True)
    navigation_width = models.PositiveSmallIntegerField(
        default=NAVIGATION_WIDTH_DEFAULT,
        validators=[
            MinValueValidator(NAVIGATION_WIDTH_MIN),
            MaxValueValidator(NAVIGATION_WIDTH_MAX),
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def defaults(cls):
        return {
            'navigation_mode': cls.NAVIGATION_PROJECT,
            'thread_order': cls.ORDER_RECENT,
            'page_size': 20,
            'default_channel': cls.CHANNEL_WHATSAPP,
            'show_manual_help': True,
            'navigation_width': cls.NAVIGATION_WIDTH_DEFAULT,
        }

    def reset(self):
        for field, value in self.defaults().items():
            setattr(self, field, value)
        self.save(update_fields=[*self.defaults(), 'updated_at'])

    def __str__(self):
        return f'{self.user_id}/communications'


class VerificationCode(models.Model):
    """
    Time-limited OTP for onboarding verification and password resets.
    """

    PURPOSE_ONBOARDING = 'onboarding'
    PURPOSE_PASSWORD_RESET = 'password_reset'
    PURPOSE_EMAIL_VALIDATION = 'email_validation'
    PURPOSE_CHOICES = [
        (PURPOSE_ONBOARDING, 'Onboarding'),
        (PURPOSE_PASSWORD_RESET, 'Password Reset'),
        (PURPOSE_EMAIL_VALIDATION, 'Email Validation'),
    ]

    MAX_ATTEMPTS = 5
    EXPIRY_MINUTES = 10

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_codes',
    )
    code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default=PURPOSE_ONBOARDING,
    )
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'OTP for {self.user.email} ({self.purpose}) — {"used" if self.is_used else "active"}'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired and self.attempts < self.MAX_ATTEMPTS

    def increment_attempts(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])

    @classmethod
    def generate_code(cls):
        return ''.join(secrets.choice(string.digits) for _ in range(6))

    @classmethod
    def create_for_user(cls, user, purpose=PURPOSE_ONBOARDING):
        """Invalidate previous codes and create a new one."""
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        return cls.objects.create(
            user=user,
            code=cls.generate_code(),
            purpose=purpose,
            expires_at=timezone.now() + timezone.timedelta(minutes=cls.EXPIRY_MINUTES),
        )


class Project(HistoryTrackedModel):
    """
    A client project managed through the platform.
    Each project belongs to a single client (User with client role).
    """

    STATUS_DEVELOPMENT = 'development'
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_COMPLETED = 'completed'
    STATUS_DECOMMISSIONED = 'decommissioned'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_DEVELOPMENT, 'En desarrollo'),
        (STATUS_ACTIVE, 'Activo'),
        (STATUS_SUSPENDED, 'Suspendido'),
        (STATUS_COMPLETED, 'Completado'),
        (STATUS_DECOMMISSIONED, 'Dado de baja'),
        (STATUS_ARCHIVED, 'Archivado'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects',
        help_text='The client user this project belongs to.',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DEVELOPMENT,
        help_text=(
            'Compatibility mirror of current_state.system_key. New writes '
            'must use the project state-transition service.'
        ),
    )
    current_state = models.ForeignKey(
        'content.DocumentState',
        on_delete=models.PROTECT,
        related_name='current_projects',
        null=True,
        blank=True,
        limit_choices_to={'catalog': 'projects'},
    )
    state_review_required = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True until a migrated legacy status is confirmed by a user.',
    )
    progress = models.PositiveIntegerField(
        default=0,
        help_text='Overall progress percentage (0-100).',
    )
    start_date = models.DateField(null=True, blank=True)
    estimated_end_date = models.DateField(null=True, blank=True)
    payment_milestones = models.JSONField(
        default=list, blank=True,
        help_text='Development payment milestones from proposal section 4 (admin-visible only).',
    )
    hosting_tiers = models.JSONField(
        default=list, blank=True,
        help_text='Hosting billing tiers from proposal (quarterly/semiannual/nine-month with pricing).',
    )
    hosting_start_date = models.DateField(
        null=True, blank=True,
        help_text='Date when hosting billing should begin (set by admin).',
    )

    # Product URLs. Operational access is served only by the dedicated detail API.
    production_url = models.URLField(max_length=500, blank=True, default='')
    staging_url = models.URLField(max_length=500, blank=True, default='')
    admin_url = models.URLField(max_length=500, blank=True, default='')
    repository_url = models.URLField(max_length=500, blank=True, default='')

    # Legacy Django-admin access awaiting environment classification. New writes
    # belong to ProjectAdminAccess; the password remains a Fernet ciphertext.
    admin_username = models.CharField(max_length=150, blank=True, default='')
    admin_password_encrypted = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.name} — {self.client.email}'

    @property
    def status_display(self):
        if self.current_state_id:
            return self.current_state.name
        return 'Sin clasificar'

    def linked_business_proposal(self):
        """Returns the first phase's BusinessProposal, or None.

        Lee desde ProjectPhase; si el proyecto todavía no tiene phase, cae al
        vínculo legacy por deliverable para que las propuestas adjuntadas antes
        de completar el cableado de phases sigan resolviéndose.

        Kept for backwards compatibility with serializers and templates that
        expect a single proposal per project. New code should iterate
        ``self.phases.all()`` instead.
        """
        first = self.phases.select_related('business_proposal').first()
        if first:
            return first.business_proposal
        from content.models import BusinessProposal
        return (
            BusinessProposal.objects.filter(deliverable__project_id=self.id)
            .select_related('deliverable')
            .order_by('deliverable_id')
            .first()
        )


class ProjectAdminAccess(HistoryTrackedModel):
    """Django-admin access for one fixed project environment.

    The password is always a Fernet token. Plaintext only exists for the
    duration of a dedicated reveal/copy request and is never serialized by a
    general project endpoint.
    """

    class Environment(models.TextChoices):
        PRODUCTION = 'production', 'Producción'
        STAGING = 'staging', 'Staging'

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='admin_accesses',
    )
    environment = models.CharField(max_length=20, choices=Environment.choices)
    admin_url = models.URLField(max_length=500, blank=True, default='')
    admin_username = models.CharField(max_length=150, blank=True, default='')
    admin_password_encrypted = models.TextField(blank=True, default='')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_project_admin_accesses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['environment']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'environment'],
                name='unique_project_admin_access_environment',
            ),
        ]

    def __str__(self):
        return f'{self.project.name} — {self.get_environment_display()}'


class ProjectAccessNote(HistoryTrackedModel):
    """Encrypted operational note attached to a project's access detail."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='access_notes',
    )
    title = models.CharField(max_length=255)
    content_encrypted = models.TextField()
    is_sensitive = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_project_access_notes',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_project_access_notes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.project.name} — {self.title}'


class ProjectPhase(models.Model):
    """One phase of a Project, backed by a BusinessProposal from the panel.

    A project can have multiple phases (e.g. discovery, design, build),
    each corresponding to a separate signed proposal. Phases are ordered;
    ``order=1`` is the first phase, ``order=2`` is the second, etc.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='phases',
    )
    business_proposal = models.ForeignKey(
        'content.BusinessProposal',
        on_delete=models.PROTECT,
        related_name='project_phases',
    )
    order = models.PositiveIntegerField()
    hosting_start_date = models.DateField(
        null=True, blank=True,
        help_text='Date when this phase\'s hosting billing begins (set by admin).',
    )
    hosting_activated_at = models.DateField(
        null=True, blank=True,
        help_text='Date this phase was incorporated into the recurring '
                  'subscription billing. Null = not yet billed (the billing '
                  'cron will onboard it once hosting_start_date arrives).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'business_proposal'],
                name='unique_proposal_per_project',
            ),
        ]

    def __str__(self):
        return f'{self.project.name} — Fase {self.order}: {self.business_proposal.title}'


class DeliveryWorkspace(models.Model):
    """Project-wide optimistic version; all delivery writes lock the project."""

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='delivery_workspace')
    version = models.PositiveIntegerField(default=0)


class DeliveryNode(models.Model):
    key = models.SlugField(max_length=100)
    title = models.CharField(max_length=300)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['id']

    def __str__(self):
        return self.title


class ProjectContract(DeliveryNode):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='delivery_contracts')
    document = models.ForeignKey('content.Document', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_contracts')
    proposal_document = models.ForeignKey('content.ProposalDocument', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_contracts')
    client_visible = models.BooleanField(default=False)

    class Meta(DeliveryNode.Meta):
        constraints = [
            models.UniqueConstraint(fields=['project', 'key'], name='delivery_contract_key'),
            models.CheckConstraint(condition=(models.Q(document__isnull=False, proposal_document__isnull=True) | models.Q(document__isnull=True, proposal_document__isnull=False)), name='delivery_contract_one_source'),
        ]


class ContractAmendment(DeliveryNode):
    contract = models.ForeignKey(ProjectContract, on_delete=models.PROTECT, related_name='amendments')
    document = models.ForeignKey('content.Document', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_amendments')
    proposal_document = models.ForeignKey('content.ProposalDocument', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_amendments')
    client_visible = models.BooleanField(default=False)

    class Meta(DeliveryNode.Meta):
        constraints = [
            models.UniqueConstraint(fields=['contract', 'key'], name='delivery_amendment_key'),
            models.CheckConstraint(condition=(models.Q(document__isnull=False, proposal_document__isnull=True) | models.Q(document__isnull=True, proposal_document__isnull=False)), name='delivery_amendment_one_source'),
        ]

    @property
    def project(self):
        return self.contract.project


class DeliveryScope(DeliveryNode):
    contract = models.ForeignKey(ProjectContract, on_delete=models.PROTECT, related_name='scopes')
    amendment = models.ForeignKey(ContractAmendment, on_delete=models.PROTECT, null=True, blank=True, related_name='scopes')
    description = models.TextField(blank=True, default='')
    is_current = models.BooleanField(default=True)

    class Meta(DeliveryNode.Meta):
        constraints = [models.UniqueConstraint(fields=['contract', 'key'], name='delivery_scope_key')]

    @property
    def project(self):
        return self.contract.project


class DeliveryPhase(DeliveryNode):
    scope = models.ForeignKey(DeliveryScope, on_delete=models.CASCADE, related_name='phases')
    commercial_phase = models.ForeignKey(ProjectPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_phases')
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta(DeliveryNode.Meta):
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['scope', 'key'], name='delivery_phase_key')]

    @property
    def project(self):
        return self.scope.project


class DeliveryStage(DeliveryNode):
    class EditorialStatus(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        PUBLISHED = 'published', 'Aprobado internamente'

    phase = models.ForeignKey(DeliveryPhase, on_delete=models.CASCADE, related_name='stages')
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    editorial_status = models.CharField(max_length=20, choices=EditorialStatus.choices, default=EditorialStatus.DRAFT)

    class Meta(DeliveryNode.Meta):
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['phase', 'key'], name='delivery_stage_key')]

    @property
    def project(self):
        return self.phase.project


class Requirement(DeliveryNode):
    """Client-readable validation guide; editorial drafts never imply approval."""

    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', 'Pendiente de publicación'
        IN_REVIEW = 'in_review', 'En revisión'
        APPROVED = 'approved', 'Aprobado'
        OBJECTED = 'objected', 'Objetado'
        REJECTED = 'rejected', 'Rechazado'

    stage = models.ForeignKey(DeliveryStage, on_delete=models.CASCADE, related_name='requirements')
    description = models.TextField(blank=True, default='')
    guide = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    context = models.ForeignKey('DeliveryPromptContext', on_delete=models.PROTECT, null=True, blank=True, related_name='requirements')
    source_references = models.JSONField(default=list, blank=True)

    class Meta(DeliveryNode.Meta):
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['stage', 'key'], name='delivery_requirement_key')]

    @property
    def project(self):
        return self.stage.project

    @property
    def project_id(self):
        return self.stage.phase.scope.contract.project_id


class DeliveryPublication(models.Model):
    """Immutable round, including the exact client-facing guide composition."""

    stage = models.ForeignKey(DeliveryStage, on_delete=models.PROTECT, related_name='publications')
    round = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_publications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-round']
        constraints = [models.UniqueConstraint(fields=['stage', 'round'], name='delivery_publication_round')]


class DeliveryDocumentLink(models.Model):
    """Exactly one delivery level owns this attachment; authorization is inherited."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='delivery_documents')
    document = models.ForeignKey('content.Document', on_delete=models.PROTECT, related_name='delivery_links')
    level = models.CharField(max_length=20)
    contract = models.ForeignKey(ProjectContract, on_delete=models.CASCADE, null=True, blank=True, related_name='document_links')
    amendment = models.ForeignKey(ContractAmendment, on_delete=models.CASCADE, null=True, blank=True, related_name='document_links')
    scope = models.ForeignKey(DeliveryScope, on_delete=models.CASCADE, null=True, blank=True, related_name='document_links')
    phase = models.ForeignKey(DeliveryPhase, on_delete=models.CASCADE, null=True, blank=True, related_name='document_links')
    stage = models.ForeignKey(DeliveryStage, on_delete=models.CASCADE, null=True, blank=True, related_name='document_links')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, null=True, blank=True, related_name='document_links')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_document_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']


class DeliveryDocumentSnapshot(models.Model):
    publication = models.ForeignKey(DeliveryPublication, on_delete=models.PROTECT, related_name='document_snapshots')
    link = models.ForeignKey(DeliveryDocumentLink, on_delete=models.PROTECT, related_name='snapshots')
    title = models.CharField(max_length=300)
    file = models.FileField(storage=get_private_storage, upload_to='delivery/snapshots/%Y/%m/', max_length=500)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['publication', 'link'], name='delivery_document_snapshot_link')]


class ContractSignatureEvidence(models.Model):
    contract = models.ForeignKey(ProjectContract, on_delete=models.PROTECT, null=True, blank=True, related_name='signature_evidence')
    amendment = models.ForeignKey(ContractAmendment, on_delete=models.PROTECT, null=True, blank=True, related_name='signature_evidence')
    file = models.FileField(storage=get_private_storage, upload_to='delivery/signatures/%Y/%m/', max_length=500)
    sha256 = models.CharField(max_length=64)
    method = models.CharField(max_length=20, choices=[('portal', 'Platform'), ('external', 'Firma externa')], default='external')
    source_sha256 = models.CharField(max_length=64, blank=True, default='')
    source_snapshot = models.JSONField(default=dict)
    signer_name = models.CharField(max_length=255)
    signed_at = models.DateTimeField()
    attestation = models.TextField()
    attested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_signature_attestations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.CheckConstraint(condition=(models.Q(contract__isnull=False, amendment__isnull=True) | models.Q(contract__isnull=True, amendment__isnull=False)), name='delivery_signature_one_parent')]

    @property
    def title(self):
        return self.source_snapshot.get('title') or (self.contract.title if self.contract_id else self.amendment.title)


class RequirementReview(models.Model):
    publication = models.ForeignKey(DeliveryPublication, on_delete=models.PROTECT, related_name='reviews')
    requirement = models.ForeignKey(Requirement, on_delete=models.PROTECT, related_name='reviews')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_reviews')
    requirement_version = models.PositiveIntegerField()
    content_snapshot = models.JSONField(default=dict)
    decision = models.CharField(max_length=20, choices=Requirement.ReviewStatus.choices)
    message = models.TextField(blank=True, default='')
    environment = models.CharField(max_length=200, blank=True, default='')
    is_external = models.BooleanField(default=False)
    client_statement = models.TextField(blank=True, default='')
    original_reviewer = models.CharField(max_length=300, blank=True, default='')
    reviewed_at = models.DateTimeField(default=timezone.now)
    source_message = models.ForeignKey('content.CommunicationMessage', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_approvals')
    source_snapshot = models.JSONField(default=dict)
    evidence_document_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class DeliveryReviewDocumentEvidence(models.Model):
    """The exact document supplied as proof for a recorded client decision."""
    review = models.ForeignKey(RequirementReview, on_delete=models.PROTECT, related_name='document_evidence')
    document = models.ForeignKey('content.Document', on_delete=models.PROTECT, related_name='delivery_review_evidence')
    title = models.CharField(max_length=300)
    file = models.FileField(storage=get_private_storage, upload_to='delivery/reviews/%Y/%m/', max_length=500)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['review', 'document'], name='delivery_review_document_unique')]


class DeliveryMessage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='delivery_messages')
    level = models.CharField(max_length=20)
    target_id = models.PositiveBigIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_messages')
    requirements = models.ManyToManyField(Requirement, blank=True, related_name='delivery_messages')
    documents = models.ManyToManyField('content.Document', blank=True, related_name='delivery_messages')
    message = models.TextField()
    is_internal = models.BooleanField(default=False)
    context = models.ForeignKey('DeliveryPromptContext', on_delete=models.PROTECT, null=True, blank=True, related_name='messages')
    source_references = models.JSONField(default=list, blank=True)
    reply_classifications = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class DeliveryOperation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='delivery_operations')
    request_id = models.CharField(max_length=100)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_operations')
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'request_id'], name='delivery_operation_key')]


class ImmutablePromptQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError('Captured authoring context cannot be edited.')

    def bulk_update(self, objs, fields, **kwargs):
        raise ValueError('Captured authoring context cannot be edited.')


class ImmutablePromptRecord(models.Model):
    objects = ImmutablePromptQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Captured authoring context cannot be edited.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)


class DeliveryPromptContext(ImmutablePromptRecord):
    """An explicit, durable authoring selection, independent of draft stages."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='delivery_prompt_contexts')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delivery_prompt_contexts')
    contract = models.ForeignKey(ProjectContract, on_delete=models.PROTECT, related_name='prompt_contexts')
    scope = models.ForeignKey(DeliveryScope, on_delete=models.PROTECT, null=True, blank=True, related_name='prompt_contexts')
    stage = models.ForeignKey(DeliveryStage, on_delete=models.PROTECT, null=True, blank=True, related_name='prompt_contexts')
    mode = models.CharField(max_length=12, choices=[('guides', 'Crear guías'), ('reply', 'Preparar respuesta')])
    request_id = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64)
    captured_version = models.PositiveIntegerField()
    amendment_ids = models.JSONField(default=list)
    missing_sources = models.JSONField(default=list)
    uncertainties = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    complete = models.BooleanField(default=False)
    prompt = models.TextField()
    template = models.JSONField(default=dict)
    schema = models.JSONField(default=dict)
    conversation = models.JSONField(default=dict)
    manifest_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['project', 'request_id'], name='delivery_prompt_request_unique')]


class DeliveryPromptSource(ImmutablePromptRecord):
    """Exact private source bytes, identity and extracted fragments for citations."""
    context = models.ForeignKey(DeliveryPromptContext, on_delete=models.PROTECT, related_name='sources')
    source_key = models.CharField(max_length=100)
    title = models.CharField(max_length=300)
    origin = models.CharField(max_length=32)
    source_id = models.CharField(max_length=100)
    role = models.CharField(max_length=32)
    applicability_note = models.TextField(blank=True, default='')
    document = models.ForeignKey('content.Document', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_prompt_sources')
    proposal_document = models.ForeignKey('content.ProposalDocument', on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_prompt_sources')
    signature_evidence = models.ForeignKey(ContractSignatureEvidence, on_delete=models.PROTECT, null=True, blank=True, related_name='prompt_sources')
    version = models.PositiveIntegerField(null=True, blank=True)
    version_kind = models.CharField(max_length=30, default='unknown')
    date = models.DateTimeField(null=True, blank=True)
    file = models.FileField(storage=get_private_storage, upload_to='delivery/prompt-sources/%Y/%m/', max_length=500, blank=True)
    filename = models.CharField(max_length=300, blank=True, default='')
    content_type = models.CharField(max_length=100, blank=True, default='')
    sha256 = models.CharField(max_length=64, blank=True, default='')
    snapshot = models.JSONField(default=dict)
    fragments = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=[('included', 'Incluida'), ('missing', 'Faltante'), ('unreadable', 'Ilegible'), ('partial', 'Parcial')])
    warnings = models.JSONField(default=list)
    limits = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['context', 'source_key'], name='delivery_prompt_source_unique')]


class ChangeRequest(models.Model):
    """
    A client-initiated change request for a project.
    The admin evaluates and responds with estimated cost/time.
    """

    STATUS_PENDING = 'pending'
    STATUS_EVALUATING = 'evaluating'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_NEEDS_CLARIFICATION = 'needs_clarification'
    STATUS_OUT_OF_SCOPE = 'out_of_scope'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_EVALUATING, 'En evaluación'),
        (STATUS_APPROVED, 'Aprobada'),
        (STATUS_REJECTED, 'Rechazada'),
        (STATUS_NEEDS_CLARIFICATION, 'Requiere aclaración'),
        (STATUS_OUT_OF_SCOPE, 'Fuera de alcance'),
    ]

    PRIORITY_CRITICAL = 'critical'
    PRIORITY_HIGH = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW = 'low'
    PRIORITY_CHOICES = [
        (PRIORITY_CRITICAL, 'Crítica'),
        (PRIORITY_HIGH, 'Alta'),
        (PRIORITY_MEDIUM, 'Media'),
        (PRIORITY_LOW, 'Baja'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='change_requests',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='change_requests',
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    module_or_screen = models.CharField(max_length=200, blank=True, default='')
    suggested_priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM,
    )
    is_urgent = models.BooleanField(default=False)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    admin_response = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Estimated additional cost in project currency.',
    )
    estimated_time = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Estimated time to implement (e.g. "2 semanas").',
    )
    linked_requirement = models.ForeignKey(
        Requirement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='source_change_request',
        help_text='Requirement created from this change request.',
    )
    source_requirement = models.ForeignKey(
        Requirement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='change_requests_about',
        help_text='Requirement this change request is about (client picked when filing).',
    )
    screenshot = models.ImageField(
        upload_to='change_requests/', null=True, blank=True,
        help_text='Optimized automatically on upload (WhatsApp-like compression).',
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Hidden from default lists; row kept for audit.',
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} [{self.get_status_display()}]'

    def save(self, *args, **kwargs):
        if self.screenshot and hasattr(self.screenshot.file, 'content_type'):
            content_type = getattr(self.screenshot.file, 'content_type', '')
            if content_type and content_type.startswith('image/'):
                try:
                    self.screenshot = optimize_image(self.screenshot, field_name='screenshot')
                except Exception:
                    pass
        super().save(*args, **kwargs)


class ChangeRequestComment(models.Model):
    """Comment thread on a change request. Supports internal (admin-only) comments."""

    change_request = models.ForeignKey(
        ChangeRequest, on_delete=models.CASCADE, related_name='comments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='change_request_comments',
    )
    content = models.TextField()
    is_internal = models.BooleanField(
        default=False, help_text='Internal comments are visible only to admins.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.user.email} on CR #{self.change_request_id}'


class BugReport(models.Model):
    """
    A bug report filed for a specific project deliverable (epic/scope).
    Admin manages the lifecycle: confirm, fix, QA, resolve.
    """

    SEVERITY_CRITICAL = 'critical'
    SEVERITY_HIGH = 'high'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_LOW = 'low'
    SEVERITY_CHOICES = [
        (SEVERITY_CRITICAL, 'Crítica'),
        (SEVERITY_HIGH, 'Alta'),
        (SEVERITY_MEDIUM, 'Media'),
        (SEVERITY_LOW, 'Baja'),
    ]

    STATUS_REPORTED = 'reported'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_FIXING = 'fixing'
    STATUS_QA = 'qa'
    STATUS_RESOLVED = 'resolved'
    STATUS_NOT_REPRODUCIBLE = 'not_reproducible'
    STATUS_WONT_FIX = 'wont_fix'
    STATUS_DUPLICATE = 'duplicate'
    STATUS_CHOICES = [
        (STATUS_REPORTED, 'Reportado'),
        (STATUS_CONFIRMED, 'Confirmado'),
        (STATUS_FIXING, 'En corrección'),
        (STATUS_QA, 'En QA'),
        (STATUS_RESOLVED, 'Resuelto por equipo'),
        (STATUS_NOT_REPRODUCIBLE, 'No reproducible'),
        (STATUS_WONT_FIX, 'No se corregirá'),
        (STATUS_DUPLICATE, 'Duplicado'),
    ]

    ENV_PRODUCTION = 'production'
    ENV_STAGING = 'staging'
    ENV_DEV = 'dev'
    ENV_CHOICES = [
        (ENV_PRODUCTION, 'Producción'),
        (ENV_STAGING, 'Staging'),
        (ENV_DEV, 'Desarrollo'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='bug_reports',
        null=True, blank=True,
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bug_reports',
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM,
    )
    steps_to_reproduce = models.JSONField(
        default=list, blank=True,
        help_text='Numbered list of steps to reproduce the bug.',
    )
    expected_behavior = models.TextField(blank=True, default='')
    actual_behavior = models.TextField(blank=True, default='')
    environment = models.CharField(
        max_length=20, choices=ENV_CHOICES, default=ENV_PRODUCTION,
    )
    device_browser = models.CharField(max_length=200, blank=True, default='')
    is_recurring = models.BooleanField(default=False)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default=STATUS_REPORTED,
    )
    admin_response = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField(default=0)
    linked_bug = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='duplicates',
        help_text='Original bug if this is a duplicate.',
    )
    source_requirement = models.ForeignKey(
        Requirement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bug_reports_about',
        help_text='Requirement this bug is about (client picked when filing).',
    )
    screenshot = models.ImageField(
        upload_to='bug_reports/', null=True, blank=True,
        help_text='Optimized automatically on upload (WhatsApp-like compression).',
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Hidden from default lists; row kept for audit.',
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} [{self.get_status_display()}]'

    def save(self, *args, **kwargs):
        if self.screenshot and hasattr(self.screenshot.file, 'content_type'):
            content_type = getattr(self.screenshot.file, 'content_type', '')
            if content_type and content_type.startswith('image/'):
                try:
                    self.screenshot = optimize_image(self.screenshot, field_name='screenshot')
                except Exception:
                    pass
        super().save(*args, **kwargs)


class BugComment(models.Model):
    """Comment thread on a bug report. Supports internal (admin-only) comments."""

    bug_report = models.ForeignKey(
        BugReport, on_delete=models.CASCADE, related_name='comments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bug_comments',
    )
    content = models.TextField()
    is_internal = models.BooleanField(
        default=False, help_text='Internal comments are visible only to admins.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.user.email} on Bug #{self.bug_report_id}'


class Deliverable(models.Model):
    """
    A file deliverable for a project, organized by category.
    Admin uploads, client downloads. Supports version history.
    Optional file for logical rows (e.g. epic scope / linked business proposal).
    """

    CATEGORY_DESIGNS = 'designs'
    CATEGORY_DOCUMENTS = 'documents'
    CATEGORY_CONTRACT = 'contract'
    CATEGORY_AMENDMENT = 'amendment'
    CATEGORY_LEGAL_ANNEX = 'legal_annex'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_DESIGNS, 'Diseños'),
        (CATEGORY_DOCUMENTS, 'Documentos'),
        (CATEGORY_CONTRACT, 'Contrato'),
        (CATEGORY_AMENDMENT, 'Otrosí'),
        (CATEGORY_LEGAL_ANNEX, 'Anexo legal'),
        (CATEGORY_OTHER, 'Otros'),
    ]

    ADMIN_ONLY_CATEGORIES = (
        CATEGORY_DESIGNS, CATEGORY_CONTRACT, CATEGORY_AMENDMENT, CATEGORY_LEGAL_ANNEX,
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='deliverables',
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER,
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    source_epic_key = models.CharField(max_length=200, blank=True, default='', db_index=True)
    source_epic_title = models.CharField(max_length=300, blank=True, default='')
    file = models.FileField(upload_to='deliverables/', blank=True, null=True)
    current_version = models.PositiveIntegerField(default=1)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='uploaded_deliverables',
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Hidden from default lists; row kept for audit.',
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                models.F('project'),
                NullIf(models.F('source_epic_key'), models.Value('')),
                name='uniq_deliverable_project_epic_key',
            ),
        ]

    def __str__(self):
        return f'{self.title} v{self.current_version} [{self.get_category_display()}]'

    @property
    def file_name(self):
        if self.file:
            return self.file.name.split('/')[-1]
        return ''

    @property
    def file_size(self):
        try:
            return self.file.size
        except Exception:
            return 0


class DataModelEntity(models.Model):
    """
    A data model entity synced from the BusinessProposal technical document.
    One copy per deliverable (FK).
    """

    deliverable = models.ForeignKey(
        Deliverable, on_delete=models.CASCADE, related_name='data_model_entities',
    )
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    key_fields = models.TextField(
        blank=True, default='',
        help_text='Comma-separated key fields for this entity.',
    )
    source_entity_name = models.CharField(
        max_length=300, blank=True, default='', db_index=True,
        help_text='Original entity name from proposal JSON, used for idempotent sync.',
    )
    synced_from_proposal = models.BooleanField(default=False)
    is_archived = models.BooleanField(
        default=False, db_index=True,
        help_text='Hidden from default lists; row kept for audit.',
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                models.F('deliverable'),
                NullIf(models.F('source_entity_name'), models.Value('')),
                name='uniq_data_model_entity_deliverable_source',
            ),
        ]

    def __str__(self):
        return f'{self.name} (deliverable={self.deliverable_id})'


class ProjectDataModelEntity(models.Model):
    """
    A data-model entity defined at the project level via admin JSON upload.
    Reflects the actual/real state of the project's data model.
    Separate from DataModelEntity (deliverable-scoped, proposal-synced).
    """

    project = models.ForeignKey(
        'Project', on_delete=models.CASCADE,
        related_name='project_data_model_entities',
    )
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    key_fields = models.TextField(
        blank=True, default='',
        help_text='Comma-separated key fields for this entity.',
    )
    relationship = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Relationship description (e.g. "1:N with Order").',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} (project={self.project_id})'


class DeliverableVersion(models.Model):
    """Historical version of a deliverable file."""

    deliverable = models.ForeignKey(
        Deliverable, on_delete=models.CASCADE, related_name='versions',
    )
    file = models.FileField(upload_to='deliverables/versions/')
    version_number = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='deliverable_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.deliverable.title} v{self.version_number}'

    @property
    def file_name(self):
        if self.file:
            return self.file.name.split('/')[-1]
        return ''

    @property
    def file_size(self):
        try:
            return self.file.size
        except Exception:
            return 0


class DeliverableFile(models.Model):
    """Additional file attached to a deliverable (contract, annex, etc.)."""

    deliverable = models.ForeignKey(
        Deliverable, on_delete=models.CASCADE, related_name='attachment_files',
    )
    file = models.FileField(upload_to='deliverables/attachments/')
    title = models.CharField(max_length=300, blank=True, default='')
    category = models.CharField(
        max_length=20, choices=Deliverable.CATEGORY_CHOICES, default=Deliverable.CATEGORY_OTHER,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='deliverable_attachment_files',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.deliverable.title} — {self.title or self.file_name}'

    @property
    def file_name(self):
        if self.file:
            return self.file.name.split('/')[-1]
        return ''


class DeliverableClientFolder(models.Model):
    """Optional folder label for client-uploaded PDFs on a deliverable."""

    deliverable = models.ForeignKey(
        Deliverable, on_delete=models.CASCADE, related_name='client_folders',
    )
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='deliverable_client_folders',
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.deliverable_id} — {self.name}'


class DeliverableClientUpload(models.Model):
    """PDF uploaded by the client (or admin) under a deliverable, optionally in a folder."""

    deliverable = models.ForeignKey(
        Deliverable, on_delete=models.CASCADE, related_name='client_uploads',
    )
    folder = models.ForeignKey(
        DeliverableClientFolder, on_delete=models.CASCADE,
        null=True, blank=True, related_name='uploads',
    )
    file = models.FileField(upload_to='deliverables/client_uploads/')
    title = models.CharField(max_length=300, blank=True, default='')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='deliverable_client_uploads',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.deliverable_id} — {self.title or self.file_name}'

    @property
    def file_name(self):
        if self.file:
            return self.file.name.split('/')[-1]
        return ''


class Notification(models.Model):
    """
    In-app notification for platform users.
    Created by the notification service when relevant events occur.
    """

    TYPE_BUG_REPORTED = 'bug_reported'
    TYPE_BUG_STATUS_CHANGED = 'bug_status_changed'
    TYPE_CR_CREATED = 'cr_created'
    TYPE_CR_STATUS_CHANGED = 'cr_status_changed'
    TYPE_CR_CONVERTED = 'cr_converted'
    TYPE_REQUIREMENT_MOVED = 'requirement_moved'
    TYPE_REQUIREMENT_APPROVED = 'requirement_approved'
    TYPE_DELIVERABLE_UPLOADED = 'deliverable_uploaded'
    TYPE_DELIVERABLE_NEW_VERSION = 'deliverable_new_version'
    TYPE_COMMENT_ADDED = 'comment_added'
    TYPE_GENERAL = 'general'
    TYPE_CHOICES = [
        (TYPE_BUG_REPORTED, 'Bug reportado'),
        (TYPE_BUG_STATUS_CHANGED, 'Estado de bug actualizado'),
        (TYPE_CR_CREATED, 'Solicitud de cambio creada'),
        (TYPE_CR_STATUS_CHANGED, 'Solicitud de cambio actualizada'),
        (TYPE_CR_CONVERTED, 'Solicitud convertida en requerimiento'),
        (TYPE_REQUIREMENT_MOVED, 'Requerimiento movido'),
        (TYPE_REQUIREMENT_APPROVED, 'Requerimiento aprobado'),
        (TYPE_DELIVERABLE_UPLOADED, 'Entregable subido'),
        (TYPE_DELIVERABLE_NEW_VERSION, 'Nueva versión de entregable'),
        (TYPE_COMMENT_ADDED, 'Nuevo comentario'),
        (TYPE_GENERAL, 'General'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
    )
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    title = models.CharField(max_length=300)
    message = models.TextField(blank=True, default='')
    related_object_type = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Model name: project, change_request, bug_report, deliverable, requirement',
    )
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications',
        help_text='Project context for deep-linking.',
    )
    deliverable = models.ForeignKey(
        'Deliverable', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications',
        help_text='Deliverable context for deep-linking when applicable.',
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_type_display()}] {self.title} → {self.user.email}'


class HostingSubscription(models.Model):
    """
    Recurring hosting subscription for a project.
    Derived from the linked BusinessProposal pricing or set manually.
    """

    # Legacy values remain readable for historical data but are intentionally
    # absent from PLAN_CHOICES so they cannot be selected for new subscriptions.
    PLAN_MONTHLY = 'monthly'
    PLAN_ANNUAL = 'annual'
    PLAN_QUARTERLY = 'quarterly'
    PLAN_SEMIANNUAL = 'semiannual'
    PLAN_NINE_MONTH = 'nine_month'
    PLAN_CHOICES = [
        (PLAN_QUARTERLY, 'Trimestral'),
        (PLAN_SEMIANNUAL, 'Semestral'),
        (PLAN_NINE_MONTH, 'Cada 9 meses'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_PENDING = 'pending'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Activa'),
        (STATUS_SUSPENDED, 'Suspendida'),
        (STATUS_CANCELLED, 'Cancelada'),
        (STATUS_PENDING, 'Pendiente'),
    ]

    # Legacy values are included only for calculations of preserved records.
    PLAN_MONTHS = {
        PLAN_MONTHLY: 1,
        PLAN_QUARTERLY: 3,
        PLAN_SEMIANNUAL: 6,
        PLAN_NINE_MONTH: 9,
        PLAN_ANNUAL: 12,
    }

    PLAN_LABELS = dict(PLAN_CHOICES) | {
        PLAN_MONTHLY: 'Mensual (histórico)',
        PLAN_ANNUAL: 'Anual (histórico)',
    }

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name='hosting_subscription',
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_QUARTERLY)
    base_monthly_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Monthly hosting cost before discount (COP).',
    )
    discount_percent = models.PositiveIntegerField(
        default=0, help_text='Discount % based on the selected hosting plan.',
    )
    effective_monthly_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Monthly cost after discount (COP).',
    )
    billing_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Total amount charged per billing cycle (COP).',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    start_date = models.DateField(
        help_text='Date from which the subscription is active and billable.',
    )
    next_billing_date = models.DateField(
        null=True, blank=True,
        help_text='Next date a payment is due.',
    )
    wompi_payment_source_id = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Wompi payment source ID for stored-card recurring billing.',
    )
    card_brand = models.CharField(max_length=20, blank=True, default='')
    card_last_four = models.CharField(max_length=4, blank=True, default='')
    card_exp_month = models.CharField(max_length=2, blank=True, default='')
    card_exp_year = models.CharField(max_length=4, blank=True, default='')
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Hidden from subscription lists; row kept for audit.',
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.name} — {self.plan_label} (${self.billing_amount:,.0f} COP)'

    @property
    def billing_months(self):
        return self.PLAN_MONTHS.get(self.plan, 1)

    @property
    def plan_label(self):
        return self.PLAN_LABELS.get(self.plan, self.plan)

    def calculate_amounts(self):
        """Recalculate effective_monthly_amount and billing_amount from base + plan."""
        from decimal import Decimal
        factor = (Decimal(100) - Decimal(self.discount_percent)) / Decimal(100)
        self.effective_monthly_amount = round(self.base_monthly_amount * factor, 2)
        self.billing_amount = round(self.effective_monthly_amount * self.billing_months, 2)


class Payment(models.Model):
    """
    A single payment record for a hosting subscription billing cycle.
    Linked to Wompi transactions for payment processing.
    """

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_OVERDUE = 'overdue'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_PROCESSING, 'Procesando'),
        (STATUS_PAID, 'Pagado'),
        (STATUS_FAILED, 'Fallido'),
        (STATUS_OVERDUE, 'Vencido'),
    ]

    subscription = models.ForeignKey(
        HostingSubscription, on_delete=models.PROTECT, related_name='payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=300, blank=True, default='')
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    due_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    wompi_transaction_id = models.CharField(max_length=100, blank=True, default='')
    wompi_payment_link_id = models.CharField(max_length=100, blank=True, default='')
    wompi_payment_link_url = models.URLField(max_length=500, blank=True, default='')
    charge_attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text='Number of automatic charge attempts made for this payment.',
    )
    last_charge_error = models.CharField(max_length=300, blank=True, default='')
    next_retry_at = models.DateField(
        null=True, blank=True,
        help_text='Earliest date the auto-billing task may retry this payment.',
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Hidden from default payment lists; row kept for audit.',
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-billing_period_start']

    def __str__(self):
        return f'Payment ${self.amount:,.0f} — {self.get_status_display()} ({self.billing_period_start} → {self.billing_period_end})'


class PaymentHistory(models.Model):
    """Append-only log of payment status transitions."""

    SOURCE_API = 'api'
    SOURCE_WOMPI_LINK = 'wompi_link'
    SOURCE_WEBHOOK = 'webhook'
    SOURCE_WOMPI_VERIFY = 'wompi_verify'
    SOURCE_SYSTEM = 'system'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_API, 'API'),
        (SOURCE_WOMPI_LINK, 'Wompi payment link'),
        (SOURCE_WEBHOOK, 'Wompi webhook'),
        (SOURCE_WOMPI_VERIFY, 'Wompi verify'),
        (SOURCE_SYSTEM, 'System'),
        (SOURCE_MANUAL, 'Manual (admin)'),
    ]

    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name='history',
    )
    from_status = models.CharField(max_length=20, choices=Payment.STATUS_CHOICES)
    to_status = models.CharField(max_length=20, choices=Payment.STATUS_CHOICES)
    source = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, blank=True, default='',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', '-created_at']),
        ]

    def __str__(self):
        return f'{self.from_status} → {self.to_status} (payment {self.payment_id})'


class SavedFilterTab(models.Model):
    """
    Pestañas de filtros guardados por admin del panel, persistidas en DB
    (antes localStorage). Una entrada por (user, view, nombre arbitrario).
    """

    VIEW_PROPOSAL = 'proposal'
    VIEW_CLIENT = 'client'
    VIEW_DIAGNOSTIC = 'diagnostic'
    VIEW_VIEW_MAP = 'view_map'
    VIEW_ACCOUNTING_INCOME = 'accounting_income'
    VIEW_ACCOUNTING_EXPENSE = 'accounting_expense'
    VIEW_ACCOUNTING_HOSTING = 'accounting_hosting'
    VIEW_ACCOUNTING_POCKET = 'accounting_pocket'
    VIEW_ACCOUNTING_RECURRING = 'accounting_recurring'
    VIEW_ACCOUNTING_ADS = 'accounting_ads'
    VIEW_ACCOUNTING_HISTORY = 'accounting_history'
    # Historial keeps one view per subtab: "Envíos" and "Cambios" filter
    # different columns, so a tab saved in one would be meaningless in the
    # other. The pre-existing `accounting_history` above was never written by
    # anything and stays only so its slot is not recycled under old rows.
    VIEW_ACCOUNTING_HISTORY_SENDS = 'accounting_history_sends'
    VIEW_ACCOUNTING_HISTORY_CHANGES = 'accounting_history_changes'
    # Cards has no seeded tabs (nothing to "reset" in Configuración), but the
    # page saves custom tabs like every other accounting view; without the
    # choice the serializer 400s each attempt.
    VIEW_ACCOUNTING_CARDS = 'accounting_cards'
    VIEW_ACCOUNTING_COLLECTIONS = 'accounting_collections'
    VIEW_COMMUNICATION = 'communication'
    VIEW_CHOICES = [
        (VIEW_PROPOSAL, 'Proposal'),
        (VIEW_CLIENT, 'Client'),
        (VIEW_DIAGNOSTIC, 'Diagnostic'),
        (VIEW_VIEW_MAP, 'View Map'),
        (VIEW_ACCOUNTING_INCOME, 'Accounting Income'),
        (VIEW_ACCOUNTING_EXPENSE, 'Accounting Expense'),
        (VIEW_ACCOUNTING_HOSTING, 'Accounting Hosting'),
        (VIEW_ACCOUNTING_POCKET, 'Accounting Pocket'),
        (VIEW_ACCOUNTING_RECURRING, 'Accounting Recurring'),
        (VIEW_ACCOUNTING_ADS, 'Accounting Ads'),
        (VIEW_ACCOUNTING_HISTORY, 'Accounting History'),
        (VIEW_ACCOUNTING_HISTORY_SENDS, 'Accounting History — Sends'),
        (VIEW_ACCOUNTING_HISTORY_CHANGES, 'Accounting History — Changes'),
        (VIEW_ACCOUNTING_CARDS, 'Accounting Cards'),
        (VIEW_ACCOUNTING_COLLECTIONS, 'Accounting Collections'),
        (VIEW_COMMUNICATION, 'Communication'),
    ]

    MAX_TABS_PER_VIEW = 12

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_filter_tabs',
    )
    # 32, not 20: 'accounting_recurring' already sat exactly on the old
    # ceiling and 'accounting_collections' is 22, so the next view to be
    # added would have been silently truncated at the database level.
    view = models.CharField(max_length=32, choices=VIEW_CHOICES, db_index=True)
    name = models.CharField(max_length=200)
    filters = models.JSONField(default=dict, blank=True)
    # Restore point: the tab's definition as seeded/created. The panel
    # auto-saves every filter edit into `filters`, so without this a seeded
    # tab like "Solo esperados" could lose its meaning irreversibly.
    base_filters = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)
    # Written by the seeding, never by the panel. It is what lets
    # "Restablecer" put the factory tabs back without taking the user's own
    # ones with them, and it survives a rename — matching by name would not.
    is_seeded = models.BooleanField(default=False)
    # Kept out of the strip without being deleted, so a tab that is only
    # useful now and then does not have to be rebuilt from scratch.
    is_hidden = models.BooleanField(default=False)
    # Non-empty marks a PLACEHOLDER row standing in for a quick-filter that
    # the frontend defines in code (its `builtinTabs`). It carries `order`,
    # `is_hidden` and a label, and nothing else: `filters` stays empty and
    # the real definition keeps living in the frontend constant this key
    # matches.
    #
    # Why a row at all, when not having one is the whole point of a builtin:
    # the order is per-user, so it has nowhere else to live. And why the row
    # still refuses to carry the filters — i.e. why not just seed them like
    # any other factory tab: a builtin like "Hoy" or "Últimos 7 días"
    # resolves its dates when it renders, so a persisted `date_from` would
    # freeze it on the day it was written.
    builtin_key = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['view', 'order', 'created_at']
        indexes = [
            models.Index(fields=['user', 'view', 'order']),
        ]
        constraints = [
            # One placeholder per builtin per view: the seeding upserts on
            # this key, and a duplicate would give one chip two orders.
            models.UniqueConstraint(
                models.F('user'),
                models.F('view'),
                NullIf(models.F('builtin_key'), models.Value('')),
                name='uniq_saved_filter_tab_builtin_key',
            ),
        ]

    def __str__(self):
        return f'{self.user_id}/{self.view}/{self.name}'

# Project billing domain (identity/context only; existing financial engines stay authoritative).
from accounts.billing_models import (  # noqa: E402,F401
    BillingContextEvent, CollectionAccountContext, HostingEvidence,
    HostingEvidenceGroup, ProjectHosting, ProjectHostingAccountingSource,
)

# Ticket domain models; imports keep the public accounts.models surface stable.
from accounts.models_issue_reports import (  # noqa: E402,F401
    IssueAttachment, IssueContext, IssueEvent, IssueResponse,
)
