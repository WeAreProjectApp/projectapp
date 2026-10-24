from content.models.editorial_text import EditorialTextModel
from decimal import Decimal

from django.db import models


class Nationality(models.TextChoices):
    COL = 'COL', 'Colombia'
    EXT = 'EXT', 'Extranjeros'
    USA = 'USA', 'Estados Unidos'


# Pricing currency implied by each nationality. EXT covers any country other
# than Colombia and USA and always quotes in USD by commercial decision.
CURRENCY_BY_NATIONALITY = {
    Nationality.COL: 'COP',
    Nationality.EXT: 'USD',
    Nationality.USA: 'USD',
}

# Settings field holding the base hourly rate for each nationality.
BASE_RATE_FIELD_BY_NATIONALITY = {
    Nationality.COL: 'base_rate_col',
    Nationality.EXT: 'base_rate_ext',
    Nationality.USA: 'base_rate_usa',
}


class HourPackage(EditorialTextModel, models.Model):
    """
    Catalog entry for a requirement package or a historical hour offer.

    Each package belongs to one nationality (COL/EXT/USA); the pricing
    currency is derived from it (COL→COP, EXT/USA→USD). Active packages
    seed the ``commercial_conditions`` section of newly created proposals
    matching the proposal's nationality. An empty requirement catalog does
    not invent capacity; historical hour sections retain their snapshots.
    """

    nationality = models.CharField(
        max_length=3,
        choices=Nationality.choices,
        default=Nationality.COL,
        db_index=True,
    )
    name_es = models.CharField(max_length=255, verbose_name='Name (Spanish)')
    name_en = models.CharField(max_length=255, verbose_name='Name (English)')
    note_es = models.TextField(blank=True, default='')
    note_en = models.TextField(blank=True, default='')
    # Old rows remain readable for historical proposals. New catalog writes
    # explicitly use requirements; never infer a conversion from hours.
    pricing_model = models.CharField(max_length=12, default='hours', choices=[
        ('hours', 'Historical hours'), ('requirements', 'Requirements'),
    ], db_index=True)
    xs_count = models.PositiveIntegerField(default=0)
    s_count = models.PositiveIntegerField(default=0)
    m_count = models.PositiveIntegerField(default=0)
    validity_months = models.PositiveIntegerField(default=12)
    hours = models.PositiveIntegerField(null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    discount_percent = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Manual sort order (lower first).')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nationality', 'order', 'pk']
        verbose_name = 'Requirement Package'
        verbose_name_plural = 'Requirement Packages'

    def __str__(self):
        if self.pricing_model == 'requirements':
            return f'{self.name_es} ({self.nationality}, {self.xs_count} XS / {self.s_count} S / {self.m_count} M)'
        return f'{self.name_es} ({self.nationality}, {self.hours}h)'

    @property
    def currency(self):
        return CURRENCY_BY_NATIONALITY[self.nationality]


class HourPackageSettings(models.Model):
    """
    Singleton storing requirement prices, market factors and panel preferences.

    Usage:
        settings = HourPackageSettings.load()
        settings.default_view_mode  # → 'table' | 'cards' | 'compare'
        settings.xs_price_cop       # → internal COP reference value for XS

    Legacy base-rate fields remain for historical integration compatibility.
    """

    class ViewMode(models.TextChoices):
        TABLE = 'table', 'Tabla'
        CARDS = 'cards', 'Tarjetas'
        COMPARE = 'compare', 'Comparativa'

    default_view_mode = models.CharField(
        max_length=10, choices=ViewMode.choices, default=ViewMode.TABLE,
    )

    xs_price_cop = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('50000'))
    s_price_cop = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('125000'))
    m_price_cop = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('360000'))
    foreign_multiplier = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal('1.4'))
    usa_multiplier = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal('1.8'))
    alliance_xs_count = models.PositiveIntegerField(default=4)
    alliance_s_count = models.PositiveIntegerField(default=2)
    alliance_m_count = models.PositiveIntegerField(default=1)

    # Base hourly rate per nationality. Defaults mirror the July 2026 ladder
    # in hour_package_service.DEFAULT_PACKAGES — keep both in lockstep.
    base_rate_col = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('30000'),
    )
    base_rate_ext = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('18'),
    )
    base_rate_usa = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('30'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Requirement package settings'
        verbose_name_plural = 'Requirement package settings'

    def __str__(self):
        return f'HourPackageSettings — vista {self.default_view_mode}'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Return the singleton instance, creating it if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
