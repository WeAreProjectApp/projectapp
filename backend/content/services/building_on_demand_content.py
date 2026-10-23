"""Strict program validation and the JSON schemas shared by future MCP tools."""
import hashlib
import json
import re
from copy import deepcopy
from content.services.editorial_contract import editorial_object_schema, prepare_editorial_object, restore_editorial_object
from datetime import date
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


class BuildingOnDemandError(ValueError):
    def __init__(self, message, code='VALIDATION_ERROR', details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


TEXT_SECTION_KEYS = (
    'seo', 'hero', 'cell', 'fit', 'tiers', 'terms', 'bag',
    'estimator', 'hosting', 'faq', 'cta', 'legal',
)
FIGURES_PATTERN = r'[%$€]|\b(COP|USD|EUR)\b'
_FIGURES = re.compile(FIGURES_PATTERN, re.IGNORECASE)
_HTTPS_URL = URLValidator(schemes=['https'])
_SLUG_PATTERN = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
_PUBLIC_TEXT_PATTERN = (
    r'^(?![\s\S]*(?:[%$€]|\b(?:[cC][oO][pP]|[uU][sS][dD]|[eE][uU][rR])\b))'
    r'[\s\S]*\S[\s\S]*$'
)
SIZE_IDS = ('xs', 's', 'm', 'l')
SERVER_FIELDS = ('vcpu', 'ram_gb', 'disk_gb', 'transfer_tb')


def _text(maximum, description, *, public=True):
    spec = {'type': 'string', 'minLength': 1, 'maxLength': maximum, 'description': description}
    if public:
        spec['pattern'] = _PUBLIC_TEXT_PATTERN
    return spec


def _id(description='Identificador estable en minúsculas, con guiones entre palabras.'):
    return {'type': 'string', 'minLength': 1, 'pattern': _SLUG_PATTERN, 'description': description}


def _integer(minimum, maximum, description):
    spec = {'type': 'integer', 'minimum': minimum, 'description': description}
    if maximum is not None:
        spec['maximum'] = maximum
    return spec


def _boolean(description):
    return {'type': 'boolean', 'description': description}


def _object(fields, description, *, partial=False):
    spec = editorial_object_schema(fields)
    spec['description'] = description
    if partial:
        spec.pop('required', None)
        spec['minProperties'] = 1
    else:
        spec['required'] = list(fields)
    return spec


def _list(item, maximum, description, *, minimum=1):
    return {
        'type': 'array', 'minItems': minimum, 'maxItems': maximum,
        'items': item, 'description': description,
    }


def _slug_map(item, description, *, minimum=0):
    return {
        'type': 'object', 'additionalProperties': False, 'minProperties': minimum,
        'propertyNames': _id(), 'patternProperties': {_SLUG_PATTERN: item},
        'description': description,
    }


def _card_text():
    return {
        'title': _text(80, 'Título de la tarjeta.'),
        'summary': _text(400, 'Descripción breve de la tarjeta.'),
    }


def _tier_text():
    return {
        'name': _text(40, 'Nombre del nivel.'),
        'badge': _text(40, 'Etiqueta que distingue el nivel.'),
        'pace_label': _text(40, 'Nombre del ritmo de trabajo.'),
        'pace_summary': _text(240, 'Descripción del ritmo de trabajo.'),
        'ideal_for': _text(400, 'Situaciones para las que se recomienda este nivel.'),
        'roles': _list(_text(160, 'Aporte de un rol al nivel.'), 10, 'Aportes de los roles de la célula.'),
        'highlights': _list(_text(160, 'Ventaja del nivel.'), 8, 'Ventajas principales del nivel.'),
        'cta_label': _text(60, 'Texto del botón de contacto.'),
    }


def _faq_text():
    return {'question': _text(200, 'Pregunta frecuente.'), 'answer': _text(800, 'Respuesta a la pregunta.')}


def _task_text():
    return {'label': _text(80, 'Nombre visible de la tarea.'), 'hint': _text(240, 'Orientación sobre el alcance de la tarea.')}


def _server_spec(*, partial=False):
    return _object({
        'vcpu': _integer(1, 256, 'Cantidad de CPU virtuales del servidor.'),
        'ram_gb': _integer(1, 2048, 'Memoria RAM del servidor, en gigabytes.'),
        'disk_gb': _integer(1, 100000, 'Almacenamiento del servidor, en gigabytes.'),
        'transfer_tb': _integer(1, 1000, 'Transferencia del servidor, en terabytes.'),
    }, 'Capacidad del servidor incluido en el nivel.', partial=partial)


def _hosting_spec(*, partial=False):
    return _object({
        'plan': _text(40, 'Nombre interno del plan del proveedor.', public=False),
        'promo_monthly': _integer(0, None, 'Costo mensual promocional del alojamiento, sin impuestos.'),
        'renewal_monthly': _integer(1, None, 'Costo mensual de renovación del alojamiento, sin impuestos.'),
    }, 'Costos privados del alojamiento de este nivel.', partial=partial)


_CARD = _object({'id': _id(), **_card_text()}, 'Tarjeta de contenido público.')
_TIER_TEXT = _object({'id': _id(), **_tier_text()}, 'Presentación pública de un nivel.')
_TERM_TEXT = _object({'id': _id(), 'label': _text(40, 'Nombre visible del plazo.')}, 'Presentación pública de un plazo.')
_TASK_TEXT = _object({'id': _id(), **_task_text()}, 'Presentación pública de una tarea del estimador.')
_FAQ_TEXT = _object({'id': _id(), **_faq_text()}, 'Pregunta frecuente de la presentación.')

SECTION_SPEC = {
    'seo': _object({
        'title': _text(70, 'Título para buscadores.'),
        'description': _text(200, 'Descripción para buscadores.'),
    }, 'Metadatos para buscadores.'),
    'hero': _object({
        'eyebrow': _text(60, 'Etiqueta superior de la portada.'),
        'title': _text(120, 'Título principal de la portada.'),
        'subtitle': _text(400, 'Explicación inicial del programa.'),
        'positioning': _text(240, 'Mensaje de posicionamiento del programa.'),
        'note': _text(300, 'Aclaración sobre la modalidad de trabajo.'),
    }, 'Portada del programa.'),
    'cell': _object({
        'title': _text(120, 'Título de la sección de la célula.'),
        'summary': _text(600, 'Descripción de la célula compartida.'),
        'note': _text(300, 'Aclaración sobre sus roles.'),
        'roles': _list(_CARD, 10, 'Roles que participan en la célula.'),
    }, 'Composición de la célula.'),
    'fit': _object({
        'title': _text(120, 'Título sobre el encaje del programa.'),
        'summary': _text(600, 'Descripción del tipo de necesidad que atiende el programa.'),
        'good_for': _list(_CARD, 8, 'Casos adecuados para el programa.'),
        'not_for': _list(_CARD, 8, 'Casos que requieren otra modalidad.'),
    }, 'Casos en los que el programa encaja.'),
    'tiers': _object({
        'title': _text(120, 'Título de los niveles.'),
        'summary': _text(600, 'Explicación de las opciones disponibles.'),
        'items': _list(_TIER_TEXT, 4, 'Niveles en el mismo orden de la oferta.'),
    }, 'Presentación de los niveles.'),
    'terms': _object({
        'title': _text(120, 'Título de los plazos.'),
        'summary': _text(600, 'Explicación de los plazos disponibles.'),
        'note': _text(300, 'Aclaración sobre los plazos.'),
        'items': _list(_TERM_TEXT, 6, 'Plazos en el mismo orden de la oferta.'),
    }, 'Presentación de los plazos.'),
    'bag': _object({
        'title': _text(120, 'Título de la bolsa de horas.'),
        'summary': _text(600, 'Descripción de la bolsa mensual.'),
        'note': _text(300, 'Aclaración sobre el uso de la bolsa.'),
        'rules': _list(_CARD, 8, 'Reglas para usar las horas disponibles.'),
    }, 'Uso de la bolsa mensual.'),
    'estimator': _object({
        'title': _text(120, 'Título del estimador.'),
        'summary': _text(600, 'Descripción del estimador de alcance.'),
        'description_label': _text(80, 'Etiqueta del campo para describir la necesidad.'),
        'description_placeholder': _text(200, 'Orientación dentro del campo de descripción.'),
        'disclaimer': _text(600, 'Aclaración sobre el carácter orientativo del estimador.'),
        'tasks': _list(_TASK_TEXT, 20, 'Tareas en el mismo orden de la oferta.'),
    }, 'Presentación del estimador.'),
    'hosting': _object({
        'title': _text(120, 'Título del alojamiento incluido.'),
        'summary': _text(600, 'Descripción del alojamiento incluido.'),
        'note': _text(300, 'Aclaración sobre el alojamiento.'),
        'features': _list(_CARD, 10, 'Características del alojamiento.'),
    }, 'Alojamiento del producto.'),
    'faq': _object({
        'title': _text(120, 'Título de las preguntas frecuentes.'),
        'items': _list(_FAQ_TEXT, 15, 'Preguntas frecuentes, en orden de presentación.'),
    }, 'Preguntas frecuentes.'),
    'cta': _object({
        'title': _text(120, 'Título de la invitación a conversar.'),
        'body': _text(400, 'Mensaje de la invitación a conversar.'),
        'button_label': _text(60, 'Texto del botón de WhatsApp.'),
        'whatsapp_message': _text(300, 'Mensaje inicial para la conversación de WhatsApp.'),
    }, 'Invitación a conversar.'),
    'legal': _object({'disclaimer': _text(600, 'Aclaración legal pública.')}, 'Aclaración legal.'),
}


def _size_spec():
    return _object({
        'id': {**_id('Tamaño fijo de estimación.'), 'enum': list(SIZE_IDS)},
        'hours_min': _integer(1, 1000, 'Límite inferior de las horas de referencia.'),
        'hours_max': _integer(1, 1000, 'Límite superior de las horas de referencia.'),
    }, 'Rango de horas de un tamaño de estimación.')


def estimator_sizes_json_schema():
    """The four fixed sizes; ids cannot be added, removed or reordered."""
    schema = _list(_size_spec(), 4, 'Rangos de los cuatro tamaños, en orden xs, s, m y l.', minimum=4)
    schema['prefixItems'] = [
        _object({
            **_size_spec()['properties'],
            'id': {**_id('Identificador fijo del tamaño.'), 'const': size},
        }, f'Rango de horas del tamaño {size}.')
        for size in SIZE_IDS
    ]
    return deepcopy(schema)


_OFFER_SPEC = _object({
    'currency': {'type': 'string', 'enum': ['COP'], 'description': 'Moneda de la oferta: pesos colombianos.'},
    'prices_include_vat': _boolean('Indica si los precios públicos ya incluyen IVA.'),
    'days_per_week': _integer(1, 7, 'Días disponibles por semana.'),
    'weeks_per_month': _integer(1, 5, 'Semanas utilizadas para calcular la bolsa mensual.'),
    'terms': _list(_object({
        'id': _id(), 'months': _integer(1, 36, 'Duración del plazo en meses.'),
    }, 'Duración de un plazo.'), 6, 'Plazos, comenzando por el mensual y en orden creciente.'),
    'tiers': _list(_object({
        'id': _id(),
        'monthly_price': _integer(100000, 1000000000, 'Precio mensual base en pesos colombianos.'),
        'daily_hours': _integer(1, 24, 'Horas disponibles por día.'),
        'recommended': _boolean('Indica si este es el único nivel recomendado.'),
        'discounts': _slug_map(_integer(0, 60, 'Descuento porcentual para el plazo.'), 'Descuentos por plazo, excluyendo el mensual.'),
        'server': _server_spec(),
    }, 'Cifras de un nivel.'), 4, 'Niveles en orden creciente de precio y horas.'),
    'estimator': _object({
        'sizes': estimator_sizes_json_schema(),
        'tasks': _list(_object({
            'id': _id(),
            'size': {**_id('Tamaño de referencia de la tarea.'), 'enum': list(SIZE_IDS)},
            'min_tier': _id('Identificador del nivel mínimo para la tarea.'),
        }, 'Configuración de una tarea del estimador.'), 20, 'Tareas disponibles en el estimador.'),
    }, 'Configuración numérica del estimador.'),
}, 'Cifras públicas de la oferta.')


def _internal_fields(*, partial_servers=False):
    return {
        'hour_cost': _integer(1000, 10000000, 'Costo interno de una hora de trabajo en pesos colombianos.'),
        'vat_percent': _integer(0, 50, 'Porcentaje de IVA utilizado para calcular el costo del alojamiento.'),
        'provider': _text(80, 'Nombre del proveedor de alojamiento.', public=False),
        'reference_url': {**_text(300, 'URL HTTPS de la fuente de los costos.', public=False), 'format': 'uri'},
        'consulted_on': {
            **_text(10, 'Fecha de consulta de los costos, en formato AAAA-MM-DD.', public=False),
            'pattern': r'^\d{4}-\d{2}-\d{2}$', 'format': 'date',
        },
        'servers': _slug_map(_hosting_spec(partial=partial_servers), 'Costos privados del servidor por identificador de nivel.', minimum=1),
    }


_INTERNAL_SPEC = _object(_internal_fields(), 'Datos económicos privados del programa.')


def _invalid(path, message):
    raise BuildingOnDemandError(message, details={'path': path})


def _child_path(path, key):
    return f'{path}.{key}' if path else str(key)


def _validate_string(value, spec, path, public_text):
    if not isinstance(value, str):
        _invalid(path, 'Debe ser texto.')
    value = value.strip()
    is_id = spec.get('pattern') == _SLUG_PATTERN
    if (public_text or spec.get('pattern') == _PUBLIC_TEXT_PATTERN) and not is_id and _FIGURES.search(value):
        raise BuildingOnDemandError(
            'La presentación pública no admite porcentajes ni importes.',
            code='PUBLIC_FIGURE_NOT_ALLOWED', details={'path': path},
        )
    if len(value) < spec.get('minLength', 0) or len(value) > spec.get('x-editorial-max-visible-length', spec.get('maxLength', float('inf'))):
        _invalid(path, 'El texto es obligatorio y debe respetar la longitud máxima.')
    if 'pattern' in spec and not re.search(spec['pattern'], value):
        _invalid(path, 'id debe ser un slug en minúsculas.' if is_id else 'El texto no tiene el formato requerido.')
    if spec.get('format') == 'date':
        try:
            date.fromisoformat(value)
        except ValueError:
            _invalid(path, 'Usa una fecha válida en formato AAAA-MM-DD.')
    if spec.get('format') == 'uri':
        try:
            _HTTPS_URL(value)
            urlsplit(value).port
        except (ValidationError, ValueError):
            _invalid(path, 'Usa una URL HTTPS válida.')
        if re.search(r'[\x00-\x20\x7f]', value):
            _invalid(path, 'Usa una URL HTTPS válida.')
    return value


def _validate_object(value, spec, path, public_text):
    if not isinstance(value, dict):
        _invalid(path, 'Debe ser un objeto.')
    value, editorial = prepare_editorial_object(value, spec, _invalid, path)
    fields = {key: child for key, child in spec.get('properties', {}).items() if key != 'text_formats'}
    patterns = spec.get('patternProperties', {})
    if not set(spec.get('required', ())).issubset(value):
        _invalid(path, 'Incluye todos los campos requeridos y ningún campo desconocido.')
    if len(value) < spec.get('minProperties', 0):
        _invalid(path, 'Incluye al menos un campo para actualizar.')
    result = {}
    for key, child in value.items():
        if not isinstance(key, str):
            _invalid(path, 'Las claves deben ser texto.')
        normalized_key = key
        if 'propertyNames' in spec:
            normalized_key = validate_schema(key, spec['propertyNames'], _child_path(path, key))
        child_spec = fields.get(normalized_key)
        if child_spec is None:
            child_spec = next((item for pattern, item in patterns.items() if re.search(pattern, normalized_key)), None)
        if child_spec is None:
            extra = spec.get('additionalProperties', True)
            if extra is False:
                _invalid(path, 'Incluye todos los campos requeridos y ningún campo desconocido.')
            if isinstance(extra, dict):
                child_spec = extra
            else:
                result[normalized_key] = deepcopy(child)
                continue
        if normalized_key in result:
            _invalid(path, 'No repitas identificadores dentro del objeto.')
        result[normalized_key] = validate_schema(
            child, child_spec, _child_path(path, normalized_key),
            public_text=public_text or (normalized_key in fields and normalized_key in ('es', 'en')),
        )
    return restore_editorial_object({
        **{key: result[key] for key in fields if key in result},
        **{key: child for key, child in result.items() if key not in fields},
    }, editorial)


def validate_schema(value, schema, path='', public_text=False):
    """Validate one closed schema and return fresh, whitespace-normalized data."""
    kind = schema.get('type')
    if kind == 'object':
        result = _validate_object(value, schema, path, public_text)
    elif kind == 'array':
        minimum, maximum = schema.get('minItems', 0), schema.get('maxItems', float('inf'))
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            _invalid(path, f'La lista debe tener entre {minimum} y {maximum} elementos.')
        prefix = schema.get('prefixItems', ())
        result = [
            validate_schema(item, prefix[index] if index < len(prefix) else schema['items'],
                            f'{path}[{index}]', public_text=public_text)
            for index, item in enumerate(value)
        ]
        item_spec = schema.get('items', {})
        if item_spec.get('type') == 'object' and 'id' in item_spec.get('properties', {}):
            ids = [item['id'] for item in result]
            if len(set(ids)) != len(ids):
                _invalid(path, 'No repitas ids dentro de la lista.')
    elif kind == 'integer':
        minimum, maximum = schema.get('minimum', -float('inf')), schema.get('maximum', float('inf'))
        if type(value) is not int or not minimum <= value <= maximum:
            message = f'Usa un entero entre {minimum} y {maximum}.' if 'maximum' in schema else f'Usa un entero mayor o igual a {minimum}.'
            _invalid(path, message)
        result = value
    elif kind == 'boolean':
        if type(value) is not bool:
            _invalid(path, 'Usa un booleano verdadero o falso.')
        result = value
    elif kind == 'string':
        result = _validate_string(value, schema, path, public_text)
    else:
        _invalid(path, 'El esquema de validación no admite este tipo.')
    if 'enum' in schema and result not in schema['enum']:
        _invalid(path, 'Usa uno de los valores permitidos.')
    if 'const' in schema and result != schema['const']:
        _invalid(path, 'El valor debe coincidir con el identificador fijo.')
    return result


def _validate_alignment(es, en, spec, path):
    if spec['type'] == 'object':
        for key, child in spec['properties'].items():
            if key == 'text_formats':
                continue
            if key == 'id' and es[key] != en[key]:
                _invalid(_child_path(path, key), 'Los ids deben coincidir entre idiomas y conservar su orden.')
            _validate_alignment(es[key], en[key], child, _child_path(path, key))
    elif spec['type'] == 'array':
        if len(es) != len(en):
            _invalid(path, 'Las listas deben tener la misma longitud en ambos idiomas.')
        for index, (left, right) in enumerate(zip(es, en)):
            _validate_alignment(left, right, spec['items'], f'{path}[{index}]')


def validate_section(key, value_by_lang):
    """Validate a complete bilingual section before replacing it."""
    if key not in SECTION_SPEC:
        _invalid(str(key), 'Sección desconocida.')
    result = validate_schema(value_by_lang, _object({
        'es': SECTION_SPEC[key], 'en': SECTION_SPEC[key],
    }, 'Sección completa en ambos idiomas.'), key)
    _validate_alignment(result['es'], result['en'], SECTION_SPEC[key], key)
    return result


def _require_increasing(items, key, path, *, strict=True):
    for index in range(1, len(items)):
        previous, current = items[index - 1][key], items[index][key]
        if current < previous or (strict and current == previous):
            message = 'Los valores deben ser estrictamente crecientes.' if strict else 'Los valores no pueden disminuir entre niveles.'
            _invalid(f'{path}[{index}].{key}', message)


def _validate_offer(offer):
    terms, tiers = offer['terms'], offer['tiers']
    if terms[0] != {'id': 'monthly', 'months': 1}:
        _invalid('offer.terms[0]', 'El primer plazo debe ser monthly y durar un mes.')
    _require_increasing(terms, 'months', 'offer.terms')
    if sum(tier['recommended'] for tier in tiers) != 1:
        _invalid('offer.tiers', 'Debe haber exactamente un nivel recomendado.')
    _require_increasing(tiers, 'monthly_price', 'offer.tiers')
    _require_increasing(tiers, 'daily_hours', 'offer.tiers')
    term_ids = [term['id'] for term in terms[1:]]
    for index, tier in enumerate(tiers):
        path = f'offer.tiers[{index}].discounts'
        if set(tier['discounts']) != set(term_ids):
            _invalid(path, 'Incluye un descuento para cada plazo, excepto el mensual.')
        previous = 0
        for term_id in term_ids:
            discount = tier['discounts'][term_id]
            if discount <= previous:
                _invalid(_child_path(path, term_id), 'A mayor plazo, el descuento debe ser mayor y positivo.')
            previous = discount
    servers = [tier['server'] for tier in tiers]
    for key in SERVER_FIELDS:
        for index in range(1, len(servers)):
            if servers[index][key] < servers[index - 1][key]:
                _invalid(f'offer.tiers[{index}].server.{key}', 'La capacidad del servidor no puede disminuir entre niveles.')
    sizes = offer['estimator']['sizes']
    for index, size in enumerate(sizes):
        if size['hours_min'] >= size['hours_max']:
            _invalid(f'offer.estimator.sizes[{index}].hours_max', 'El límite superior debe ser mayor que el inferior.')
    _require_increasing(sizes, 'hours_min', 'offer.estimator.sizes', strict=False)
    _require_increasing(sizes, 'hours_max', 'offer.estimator.sizes')
    tier_ids = {tier['id'] for tier in tiers}
    for index, task in enumerate(offer['estimator']['tasks']):
        if task['min_tier'] not in tier_ids:
            _invalid(f'offer.estimator.tasks[{index}].min_tier', 'La tarea debe indicar un nivel existente.')


def validate_content(content):
    """Validate the entire immutable document, including all cross-item rules."""
    language = _object({key: SECTION_SPEC[key] for key in TEXT_SECTION_KEYS}, 'Presentación en un idioma.')
    result = validate_schema(content, _object({
        'es': language, 'en': language, 'offer': _OFFER_SPEC, 'internal': _INTERNAL_SPEC,
    }, 'Documento completo del programa.'))
    for key in TEXT_SECTION_KEYS:
        _validate_alignment(result['es'][key], result['en'][key], SECTION_SPEC[key], key)
    _validate_offer(result['offer'])
    offer = result['offer']
    collections = (
        ('tiers', 'items', offer['tiers']),
        ('terms', 'items', offer['terms']),
        ('estimator', 'tasks', offer['estimator']['tasks']),
    )
    for section, collection, items in collections:
        expected = [item['id'] for item in items]
        for lang in ('es', 'en'):
            if [item['id'] for item in result[lang][section][collection]] != expected:
                _invalid(f'{lang}.{section}.{collection}', 'Los ids y su orden deben coincidir con la oferta.')
    if set(result['internal']['servers']) != {tier['id'] for tier in offer['tiers']}:
        _invalid('internal.servers', 'Los costos de alojamiento deben corresponder exactamente a los niveles.')
    return result


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def section_json_schema():
    """Supplied sections replace complete texts in both languages."""
    return deepcopy(_object({
        key: _object({'es': SECTION_SPEC[key], 'en': SECTION_SPEC[key]}, f'Textos de {key} en ambos idiomas.')
        for key in TEXT_SECTION_KEYS
    }, 'Secciones públicas que se desean reemplazar.', partial=True))


def settings_json_schema():
    return deepcopy(_object({
        key: _OFFER_SPEC['properties'][key]
        for key in ('days_per_week', 'weeks_per_month', 'prices_include_vat')
    }, 'Configuración de la bolsa y la presentación de impuestos.', partial=True))


def _bilingual_item(fields, text_fields, description, *, partial=False):
    if not partial:
        fields = {'id': _id(), **fields}
    fields = {
        **fields,
        'es': _object(text_fields, 'Textos del elemento en español.', partial=partial),
        'en': _object(deepcopy(text_fields), 'Textos del elemento en inglés.', partial=partial),
    }
    return deepcopy(_object(fields, description, partial=partial))


def tier_json_schema(partial=False):
    return _bilingual_item({
        'monthly_price': _integer(100000, 1000000000, 'Precio mensual base en pesos colombianos.'),
        'daily_hours': _integer(1, 24, 'Horas disponibles por día.'),
        'recommended': _boolean('Marca este nivel como el único recomendado.'),
        'discounts': _slug_map(_integer(0, 60, 'Descuento porcentual para un plazo existente.'), 'Descuentos por plazo, excluyendo el mensual.', minimum=int(partial)),
        'server': _server_spec(partial=partial),
        'hosting': _hosting_spec(partial=partial),
    }, _tier_text(), 'Datos de un nivel del programa.', partial=partial)


def term_json_schema(partial=False):
    return _bilingual_item({
        'months': _integer(1, 36, 'Duración del plazo en meses.'),
        'discounts': _slug_map(_integer(0, 60, 'Descuento porcentual para un nivel existente.'), 'Descuentos por identificador de nivel.', minimum=1),
    }, {'label': _text(40, 'Nombre visible del plazo.')}, 'Datos de un plazo del programa.', partial=partial)


def estimator_task_json_schema(partial=False):
    return _bilingual_item({
        'size': {**_id('Tamaño de referencia de la tarea.'), 'enum': list(SIZE_IDS)},
        'min_tier': _id('Identificador del nivel mínimo para la tarea.'),
    }, _task_text(), 'Datos de una tarea del estimador.', partial=partial)


def faq_json_schema(partial=False):
    return _bilingual_item({}, _faq_text(), 'Datos de una pregunta frecuente.', partial=partial)


def card_json_schema(partial=False):
    return _bilingual_item({}, _card_text(), 'Datos de una tarjeta de contenido.', partial=partial)


def economics_json_schema():
    return deepcopy(_object(_internal_fields(partial_servers=True), 'Cambios en los datos económicos privados.', partial=True))
