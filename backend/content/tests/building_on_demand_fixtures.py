"""Real seeded program content and small bilingual operation item builders."""
import os
from copy import deepcopy
from hashlib import sha256
from importlib import import_module
from pathlib import Path

import django
import pytest
from django.apps import apps
from django.conf import settings

from content.models import BuildingOnDemandProgram


@pytest.fixture(scope='session')
def django_db_modify_db_settings(request, django_db_modify_db_settings_parallel_suffix, django_db_use_migrations):
    """Keep ordinary setup unchanged; cache a fully migrated DB on explicit reuse."""
    if not request.config.getoption('reuse_db'):
        return
    database = settings.DATABASES['default']
    assert database['ENGINE'] == 'django.db.backends.sqlite3'
    if not django_db_use_migrations:
        raise pytest.UsageError('Reusable program databases require migrations.')

    fingerprint = sha256(str(Path(__file__).resolve().parents[3]).encode())
    fingerprint.update(django.get_version().encode())
    for app_config in sorted(apps.get_app_configs(), key=lambda item: item.label):
        module_name = settings.MIGRATION_MODULES.get(app_config.label, f'{app_config.name}.migrations')
        if module_name is None:
            continue
        try:
            migration_package = import_module(module_name)
        except ModuleNotFoundError as error:
            if error.name != module_name:
                raise
            continue
        for package_path in sorted(migration_package.__path__):
            migration_root = Path(package_path)
            for source in sorted(migration_root.rglob('*.py')):
                fingerprint.update(f'{module_name}/{source.relative_to(migration_root)}\0'.encode())
                fingerprint.update(source.read_bytes())
                fingerprint.update(b'\0')

    cache_directory = Path('/tmp/projectapp-building-on-demand-tests')
    cache_directory.mkdir(mode=0o700, exist_ok=True)
    assert not cache_directory.is_symlink()
    assert cache_directory.stat().st_uid == os.getuid()
    cache_directory.chmod(0o700)
    worker = getattr(request.config, 'workerinput', {}).get('workerid', 'main')
    assert worker.replace('-', '').isalnum()
    cache_file = cache_directory / f'{fingerprint.hexdigest()}-{worker}.sqlite3'
    database.setdefault('TEST', {})['NAME'] = str(cache_file)
    print(f'Reusable migrated Building on Demand test database: {cache_file}')


@pytest.fixture
def building_on_demand_seed_content():
    """Read the actual historical seed without requiring the ORM."""
    migration = import_module('content.migrations.0291_building_on_demand_program')
    return deepcopy(migration.PROGRAM_V1)


@pytest.fixture
def building_on_demand_program(db):
    """Use the real migration seed so tests fail if deployment leaves it absent."""
    return BuildingOnDemandProgram.load()


@pytest.fixture
def building_on_demand_content(building_on_demand_program):
    """Return isolated content without mutating the seeded revision."""
    return deepcopy(building_on_demand_program.current_revision.content)


def hero_update(snapshot):
    """Build a bilingual text edit against the current program etag."""
    sections = {'hero': {lang: deepcopy(snapshot['content'][lang]['hero']) for lang in ('es', 'en')}}
    sections['hero']['es']['title'] = 'Tu producto avanza con criterio.'
    sections['hero']['en']['title'] = 'Your product moves forward with judgment.'
    return {'sections': sections, 'if_match': snapshot['etag'], 'change_note': 'Aclara cómo avanza el producto.'}


def make_tier_item(content, *, tier_id='scale', **changes):
    """Build a fourth tier that can be appended to the seeded offer."""
    last = content['offer']['tiers'][-1]
    item = {
        'id': tier_id,
        'monthly_price': last['monthly_price'] + 2000000,
        'daily_hours': last['daily_hours'] + 4,
        'recommended': False,
        'discounts': deepcopy(last['discounts']),
        'server': deepcopy(last['server']),
        'hosting': {
            'plan': 'Plan ampliado',
            'promo_monthly': 90000,
            'renewal_monthly': 190000,
        },
        'es': {
            'name': 'Scale', 'badge': 'Más capacidad', 'pace_label': 'Ritmo ampliado',
            'pace_summary': 'Avanza con más espacio para las prioridades de tu equipo.',
            'ideal_for': 'Un producto en operación que necesita ampliar su capacidad.',
            'roles': ['Todo lo de Enterprise.'],
            'highlights': ['Más espacio para tus prioridades.'],
            'cta_label': 'Hablemos de Scale',
        },
        'en': {
            'name': 'Scale', 'badge': 'More capacity', 'pace_label': 'Expanded pace',
            'pace_summary': 'Move forward with more room for your team’s priorities.',
            'ideal_for': 'A running product that needs additional capacity.',
            'roles': ['Everything in Enterprise.'],
            'highlights': ['More room for your priorities.'],
            'cta_label': 'Let’s talk about Scale',
        },
    }
    item.update(deepcopy(changes))
    return item


def make_term_item(content, *, term_id='annual', months=12, **changes):
    """Build a longer term with a discount for each current tier."""
    item = {
        'id': term_id,
        'months': months,
        'discounts': {
            tier['id']: max(tier['discounts'].values(), default=0) + 5
            for tier in content['offer']['tiers']
        },
        'es': {'label': f'{months} meses'},
        'en': {'label': f'{months} months'},
    }
    item.update(deepcopy(changes))
    return item


def make_estimator_task_item(*, task_id='integration', **changes):
    """Build an estimator task using fixed size and existing tier ids."""
    item = {
        'id': task_id, 'size': 'm', 'min_tier': 'business',
        'es': {'label': 'Integración', 'hint': 'Conecta tu producto con otro servicio.'},
        'en': {'label': 'Integration', 'hint': 'Connect your product to another service.'},
    }
    item.update(deepcopy(changes))
    return item


def make_faq_item(*, item_id='support', **changes):
    """Build a bilingual question that is absent from the seeded FAQ."""
    item = {
        'id': item_id,
        'es': {'question': '¿Cómo recibo soporte?', 'answer': 'Usa el canal acordado con tu equipo.'},
        'en': {'question': 'How do I receive support?', 'answer': 'Use the channel agreed with your team.'},
    }
    item.update(deepcopy(changes))
    return item


def make_card_item(*, item_id='monitoring', **changes):
    """Build a bilingual card suitable for a seeded card collection."""
    item = {
        'id': item_id,
        'es': {'title': 'Seguimiento', 'summary': 'Mantén visibles las prioridades de tu producto.'},
        'en': {'title': 'Tracking', 'summary': 'Keep your product’s priorities visible.'},
    }
    item.update(deepcopy(changes))
    return item
