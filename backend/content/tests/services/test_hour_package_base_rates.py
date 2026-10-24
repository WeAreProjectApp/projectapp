"""Tests for base-rate propagation from HourPackageSettings to the catalog."""
from decimal import Decimal

import pytest

from content.models import HourPackage, HourPackageSettings
from content.services.hour_package_service import (
    apply_base_rates_to_catalog,
    restore_default_packages,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def ext_catalog(db):
    # Start from a clean EXT catalog — migrations seed a default ladder.
    HourPackage.objects.filter(nationality='EXT').delete()
    active = HourPackage.objects.create(
        nationality='EXT', name_es='Hora Puntual', name_en='Single Hour',
        hours=1, hourly_rate=18, discount_percent=0, order=1,
    )
    inactive = HourPackage.objects.create(
        nationality='EXT', name_es='Paquete Ágil', name_en='Agile Pack',
        hours=20, hourly_rate=18, discount_percent=10, order=2,
        is_active=False,
    )
    return active, inactive


class TestApplyBaseRatesToCatalog:
    def test_updates_all_rows_including_inactive(self, ext_catalog):
        counts = apply_base_rates_to_catalog({'EXT': Decimal('25')})
        assert counts == {'EXT': 2}
        rates = set(
            HourPackage.objects.filter(nationality='EXT')
            .values_list('hourly_rate', flat=True)
        )
        assert rates == {Decimal('25')}

    def test_leaves_other_nationalities_untouched(self, ext_catalog):
        col_rates_before = list(
            HourPackage.objects.filter(nationality='COL')
            .values_list('hourly_rate', flat=True)
        )
        apply_base_rates_to_catalog({'EXT': Decimal('25')})
        col_rates_after = list(
            HourPackage.objects.filter(nationality='COL')
            .values_list('hourly_rate', flat=True)
        )
        assert col_rates_after == col_rates_before

    def test_empty_dict_is_noop(self, ext_catalog):
        assert apply_base_rates_to_catalog({}) == {}
        assert set(
            HourPackage.objects.filter(nationality='EXT')
            .values_list('hourly_rate', flat=True)
        ) == {Decimal('18')}

    def test_updates_updated_at(self, ext_catalog):
        active, _ = ext_catalog
        before = active.updated_at
        apply_base_rates_to_catalog({'EXT': Decimal('25')})
        active.refresh_from_db()
        assert active.updated_at > before


class TestSettingsBaseRates:
    def test_load_carries_defaults(self):
        settings = HourPackageSettings.load()
        assert settings.base_rate_col == Decimal('30000')
        assert settings.base_rate_ext == Decimal('18')
        assert settings.base_rate_usa == Decimal('30')

    def test_restore_defaults_preserves_legacy_base_rate_configuration(self):
        """Fails if restoring requirement tiers silently rewrites a saved rate setting."""
        settings = HourPackageSettings.load()
        settings.base_rate_col = Decimal('55000')
        settings.save()
        restore_default_packages('COL')
        settings.refresh_from_db()
        assert settings.base_rate_col == Decimal('55000')
