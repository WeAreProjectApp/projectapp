"""Optional editorial metadata for closed public-program JSON contracts."""
from copy import deepcopy

from rest_framework.exceptions import ValidationError

from content.mcp.editorial_schemas import TEXT_FORMATS_SCHEMA
from content.services.editorial_format import MAX_SOURCE, plain_text, resolve_pointer, validate_nested_formats

PROSE_FIELDS = frozenset(('summary', 'subtitle', 'note', 'trust_note', 'body', 'description',
    'answer', 'disclaimer', 'positioning', 'pace_summary', 'ideal_for', 'roles', 'highlights', 'hint', 'points', 'industries', 'expert_contributes',
    'projectapp_contributes', 'benefits', 'requirements', 'includes', 'excludes', 'details'))


def editorial_object_schema(fields):
    fields = deepcopy(fields)
    eligible = [key for key, spec in fields.items() if key in PROSE_FIELDS and (
        spec.get('type') == 'string' or (spec.get('type') == 'array' and spec.get('items', {}).get('type') == 'string'))]
    if set(fields) == {'title', 'description'}:
        eligible = []  # SEO metadata remains plain text.
    required = list(fields)
    for key in eligible:
        text_spec = fields[key] if fields[key]['type'] == 'string' else fields[key]['items']
        text_spec['x-editorial-max-visible-length'] = text_spec.get('maxLength', MAX_SOURCE)
        text_spec['maxLength'] = MAX_SOURCE
    if eligible:
        fields['text_formats'] = deepcopy(TEXT_FORMATS_SCHEMA)
        fields['text_formats']['description'] += ' Campos admitidos en este objeto: ' + ', '.join(eligible) + '.'
    return {'type': 'object', 'additionalProperties': False, 'properties': fields, 'required': required,
            'x-editorial-fields': eligible}


def prepare_editorial_object(value, spec, invalid, path):
    """Validate raw sources, then expose visible text to existing business limits."""
    if not isinstance(value, dict) or 'text_formats' not in value:
        return value, {}
    eligible = spec.get('x-editorial-fields', ())
    formats = value['text_formats']
    try:
        validate_nested_formats(value)
        for pointer in formats:
            if pointer.split('/')[1] not in eligible:
                raise ValidationError('El campo no admite formato editorial.')
    except (ValidationError, IndexError, TypeError) as error:
        invalid(path + '.text_formats', str(error))
    clean = deepcopy(value)
    originals = {}
    for pointer, format_name in formats.items():
        source = resolve_pointer(value, pointer)
        originals[pointer] = source
        _assign(clean, pointer, plain_text(source, format=format_name) if format_name != 'plain' else source)
    clean.pop('text_formats', None)
    return clean, {'formats': deepcopy(formats), 'sources': originals}


def restore_editorial_object(value, editorial):
    if editorial:
        for pointer, source in editorial['sources'].items():
            _assign(value, pointer, source)
        value['text_formats'] = editorial['formats']
    return value


def _assign(owner, pointer, value):
    parts = pointer[1:].split('/')
    for part in parts[:-1]:
        key = part.replace('~1', '/').replace('~0', '~')
        owner = owner[int(key)] if isinstance(owner, list) else owner[key]
    key = parts[-1].replace('~1', '/').replace('~0', '~')
    owner[int(key) if isinstance(owner, list) else key] = value
