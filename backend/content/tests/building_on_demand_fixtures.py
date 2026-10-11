"""Real seeded program content and small bilingual operation item builders."""
from copy import deepcopy
from importlib import import_module

import pytest

from content.models import BuildingOnDemandContract, BuildingOnDemandProgram, ContractTemplate, DocumentFolder


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


@pytest.fixture
def building_on_demand_contract(db):
    """Exercise the immutable contract deployed by the real data migration."""
    return BuildingOnDemandContract.load()


@pytest.fixture
def unpinned_contracts_folder(db):
    """An explicit internal folder with no configured or derived shared pin."""
    ContractTemplate.objects.filter(is_default=True).update(mirror_folder=None, mirror_document=None)
    root = DocumentFolder.objects.create(name='ProjectApp')
    return DocumentFolder.objects.create(name='Contratos', parent=root)


@pytest.fixture
def pinned_contracts_folder(unpinned_contracts_folder):
    """Use the same folder pin as all proposal and module contract mirrors."""
    template = ContractTemplate.get_default()
    if template is None:
        template = ContractTemplate.objects.create(name='Contrato de pruebas', is_default=True)
    template.mirror_folder = unpinned_contracts_folder
    template.save(update_fields=['mirror_folder', 'updated_at'])
    return unpinned_contracts_folder


def contract_update(snapshot):
    """Build an attributed contract edit against the current etag."""
    return {'markdown': snapshot['markdown'] + '\n\n## ACLARACIÓN\n\nCada estimación aprobada queda registrada por escrito.\n',
            'if_match': snapshot['etag'], 'change_note': 'Aclara el registro de la estimación aprobada.'}
