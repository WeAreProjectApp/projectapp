"""
Service for generating branded PDF documents from structured JSON blocks
using the shared PDF utilities (ReportLab).

Reuses the Project App brand palette, fonts, header/footer, and cover
pages from the proposal PDF system.
"""

import io
import logging
import math
import textwrap

from django.utils import timezone as _tz
from django.utils.text import slugify
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.services.document_content import resolve_blocks
from content.services.pdf_theme import get_theme
from content.services.pdf_utils import (
    _register_fonts, _font,
    ESMERALD, ESMERALD_DARK, ESMERALD_LIGHT, GREEN_LIGHT, LEMON, BONE,
    GRAY_500, GRAY_300, WHITE, ESMERALD_80,
    COVER_PDF, BACK_COVER_PDF,
    PAGE_W, PAGE_H, MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B, CONTENT_W,
    _sanitize_pdf_text, _replace_urls_with_placeholders,
    _draw_line_with_links, _draw_mixed_string, _draw_mixed_centred,
    _mixed_string_width,
    _wrap_by_width, _table_col_widths,
    _new_page, _check_y,
    _draw_header_bar, _draw_footer,
    _draw_section_header, _draw_paragraphs, _draw_bullet_list,
    _draw_subtitle, _draw_banner_box,
    _draw_table, _draw_blockquote, _draw_code_block, _draw_separator,
    _draw_callout_box,
)

logger = logging.getLogger(__name__)

_TOC_LINE_H = 18  # vertical spacing per TOC entry (points)


class DocumentPdfService:
    """Generate a branded PDF from a Document model instance."""

    @classmethod
    def generate_from_markdown(
        cls,
        *,
        title,
        markdown_text,
        client_name='',
        include_portada=True,
        include_subportada=True,
        include_contraportada=True,
        language='es',
        template_style='professional',
    ):
        """Render PDF bytes from raw markdown without persisting a Document."""
        from content.models import Document
        from content.services.markdown_parser import markdown_to_blocks

        blocks = markdown_to_blocks(markdown_text or '')
        meta = {
            'title': title,
            'client_name': client_name,
            'cover_type': 'generic',
            'include_portada': include_portada,
            'include_subportada': include_subportada,
            'include_contraportada': include_contraportada,
        }
        document = Document(
            title=title,
            client_name=client_name,
            language=language,
            cover_type='generic',
            include_portada=include_portada,
            include_subportada=include_subportada,
            include_contraportada=include_contraportada,
            content_markdown=markdown_text or '',
            content_json={'meta': meta, 'blocks': blocks},
        )
        document.template_style = template_style
        return cls.generate(document, template_style=template_style)

    @classmethod
    def generate(cls, document, template_style=None):
        """Generate PDF bytes from a Document instance.

        Args:
            document: Document model instance with content_json populated.
            template_style: Optional explicit style ('professional' |
                'friendly'). Falls back to ``document.template_style`` when
                not given, then defaults to 'professional'.

        Returns:
            bytes: PDF content, or None on failure.
        """
        try:
            _register_fonts()

            style = (
                template_style
                or getattr(document, 'template_style', None)
                or 'professional'
            )
            theme = get_theme(style)

            meta = (document.content_json or {}).get('meta', {})
            blocks = resolve_blocks(document)

            if not blocks:
                logger.warning('Document %s has no blocks to render', document.id)
                return None

            # --- Two-pass TOC setup -------------------------------------------
            has_toc = any(b.get('type') == 'toc' for b in blocks)
            toc_entries = []
            toc_by_idx = {}
            if has_toc:
                raw_entries, toc_insert_page = cls._collect_section_pages(document, theme)
                toc_pages = cls._estimate_toc_pages(raw_entries)
                for entry in raw_entries:
                    if entry['page'] >= toc_insert_page:
                        entry['page'] += toc_pages
                toc_entries = raw_entries
                toc_by_idx = {e['block_idx']: e for e in toc_entries}
            # ------------------------------------------------------------------

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)

            ps = {
                'num': 1,
                'client': meta.get('client_name', document.client_name or ''),
                'total': None,
                'theme': theme,
            }

            include_portada = document.include_portada
            include_subportada = document.include_subportada
            include_contraportada = document.include_contraportada

            # Start first page
            _draw_header_bar(c, theme=theme)
            y = PAGE_H - MARGIN_T

            # Render title page (subportada) if requested
            if include_subportada:
                y = cls._render_title_page(c, document, meta, ps, theme)
                # Start new page for content
                _draw_footer(c, ps['num'], client_name=ps['client'])
                c.showPage()
                ps['num'] += 1
                _draw_header_bar(c, theme=theme)
                y = PAGE_H - MARGIN_T

            # Render blocks
            first_block = True
            for idx, block in enumerate(blocks):
                block_type = block.get('type', '')

                # Handle TOC block: render the table of contents page
                if block_type == 'toc':
                    if has_toc:
                        if not first_block:
                            _draw_footer(c, ps['num'], client_name=ps['client'])
                            c.showPage()
                            ps['num'] += 1
                            _draw_header_bar(c, theme=theme)
                            y = PAGE_H - MARGIN_T
                        y = cls._render_toc(c, y, toc_entries, ps)
                        _draw_footer(c, ps['num'], client_name=ps['client'])
                        c.showPage()
                        ps['num'] += 1
                        _draw_header_bar(c, theme=theme)
                        y = PAGE_H - MARGIN_T
                        first_block = True
                    continue

                if not first_block and block_type in ('section_header', 'heading'):
                    y -= 28
                    y = _check_y(c, y, ps, need=80)
                elif not first_block:
                    y -= 6

                first_block = False

                if block_type == 'rich_html':
                    from content.services.editorial_pdf import draw_editorial_html
                    y = draw_editorial_html(c, y, block.get('html', ''), ps=ps, color=theme.body_color)
                elif block_type == 'heading':
                    if has_toc and idx in toc_by_idx:
                        c.bookmarkPage(toc_by_idx[idx]['key'])
                    y = cls._render_heading(c, y, block, ps, theme)
                elif block_type == 'paragraph':
                    y = cls._render_paragraph(c, y, block, ps, theme)
                elif block_type == 'table':
                    y = cls._render_table(c, y, block, ps, theme)
                elif block_type == 'list':
                    y = cls._render_list(c, y, block, ps, theme)
                elif block_type == 'blockquote':
                    y = cls._render_blockquote(c, y, block, ps, theme)
                elif block_type == 'code':
                    y = cls._render_code(c, y, block, ps, theme)
                elif block_type == 'separator':
                    y = cls._render_separator(c, y, block, ps, theme)
                elif block_type == 'section_header':
                    if has_toc and idx in toc_by_idx:
                        c.bookmarkPage(toc_by_idx[idx]['key'])
                    y = cls._render_section_header(c, y, block, ps, theme)
                elif block_type == 'sub_section':
                    y = cls._render_sub_section(c, y, block, ps)
                elif block_type == 'callout':
                    y = cls._render_callout(c, y, block, ps)

            # Finalize last page
            _draw_footer(c, ps['num'], client_name=ps['client'])
            c.save()

            content_bytes = buf.getvalue()
            buf.close()

            # Merge with covers
            pdf_bytes = cls._merge_with_covers(
                content_bytes,
                include_portada=include_portada,
                include_contraportada=include_contraportada,
            )

            logger.info(
                'Generated document PDF for "%s" (%d bytes, %d pages)',
                document.title, len(pdf_bytes), ps['num'],
            )
            return pdf_bytes

        except Exception:
            logger.exception(
                'Failed to generate PDF for document %s', document.id,
            )
            return None

    @classmethod
    def _render_title_page(cls, c, document, meta, ps, theme):
        """Render a branded title page with decorative elements."""
        # Decorative circle top-right
        c.saveState()
        c.setFillColor(ESMERALD_LIGHT)
        c.circle(PAGE_W - 40, PAGE_H - 40, 140, fill=1, stroke=0)
        c.restoreState()

        # Small accent circle bottom-left
        c.saveState()
        c.setFillColor(BONE)
        c.circle(60, 80, 70, fill=1, stroke=0)
        c.restoreState()

        # Title
        title = _sanitize_pdf_text(meta.get('title', document.title or 'Documento'))
        y = PAGE_H / 2 + 60

        # Subtitle label (above title)
        subtitle = meta.get('subtitle', '')
        if subtitle:
            c.setFont(_font('light'), 14)
            c.setFillColor(GREEN_LIGHT)
            _draw_mixed_centred(c, PAGE_W / 2, y + 30, _sanitize_pdf_text(subtitle),
                                _font('light'), 14)

        # Main title
        c.setFont(_font('light'), 36)
        c.setFillColor(theme.title_color)
        title_lines = textwrap.wrap(title, width=24)
        for line in title_lines:
            _draw_mixed_centred(c, PAGE_W / 2, y, line, _font('light'), 36)
            y -= 44

        # Divider
        y -= 10
        div_w = 60
        c.setStrokeColor(theme.section_rule_color)
        c.setLineWidth(2)
        c.line(PAGE_W / 2 - div_w / 2, y, PAGE_W / 2 + div_w / 2, y)
        c.setFillColor(theme.section_rule_color)
        c.circle(PAGE_W / 2 - div_w / 2 - 3, y, 3, fill=1, stroke=0)
        c.circle(PAGE_W / 2 + div_w / 2 + 3, y, 3, fill=1, stroke=0)

        # Client name
        client = meta.get('client_name', document.client_name or '')
        if client:
            y -= 30
            c.setFont(_font('regular'), 14)
            c.setFillColor(ESMERALD)
            _draw_mixed_centred(c, PAGE_W / 2, y, _sanitize_pdf_text(client),
                                _font('regular'), 14)

        # Date
        date_str = meta.get('date', '')
        if not date_str and document.created_at:
            from content.services.pdf_utils import format_date_es
            date_str = format_date_es(document.created_at)
        if date_str:
            c.setFont(_font('regular'), 9)
            c.setFillColor(GRAY_500)
            c.drawCentredString(PAGE_W / 2, MARGIN_B + 40, date_str)

        return y

    # -- Block renderers -------------------------------------------

    @classmethod
    def _render_heading(cls, c, y, block, ps, theme):
        """Render h1/h2/h3 headings."""
        if block.get('html'):
            from content.services.editorial_pdf import draw_editorial_html
            return draw_editorial_html(c, y, block['html'], ps=ps, color=theme.body_color)
        level = block.get('level', 1)
        text = block.get('text', '')

        if level == 1:
            font_size, font_style, color = 20, 'light', theme.h1_color
            y = _check_y(c, y, ps, need=40)
        elif level == 2:
            font_size, font_style, color = 16, 'bold', theme.h2_color
            y = _check_y(c, y, ps, need=30)
        else:
            font_size, font_style, color = 13, 'bold', theme.h3_color
            y = _check_y(c, y, ps, need=24)

        fn = _font(font_style)
        # Width-accurate wrapping/drawing keeps measure == draw and emoji-safe.
        lines = _wrap_by_width(text, fn, font_size, CONTENT_W)
        for line in lines:
            _draw_line_with_links(c, MARGIN_L, y, line, fn, font_size, color,
                                  link_color=theme.link_color)
            y -= font_size + 6

        if level <= 2:
            # Accent line under h1/h2.
            c.setStrokeColor(theme.heading_rule_color)
            if theme.heading_rule_full:
                c.setLineWidth(1)
                c.line(MARGIN_L, y + 4, MARGIN_L + CONTENT_W, y + 4)
            else:
                c.setLineWidth(2)
                c.line(MARGIN_L, y + 4, MARGIN_L + 60, y + 4)
            y -= 12

        return y

    @staticmethod
    def _render_paragraph(c, y, block, ps, theme):
        """Render a paragraph."""
        text = block.get('text', '')
        if not text:
            return y
        y = _draw_paragraphs(c, y, [text], max_width=CONTENT_W, ps=ps,
                              color=theme.body_color, link_color=theme.link_color)
        return y

    @staticmethod
    def _render_table(c, y, block, ps, theme):
        """Render a table with content-proportional column widths."""
        headers = block.get('headers', [])
        rows = block.get('rows', [])
        if not headers:
            return y
        # Size columns to their content, then hand the drawer relative
        # fractions (its col_widths are normalised by their sum).
        abs_widths = _table_col_widths(headers, rows, CONTENT_W, 6)
        total = sum(abs_widths)
        col_widths = [w / total for w in abs_widths] if total > 0 else None
        return _draw_table(c, y, headers, rows, ps=ps,
                           col_widths=col_widths, theme=theme)

    @staticmethod
    def _render_list(c, y, block, ps, theme):
        """Render ordered or unordered list."""
        items = block.get('items', [])
        ordered = block.get('ordered', False)
        if not items:
            return y
        return _draw_bullet_list(c, y, items, max_width=CONTENT_W, ps=ps,
                                  numbered=ordered, color=theme.body_color,
                                  link_color=theme.link_color)

    @staticmethod
    def _render_blockquote(c, y, block, ps, theme):
        """Render a blockquote."""
        text = block.get('text', '')
        if not text:
            return y
        return _draw_blockquote(c, y, text, ps=ps, theme=theme)

    @staticmethod
    def _render_code(c, y, block, ps, theme):
        """Render a code block."""
        content = block.get('content', '')
        language = block.get('language', 'text')
        if not content:
            return y
        return _draw_code_block(c, y, content, ps=ps, language=language, theme=theme)

    @staticmethod
    def _render_separator(c, y, block, ps, theme):
        """Render a horizontal separator."""
        return _draw_separator(c, y, ps=ps, theme=theme)

    @staticmethod
    def _render_section_header(c, y, block, ps, theme):
        """Render a numbered section header."""
        index = block.get('index', '')
        title = block.get('title', '')
        return _draw_section_header(c, y, index, title, ps=ps, theme=theme)

    @staticmethod
    def _render_sub_section(c, y, block, ps):
        """Render a sub-section header."""
        index = block.get('index', '')
        title = block.get('title', '')

        y = _check_y(c, y, ps, need=24)

        # Draw index in lighter color
        if index:
            c.setFont(_font('medium'), 9)
            c.setFillColor(GREEN_LIGHT)
            c.drawString(MARGIN_L, y, index)
            y -= 4

        # Draw title
        y = _draw_subtitle(c, y, title, ps=ps)
        return y

    @staticmethod
    def _render_callout(c, y, block, ps):
        """Render a GitHub-style callout box (note/tip/warning/caution/important)."""
        style = block.get('style', 'note')
        text  = block.get('text', '')
        if not text:
            return y
        return _draw_callout_box(c, y, text, style=style, ps=ps)

    @classmethod
    def _collect_section_pages(cls, document, theme):
        """Dry-run render (skipping toc blocks) to find which page each section lands on.

        Uses the SAME theme as the real render pass so pagination (and thus
        TOC page numbers) can't drift between the two passes.

        Returns:
            (entries, toc_insert_page)
            entries: list of dicts with {key, display_title, page, level, block_idx}
            toc_insert_page: page number where the [TOC] block appears
        """
        _register_fonts()
        # Misma resolución de bloques que el pase real: si las dos pasadas no
        # ven exactamente el mismo contenido, los números del TOC se desfasan.
        meta = (document.content_json or {}).get('meta', {})
        blocks = resolve_blocks(document)

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        ps = {'num': 1, 'client': meta.get('client_name', document.client_name or ''),
              'total': None, 'theme': theme}

        _draw_header_bar(c, theme=theme)
        y = PAGE_H - MARGIN_T

        if document.include_subportada:
            y = cls._render_title_page(c, document, meta, ps, theme)
            _draw_footer(c, ps['num'], client_name=ps['client'])
            c.showPage()
            ps['num'] += 1
            _draw_header_bar(c, theme=theme)
            y = PAGE_H - MARGIN_T

        entries = []
        toc_insert_page = ps['num']
        first_block = True

        for idx, block in enumerate(blocks):
            block_type = block.get('type', '')

            if block_type == 'toc':
                toc_insert_page = ps['num']
                first_block = True
                continue

            if not first_block and block_type in ('section_header', 'heading'):
                y -= 28
                y = _check_y(c, y, ps, need=80)
            elif not first_block:
                y -= 6

            first_block = False

            if block_type == 'section_header':
                entries.append({
                    'key': f'sec-{len(entries)}',
                    'display_title': f'{block.get("index", "")}. {block.get("title", "")}',
                    'page': ps['num'],
                    'level': 1,
                    'block_idx': idx,
                })
                y = cls._render_section_header(c, y, block, ps, theme)
            elif block_type == 'heading':
                level = block.get('level', 1)
                if level <= 2:
                    entries.append({
                        'key': f'hdg-{len(entries)}',
                        'display_title': block.get('text', ''),
                        'page': ps['num'],
                        'level': level,
                        'block_idx': idx,
                    })
                y = cls._render_heading(c, y, block, ps, theme)
            elif block_type == 'rich_html':
                from content.services.editorial_pdf import draw_editorial_html
                y = draw_editorial_html(c, y, block.get('html', ''), ps=ps, color=theme.body_color)
            elif block_type == 'paragraph':
                y = cls._render_paragraph(c, y, block, ps, theme)
            elif block_type == 'table':
                y = cls._render_table(c, y, block, ps, theme)
            elif block_type == 'list':
                y = cls._render_list(c, y, block, ps, theme)
            elif block_type == 'blockquote':
                y = cls._render_blockquote(c, y, block, ps, theme)
            elif block_type == 'code':
                y = cls._render_code(c, y, block, ps, theme)
            elif block_type == 'separator':
                y = cls._render_separator(c, y, block, ps, theme)
            elif block_type == 'sub_section':
                y = cls._render_sub_section(c, y, block, ps)
            elif block_type == 'callout':
                y = cls._render_callout(c, y, block, ps)

        buf.close()
        return entries, toc_insert_page

    @classmethod
    def _estimate_toc_pages(cls, entries):
        """Return how many pages the TOC will occupy."""
        available_h = PAGE_H - MARGIN_T - MARGIN_B - 40  # minus heading row
        per_page = max(1, int(available_h / _TOC_LINE_H))
        return max(1, math.ceil(len(entries) / per_page))

    @classmethod
    def _render_toc(cls, c, y, entries, ps):
        """Render a table of contents with clickable internal navigation links."""
        regular = _font('regular')
        bold = _font('bold')

        # TOC heading
        c.setFont(bold, 11)
        c.setFillColor(ESMERALD)
        c.drawString(MARGIN_L, y, 'Índice')
        y -= 8
        c.setStrokeColor(LEMON)
        c.setLineWidth(2)
        c.line(MARGIN_L, y, MARGIN_L + 50, y)
        y -= 22

        for entry in entries:
            if y < MARGIN_B + _TOC_LINE_H:
                _draw_footer(c, ps['num'], client_name=ps.get('client', ''))
                c.showPage()
                ps['num'] += 1
                _draw_header_bar(c, theme=ps.get('theme'))
                y = PAGE_H - MARGIN_T

            key = entry['key']
            title = _sanitize_pdf_text(str(entry['display_title']))
            page_str = str(entry['page'])
            level = entry.get('level', 1)

            indent = 14 if level > 1 else 0
            x = MARGIN_L + indent
            fn = bold if level == 1 else regular
            font_size = 9
            right_x = MARGIN_L + CONTENT_W

            # Title
            c.setFont(fn, font_size)
            c.setFillColor(ESMERALD if level == 1 else ESMERALD_DARK)
            _draw_mixed_string(c, x, y, title, fn, font_size)
            title_w = _mixed_string_width(c, title, fn, font_size)

            # Page number (right-aligned)
            c.setFont(regular, font_size)
            c.setFillColor(GRAY_500)
            pg_w = c.stringWidth(page_str, regular, font_size)
            c.drawRightString(right_x, y, page_str)

            # Dot leader
            dot_char = '.'
            dot_w = c.stringWidth(dot_char, regular, font_size)
            gap_start = x + title_w + 4
            gap_end = right_x - pg_w - 4
            if gap_end > gap_start and dot_w > 0:
                c.setFillColor(GRAY_300)
                c.drawString(gap_start, y, dot_char * max(1, int((gap_end - gap_start) / dot_w)))

            # Clickable link to the bookmark
            c.linkAbsolute('', key, (x, y - 2, right_x, y + font_size))

            y -= _TOC_LINE_H

        return y

    @classmethod
    def _merge_with_covers(cls, content_bytes, include_portada=True, include_contraportada=True):
        """Merge content with cover PDFs based on include_* flags.

        Delegates to the shared ``merge_with_covers`` in pdf_utils.
        """
        from content.services.pdf_utils import merge_with_covers
        return merge_with_covers(
            content_bytes,
            include_portada=include_portada,
            include_contraportada=include_contraportada,
        )
