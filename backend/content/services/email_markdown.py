"""
Markdown-to-email-HTML conversion for user-composed branded emails.

Renders a safe subset of Markdown into inline-styled HTML matching the
branded email design (emails/branded_email.html). Every user character is
HTML-escaped before any tag emission and link hrefs are scheme-whitelisted,
which is what makes the final ``mark_safe`` sound.

Block segmentation is delegated to the existing
``content.services.markdown_parser.markdown_to_blocks`` (the Document PDF
parser); this module only renders those blocks as email-client-friendly
HTML (inline styles, no classes, no scripts, no external images).
"""
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

from content.services.markdown_parser import markdown_to_blocks

_FONT = "font-family:Ubuntu,Helvetica,Arial,sans-serif;"
_MONO = "font-family:'Ubuntu Mono',Menlo,Consolas,monospace;"
_BODY_TEXT = f'{_FONT}font-weight:300;font-size:16px;line-height:26px;color:#001713;'

_P_STYLE = f'margin:14px 0 0 0;{_BODY_TEXT}'
_HEADING_STYLES = {
    1: f'margin:24px 0 0 0;{_FONT}font-weight:500;font-size:22px;line-height:30px;color:#001713;',
    2: f'margin:20px 0 0 0;{_FONT}font-weight:500;font-size:19px;line-height:26px;color:#001713;',
    3: f'margin:18px 0 0 0;{_FONT}font-weight:700;font-size:16px;line-height:24px;color:#001713;',
}
_LIST_STYLE = 'margin:14px 0 0 0;padding:0 0 0 22px;'
_NESTED_LIST_STYLE = 'margin:4px 0 0 0;padding:0 0 0 18px;'
_LI_STYLE = f'margin:6px 0 0 0;{_BODY_TEXT}'
_QUOTE_STYLE = (
    f'margin:14px 0 0 0;border-left:3px solid #F0FF3D;background:#faf7ee;'
    f'padding:10px 16px;{_FONT}font-weight:300;font-size:15px;line-height:24px;color:#001713;'
)
_SEPARATOR_HTML = (
    '<div style="height:1px;background:#ece8db;margin:24px 0 0 0;'
    'font-size:1px;line-height:1px;">&nbsp;</div>'
)
_PRE_STYLE = (
    f'margin:14px 0 0 0;background:#faf7ee;border:1px solid #ece8db;border-radius:10px;'
    f'padding:14px 16px;{_MONO}font-size:13px;line-height:20px;color:#001713;'
    f'white-space:pre-wrap;word-break:break-word;'
)
_CODE_SPAN_STYLE = (
    f"{_MONO}font-size:14px;background:#faf7ee;border:1px solid #ece8db;"
    f'border-radius:4px;padding:1px 5px;'
)
_TABLE_STYLE = 'width:100%;border-collapse:collapse;margin:14px 0 0 0;'
_TH_STYLE = (
    f'text-align:left;padding:8px 10px;border-bottom:2px solid #001713;'
    f'{_FONT}font-weight:500;font-size:14px;line-height:20px;color:#001713;'
)
_TD_STYLE = (
    f'padding:8px 10px;border-bottom:1px solid #ece8db;'
    f'{_FONT}font-weight:300;font-size:14px;line-height:20px;color:#001713;'
)
_LINK_STYLE = 'color:#001713;font-weight:400;text-decoration:underline;'

_ALLOWED_HREF_RE = re.compile(r'^(https?://|mailto:)', re.IGNORECASE)
_CODE_SPAN_RE = re.compile(r'`([^`]+)`')
_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_RE = re.compile(r'\*([^*]+)\*')
_CODE_PLACEHOLDER_RE = re.compile(r'\x00(\d+)\x00')


def normalize_sections(raw_sections, *, strict_editorial=False):
    """Coerce a mixed list of strings / ``{text, markdown}`` dicts into a
    uniform list, dropping empties.

    Single normalization point shared by the send parsers (standalone,
    proposal, diagnostic) and the composed-email preview endpoint, so both
    the legacy payload shape (plain strings) and the new one keep working.

    New Visual/Source editor submissions opt into ``strict_editorial``. Their
    Markdown sections are validated against the versioned editorial contract
    and receive an internal format marker. That marker survives the second
    normalization performed by the send services, while historical Markdown
    metadata without it keeps the legacy email renderer.
    """
    from content.services.editorial_format import FORMAT, render_source

    normalized = []
    if not isinstance(raw_sections, list):
        return normalized
    for item in raw_sections:
        if isinstance(item, str):
            text, markdown = item, False
        elif isinstance(item, dict) and isinstance(item.get('text'), str):
            text, markdown = item['text'], bool(item.get('markdown'))
        else:
            continue
        if text.strip():
            section = {'text': text, 'markdown': markdown}
            editorial_format = (
                FORMAT
                if markdown and (
                    strict_editorial
                    or (
                        isinstance(item, dict)
                        and item.get('format') == FORMAT
                    )
                )
                else None
            )
            if editorial_format:
                # Fail before sending or persisting metadata. Rendering with
                # strict=False later is only for already validated content.
                render_source(text, format=editorial_format, strict=True)
                section['format'] = editorial_format
            normalized.append(section)
    return normalized


def _render_inline(text):
    """Escape ``text`` and apply inline Markdown (code, links, bold, italic)."""
    working = escape(text)

    # Protect `code` spans from the other inline transforms.
    stashed = []

    def _stash(match):
        stashed.append(match.group(1))
        return f'\x00{len(stashed) - 1}\x00'

    working = _CODE_SPAN_RE.sub(_stash, working)

    def _link(match):
        label, url = match.group(1), match.group(2)
        if not _ALLOWED_HREF_RE.match(url):
            return match.group(0)  # unknown scheme: keep as literal text
        return f'<a href="{url}" style="{_LINK_STYLE}">{label}</a>'

    working = _LINK_RE.sub(_link, working)
    working = _BOLD_RE.sub(r'<strong style="font-weight:500;">\1</strong>', working)
    working = _ITALIC_RE.sub(r'<em>\1</em>', working)

    def _restore(match):
        code = stashed[int(match.group(1))]
        return f'<code style="{_CODE_SPAN_STYLE}">{code}</code>'

    return _CODE_PLACEHOLDER_RE.sub(_restore, working)


def _render_list(block):
    tag = 'ol' if block.get('ordered') else 'ul'
    items_html = []
    for item in block.get('items', []):
        inner = _render_inline(item.get('text', ''))
        children = item.get('children') or []
        if children:
            child_lis = ''.join(
                f'<li style="{_LI_STYLE}">{_render_inline(child)}</li>'
                for child in children
            )
            inner += f'<ul style="{_NESTED_LIST_STYLE}">{child_lis}</ul>'
        items_html.append(f'<li style="{_LI_STYLE}">{inner}</li>')
    return f'<{tag} style="{_LIST_STYLE}">{"".join(items_html)}</{tag}>'


def _render_table(block):
    header_cells = ''.join(
        f'<th style="{_TH_STYLE}">{_render_inline(cell)}</th>'
        for cell in block.get('headers', [])
    )
    body_rows = ''.join(
        '<tr>' + ''.join(
            f'<td style="{_TD_STYLE}">{_render_inline(cell)}</td>' for cell in row
        ) + '</tr>'
        for row in block.get('rows', [])
    )
    return (
        f'<table cellpadding="0" cellspacing="0" style="{_TABLE_STYLE}">'
        f'<tr>{header_cells}</tr>{body_rows}</table>'
    )


def _render_block(block):
    block_type = block.get('type')

    if block_type == 'rich_html':
        return editorial_email_html(block.get('html', ''))

    if block_type == 'paragraph':
        return f'<p style="{_P_STYLE}">{_render_inline(block.get("text", ""))}</p>'

    if block_type == 'heading':
        level = min(max(block.get('level', 1), 1), 3)
        return (
            f'<div style="{_HEADING_STYLES[level]}">'
            f'{_render_inline(block.get("text", ""))}</div>'
        )

    if block_type == 'section_header':
        title = f'{block.get("index", "")}. {block.get("title", "")}'.lstrip('. ')
        return f'<div style="{_HEADING_STYLES[2]}">{_render_inline(title)}</div>'

    if block_type == 'sub_section':
        title = f'{block.get("index", "")} {block.get("title", "")}'.strip()
        return f'<div style="{_HEADING_STYLES[3]}">{_render_inline(title)}</div>'

    if block_type == 'list':
        return _render_list(block)

    if block_type in ('blockquote', 'callout'):
        text = _render_inline(block.get('text', ''))
        if block_type == 'callout':
            label = escape(block.get('style', '').capitalize())
            text = f'<strong style="font-weight:500;">{label}:</strong> {text}'
        return f'<div style="{_QUOTE_STYLE}">{text}</div>'

    if block_type == 'code':
        return f'<pre style="{_PRE_STYLE}">{escape(block.get("content", ""))}</pre>'

    if block_type == 'separator':
        return _SEPARATOR_HTML

    if block_type == 'table':
        return _render_table(block)

    return ''  # toc and any unknown block type render nothing in emails


def markdown_to_email_html(text):
    """Render Markdown ``text`` as inline-styled, email-safe HTML.

    Returns a SafeString; may be empty if the input yields no blocks.
    """
    parts = [_render_block(block) for block in markdown_to_blocks(text or '')]
    return mark_safe(''.join(part for part in parts if part))


def editorial_email_html(html):
    """Inline the declared styles for mail clients, preserving user choices."""
    from content.services.editorial_format import parse_html, serialize_html
    root = parse_html(html, strict=False)
    styles = {'p': _P_STYLE, 'ul': _LIST_STYLE, 'ol': _LIST_STYLE,
              'li': _LI_STYLE, 'blockquote': _QUOTE_STYLE, 'pre': _PRE_STYLE,
              'table': _TABLE_STYLE, 'th': _TH_STYLE, 'td': _TD_STYLE}
    for element in root.iter():
        base = styles.get(element.tag, '')
        if element.tag in ('h1', 'h2', 'h3'): base = _HEADING_STYLES[int(element.tag[1])]
        if base: element.set('style', base + element.attrib.get('style', ''))
    return serialize_html(root)
