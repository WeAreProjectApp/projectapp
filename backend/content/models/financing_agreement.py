from accounts.retention import RetainedProjectModel
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from content.storage import get_private_storage


def financing_signed_document_path(instance, filename):
    """Keep signed agreements isolated by immutable agreement UUID."""

    extension = '.pdf' if str(filename).lower().endswith('.pdf') else ''
    return f'financing-agreements/{instance.uuid}/signed-agreement{extension}'


class FinancingAgreementTemplate(models.Model):
    """Versioned Spanish template used to create financing addenda."""

    name = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    content_markdown = models.TextField()
    is_default = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-version', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'version'],
                name='uniq_financing_template_name_version',
            ),
        ]

    def __str__(self):
        suffix = ' (predeterminada)' if self.is_default else ''
        return f'{self.name} v{self.version}{suffix}'

    def save(self, *args, **kwargs):
        if self.is_default:
            type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False,
            )
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True, is_active=True).first()


class FinancingAgreementNumberSequence(models.Model):
    """Locked yearly counter for human financing-agreement numbers."""

    year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Financing agreement number sequence'

    def __str__(self):
        return f'OFIN {self.year}: {self.last_number}'


class FinancingPolicyRevision(models.Model):
    """Immutable, auditable commercial policy used by financing agreements."""

    version = models.PositiveIntegerField(unique=True)
    minimum_project_value_cop = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('20000000.00'),
        validators=[MinValueValidator(0)],
    )
    maximum_project_value_cop = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('140000000.00'),
        validators=[MinValueValidator(0)],
    )
    financing_months = models.PositiveSmallIntegerField(default=12)
    maximum_financed_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('80.00'),
        validators=[MinValueValidator(0)],
    )
    late_hosting_increase_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.00'),
        validators=[MinValueValidator(0)],
    )
    installment_due_day_start = models.PositiveSmallIntegerField(default=1)
    installment_due_day_end = models.PositiveSmallIntegerField(default=5)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_policy_revisions_created',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        constraints = [
            models.CheckConstraint(
                condition=Q(minimum_project_value_cop__gte=0),
                name='financing_policy_minimum_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(maximum_project_value_cop__gte=F('minimum_project_value_cop')),
                name='financing_policy_maximum_gte_minimum',
            ),
            models.CheckConstraint(
                condition=Q(financing_months__gte=1) & Q(financing_months__lte=36),
                name='financing_policy_months_range',
            ),
            models.CheckConstraint(
                condition=(
                    Q(maximum_financed_percent__gt=0)
                    & Q(maximum_financed_percent__lte=100)
                ),
                name='financing_policy_financed_percent_range',
            ),
            models.CheckConstraint(
                condition=(
                    Q(late_hosting_increase_percent__gte=0)
                    & Q(late_hosting_increase_percent__lte=100)
                ),
                name='financing_policy_hosting_percent_range',
            ),
            models.CheckConstraint(
                condition=(
                    Q(installment_due_day_start__gte=1)
                    & Q(installment_due_day_start__lte=28)
                    & Q(installment_due_day_end__gte=F('installment_due_day_start'))
                    & Q(installment_due_day_end__lte=28)
                ),
                name='financing_policy_due_days_range',
            ),
        ]

    def __str__(self):
        return f'Política de financiación v{self.version}'

    @property
    def minimum_initial_payment_percent(self):
        return (Decimal('100.00') - self.maximum_financed_percent).quantize(
            Decimal('0.01'),
        )

    @classmethod
    def get_current(cls):
        return cls.objects.order_by('-version').first()


class FinancingAgreement(RetainedProjectModel, models.Model):
    """Administrative financing addendum and its immutable legal snapshots."""

    class Modality(models.TextChoices):
        FIVE_YEAR = 'five_year', 'Alianza a 5 años'
        THREE_YEAR = 'three_year', 'Alianza a 3 años'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        READY = 'ready', 'Listo para firma'
        ACTIVE = 'active', 'Activo'
        COMPLETED = 'completed', 'Completado'
        CANCELLED = 'cancelled', 'Cancelado'

    class HostingPeriod(models.TextChoices):
        MONTHLY = 'monthly', 'Mensual'
        QUARTERLY = 'quarterly', 'Trimestral'
        SEMIANNUAL = 'semiannual', 'Semestral'
        ANNUAL = 'annual', 'Anual'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text='Assigned atomically when the draft is marked ready.',
    )
    client = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.PROTECT,
        related_name='financing_agreements',
        limit_choices_to={'role': 'client'},
    )
    source_proposal = models.ForeignKey(
        'content.BusinessProposal',
        on_delete=models.SET_NULL,
        related_name='financing_agreements',
        null=True,
        blank=True,
    )
    source_project = models.ForeignKey('accounts.Project', on_delete=models.PROTECT, related_name='financing_agreements', null=True, blank=True)

    client_full_name = models.CharField(max_length=311)
    client_company = models.CharField(max_length=200, blank=True, default='')
    client_id_type = models.CharField(max_length=20, blank=True, default='')
    client_id_number = models.CharField(max_length=32, blank=True, default='')
    client_email = models.EmailField(blank=True, default='')
    client_phone = models.CharField(max_length=30, blank=True, default='')

    original_contract_reference = models.CharField(max_length=255)
    original_contract_date = models.DateField()
    project_name = models.CharField(max_length=255)
    financed_scope = models.TextField()

    modality = models.CharField(max_length=20, choices=Modality.choices)
    cycle_number = models.PositiveSmallIntegerField(default=1)
    previous_agreement = models.OneToOneField(
        'self',
        on_delete=models.PROTECT,
        related_name='second_cycle',
        null=True,
        blank=True,
    )
    policy_revision = models.ForeignKey(
        FinancingPolicyRevision,
        on_delete=models.PROTECT,
        related_name='agreements',
    )
    partnership_start_date = models.DateField()
    partnership_end_date = models.DateField()

    currency = models.CharField(
        max_length=3,
        choices=(('COP', 'COP'), ('USD', 'USD')),
        default='COP',
    )
    eligibility_exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='COP per USD snapshot used to evaluate the policy limits.',
    )
    total_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    initial_payment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    financed_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    hosting_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    hosting_period = models.CharField(
        max_length=20,
        choices=HostingPeriod.choices,
        default=HostingPeriod.MONTHLY,
    )
    installment_schedule = models.JSONField(default=list, blank=True)

    template = models.ForeignKey(
        FinancingAgreementTemplate,
        on_delete=models.PROTECT,
        related_name='agreements',
    )
    template_version = models.PositiveIntegerField(default=1)
    contract_markdown = models.TextField()
    resolved_contract_markdown = models.TextField(blank=True, default='')
    resolved_contract_sha256 = models.CharField(max_length=64, blank=True, default='')

    signed_document = models.FileField(
        upload_to=financing_signed_document_path,
        storage=get_private_storage,
        max_length=500,
        null=True,
        blank=True,
    )
    signed_document_sha256 = models.CharField(max_length=64, blank=True, default='')
    signed_document_size = models.PositiveBigIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    ready_at = models.DateTimeField(null=True, blank=True)
    ready_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_prepared',
        null=True,
        blank=True,
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_activated',
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_completed',
        null=True,
        blank=True,
    )
    completion_note = models.TextField(blank=True, default='')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_cancelled',
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(blank=True, default='')
    second_cycle_approved_at = models.DateTimeField(null=True, blank=True)
    second_cycle_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_second_cycles_approved',
        null=True,
        blank=True,
    )
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_archived',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_created',
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreements_updated',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['is_archived', 'status', '-created_at']),
            models.Index(fields=['client', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(cycle_number__in=(1, 2)),
                name='financing_cycle_one_or_two',
            ),
            models.CheckConstraint(
                condition=Q(initial_payment__lte=F('total_value')),
                name='financing_initial_not_above_total',
            ),
            models.CheckConstraint(
                condition=Q(cycle_number=1) | Q(modality='five_year'),
                name='financing_second_cycle_five_year_only',
            ),
        ]

    def __str__(self):
        return f'{self.number or "Borrador"} — {self.client_full_name}'

    @property
    def modality_years(self):
        return 5 if self.modality == self.Modality.FIVE_YEAR else 3

    @property
    def equivalent_total_cop(self):
        if self.currency == 'COP':
            return self.total_value
        if self.eligibility_exchange_rate is None:
            return None
        return (self.total_value * self.eligibility_exchange_rate).quantize(
            Decimal('0.01'),
        )


class FinancingAgreementEvent(models.Model):
    """Append-only audit entry for every financing agreement mutation."""

    agreement = models.ForeignKey(
        FinancingAgreement,
        on_delete=models.CASCADE,
        related_name='events',
    )
    event_type = models.CharField(max_length=50, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='financing_agreement_events',
        null=True,
        blank=True,
    )
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['agreement', '-created_at'])]

    def __str__(self):
        return f'{self.agreement_id}: {self.event_type}'
