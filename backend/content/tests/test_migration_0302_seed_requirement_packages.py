"""Regression tests for preserving hour offers while seeding size packages."""
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import (
    BusinessProposal,
    ContractTemplate,
    ContractTemplateVersion,
    HourPackage,
    ProposalDefaultConfig,
    ProposalSection,
)
from content.services.proposal_service import ProposalService

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0302_seed_requirement_packages')


def _hour_package(name, hours, order):
    return HourPackage.objects.create(
        nationality='COL', pricing_model='hours', name_es=name, name_en=name,
        hours=hours, hourly_rate=30000, discount_percent=10, order=order, is_active=True,
    )


def test_migration_freezes_effective_auto_hours_but_preserves_manual_offer():
    """Fails if the catalog migration invents sizes for old proposals or overwrites manual terms."""
    HourPackage.objects.all().delete()
    agile = _hour_package('Ágil histórico', 20, 1)
    pro = _hour_package('Pro histórico', 60, 2)
    auto = BusinessProposal.objects.create(title='Auto', client_name='Cliente', nationality='COL', language='es')
    manual = BusinessProposal.objects.create(title='Manual', client_name='Cliente', nationality='COL', language='es')
    auto_section = ProposalSection.objects.create(
        proposal=auto, section_type='commercial_conditions', title='Condiciones', order=1,
        content_json={'hourPackagesMode': 'auto'},
    )
    manual_section = ProposalSection.objects.create(
        proposal=manual, section_type='commercial_conditions', title='Condiciones', order=1,
        content_json={'hourPackagesMode': 'manual', 'packages': [{'name': 'Pacto manual', 'hours': 7}]},
    )

    migration.seed(apps, SimpleNamespace(connection=connection))

    auto_section.refresh_from_db()
    manual_section.refresh_from_db()
    assert auto_section.content_json['packages'] == [
        {'id': agile.pk, 'name': 'Ágil histórico', 'note': '', 'hours': 20, 'hourlyRate': 30000.0, 'discountPercent': 10},
        {'id': pro.pk, 'name': 'Pro histórico', 'note': '', 'hours': 60, 'hourlyRate': 30000.0, 'discountPercent': 10},
    ]
    assert auto_section.content_json['pricingModel'] == 'hours'
    assert auto_section.content_json['packagesFrozen'] is True
    assert manual_section.content_json['packages'] == [{'name': 'Pacto manual', 'hours': 7}]
    assert manual_section.content_json['pricingModel'] == 'hours'
    assert not HourPackage.objects.filter(pricing_model='hours', is_active=True).exists()
    assert HourPackage.objects.filter(pricing_model='requirements', is_active=True).count() == 9


def test_migration_versions_only_contract_text_that_changes():
    """Fails if package wording mutates old contract revisions or creates revisions for unchanged text."""
    template = ContractTemplate.objects.create(
        name='Base', content_markdown='Incluye paquetes de horas para esfuerzos bajos o medio-bajos.',
        product_content_markdown='Producto sin referencia comercial.', service_content_markdown='',
    )
    original = ContractTemplateVersion.objects.create(
        template=template, variant='combined', version=1, markdown=template.content_markdown,
        author_label='Sistema', change_note='Versión previa',
    )

    migration.seed(apps, SimpleNamespace(connection=connection))

    template.refresh_from_db()
    versions = ContractTemplateVersion.objects.filter(template=template, variant='combined').order_by('version')
    assert versions.count() == 2
    assert versions.first().pk == original.pk
    assert versions.first().markdown == 'Incluye paquetes de horas para esfuerzos bajos o medio-bajos.'
    assert versions.last().markdown == 'Incluye paquetes de requerimientos XS, S y M para tallas XS, S o M.'
    assert ContractTemplateVersion.objects.filter(template=template, variant='product').count() == 0


@pytest.mark.parametrize('language', ['es', 'en'])
def test_migration_replaces_saved_hour_defaults_before_new_proposals_read_them(language):
    """Fails if a DB-backed default configuration keeps creating new proposals with hours."""
    ProposalDefaultConfig.objects.create(
        language=language,
        sections_json=[
            {
                'section_type': 'greeting', 'title': 'Saludo', 'order': 0,
                'content_json': {'title': 'Texto que no cambia'},
            },
            {
                'section_type': 'commercial_conditions', 'title': 'Condiciones', 'order': 1,
                'content_json': {
                    'pricingModel': 'hours', 'hourlyRate': 90000,
                    'packages': [{'name': 'Bolsa anterior', 'hours': 20}],
                },
            },
        ],
    )

    migration.seed(apps, SimpleNamespace(connection=connection))

    defaults = ProposalService.get_default_sections(language)
    commercial = next(row['content_json'] for row in defaults if row['section_type'] == 'commercial_conditions')
    greeting = next(row['content_json'] for row in defaults if row['section_type'] == 'greeting')
    assert commercial['pricingModel'] == 'requirements'
    assert 'hourlyRate' not in commercial
    assert commercial['packages'] == []
    assert greeting == {'title': 'Texto que no cambia'}
