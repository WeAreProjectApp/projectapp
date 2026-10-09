"""Single source of truth for bilingual presentation validation and MCP schemas."""
import hashlib
import json
import re
from copy import deepcopy


class BuildingWithUsError(ValueError):
    def __init__(self, message, code='VALIDATION_ERROR', details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


SECTION_KEYS = (
    'seo', 'hero', 'origin', 'contribution', 'expert_profile',
    'participation_models', 'incubation_periods', 'scope', 'milestones',
    'agreement', 'process', 'faq', 'cta', 'legal',
)
FIGURES_PATTERN = r'[%$€]|\b(COP|USD|EUR)\b'
_FIGURES = re.compile(FIGURES_PATTERN, re.IGNORECASE)
_SLUG_PATTERN = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'


def _text(max_length):
    return {'type': 'string', 'minLength': 1, 'maxLength': max_length}


def _object(fields):
    return {'type': 'object', 'additionalProperties': False, 'properties': fields, 'required': list(fields)}


def _list(item, maximum, minimum=1):
    return {'type': 'array', 'minItems': minimum, 'maxItems': maximum, 'items': item}


_ID = {'type': 'string', 'minLength': 1, 'pattern': _SLUG_PATTERN}
_CARD = _object({'id': _ID, 'title': _text(80), 'summary': _text(400)})


def _cards(maximum):
    return {'title': _text(120), 'summary': _text(600), 'items': _list(_CARD, maximum)}


SECTION_SPEC = {
    'seo': _object({'title': _text(70), 'description': _text(200)}),
    'hero': _object({'eyebrow': _text(60), 'title': _text(120), 'subtitle': _text(400), 'note': _text(240)}),
    'origin': _object({'title': _text(120), 'summary': _text(600), 'industries': _list(_text(60), 8), 'points': _list(_text(240), 6)}),
    'contribution': _object(_cards(10)),
    'expert_profile': _object(_cards(8)),
    'participation_models': _object({
        'title': _text(120), 'summary': _text(600),
        'items': _list(_object({
            'id': _ID, 'name': _text(80), 'badge': _text(40), 'summary': _text(500), 'ideal_for': _text(240),
            'expert_contributes': _list(_text(200), 6), 'projectapp_contributes': _list(_text(200), 6),
        }), 4),
    }),
    'incubation_periods': _object({
        'title': _text(120), 'summary': _text(600),
        'items': _list(_object({'id': _ID, 'months': {'type': 'integer', 'minimum': 1, 'maximum': 36}, 'title': _text(60), 'summary': _text(300)}), 6),
    }),
    'scope': _object(_cards(10)),
    'milestones': _object({**_cards(8), 'note': _text(300)}),
    'agreement': _object(_cards(10)),
    'process': _object({'title': _text(120), 'items': _list(_CARD, 8)}),
    'faq': _object({'title': _text(120), 'items': _list(_object({'id': _ID, 'question': _text(200), 'answer': _text(800)}), 15)}),
    'cta': _object({'title': _text(120), 'body': _text(400), 'button_label': _text(60), 'whatsapp_message': _text(300)}),
    'legal': _object({'disclaimer': _text(600)}),
}


def _invalid(path, message):
    raise BuildingWithUsError(message, details={'path': path})


def _validate(value, spec, path):
    kind = spec['type']
    if kind == 'object':
        if not isinstance(value, dict):
            _invalid(path, 'Debe ser un objeto.')
        fields = spec['properties']
        if set(value) != set(fields):
            _invalid(path, 'Incluye todos los campos requeridos y ningún campo desconocido.')
        return {key: _validate(value[key], child, f'{path}.{key}' if path else key) for key, child in fields.items()}
    if kind == 'array':
        if not isinstance(value, list) or not spec['minItems'] <= len(value) <= spec['maxItems']:
            _invalid(path, f'La lista debe tener entre {spec["minItems"]} y {spec["maxItems"]} elementos.')
        result = [_validate(item, spec['items'], f'{path}[{index}]') for index, item in enumerate(value)]
        if spec['items']['type'] == 'object' and 'id' in spec['items']['properties']:
            ids = [item['id'] for item in result]
            if len(set(ids)) != len(ids):
                _invalid(path, 'No repitas ids dentro de la lista.')
        return result
    if kind == 'integer':
        if type(value) is not int or not spec['minimum'] <= value <= spec['maximum']:
            _invalid(path, f'Usa un entero entre {spec["minimum"]} y {spec["maximum"]}.')
        return value
    if not isinstance(value, str):
        _invalid(path, 'Debe ser texto.')
    value = value.strip()
    if _FIGURES.search(value):
        raise BuildingWithUsError('La presentación pública no admite porcentajes ni importes.',
                                  code='PUBLIC_FIGURE_NOT_ALLOWED', details={'path': path})
    if not value or len(value) > spec.get('maxLength', float('inf')):
        _invalid(path, 'El texto es obligatorio y debe respetar la longitud máxima.')
    if 'pattern' in spec and not re.fullmatch(spec['pattern'], value):
        _invalid(path, 'id debe ser un slug en minúsculas.')
    return value


def _validate_alignment(es, en, spec, path):
    if spec['type'] == 'object':
        for key, child in spec['properties'].items():
            if key in ('id', 'months') and es[key] != en[key]:
                _invalid(f'{path}.{key}', 'Los ids y meses deben coincidir entre idiomas y conservar su orden.')
            _validate_alignment(es[key], en[key], child, f'{path}.{key}')
    elif spec['type'] == 'array':
        if len(es) != len(en):
            _invalid(path, 'Las listas deben tener la misma longitud en ambos idiomas.')
        for index, (left, right) in enumerate(zip(es, en)):
            _validate_alignment(left, right, spec['items'], f'{path}[{index}]')


def validate_section(key, value_by_lang):
    if key not in SECTION_SPEC:
        _invalid(str(key), 'Sección desconocida.')
    result = _validate(value_by_lang, _object({'es': SECTION_SPEC[key], 'en': SECTION_SPEC[key]}), key)
    _validate_alignment(result['es'], result['en'], SECTION_SPEC[key], key)
    return result


def validate_content(content):
    language_spec = _object({key: SECTION_SPEC[key] for key in SECTION_KEYS})
    result = _validate(content, _object({'es': language_spec, 'en': language_spec}), '')
    for key in SECTION_KEYS:
        _validate_alignment(result['es'][key], result['en'][key], SECTION_SPEC[key], key)
    return result


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def section_json_schema():
    """Partial section updates; supplied sections require both complete languages."""
    return deepcopy({
        'type': 'object', 'additionalProperties': False, 'minProperties': 1,
        'properties': {key: _object({'es': SECTION_SPEC[key], 'en': SECTION_SPEC[key]}) for key in SECTION_KEYS},
    })
