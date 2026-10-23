"""Bilingual public copy contract shared by validation, PDF and MCP."""
import hashlib
import json
import re
from copy import deepcopy


class ConsultingError(ValueError):
    def __init__(self, message, code='VALIDATION_ERROR', details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


SECTION_KEYS = ('seo', 'hero', 'areas', 'impact', 'measurement', 'deliverable',
                'process', 'implementation', 'diagnostic', 'faq', 'cta', 'legal')


def _text(maximum):
    return {'type': 'string', 'minLength': 1, 'maxLength': maximum}


def _object(properties):
    return {'type': 'object', 'additionalProperties': False,
            'properties': properties, 'required': list(properties)}


def _cards(minimum=1, maximum=8):
    return _object({'title': _text(120), 'summary': _text(1000), 'items': {
        'type': 'array', 'minItems': minimum, 'maxItems': maximum,
        'items': _object({'id': {'type': 'string', 'minLength': 1, 'maxLength': 60,
                               'pattern': r'^[a-z0-9]+(?:-[a-z0-9]+)*$'},
                          'title': _text(120), 'summary': _text(1000)}),
    }})


SECTION_SPEC = {
    'seo': _object({'title': _text(70), 'description': _text(200)}),
    'hero': _object({'eyebrow': _text(60), 'title': _text(120), 'subtitle': _text(600), 'note': _text(400)}),
    'areas': _cards(5, 5),
    'impact': _cards(6, 6),
    **{key: _cards() for key in ('measurement', 'deliverable', 'process', 'implementation', 'diagnostic')},
    'faq': _object({'title': _text(120), 'items': {
        'type': 'array', 'minItems': 1, 'maxItems': 12,
        'items': _object({'id': _text(60), 'question': _text(200), 'answer': _text(1200)}),
    }}),
    'cta': _object({'title': _text(120), 'body': _text(600), 'button_label': _text(60), 'whatsapp_message': _text(300)}),
    'legal': _object({'disclaimer': _text(1000)}),
}


def _invalid(path, message):
    raise ConsultingError(message, details={'path': path})


def _validate(value, spec, path):
    if spec['type'] == 'object':
        if not isinstance(value, dict) or set(value) != set(spec['properties']):
            _invalid(path, 'Incluye los campos requeridos sin campos desconocidos.')
        return {key: _validate(value[key], child, f'{path}.{key}')
                for key, child in spec['properties'].items()}
    if spec['type'] == 'array':
        if not isinstance(value, list) or not spec['minItems'] <= len(value) <= spec['maxItems']:
            _invalid(path, f'Usa entre {spec["minItems"]} y {spec["maxItems"]} elementos.')
        result = [_validate(item, spec['items'], f'{path}[{index}]') for index, item in enumerate(value)]
        ids = [item['id'] for item in result]
        if len(set(ids)) != len(ids):
            _invalid(path, 'No repitas ids en la lista.')
        return result
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= spec['maxLength']:
        _invalid(path, 'El texto es obligatorio y debe respetar su longitud máxima.')
    value = value.strip()
    if re.search(r'<[^>]*>', value):
        _invalid(path, 'Usa texto plano sin HTML.')
    if 'pattern' in spec and not re.fullmatch(spec['pattern'], value):
        _invalid(path, 'Usa un id en minúsculas separado por guiones.')
    return value


def _alignment(es, en, spec, path):
    if spec['type'] == 'object':
        for key, child in spec['properties'].items():
            if key == 'id' and es[key] != en[key]:
                _invalid(path, 'Conserva los mismos ids y orden en ambos idiomas.')
            _alignment(es[key], en[key], child, f'{path}.{key}')
    elif spec['type'] == 'array':
        if len(es) != len(en):
            _invalid(path, 'Conserva la misma cantidad de elementos en ambos idiomas.')
        for left, right in zip(es, en):
            _alignment(left, right, spec['items'], path)


def validate_content(content):
    language = _object(SECTION_SPEC)
    result = _validate(content, _object({'es': language, 'en': language}), 'content')
    _alignment(result['es'], result['en'], language, 'content')
    return result


def canonical_hash(content):
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def section_json_schema():
    return deepcopy({'type': 'object', 'additionalProperties': False, 'minProperties': 1,
                     'properties': {key: _object({'es': value, 'en': value})
                                    for key, value in SECTION_SPEC.items()}})
