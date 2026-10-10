from accounts.retention import RetainedProjectModel
from django.db import models
from django.db.models import Q

from .accounting_base import AccountingRecordBase, PartnerSplitMixin, VatBreakdownMixin
from .recurring_payment import RecurringPayment


class IncomeRecord(RetainedProjectModel, VatBreakdownMixin, PartnerSplitMixin, AccountingRecordBase):
    """
    Income entry of the accounting module.

    A single model covers expected income (projection), liquid income
    (actually received) and lost income (written off): they share the same
    shape and the core dashboard question — expected vs liquid difference —
    becomes a single-table aggregate. A liquid record may point to the
    expected record it fulfills via `expected_income`.

    Every aggregate filters `kind` explicitly, so `LOST` rows drop out of
    the projection and the utility without any of them having to know the
    kind exists.
    """

    class Kind(models.TextChoices):
        EXPECTED = 'expected', 'Esperado'
        LIQUID = 'liquid', 'Líquido'
        LOST = 'lost', 'Perdido'
        CANCELLED = 'cancelled', 'Cancelado'

    class Destination(models.TextChoices):
        PARTNERS = 'partners', 'Socios'
        POCKET = 'pocket', 'Bolsillo ProjectApp'

    class Origin(models.TextChoices):
        DEVELOPMENT = 'development', 'Desarrollo'
        HOSTING = 'hosting', 'Hosting'
        DIAGNOSTIC = 'diagnostic', 'Diagnóstico'
        OTHER = 'other', 'Otro'

    class CollectionConfidence(models.TextChoices):
        HIGH = 'high', 'Cobro muy probable'
        MEDIUM = 'medium', 'Cobro incierto (50/50)'
        LOW = 'low', 'Alto riesgo de pérdida'

    concept = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # Optional on purpose: nearly every income has a client behind it, but a
    # refund or a financial yield may legitimately have none, and requiring
    # one would block the entry. PROTECT mirrors proposals and diagnostics —
    # a client with incomes cannot be deleted until they are resolved.
    client = models.ForeignKey(
        'accounts.UserProfile',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='income_records',
        limit_choices_to={'role': 'client'},
    )
    # The project the income belongs to. Optional by nature, not by
    # tolerance: a cobro por diagnóstico happens before any project exists,
    # and a refund or a financial yield never has one. SET_NULL — unlike
    # `client`, which is PROTECT — because the money is permanent and the
    # project is a label on it: losing the label must never block deleting a
    # project, and `delete_fake_data` deletes projects BEFORE the accounting
    # sweep, so PROTECT here would break the fake-data cycle outright.
    project = models.ForeignKey('accounts.Project', null=True, blank=True, on_delete=models.PROTECT, related_name='income_records')
    # Business line. Blank means "sin clasificar" (records predating the
    # field); hosting incomes rely on it because hosting clients are stored
    # as plain text and often have no platform profile to link to.
    origin = models.CharField(
        max_length=20, choices=Origin.choices, blank=True, default='',
    )
    # Manual forecast maintained by the operators. Selection and confidence
    # are intentionally separate: an income may be shortlisted before the
    # team has enough context to classify its likelihood. Removing it from
    # the shortlist preserves the last classification as historical context.
    is_receivable_candidate = models.BooleanField(default=False)
    collection_confidence = models.CharField(
        max_length=10,
        choices=CollectionConfidence.choices,
        blank=True,
        default='',
    )
    # When the money is expected (or received), independently of what service
    # window the charge covers. Month granularity by default (serializer
    # accepts "YYYY-MM" → day 1);
    # a day other than 1 records the exact payment date when it is known.
    period_date = models.DateField()
    # The service window a hosting income covers — only origin=hosting carries
    # it (the write serializer enforces both directions, except for the
    # records a settlement DERIVES from one: the payment and the rescheduled
    # balance inherit the origin but not the window, which stays on the
    # expected record that was billed). `period_end` is INCLUSIVE: start +
    # cadence months − 1 day, so the next cycle starts the day after it. For
    # hosting creates, `period_date` defaults to `period_start` only when
    # omitted. Window edits keep an independent expected-payment date and
    # move it with the start only if the stored date already followed it.
    # Reminders, ordering, KPIs and filters use that expected-payment date.
    # Cadence reuses the recurring-payments catalog rather than growing a third one.
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    period_cadence = models.CharField(
        max_length=20,
        choices=RecurringPayment.Frequency.choices,
        blank=True,
        default='',
    )
    destination = models.CharField(
        max_length=10,
        choices=Destination.choices,
        default=Destination.PARTNERS,
    )
    expected_income = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='liquid_records',
        limit_choices_to={'kind': 'expected'},
    )
    # Auto-managed by accounting_service when kind=liquid and destination=pocket.
    # A ForeignKey (not OneToOne) since the abono flow: one pocket movement may
    # cover several expected incomes, materialized as N liquid children sharing
    # the same movement — each child's total_amount IS the per-income allocation.
    pocket_movement = models.ForeignKey(
        'PocketMovement',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='income_records',
    )

    # Payment calendar: an expected income is announced 15 and 7 days before
    # `period_date`, again on the day itself, and then every week or fortnight
    # (see AccountingSettings.overdue_reminder_frequency) until it is collected.
    # Muting silences one income on its own, for the cases where the delay is
    # already known and the reminder is only noise. `reminders_muted_until`
    # empty while muted means indefinitely; a date resumes the notices by
    # itself, so nothing gets silenced and forgotten.
    reminders_muted = models.BooleanField(default=False)
    reminders_muted_until = models.DateField(null=True, blank=True)
    # Cadence state, not user settings: `reminder_target_date` snapshots the
    # period_date the cadence is armed against, so moving the expected date
    # re-arms it automatically on the next daily run.
    reminder_target_date = models.DateField(null=True, blank=True)
    reminder_last_sent_at = models.DateField(null=True, blank=True)
    reminder_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-period_date', '-created_at']
        indexes = [
            models.Index(fields=['kind', 'period_date']),
            models.Index(fields=['client', 'period_date']),
            models.Index(fields=['project', 'period_date']),
            models.Index(fields=[
                'ledger', 'kind', 'is_receivable_candidate',
                'collection_confidence',
            ], name='income_receivable_lookup_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(is_receivable_candidate=False)
                    | Q(kind='expected', ledger='company')
                ),
                name='income_candidate_expected_company',
            ),
        ]

    def __str__(self):
        return f'{self.concept} ({self.get_kind_display()} — {self.period_date:%Y-%m})'
