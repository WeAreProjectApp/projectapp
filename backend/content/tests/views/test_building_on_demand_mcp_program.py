"""Real program mutations publish only after version-bound MCP confirmation."""
from copy import deepcopy

import pytest

from content.mcp.building_on_demand_tools import BUILDING_ON_DEMAND_TOOLS
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.protocol import ToolError
from content.models import BuildingOnDemandProgramRevision, McpActionIntent
from content.services import building_on_demand_program_service as service
from content.tests.building_on_demand_fixtures import (
    confirm, hero_update, make_card_item, make_estimator_task_item, make_faq_item,
    make_term_item, make_tier_item, rpc_call,
)

pytestmark = pytest.mark.django_db
ITEM_KINDS = ['tier', 'term', 'estimator_task', 'faq', 'roles', 'bag_rules',
              'hosting_features', 'good_for', 'not_for']
WRITE_TOOLS = {tool['name']: tool for tool in BUILDING_ON_DEMAND_TOOLS
               if tool.get('requires_confirmation')}
TEXT_PATHS = {
    'tier': ('tiers', 'items'), 'term': ('terms', 'items'),
    'estimator_task': ('estimator', 'tasks'), 'faq': ('faq', 'items'),
    'roles': ('cell', 'roles'), 'bag_rules': ('bag', 'rules'),
    'hosting_features': ('hosting', 'features'), 'good_for': ('fit', 'good_for'),
    'not_for': ('fit', 'not_for'),
}


@pytest.fixture
def item_case(kind, building_on_demand_content):
    """Keep item-family setup outside the single-operation assertions."""
    builders = {
        'tier': lambda: make_tier_item(building_on_demand_content),
        'term': lambda: make_term_item(building_on_demand_content),
        'estimator_task': make_estimator_task_item, 'faq': make_faq_item,
    }
    card = kind not in builders
    noun = 'card' if card else kind
    source = {'tier': 'tier', 'term': 'term', 'estimator_task': 'task'}.get(kind, 'item')
    selector = {'tier': 'tier_id', 'term': 'term_id', 'estimator_task': 'task_id'}.get(kind, 'item_id')
    return {
        'noun': noun, 'source': source, 'selector': selector,
        'item': builders.get(kind, make_card_item)(),
        'extra': {'collection': kind} if card else {},
        'field': {'tier': 'name', 'term': 'label', 'estimator_task': 'label', 'faq': 'question'}.get(kind, 'title'),
    }


def _text_items(snapshot, kind, lang='es'):
    section, key = TEXT_PATHS[kind]
    return snapshot['content'][lang][section][key]


def _created_arguments(case):
    return {case['source']: case['item'], **case['extra']}


def _prepare_write(api_client, token, name, arguments):
    snapshot = rpc_call(api_client, token, 'get_building_on_demand_program', {})['structuredContent']
    return rpc_call(api_client, token, name, {
        **arguments, 'if_match': snapshot['etag'], 'change_note': 'Ajusta la oferta de la célula.',
    })['structuredContent']


def _create_for_edit(case, actor):
    service.apply_operation(f'create_{case["noun"]}', {
        **_created_arguments(case), 'if_match': service.read_program()['etag'],
        'change_note': 'Prepara un elemento independiente para la prueba.',
    }, actor=actor)


def test_confirmed_program_update_publishes_bilingual_text(api_client, building_on_demand_mcp,
                                                        monkeypatch, django_capture_on_commit_callbacks):
    """Fails if preview publishes early or confirmation loses bilingual content."""
    token, credential = building_on_demand_mcp
    original = service.read_program()
    arguments = hero_update(original)
    rebuild_requests = []
    monkeypatch.setattr(service, 'schedule_rebuild_after_publish', lambda **kwargs: rebuild_requests.append(kwargs))
    preview = rpc_call(api_client, token, 'preview_building_on_demand_program_update',
                       {'sections': arguments['sections']})['structuredContent']
    intent = rpc_call(api_client, token, 'update_building_on_demand_program', arguments)['structuredContent']
    assert service.read_program()['version'] == 1

    with django_capture_on_commit_callbacks(execute=True):
        result = confirm(api_client, token, intent)['structuredContent']['result']
    published = service.read_program()
    revision = BuildingOnDemandProgramRevision.objects.get(pk=result['version_id'])

    assert preview['changed'] is True
    assert result['version'] == 2
    assert published['content']['es']['hero'] == arguments['sections']['hero']['es']
    assert published['content']['en']['hero'] == arguments['sections']['hero']['en']
    assert revision.credential_id == credential.pk
    assert revision.author_id == credential.actor_id
    assert rebuild_requests == [{'reason': 'building-on-demand'}]


def test_confirmed_program_restore_preserves_history(api_client, building_on_demand_mcp, superuser):
    """Fails if restore overwrites history instead of creating an attributed revision."""
    token, credential = building_on_demand_mcp
    initial = service.read_program()
    service.apply_operation('update_program', hero_update(initial), actor=superuser)
    intent = _prepare_write(api_client, token, 'restore_building_on_demand_program_version',
                            {'version_id': initial['version_id']})
    assert service.read_program()['version'] == 2

    result = confirm(api_client, token, intent)['structuredContent']['result']
    versions = rpc_call(api_client, token, 'list_building_on_demand_program_versions',
                        {'include_content': True})['structuredContent']

    assert result['version'] == 3
    assert versions['total'] == 3
    assert versions['versions'][0]['restored_from_version_id'] == initial['version_id']
    assert versions['versions'][0]['restored_from_version'] == 1
    assert versions['versions'][0]['content'] == initial['content']
    assert BuildingOnDemandProgramRevision.objects.get(pk=result['version_id']).credential_id == credential.pk


@pytest.mark.parametrize('kind', ITEM_KINDS)
def test_confirmed_item_creation_publishes_revision(api_client, building_on_demand_mcp, kind, item_case):
    """Fails if a collection cannot create an item through preview and confirmation."""
    token, credential = building_on_demand_mcp
    intent = _prepare_write(api_client, token, f'create_building_on_demand_{item_case["noun"]}',
                            _created_arguments(item_case))
    assert service.read_program()['version'] == 1

    result = confirm(api_client, token, intent)['structuredContent']['result']
    published = rpc_call(api_client, token, 'get_building_on_demand_program', {})['structuredContent']

    assert result['version'] == 2
    assert _text_items(published, kind)[-1] == {'id': item_case['item']['id'], **item_case['item']['es']}
    assert _text_items(published, kind, 'en')[-1] == {'id': item_case['item']['id'], **item_case['item']['en']}
    assert published['change_note'] == 'Ajusta la oferta de la célula.'
    assert BuildingOnDemandProgramRevision.objects.get(pk=result['version_id']).credential_id == credential.pk


@pytest.mark.parametrize('kind', ITEM_KINDS)
def test_confirmed_item_update_publishes_revision(api_client, building_on_demand_mcp, superuser, kind, item_case):
    """Fails if editing an existing collection item skips the immutable publication."""
    token, _ = building_on_demand_mcp
    _create_for_edit(item_case, superuser)
    changes = {'es': {item_case['field']: 'Prioridades compartidas'},
               'en': {item_case['field']: 'Shared priorities'}}
    intent = _prepare_write(api_client, token, f'update_building_on_demand_{item_case["noun"]}', {
        item_case['selector']: item_case['item']['id'], 'changes': changes, **item_case['extra'],
    })
    assert service.read_program()['version'] == 2

    result = confirm(api_client, token, intent)['structuredContent']['result']
    published = service.read_program()

    assert result['version'] == 3
    assert _text_items(published, kind)[-1] == {
        'id': item_case['item']['id'], **item_case['item']['es'], **changes['es'],
    }
    assert _text_items(published, kind, 'en')[-1] == {
        'id': item_case['item']['id'], **item_case['item']['en'], **changes['en'],
    }
    assert BuildingOnDemandProgramRevision.objects.count() == 3


@pytest.mark.parametrize('kind', ITEM_KINDS)
def test_confirmed_item_removal_publishes_revision(api_client, building_on_demand_mcp, superuser, kind, item_case):
    """Fails if a removable item cannot be deleted through a frozen preview."""
    token, _ = building_on_demand_mcp
    original = service.read_program()['content']
    _create_for_edit(item_case, superuser)
    intent = _prepare_write(api_client, token, f'remove_building_on_demand_{item_case["noun"]}', {
        item_case['selector']: item_case['item']['id'], **item_case['extra'],
    })
    assert service.read_program()['version'] == 2

    result = confirm(api_client, token, intent)['structuredContent']['result']

    assert result['version'] == 3
    assert service.read_program()['content'] == original
    assert BuildingOnDemandProgramRevision.objects.count() == 3


def test_confirmed_reorder_aligns_bilingual_items(api_client, building_on_demand_mcp):
    """Fails if item order changes before confirmation or differs between languages."""
    token, _ = building_on_demand_mcp
    original = service.read_program()
    ids = [item['id'] for item in original['content']['offer']['estimator']['tasks']][::-1]
    intent = _prepare_write(api_client, token, 'reorder_building_on_demand_items',
                            {'collection': 'estimator_tasks', 'ids': ids})
    assert service.read_program()['version'] == 1

    result = confirm(api_client, token, intent)['structuredContent']['result']
    content = service.read_program()['content']

    assert result['version'] == 2
    assert [item['id'] for item in content['offer']['estimator']['tasks']] == ids
    assert [item['id'] for item in content['es']['estimator']['tasks']] == ids
    assert [item['id'] for item in content['en']['estimator']['tasks']] == ids


def test_confirmed_sizes_update_publishes_hour_ranges(api_client, building_on_demand_mcp):
    """Fails if fixed estimator sizes cannot publish a validated range change."""
    token, _ = building_on_demand_mcp
    sizes = deepcopy(service.read_program()['content']['offer']['estimator']['sizes'])
    sizes[0]['hours_max'] = 6
    intent = _prepare_write(api_client, token, 'update_building_on_demand_estimator_sizes', {'sizes': sizes})
    assert service.read_program()['version'] == 1

    result = confirm(api_client, token, intent)['structuredContent']['result']

    assert result['version'] == 2
    assert service.read_program()['content']['offer']['estimator']['sizes'] == sizes


def test_confirmed_economics_update_changes_private_calculation(api_client, building_on_demand_mcp):
    """Fails if a confirmed internal cost edit omits its new breakeven calculation."""
    token, _ = building_on_demand_mcp
    intent = _prepare_write(api_client, token, 'update_building_on_demand_economics',
                            {'economics': {'hour_cost': 60000}})
    assert service.economics()['hour_cost'] == 55000

    result = confirm(api_client, token, intent)['structuredContent']['result']
    economics = rpc_call(api_client, token, 'get_building_on_demand_economics', {})['structuredContent']

    assert result['version'] == 2
    assert economics['hour_cost'] == 60000
    assert economics['rows'][0]['breakeven_hours'] == 29.2


@pytest.mark.parametrize(('name', 'arguments', 'observe', 'expected'), [
    ('update_building_on_demand_program', {'settings': {'days_per_week': 5}},
     lambda content: content['offer']['days_per_week'], 5),
    ('update_building_on_demand_tier', {'tier_id': 'starter', 'changes': {'monthly_price': 1900000, 'server': {'ram_gb': 8}}},
     lambda content: (content['offer']['tiers'][0]['monthly_price'], content['offer']['tiers'][0]['server']['ram_gb']), (1900000, 8)),
    ('update_building_on_demand_term', {'term_id': 'quarterly', 'changes': {'months': 4, 'discounts': {'starter': 7}}},
     lambda content: (content['offer']['terms'][1]['months'], content['offer']['tiers'][0]['discounts']['quarterly']), (4, 7)),
    ('update_building_on_demand_estimator_task', {'task_id': 'requirements-session', 'changes': {'size': 'm', 'min_tier': 'enterprise'}},
     lambda content: (content['offer']['estimator']['tasks'][0]['size'], content['offer']['estimator']['tasks'][0]['min_tier']), ('m', 'enterprise')),
], ids=['bag-settings', 'tier-offer', 'term-offer', 'task-configuration'])
def test_confirmed_numeric_edit_publishes_configuration(api_client, building_on_demand_mcp, name, arguments, observe, expected):
    """Fails if typed offer edits only change text or publish before confirmation."""
    token, _ = building_on_demand_mcp
    intent = _prepare_write(api_client, token, name, arguments)
    assert observe(service.read_program()['content']) != expected

    result = confirm(api_client, token, intent)['structuredContent']['result']

    assert result['version'] == 2
    assert observe(service.read_program()['content']) == expected


def test_confirmed_card_creation_respects_position(api_client, building_on_demand_mcp):
    """Fails if an explicit zero-based insertion position is lost during preview."""
    token, _ = building_on_demand_mcp
    item = make_card_item()
    intent = _prepare_write(api_client, token, 'create_building_on_demand_card',
                            {'collection': 'roles', 'item': item, 'position': 0})
    assert _text_items(service.read_program(), 'roles')[0]['id'] != item['id']

    result = confirm(api_client, token, intent)['structuredContent']['result']
    published = service.read_program()

    assert result['version'] == 2
    assert _text_items(published, 'roles')[0] == {'id': item['id'], **item['es']}
    assert _text_items(published, 'roles', 'en')[0] == {'id': item['id'], **item['en']}


def test_referenced_tier_removal_creates_no_intent(api_client, building_on_demand_mcp):
    """Fails if removing a referenced tier can break the estimator's minimum plan."""
    token, credential = building_on_demand_mcp

    result = rpc_call(api_client, token, 'remove_building_on_demand_tier', {
        'tier_id': 'enterprise', 'if_match': service.read_program()['etag'],
        'change_note': 'Intenta retirar un plan que todavía está usado.',
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'REFERENCED_ITEM'
    assert result['structuredContent']['error']['details']['references'] == [
        'offer.estimator.tasks[continuous-devops].min_tier',
    ]
    assert not McpActionIntent.objects.filter(credential=credential).exists()
    assert service.read_program()['version'] == 1


def test_confirmation_rejects_a_later_program_version(api_client, building_on_demand_mcp, superuser):
    """Fails if an old intent overwrites a program publication made after preview."""
    token, _ = building_on_demand_mcp
    original = service.read_program()
    intent = _prepare_write(api_client, token, 'update_building_on_demand_economics',
                            {'economics': {'hour_cost': 60000}})
    service.apply_operation('update_program', hero_update(original), actor=superuser)

    result = confirm(api_client, token, intent)

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert service.read_program()['content']['internal']['hour_cost'] == 55000
    assert BuildingOnDemandProgramRevision.objects.count() == 2


@pytest.mark.parametrize('name', sorted(WRITE_TOOLS))
def test_direct_program_write_requires_confirmation(building_on_demand_mcp, name):
    """Fails if a registered write handler bypasses the durable confirmation."""
    _, credential = building_on_demand_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='unconfirmed-program-write', actor=credential.actor)

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        WRITE_TOOLS[name]['handler']({})

    assert error.value.code == 'CONFIRMATION_REQUIRED'
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize('name', sorted(WRITE_TOOLS))
def test_confirmed_program_handler_requires_frozen_etags(building_on_demand_mcp, name):
    """Fails if a confirmed handler accepts arguments without the preview's etags."""
    _, credential = building_on_demand_mcp
    context = McpExecutionContext(connector=credential.connector, credential=credential,
                                  request_id='missing-program-preview', actor=credential.actor, confirmation_bypass=True)

    with use_mcp_context(context, atomic_history=False), pytest.raises(ToolError) as error:
        WRITE_TOOLS[name]['handler']({})

    assert error.value.code == 'STALE_VERSION'
    assert BuildingOnDemandProgramRevision.objects.count() == 1
