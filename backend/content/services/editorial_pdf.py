"""Draw validated editorial HTML using ReportLab's wrapping and splitting.

The existing canvas/page-state infrastructure keeps covers and footers. Only
the rich block is handed to Platypus; it never fetches files or remote assets.
"""
import copy
import re
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, LongTable, TableStyle, Spacer

from content.services.editorial_format import FORMAT, parse_html, render_source, style_properties


def _inline(element):
    result = escape(element.text or '')
    for child in element:
        tag = child.tag
        inside = _inline(child)
        attrs = style_properties(child.attrib.get('style', ''))
        if tag in ('strong', 'b'): value = f'<b>{inside}</b>'
        elif tag in ('em', 'i'): value = f'<i>{inside}</i>'
        elif tag in ('s', 'del', 'strike'): value = f'<strike>{inside}</strike>'
        elif tag == 'u': value = f'<u>{inside}</u>'
        elif tag == 'br': value = '<br/>'
        elif tag == 'a' and child.attrib.get('href'): value = f'<link href="{escape(child.attrib["href"], quote=True)}" color="#059669"><u>{inside}</u></link>'
        elif tag == 'code': value = f'<font name="Courier">{inside}</font>'
        else: value = inside
        if attrs.get('color'): value = f'<font color="{_pdf_color(attrs["color"])}">{value}</font>'
        if attrs.get('background-color'): value = f'<font backColor="{_pdf_color(attrs["background-color"])}">{value}</font>'
        result += value + escape(child.tail or '')
    return result


def _pdf_color(value):
    if value == 'transparent': return '#ffffff'
    rgb = re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value)
    if rgb: return '#%02x%02x%02x' % tuple(min(255, int(part)) for part in rgb.groups())
    return value


def _style(element, font, size, color, indent=0):
    align = style_properties(element.attrib.get('style', '')).get('text-align', 'left')
    return ParagraphStyle('editorial', fontName=font, fontSize=size, leading=size * 1.5,
                          textColor=color, alignment={'left': TA_LEFT, 'center': TA_CENTER, 'right': TA_RIGHT, 'justify': TA_JUSTIFY}[align],
                          leftIndent=indent, spaceAfter=6, allowWidows=0, allowOrphans=0)


def _flowables(root, width, font, size, color, indent=0):
    from content.services.pdf_utils import _font
    result = []
    if root.text and root.text.strip():
        result.append(Paragraph(escape(root.text), _style(root, font, size, color, indent)))
    for el in root:
        if el.tag in ('ul', 'ol'):
            start = int(el.attrib.get('start', 1))
            for index, item in enumerate(el):
                item = copy.deepcopy(item)
                prefix = f'{start + index}. ' if el.tag == 'ol' else '• '
                first = item[0] if len(item) and item[0].tag == 'p' else item
                first.text = prefix + (first.text or '')
                result.extend(_flowables(item, width, font, size, color, indent + 14))
        elif el.tag == 'table':
            rows = list(el.iter('tr'))
            count = max((sum(int(cell.attrib.get('colspan', 1)) for cell in row) for row in rows), default=0)
            if not count: continue
            data, spans = [], []
            occupied = set()
            for y, row in enumerate(rows):
                values = [''] * count
                x = 0
                for cell in row:
                    while (x, y) in occupied: x += 1
                    cols, height = int(cell.attrib.get('colspan', 1)), int(cell.attrib.get('rowspan', 1))
                    values[x] = _flowables(cell, width / count * cols - 12, font, size - 1, color) or [Paragraph(_inline(cell) or ' ', _style(cell, font, size - 1, color))]
                    if cols > 1 or height > 1:
                        spans.append(('SPAN', (x, y), (x + cols - 1, y + height - 1)))
                        occupied.update((cx, cy) for cx in range(x, x + cols) for cy in range(y, y + height) if (cx, cy) != (x, y))
                    x += cols
                data.append(values)
            table = LongTable(data, colWidths=[width / count] * count, repeatRows=1 if any(cell.tag == 'th' for cell in rows[0]) else 0, hAlign='LEFT')
            table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .5, colors.HexColor('#94a3b8')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)] + spans))
            result.extend([table, Spacer(1, 8)])
        elif el.tag in ('blockquote', 'div', 'thead', 'tbody', 'tfoot'):
            if el.attrib.get('data-editor-block') != 'toc': result.extend(_flowables(el, width, font, size, color, indent + (12 if el.tag == 'blockquote' else 0)))
        elif el.tag == 'pre':
            result.append(Paragraph(escape(''.join(el.itertext())).replace('\n', '<br/>'), _style(el, 'Courier', size - 1, color, indent)))
        elif el.tag == 'hr': result.append(Paragraph('―' * 24, _style(el, font, size, color)))
        else:
            heading = re.fullmatch(r'h([1-6])', el.tag)
            result.append(Paragraph(_inline(el) or ' ', _style(el, _font('bold') if heading else font, size + max(0, 12 - int(heading[1]) * 2) if heading else size, color, indent)))
    return result


def draw_editorial_html(canvas, y, html, *, ps=None, width=None, x=None, font=None, size=10, color=None):
    from content.services.pdf_utils import CONTENT_W, MARGIN_L, MARGIN_B, MARGIN_T, PAGE_H, _font, _new_page, ESMERALD_80
    from content.services.pdf_utils import _register_fonts
    _register_fonts()
    width, x, font, color = width or CONTENT_W, MARGIN_L if x is None else x, font or _font('regular'), color or ESMERALD_80
    queue = _flowables(parse_html(html, strict=False), width, font, size, color)
    while queue:
        flow = queue.pop(0)
        available = max(0, y - MARGIN_B - 12)
        _, height = flow.wrap(width, available)
        if height > available:
            parts = flow.split(width, available) if available > size * 2 else []
            if parts:
                flow = parts[0]
                queue = parts[1:] + queue
                _, height = flow.wrap(width, available)
            elif ps:
                if available >= PAGE_H - MARGIN_T - MARGIN_B - 13:
                    raise ValueError('El bloque editorial excede el área imprimible.')
                y = _new_page(canvas, ps)
                queue.insert(0, flow)
                continue
            else: return y
        flow.drawOn(canvas, x, y - height)
        y -= height + getattr(flow, 'spaceAfter', 0)
    return y


def draw_editorial_source(canvas, y, source, *, format=FORMAT, **kwargs):
    html = render_source(source, format=format, strict=False)
    return draw_editorial_html(canvas, y, html, **kwargs)
