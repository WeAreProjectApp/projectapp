"""Successful program operations preserve item ownership and bilingual alignment."""

from copy import deepcopy

import pytest

from content.models import BuildingOnDemandProgramRevision
from content.services import building_on_demand_program_service as service
from content.tests.building_on_demand_fixtures import (
    hero_update, make_tier_item, make_term_item, make_estimator_task_item, make_faq_item, make_card_item,
)

pytestmark = pytest.mark.django_db

CARD_COLLECTIONS = [
    ('roles', 'cell', 'roles'), ('bag_rules', 'bag', 'rules'),
    ('hosting_features', 'hosting', 'features'), ('good_for', 'fit', 'good_for'), ('not_for', 'fit', 'not_for'),
]
REORDER_COLLECTIONS = [
    ('estimator_tasks', 'estimator', 'tasks'), ('faq', 'faq', 'items'), *CARD_COLLECTIONS,
]


def _publish(operation, arguments):
    arguments = {**deepcopy(arguments), 'if_match': service.read_program()['etag'], 'change_note': 'Ajuste de catálogo revisado.'}
    return service.apply_operation(operation, arguments, actor=None)


def _ids(items):
    return [item['id'] for item in items]


def _flags(content):
    return [tier['recommended'] for tier in content['offer']['tiers']]


def _discounts_for(content, term):
    return [tier['discounts'].get(term) for tier in content['offer']['tiers']]


def _current_content():
    return service.read_program()['content']


def test_update_program_preserves_untouched_sections(building_on_demand_program):
    """Fails if a bilingual presentation edit drops unrelated content or offer settings."""
    before = service.read_program()
    arguments = hero_update(before)
    arguments['settings'] = {'days_per_week': 5}

    result = service.apply_operation('update_program', arguments, actor=None)
    content = _current_content()

    assert result['version'] == 2
    assert content['es']['hero']['title'] == 'Tu producto avanza con criterio.'
    assert content['en']['hero']['title'] == 'Your product moves forward with judgment.'
    assert content['es']['cell'] == before['content']['es']['cell']
    assert content['offer']['weeks_per_month'] == 4
    assert service.serialize_public_program('es')['tiers']['items'][0]['bag_hours'] == 80


def test_create_tier_stores_its_owned_hosting_costs(building_on_demand_content):
    """Fails if a new tier loses its private costs, texts or exclusive recommendation."""
    tier = make_tier_item(building_on_demand_content, recommended=True)

    result = _publish('create_tier', {'tier': tier})
    content = _current_content()

    assert result['version'] == 2
    assert _ids(content['offer']['tiers']) == ['starter', 'business', 'enterprise', 'scale']
    assert _flags(content) == [False, False, False, True]
    assert content['es']['tiers']['items'][-1] == {'id': 'scale', **tier['es']}
    assert content['en']['tiers']['items'][-1] == {'id': 'scale', **tier['en']}
    assert content['internal']['servers']['scale'] == tier['hosting']
    assert service.serialize_public_program('es')['tiers']['items'][-1]['bag_hours'] == 384


def test_update_tier_merges_nested_patches(building_on_demand_content):
    """Fails if a partial tier edit drops siblings or leaves multiple recommended tiers."""
    changes = {
        'monthly_price': 1900000, 'recommended': True, 'server': {'vcpu': 2},
        'hosting': {'renewal_monthly': 40000}, 'es': {'name': 'Inicial'}, 'en': {'name': 'Initial'},
    }

    _publish('update_tier', {'tier_id': 'starter', 'changes': changes})
    content = _current_content()

    assert _flags(content) == [True, False, False]
    assert content['offer']['tiers'][0]['monthly_price'] == 1900000
    assert content['offer']['tiers'][0]['server'] == {'vcpu': 2, 'ram_gb': 4, 'disk_gb': 50, 'transfer_tb': 4}
    assert content['internal']['servers']['starter'] == {'plan': 'KVM 1', 'promo_monthly': 19900, 'renewal_monthly': 40000}
    assert content['es']['tiers']['items'][0]['name'] == 'Inicial'
    assert content['en']['tiers']['items'][0]['name'] == 'Initial'
    assert content['es']['tiers']['items'][0]['ideal_for'] == building_on_demand_content['es']['tiers']['items'][0]['ideal_for']


def test_remove_tier_removes_its_owned_data(building_on_demand_content):
    """Fails if an unreferenced tier's texts or hosting costs survive its removal."""
    _publish('create_tier', {'tier': make_tier_item(building_on_demand_content)})

    result = _publish('remove_tier', {'tier_id': 'scale'})
    content = _current_content()

    assert result['version'] == 3
    assert _ids(content['offer']['tiers']) == ['starter', 'business', 'enterprise']
    assert _ids(content['es']['tiers']['items']) == ['starter', 'business', 'enterprise']
    assert _ids(content['en']['tiers']['items']) == ['starter', 'business', 'enterprise']
    assert set(content['internal']['servers']) == {'starter', 'business', 'enterprise'}


def test_create_term_inserts_by_months(building_on_demand_content):
    """Fails if a new term appends out of order or omits a tier's owned discount."""
    term = make_term_item(building_on_demand_content, term_id='bimonthly', months=2,
                          discounts={'starter': 2, 'business': 5, 'enterprise': 10})

    _publish('create_term', {'term': term})
    content = _current_content()

    assert _ids(content['offer']['terms']) == ['monthly', 'bimonthly', 'quarterly', 'semiannual', 'nine-month']
    assert content['offer']['terms'][1] == {'id': 'bimonthly', 'months': 2}
    assert content['es']['terms']['items'][1] == {'id': 'bimonthly', 'label': '2 meses'}
    assert content['en']['terms']['items'][1] == {'id': 'bimonthly', 'label': '2 months'}
    assert _discounts_for(content, 'bimonthly') == [2, 5, 10]


def test_update_term_distributes_the_tier_discounts(building_on_demand_program):
    """Fails if a term edit leaves its duration, translations or tier discounts stale."""
    changes = {'months': 4, 'discounts': {'starter': 6, 'business': 11, 'enterprise': 16},
               'es': {'label': 'Cuatro meses'}, 'en': {'label': 'Four months'}}

    _publish('update_term', {'term_id': 'quarterly', 'changes': changes})
    content = _current_content()

    assert content['offer']['terms'][1] == {'id': 'quarterly', 'months': 4}
    assert content['es']['terms']['items'][1] == {'id': 'quarterly', 'label': 'Cuatro meses'}
    assert content['en']['terms']['items'][1] == {'id': 'quarterly', 'label': 'Four months'}
    assert _discounts_for(content, 'quarterly') == [6, 11, 16]


def test_remove_term_removes_its_owned_discounts(building_on_demand_program):
    """Fails if a term's own discounts incorrectly block removal or remain dangling."""
    _publish('remove_term', {'term_id': 'quarterly'})
    content = _current_content()

    assert _ids(content['offer']['terms']) == ['monthly', 'semiannual', 'nine-month']
    assert _ids(content['es']['terms']['items']) == ['monthly', 'semiannual', 'nine-month']
    assert _ids(content['en']['terms']['items']) == ['monthly', 'semiannual', 'nine-month']
    assert _discounts_for(content, 'quarterly') == [None, None, None]
    assert _discounts_for(content, 'semiannual') == [10, 15, 20]


def test_create_estimator_task_inserts_bilingual_references(building_on_demand_program):
    """Fails if a positioned estimator task separates its translations from its references."""
    task = make_estimator_task_item()

    _publish('create_estimator_task', {'task': task, 'position': 1})
    content = _current_content()

    assert content['offer']['estimator']['tasks'][1] == {'id': 'integration', 'size': 'm', 'min_tier': 'business'}
    assert content['es']['estimator']['tasks'][1] == {'id': 'integration', **task['es']}
    assert content['en']['estimator']['tasks'][1] == {'id': 'integration', **task['en']}
    assert len(content['offer']['estimator']['tasks']) == 10


def test_update_estimator_task_merges_its_text_patch(building_on_demand_content):
    """Fails if a task edit drops its hint or leaves stale size and tier references."""
    changes = {'size': 'm', 'min_tier': 'enterprise',
               'es': {'label': 'Exploración'}, 'en': {'label': 'Discovery'}}

    _publish('update_estimator_task', {'task_id': 'requirements-session', 'changes': changes})
    content = _current_content()

    assert content['offer']['estimator']['tasks'][0] == {'id': 'requirements-session', 'size': 'm', 'min_tier': 'enterprise'}
    assert content['es']['estimator']['tasks'][0]['label'] == 'Exploración'
    assert content['en']['estimator']['tasks'][0]['label'] == 'Discovery'
    assert content['es']['estimator']['tasks'][0]['hint'] == building_on_demand_content['es']['estimator']['tasks'][0]['hint']


def test_remove_estimator_task_removes_both_translations(building_on_demand_program):
    """Fails if a removed estimator task remains public in either language."""
    _publish('remove_estimator_task', {'task_id': 'continuous-devops'})
    content = _current_content()

    assert len(content['offer']['estimator']['tasks']) == 8
    assert 'continuous-devops' not in _ids(content['offer']['estimator']['tasks'])
    assert 'continuous-devops' not in _ids(content['es']['estimator']['tasks'])
    assert 'continuous-devops' not in _ids(content['en']['estimator']['tasks'])


def test_create_faq_inserts_both_translations(building_on_demand_program):
    """Fails if a new FAQ loses its answer or position in one language."""
    item = make_faq_item()

    _publish('create_faq', {'item': item, 'position': 0})
    content = _current_content()

    assert content['es']['faq']['items'][0] == {'id': 'support', **item['es']}
    assert content['en']['faq']['items'][0] == {'id': 'support', **item['en']}


def test_update_faq_preserves_its_question(building_on_demand_content):
    """Fails if updating an FAQ answer replaces its question or sibling translation."""
    item = building_on_demand_content['es']['faq']['items'][0]
    changes = {'es': {'answer': 'Acordamos el canal contigo.'}, 'en': {'answer': 'We agree on the channel with you.'}}

    _publish('update_faq', {'item_id': item['id'], 'changes': changes})
    content = _current_content()

    assert content['es']['faq']['items'][0] == {**item, 'answer': 'Acordamos el canal contigo.'}
    assert content['en']['faq']['items'][0]['answer'] == 'We agree on the channel with you.'
    assert content['en']['faq']['items'][0]['question'] == building_on_demand_content['en']['faq']['items'][0]['question']


def test_remove_faq_removes_both_translations(building_on_demand_content):
    """Fails if removing a question leaves a dangling English or Spanish FAQ."""
    removed_id = building_on_demand_content['es']['faq']['items'][-1]['id']
    expected_ids = _ids(building_on_demand_content['es']['faq']['items'][:-1])

    _publish('remove_faq', {'item_id': removed_id})
    content = _current_content()

    assert _ids(content['es']['faq']['items']) == expected_ids
    assert _ids(content['en']['faq']['items']) == expected_ids


@pytest.mark.parametrize('collection,section,key', CARD_COLLECTIONS)
def test_create_card_inserts_in_the_selected_collection(building_on_demand_program, collection, section, key):
    """Fails if a new card is written to the wrong list or loses a language."""
    item = make_card_item()

    _publish('create_card', {'collection': collection, 'item': item, 'position': 0})
    content = _current_content()

    assert content['es'][section][key][0] == {'id': 'monitoring', **item['es']}
    assert content['en'][section][key][0] == {'id': 'monitoring', **item['en']}


@pytest.mark.parametrize('collection,section,key', CARD_COLLECTIONS)
def test_update_card_preserves_its_other_fields(building_on_demand_content, collection, section, key):
    """Fails if a partial card edit replaces its summary or targets a different list."""
    item = building_on_demand_content['es'][section][key][0]
    changes = {'es': {'title': 'Prioridades claras'}, 'en': {'title': 'Clear priorities'}}

    _publish('update_card', {'collection': collection, 'item_id': item['id'], 'changes': changes})
    content = _current_content()

    assert content['es'][section][key][0] == {**item, 'title': 'Prioridades claras'}
    assert content['en'][section][key][0]['title'] == 'Clear priorities'
    assert content['en'][section][key][0]['summary'] == building_on_demand_content['en'][section][key][0]['summary']


@pytest.mark.parametrize('collection,section,key', CARD_COLLECTIONS)
def test_remove_card_removes_both_translations(building_on_demand_content, collection, section, key):
    """Fails if a removed card remains visible in one translation of its collection."""
    item_id = building_on_demand_content['es'][section][key][0]['id']
    expected_ids = _ids(building_on_demand_content['es'][section][key][1:])

    _publish('remove_card', {'collection': collection, 'item_id': item_id})
    content = _current_content()

    assert _ids(content['es'][section][key]) == expected_ids
    assert _ids(content['en'][section][key]) == expected_ids


@pytest.mark.parametrize('collection,section,key', REORDER_COLLECTIONS)
def test_reorder_items_preserves_bilingual_alignment(building_on_demand_content, collection, section, key):
    """Fails if reordering translates a different sequence of cards or estimator tasks."""
    expected_ids = list(reversed(_ids(building_on_demand_content['es'][section][key])))

    _publish('reorder_items', {'collection': collection, 'ids': expected_ids})
    content = _current_content()

    assert _ids(content['es'][section][key]) == expected_ids
    assert _ids(content['en'][section][key]) == expected_ids
    assert len(content['es'][section][key]) == len(building_on_demand_content['es'][section][key])


@pytest.mark.parametrize('collection', ['tiers', 'terms'])
def test_reorder_numeric_items_accepts_an_identity_permutation(building_on_demand_content, collection):
    """Fails if a valid unchanged tier or term order produces redundant history."""
    ids = _ids(building_on_demand_content['offer'][collection])

    result = _publish('reorder_items', {'collection': collection, 'ids': ids})

    assert result['changed'] is False
    assert result['version'] == 1
    assert BuildingOnDemandProgramRevision.objects.count() == 1


def test_update_estimator_sizes_replaces_the_fixed_ranges(building_on_demand_content):
    """Fails if size edits alter the fixed identities or fail to publish reference hours."""
    sizes = deepcopy(building_on_demand_content['offer']['estimator']['sizes'])
    sizes[0]['hours_max'] = 8

    _publish('update_estimator_sizes', {'sizes': sizes})

    assert service.serialize_public_program('es')['estimator']['sizes'] == sizes
    assert _ids(sizes) == ['xs', 's', 'm', 'l']


def test_update_economics_merges_private_server_patches(building_on_demand_content):
    """Fails if private cost updates overwrite unchanged server plans or public offer data."""
    economics = {'hour_cost': 60000, 'servers': {'starter': {'renewal_monthly': 40000}}}

    _publish('update_economics', {'economics': economics})
    content = _current_content()

    assert content['internal']['hour_cost'] == 60000
    assert content['internal']['servers']['starter'] == {'plan': 'KVM 1', 'promo_monthly': 19900, 'renewal_monthly': 40000}
    assert content['internal']['servers']['business'] == building_on_demand_content['internal']['servers']['business']
    assert content['offer'] == building_on_demand_content['offer']


@pytest.mark.parametrize('operation,arguments', [
    ('update_program', {'settings': {'days_per_week': 5}}),
    ('update_program', {'settings': {'weeks_per_month': 5}}),
    ('update_program', {'settings': {'prices_include_vat': True}}),
    ('update_tier', {'tier_id': 'starter', 'changes': {'monthly_price': 1900000}}),
    ('update_tier', {'tier_id': 'starter', 'changes': {'daily_hours': 5}}),
    ('update_tier', {'tier_id': 'starter', 'changes': {'discounts': {'quarterly': 6}}}),
    ('update_term', {'term_id': 'quarterly', 'changes': {'months': 4}}),
    ('remove_term', {'term_id': 'quarterly'}),
])
def test_pricing_preview_warns_about_the_contract(building_on_demand_program, operation, arguments):
    """Fails if a commercial plan, price or capacity change omits contractual review."""
    preview = service.prepare_operation(operation, arguments)

    assert preview['warnings'] == ['El contrato cita planes y precios: revísalo.']
    assert preview['changed'] is True
    assert service.read_program()['version'] == 1


def test_private_preview_does_not_request_contract_review(building_on_demand_program):
    """Fails if an internal hourly cost edit falsely claims the public contract changed."""
    preview = service.prepare_operation('update_economics', {'economics': {'hour_cost': 60000}})

    assert preview['warnings'] == []
    assert preview['changed'] is True
    assert preview['change_note'] == ''
