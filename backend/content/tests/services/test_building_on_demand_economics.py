"""Pinned commercial economics and Decimal rounding at consumer boundaries."""

from math import isfinite

import pytest

from content.services import building_on_demand_program_service as service
from content.services.building_on_demand_content import BuildingOnDemandError

ECONOMIC_ROWS = [
    ('starter', 'monthly', 1, 1800000, 46291, 1753709, 31.9, 32, 96, 33, 32.7),
    ('starter', 'quarterly', 3, 1710000, 46291, 1663709, 30.2, 30, 96, 32, 31.1),
    ('starter', 'semiannual', 6, 1620000, 46291, 1573709, 28.6, 29, 96, 30, 29.5),
    ('starter', 'nine-month', 9, 1530000, 46291, 1483709, 27.0, 27, 96, 28, 27.8),
    ('business', 'monthly', 1, 4200000, 116501, 4083499, 74.2, 74, 192, 39, 76.4),
    ('business', 'quarterly', 3, 3780000, 116501, 3663499, 66.6, 67, 192, 35, 68.7),
    ('business', 'semiannual', 6, 3570000, 116501, 3453499, 62.8, 63, 192, 33, 64.9),
    ('business', 'nine-month', 9, 3360000, 116501, 3243499, 59.0, 59, 192, 31, 61.1),
    ('enterprise', 'monthly', 1, 9600000, 200991, 9399009, 170.9, 171, 288, 59, 174.5),
    ('enterprise', 'quarterly', 3, 8160000, 200991, 7959009, 144.7, 145, 288, 50, 148.4),
    ('enterprise', 'semiannual', 6, 7680000, 200991, 7479009, 136.0, 136, 288, 47, 139.6),
    ('enterprise', 'nine-month', 9, 7200000, 200991, 6999009, 127.3, 127, 288, 44, 130.9),
]
ROW_KEYS = (
    'tier', 'term', 'months', 'monthly_price', 'hosting_cost_monthly', 'net_monthly',
    'breakeven_hours', 'breakeven_hours_rounded', 'bag_hours', 'bag_share_percent',
    'breakeven_hours_without_hosting',
)
ECONOMIC_KEYS = {
    'currency', 'hour_cost', 'vat_percent', 'provider', 'reference_url', 'consulted_on', 'tiers', 'rows',
}


def _row(payload, tier, term):
    return next(row for row in payload['rows'] if row['tier'] == tier and row['term'] == term)


def _rounding_content(content, *, hour_cost=200000, renewal_monthly=3, vat_percent=50):
    content['offer']['tiers'][0]['monthly_price'] = 100005
    content['internal']['hour_cost'] = hour_cost
    content['internal']['vat_percent'] = vat_percent
    content['internal']['servers']['starter']['renewal_monthly'] = renewal_monthly
    return content


def test_economics_exposes_private_inputs_to_the_panel(building_on_demand_program):
    """Fails if the panel cannot identify the exact private cost assumptions."""
    payload = service.economics()

    assert set(payload) == ECONOMIC_KEYS
    assert payload['currency'] == 'COP'
    assert payload['hour_cost'] == 55000
    assert payload['vat_percent'] == 19
    assert payload['provider'] == 'Hostinger'
    assert payload['reference_url'] == 'https://www.hostinger.com/co/vps-servidor-web'
    assert payload['consulted_on'] == '2026-10-10'


@pytest.mark.parametrize('expected', ECONOMIC_ROWS, ids=lambda row: f'{row[0]}-{row[1]}')
def test_economics_matches_the_pinned_break_even_row(building_on_demand_program, expected):
    """Fails if a tier or term silently changes its commercial break-even math."""
    payload = service.economics()

    actual = _row(payload, expected[0], expected[1])

    assert actual == dict(zip(ROW_KEYS, expected))
    assert type(actual['breakeven_hours']) is float
    assert type(actual['breakeven_hours_without_hosting']) is float


@pytest.mark.parametrize('index,expected', [
    (0, {'id': 'starter', 'name': 'Starter', 'bag_hours': 96, 'plan': 'KVM 1',
         'promo_monthly': 19900, 'renewal_monthly': 38900, 'hosting_cost_monthly': 46291}),
    (1, {'id': 'business', 'name': 'Business', 'bag_hours': 192, 'plan': 'KVM 4',
         'promo_monthly': 38900, 'renewal_monthly': 97900, 'hosting_cost_monthly': 116501}),
    (2, {'id': 'enterprise', 'name': 'Enterprise', 'bag_hours': 288, 'plan': 'KVM 8',
         'promo_monthly': 77900, 'renewal_monthly': 168900, 'hosting_cost_monthly': 200991}),
])
def test_economics_uses_renewal_cost_for_the_tier(building_on_demand_program, index, expected):
    """Fails if profitability uses promotional hosting instead of renewal plus VAT."""
    payload = service.economics()

    assert payload['tiers'][index] == expected
    assert len(payload['rows']) == 12


def test_hosting_tax_rounds_half_up(building_on_demand_content):
    """Fails if a half-peso hosting tax rounds down through banker rounding."""
    content = _rounding_content(building_on_demand_content)

    actual = _row(service.economics(content), 'starter', 'monthly')

    assert actual['hosting_cost_monthly'] == 5
    assert actual['net_monthly'] == 100000


def test_whole_break_even_hours_round_half_up(building_on_demand_content):
    """Fails if exactly half an hour rounds down to zero executable hours."""
    content = _rounding_content(building_on_demand_content)

    actual = _row(service.economics(content), 'starter', 'monthly')

    assert actual['breakeven_hours'] == 0.5
    assert actual['breakeven_hours_rounded'] == 1


def test_decimal_break_even_hours_round_half_up(building_on_demand_content):
    """Fails if a quarter hour rounds down at the one-decimal display boundary."""
    content = _rounding_content(building_on_demand_content, hour_cost=400000)

    actual = _row(service.economics(content), 'starter', 'monthly')

    assert actual['breakeven_hours'] == 0.3
    assert actual['breakeven_hours_without_hosting'] == 0.3


def test_bag_share_uses_unrounded_break_even_hours(building_on_demand_content):
    """Fails if profitability shares are derived from already rounded display hours."""
    content = _rounding_content(building_on_demand_content, renewal_monthly=2005, vat_percent=0)
    content['offer']['days_per_week'] = 1
    content['offer']['weeks_per_month'] = 1
    content['offer']['tiers'][0]['daily_hours'] = 1

    actual = _row(service.economics(content), 'starter', 'monthly')

    assert actual['breakeven_hours'] == 0.5
    assert actual['bag_hours'] == 1
    assert actual['bag_share_percent'] == 49
    assert actual['breakeven_hours_rounded'] == 0


def test_discounted_monthly_price_rounds_half_up(building_on_demand_content):
    """Fails if half-peso discounts reduce the charged monthly total by one peso."""
    building_on_demand_content['offer']['tiers'][0]['monthly_price'] = 100001
    building_on_demand_content['offer']['tiers'][0]['discounts'] = {
        'quarterly': 50, 'semiannual': 51, 'nine-month': 52,
    }

    actual = _row(service.economics(building_on_demand_content), 'starter', 'quarterly')

    assert actual['monthly_price'] == 50001
    assert actual['months'] == 3


def test_explicit_economics_content_preserves_the_current_program(building_on_demand_content):
    """Fails if an economics preview publishes its private cost assumptions."""
    before = service.read_program()
    building_on_demand_content['internal']['hour_cost'] = 60000

    actual = service.economics(building_on_demand_content)

    assert actual['hour_cost'] == 60000
    assert service.read_program()['content'] == before['content']
    assert building_on_demand_content['internal']['hour_cost'] == 60000


def test_economics_revalidates_explicit_content(building_on_demand_content):
    """Fails if the economics reader computes using a missing hosting cost entry."""
    building_on_demand_content['internal']['servers'].pop('starter')

    with pytest.raises(BuildingOnDemandError) as error:
        service.economics(building_on_demand_content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details['path'] == 'internal.servers'


def test_economics_preserves_large_hosting_cost_precision(building_on_demand_seed_content):
    """Fails if valid large hosting costs overflow Decimal or lose a whole peso."""
    building_on_demand_seed_content['internal']['servers']['starter']['renewal_monthly'] = 10**30 + 1

    actual = _row(service.economics(building_on_demand_seed_content), 'starter', 'monthly')

    assert actual['hosting_cost_monthly'] == 1190000000000000000000000000001
    assert actual['net_monthly'] == -1189999999999999999999998200001
    assert actual['breakeven_hours_rounded'] == -21636363636363636363636331
    assert actual['bag_share_percent'] == -22537878787878787878787845
    assert isfinite(actual['breakeven_hours']) is True


def test_economics_rejects_unrepresentable_break_even_numbers(building_on_demand_seed_content):
    """Fails if an extreme hosting cost serializes nonfinite break-even JSON numbers."""
    building_on_demand_seed_content['internal']['servers']['starter']['renewal_monthly'] = 10**400

    with pytest.raises(BuildingOnDemandError) as error:
        service.economics(building_on_demand_seed_content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': 'internal.servers.starter.renewal_monthly'}
