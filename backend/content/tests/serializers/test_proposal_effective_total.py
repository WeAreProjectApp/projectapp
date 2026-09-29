"""Serializer compatibility for manually agreed proposal investment."""
from decimal import Decimal

import pytest

from content.serializers.proposal import ProposalDetailSerializer

pytestmark = pytest.mark.django_db


def test_effective_total_ignores_legacy_selected_modules(proposal):
    """Falla si una selección histórica vuelve a sumar porcentajes al total manual."""
    proposal.total_investment = Decimal('15000.00')
    proposal.selected_modules = ['module-legacy-crm']
    proposal.save(update_fields=['total_investment', 'selected_modules'])

    data = ProposalDetailSerializer(proposal, context={'is_admin': True}).data

    assert Decimal(data['effective_total_investment']) == Decimal('15000.00')


def test_discounted_investment_uses_migrated_snapshot(proposal):
    """Falla si serializar una propuesta migrada recalcula y pierde su descuento histórico."""
    proposal.total_investment = Decimal('1200.00')
    proposal.discount_percent = 10
    proposal.legacy_pricing_snapshot = {
        'original_investment': '1000.00',
        'total_investment': '1200.00',
        'discount_percent': 10,
        'currency': 'COP',
        'discounted_investment': '900.00',
    }
    proposal.save(update_fields=[
        'total_investment',
        'discount_percent',
        'legacy_pricing_snapshot',
    ])

    data = ProposalDetailSerializer(proposal, context={'is_admin': True}).data

    assert Decimal(data['discounted_investment']) == Decimal('900.00')
    assert Decimal(data['discount_original_investment']) == Decimal('1000.00')


def test_discount_reference_uses_edited_manual_total_after_snapshot_is_cleared(proposal):
    """Falla si una edición financiera conserva una referencia de descuento obsoleta."""
    proposal.total_investment = Decimal('1200.00')
    proposal.discount_percent = 10
    proposal.legacy_pricing_snapshot = {
        'original_investment': '1000.00',
        'total_investment': '1200.00',
        'discount_percent': 10,
        'currency': 'COP',
        'discounted_investment': '900.00',
    }
    proposal.save(update_fields=[
        'total_investment',
        'discount_percent',
        'legacy_pricing_snapshot',
    ])
    proposal.total_investment = Decimal('1300.00')
    proposal.save(update_fields=['total_investment'])

    data = ProposalDetailSerializer(proposal, context={'is_admin': True}).data

    assert proposal.legacy_pricing_snapshot == {}
    assert Decimal(data['discount_original_investment']) == Decimal('1300.00')
    assert Decimal(data['discounted_investment']) == Decimal('1170.00')
