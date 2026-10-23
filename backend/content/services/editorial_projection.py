"""Transient rendering projections; the database keeps one editable source."""
from copy import deepcopy
from xml.sax.saxutils import escape

from reportlab.platypus import Flowable, Paragraph

from content.services.editorial_format import FORMAT, render_source, resolve_pointer


class EditorialSource(str):
    def __new__(cls, source, format=FORMAT):
        value = super().__new__(cls, source)
        value.format = format
        return value


def editorial_projection(value, formats=None):
    if isinstance(value, list):
        result = [editorial_projection(item) for item in value]
    elif isinstance(value, dict):
        result = {key: editorial_projection(item) for key, item in value.items()}
        formats = formats if formats is not None else value.get('text_formats', {})
    else:
        return deepcopy(value)
    for pointer, format_name in (formats or {}).items():
        if format_name == 'plain':
            continue
        try:
            source = resolve_pointer(result, pointer)
            owner = result
            tokens = pointer[1:].split('/')
            for token in tokens[:-1]:
                key = token.replace('~1', '/').replace('~0', '~')
                owner = owner[int(key)] if isinstance(owner, list) else owner[key]
            key = tokens[-1].replace('~1', '/').replace('~0', '~')
            if isinstance(source, str):
                owner[int(key) if isinstance(owner, list) else key] = EditorialSource(source, format_name)
        except (KeyError, IndexError, TypeError, AttributeError):
            continue  # Historical dangling metadata cannot break a read.
    return result


class EditorialBlock(Flowable):
    def __init__(self, source, style):
        super().__init__()
        self.source, self.style = source, style

    def wrap(self, width, height):
        from content.services.editorial_format import parse_html
        from content.services.editorial_pdf import _flowables
        html = render_source(self.source, format=self.source.format, strict=False)
        self.parts = _flowables(parse_html(html, strict=False), width, self.style.fontName,
                                self.style.fontSize, self.style.textColor)
        self.sizes = [part.wrap(width, height)[1] + part.getSpaceAfter() for part in self.parts]
        self.width, self.height = width, sum(self.sizes)
        return self.width, self.height

    def split(self, width, height):
        self.wrap(width, height)
        return self.parts

    def draw(self):
        y = self.height
        for part, height in zip(self.parts, self.sizes):
            gap = part.getSpaceAfter()
            y -= height - gap
            part.drawOn(self.canv, 0, y)
            y -= gap


def editorial_paragraph(source, style):
    if isinstance(source, EditorialSource):
        return EditorialBlock(source, style)
    return Paragraph(escape(str(source or '')), style)
