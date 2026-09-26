from importlib import import_module

import pytest
from django.apps import apps

from content.models import AdditionalModule, AdditionalModuleCategory


pytestmark = pytest.mark.django_db


SLUG = 'intellectual-property-protection'
migration = import_module('content.migrations.0259_seed_intellectual_property_module')


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


def test_migration_seeds_bilingual_intellectual_property_module(module):
    assert module.category.slug == 'identity-access'
    assert module.name_es == 'Protección de propiedad intelectual'
    assert module.name_en == 'Intellectual property protection'
    assert module.icon == '🛡️'
    assert module.is_active is True


def test_intellectual_property_module_carries_both_languages_of_every_list(module):
    assert len(module.problems_solved_es) == len(module.problems_solved_en) == 3
    assert len(module.integrations_es) == len(module.integrations_en) == 3
    assert len(module.implementation_requirements_es) == 6
    assert len(module.implementation_requirements_en) == 6


def test_intellectual_property_module_promises_to_hinder_copying_never_to_prevent_it(module):
    """Anything shipped to a browser can be read: the copy sells a higher cost, not a wall."""
    spanish = _copy(module, 'es')
    english = _copy(module, 'en')

    assert module.summary_es.startswith('Dificulta que bots y agentes')
    assert module.summary_en.startswith('Makes it hard for bots and AI agents')
    for absolute in ('impide', 'imposible', 'garantiza'):
        assert absolute not in spanish
    for absolute in ('prevent', 'impossible', 'guarantee'):
        assert absolute not in english


def test_intellectual_property_module_covers_only_the_agreed_layers(module):
    what_is = module.what_is_es.lower()
    spanish = _copy(module, 'es')

    assert 'código que llega al navegador' in what_is
    assert 'lógica sensible' in what_is
    assert 'acceso a tus datos' in what_is
    assert 'agentes de inteligencia artificial' in what_is
    # The catalog also sells search and AI-assistant metadata (corporate
    # branding), so public pages must stay indexable.
    assert 'sin sacar tus páginas públicas de los buscadores' in what_is
    # Forensic tracing and the legal layer were left out of the offer.
    for excluded in ('marca de agua', 'marcas de agua', 'datos trampa', 'términos de uso'):
        assert excluded not in spanish


def test_intellectual_property_module_leaves_the_scope_to_the_proposal(module):
    assert module.implementation_requirements_es[-1] == (
        'Capas y alcance definidos con el representante comercial en la propuesta.'
    )
    assert module.implementation_requirements_en[-1] == (
        'Layers and scope defined with the sales representative in the proposal.'
    )


def test_intellectual_property_module_occupies_a_free_position_in_its_category(module):
    siblings = AdditionalModule.objects.filter(
        category_id=module.category_id,
    ).exclude(pk=module.pk).values_list('order', flat=True)

    assert module.order not in set(siblings)


def test_seed_keeps_a_module_already_created_from_the_panel(module):
    module.name_es = 'Nombre editado desde el panel'
    module.save(update_fields=['name_es'])

    migration.seed_intellectual_property_module(apps, None)

    seeded = AdditionalModule.objects.filter(slug=SLUG)
    assert seeded.count() == 1
    assert seeded.get().name_es == 'Nombre editado desde el panel'


def test_seed_refuses_to_run_without_its_category(module):
    module.delete()
    AdditionalModuleCategory.objects.filter(slug='identity-access').update(
        slug='renamed-identity-access',
    )

    with pytest.raises(RuntimeError, match='identity-access'):
        migration.seed_intellectual_property_module(apps, None)

    assert not AdditionalModule.objects.filter(slug=SLUG).exists()


def test_unseed_removes_only_the_seeded_module(module):
    others = AdditionalModule.objects.exclude(pk=module.pk).count()
    assert others > 0

    migration.unseed_intellectual_property_module(apps, None)

    assert not AdditionalModule.objects.filter(slug=SLUG).exists()
    assert AdditionalModule.objects.count() == others
