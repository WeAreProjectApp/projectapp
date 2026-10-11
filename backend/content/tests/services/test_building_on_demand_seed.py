"""Deployment seed, repeatable setup and safe rollback of program history."""
from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from content.models import BuildingOnDemandProgram, BuildingOnDemandProgramRevision, McpConnector, McpCredential
from content.services.building_on_demand_content import validate_content

pytestmark = pytest.mark.django_db
seed_migration = import_module('content.migrations.0291_building_on_demand_program')


def test_seeded_program_passes_validation(building_on_demand_program):
    """Fails if the real migration seed cannot be consumed by the current spec."""
    revision = building_on_demand_program.current_revision

    content = validate_content(revision.content)

    assert content == revision.content
    assert content['es']['hero']['positioning'] == 'Una suscripción de IA te da capacidad de producción. Una célula te da criterio.'
    assert content['en']['hero']['positioning'] == 'An AI subscription gives you production capacity. A cell gives you judgment.'


@pytest.mark.parametrize(('section', 'expected'), [
    ('offer', {
        'currency': 'COP', 'prices_include_vat': False, 'days_per_week': 6, 'weeks_per_month': 4,
        'terms': [
            {'id': 'monthly', 'months': 1}, {'id': 'quarterly', 'months': 3},
            {'id': 'semiannual', 'months': 6}, {'id': 'nine-month', 'months': 9},
        ],
        'tiers': [
            {
                'id': 'starter', 'monthly_price': 1800000, 'daily_hours': 4, 'recommended': False,
                'discounts': {'quarterly': 5, 'semiannual': 10, 'nine-month': 15},
                'server': {'vcpu': 1, 'ram_gb': 4, 'disk_gb': 50, 'transfer_tb': 4},
            },
            {
                'id': 'business', 'monthly_price': 4200000, 'daily_hours': 8, 'recommended': True,
                'discounts': {'quarterly': 10, 'semiannual': 15, 'nine-month': 20},
                'server': {'vcpu': 4, 'ram_gb': 16, 'disk_gb': 200, 'transfer_tb': 16},
            },
            {
                'id': 'enterprise', 'monthly_price': 9600000, 'daily_hours': 12, 'recommended': False,
                'discounts': {'quarterly': 15, 'semiannual': 20, 'nine-month': 25},
                'server': {'vcpu': 8, 'ram_gb': 32, 'disk_gb': 400, 'transfer_tb': 32},
            },
        ],
        'estimator': {
            'sizes': [
                {'id': 'xs', 'hours_min': 2, 'hours_max': 7},
                {'id': 's', 'hours_min': 7, 'hours_max': 20},
                {'id': 'm', 'hours_min': 20, 'hours_max': 50},
                {'id': 'l', 'hours_min': 55, 'hours_max': 90},
            ],
            'tasks': [
                {'id': 'requirements-session', 'size': 's', 'min_tier': 'business'},
                {'id': 'screen-design', 'size': 's', 'min_tier': 'business'},
                {'id': 'small-change', 'size': 'xs', 'min_tier': 'starter'},
                {'id': 'component', 'size': 's', 'min_tier': 'starter'},
                {'id': 'feature', 'size': 'm', 'min_tier': 'starter'},
                {'id': 'large-feature', 'size': 'l', 'min_tier': 'starter'},
                {'id': 'architecture-review', 'size': 'm', 'min_tier': 'business'},
                {'id': 'production-deploy', 'size': 'xs', 'min_tier': 'business'},
                {'id': 'continuous-devops', 'size': 'm', 'min_tier': 'enterprise'},
            ],
        },
    }),
    ('internal', {
        'hour_cost': 55000, 'vat_percent': 19, 'provider': 'Hostinger',
        'reference_url': 'https://www.hostinger.com/co/vps-servidor-web', 'consulted_on': '2026-10-10',
        'servers': {
            'starter': {'plan': 'KVM 1', 'promo_monthly': 19900, 'renewal_monthly': 38900},
            'business': {'plan': 'KVM 4', 'promo_monthly': 38900, 'renewal_monthly': 97900},
            'enterprise': {'plan': 'KVM 8', 'promo_monthly': 77900, 'renewal_monthly': 168900},
        },
    }),
])
def test_seeded_numbers_match_specification(building_on_demand_content, section, expected):
    """Fails if deployed numeric inputs drift from the product specification."""
    actual = building_on_demand_content[section]

    assert actual == expected


def test_seed_records_initial_provenance(building_on_demand_program):
    """Fails if deployment leaves an unauditable initial program revision."""
    revision = building_on_demand_program.current_revision

    assert revision.version == 1
    assert revision.author_label == 'Sistema'
    assert revision.change_note == 'Versión inicial de Building on Demand (PA-177).'
    assert revision.author_id is None
    assert revision.credential_id is None
    assert revision.restored_from_id is None


def test_seeded_connector_starts_inactive():
    """Fails if deployment exposes Building on Demand before the MCP wave."""
    connector = McpConnector.objects.get(slug='building-on-demand')

    assert connector.name == 'Building on Demand'
    assert connector.is_active is False
    assert connector.credentials.count() == 0


def test_seed_reentry_preserves_published_content(building_on_demand_program, building_on_demand_content):
    """Fails if rerunning data setup overwrites an already published program."""
    building_on_demand_content['es']['hero']['title'] = 'Una célula para tus siguientes prioridades'
    revision = BuildingOnDemandProgramRevision.objects.create(
        version=2, content=building_on_demand_content, change_note='Nueva presentación.',
    )
    BuildingOnDemandProgram.objects.filter(pk=1).update(current_revision=revision)

    seed_migration.seed_program(apps, SimpleNamespace(connection=connection))

    current = BuildingOnDemandProgram.load().current_revision
    assert current.pk == revision.pk
    assert current.content == building_on_demand_content
    assert BuildingOnDemandProgramRevision.objects.count() == 2


def test_seed_reentry_preserves_connector_activation():
    """Fails if repeatable deployment unexpectedly disables an existing connector."""
    connector = McpConnector.objects.get(slug='building-on-demand')
    connector.is_active = True
    connector.save(update_fields=['is_active'])

    seed_migration.seed_program(apps, SimpleNamespace(connection=connection))

    connector.refresh_from_db()
    assert connector.is_active is True
    assert McpConnector.objects.filter(slug='building-on-demand').count() == 1


def test_reverse_seed_removes_unused_connector(building_on_demand_program):
    """Fails if rollback leaves an unused connector or presentation records."""
    connector_id = McpConnector.objects.get(slug='building-on-demand').pk

    seed_migration.reverse_seed(apps, SimpleNamespace(connection=connection))

    assert McpConnector.objects.filter(pk=connector_id).exists() is False
    assert BuildingOnDemandProgram.objects.count() == 0
    assert BuildingOnDemandProgramRevision.objects.count() == 0


def test_reverse_seed_retains_connector_credentials(building_on_demand_program):
    """Fails if rollback destroys credentials belonging to a configured connector."""
    connector = McpConnector.objects.get(slug='building-on-demand')
    credential = McpCredential.objects.create(
        connector=connector, label='Migration safety', token_hash='1' * 64,
        token_prefix='seedtest',
    )

    seed_migration.reverse_seed(apps, SimpleNamespace(connection=connection))

    assert McpConnector.objects.get(pk=connector.pk).slug == 'building-on-demand'
    assert McpCredential.objects.get(pk=credential.pk).connector_id == connector.pk


def test_reverse_seed_removes_restored_history(building_on_demand_program, building_on_demand_content):
    """Fails if protected restoration provenance prevents migration rollback."""
    revision = BuildingOnDemandProgramRevision.objects.create(
        version=2, content=building_on_demand_content,
        restored_from=building_on_demand_program.current_revision,
        change_note='Restauración inicial.',
    )
    BuildingOnDemandProgram.objects.filter(pk=1).update(current_revision=revision)

    seed_migration.reverse_seed(apps, SimpleNamespace(connection=connection))

    assert BuildingOnDemandProgramRevision.objects.count() == 0
    assert BuildingOnDemandProgram.objects.count() == 0


@pytest.mark.parametrize('operation', ['save', 'delete'])
def test_seeded_revision_rejects_mutation(building_on_demand_program, operation):
    """Fails if published seed history can be rewritten or deleted through its model."""
    revision = building_on_demand_program.current_revision
    before = deepcopy(revision.content)
    revision.content['es']['hero']['title'] = 'Cambio prohibido'

    with pytest.raises(ValidationError, match='Building on Demand'):
        getattr(revision, operation)()

    assert BuildingOnDemandProgramRevision.objects.get(pk=revision.pk).content == before


def test_seeded_revision_version_is_unique(building_on_demand_content):
    """Fails if a second version can reuse the deployed seed’s version number."""
    with pytest.raises(IntegrityError), transaction.atomic():
        BuildingOnDemandProgramRevision.objects.create(
            version=1, content=building_on_demand_content, change_note='Versión duplicada.',
        )

    assert BuildingOnDemandProgramRevision.objects.count() == 1


def test_seeded_program_rejects_second_singleton(building_on_demand_program):
    """Fails if the database permits a second current-presentation pointer."""
    with pytest.raises(IntegrityError), transaction.atomic():
        BuildingOnDemandProgram.objects.create(
            pk=2, current_revision=building_on_demand_program.current_revision,
        )

    assert BuildingOnDemandProgram.objects.count() == 1


def test_locked_load_returns_seeded_revision(building_on_demand_program):
    """Fails if writes lock a different program snapshot from the seeded singleton."""
    program = BuildingOnDemandProgram.load(lock=True)

    assert program.pk == 1
    assert program.current_revision_id == building_on_demand_program.current_revision_id
    assert program.current_revision.version == 1
