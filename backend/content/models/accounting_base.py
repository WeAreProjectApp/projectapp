from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from content.models.history_tracked import HistoryTrackedModel


class AccountingRecordBase(HistoryTrackedModel):
    """
    Common plumbing shared by every accounting entity.

    `source_ref` is an idempotency key: `import:<hash>` for spreadsheet
    imports, `fake:<tag>` for fake data, empty for manual records.
    """

    notes = models.TextField(blank=True, default='')
    source_ref = models.CharField(
        max_length=64,
        blank=True,
        default='',
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Ledger(models.TextChoices):
    """Which accounting a record belongs to.

    The source spreadsheet interleaves two ledgers: the company one and
    each partner's personal one. Personal records belong 100% to their
    owner and never count toward company totals.
    """

    COMPANY = 'company', 'Empresa'
    GUSTAVO = 'gustavo', 'Personal Gustavo'
    CARLOS = 'carlos', 'Personal Carlos'


class PartnerSplitMixin(models.Model):
    """
    Total amount plus editable per-partner amounts.

    Amounts (not percentages) are the source of truth, mirroring the
    original spreadsheet. The 50/50 default is applied at serializer
    level so explicit zeros are respected. Whatever is not assigned to
    a partner belongs to the company pocket (`company_amount`).
    """

    Ledger = Ledger

    ledger = models.CharField(
        max_length=10,
        choices=Ledger.choices,
        default=Ledger.COMPANY,
        db_index=True,
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    gustavo_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    carlos_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )

    class Meta:
        abstract = True

    @property
    def company_amount(self):
        return self.total_amount - self.gustavo_amount - self.carlos_amount

    @property
    def partner_attribution(self):
        """Which party this record is effectively assigned to.

        Company-ledger records fully assigned to one partner are partner
        draws (money taken from the pocket for that partner); the pocket
        modal round-trips this value through its "Atribuir a" control.
        """
        if self.ledger in (Ledger.GUSTAVO, Ledger.CARLOS):
            return self.ledger
        if self.total_amount:
            if self.gustavo_amount == self.total_amount:
                return Ledger.GUSTAVO
            if self.carlos_amount == self.total_amount:
                return Ledger.CARLOS
        return Ledger.COMPANY

    def clean(self):
        super().clean()
        for field in ('total_amount', 'gustavo_amount', 'carlos_amount'):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValidationError(
                    {field: 'Los montos no pueden ser negativos.'}
                )
        if (
            self.total_amount is not None
            and self.gustavo_amount is not None
            and self.carlos_amount is not None
            and self.gustavo_amount + self.carlos_amount > self.total_amount
        ):
            raise ValidationError(
                'La suma de los montos de los socios no puede superar el monto total.'
            )
        personal_owner = {
            Ledger.GUSTAVO: ('gustavo_amount', 'carlos_amount'),
            Ledger.CARLOS: ('carlos_amount', 'gustavo_amount'),
        }.get(self.ledger)
        if personal_owner is not None and self.total_amount is not None:
            owner_field, other_field = personal_owner
            if (
                getattr(self, owner_field) != self.total_amount
                or getattr(self, other_field)
            ):
                raise ValidationError(
                    'Un movimiento personal debe asignarse 100% al socio dueño.'
                )


class VatBreakdownMixin(models.Model):
    """Nullable rate distinguishes unclassified history from an explicit 0%."""
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    vat_total_field = 'total_amount'

    class Meta:
        abstract = True

    @property
    def base_amount(self):
        from content.services.accounting_vat import vat_breakdown
        return vat_breakdown(getattr(self, self.vat_total_field), self.vat_rate)[0]

    @property
    def vat_amount(self):
        from content.services.accounting_vat import vat_breakdown
        return vat_breakdown(getattr(self, self.vat_total_field), self.vat_rate)[1]
