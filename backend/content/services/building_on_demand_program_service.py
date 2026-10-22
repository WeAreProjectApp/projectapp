"""Versioned cell presentation and previewable operations for its MCP connector."""
import hashlib
import json
import re
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP, localcontext
from math import isfinite
from urllib.parse import quote

from django.db import transaction

from content.models import BuildingOnDemandProgram, BuildingOnDemandProgramRevision, McpConnector
from content.services.building_on_demand_content import (
    BuildingOnDemandError, TEXT_SECTION_KEYS, canonical_hash, validate_content, validate_schema,
    section_json_schema, settings_json_schema, tier_json_schema, term_json_schema,
    estimator_task_json_schema, faq_json_schema, card_json_schema, estimator_sizes_json_schema,
    economics_json_schema,
)
from content.services.contract_template_validation import markdown_diff
from content.services.financing_program_service import WHATSAPP_NUMBER
from content.services.frontend_build import schedule_rebuild_after_publish

PUBLIC_PATHS = {'es': '/es-co/building-on-demand', 'en': '/en-us/building-on-demand'}
_CARD_COLLECTIONS = {
    'roles': ('cell', 'roles'), 'bag_rules': ('bag', 'rules'),
    'hosting_features': ('hosting', 'features'), 'good_for': ('fit', 'good_for'),
    'not_for': ('fit', 'not_for'),
}
_TEXT_COLLECTIONS = {
    'tiers': ('tiers', 'items'), 'terms': ('terms', 'items'),
    'estimator_tasks': ('estimator', 'tasks'), 'faq': ('faq', 'items'), **_CARD_COLLECTIONS,
}
_CONTRACT_WARNING = 'El contrato cita planes y precios: revísalo.'
_SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def _load(*, lock=False):
    try:
        return BuildingOnDemandProgram.load(lock=lock)
    except BuildingOnDemandProgram.DoesNotExist as exc:
        raise BuildingOnDemandError('La presentación no está configurada.', code='NOT_FOUND') from exc


def program_etag(revision):
    identity = f'bod:program:{revision.pk}:{revision.version}:{canonical_hash(revision.content)}'
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


def resource_etags(arguments=None):
    return {'program': program_etag(_load().current_revision)}


def _metadata(program):
    revision = program.current_revision
    return {
        'version': revision.version, 'version_id': revision.pk, 'updated_at': program.updated_at.isoformat(),
        'author': revision.author_label, 'change_note': revision.change_note, 'etag': program_etag(revision),
    }


def _round(value, quantum='1'):
    return value.quantize(Decimal(quantum), rounding=ROUND_HALF_UP)


def _bag_hours(tier, offer):
    return tier['daily_hours'] * offer['days_per_week'] * offer['weeks_per_month']


def _prices(tier, terms):
    prices = []
    for term in terms:
        discount = tier['discounts'].get(term['id'], 0)
        monthly = int(_round(Decimal(tier['monthly_price']) * (100 - discount) / 100))
        prices.append({
            'term': term['id'], 'months': term['months'], 'discount_percent': discount,
            'monthly_price': monthly, 'total': monthly * term['months'],
            'savings': (tier['monthly_price'] - monthly) * term['months'],
        })
    return prices


def _derived(content):
    offer = content['offer']
    return {'tiers': [
        {'id': tier['id'], 'bag_hours': _bag_hours(tier, offer), 'prices': _prices(tier, offer['terms'])}
        for tier in offer['tiers']
    ]}


def read_program():
    program = _load()
    content = validate_content(program.current_revision.content)
    return {**_metadata(program), 'sections': list(TEXT_SECTION_KEYS), 'content': content, 'derived': _derived(content)}


def serialize_public_program(lang):
    if not isinstance(lang, str) or lang not in PUBLIC_PATHS:
        raise BuildingOnDemandError('Usa es o en.', code='INVALID_LANGUAGE')
    program = _load()
    content = validate_content(program.current_revision.content)
    offer = content['offer']
    payload = deepcopy(content[lang])
    for text, tier in zip(payload['tiers']['items'], offer['tiers']):
        text.update({
            'recommended': tier['recommended'], 'monthly_price': tier['monthly_price'],
            'daily_hours': tier['daily_hours'], 'bag_hours': _bag_hours(tier, offer),
            'server': deepcopy(tier['server']), 'prices': _prices(tier, offer['terms']),
        })
    for text, term in zip(payload['terms']['items'], offer['terms']):
        text['months'] = term['months']
    payload['estimator']['sizes'] = deepcopy(offer['estimator']['sizes'])
    for text, task in zip(payload['estimator']['tasks'], offer['estimator']['tasks']):
        text.update({'size': task['size'], 'min_tier': task['min_tier']})
    message = payload['cta'].pop('whatsapp_message')
    base_url = f'https://wa.me/{WHATSAPP_NUMBER}'
    payload['cta']['whatsapp_url'] = base_url + '?text=' + quote(message)
    from content.services.explainer_video_service import explainer_video_visible
    from content.services.video_resource_service import public_resource
    return {
        'language': lang, 'version': program.current_revision.version, 'updated_at': program.updated_at.isoformat(),
        'canonical_path': PUBLIC_PATHS[lang], 'alternate_path': PUBLIC_PATHS['en' if lang == 'es' else 'es'],
        'pdf_path': f'/api/building-on-demand/public/pdf/?lang={lang}', **payload,
        'offer': {
            'currency': offer['currency'], 'prices_include_vat': offer['prices_include_vat'],
            'days_per_week': offer['days_per_week'], 'weeks_per_month': offer['weeks_per_month'],
            'recommended_tier': next(tier['id'] for tier in offer['tiers'] if tier['recommended']),
        },
        'contact': {'whatsapp_base_url': base_url},
        'show_explainer_video': explainer_video_visible('building-on-demand'),
        'explainer_video': public_resource('building-on-demand', lang),
    }


def economics(content=None):
    if content is None:
        content = _load().current_revision.content
    content = validate_content(content)
    precision = max(Decimal(server['renewal_monthly']).adjusted() + 1
                    for server in content['internal']['servers'].values()) + 20
    with localcontext() as context:
        context.prec = max(28, precision)
        return _economics_payload(content)


def _economics_payload(content):
    offer, internal = content['offer'], content['internal']
    names = {tier['id']: tier['name'] for tier in content['es']['tiers']['items']}
    tiers, rows = [], []
    for tier in offer['tiers']:
        server = internal['servers'][tier['id']]
        hosting_cost = int(_round(Decimal(server['renewal_monthly']) * (100 + internal['vat_percent']) / 100))
        bag_hours = _bag_hours(tier, offer)
        tiers.append({
            'id': tier['id'], 'name': names[tier['id']], 'bag_hours': bag_hours,
            **server, 'hosting_cost_monthly': hosting_cost,
        })
        for price in _prices(tier, offer['terms']):
            net_monthly = price['monthly_price'] - hosting_cost
            breakeven = Decimal(net_monthly) / internal['hour_cost']
            display_hours = float(_round(breakeven, '0.1'))
            if not isfinite(display_hours):
                _invalid(f"internal.servers.{tier['id']}.renewal_monthly",
                         'El costo de renovación es demasiado grande para expresar la economía en JSON.')
            rows.append({
                'tier': tier['id'], 'term': price['term'], 'months': price['months'],
                'monthly_price': price['monthly_price'], 'hosting_cost_monthly': hosting_cost,
                'net_monthly': net_monthly, 'breakeven_hours': display_hours,
                'breakeven_hours_rounded': int(_round(breakeven)), 'bag_hours': bag_hours,
                'bag_share_percent': int(_round(breakeven / bag_hours * 100)),
                'breakeven_hours_without_hosting': float(_round(Decimal(price['monthly_price']) / internal['hour_cost'], '0.1')),
            })
    return {
        'currency': offer['currency'],
        **{key: internal[key] for key in ('hour_cost', 'vat_percent', 'provider', 'reference_url', 'consulted_on')},
        'tiers': tiers, 'rows': rows,
    }


def list_versions(*, offset=0, limit=20, include_content=False):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50 or type(include_content) is not bool:
        raise BuildingOnDemandError('Usa offset >= 0, limit entre 1 y 50 e include_content booleano.')
    queryset = BuildingOnDemandProgramRevision.objects.select_related('restored_from')
    versions = []
    for revision in queryset[offset:offset + limit]:
        item = {
            'version_id': revision.pk, 'version': revision.version, 'author': revision.author_label,
            'created_at': revision.created_at.isoformat(), 'change_note': revision.change_note,
            'restored_from_version_id': revision.restored_from_id,
            'restored_from_version': revision.restored_from.version if revision.restored_from_id else None,
        }
        if include_content:
            item['content'] = deepcopy(revision.content)
        versions.append(item)
    return {'total': queryset.count(), 'versions': versions}


def _contract_summary():
    """Expose private contract provenance without duplicating its content."""
    from content.services.building_on_demand_contract_service import read_contract

    try:
        contract = read_contract()
    except BuildingOnDemandError as exc:
        if exc.code == 'NOT_FOUND':
            return None
        raise
    return {key: contract[key] for key in (
        'version', 'version_id', 'updated_at', 'author', 'change_note', 'mirror',
    )}


def admin_overview():
    active = McpConnector.objects.filter(slug='programs', is_active=True).exists()
    return {
        'program': _metadata(_load()), 'contract': _contract_summary(),
        'connector': {'slug': 'programs', 'is_active': active},
        'public_paths': dict(PUBLIC_PATHS),
        'pdf_paths': {lang: f'/api/building-on-demand/public/pdf/?lang={lang}' for lang in PUBLIC_PATHS},
    }


def _invalid(path, message):
    raise BuildingOnDemandError(message, details={'path': path})


def _identifier(value, path):
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        _invalid(path, 'Usa un id en minúsculas separado por guiones.')
    return value


def _find(items, item_id, path):
    for item in items:
        if item['id'] == item_id:
            return item
    raise BuildingOnDemandError('El elemento no existe.', code='NOT_FOUND', details={'path': path, 'id': item_id})


def _ensure_new(items, item_id, path):
    if any(item['id'] == item_id for item in items):
        raise BuildingOnDemandError('El id ya existe en esta lista.', code='DUPLICATE_ID', details={'path': path, 'id': item_id})


def _position(arguments, length):
    position = arguments.get('position', length)
    if type(position) is not int or not 0 <= position <= length:
        _invalid('position', f'Usa una posición entre 0 y {length}.')
    return position


def _merge(target, changes):
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _texts(content, collection, lang):
    section, key = _TEXT_COLLECTIONS[collection]
    return content[lang][section][key]


def _insert_texts(content, collection, item, position):
    for lang in ('es', 'en'):
        _texts(content, collection, lang).insert(position, {'id': item['id'], **deepcopy(item[lang])})


def _update_texts(content, collection, item_id, changes):
    for lang in ('es', 'en'):
        if lang in changes:
            _merge(_find(_texts(content, collection, lang), item_id, f'{lang}.{collection}'), changes[lang])


def _remove_texts(content, collection, item_id):
    for lang in ('es', 'en'):
        items = _texts(content, collection, lang)
        items.remove(_find(items, item_id, f'{lang}.{collection}'))


def _update_program(content, arguments):
    if not {'sections', 'settings'} & set(arguments):
        _invalid('sections', 'Incluye secciones o ajustes para actualizar.')
    if 'sections' in arguments:
        sections = validate_schema(arguments['sections'], section_json_schema(), 'sections', public_text=True)
        for key, translations in sections.items():
            for lang in ('es', 'en'):
                content[lang][key] = translations[lang]
    if 'settings' in arguments:
        _merge(content['offer'], validate_schema(arguments['settings'], settings_json_schema(), 'settings'))


def _create_tier(content, arguments):
    tier = validate_schema(arguments['tier'], tier_json_schema(), 'tier')
    tiers = content['offer']['tiers']
    _ensure_new(tiers, tier['id'], 'tier.id')
    position = _position(arguments, len(tiers))
    stored = {key: deepcopy(value) for key, value in tier.items() if key not in ('es', 'en', 'hosting')}
    if stored['recommended']:
        for current in tiers:
            current['recommended'] = False
    tiers.insert(position, stored)
    _insert_texts(content, 'tiers', tier, position)
    content['internal']['servers'][tier['id']] = tier['hosting']


def _update_tier(content, arguments):
    tier_id = _identifier(arguments['tier_id'], 'tier_id')
    tier = _find(content['offer']['tiers'], tier_id, 'tier_id')
    changes = validate_schema(arguments['changes'], tier_json_schema(partial=True), 'changes')
    if changes.get('recommended') is True:
        for current in content['offer']['tiers']:
            current['recommended'] = False
    _merge(tier, {key: value for key, value in changes.items() if key not in ('es', 'en', 'hosting')})
    if 'hosting' in changes:
        _merge(content['internal']['servers'][tier_id], changes['hosting'])
    _update_texts(content, 'tiers', tier_id, changes)


def _remove_tier(content, arguments):
    tier_id = _identifier(arguments['tier_id'], 'tier_id')
    tiers = content['offer']['tiers']
    tier = _find(tiers, tier_id, 'tier_id')
    if len(tiers) == 1:
        _invalid('tier_id', 'No puedes eliminar el último plan.')
    if tier['recommended']:
        _invalid('tier_id', 'No puedes eliminar el plan recomendado; recomienda otro primero.')
    references = [
        f'offer.estimator.tasks[{task["id"]}].min_tier'
        for task in content['offer']['estimator']['tasks'] if task['min_tier'] == tier_id
    ]
    if references:
        raise BuildingOnDemandError('El plan está usado por tareas del estimador.', code='REFERENCED_ITEM',
                                    details={'references': references})
    tiers.remove(tier)
    _remove_texts(content, 'tiers', tier_id)
    del content['internal']['servers'][tier_id]


def _create_term(content, arguments):
    term = validate_schema(arguments['term'], term_json_schema(), 'term')
    terms = content['offer']['terms']
    _ensure_new(terms, term['id'], 'term.id')
    tiers = content['offer']['tiers']
    if set(term['discounts']) != {tier['id'] for tier in tiers}:
        _invalid('term.discounts', 'Incluye un descuento para cada plan y ningún plan desconocido.')
    position = next((index for index, current in enumerate(terms) if current['months'] >= term['months']), len(terms))
    terms.insert(position, {'id': term['id'], 'months': term['months']})
    _insert_texts(content, 'terms', term, position)
    for tier in tiers:
        tier['discounts'][term['id']] = term['discounts'][tier['id']]


def _update_term(content, arguments):
    term_id = _identifier(arguments['term_id'], 'term_id')
    term = _find(content['offer']['terms'], term_id, 'term_id')
    changes = validate_schema(arguments['changes'], term_json_schema(partial=True), 'changes')
    if 'months' in changes:
        term['months'] = changes['months']
    if 'discounts' in changes:
        tiers = {tier['id']: tier for tier in content['offer']['tiers']}
        if set(changes['discounts']) - set(tiers):
            _invalid('changes.discounts', 'Los descuentos sólo admiten planes existentes.')
        if term_id == 'monthly':
            _invalid('changes.discounts', 'El plazo mensual no admite descuentos.')
        for tier_id, discount in changes['discounts'].items():
            tiers[tier_id]['discounts'][term_id] = discount
    _update_texts(content, 'terms', term_id, changes)


def _remove_term(content, arguments):
    term_id = _identifier(arguments['term_id'], 'term_id')
    terms = content['offer']['terms']
    term = _find(terms, term_id, 'term_id')
    if term_id == 'monthly':
        _invalid('term_id', 'No puedes eliminar el plazo mensual.')
    terms.remove(term)
    _remove_texts(content, 'terms', term_id)
    for tier in content['offer']['tiers']:
        del tier['discounts'][term_id]


def _create_estimator_task(content, arguments):
    task = validate_schema(arguments['task'], estimator_task_json_schema(), 'task')
    tasks = content['offer']['estimator']['tasks']
    _ensure_new(tasks, task['id'], 'task.id')
    position = _position(arguments, len(tasks))
    tasks.insert(position, {key: task[key] for key in ('id', 'size', 'min_tier')})
    _insert_texts(content, 'estimator_tasks', task, position)


def _update_estimator_task(content, arguments):
    task_id = _identifier(arguments['task_id'], 'task_id')
    task = _find(content['offer']['estimator']['tasks'], task_id, 'task_id')
    changes = validate_schema(arguments['changes'], estimator_task_json_schema(partial=True), 'changes')
    _merge(task, {key: value for key, value in changes.items() if key not in ('es', 'en')})
    _update_texts(content, 'estimator_tasks', task_id, changes)


def _remove_estimator_task(content, arguments):
    task_id = _identifier(arguments['task_id'], 'task_id')
    tasks = content['offer']['estimator']['tasks']
    tasks.remove(_find(tasks, task_id, 'task_id'))
    _remove_texts(content, 'estimator_tasks', task_id)


def _create_text_item(content, arguments, *, collection, schema):
    item = validate_schema(arguments['item'], schema(), 'item', public_text=True)
    _ensure_new(_texts(content, collection, 'es'), item['id'], 'item.id')
    _insert_texts(content, collection, item, _position(arguments, len(_texts(content, collection, 'es'))))


def _update_text_item(content, arguments, *, collection, schema):
    item_id = _identifier(arguments['item_id'], 'item_id')
    _find(_texts(content, collection, 'es'), item_id, 'item_id')
    changes = validate_schema(arguments['changes'], schema(partial=True), 'changes', public_text=True)
    _update_texts(content, collection, item_id, changes)


def _remove_text_item(content, arguments, *, collection):
    item_id = _identifier(arguments['item_id'], 'item_id')
    _find(_texts(content, collection, 'es'), item_id, 'item_id')
    _remove_texts(content, collection, item_id)


def _create_faq(content, arguments):
    _create_text_item(content, arguments, collection='faq', schema=faq_json_schema)


def _update_faq(content, arguments):
    _update_text_item(content, arguments, collection='faq', schema=faq_json_schema)


def _remove_faq(content, arguments):
    _remove_text_item(content, arguments, collection='faq')


def _card_collection(arguments):
    collection = arguments['collection']
    if not isinstance(collection, str) or collection not in _CARD_COLLECTIONS:
        _invalid('collection', 'Usa roles, bag_rules, hosting_features, good_for o not_for.')
    return collection


def _create_card(content, arguments):
    _create_text_item(content, arguments, collection=_card_collection(arguments), schema=card_json_schema)


def _update_card(content, arguments):
    _update_text_item(content, arguments, collection=_card_collection(arguments), schema=card_json_schema)


def _remove_card(content, arguments):
    _remove_text_item(content, arguments, collection=_card_collection(arguments))


def _reorder(items, ids):
    by_id = {item['id']: item for item in items}
    items[:] = [by_id[item_id] for item_id in ids]


def _reorder_items(content, arguments):
    collection = arguments['collection']
    if not isinstance(collection, str) or collection not in _TEXT_COLLECTIONS:
        _invalid('collection', 'La colección no admite reordenamiento.')
    ids = arguments['ids']
    current_ids = [item['id'] for item in _texts(content, collection, 'es')]
    if not isinstance(ids, list) or any(not isinstance(item_id, str) for item_id in ids):
        _invalid('ids', 'Incluye una permutación exacta de los ids de la colección.')
    if len(ids) != len(current_ids) or len(set(ids)) != len(ids) or set(ids) != set(current_ids):
        _invalid('ids', 'Incluye una permutación exacta de los ids de la colección.')
    for lang in ('es', 'en'):
        _reorder(_texts(content, collection, lang), ids)
    if collection in ('tiers', 'terms'):
        _reorder(content['offer'][collection], ids)
    elif collection == 'estimator_tasks':
        _reorder(content['offer']['estimator']['tasks'], ids)


def _update_estimator_sizes(content, arguments):
    content['offer']['estimator']['sizes'] = validate_schema(arguments['sizes'], estimator_sizes_json_schema(), 'sizes')


def _update_economics(content, arguments):
    changes = validate_schema(arguments['economics'], economics_json_schema(), 'economics')
    if 'servers' in changes and set(changes['servers']) - set(content['internal']['servers']):
        _invalid('economics.servers', 'Los costos de hosting sólo admiten planes existentes.')
    _merge(content['internal'], changes)


def _operation(handler, required, optional=(), *, summary):
    return {'handler': handler, 'required': set(required), 'allowed': set(required) | set(optional), 'summary': summary}


OPERATIONS = {
    'update_program': _operation(_update_program, (), ('sections', 'settings'), summary='Actualizar la presentación y sus ajustes.'),
    'restore_version': _operation(None, ('version_id',), summary='Restaurar una versión de la presentación.'),
    'create_tier': _operation(_create_tier, ('tier',), ('position',), summary='Crear un plan con sus textos y costos de hosting.'),
    'update_tier': _operation(_update_tier, ('tier_id', 'changes'), summary='Actualizar un plan.'),
    'remove_tier': _operation(_remove_tier, ('tier_id',), summary='Eliminar un plan con sus textos y costos de hosting.'),
    'create_term': _operation(_create_term, ('term',), summary='Crear un plazo con los descuentos de cada plan.'),
    'update_term': _operation(_update_term, ('term_id', 'changes'), summary='Actualizar un plazo.'),
    'remove_term': _operation(_remove_term, ('term_id',), summary='Eliminar un plazo con sus textos y descuentos.'),
    'create_estimator_task': _operation(_create_estimator_task, ('task',), ('position',), summary='Crear una tarea de referencia.'),
    'update_estimator_task': _operation(_update_estimator_task, ('task_id', 'changes'), summary='Actualizar una tarea de referencia.'),
    'remove_estimator_task': _operation(_remove_estimator_task, ('task_id',), summary='Eliminar una tarea de referencia.'),
    'create_faq': _operation(_create_faq, ('item',), ('position',), summary='Crear una pregunta frecuente.'),
    'update_faq': _operation(_update_faq, ('item_id', 'changes'), summary='Actualizar una pregunta frecuente.'),
    'remove_faq': _operation(_remove_faq, ('item_id',), summary='Eliminar una pregunta frecuente.'),
    'create_card': _operation(_create_card, ('collection', 'item'), ('position',), summary='Crear una tarjeta bilingüe.'),
    'update_card': _operation(_update_card, ('collection', 'item_id', 'changes'), summary='Actualizar una tarjeta bilingüe.'),
    'remove_card': _operation(_remove_card, ('collection', 'item_id'), summary='Eliminar una tarjeta bilingüe.'),
    'reorder_items': _operation(_reorder_items, ('collection', 'ids'), summary='Reordenar una colección en ambos idiomas.'),
    'update_estimator_sizes': _operation(_update_estimator_sizes, ('sizes',), summary='Actualizar los rangos de horas de referencia.'),
    'update_economics': _operation(_update_economics, ('economics',), summary='Actualizar los costos internos del programa.'),
}


def _diff(content, candidate):
    changes = []
    blocks = [(f'{key}.{lang}', content[lang][key], candidate[lang][key])
              for key in TEXT_SECTION_KEYS for lang in ('es', 'en')]
    blocks.extend((key, content[key], candidate[key]) for key in ('offer', 'internal'))
    for block, before, after in blocks:
        diff = markdown_diff(json.dumps(before, indent=2, sort_keys=True, ensure_ascii=False),
                             json.dumps(after, indent=2, sort_keys=True, ensure_ascii=False), block)
        changes.append({'block': block, 'changed': bool(diff), 'diff': diff})
    return changes


def _warnings(content, candidate):
    public_pricing = ('tiers', 'terms', 'days_per_week', 'weeks_per_month', 'prices_include_vat')
    changed = any(content['offer'][key] != candidate['offer'][key] for key in public_pricing)
    changed = changed or any(content[lang][key] != candidate[lang][key] for lang in ('es', 'en') for key in ('tiers', 'terms'))
    return [_CONTRACT_WARNING] if changed else []


def _prepare_operation(operation, arguments, *, program, require_match):
    if not isinstance(operation, str) or operation not in OPERATIONS:
        _invalid('operation', 'La operación no existe.')
    spec = OPERATIONS[operation]
    if not isinstance(arguments, dict) or set(arguments) - (spec['allowed'] | {'if_match', 'change_note'}):
        raise BuildingOnDemandError('Hay argumentos desconocidos.')
    etag = program_etag(program.current_revision)
    if require_match and not arguments.get('if_match'):
        raise BuildingOnDemandError('if_match es obligatorio.', code='PRECONDITION_REQUIRED')
    if 'if_match' in arguments and arguments['if_match'] != etag:
        raise BuildingOnDemandError('La presentación cambió; vuelve a leerla.', code='STALE_VERSION', details={'current_etag': etag})
    note = arguments.get('change_note', '')
    if not isinstance(note, str) or len(note.strip()) > 4000 or (require_match and not note.strip()):
        raise BuildingOnDemandError('change_note debe explicar el cambio (entre 1 y 4000 caracteres).')
    missing = spec['required'] - set(arguments)
    if missing:
        _invalid(sorted(missing)[0], 'Faltan argumentos obligatorios para la operación.')
    current = validate_content(program.current_revision.content)
    restored = None
    if operation == 'restore_version':
        version_id = arguments['version_id']
        if type(version_id) is not int or version_id < 1:
            _invalid('version_id', 'version_id debe ser un entero positivo.')
        restored = BuildingOnDemandProgramRevision.objects.filter(pk=version_id).first()
        if restored is None:
            raise BuildingOnDemandError('La versión no existe.', code='NOT_FOUND')
        candidate = deepcopy(restored.content)
    else:
        candidate = deepcopy(current)
        spec['handler'](candidate, arguments)
    candidate = validate_content(candidate)
    changes = _diff(current, candidate)
    return ({
        'operation': operation, 'changed': any(row['changed'] for row in changes), 'changes': changes,
        'warnings': _warnings(current, candidate), 'summary': spec['summary'],
        'change_note': note.strip(), 'if_match': etag, 'resource_etags': {'program': etag},
    }, candidate, restored)


def prepare_operation(operation, arguments, *, require_match=False):
    prepared, _, _ = _prepare_operation(operation, arguments, program=_load(), require_match=require_match)
    return prepared


@transaction.atomic
def apply_operation(operation, arguments, *, actor, credential=None, expected_etags=None):
    program = _load(lock=True)
    etag = program_etag(program.current_revision)
    if expected_etags is not None and expected_etags != {'program': etag}:
        raise BuildingOnDemandError('La presentación cambió desde la vista previa.', code='STALE_VERSION',
                                    details={'current_etag': etag})
    prepared, content, restored = _prepare_operation(operation, arguments, program=program, require_match=True)
    if not prepared['changed']:
        revision = program.current_revision
        return {'applied': True, 'changed': False, 'version': revision.version, 'version_id': revision.pk, 'etag': etag}
    before = program.current_revision.content
    revision = BuildingOnDemandProgramRevision.objects.create(
        version=program.current_revision.version + 1, content=content, author=actor, credential=credential,
        author_label=actor.get_username() if actor else 'Consola', change_note=prepared['change_note'], restored_from=restored,
    )
    program.current_revision = revision
    program.save(update_fields=['current_revision', 'updated_at'])
    if any(before[key] != content[key] for key in ('es', 'en', 'offer')):
        transaction.on_commit(lambda: schedule_rebuild_after_publish(reason='building-on-demand'))
    return {'applied': True, 'changed': True, 'version': revision.version, 'version_id': revision.pk, 'etag': program_etag(revision)}
