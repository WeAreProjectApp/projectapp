"""Finite, versioned editorial grammar shared by REST, MCP, email and PDF.

HTML is parsed, never accepted through a regex sanitizer. Unknown constructs
raise a validation error on writes; rendering historical content fails closed.
"""
import copy
import re
from html import escape

import html5lib
import tinycss2
from markdown_it import MarkdownIt
from rest_framework.exceptions import ValidationError

FORMAT = 'markdown_html_v1'
FORMATS = ('plain', 'markdown', FORMAT, 'whatsapp_v1')
TAGS = frozenset('p br h1 h2 h3 h4 h5 h6 strong b em i u s del strike span mark a ul ol li blockquote pre code hr table thead tbody tfoot tr th td div'.split())
ATTRS = frozenset('href title target rel start colspan rowspan style data-callout data-editor-block class'.split())
ALIGNMENTS = frozenset(('left', 'center', 'right', 'justify'))
STYLE_TAGS = {
    'color': frozenset(('span',)),
    'background-color': frozenset(('mark',)),
    'text-align': frozenset(('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th')),
}
NAMED_COLORS = {
    'black': (0, 0, 0),
    'white': (255, 255, 255),
    'red': (255, 0, 0),
    'green': (0, 128, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'orange': (255, 165, 0),
    'purple': (128, 0, 128),
    'gray': (128, 128, 128),
    'grey': (128, 128, 128),
}
WHATSAPP_TAGS = frozenset('p br strong b em i s del strike ul ol li blockquote pre code'.split())
ACTIVE_TAGS = frozenset(('script', 'style', 'iframe', 'object', 'embed', 'template', 'noscript'))
MAX_SOURCE = 500_000
_MAX_VALIDATION_CACHE_ENTRIES = 1000

# JSON Pointer roots. Nested structures retain their existing business shape.
EDITORIAL_ROOTS = {
    'document': ('content_markdown', 'client_email_body', 'client_whatsapp_message', 'client_custom_notes'),
    'documentnote': ('content', 'resolution_note'),
    'communicationmessage': ('content',),
    'businessproposal': ('email_intro', 'email_features', 'email_method_phases'),
    'proposalsection': ('content_json',),
    'proposaldocument': ('content_markdown',),
    'proposaldefaultconfig': ('sections_json',),
    'diagnosticsection': ('content_json',),
    'webappdiagnostic': ('email_intro',),
    'emailtemplateconfig': ('content_overrides',),
    'blogpost': ('content_es', 'content_en', 'content_json_es', 'content_json_en', 'excerpt_es', 'excerpt_en'),
    'portfoliowork': ('content_json_es', 'content_json_en'),
    'hourpackage': ('note_es', 'note_en'),
    'additionalmodule': ('summary_es', 'summary_en', 'what_is_es', 'what_is_en', 'purpose_es', 'purpose_en', 'problems_solved_es', 'problems_solved_en', 'integrations_es', 'integrations_en', 'implementation_requirements_es', 'implementation_requirements_en'),
    'contracttemplate': ('content_markdown', 'product_content_markdown', 'service_content_markdown'),
    'confidentialitytemplate': ('content_markdown',),
}


def normalize_editorial_color(value):
    value = str(value or '').strip().lower()
    if value == 'transparent':
        return value
    channels = NAMED_COLORS.get(value)
    if re.fullmatch(r'#[\da-f]{3}(?:[\da-f]{3})?', value):
        digits = value[1:]
        if len(digits) == 3:
            digits = ''.join(character * 2 for character in digits)
        channels = tuple(int(digits[index:index + 2], 16) for index in (0, 2, 4))
    match = re.fullmatch(
        r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)',
        value,
    )
    if match:
        channels = tuple(int(channel) for channel in match.groups())
    if channels is None or any(channel > 255 for channel in channels):
        return None
    return f'rgb({", ".join(str(channel) for channel in channels)})'


def style_properties(value):
    result = {}
    declarations = tinycss2.parse_declaration_list(
        value,
        skip_comments=False,
        skip_whitespace=True,
    )
    for item in declarations:
        if item.type != 'declaration' or item.important or item.lower_name in result:
            raise ValidationError('Estilo editorial no permitido.')
        name = item.lower_name
        text = tinycss2.serialize(item.value).strip()
        if name in ('color', 'background-color'):
            text = normalize_editorial_color(text)
        elif name == 'text-align' and text in ALIGNMENTS:
            pass
        else:
            text = None
        if text is None:
            raise ValidationError(f'Estilo editorial no permitido: {name}.')
        result[name] = text
    return result


def safe_href(value):
    value = re.sub(r'[\s\x00-\x1f\x7f]', '', value)
    return not re.match(r'^[a-z][a-z\d+.-]*:', value, re.I) or bool(re.match(r'^(https?:|mailto:|tel:)', value, re.I))


def _tag_name(element):
    if not isinstance(element.tag, str):
        return None
    return element.tag.rsplit('}', 1)[-1].lower()


def _append_at(parent, index, text):
    if not text:
        return
    if index:
        previous = parent[index - 1]
        previous.tail = (previous.tail or '') + text
    else:
        parent.text = (parent.text or '') + text


def _discard_element(parent, element):
    index = list(parent).index(element)
    tail = element.tail
    parent.remove(element)
    _append_at(parent, index, tail)


def _unwrap_element(parent, element):
    index = list(parent).index(element)
    children = list(element)
    _append_at(parent, index, element.text)
    for child in children:
        element.remove(child)
    tail = element.tail
    parent.remove(element)
    for offset, child in enumerate(children):
        parent.insert(index + offset, child)
    if children:
        children[-1].tail = (children[-1].tail or '') + (tail or '')
    else:
        _append_at(parent, index, tail)


def _safe_style(value, tag):
    properties = {}
    declarations = tinycss2.parse_declaration_list(
        value,
        skip_comments=False,
        skip_whitespace=True,
    )
    for item in declarations:
        if item.type != 'declaration' or item.important:
            continue
        name = item.lower_name
        if tag not in STYLE_TAGS.get(name, ()):
            continue
        text = tinycss2.serialize(item.value).strip()
        if name in ('color', 'background-color'):
            text = normalize_editorial_color(text)
        elif name == 'text-align' and text in ALIGNMENTS:
            pass
        else:
            text = None
        if text is not None:
            properties[name] = text
    return '; '.join(f'{name}: {value}' for name, value in properties.items())


def _valid_attribute(tag, name, value):
    if name not in ATTRS:
        return False
    if name == 'href':
        return tag == 'a' and bool(value) and safe_href(value)
    if name == 'title':
        return tag == 'a'
    if name == 'target':
        return tag == 'a' and value in ('_blank', '_self')
    if name == 'rel':
        return tag == 'a' and set(value.split()) <= {'noopener', 'noreferrer', 'nofollow'}
    if name == 'start':
        return tag == 'ol' and bool(re.fullmatch(r'\d{1,4}', value))
    if name in ('colspan', 'rowspan'):
        return tag in ('td', 'th') and bool(re.fullmatch(r'[1-9]\d{0,3}', value))
    if name == 'class':
        return tag == 'code' and bool(re.fullmatch(r'language-[\w-]+', value))
    if name == 'data-callout':
        return tag == 'blockquote' and value in ('NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION')
    if name == 'data-editor-block':
        return tag == 'div' and value == 'toc'
    if name == 'style':
        try:
            properties = style_properties(value)
        except ValidationError:
            return False
        return all(tag in STYLE_TAGS.get(property_name, ()) for property_name in properties)
    return False


def _sanitize_children(parent, strict):
    index = 0
    while index < len(parent):
        element = parent[index]
        tag = _tag_name(element)
        if tag not in TAGS:
            if strict:
                raise ValidationError('El contenido incluye una etiqueta no compatible.')
            if tag in ACTIVE_TAGS or tag is None:
                _discard_element(parent, element)
                continue
            _sanitize_children(element, strict=False)
            child_count = len(element)
            _unwrap_element(parent, element)
            index += child_count
            continue

        for name, value in list(element.attrib.items()):
            if name == 'style' and not strict:
                sanitized = _safe_style(value, tag)
                if sanitized:
                    element.attrib[name] = sanitized
                else:
                    del element.attrib[name]
                continue
            if _valid_attribute(tag, name, value):
                if name == 'style':
                    properties = style_properties(value)
                    element.attrib[name] = '; '.join(
                        f'{property_name}: {property_value}'
                        for property_name, property_value in properties.items()
                    )
                continue
            if strict:
                raise ValidationError(f'Atributo editorial no permitido: {name}.')
            del element.attrib[name]

        _sanitize_children(element, strict)
        if strict and tag == 'div':
            if (
                element.attrib.get('data-editor-block') != 'toc'
                or len(element)
                or element.text != '[TOC]'
            ):
                raise ValidationError('Bloque editorial no permitido.')
        if strict and tag == 'a' and not element.attrib.get('href'):
            raise ValidationError('Atributo editorial no permitido: href.')
        index += 1


def parse_html(html, *, strict=True):
    root = html5lib.parseFragment(html, namespaceHTMLElements=False)
    _sanitize_children(root, strict)
    return root


def serialize_html(root):
    return html5lib.serialize(root, tree='etree', quote_attr_values='always', omit_optional_tags=False, alphabetical_attributes=True)


def _editorial_toc(state, start_line, end_line, silent):
    start = state.bMarks[start_line] + state.tShift[start_line]
    end = state.eMarks[start_line]
    if state.src[start:end] != '[TOC]':
        return False
    if silent:
        return True
    state.line = start_line + 1
    token = state.push('editorial_toc', 'div', 0)
    token.map = [start_line, state.line]
    return True


def _render_editorial_toc(tokens, index, options, env):
    return '<div data-editor-block="toc">[TOC]</div>\n'


def _whatsapp_fence(state, start_line, end_line, silent):
    start = state.bMarks[start_line] + state.tShift[start_line]
    end = state.eMarks[start_line]
    if state.sCount[start_line] != state.blkIndent or state.src[start:end] != '```':
        return False
    closing_line = None
    for line in range(start_line + 1, end_line):
        line_start = state.bMarks[line] + state.tShift[line]
        line_end = state.eMarks[line]
        if state.sCount[line] == state.blkIndent and state.src[line_start:line_end] == '```':
            closing_line = line
            break
    if closing_line is None:
        return False
    if silent:
        return True
    state.line = closing_line + 1
    token = state.push('whatsapp_fence', 'code', 0)
    token.content = state.getLines(
        start_line + 1,
        closing_line,
        state.blkIndent,
        False,
    )
    token.map = [start_line, state.line]
    return True


def _escape_html_text(value):
    return (
        value.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _render_whatsapp_fence(tokens, index, options, env):
    return f'<pre><code>{_escape_html_text(tokens[index].content)}</code></pre>\n'


def _render_whatsapp_break(tokens, index, options, env):
    return '<br>'


def _whatsapp_mark(state, silent):
    position = state.pos
    source = state.src
    marker = source[position]
    if marker not in ('*', '_', '~'):
        return False
    if (
        position + 1 >= state.posMax
        or source[position + 1] == marker
        or source[position + 1].isspace()
    ):
        return False
    closing = source.find(marker, position + 1)
    if (
        closing < 0
        or (closing + 1 < state.posMax and source[closing + 1] == marker)
        or source[closing - 1].isspace()
        or '\n' in source[position + 1:closing]
    ):
        return False
    if not silent:
        token_type, tag = {
            '*': ('strong', 'strong'),
            '_': ('em', 'em'),
            '~': ('s', 's'),
        }[marker]
        state.push(f'{token_type}_open', tag, 1)
        nested = []
        state.md.inline.parse(
            source[position + 1:closing],
            state.md,
            state.env,
            nested,
        )
        state.tokens.extend(nested)
        state.tokens_meta.extend([None] * len(nested))
        state.push(f'{token_type}_close', tag, -1)
    state.pos = closing + 1
    return True


def _build_document_parser():
    parser = MarkdownIt('commonmark', {'html': True}).enable(['table', 'strikethrough'])
    parser.block.ruler.before(
        'paragraph',
        'editorial_toc',
        _editorial_toc,
        {'alt': ['paragraph', 'reference', 'blockquote', 'list']},
    )
    parser.renderer.rules['editorial_toc'] = _render_editorial_toc
    return parser


def _build_whatsapp_parser():
    parser = MarkdownIt('commonmark', {'breaks': True, 'html': False})
    parser.disable(
        [
            'code',
            'fence',
            'hr',
            'reference',
            'heading',
            'lheading',
            'html_block',
            'escape',
            'strikethrough',
            'emphasis',
            'link',
            'image',
            'autolink',
            'html_inline',
        ],
        ignoreInvalid=True,
    )
    parser.block.ruler.before(
        'blockquote',
        'whatsapp_fence',
        _whatsapp_fence,
        {'alt': ['paragraph', 'reference', 'blockquote', 'list']},
    )
    parser.inline.ruler.before('link', 'whatsapp_mark', _whatsapp_mark)
    parser.renderer.rules['whatsapp_fence'] = _render_whatsapp_fence
    parser.renderer.rules['softbreak'] = _render_whatsapp_break
    parser.renderer.rules['hardbreak'] = _render_whatsapp_break
    return parser


PARSER = _build_document_parser()
WHATSAPP_PARSER = _build_whatsapp_parser()


def _apply_callouts(root):
    marker_pattern = re.compile(
        r'^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\s|$)'
    )
    for quote in root.iter('blockquote'):
        first = next(iter(quote), None)
        if first is None or first.tag != 'p' or not first.text:
            continue
        match = marker_pattern.match(first.text)
        if not match:
            continue
        quote.attrib['data-callout'] = match.group(1)
        first.text = re.sub(
            r'^\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*',
            '',
            first.text,
        )
        if not first.text and not len(first):
            quote.remove(first)


def _validate_whatsapp(root, strict):
    for element in root.iter():
        tag = _tag_name(element)
        if element is root:
            continue
        invalid_tag = tag not in WHATSAPP_TAGS
        invalid_attributes = any(name != 'start' for name in element.attrib)
        if not invalid_tag and not invalid_attributes:
            continue
        if strict:
            raise ValidationError('Este formato no es compatible con WhatsApp.')
        element.attrib.clear()


def render_source(source, *, format=FORMAT, strict=True):
    if not isinstance(source, str) or len(source) > MAX_SOURCE:
        raise ValidationError('El contenido debe ser texto de hasta 500000 caracteres.')
    if format not in FORMATS:
        raise ValidationError('Formato editorial desconocido.')
    if format == 'plain':
        return '<p>' + escape(source).replace('\n', '<br>') + '</p>'
    if format == 'whatsapp_v1':
        root = parse_html(WHATSAPP_PARSER.render(source), strict=strict)
        _validate_whatsapp(root, strict)
        return serialize_html(root)
    rendered = PARSER.render(source)
    parsed = html5lib.parseFragment(rendered, namespaceHTMLElements=False)
    _apply_callouts(parsed)
    root = parse_html(serialize_html(parsed), strict=strict)
    return serialize_html(root)


def plain_text(source, *, format=FORMAT):
    root = parse_html(render_source(source, format=format, strict=False), strict=False)

    def text_value(value, parent):
        if not value:
            return ''
        block_whitespace = (
            parent is root
            or parent.tag in ('ul', 'ol', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'blockquote')
            or any(
                child.tag in ('p', 'ul', 'ol', 'table', 'blockquote', 'pre')
                or re.fullmatch(r'h[1-6]', child.tag or '')
                for child in parent
            )
        )
        if not value.strip() and block_whitespace:
            return ''
        return value

    def element_text(element, parent=None):
        tag = element.tag if isinstance(element.tag, str) else ''
        if tag == 'br':
            return '\n'
        if tag == 'pre':
            return ''.join(element.itertext()).rstrip() + '\n\n'
        if tag == 'tr':
            cells = [element_text(cell, element).strip() for cell in element]
            return '\t'.join(cells) + '\n'
        result = text_value(element.text, element)
        for child in element:
            if (
                child.tag in ('p', 'ul', 'ol', 'table', 'blockquote', 'pre')
                and result
                and not result.endswith('\n')
            ):
                result += '\n'
            result += element_text(child, element)
            result += text_value(child.tail, element)
        if tag == 'li':
            return result.rstrip() + '\n'
        if tag == 'p' and parent is not None and parent.tag in ('li', 'td', 'th'):
            return result + ('\n' if len(parent) > 1 else '')
        if tag in ('p', 'blockquote', 'ul', 'ol', 'table') or re.fullmatch(r'h[1-6]', tag):
            return result.rstrip() + '\n\n'
        return result

    return re.sub(r'\n{3,}', '\n\n', element_text(root)).strip()


def resolve_pointer(data, pointer):
    current = data
    for token in pointer.lstrip('/').split('/'):
        key = token.replace('~1', '/').replace('~0', '~')
        if isinstance(current, (list, tuple)):
            if not key.isdecimal() or int(key) >= len(current): raise KeyError(pointer)
            current = current[int(key)]
        elif isinstance(current, dict): current = current[key]
        else: current = getattr(current, key)
    return current


def _validate_format_agreement(owner, pointer, expected):
    """Two annotations for one leaf must agree, regardless of map location."""
    parts = pointer[1:].split('/')
    current = owner
    for index, token in enumerate(parts):
        if isinstance(current, dict):
            annotations = current.get('text_formats')
            declared = annotations.get('/' + '/'.join(parts[index:])) if isinstance(annotations, dict) else None
            if declared and declared != expected:
                raise ValidationError({'text_formats': 'Hay formatos contradictorios para el mismo texto.'})
        key = token.replace('~1', '/').replace('~0', '~')
        current = current[int(key)] if isinstance(current, list) else current[key]


def _validate_source_once(source, format_name, validated_sources):
    """Reuse successful parses only within one bounded validation operation."""
    key = (source, format_name) if isinstance(source, str) else None
    if key is not None and key in validated_sources:
        return
    render_source(source, format=format_name)
    if key is not None and len(validated_sources) < _MAX_VALIDATION_CACHE_ENTRIES:
        validated_sources.add(key)


def validate_formats(model_name, values, formats, *, instance=None, _validated_sources=None):
    validated_sources = set() if _validated_sources is None else _validated_sources
    if not isinstance(formats, dict) or len(formats) > 1000:
        raise ValidationError({'text_formats': 'Debe ser un objeto de hasta 1000 campos.'})
    roots = EDITORIAL_ROOTS.get(model_name, ())
    result = copy.deepcopy(formats)
    for pointer, format in result.items():
        if not isinstance(pointer, str) or not pointer.startswith('/') or pointer.split('/')[1] not in roots or format not in FORMATS:
            raise ValidationError({'text_formats': f'Campo o formato no permitido: {pointer}.'})
        root = pointer.split('/')[1]
        if root == 'client_whatsapp_message' and format not in ('plain', 'whatsapp_v1'):
            raise ValidationError({'text_formats': 'WhatsApp utiliza plain o whatsapp_v1.'})
        channel = values.get('channel', getattr(instance, 'channel', None))
        if model_name == 'communicationmessage' and channel == 'whatsapp' and format not in ('plain', 'whatsapp_v1'):
            raise ValidationError({'text_formats': 'WhatsApp utiliza plain o whatsapp_v1.'})
        data = {root: values[root] if root in values else getattr(instance, root, None)}
        try: source = resolve_pointer(data, pointer)
        except (KeyError, IndexError, AttributeError, TypeError) as error:
            raise ValidationError({'text_formats': f'El campo ya no existe: {pointer}.'}) from error
        _validate_format_agreement(data, pointer, format)
        try: _validate_source_once(source, format, validated_sources)
        except ValidationError as error:
            raise ValidationError({'text_formats': {pointer: error.detail}}) from error
    return result


def validate_editorial_values(model_name, values, *, instance=None):
    """Validate changed sources and their metadata together, before any write."""
    validated_sources = set()
    previous = getattr(instance, 'text_formats', {}) or {}
    formats = values.get('text_formats', previous)
    if formats or 'text_formats' in values:
        values['text_formats'] = validate_formats(
            model_name, values, formats, instance=instance,
            _validated_sources=validated_sources,
        )
    for key in EDITORIAL_ROOTS.get(model_name, ()):
        if key not in values:
            continue
        value = values[key]
        if isinstance(value, (dict, list)):
            validate_nested_formats(value, _validated_sources=validated_sources)
        elif key.endswith('content_markdown') and isinstance(value, str):
            _validate_source_once(value, formats.get(f'/{key}', FORMAT), validated_sources)
    return values


def validate_nested_formats(value, *, _validated_sources=None):
    validated_sources = set() if _validated_sources is None else _validated_sources
    def resolve_json_pointer(owner, pointer):
        current = owner
        for token in pointer.lstrip('/').split('/'):
            key = token.replace('~1', '/').replace('~0', '~')
            if isinstance(current, list):
                if not key.isdecimal() or int(key) >= len(current):
                    raise KeyError(pointer)
                current = current[int(key)]
            elif isinstance(current, dict):
                current = current[key]
            else:
                raise KeyError(pointer)
        return current

    def walk(current, depth, ancestors):
        if depth > 50:
            raise ValidationError({'text_formats': 'La estructura supera 50 niveles.'})
        if not isinstance(current, (dict, list)):
            return
        identity = id(current)
        if identity in ancestors:
            raise ValidationError({'text_formats': 'La estructura editorial es circular.'})
        ancestors.add(identity)
        try:
            if isinstance(current, dict) and 'text_formats' in current:
                formats = current['text_formats']
                if not isinstance(formats, dict) or len(formats) > 1000:
                    raise ValidationError({
                        'text_formats': 'Debe ser un objeto de hasta 1000 campos.'
                    })
                for pointer, format_name in formats.items():
                    if (
                        not isinstance(pointer, str)
                        or not pointer.startswith('/')
                        or pointer.startswith('/text_formats')
                        or format_name not in FORMATS
                    ):
                        raise ValidationError({
                            'text_formats': f'Campo o formato no permitido: {pointer}.'
                        })
                    try:
                        source = resolve_json_pointer(current, pointer)
                    except (KeyError, IndexError, TypeError) as error:
                        raise ValidationError({
                            'text_formats': f'El campo ya no existe: {pointer}.'
                        }) from error
                    _validate_format_agreement(current, pointer, format_name)
                    if not isinstance(source, str):
                        raise ValidationError({
                            'text_formats': f'El campo no contiene texto: {pointer}.'
                        })
                    try:
                        _validate_source_once(source, format_name, validated_sources)
                    except ValidationError as error:
                        raise ValidationError({
                            'text_formats': {pointer: error.detail}
                        }) from error
            children = (
                (item for key, item in current.items() if key != 'text_formats')
                if isinstance(current, dict)
                else iter(current)
            )
            for child in children:
                walk(child, depth + 1, ancestors)
        finally:
            ancestors.remove(identity)

    walk(value, 0, set())
    return value
