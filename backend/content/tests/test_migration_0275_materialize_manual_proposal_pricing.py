"""Regression coverage for materializing retired module percentage pricing."""
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import (
    BusinessProposal,
    ProposalChangeLog,
    ProposalDefaultConfig,
    ProposalSection,
)

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0275_materialize_manual_proposal_pricing')


def _legacy_functional_requirements():
    return {
        'groups': [],
        'additionalModules': [{
            'id': 'legacy-crm',
            'title': 'CRM legado',
            'is_calculator_module': True,
            'price_percent': 20,
        }],
    }


def _materialize_discounted_legacy_proposal():
    proposal = BusinessProposal.objects.create(
        title='Oferta anterior',
        client_name='Cliente histórico',
        total_investment=Decimal('1000.00'),
        discount_percent=10,
        selected_modules=['module-legacy-crm'],
        status='sent',
    )
    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type=ProposalChangeLog.ChangeType.CALCULATOR_CONFIRMED,
    )
    functional_requirements = ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS,
        title='Alcance',
        order=0,
        content_json={'groups': [], 'additionalModules': []},
    )
    investment = ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSection.SectionType.INVESTMENT,
        title='Inversión',
        order=1,
        content_json={
            'totalInvestment': '$1.000',
            'paymentOptions': [{'label': '40% al firmar', 'description': '$400 COP'}],
        },
    )
    defaults = ProposalDefaultConfig.objects.create(language='es', sections_json=[])

    ProposalSection.objects.filter(pk=functional_requirements.pk).update(
        content_json=_legacy_functional_requirements(),
    )
    ProposalDefaultConfig.objects.filter(pk=defaults.pk).update(
        sections_json=[{
            'section_type': 'functional_requirements',
            'content_json': _legacy_functional_requirements(),
        }],
    )

    migration.migrate_prices(apps, SimpleNamespace(connection=connection))

    proposal.refresh_from_db()
    functional_requirements.refresh_from_db()
    investment.refresh_from_db()
    defaults.refresh_from_db()
    return proposal, functional_requirements, investment, defaults


def test_forward_materializes_legacy_surcharge_with_discount_snapshot():
    """Falla si retirar porcentajes cambia el total o descuento histórico."""
    proposal, _functional_requirements, _investment, _defaults = (
        _materialize_discounted_legacy_proposal()
    )

    assert proposal.total_investment == Decimal('1200.00')
    assert proposal.legacy_pricing_snapshot == {
        'original_investment': '1000.00',
        'total_investment': '1200.00',
        'discount_percent': 10,
        'currency': 'COP',
        'discounted_investment': '900.00',
    }


def test_forward_materializes_legacy_investment_copy():
    """Falla si las cuotas históricas no reflejan el total materializado."""
    _proposal, _functional_requirements, investment, _defaults = (
        _materialize_discounted_legacy_proposal()
    )

    assert investment.content_json['totalInvestment'] == '$1.200'
    assert investment.content_json['paymentOptions'][0]['description'] == '$480 COP'


def test_forward_removes_legacy_percentages_from_sections_and_defaults():
    """Falla si quedan precios retirados en contenido que se copiará a propuestas nuevas."""
    _proposal, functional_requirements, _investment, defaults = (
        _materialize_discounted_legacy_proposal()
    )

    assert 'price_percent' not in functional_requirements.content_json['additionalModules'][0]
    assert functional_requirements.content_json['additionalModules'][0]['is_always_included'] is False
    assert 'price_percent' not in defaults.sections_json[0]['content_json']['additionalModules'][0]


@pytest.mark.parametrize(
    ('confirmed', 'selected_modules', 'groups', 'base_total', 'expected_total'),
    [
        (
            False,
            [],
            [{'id': 'default-off', 'is_calculator_module': True,
              'selected': False, 'default_selected': True, 'price_percent': 20}],
            Decimal('1000.00'),
            Decimal('1000.00'),
        ),
        (
            False,
            [],
            [{'id': 'default-on', 'is_calculator_module': True,
              'default_selected': True, 'price_percent': 20}],
            Decimal('1000.00'),
            Decimal('1200.00'),
        ),
        (
            False,
            [],
            [{'id': 'hidden', 'is_calculator_module': True, 'is_visible': False,
              'selected': True, 'price_percent': 20}],
            Decimal('1000.00'),
            Decimal('1000.00'),
        ),
        (
            True,
            [],
            [{'id': 'pinned', 'is_calculator_module': True,
              'selected': True, 'price_percent': 20}],
            Decimal('1000.00'),
            Decimal('1200.00'),
        ),
        (
            True,
            ['module-client-choice'],
            [
                {'id': 'client-choice', 'is_calculator_module': True,
                 'selected': False, 'price_percent': 20},
                {'id': 'admin-pinned', 'is_calculator_module': True,
                 'selected': True, 'price_percent': 30},
            ],
            Decimal('1000.00'),
            Decimal('1500.00'),
        ),
        (
            False,
            [],
            [
                {'id': 'duplicate', 'is_calculator_module': True,
                 'selected': True, 'price_percent': 10},
                {'id': 'duplicate', 'is_calculator_module': True,
                 'selected': True, 'price_percent': 50},
            ],
            Decimal('1003.00'),
            Decimal('1505.00'),
        ),
    ],
)
def test_forward_preserves_legacy_selection_rules(
    confirmed,
    selected_modules,
    groups,
    base_total,
    expected_total,
):
    """Falla si materializar precios cambia la regla histórica de selección."""
    proposal = BusinessProposal.objects.create(
        title='Regla histórica',
        client_name='Cliente',
        status='sent',
        total_investment=base_total,
        selected_modules=selected_modules,
    )
    if confirmed:
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.CALCULATOR_CONFIRMED,
        )
    section = ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS,
        title='Alcance',
        order=0,
        content_json={'groups': [], 'additionalModules': []},
    )
    ProposalSection.objects.filter(pk=section.pk).update(content_json={
        'groups': [], 'additionalModules': groups,
    })

    migration.migrate_prices(apps, SimpleNamespace(connection=connection))

    proposal.refresh_from_db()
    assert proposal.total_investment == expected_total
