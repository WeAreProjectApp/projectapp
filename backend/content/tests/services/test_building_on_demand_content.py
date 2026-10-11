"""Content invariants and the schemas consumed by the operations engine."""
import hashlib
import json
from copy import deepcopy

import pytest

from content.services.building_on_demand_content import (
    BuildingOnDemandError,
    TEXT_SECTION_KEYS,
    canonical_hash,
    card_json_schema,
    economics_json_schema,
    estimator_sizes_json_schema,
    estimator_task_json_schema,
    faq_json_schema,
    section_json_schema,
    settings_json_schema,
    term_json_schema,
    tier_json_schema,
    validate_content,
    validate_schema,
    validate_section,
)

def _replace(content, path, value):
    target = content
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def _path_name(path):
    result = ''
    for key in path:
        result += f'[{key}]' if isinstance(key, int) else f'.{key}'
    return result.lstrip('.')


def _field_error(content, path, value):
    _replace(content, path, value)
    with pytest.raises(BuildingOnDemandError) as error:
        validate_content(content)
    return error.value


def _schema_nodes(schema):
    yield schema
    for child in schema.get('properties', {}).values():
        yield from _schema_nodes(child)
    for child in schema.get('patternProperties', {}).values():
        yield from _schema_nodes(child)
    for child in schema.get('prefixItems', []):
        yield from _schema_nodes(child)
    if 'items' in schema:
        yield from _schema_nodes(schema['items'])
    if 'propertyNames' in schema:
        yield from _schema_nodes(schema['propertyNames'])


def _schema_issues(schema):
    issues = []
    for node in _schema_nodes(schema):
        if not isinstance(node.get('description'), str) or not node['description'].strip():
            issues.append('missing description')
        if node.get('type') == 'object' and node.get('additionalProperties') is not False:
            issues.append('open object')
        if set(node).intersection({'oneOf', 'anyOf', '$ref'}):
            issues.append('implicit schema')
    return issues


FULL_ITEM_BUILDERS = [tier_json_schema, term_json_schema, estimator_task_json_schema, faq_json_schema, card_json_schema]
SCHEMA_BUILDERS = [
    section_json_schema, settings_json_schema, tier_json_schema, term_json_schema,
    estimator_task_json_schema, faq_json_schema, card_json_schema,
    estimator_sizes_json_schema, economics_json_schema,
]


class TestDocumentObjects:
    @pytest.mark.parametrize('value', [None, [], 'program'])
    def test_document_requires_an_object(self, value):
        """Fails if a non-object document bypasses the structured validation error."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(value)

        assert error.value.code == 'VALIDATION_ERROR'
        assert error.value.details == {'path': ''}

    @pytest.mark.parametrize('path', [
        (), ('es',), ('es', 'hero'), ('offer',), ('offer', 'tiers', 0),
        ('offer', 'tiers', 0, 'server'), ('internal',), ('internal', 'servers', 'starter'),
    ])
    def test_document_rejects_unknown_fields(self, building_on_demand_seed_content, path):
        """Fails if unknown document fields survive shape validation."""
        target = _object_at(building_on_demand_seed_content, path)
        target['unexpected'] = 'ignored'

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.code == 'VALIDATION_ERROR'
        assert error.value.details == {'path': _path_name(path)}

    @pytest.mark.parametrize(('path', 'key'), [
        ((), 'internal'), (('en',), 'legal'), (('es', 'hero'), 'positioning'),
        (('offer', 'tiers', 0), 'discounts'), (('internal',), 'hour_cost'),
    ])
    def test_document_rejects_missing_fields(self, building_on_demand_seed_content, path, key):
        """Fails if a stored document omits a required field."""
        del _object_at(building_on_demand_seed_content, path)[key]

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': _path_name(path)}
        assert error.value.message == 'Incluye todos los campos requeridos y ningún campo desconocido.'

    def test_seed_document_is_valid(self, building_on_demand_seed_content):
        """Fails if the literal deployment seed violates the live content contract."""
        validated = validate_content(building_on_demand_seed_content)

        assert validated == building_on_demand_seed_content
        assert tuple(validated['es']) == TEXT_SECTION_KEYS


def _object_at(content, path):
    target = content
    for key in path:
        target = target[key]
    return target


class TestPublicText:
    @pytest.mark.parametrize('value', [None, 42])
    def test_public_title_requires_text(self, building_on_demand_seed_content, value):
        """Fails if public titles accept values that are not strings."""
        error = _field_error(building_on_demand_seed_content, ('es', 'hero', 'title'), value)

        assert error.message == 'Debe ser texto.'
        assert error.details == {'path': 'es.hero.title'}

    @pytest.mark.parametrize('value', ['', '  ', 'x' * 121])
    def test_public_title_rejects_invalid_length(self, building_on_demand_seed_content, value):
        """Fails if a public title is blank or exceeds its documented limit."""
        error = _field_error(building_on_demand_seed_content, ('es', 'hero', 'title'), value)

        assert error.code == 'VALIDATION_ERROR'
        assert error.message == 'El texto es obligatorio y debe respetar la longitud máxima.'

    @pytest.mark.parametrize('value', ['Ahorra 5%', 'Desde $100', 'Precio €20', 'Precio COP', 'Tarifa usd', 'Cobro EUR'])
    def test_public_title_rejects_figures(self, building_on_demand_seed_content, value):
        """Fails if public copy duplicates offer figures or monetary currencies."""
        error = _field_error(building_on_demand_seed_content, ('es', 'hero', 'title'), value)

        assert error.code == 'PUBLIC_FIGURE_NOT_ALLOWED'
        assert error.details == {'path': 'es.hero.title'}

    @pytest.mark.parametrize('slug', ['Upper', 'bad id', 'two--hyphens'])
    def test_card_identifiers_require_slugs(self, building_on_demand_seed_content, slug):
        """Fails if a public card accepts an unstable identifier format."""
        error = _field_error(building_on_demand_seed_content, ('es', 'cell', 'roles', 0, 'id'), slug)

        assert error.message == 'id debe ser un slug en minúsculas.'
        assert error.details == {'path': 'es.cell.roles[0].id'}

    def test_public_text_permits_plain_digits(self, building_on_demand_seed_content):
        """Fails if the public figure guard incorrectly rejects plain legal numerals."""
        building_on_demand_seed_content['es']['legal']['disclaimer'] = 'Conforme a la Ley 1581, contamos con 4 principios.'

        result = validate_content(building_on_demand_seed_content)

        assert result['es']['legal']['disclaimer'] == 'Conforme a la Ley 1581, contamos con 4 principios.'

    def test_normalization_preserves_the_input(self, building_on_demand_seed_content):
        """Fails if whitespace normalization mutates the source revision."""
        building_on_demand_seed_content['es']['hero']['title'] = '  Una célula a tu lado.  '
        building_on_demand_seed_content['internal']['provider'] = '  Hostinger  '

        result = validate_content(building_on_demand_seed_content)

        assert result['es']['hero']['title'] == 'Una célula a tu lado.'
        assert result['internal']['provider'] == 'Hostinger'
        assert building_on_demand_seed_content['es']['hero']['title'] == '  Una célula a tu lado.  '

    def test_private_text_permits_currency_mentions(self, building_on_demand_seed_content):
        """Fails if the public copy restriction leaks into private provider data."""
        building_on_demand_seed_content['internal']['provider'] = 'Proveedor COP USD EUR % $ €'

        result = validate_content(building_on_demand_seed_content)

        assert result['internal']['provider'] == 'Proveedor COP USD EUR % $ €'


class TestDocumentLists:
    @pytest.mark.parametrize('value', [None, {}, ('role',)])
    def test_public_roles_require_a_list(self, building_on_demand_seed_content, value):
        """Fails if roles accept a non-list structure."""
        error = _field_error(building_on_demand_seed_content, ('es', 'cell', 'roles'), value)

        assert error.details == {'path': 'es.cell.roles'}
        assert error.message == 'La lista debe tener entre 1 y 10 elementos.'

    @pytest.mark.parametrize('path', [
        ('es', 'fit', 'good_for'), ('es', 'tiers', 'items'), ('es', 'faq', 'items'),
        ('offer', 'terms'), ('offer', 'tiers'), ('offer', 'estimator', 'tasks'),
    ])
    def test_required_collections_reject_empty_lists(self, building_on_demand_seed_content, path):
        """Fails if a required public or numeric collection can become empty."""
        error = _field_error(building_on_demand_seed_content, path, [])

        assert error.code == 'VALIDATION_ERROR'
        assert error.details == {'path': _path_name(path)}

    @pytest.mark.parametrize(('path', 'maximum'), [
        (('es', 'cell', 'roles'), 10), (('es', 'bag', 'rules'), 8), (('es', 'faq', 'items'), 15),
    ])
    def test_public_collections_enforce_size_limits(self, building_on_demand_seed_content, path, maximum):
        """Fails if a public collection exceeds its allowed number of entries."""
        item = _object_at(building_on_demand_seed_content, path)[0]

        error = _field_error(building_on_demand_seed_content, path, [item] * (maximum + 1))

        assert error.details == {'path': _path_name(path)}
        assert error.message == f'La lista debe tener entre 1 y {maximum} elementos.'

    @pytest.mark.parametrize('path', [
        ('es', 'cell', 'roles'), ('es', 'faq', 'items'), ('offer', 'terms'),
        ('offer', 'tiers'), ('offer', 'estimator', 'tasks'),
    ])
    def test_collections_reject_duplicate_ids(self, building_on_demand_seed_content, path):
        """Fails if a list accepts multiple items with one stable identifier."""
        entries = _object_at(building_on_demand_seed_content, path)
        entries[1]['id'] = entries[0]['id']

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': _path_name(path)}
        assert error.value.message == 'No repitas ids dentro de la lista.'


class TestBilingualAlignment:
    @pytest.mark.parametrize('path', [
        ('cell', 'roles'), ('fit', 'good_for'), ('fit', 'not_for'), ('tiers', 'items'),
        ('terms', 'items'), ('bag', 'rules'), ('hosting', 'features'), ('estimator', 'tasks'), ('faq', 'items'),
    ])
    def test_translation_collections_require_matching_ids(self, building_on_demand_seed_content, path):
        """Fails if translated items stop referring to the same public content."""
        _object_at(building_on_demand_seed_content['en'], path)[0]['id'] = 'different'

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': f'{_path_name(path)}[0].id'}

    @pytest.mark.parametrize('path', [('faq', 'items'), ('tiers', 'items', 0, 'roles')])
    def test_translation_lists_require_matching_lengths(self, building_on_demand_seed_content, path):
        """Fails if translated lists omit visible entries from one language."""
        _object_at(building_on_demand_seed_content['en'], path).pop()

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': _path_name(path)}
        assert error.value.message == 'Las listas deben tener la misma longitud en ambos idiomas.'

    def test_translated_items_require_matching_order(self, building_on_demand_seed_content):
        """Fails if translated FAQ entries can appear in a different order."""
        building_on_demand_seed_content['en']['faq']['items'].reverse()

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': 'faq.items[0].id'}

    @pytest.mark.parametrize('path', [('tiers', 'items'), ('terms', 'items'), ('estimator', 'tasks')])
    def test_public_item_ids_match_the_offer(self, building_on_demand_seed_content, path):
        """Fails if matching translations reference an item absent from the offer."""
        _object_at(building_on_demand_seed_content['es'], path)[0]['id'] = 'different'
        _object_at(building_on_demand_seed_content['en'], path)[0]['id'] = 'different'

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': f'es.{_path_name(path)}'}

    @pytest.mark.parametrize('tier_id', ['starter', 'unknown'])
    def test_private_server_keys_match_tier_ids(self, building_on_demand_seed_content, tier_id):
        """Fails if private hosting costs omit or invent a public tier."""
        servers = building_on_demand_seed_content['internal']['servers']
        servers[tier_id] = servers.pop('starter')
        servers.pop('business')

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': 'internal.servers'}


class TestOfferTypes:
    @pytest.mark.parametrize('value', [0, 1, None, 'false'])
    def test_tax_setting_requires_a_real_boolean(self, building_on_demand_seed_content, value):
        """Fails if truthy values can stand in for the tax inclusion boolean."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'prices_include_vat'), value)

        assert error.message == 'Usa un booleano verdadero o falso.'
        assert error.details == {'path': 'offer.prices_include_vat'}

    @pytest.mark.parametrize('value', [0, 1, 'true'])
    def test_recommendation_requires_a_real_boolean(self, building_on_demand_seed_content, value):
        """Fails if a recommendation flag accepts values other than booleans."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 0, 'recommended'), value)

        assert error.details == {'path': 'offer.tiers[0].recommended'}
        assert error.message == 'Usa un booleano verdadero o falso.'

    @pytest.mark.parametrize('value', [True, 1.5, '6'])
    def test_bag_days_require_an_integer(self, building_on_demand_seed_content, value):
        """Fails if booleans or coerced numbers can alter the monthly bag."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'days_per_week'), value)

        assert error.message == 'Usa un entero entre 1 y 7.'

    @pytest.mark.parametrize(('key', 'value'), [('days_per_week', 0), ('days_per_week', 8), ('weeks_per_month', 0), ('weeks_per_month', 6)])
    def test_bag_settings_enforce_calendar_bounds(self, building_on_demand_seed_content, key, value):
        """Fails if bag calculation permits impossible calendar factors."""
        error = _field_error(building_on_demand_seed_content, ('offer', key), value)

        assert error.details == {'path': f'offer.{key}'}
        assert error.code == 'VALIDATION_ERROR'

    def test_offer_currency_is_cop(self, building_on_demand_seed_content):
        """Fails if the offer accepts a currency that its calculations do not support."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'currency'), 'USD')

        assert error.details == {'path': 'offer.currency'}
        assert error.message == 'Usa uno de los valores permitidos.'

    @pytest.mark.parametrize(('index', 'value'), [(1, False), (0, True)])
    def test_offer_requires_one_recommended_tier(self, building_on_demand_seed_content, index, value):
        """Fails if the offer has no recommended tier or more than one."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', index, 'recommended'), value)

        assert error.details == {'path': 'offer.tiers'}
        assert error.message == 'Debe haber exactamente un nivel recomendado.'


class TestTierBounds:
    @pytest.mark.parametrize(('field', 'value'), [('monthly_price', 99999), ('monthly_price', 1000000001), ('daily_hours', 0), ('daily_hours', 25)])
    def test_tier_quantities_enforce_bounds(self, building_on_demand_seed_content, field, value):
        """Fails if a tier's monetary price or available daily hours exceed bounds."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 0, field), value)

        assert error.details == {'path': f'offer.tiers[0].{field}'}
        assert error.code == 'VALIDATION_ERROR'

    @pytest.mark.parametrize(('field', 'value'), [
        ('vcpu', 0), ('vcpu', 257), ('ram_gb', 0), ('ram_gb', 2049),
        ('disk_gb', 0), ('disk_gb', 100001), ('transfer_tb', 0), ('transfer_tb', 1001),
    ])
    def test_server_capacity_enforces_bounds(self, building_on_demand_seed_content, field, value):
        """Fails if a server's capacity falls outside the allowed range."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 0, 'server', field), value)

        assert error.details == {'path': f'offer.tiers[0].server.{field}'}
        assert error.code == 'VALIDATION_ERROR'

    @pytest.mark.parametrize('value', [-1, 61, True])
    def test_discount_quantities_enforce_bounds(self, building_on_demand_seed_content, value):
        """Fails if discounts accept invalid percentages or a boolean."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 0, 'discounts', 'quarterly'), value)

        assert error.message == 'Usa un entero entre 0 y 60.'
        assert error.details == {'path': 'offer.tiers[0].discounts.quarterly'}


class TestOrderedOffer:
    @pytest.mark.parametrize(('field', 'value'), [('id', 'other'), ('months', 2)])
    def test_first_term_is_monthly(self, building_on_demand_seed_content, field, value):
        """Fails if the first offer term stops representing one monthly payment."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'terms', 0, field), value)

        assert error.details == {'path': 'offer.terms[0]'}
        assert error.message == 'El primer plazo debe ser monthly y durar un mes.'

    @pytest.mark.parametrize('value', [0, 37])
    def test_term_months_enforce_bounds(self, building_on_demand_seed_content, value):
        """Fails if a term duration exceeds the supported number of months."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'terms', 1, 'months'), value)

        assert error.details == {'path': 'offer.terms[1].months'}
        assert error.message == 'Usa un entero entre 1 y 36.'

    @pytest.mark.parametrize('value', [3, 2])
    def test_term_months_increase_strictly(self, building_on_demand_seed_content, value):
        """Fails if later terms repeat or reduce the previous duration."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'terms', 2, 'months'), value)

        assert error.details == {'path': 'offer.terms[2].months'}
        assert error.message == 'Los valores deben ser estrictamente crecientes.'

    @pytest.mark.parametrize(('field', 'value'), [('monthly_price', 1800000), ('monthly_price', 1700000), ('daily_hours', 4), ('daily_hours', 3)])
    def test_tier_quantities_increase_strictly(self, building_on_demand_seed_content, field, value):
        """Fails if a larger tier repeats or reduces its price or daily hours."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 1, field), value)

        assert error.details == {'path': f'offer.tiers[1].{field}'}
        assert error.message == 'Los valores deben ser estrictamente crecientes.'

    @pytest.mark.parametrize('field', ['vcpu', 'ram_gb', 'disk_gb', 'transfer_tb'])
    def test_larger_tiers_keep_server_capacity(self, building_on_demand_seed_content, field):
        """Fails if a larger tier offers less server capacity than the prior tier."""
        value = building_on_demand_seed_content['offer']['tiers'][1]['server'][field] - 1

        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 2, 'server', field), value)

        assert error.details == {'path': f'offer.tiers[2].server.{field}'}
        assert error.message == 'La capacidad del servidor no puede disminuir entre niveles.'

    @pytest.mark.parametrize('discounts', [
        {'quarterly': 5, 'semiannual': 10},
        {'quarterly': 5, 'semiannual': 10, 'nine-month': 15, 'annual': 20},
        {'monthly': 0, 'quarterly': 5, 'semiannual': 10, 'nine-month': 15},
    ])
    def test_tier_discounts_match_nonmonthly_terms(self, building_on_demand_seed_content, discounts):
        """Fails if tier discounts omit, invent or explicitly include the monthly term."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 0, 'discounts'), discounts)

        assert error.details == {'path': 'offer.tiers[0].discounts'}
        assert error.message == 'Incluye un descuento para cada plazo, excepto el mensual.'

    @pytest.mark.parametrize(('field', 'value'), [('quarterly', 0), ('semiannual', 5), ('semiannual', 4)])
    def test_longer_terms_have_larger_discounts(self, building_on_demand_seed_content, field, value):
        """Fails if a term's discount is zero, equal to or below the shorter term."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'tiers', 0, 'discounts', field), value)

        assert error.details == {'path': f'offer.tiers[0].discounts.{field}'}
        assert error.message == 'A mayor plazo, el descuento debe ser mayor y positivo.'


class TestEstimator:
    @pytest.mark.parametrize('length', [3, 5])
    def test_estimator_requires_four_sizes(self, building_on_demand_seed_content, length):
        """Fails if an estimator size can be added or removed."""
        sizes = building_on_demand_seed_content['offer']['estimator']['sizes']
        sizes = (sizes + [sizes[-1]])[:length]

        error = _field_error(building_on_demand_seed_content, ('offer', 'estimator', 'sizes'), sizes)

        assert error.details == {'path': 'offer.estimator.sizes'}
        assert error.message == 'La lista debe tener entre 4 y 4 elementos.'

    def test_estimator_sizes_keep_fixed_order(self, building_on_demand_seed_content):
        """Fails if fixed estimator sizes are reordered."""
        building_on_demand_seed_content['offer']['estimator']['sizes'].reverse()

        with pytest.raises(BuildingOnDemandError) as error:
            validate_content(building_on_demand_seed_content)

        assert error.value.details == {'path': 'offer.estimator.sizes[0].id'}

    @pytest.mark.parametrize(('field', 'value'), [('hours_min', 0), ('hours_max', 1001), ('hours_min', True)])
    def test_estimator_hours_enforce_bounds(self, building_on_demand_seed_content, field, value):
        """Fails if estimation hours fall outside integer bounds."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'estimator', 'sizes', 0, field), value)

        assert error.details == {'path': f'offer.estimator.sizes[0].{field}'}
        assert error.message == 'Usa un entero entre 1 y 1000.'

    @pytest.mark.parametrize('value', [7, 8])
    def test_estimator_range_has_positive_width(self, building_on_demand_seed_content, value):
        """Fails if an estimation range has an equal or inverted lower bound."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'estimator', 'sizes', 0, 'hours_min'), value)

        assert error.details == {'path': 'offer.estimator.sizes[0].hours_max'}
        assert error.message == 'El límite superior debe ser mayor que el inferior.'

    def test_estimator_lower_bounds_do_not_decrease(self, building_on_demand_seed_content):
        """Fails if a later estimation size starts below the previous one."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'estimator', 'sizes', 1, 'hours_min'), 1)

        assert error.details == {'path': 'offer.estimator.sizes[1].hours_min'}

    @pytest.mark.parametrize('value', [20, 19])
    def test_estimator_upper_bounds_increase_strictly(self, building_on_demand_seed_content, value):
        """Fails if later size ranges repeat or reduce their upper bound."""
        building_on_demand_seed_content['offer']['estimator']['sizes'][2]['hours_min'] = 10

        error = _field_error(building_on_demand_seed_content, ('offer', 'estimator', 'sizes', 2, 'hours_max'), value)

        assert error.details == {'path': 'offer.estimator.sizes[2].hours_max'}

    def test_estimator_lower_bounds_may_be_equal(self, building_on_demand_seed_content):
        """Fails if non-decreasing lower bounds are treated as strictly increasing."""
        building_on_demand_seed_content['offer']['estimator']['sizes'][1]['hours_min'] = 2

        result = validate_content(building_on_demand_seed_content)

        assert result['offer']['estimator']['sizes'][1]['hours_min'] == 2

    @pytest.mark.parametrize(('field', 'value'), [('size', 'xl'), ('min_tier', 'absent')])
    def test_estimator_tasks_require_existing_references(self, building_on_demand_seed_content, field, value):
        """Fails if a task references an unknown estimation size or tier."""
        error = _field_error(building_on_demand_seed_content, ('offer', 'estimator', 'tasks', 0, field), value)

        assert error.details == {'path': f'offer.estimator.tasks[0].{field}'}
        assert error.code == 'VALIDATION_ERROR'


class TestPrivateEconomics:
    @pytest.mark.parametrize(('path', 'value'), [
        (('hour_cost',), 999), (('hour_cost',), 10000001), (('vat_percent',), -1), (('vat_percent',), 51),
        (('servers', 'starter', 'promo_monthly'), -1), (('servers', 'starter', 'renewal_monthly'), 0),
        (('provider',), 'x' * 81), (('servers', 'starter', 'plan'), 'x' * 41),
    ])
    def test_private_economics_enforce_bounds(self, building_on_demand_seed_content, path, value):
        """Fails if private cost inputs exceed their numeric or text limits."""
        error = _field_error(building_on_demand_seed_content, ('internal', *path), value)

        assert error.details == {'path': f'internal.{_path_name(path)}'}
        assert error.code == 'VALIDATION_ERROR'

    @pytest.mark.parametrize('value', ['2026-02-30', '2026-10-1', '20261010', '2026-13-01'])
    def test_cost_consultation_requires_an_iso_date(self, building_on_demand_seed_content, value):
        """Fails if the consultation date is malformed or does not exist."""
        error = _field_error(building_on_demand_seed_content, ('internal', 'consulted_on'), value)

        assert error.details == {'path': 'internal.consulted_on'}
        assert error.code == 'VALIDATION_ERROR'

    @pytest.mark.parametrize('value', [
        'http://example.com', 'https://', 'https://host:bad', 'https://exa mple.com',
        'x' * 301, 'https://example..com', 'https://example.com/path\x00',
    ])
    def test_cost_reference_requires_an_https_url(self, building_on_demand_seed_content, value):
        """Fails if the reference URL is insecure, malformed or too long."""
        error = _field_error(building_on_demand_seed_content, ('internal', 'reference_url'), value)

        assert error.details == {'path': 'internal.reference_url'}
        assert error.code == 'VALIDATION_ERROR'

    def test_zero_promotional_cost_is_valid(self, building_on_demand_seed_content):
        """Fails if a free introductory hosting promotion is rejected."""
        building_on_demand_seed_content['internal']['servers']['starter']['promo_monthly'] = 0

        result = validate_content(building_on_demand_seed_content)

        assert result['internal']['servers']['starter']['promo_monthly'] == 0


class TestSectionsSettings:
    def test_section_update_requires_both_languages(self, building_on_demand_seed_content):
        """Fails if a section update silently retains a stale translation."""
        sections = {'hero': {'es': building_on_demand_seed_content['es']['hero']}}

        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(sections, section_json_schema(), 'sections')

        assert error.value.details == {'path': 'sections.hero'}

    def test_section_update_requires_the_complete_section(self):
        """Fails if a replacement section accepts partial language content."""
        sections = {'hero': {'es': {'title': 'Nueva portada'}, 'en': {'title': 'New cover'}}}

        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(sections, section_json_schema(), 'sections')

        assert error.value.details == {'path': 'sections.hero.es'}

    def test_section_update_rejects_unknown_sections(self):
        """Fails if an update introduces a section outside the presentation contract."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema({'unexpected': {}}, section_json_schema(), 'sections')

        assert error.value.details == {'path': 'sections'}

    def test_section_validator_rejects_unknown_names(self):
        """Fails if direct section validation accepts an unknown name."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_section('unknown', {})

        assert error.value.message == 'Sección desconocida.'
        assert error.value.details == {'path': 'unknown'}

    def test_section_validator_checks_item_alignment(self, building_on_demand_seed_content):
        """Fails if direct section validation permits differently identified roles."""
        section = {'es': building_on_demand_seed_content['es']['cell'], 'en': building_on_demand_seed_content['en']['cell']}
        section['en']['roles'][0]['id'] = 'other'

        with pytest.raises(BuildingOnDemandError) as error:
            validate_section('cell', section)

        assert error.value.details == {'path': 'cell.roles[0].id'}

    @pytest.mark.parametrize('value', [{}, {'currency': 'COP'}, {'days_per_week': 0}, {'prices_include_vat': 1}])
    def test_settings_patch_rejects_invalid_configuration(self, value):
        """Fails if settings updates bypass their closed schema or scalar bounds."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(value, settings_json_schema(), 'settings')

        assert error.value.code == 'VALIDATION_ERROR'
        assert error.value.details['path'].startswith('settings')

    def test_settings_patch_accepts_one_property(self):
        """Fails if a legal partial settings update requires unrelated properties."""
        result = validate_schema({'days_per_week': 7}, settings_json_schema(), 'settings')

        assert result == {'days_per_week': 7}

    def test_section_update_normalizes_whatsapp_copy(self, building_on_demand_seed_content):
        """Fails if a bilingual section update retains whitespace in contact copy."""
        sections = {'cta': {'es': building_on_demand_seed_content['es']['cta'], 'en': building_on_demand_seed_content['en']['cta']}}
        sections['cta']['es']['whatsapp_message'] = '  Quiero conversar sobre mi producto.  '

        result = validate_schema(sections, section_json_schema(), 'sections')

        assert result['cta']['es']['whatsapp_message'] == 'Quiero conversar sobre mi producto.'


class TestItemSchemas:
    @pytest.mark.parametrize('builder', FULL_ITEM_BUILDERS)
    def test_item_creation_requires_its_complete_shape(self, builder):
        """Fails if item creation permits missing language or numeric data."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema({'id': 'new-item'}, builder(), 'item')

        assert error.value.details == {'path': 'item'}
        assert error.value.message == 'Incluye todos los campos requeridos y ningún campo desconocido.'

    @pytest.mark.parametrize('builder', FULL_ITEM_BUILDERS)
    def test_item_patch_forbids_identifier_changes(self, builder):
        """Fails if an update can change the stable id used by other items."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema({'id': 'changed'}, builder(partial=True), 'changes')

        assert error.value.details == {'path': 'changes'}

    @pytest.mark.parametrize('builder', FULL_ITEM_BUILDERS)
    def test_item_patch_rejects_unknown_translated_fields(self, builder):
        """Fails if unknown translated patch keys disappear during a merge."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema({'es': {'unexpected': 'Ignored'}}, builder(partial=True), 'changes')

        assert error.value.details == {'path': 'changes.es'}

    @pytest.mark.parametrize('builder', FULL_ITEM_BUILDERS)
    def test_item_patch_requires_at_least_one_change(self, builder):
        """Fails if an empty item patch passes input validation."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema({}, builder(partial=True), 'changes')

        assert error.value.details == {'path': 'changes'}
        assert error.value.message == 'Incluye al menos un campo para actualizar.'


class TestNestedPatches:
    @pytest.mark.parametrize('changes', [
        {'monthly_price': 2000000}, {'server': {'vcpu': 2}}, {'hosting': {'renewal_monthly': 40000}},
        {'discounts': {'quarterly': 6}}, {'es': {'name': '  Inicial  '}},
    ])
    def test_tier_patch_accepts_nested_partial_data(self, changes):
        """Fails if a nested tier update unnecessarily requires a whole item."""
        original = deepcopy(changes)

        result = validate_schema(changes, tier_json_schema(partial=True), 'changes')

        assert result == _trim_fixture_text(original)
        assert changes == original

    @pytest.mark.parametrize('changes', [
        {'server': {'unknown': 1}}, {'hosting': {'unknown': 1}}, {'server': {}}, {'en': {}},
        {'discounts': {'Invalid Key': 10}},
    ])
    def test_tier_patch_rejects_invalid_nested_data(self, changes):
        """Fails if a partial nested tier patch can hide unknown or empty inputs."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(changes, tier_json_schema(partial=True), 'changes')

        assert error.value.code == 'VALIDATION_ERROR'
        assert error.value.details['path'].startswith('changes.')

    @pytest.mark.parametrize('changes', [
        {'hour_cost': 60000}, {'servers': {'starter': {'renewal_monthly': 40000}}},
        {'provider': 'Hostinger COP %'},
    ])
    def test_economics_patch_accepts_private_partial_data(self, changes):
        """Fails if a private patch requires all economics data or rejects figures."""
        result = validate_schema(changes, economics_json_schema(), 'economics')

        assert result == changes

    @pytest.mark.parametrize('changes', [{}, {'servers': {'starter': {}}}, {'servers': {'starter': {'unknown': 5}}}])
    def test_economics_patch_rejects_invalid_server_inputs(self, changes):
        """Fails if private server changes bypass the partial closed schema."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(changes, economics_json_schema(), 'economics')

        assert error.value.code == 'VALIDATION_ERROR'
        assert error.value.details['path'].startswith('economics')

    def test_translated_patch_rejects_public_figures(self):
        """Fails if figure restrictions apply only after patch merging."""
        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema({'en': {'summary': 'Costs USD'}}, card_json_schema(partial=True), 'changes')

        assert error.value.code == 'PUBLIC_FIGURE_NOT_ALLOWED'
        assert error.value.details == {'path': 'changes.en.summary'}

    def test_private_tier_keys_do_not_change_text_rules(self):
        """Fails if a tier named es activates public restrictions on private plans."""
        changes = {'servers': {'es': {'plan': 'Plan COP %'}}}

        result = validate_schema(changes, economics_json_schema(), 'economics')

        assert result == changes

    def test_discount_patches_reject_normalized_duplicate_keys(self):
        """Fails if whitespace normalization silently replaces a discount value."""
        changes = {'discounts': {'quarterly': 5, ' quarterly ': 6}}

        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(changes, tier_json_schema(partial=True), 'changes')

        assert error.value.details == {'path': 'changes.discounts'}
        assert error.value.message == 'No repitas identificadores dentro del objeto.'

    def test_discount_patch_normalizes_term_keys(self):
        """Fails if normalized term ids cannot merge into the existing discounts."""
        result = validate_schema({'discounts': {' quarterly ': 6}}, tier_json_schema(partial=True), 'changes')

        assert result == {'discounts': {'quarterly': 6}}


def _trim_fixture_text(value):
    if isinstance(value, dict):
        return {key: _trim_fixture_text(child) for key, child in value.items()}
    if isinstance(value, str):
        return value.strip()
    return value


class TestPublishedSchemas:
    @pytest.mark.parametrize('builder', SCHEMA_BUILDERS)
    def test_tool_schemas_publish_explicit_closed_shapes(self, builder):
        """Fails if published tool schemas omit descriptions or permit unknown keys."""
        schema = builder()

        assert _schema_issues(schema) == []

    @pytest.mark.parametrize('builder', FULL_ITEM_BUILDERS)
    def test_full_item_schema_requires_every_property(self, builder):
        """Fails if a create schema publishes any top-level field as optional."""
        schema = builder()

        assert schema['required'] == list(schema['properties'])
        assert schema['properties']['es']['required'] == list(schema['properties']['es']['properties'])

    def test_schema_builders_return_independent_documents(self):
        """Fails if a caller can mutate future schemas by editing a returned document."""
        schema = tier_json_schema()
        schema['properties']['es']['properties']['name']['maxLength'] = 999

        fresh = tier_json_schema()

        assert fresh['properties']['es']['properties']['name']['maxLength'] == 40

    def test_size_schema_rejects_reordering_before_merge(self, building_on_demand_seed_content):
        """Fails if the fixed-size input schema accepts a reordered list."""
        sizes = list(reversed(building_on_demand_seed_content['offer']['estimator']['sizes']))

        with pytest.raises(BuildingOnDemandError) as error:
            validate_schema(sizes, estimator_sizes_json_schema(), 'sizes')

        assert error.value.details == {'path': 'sizes[0].id'}


class TestCanonicalHash:
    def test_hash_ignores_object_key_order(self):
        """Fails if semantically identical objects acquire different revision hashes."""
        left = {'es': {'title': 'Célula'}, 'offer': {'days': 6}}
        right = {'offer': {'days': 6}, 'es': {'title': 'Célula'}}

        assert canonical_hash(left) == canonical_hash(right)
        assert canonical_hash(left) == hashlib.sha256(json.dumps(left, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

    def test_hash_preserves_list_order(self):
        """Fails if reordering visible items produces the same revision hash."""
        original = {'ids': ['starter', 'business']}
        reordered = {'ids': ['business', 'starter']}

        assert canonical_hash(original) != canonical_hash(reordered)

    def test_hash_changes_with_private_costs(self):
        """Fails if a private economics change leaves the canonical content hash stale."""
        before = {'internal': {'hour_cost': 55000}}
        after = {'internal': {'hour_cost': 60000}}

        assert canonical_hash(before) != canonical_hash(after)
