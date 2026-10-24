"""Transient composition metadata uses the same versioned content contract."""
import json
from rest_framework.exceptions import ValidationError
from content.services.editorial_format import FORMATS, render_source


def email_formats(value, sources):
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError) as error:
            raise ValidationError({'text_formats': 'Debe ser un objeto JSON válido.'}) from error
    if value is None: value = {}
    if not isinstance(value, dict) or len(value) > len(sources):
        raise ValidationError({'text_formats': 'Mapa de formato no válido.'})
    for path, format in value.items():
        if path not in {f'/{key}' for key in sources} or format not in FORMATS:
            raise ValidationError({'text_formats': 'Campo o formato no permitido.'})
        render_source(sources[path[1:]], format=format)
    return dict(value)


def template_formats(config):
    return {path.removeprefix('/content_overrides/'): format
            for path, format in (getattr(config, 'text_formats', {}) or {}).items()
            if path.startswith('/content_overrides/')}
