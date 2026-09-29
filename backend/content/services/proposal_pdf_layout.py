"""Measured spacing for the commercial and technical proposal PDFs.

Only these renderers opt in. The document/contract PDF families keep the
defaults in pdf_utils. A row uses the same measured blocks for pagination
and drawing, including priority badges and explicit paragraph boundaries.
"""
from dataclasses import dataclass
from functools import partial

from reportlab.pdfbase import pdfmetrics

from content.services import pdf_utils as pdf

BADGE_GAP = 30
CELL_GAP = 6
PARAGRAPH_GAP = 8
BLOCK_GAP = 12

_draw_paragraphs = partial(pdf._draw_paragraphs, preserve_breaks=True,
                           paragraph_gap=PARAGRAPH_GAP, block_gap=BLOCK_GAP)
_estimate_text_height = partial(pdf._estimate_text_height, preserve_breaks=True,
                                paragraph_gap=PARAGRAPH_GAP, block_gap=BLOCK_GAP)
_draw_table = partial(pdf._draw_table, preserve_breaks=True)


def _draw_subtitle(c, y, text, color=pdf.ESMERALD, ps=None):
    lines = pdf._wrap_by_width(pdf._sanitize_pdf_text(str(text)),
                               pdf._font('bold'), 12, pdf.CONTENT_W)
    if ps:
        y = pdf._check_y(c, y, ps, need=len(lines) * 16 + BLOCK_GAP + 20)
    for line in lines:
        pdf._draw_line_with_links(c, pdf.MARGIN_L, y, line,
                                  pdf._font('bold'), 12, color)
        y -= 16
    return y - BLOCK_GAP


def _draw_badge_panel(c, y, title, items, ps=None):
    if not items:
        return y
    return pdf._draw_badge_panel(c, y - BADGE_GAP, title, items, ps) - BADGE_GAP


def _draw_feature_row(c, y, title, description=None, ps=None, x=None,
                      max_width=None, index=None, pill_text=None,
                      pill_bg=pdf.ESMERALD_LIGHT, pill_fg=pdf.ESMERALD,
                      children=None):
    x = pdf.MARGIN_L if x is None else x
    max_width = pdf.CONTENT_W if max_width is None else max_width
    chip_w = 22 if index is not None else 0
    title = pdf._sanitize_pdf_text(str(title or ''))
    lines = pdf._wrap_by_width(title, pdf._font('bold'), 11, max_width - chip_w)
    need = len(lines) * 15 + BLOCK_GAP + 20
    if pill_text:
        need += BADGE_GAP * 2 + _badge_size(c, pill_text, max_width=max_width - chip_w)[2]
    if ps:
        y = pdf._check_y(c, y, ps, need=need)
    if index is not None:
        c.setFillColor(pdf.ESMERALD)
        c.circle(x + 8, y + 3.5, 8, fill=1, stroke=0)
        c.setFont(pdf._font('bold'), 9)
        c.setFillColor(pdf.WHITE)
        c.drawCentredString(x + 8, y, str(index))
    for line in lines:
        pdf._draw_line_with_links(c, x + chip_w, y, line,
                                  pdf._font('bold'), 11, pdf.ESMERALD)
        y -= 15
    if pill_text:
        y = _draw_badge_group(c, y, [{'text': pill_text, 'bg': pill_bg, 'fg': pill_fg}],
                              ps=ps, x=x + chip_w, max_width=max_width - chip_w)
    else:
        y -= BLOCK_GAP
    if description:
        y = _draw_paragraphs(c, y, [description], ps=ps, x=x + chip_w,
                             max_width=max_width - chip_w, font_size=9, leading=13)
    if children:
        y = pdf._draw_bullet_list(c, y, children, x=x + chip_w,
                                  max_width=max_width - chip_w,
                                  font_size=8, leading=11, ps=ps)
    return y - BLOCK_GAP


def _badge_size(c, text, font_size=7, max_width=pdf.CONTENT_W,
                padding_h=8, padding_v=3):
    lines = pdf._wrap_by_width(pdf._sanitize_pdf_text(str(text)),
                               pdf._font('medium'), font_size,
                               max_width - 2 * padding_h)
    width = max(pdf._string_width_mixed(line, pdf._font('medium'), font_size)
                for line in lines) + 2 * padding_h
    height = font_size + 2 * padding_v + (len(lines) - 1) * (font_size + 3)
    return lines, width, height


def _paint_badge(c, x, top, spec, max_width):
    text = spec['text']
    size = spec.get('font_size', 7)
    ph, pv = spec.get('padding_h', 8), spec.get('padding_v', 3)
    lines, width, height = _badge_size(c, text, size, max_width, ph, pv)
    bottom = top - height
    bg, fg = spec.get('bg', pdf.ESMERALD_LIGHT), spec.get('fg', pdf.ESMERALD)
    c.setFillColor(bg)
    c.roundRect(x, bottom, width, height, min(height / 2, 8), fill=1, stroke=0)
    c.setFillColor(fg)
    baseline = top - pv - size
    c.setFont(pdf._font('medium'), size)
    for line in lines:
        pdf._draw_mixed_string(c, x + ph, baseline, line, pdf._font('medium'), size)
        # _draw_mixed_string preserves the selected fill colour.
        baseline -= size + 3
    return x + width, bottom


def _draw_badge_group(c, y, badges, ps=None, x=pdf.MARGIN_L,
                      max_width=pdf.CONTENT_W, before=BADGE_GAP, after=BADGE_GAP):
    """Wrap whole badges, including long labels, with one exterior margin."""
    badges = [b for b in badges if b.get('text')]
    if not badges:
        return y
    rows, row, used, height = [], [], 0, 0
    for badge in badges:
        _, width, badge_h = _badge_size(
            c, badge['text'], badge.get('font_size', 7), max_width,
            badge.get('padding_h', 8), badge.get('padding_v', 3))
        if row and used + width > max_width:
            rows.append((row, height))
            row, used, height = [], 0, 0
        row.append((badge, used, width))
        used += width + 8
        height = max(height, badge_h)
    rows.append((row, height))
    if ps:
        y = pdf._check_y(c, y, ps, need=before + rows[0][1] + after + 15)
    y -= before
    for row, height in rows:
        if ps:
            y = pdf._check_y(c, y, ps, need=height + after + 15)
        for badge, offset, _ in row:
            right, bottom = _paint_badge(c, x + offset, y, badge, max_width)
            if badge.get('link'):
                c.linkURL(badge['link'], (x + offset, bottom, right, y), relative=0)
        y -= height + 8
    return y - after - 8  # next text baseline has room for its ascent


def _heading_badge_height(c, title, badge, font_size=12, font_name=None,
                          max_width=pdf.CONTENT_W):
    font_name = font_name or pdf._font('bold')
    lines = pdf._wrap_by_width(pdf._sanitize_pdf_text(str(title)), font_name, font_size, max_width)
    badge_h = _badge_size(c, badge, max_width=max_width)[2] if badge else 0
    return len(lines) * (font_size + 6) + (BADGE_GAP * 2 + badge_h if badge else BLOCK_GAP) + 20


def _draw_heading_badge(c, y, title, badge, ps=None, font_size=12,
                        font_name=None, x=pdf.MARGIN_L, max_width=pdf.CONTENT_W):
    font_name = font_name or pdf._font('bold')
    lines = pdf._wrap_by_width(pdf._sanitize_pdf_text(str(title)),
                               font_name, font_size, max_width)
    leading = font_size + 6
    need = _heading_badge_height(c, title, badge, font_size, font_name, max_width)
    if ps:
        y = pdf._check_y(c, y, ps, need=need)
    for line in lines:
        pdf._draw_line_with_links(c, x, y, line, font_name, font_size, pdf.ESMERALD)
        y -= leading
    if badge:
        return _draw_badge_group(c, y, [{'text': badge, 'bg': pdf.BONE}],
                                 ps=ps, x=x, max_width=max_width)
    return y - BLOCK_GAP


@dataclass
class _CellBlock:
    text: str = ''
    font: str = 'regular'
    size: int = 8
    height: float = 11
    badge: dict | None = None
    keep_next: float = 0


def _cell_text(text, width, *, font='regular', size=8):
    lines = pdf._wrap_paragraph_lines(str(text or ''), pdf._font(font), size, width)
    return [_CellBlock(line, font, size) if line is not None
            else _CellBlock(height=PARAGRAPH_GAP) for line in lines]


def _priority_spec(priority, lang):
    key = str(priority or '').strip().lower()
    if not key:
        return None
    labels = pdf._REQ_PRIORITY_LABELS.get(lang) or pdf._REQ_PRIORITY_LABELS['es']
    bg, fg = pdf._PRIORITY_PILL_COLORS.get(key, (pdf.ESMERALD_LIGHT, pdf.ESMERALD))
    return {'text': labels.get(key) or key.capitalize(), 'bg': bg, 'fg': fg}


def _title_blocks(c, title, width, priority='', lang='es'):
    blocks = _cell_text(pdf._clean_cell_text(title), width, font='bold', size=9)
    spec = _priority_spec(priority, lang)
    if spec:
        badge_h = _badge_size(c, spec['text'], max_width=width)[2] + CELL_GAP
        if blocks:
            blocks[-1].keep_next = badge_h
        blocks.append(_CellBlock(height=badge_h, badge=spec))
    return blocks


def _take_blocks(blocks, available):
    height, take = 0, 0
    for block in blocks:
        if height + block.height + block.keep_next > available:
            break
        take += 1
        height += block.height
    return blocks[:take], blocks[take:], height


def _paint_cell(c, x, top, blocks, width):
    cursor = top
    for block in blocks:
        if block.badge:
            _paint_badge(c, x, cursor - CELL_GAP, block.badge, width)
        elif block.text:
            font = pdf._font(block.font)
            ascent, _ = pdfmetrics.getAscentDescent(font, block.size)
            pdf._draw_line_with_links(c, x, cursor - ascent, block.text,
                                      font, block.size, pdf.ESMERALD_80)
        cursor -= block.height


def _draw_measured_row(c, y, cells, widths, ps=None, redraw=None,
                       number='', bg=pdf.ESMERALD_LIGHT, accent=pdf.LEMON):
    """Draw measured cells, splitting oversized rows at block boundaries."""
    pending = [list(cell) for cell in cells]
    full_h = max(16, max((sum(b.height for b in cell) for cell in pending), default=0)) + CELL_GAP * 2
    page_capacity = pdf.PAGE_H - pdf.MARGIN_T - pdf.MARGIN_B - 22
    if ps and full_h <= page_capacity:
        y = pdf._check_y_with_redraw(c, y, ps, need=full_h, redraw=redraw)
    first = True
    while first or any(pending):
        first = False
        available = y - pdf.MARGIN_B - CELL_GAP * 2 if ps else full_h
        chunks = [_take_blocks(cell, available) for cell in pending]
        if not any(chunk for chunk, _, _ in chunks) and any(pending):
            y = pdf._new_page(c, ps)
            if redraw:
                y = redraw(c, y)
            continue
        row_h = max(16, max((height for _, _, height in chunks), default=0)) + CELL_GAP * 2
        bottom = y - row_h
        c.setFillColor(bg)
        c.rect(pdf.MARGIN_L, bottom, pdf.CONTENT_W, row_h, fill=1, stroke=0)
        c.setFillColor(accent)
        c.rect(pdf.MARGIN_L, bottom, 3, row_h, fill=1, stroke=0)
        if number:
            c.setFont(pdf._font('bold'), 8)
            c.setFillColor(pdf.ESMERALD_80)
            c.drawCentredString(pdf.MARGIN_L + 14, bottom + (row_h - 8) / 2, number)
        x = pdf.MARGIN_L + 28
        for (chunk, _, _), width in zip(chunks, widths):
            _paint_cell(c, x + CELL_GAP, y - CELL_GAP, chunk, width - CELL_GAP * 2)
            x += width
        pending = [rest for _, rest, _ in chunks]
        y = bottom
        if any(pending):
            y = pdf._new_page(c, ps)
            if redraw:
                y = redraw(c, y)
    return y


def _draw_requirements_table(c, y, rows, ps=None, linked_renderer=None):
    """Shared compact commercial/technical requirement table."""
    name_w = int((pdf.CONTENT_W - 28) * .36)
    desc_w = pdf.CONTENT_W - 28 - name_w
    lang = (ps or {}).get('_pdf_lang', 'es')

    def header(canvas, top):
        canvas.setFillColor(pdf.ESMERALD)
        canvas.rect(pdf.MARGIN_L, top - 22, pdf.CONTENT_W, 22, fill=1, stroke=0)
        canvas.setFont(pdf._font('bold'), 8)
        canvas.setFillColor(pdf.WHITE)
        canvas.drawCentredString(pdf.MARGIN_L + 14, top - 14, '#')
        canvas.drawString(pdf.MARGIN_L + 34, top - 14, 'Requerimiento')
        canvas.drawString(pdf.MARGIN_L + 28 + name_w + CELL_GAP, top - 14, 'Descripción')
        return top - 22

    if ps:
        y = pdf._check_y(c, y, ps, need=80)
    y = header(c, y)
    for index, row in enumerate(rows):
        title = _title_blocks(c, row.get('title', ''), name_w - CELL_GAP * 2,
                               row.get('priority'), lang)
        desc = _cell_text(row.get('description', ''), desc_w - CELL_GAP * 2)
        y = _draw_measured_row(c, y, [title, desc], [name_w, desc_w], ps, header,
                               str(index + 1).zfill(2),
                               pdf.ESMERALD_LIGHT if index % 2 == 0 else pdf.WHITE)
        if linked_renderer:
            y = linked_renderer(c, row, ps, y, redraw=header)
    return y - BLOCK_GAP


def _draw_linked_row(c, y, req, ps, redraw=None):
    width = pdf.CONTENT_W - 28
    title = _title_blocks(c, req.get('title', ''), width - CELL_GAP * 2,
                           req.get('priority'), ps.get('_pdf_lang', 'es'))
    desc = _cell_text(req.get('description', ''), width - CELL_GAP * 2)
    gap = [_CellBlock(height=CELL_GAP)] if title and desc else []
    return _draw_measured_row(c, y, [title + gap + desc], [width], ps, redraw,
                              bg=pdf.BONE, accent=pdf.GREEN_LIGHT)


def _payment_blocks(c, label, badge, width):
    blocks = _cell_text(label, width - CELL_GAP * 2)
    if badge:
        spec = {'text': badge, 'bg': pdf.ESMERALD, 'fg': pdf.WHITE}
        height = _badge_size(c, badge, max_width=width - CELL_GAP * 2)[2]
        blocks.append(_CellBlock(height=CELL_GAP + height, badge=spec))
    return blocks


def _payment_option_height(c, label, badge, width):
    return sum(b.height for b in _payment_blocks(c, label, badge, width)) + CELL_GAP * 2 + 8


def _draw_payment_option(c, y, label, badge, width, ps=None):
    blocks = _payment_blocks(c, label, badge, width)
    height = sum(b.height for b in blocks) + CELL_GAP * 2
    if ps:
        y = pdf._check_y(c, y, ps, need=height + 8)
    c.setFillColor(pdf.ESMERALD_LIGHT)
    c.roundRect(pdf.MARGIN_L, y - height, width, height, 4, fill=1, stroke=0)
    _paint_cell(c, pdf.MARGIN_L + CELL_GAP, y - CELL_GAP, blocks, width - CELL_GAP * 2)
    return y - height - 8


def _draw_contact_value(c, y, value, link=None, ps=None):
    lines = pdf._wrap_paragraph_lines(value, pdf._font('regular'), 9, pdf.CONTENT_W)
    for line in lines:
        if line is None:
            y -= PARAGRAPH_GAP
            continue
        if ps:
            y = pdf._check_y(c, y, ps, need=20)
        c.setFont(pdf._font('regular'), 9)
        c.setFillColor(pdf.ESMERALD_80)
        end_x = pdf._draw_mixed_string(c, pdf.MARGIN_L, y, line, pdf._font('regular'), 9)
        if link:
            c.linkURL(link, (pdf.MARGIN_L, y - 2, end_x, y + 10), relative=0)
        y -= 13
    return y - BLOCK_GAP
