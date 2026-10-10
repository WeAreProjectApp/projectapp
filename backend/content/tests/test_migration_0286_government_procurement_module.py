import re
from importlib import import_module

import pytest
from django.apps import apps

from content.models import AdditionalModule, AdditionalModuleCategory


pytestmark = pytest.mark.django_db


SLUG = 'government-procurement'
migration = import_module('content.migrations.0286_seed_government_procurement_module')


@pytest.fixture
def module():
    return AdditionalModule.objects.select_related('category').get(slug=SLUG)


def _copy(module, language):
    return ' '.join(
        [
            getattr(module, f'name_{language}'),
            getattr(module, f'summary_{language}'),
            getattr(module, f'what_is_{language}'),
            getattr(module, f'purpose_{language}'),
            *getattr(module, f'problems_solved_{language}'),
            *getattr(module, f'integrations_{language}'),
            *getattr(module, f'implementation_requirements_{language}'),
        ],
    ).lower()


def test_migration_seeds_bilingual_public_sector_catalog_entry(module):
    """The new bilingual entry occupies free category and module positions."""
    category = module.category

    assert (category.slug, category.name_es, category.name_en, category.is_active) == (
        'public-sector', 'Sector público', 'Public sector', True,
    )
    assert not AdditionalModuleCategory.objects.filter(
        order=category.order,
    ).exclude(pk=category.pk).exists()
    assert (module.name_es, module.name_en, module.icon, module.is_active) == (
        'Contratación estatal', 'Government procurement', '🏛️', True,
    )
    assert module.order == 0
    assert not AdditionalModule.objects.filter(
        category=category, order=module.order,
    ).exclude(pk=module.pk).exists()
    assert (
        len(module.problems_solved_es), len(module.problems_solved_en),
        len(module.integrations_es), len(module.integrations_en),
        len(module.implementation_requirements_es),
        len(module.implementation_requirements_en),
    ) == (3, 3, 3, 3, 6, 6)


def test_procurement_copy_identifies_only_the_public_data_source(module):
    """Both languages name SECOP II without exposing internal tools or a client."""
    spanish = _copy(module, 'es')
    english = _copy(module, 'en')

    assert 'secop ii' in spanish
    assert 'secop ii' in english
    assert 'secob' not in spanish + english
    assert re.search(r'socrata|soql|huey|redis|g&m', spanish + english) is None
    assert module.integrations_es[0] == (
        'Datos abiertos del SECOP II que publica Colombia Compra Eficiente, '
        'actualizados una vez al día.'
    )
    assert module.integrations_en[0] == (
        'SECOP II open data published by Colombia Compra Eficiente, updated once a day.'
    )


def test_procurement_copy_targets_the_confirmed_bid_participants(module):
    """The purpose addresses bidders and advisers, excluding finance and treasury."""
    purpose = module.purpose_es.lower()
    copy = _copy(module, 'es') + _copy(module, 'en')

    assert set(re.findall(
        r'proveedores|contratistas|constructoras|interventoría|consultoras|'
        r'licitaciones|abogados|gremios',
        purpose,
    )) == {
        'proveedores', 'contratistas', 'constructoras', 'interventoría',
        'consultoras', 'licitaciones', 'abogados', 'gremios',
    }
    assert re.search(r'tesorería|financier|treasury|finance', copy) is None


def test_procurement_copy_limits_promises_to_open_process_tracking(module):
    """Daily open-process discovery never promises awards or real-time coverage."""
    spanish = _copy(module, 'es')
    english = _copy(module, 'en')

    assert 'procesos abiertos' in module.what_is_es.lower()
    assert 'open processes' in module.what_is_en.lower()
    assert 'cada día' in spanish
    assert 'every day' in english
    assert re.search(r'adjudicad|tiempo real|en vivo|garantiza', spanish) is None
    assert re.search(r'awarded|real time|real-time|guarantee', english) is None


def test_procurement_requirements_leave_the_scope_to_the_proposal(module):
    """Client roles, alert settings and email identity precede the agreed scope."""
    spanish = module.implementation_requirements_es
    english = module.implementation_requirements_en

    assert spanish[-1] == 'Alcance definido con el representante comercial en la propuesta.'
    assert english[-1] == 'Scope defined with the sales representative in the proposal.'
    assert spanish[1:4] == [
        'Lista de las personas que van a usar el módulo y qué puede hacer cada una.',
        'Correos que recibirán las alertas y la frecuencia de cada una: inmediata, diaria o semanal.',
        'Identidad de marca y remitente para los correos de alerta.',
    ]
    assert english[1:4] == [
        'A list of the people who will use the module and what each one can do.',
        'The emails that will receive alerts and how often each one: immediate, daily, or weekly.',
        'Brand identity and sender for the alert emails.',
    ]


def test_seed_preserves_panel_customizations_on_repeated_runs(module):
    """Rerunning preserves both edited records, including positions and inactivity."""
    module.name_es = 'Seguimiento de licitaciones del equipo'
    module.summary_en = 'Our edited procurement workflow.'
    module.order = 9
    module.is_active = False
    module.save(update_fields=['name_es', 'summary_en', 'order', 'is_active'])
    category = module.category
    category.name_es = 'Licitaciones públicas del equipo'
    category.name_en = 'Our public bids'
    category.order = 40
    category.is_active = False
    category.save(update_fields=['name_es', 'name_en', 'order', 'is_active'])
    module_before = AdditionalModule.objects.values().get(pk=module.pk)
    category_before = AdditionalModuleCategory.objects.values().get(pk=category.pk)

    migration.seed_government_procurement_module(apps, None)
    migration.seed_government_procurement_module(apps, None)

    assert AdditionalModule.objects.filter(slug=SLUG).count() == 1
    assert AdditionalModuleCategory.objects.filter(slug='public-sector').count() == 1
    assert AdditionalModule.objects.values().get(slug=SLUG) == module_before
    assert AdditionalModuleCategory.objects.values().get(slug='public-sector') == category_before


def test_seed_appends_public_sector_after_inactive_categories(module):
    """An inactive category still reserves the highest global position."""
    migration.unseed_government_procurement_module(apps, None)
    inactive = AdditionalModuleCategory.objects.create(
        slug='archived-sector', name_es='Sector archivado', name_en='Archived sector',
        order=40, is_active=False,
    )

    migration.seed_government_procurement_module(apps, None)

    category = AdditionalModuleCategory.objects.get(slug='public-sector')
    seeded = AdditionalModule.objects.get(slug=SLUG)
    inactive.refresh_from_db()
    assert category.order == inactive.order + 1 == 41
    assert category.is_active is True
    assert seeded.category_id == category.pk
    assert seeded.order == 0
    assert seeded.is_active is True
    assert inactive.is_active is False


def test_seed_reuses_a_panel_category_after_its_inactive_module(module):
    """A retired panel category receives a retired module after its inactive sibling."""
    category = module.category
    module.delete()
    category.name_es = 'Oportunidades públicas'
    category.name_en = 'Public opportunities'
    category.order = 40
    category.is_active = False
    category.save(update_fields=['name_es', 'name_en', 'order', 'is_active'])
    sibling = AdditionalModule.objects.create(
        category=category, slug='archived-public-advisory', order=7, is_active=False,
        name_es='Asesoría archivada', name_en='Archived advisory',
    )
    category_before = AdditionalModuleCategory.objects.values().get(pk=category.pk)
    sibling_before = AdditionalModule.objects.values().get(pk=sibling.pk)

    migration.seed_government_procurement_module(apps, None)

    seeded = AdditionalModule.objects.get(slug=SLUG)
    assert seeded.category_id == category.pk
    assert seeded.order == sibling.order + 1 == 8
    assert seeded.is_active is False
    assert AdditionalModuleCategory.objects.filter(slug='public-sector').count() == 1
    assert AdditionalModuleCategory.objects.values().get(pk=category.pk) == category_before
    assert AdditionalModule.objects.values().get(pk=sibling.pk) == sibling_before


def test_seed_starts_an_empty_catalog_at_zero():
    """Missing maxima place the first category and its first module at zero."""
    AdditionalModule.objects.all().delete()
    AdditionalModuleCategory.objects.all().delete()

    migration.seed_government_procurement_module(apps, None)

    category = AdditionalModuleCategory.objects.get()
    seeded = AdditionalModule.objects.get()
    assert (category.slug, category.order, category.is_active) == ('public-sector', 0, True)
    assert (seeded.slug, seeded.category_id, seeded.order, seeded.is_active) == (
        SLUG, category.pk, 0, True,
    )


def test_unseed_restores_the_remaining_catalog_without_changes(module):
    """Removing this entry and its empty category preserves every other record."""
    other_modules = list(AdditionalModule.objects.exclude(pk=module.pk).order_by('pk').values())
    other_categories = list(
        AdditionalModuleCategory.objects.exclude(pk=module.category_id).order_by('pk').values(),
    )

    migration.unseed_government_procurement_module(apps, None)

    assert not AdditionalModule.objects.filter(slug=SLUG).exists()
    assert not AdditionalModuleCategory.objects.filter(slug='public-sector').exists()
    assert list(AdditionalModule.objects.order_by('pk').values()) == other_modules
    assert list(AdditionalModuleCategory.objects.order_by('pk').values()) == other_categories


def test_unseed_retains_public_sector_with_another_module(module):
    """Even an inactive remaining module protects its category during reversal."""
    category = module.category
    sibling = AdditionalModule.objects.create(
        category=category, slug='public-sector-advisory', order=module.order + 1,
        name_es='Asesoría pública', name_en='Public advisory', is_active=False,
    )
    sibling_before = AdditionalModule.objects.values().get(pk=sibling.pk)
    category_before = AdditionalModuleCategory.objects.values().get(pk=category.pk)

    migration.unseed_government_procurement_module(apps, None)

    assert not AdditionalModule.objects.filter(slug=SLUG).exists()
    assert AdditionalModule.objects.values().get(pk=sibling.pk) == sibling_before
    assert AdditionalModuleCategory.objects.values().get(pk=category.pk) == category_before
