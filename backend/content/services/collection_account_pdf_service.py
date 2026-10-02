"""
Generate a branded PDF for collection account documents from relational data.

The page is cut to its content instead of forcing an A4 sheet: we bill three
concepts (development, diagnostics, hosting), never by units and never with
itemised taxes, so an A4 cuenta de cobro was half empty. Width is fixed at A5
(148mm) and the height comes from measuring the content — see `generate`.
"""
import io
import logging

from reportlab.lib.pagesizes import A5
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from content.services.collection_account_service import is_collection_account
from content.services.pdf_utils import (
    ESMERALD,
    ESMERALD_LIGHT,
    GRAY_700,
    _draw_footer,
    _draw_header_bar,
    _draw_logo_watermark,
    _font,
    _format_cop,
    _register_fonts,
    amount_in_words_es,
    format_date_es,
)

logger = logging.getLogger(__name__)

_IDENT_LABELS = {'NIT': 'NIT', 'CC': 'C.C.'}

# ── Page geometry ────────────────────────────────────────────
# Local on purpose: PAGE_W/PAGE_H in pdf_utils are shared by every other
# generator (proposals, contracts, technical docs) and must stay A4.
PAGE_W = A5[0]                      # 419.5pt ≈ 148mm
MARGIN_X = 36                       # 48 suited 595pt of width, not 420
MARGIN_TOP = 44
MARGIN_BOTTOM = 40
CONTENT_W = PAGE_W - 2 * MARGIN_X   # ≈ 348pt

# Measuring canvas: never saved, so ReportLab does not care that this is far
# beyond the format's real limit. It only has to be taller than any content.
_PROBE_H = 200_000
# A PDF page cannot exceed 14400pt a side. Past that we fall back to paging.
_MAX_PAGE_H = 14400

_AMOUNT_COL_W = 70                  # room for "$1.490.000" at 8pt

# ── "Formas de pago" box ─────────────────────────────────────
# The client's next action after reading the total is paying, so the payment
# data gets a filled box of its own instead of the single 8pt line it used to
# share with the footer.
_PAY_PAD = 12                       # inner padding of the box
_PAY_LABEL_W = 84                   # "Número de cuenta" at 8pt bold plus air
_PAY_ROW_H = 11
_PAY_VALUE_W = CONTENT_W - 2 * _PAY_PAD - _PAY_LABEL_W


def _ident_line(id_type, number):
    """'NIT 901234567' / 'C.C. 12345678' / bare number when untyped."""
    if not number:
        return ''
    label = _IDENT_LABELS.get((id_type or '').upper(), id_type or '')
    return f'{label} {number}'.strip()


def _wrap(text, style, size, width):
    """Split *text* into lines that fit *width*, measured in the real font.

    Replaces the old fixed character truncation, which silently dropped text
    and was calibrated for A4's wider column.

    Authored line breaks survive, blank lines included: the descripción del
    concepto is written in the panel as several paragraphs, and the blank line
    between them is what makes an enumeration of requirements readable.
    `simpleSplit` does split on '\\n', but it drops an empty line on the floor
    — hence the per-paragraph loop and the ``or ['']``. Empty input still
    yields no lines at all, so a missing value consumes no vertical space.
    The CRLF normalisation is for text that reached us from a textarea.
    """
    normalised = str(text or '').replace('\r\n', '\n').replace('\r', '\n')
    if not normalised:
        return []
    font = _font(style)
    lines = []
    for paragraph in normalised.split('\n'):
        lines.extend(simpleSplit(paragraph, font, size, width) or [''])
    return lines


def _payment_blocks(methods):
    """Pre-measure each payment method into ``(title, rows, instructions)``.

    Everything is wrapped up front because the box is painted before its own
    text — its height has to be known while the cursor is still at the top.
    """
    blocks = []
    for method in methods:
        rows = []
        for label, value in (
            ('Entidad', method.bank_name),
            ('Tipo de cuenta', method.account_type),
            ('Número de cuenta', method.account_number),
            ('Titular', method.account_holder_name),
            # The holder's id continues the Titular row rather than opening one
            # of its own: it qualifies the name, it is not a separate fact.
            ('', method.account_holder_identification),
        ):
            if value:
                rows.append((label, _wrap(value, 'regular', 8, _PAY_VALUE_W)))
        instructions = _wrap(
            method.payment_instructions, 'regular', 8, CONTENT_W - 2 * _PAY_PAD,
        ) if method.payment_instructions else []
        blocks.append((
            method.get_payment_method_type_display(), rows, instructions,
        ))
    return blocks


def _payment_box_height(blocks):
    """Height the whole box will consume, headings and padding included.

    Every line is counted by its leading, so the last one already carries the
    air under its own baseline and the bottom padding lands even with the top.
    """
    height = 2 * _PAY_PAD + 14          # top/bottom padding + 'Formas de pago'
    for index, (_, rows, instructions) in enumerate(blocks):
        if index:
            height += 8                 # air between two methods
        height += 13                    # the method's own title
        height += sum(len(lines) for _, lines in rows) * _PAY_ROW_H
        height += len(instructions) * _PAY_ROW_H
    return height


def _draw_payment_methods(c, y, methods, ensure_space):
    """Draw the 'Formas de pago' box and return the ``y`` below it."""
    blocks = _payment_blocks(methods)
    if not blocks:
        return y

    box_h = _payment_box_height(blocks)
    ensure_space(box_h + 6)

    box_bottom = y - box_h
    c.setFillColor(ESMERALD_LIGHT)
    c.roundRect(
        MARGIN_X, box_bottom, CONTENT_W, box_h, 6, fill=1, stroke=0,
    )

    text_x = MARGIN_X + _PAY_PAD
    y -= _PAY_PAD + 10
    c.setFont(_font('bold'), 10)
    c.setFillColor(ESMERALD)
    c.drawString(text_x, y, 'Formas de pago')
    y -= 14

    for index, (title, rows, instructions) in enumerate(blocks):
        if index:
            y -= 8
        c.setFont(_font('medium'), 9)
        c.setFillColor(ESMERALD)
        c.drawString(text_x, y, title)
        y -= 13
        for label, lines in rows:
            if label:
                c.setFont(_font('bold'), 8)
                c.setFillColor(GRAY_700)
                c.drawString(text_x, y, label)
            c.setFont(_font('regular'), 8)
            c.setFillColor(GRAY_700)
            for line in lines:
                c.drawString(text_x + _PAY_LABEL_W, y, line)
                y -= _PAY_ROW_H
        for line in instructions:
            c.setFont(_font('regular'), 8)
            c.setFillColor(GRAY_700)
            c.drawString(text_x, y, line)
            y -= _PAY_ROW_H

    # The box bottom, not the text cursor: the cursor sits a full row below the
    # last baseline, which would pad the page with a phantom empty line.
    return box_bottom


class CollectionAccountPdfService:
    """Build PDF bytes from a Document with collection_account extension."""

    @classmethod
    def generate(cls, document):
        if not is_collection_account(document):
            logger.warning('Document %s is not a collection account', document.id)
            return None
        ext = getattr(document, 'collection_account', None)
        if ext is None:
            logger.warning('Document %s has no collection_account row', document.id)
            return None

        try:
            _register_fonts()

            # Two passes. The layout is a chain of relative `y` decrements, so
            # the height it consumes does not depend on where it starts — draw
            # it once on a throwaway tall canvas to measure, then for real on a
            # page cut to exactly that. Nothing from the first pass is kept.
            # The watermark costs a raster decode and changes no `y`, so the
            # discarded pass does not pay for it.
            probe = canvas.Canvas(io.BytesIO(), pagesize=(PAGE_W, _PROBE_H))
            content_h = _PROBE_H - cls._draw(
                probe, document, ext, _PROBE_H, watermark=False,
            )
            page_h = min(_MAX_PAGE_H, content_h + MARGIN_BOTTOM)

            # The page was cut to fit, so paging is off for the real pass:
            # `ensure_space` reserves a rounded-up estimate and would break a
            # phantom second page on the last line. It stays on only when the
            # content did not fit the format's maximum page height.
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(PAGE_W, page_h))
            cls._set_metadata(c, document, ext)
            cls._draw(c, document, ext, page_h, paginate=page_h >= _MAX_PAGE_H)
            c.save()
            out = buf.getvalue()
            buf.close()
            return out
        except Exception:
            logger.exception('Collection account PDF failed for document %s', document.id)
            return None

    @classmethod
    def _set_metadata(cls, c, document, ext):
        """Fill the PDF's DocInfo so viewers can name and file the document.

        Without `/Title` a viewer has nothing to show but "untitled" — the
        download filename lives in a Content-Disposition header the PDF itself
        never sees. `/CreationDate` is written by ReportLab on save; it has no
        public setter, so it marks when this copy was rendered.
        """
        title = document.public_number or f'Cuenta de cobro #{document.id}'
        issued = format_date_es(document.issue_date) if document.issue_date else ''
        subject = ' — '.join(
            part for part in (
                'Cuenta de cobro', ext.customer_name or '', issued,
            ) if part
        )
        c.setTitle(title)
        c.setAuthor(ext.payer_name or 'Project App')
        c.setSubject(subject)
        c.setCreator('Project App')

    @classmethod
    def _draw(cls, c, document, ext, page_h, paginate=True, watermark=True):
        """Render the whole document; return the `y` where the content ended.

        Called twice by `generate` — once to measure, once for real.
        """
        page_num = 1
        y = page_h - MARGIN_TOP
        right_x = PAGE_W - MARGIN_X

        def footer():
            _draw_footer(
                c, page_num, client_name=ext.customer_name or '',
                page_w=PAGE_W, margin_x=MARGIN_X, margin_b=MARGIN_BOTTOM,
            )

        def start_page():
            """Chrome every page opens with. The watermark goes first because
            PDF has no z-index: behind the content means painted before it."""
            if watermark:
                _draw_logo_watermark(c, PAGE_W, page_h)
            _draw_header_bar(c, page_w=PAGE_W, page_h=page_h)

        def ensure_space(need):
            """Page break valve. Off on a page cut to content — it only fires
            for a document too tall for the PDF format itself."""
            nonlocal y, page_num
            if not paginate or y - need >= MARGIN_BOTTOM:
                return
            footer()
            c.showPage()
            page_num += 1
            start_page()
            y = page_h - MARGIN_TOP

        def paragraph(text, style, size, color, leading, width=CONTENT_W):
            """Draw wrapped text at the left margin."""
            nonlocal y
            c.setFont(_font(style), size)
            c.setFillColor(color)
            for chunk in _wrap(text, style, size, width):
                ensure_space(leading + 4)
                c.drawString(MARGIN_X, y, chunk)
                y -= leading

        start_page()

        c.setFont(_font('bold'), 16)
        c.setFillColor(ESMERALD)
        c.drawString(MARGIN_X, y, 'Cuenta de cobro')
        y -= 20
        c.setFont(_font('regular'), 10)
        c.setFillColor(GRAY_700)
        c.drawString(MARGIN_X, y, document.public_number or f'#{document.id}')
        y -= 24

        # The stored title is "Cuenta de cobro — <concepto>", so printing it
        # whole repeats the heading right under itself. The concepto alone is
        # the part that carries information.
        paragraph(
            ext.billing_concept or document.title,
            'medium', 11, ESMERALD, 14,
        )
        y -= 8

        def field(label, value):
            nonlocal y
            ensure_space(34)
            c.setFont(_font('bold'), 9)
            c.setFillColor(GRAY_700)
            c.drawString(MARGIN_X, y, label)
            y -= 12
            paragraph(value, 'regular', 9, GRAY_700, 12)
            y -= 6

        # The project gets a labelled line of its own. It used to reach the
        # document only by hiding inside the client's name (a cobro that read
        # "MIMITTOS" next to a personal cédula); naming it explicitly is what
        # lets the Cliente block state the legal holder and nothing else.
        if ext.customer_project_name:
            field('Proyecto', ext.customer_project_name)
        if document.issue_date:
            field('Fecha de emisión', format_date_es(document.issue_date))
        if document.due_date:
            field('Fecha de vencimiento', format_date_es(document.due_date))
        if document.city:
            field('Ciudad', document.city)

        def party(label, values):
            """A party block. The heading was LEMON (#F0FF3D), a colour meant
            for the dark header bar — about 1.2:1 against white, so it read as
            blank. Brand green instead."""
            nonlocal y
            y -= 8
            ensure_space(52)
            c.setFont(_font('bold'), 10)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_X, y, label)
            y -= 14
            for value in values:
                if value:
                    paragraph(value, 'regular', 9, GRAY_700, 12)
            y -= 8

        # "Pagador" printed the issuer's own data (see _fill_payer_from_issuer);
        # the party who pays is the client, below.
        party('Emisor', (
            ext.payer_name,
            _ident_line(ext.payer_identification_type, ext.payer_identification),
            ext.payer_address,
            ext.payer_phone,
            ext.payer_email,
        ))
        party('Cliente', (
            ext.customer_name,
            _ident_line(
                ext.customer_identification_type, ext.customer_identification,
            ),
            ext.customer_contact_name,
            ext.customer_email,
            ext.customer_address,
        ))

        y -= 2
        ensure_space(60)
        c.setFont(_font('bold'), 10)
        c.setFillColor(ESMERALD)
        c.drawString(MARGIN_X, y, 'Detalle')
        y -= 16

        # No "Cant." column: nothing here is billed by units.
        c.setFont(_font('bold'), 8)
        c.setFillColor(ESMERALD)
        c.drawString(MARGIN_X, y, 'Descripción')
        c.drawRightString(right_x, y, 'Total')
        y -= 10
        c.setStrokeColor(GRAY_700)
        c.setLineWidth(0.4)
        c.line(MARGIN_X, y, right_x, y)
        y -= 12

        desc_w = CONTENT_W - _AMOUNT_COL_W - 10
        for item in document.items.all().order_by('position', 'id'):
            # A descripción can run to several paragraphs, so the space is
            # reserved line by line rather than for the whole item: reserving
            # the block up front asks for more than a page fits and breaks
            # ahead of text that would have flowed fine.
            chunks = _wrap(item.description, 'regular', 8, desc_w) or ['']
            amount = _format_cop(item.line_total)
            for index, chunk in enumerate(chunks):
                ensure_space(11)
                c.setFont(_font('regular'), 8)
                c.setFillColor(GRAY_700)
                c.drawString(MARGIN_X, y, chunk)
                if index == 0:
                    c.drawRightString(right_x, y, amount)
                y -= 11
            y -= 3

        if ext.vat_rate is not None or document.tax_total:
            rate_label = f' ({ext.vat_rate.normalize():f} %)' if ext.vat_rate is not None else ''
            ensure_space(64)
            c.setFont(_font('regular'), 9)
            c.setFillColor(GRAY_700)
            c.drawRightString(right_x, y, f'Valor antes de IVA: {_format_cop(document.total - document.tax_total)}')
            y -= 14
            c.drawRightString(right_x, y, f'IVA{rate_label}: {_format_cop(document.tax_total)}')
            y -= 14

        y -= 9
        ensure_space(34)
        c.setFont(_font('bold'), 10)
        c.setFillColor(ESMERALD)
        c.drawRightString(
            right_x, y,
            f'Total ({document.currency}): {_format_cop(document.total)}',
        )
        y -= 16

        words = amount_in_words_es(document.total)
        if words:
            paragraph(f'Son: {words}', 'regular', 8, GRAY_700, 11)
        y -= 10

        y = _draw_payment_methods(
            c, y, list(document.payment_methods.all()), ensure_space,
        )

        footer()
        return y
