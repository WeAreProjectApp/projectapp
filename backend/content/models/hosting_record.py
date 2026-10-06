from accounts.retention import RetainedProjectModel
from decimal import Decimal

from django.db import models

from .accounting_base import AccountingRecordBase, VatBreakdownMixin


class HostingRecord(RetainedProjectModel, VatBreakdownMixin, AccountingRecordBase):
    """
    Client hosting subscription registry (accounting view).

    Named HostingRecord to avoid confusion with accounts.HostingSubscription
    (Wompi-billed platform hosting). Hosting income itself is registered as
    IncomeRecord rows; this table tracks the per-client contract parameters.
    """

    vat_total_field = 'payment_per_cycle'

    class Modality(models.TextChoices):
        QUARTERLY = 'quarterly', 'Trimestral'
        SEMIANNUAL = 'semiannual', 'Semestral'
        NINE_MONTH = 'nine_month', 'Cada 9 meses'

    LEGACY_MONTHLY = 'monthly'
    LEGACY_ANNUAL = 'annual'

    MODALITY_MONTHS = {
        LEGACY_MONTHLY: 1,
        Modality.QUARTERLY: 3,
        Modality.SEMIANNUAL: 6,
        Modality.NINE_MONTH: 9,
        LEGACY_ANNUAL: 12,
    }

    MODALITY_LABELS = dict(Modality.choices) | {
        LEGACY_MONTHLY: 'Mensual (histórico)',
        LEGACY_ANNUAL: 'Anual (histórico)',
    }

    # The client the hosting belongs to. Nullable at the DB level only so
    # records created before the relation existed can still be opened and
    # saved while they are completed; the write serializer requires it on
    # create. PROTECT mirrors proposals, diagnostics and incomes.
    client = models.ForeignKey(
        'accounts.UserProfile',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='hosting_records',
        limit_choices_to={'role': 'client'},
    )
    # The project this hosting serves. The house convention crammed it into
    # `client_name` as `Persona - Marca` ("German - Kore"); this is the half
    # that was never a client. SET_NULL for the same reason as on incomes:
    # the project is a label, and `delete_fake_data` deletes projects before
    # the accounting sweep.
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='hosting_records')
    # Billing snapshot: what the cuenta de cobro prints and mails. Filled
    # from the linked client and editable afterwards, because the billing
    # contact may legitimately differ from the account holder. The FK above
    # is the source of truth for grouping and filtering.
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField(blank=True, default='')
    client_contact_name = models.CharField(max_length=255, blank=True, default='')
    client_identification = models.CharField(max_length=64, blank=True, default='')
    domain_url = models.CharField(max_length=255, blank=True, default='')
    monthly_value = models.DecimalField(max_digits=14, decimal_places=2)
    payment_modality = models.CharField(
        max_length=12,
        choices=Modality.choices,
        default=Modality.QUARTERLY,
    )
    benefit = models.CharField(max_length=255, blank=True, default='')
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    cycles_count = models.PositiveIntegerField(default=0)
    payment_per_cycle = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    total_paid = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Expiry-notice cadence state (system fields, managed by
    # hosting_expiry_service — not user settings, not audited).
    # `expiry_notice_target` snapshots the valid_to the cadence is armed
    # against: when it differs from the live valid_to (renewal/correction)
    # the daily task re-arms automatically.
    expiry_notice_target = models.DateField(null=True, blank=True)
    expiry_notice_last_sent_at = models.DateField(null=True, blank=True)
    expiry_notice_count = models.PositiveSmallIntegerField(default=0)
    # Set when the cuenta de cobro is sent to the client; silences the
    # cadence for the current target period.
    billing_requested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Two keys now that the project left `client_name`: a client with
        # more than one hosting used to be ordered by the project hiding
        # inside the string, and on the client half alone the tie would be
        # DB-arbitrary — the list and the export would shuffle per request.
        # The second key traverses the relation (`project_name` is a property
        # now, and Meta.ordering only takes real fields and lookups).
        ordering = ['client_name', 'project__name']
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['project']),
        ]

    @property
    def billing_email(self):
        """Where the cuenta de cobro actually goes.

        The hosting's own address is an override for a billing contact that
        differs from the account holder; with none, the linked client's
        address is used. Placeholder addresses never count — they cannot
        receive mail. An empty result means the hosting cannot be billed yet.
        """
        override = (self.client_email or '').strip()
        if override:
            return override
        if not self.client_id:
            return ''
        from accounts.models import UserProfile

        email = (self.client.user.email or '').strip()
        if email and not email.endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN):
            return email
        return ''

    @property
    def project_name(self):
        """The linked project's name, or '' — same convention the income
        serializer follows (`source='project.name'`)."""
        return self.project.name if self.project_id else ''

    @classmethod
    def modality_label(cls, value):
        return cls.MODALITY_LABELS.get(value, value)

    @property
    def payment_modality_label(self):
        return self.modality_label(self.payment_modality)

    @property
    def display_label(self):
        """Client and project rejoined, for the screens that need to
        recognise the row at a glance (expiry notices, origin labels).

        The em dash is deliberate: `client_name` splits on ' - ', so
        rejoining with the same separator would make the label look like a
        value that still needs splitting.
        """
        project = self.project_name
        if self.client_name and project:
            return f'{self.client_name} — {project}'
        return self.client_name or project or self.domain_url

    def __str__(self):
        return f'{self.client_name} — {self.domain_url or "(sin dominio)"}'
