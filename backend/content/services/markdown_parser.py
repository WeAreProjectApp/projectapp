"""
Markdown-to-blocks parser for the Document PDF system.

Converts Markdown text into a flat list of typed block dicts
that the DocumentPdfService can render into a branded PDF.
"""

import re

from content.services.emoji_shortcodes import replace_shortcodes

_CALLOUT_RE = re.compile(r'^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]$', re.IGNORECASE)
_LIST_ITEM_RE = re.compile(r'^([ \t]*)([-*]|\d+\.)\s+(.+)$')


def _indent_depth(ws):
    """2 spaces or 1 tab = one nesting level."""
    return ws.count('\t') + len(ws.replace('\t', '')) // 2


def markdown_to_blocks(text, *, editorial=False):
    """Convert Markdown text into a list of block dicts.

    Supported block types:
    - heading: # H1, ## H2, ### H3
    - paragraph: regular text (consecutive non-empty lines merged)
    - table: lines starting with |
    - list (unordered): lines starting with - or *
    - list (ordered): lines starting with 1. 2. etc.
    - blockquote: lines starting with >
    - code: fenced with ```
    - separator: --- or *** or ___
    - section_header: ### with numbered pattern like "### 1. Title"
    - sub_section: **N.N. Title** pattern (bold numbered sub-heading)
    - toc: [TOC] on its own line — triggers table-of-contents generation

    Returns:
        list[dict]: List of block objects.
    """
    # Extended editorial HTML needs the same parsed grammar as email and the
    # browser, rather than falling through the historical line parser.
    if editorial or re.search(r'<(?:p|h[1-6]|span|mark|u|table|ul|ol|blockquote)\b', text or '', re.I):
        import copy
        import xml.etree.ElementTree as ET
        from content.services.editorial_format import parse_html, render_source, serialize_html
        root = parse_html(render_source(replace_shortcodes(text or ''), strict=False), strict=False)
        blocks = []
        for element in root:
            wrapper = ET.Element('div')
            wrapper.append(copy.deepcopy(element))
            html = serialize_html(wrapper)
            if element.attrib.get('data-editor-block') == 'toc':
                blocks.append({'type': 'toc'})
            elif re.fullmatch(r'h[1-6]', element.tag):
                blocks.append({'type': 'heading', 'level': int(element.tag[1]),
                               'text': ''.join(element.itertext()), 'html': html})
            else:
                blocks.append({'type': 'rich_html', 'html': html})
        return blocks

    # :shortcode: → emoji before parsing (code spans are left untouched),
    # so every writer — panel, MCP connector, seeds — gets the same PDF.
    text = replace_shortcodes(text or '')

    blocks = []
    lines = text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # 1. Code blocks (highest priority)
        if stripped.startswith('```'):
            language = stripped[3:].strip() or 'text'
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # skip closing ```
            blocks.append({
                'type': 'code',
                'language': language,
                'content': '\n'.join(code_lines),
            })
            continue

        # 2. TOC marker
        if stripped == '[TOC]':
            blocks.append({'type': 'toc'})
            i += 1
            continue

        # 3. Separator
        if re.match(r'^[-*_]{3,}\s*$', stripped):
            blocks.append({'type': 'separator'})
            i += 1
            continue

        # 4. Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title_text = heading_match.group(2).strip()
            # Check for numbered section: ### 1. Title or ### 14. Title
            section_match = re.match(r'^(\d+)\.\s+(.+)$', title_text)
            if level == 3 and section_match:
                index = section_match.group(1).zfill(2)
                blocks.append({
                    'type': 'section_header',
                    'index': index,
                    'title': section_match.group(2),
                })
            else:
                blocks.append({
                    'type': 'heading',
                    'level': level,
                    'text': title_text,
                })
            i += 1
            continue

        # 5. Blockquote / Callout
        if stripped.startswith('>'):
            quote_lines = []
            while i < len(lines):
                s = lines[i].strip()
                if s == '>':
                    quote_lines.append('')
                elif s.startswith('>'):
                    # Accept '>text' without the space too — otherwise the
                    # line is never consumed and the loop stops progressing.
                    quote_lines.append(s[1:].lstrip())
                else:
                    break
                i += 1
            if quote_lines:
                callout_match = _CALLOUT_RE.match(quote_lines[0].strip())
                if callout_match:
                    style = callout_match.group(1).lower()
                    body = ' '.join(ln for ln in quote_lines[1:] if ln).strip()
                    blocks.append({
                        'type': 'callout',
                        'style': style,
                        'text': body,
                    })
                else:
                    blocks.append({
                        'type': 'blockquote',
                        'text': ' '.join(ln for ln in quote_lines if ln).strip(),
                    })
            continue

        # 6. Table
        if stripped.startswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                def parse_row(row_str):
                    cells = row_str.split('|')
                    if cells and not cells[0].strip():
                        cells = cells[1:]
                    if cells and not cells[-1].strip():
                        cells = cells[:-1]
                    return [c.strip() for c in cells]

                headers = parse_row(table_lines[0])
                rows = []
                for row_line in table_lines[1:]:
                    if re.match(r'^[\s|:\-]+$', row_line):
                        continue
                    rows.append(parse_row(row_line))
                blocks.append({
                    'type': 'table',
                    'headers': headers,
                    'rows': rows,
                })
            continue

        # 7. Lists (ordered or unordered, arbitrarily nested)
        list_m = _LIST_ITEM_RE.match(line)
        if list_m and not re.match(r'^[-*_]{3,}\s*$', stripped):
            ordered = list_m.group(2) not in ('-', '*')
            root_items = []
            stack = [(0, root_items)]  # (depth, items list at that depth)
            while i < len(lines):
                raw = lines[i]
                m = _LIST_ITEM_RE.match(raw)
                if m and not re.match(r'^[-*_]{3,}\s*$', raw.strip()):
                    depth = min(_indent_depth(m.group(1)), stack[-1][0] + 1)
                    while len(stack) > 1 and depth < stack[-1][0]:
                        stack.pop()
                    if depth > stack[-1][0] and stack[-1][1]:
                        stack.append((depth, stack[-1][1][-1]['children']))
                    stack[-1][1].append(
                        {'text': m.group(3).strip(), 'children': []})
                    i += 1
                    continue
                s = raw.strip()
                if (
                    s
                    and not s.startswith('#')
                    and not s.startswith('|')
                    and not s.startswith('>')
                    and not s.startswith('```')
                    and not re.match(r'^[-*_]{3,}\s*$', s)
                    and not re.match(r'^\*\*\d+\.\d+', s)
                ):
                    # Continuation line: append to the innermost last item
                    items = stack[-1][1]
                    if items:
                        items[-1]['text'] += ' ' + s
                        i += 1
                        continue
                break
            if root_items:
                blocks.append({
                    'type': 'list',
                    'ordered': ordered,
                    'items': root_items,
                })
            continue

        # 9. Sub-section: **N.N. Title** or **N.N Title**
        subsection_match = re.match(
            r'^\*\*(\d+\.\d+\.?)\s+(.+?)\*\*$', stripped,
        )
        if subsection_match:
            blocks.append({
                'type': 'sub_section',
                'index': subsection_match.group(1).rstrip('.'),
                'title': subsection_match.group(2),
            })
            i += 1
            continue

        # 9b. Bold numbered stub: **N.N**, **N.N.**, **N.N:** rest — a bold
        # number without an inline bolded title. Emitted as a sub_section so
        # it never falls through to the paragraph guard, which refuses to
        # consume '**N.N'-prefixed lines.
        stub_match = re.match(r'^\*\*(\d+\.\d+[.:)]?)\*\*\s*(.*)$', stripped)
        if stub_match:
            blocks.append({
                'type': 'sub_section',
                'index': stub_match.group(1).rstrip('.:)'),
                'title': stub_match.group(2).strip(),
            })
            i += 1
            continue

        # 10. Paragraph (fallback)
        para_lines = []
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                break
            if (
                s.startswith('#')
                or s.startswith('|')
                or s.startswith('>')
                or s.startswith('```')
                or re.match(r'^[-*_]{3,}\s*$', s)
                or re.match(r'^[-*]\s+', s)
                or re.match(r'^\d+\.\s+', s)
                or re.match(r'^\*\*\d+\.\d+', s)
            ):
                break
            para_lines.append(s)
            i += 1
        if not para_lines:
            # Forward-progress guarantee: a line that reached the fallback
            # but matches one of the break prefixes (e.g. '**2.1 —' with no
            # closing '**') would otherwise loop forever without consuming
            # anything. Take it as-is so the parser always advances.
            para_lines.append(stripped)
            i += 1
        blocks.append({
            'type': 'paragraph',
            'text': ' '.join(para_lines),
        })
        continue

    return blocks
