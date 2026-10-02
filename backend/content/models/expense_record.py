from django.db import models

from .accounting_base import AccountingRecordBase, PartnerSplitMixin, VatBreakdownMixin
from .history_tracked import HistoryQuerySet


class ExpenseRecordQuerySet(HistoryQuerySet):
    """Splits ordinary spending from income deductions."""

    def operational(self):
        """Ordinary expenses — everything but income deductions."""
        return self.filter(deduction_type='')

    def deductions(self):
        """Gateway/bank fees and withholdings discounted from an income."""
        return self.exclude(deduction_type='')


class ExpenseRecord(VatBreakdownMixin, PartnerSplitMixin, AccountingRecordBase):
    """
    Expense entry of the accounting module.

    Partner amounts represent each partner's share of the expense.
    Every expense draws from money already in the pocket, so new expenses
    keep a linked pocket OUT movement in sync (see accounting_service);
    records created before the linkage existed stay unlinked.

    ``deduction_type`` marks the rows that are a discount taken out of an
    income before it landed (a Wompi fee, a bank fee, a withholding). The
    expected income keeps its GROSS total, so a deduction reduces utility
    like any other expense and additionally counts as payment credit toward
    its ``source_income`` (liquid children + linked deductions must add up
    to the parent's gross total for it to read as paid). It never touches
    the pocket: that money never entered the account.
    """

    class Category(models.TextChoices):
        BUSINESS = 'business', 'Negocio'
        PERSONAL = 'personal', 'Personal'

    class DeductionType(models.TextChoices):
        GATEWAY_FEE = 'gateway_fee', 'Comisión plataforma de pago'
        BANK_FEE = 'bank_fee', 'Comisión bancaria'
        WITHHOLDING = 'withholding', 'Retención en la fuente'
        OTHER = 'other', 'Otro'

    concept = models.CharField(max_length=255)
    # Month granularity by default (serializer accepts "YYYY-MM" → day 1);
    # a day other than 1 records the exact payment date when it is known.
    period_date = models.DateField()
    category = models.CharField(
        max_length=10,
        choices=Category.choices,
        default=Category.BUSINESS,
    )
    # Blank for ordinary expenses; set only by the income settlement flow.
    # Its presence IS the "this is an income deduction" flag — no extra boolean.
    deduction_type = models.CharField(
        max_length=20,
        choices=DeductionType.choices,
        blank=True,
        default='',
    )
    # The expected income this deduction was discounted from. Load-bearing
    # for payment credit: paid_amount sums liquid children + linked
    # deductions, so an income settled with a fee still reads as paid.
    source_income = models.ForeignKey(
        'IncomeRecord',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='deduction_records',
        limit_choices_to={'kind': 'expected'},
    )
    # Auto-managed pocket OUT movement kept in sync by accounting_service.
    pocket_movement = models.OneToOneField(
        'PocketMovement',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='expense_record',
    )

    objects = ExpenseRecordQuerySet.as_manager()

    class Meta:
        ordering = ['-period_date', '-created_at']
        indexes = [
            models.Index(fields=['period_date']),
        ]

    def __str__(self):
        return f'{self.concept} ({self.period_date:%Y-%m})'
