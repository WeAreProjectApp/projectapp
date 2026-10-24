"""
Generate the Acuerdo de Confidencialidad (NDA) PDF for a WebAppDiagnostic.

Loads the default ``ConfidentialityTemplate`` from the database, substitutes
``{placeholders}`` with values from ``diagnostic.confidentiality_params``,
parses the resulting markdown into blocks, and renders a branded PDF using
the same ReportLab pipeline as ``contract_pdf_service``.
"""

import io
import logging
import re

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.services.contractor_identity import (
    UNKNOWN_LABEL,
    resolve_contractor_identity,
)
from content.services.markdown_parser import markdown_to_blocks
from content.services.pdf_utils import (
    CONTENT_W,
    ESMERALD,
    ESMERALD_80,
    GRAY_300,
    GRAY_500,
    LEMON,
    MARGIN_L,
    MARGIN_T,
    PAGE_H,
    _check_y,
    _draw_blockquote,
    _draw_code_block,
    _draw_footer,
    _draw_header_bar,
    _draw_paragraphs,
    _draw_separator,
    _draw_table,
    _font,
    _register_fonts,
    _strip_emoji,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER_BLANK = '_______________'
_PLACEHOLDER_DRAFT = 'XXX-XXX-XXX'

_BODY_FONT = 'Helvetica'
_BODY_BOLD_FONT = 'Helvetica-Bold'
_BODY_SIZE = 11
_BODY_LEADING = 15

_PARAM_KEYS = (
    'client_full_name',
    'client_cedula',
    'client_legal_representative',
    'client_email',
    'contractor_full_name',
    'contractor_nit',
    'contractor_cedula',
    # Computed from the two above by _build_params; listed here so the key set
    # stays the single source of truth for what a params dict contains.
    'contractor_id_type',
    'contractor_id_number',
    'contractor_email',
    'contract_city',
    'contract_day',
    'contract_month',
    'contract_year',
    'penal_clause_value',
)

_DEFAULT_CONTRACTOR = {
    'contractor_full_name': 'Project App SAS',
    'contract_city': 'Medellín',
    'penal_clause_value': 'CINCUENTA SALARIOS MÍNIMOS MENSUALES LEGALES VIGENTES (50 SMMLV)',
}


def _build_params(raw_params: dict, draft: bool = False) -> dict:
    """Build a substitution dict with sensible defaults for missing values.

    When draft=True every value is replaced with XXX-XXX-XXX so no sensitive
    data leaks in draft PDFs sent for client review — except the contractor's
    document type, which is a label rather than data and stays readable.
    """
    if draft:
        out = {key: _PLACEHOLDER_DRAFT for key in _PARAM_KEYS}
        out['contractor_id_type'] = UNKNOWN_LABEL
        out['contractor_id_number'] = _PLACEHOLDER_DRAFT
        return out

    out = {}
    for key in _PARAM_KEYS:
        value = raw_params.get(key) if raw_params else None
        if value:
            out[key] = str(value)
        else:
            out[key] = _DEFAULT_CONTRACTOR.get(key, _PLACEHOLDER_BLANK)

    # Resolve from the raw values, not from `out`: unset fields have already
    # been replaced by the blank filler above, which would read as a NIT.
    id_type, id_number = resolve_contractor_identity(
        (raw_params or {}).get('contractor_nit'),
        (raw_params or {}).get('contractor_cedula'),
        blank=_PLACEHOLDER_BLANK,
    )
    out['contractor_id_type'] = id_type
    out['contractor_id_number'] = id_number
    return out


def _substitute_placeholders(markdown_text: str, params: dict) -> str:
    try:
        return markdown_text.format(**params)
    except (KeyError, IndexError) as exc:
        logger.warning(
            'Unknown placeholder %s in NDA template; falling back to per-key substitution', exc,
        )
        result = markdown_text
        for key, value in params.items():
            result = result.replace('{' + key + '}', str(value))
        return result


def _get_markdown(params: dict) -> str:
    from content.models import ConfidentialityTemplate
    template = ConfidentialityTemplate.get_default()
    if not template:
        logger.error('No default ConfidentialityTemplate found in DB')
        return ''
    text = _substitute_placeholders(template.content_markdown, params)
    return re.sub(r' -- ', ' - ', text)


def _render_block(c, y, block, ps):
    block_type = block.get('type', '')

    if block_type == 'rich_html' or block.get('html'):
        from content.services.editorial_pdf import draw_editorial_html
        return draw_editorial_html(c, y, block.get('html', ''), ps=ps)

    if block_type == 'heading':
        level = block.get('level', 2)
        text = _strip_emoji(block.get('text', ''))
        if level == 1:
            y = _check_y(c, y, ps, need=50)
            c.setFont(_font('bold'), 14)
            c.setFillColor(ESMERALD)
        elif level == 2:
            y = _check_y(c, y, ps, need=40)
            y -= 16
            c.setFont(_font('bold'), 12)
            c.setFillColor(ESMERALD)
        else:
            y = _check_y(c, y, ps, need=30)
            y -= 8
            c.setFont(_font('bold'), 10)
            c.setFillColor(ESMERALD)
        c.drawString(MARGIN_L, y, text)
        y -= 18

    elif block_type == 'paragraph':
        text = block.get('text', '')
        y = _check_y(c, y, ps, need=30)
        y = _draw_paragraphs(
            c, y, [text], ps=ps,
            color=ESMERALD_80, font_size=_BODY_SIZE, leading=_BODY_LEADING,
            font_name=_BODY_FONT, justify=True,
            bold_font_name=_BODY_BOLD_FONT,
        )
        y -= 4

    elif block_type == 'list':
        items = block.get('items', [])
        ordered = block.get('ordered', False)
        y = _check_y(c, y, ps, need=30)
        texts = []
        for i, item in enumerate(items):
            txt = item.get('text', item) if isinstance(item, dict) else str(item)
            if ordered and not txt[0:3].replace('.', '').replace(')', '').strip().isdigit():
                txt = f'{i + 1}. {txt}'
            texts.append(txt)
        y = _draw_paragraphs(
            c, y, texts, ps=ps,
            color=ESMERALD_80, font_size=_BODY_SIZE, leading=_BODY_LEADING,
            x=MARGIN_L + 12,
            max_width=CONTENT_W - 12,
            font_name=_BODY_FONT, justify=True,
            bold_font_name=_BODY_BOLD_FONT,
        )
        y -= 4

    elif block_type == 'separator':
        y = _draw_separator(c, y, ps)

    elif block_type == 'blockquote':
        text = block.get('text', '')
        y = _check_y(c, y, ps, need=30)
        y = _draw_blockquote(c, y, text, ps)

    elif block_type == 'code':
        text = block.get('text', '')
        y = _check_y(c, y, ps, need=40)
        y = _draw_code_block(c, y, text, ps)

    elif block_type == 'table':
        y = _check_y(c, y, ps, need=50)
        headers = block.get('headers', [])
        rows = block.get('rows', [])
        y = _draw_table(c, y, headers, rows, ps)

    return y


def _draw_title_page(c, y, params, ps):
    c.setFont(_font('light'), 22)
    c.setFillColor(ESMERALD)
    c.drawString(MARGIN_L, y, 'ACUERDO DE')
    y -= 28
    c.drawString(MARGIN_L, y, 'CONFIDENCIALIDAD')
    y -= 36

    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(MARGIN_L, y + 6, MARGIN_L + 80, y + 6)
    y -= 18

    c.setFont(_font('bold'), 10)
    c.setFillColor(ESMERALD)
    c.drawString(MARGIN_L, y, f'ENTRE: {params.get("client_full_name", "")} (EL CLIENTE)')
    y -= 16
    c.drawString(MARGIN_L, y, f'Y: {params.get("contractor_full_name", "")} (EL CONSULTOR)')
    y -= 24

    contract_city = params.get('contract_city', '')
    contract_day = params.get('contract_day', '')
    contract_month = params.get('contract_month', '')
    contract_year = params.get('contract_year', '')
    if any([contract_city, contract_day, contract_month, contract_year]):
        c.setFont(_font('regular'), 9)
        c.setFillColor(GRAY_500)
        date_str = (
            f'Suscrito en {contract_city or "_______"} a los '
            f'{contract_day or "__"} días del mes de '
            f'{contract_month or "________"} de {contract_year or "____"}'
        )
        c.drawString(MARGIN_L, y, date_str)
        y -= 20

    return y


def _draw_signature_block(c, y, params, ps):
    need = 160
    y = _check_y(c, y, ps, need=need)
    y -= 20

    c.setFont(_font('bold'), 11)
    c.setFillColor(ESMERALD)
    c.drawString(MARGIN_L, y, 'EN CONSTANCIA DE LO ANTERIOR,')
    y -= 14
    c.setFont(_font('regular'), 9)
    c.setFillColor(ESMERALD_80)
    c.drawString(
        MARGIN_L, y,
        'las partes firman el presente acuerdo en dos (2) ejemplares del mismo tenor.',
    )
    y -= 55

    col1_x = MARGIN_L
    col2_x = MARGIN_L + CONTENT_W / 2 + 10
    sig_width = CONTENT_W / 2 - 20

    c.setStrokeColor(GRAY_300)
    c.setLineWidth(0.6)
    c.line(col1_x, y, col1_x + sig_width, y)
    c.line(col2_x, y, col2_x + sig_width, y)
    y -= 14

    c.setFont(_font('bold'), 9)
    c.setFillColor(ESMERALD)
    c.drawString(col1_x, y, 'EL CLIENTE')
    c.drawString(col2_x, y, 'EL CONSULTOR')
    y -= 14

    c.setFont(_font('regular'), 8)
    c.setFillColor(ESMERALD_80)
    c.drawString(col1_x, y, params.get('client_full_name', ''))
    c.drawString(col2_x, y, params.get('contractor_full_name', ''))
    y -= 12
    c.drawString(col1_x, y, f'C.C./NIT {params.get("client_cedula", "")}')
    contractor_id = f'{params.get("contractor_id_type", "")} {params.get("contractor_id_number", "")}'
    c.drawString(col2_x, y, contractor_id.strip())

    return y


def generate_confidentiality_pdf(diagnostic, draft: bool = False) -> bytes | None:
    """Generate the NDA PDF for a diagnostic; return bytes or None on failure."""
    try:
        raw_params = getattr(diagnostic, 'confidentiality_params', None) or {}
        params = _build_params(raw_params, draft=draft)

        markdown_text = _get_markdown(params)
        if not markdown_text:
            logger.warning(
                'Empty NDA markdown for diagnostic %s', getattr(diagnostic, 'pk', '?'),
            )
            return None

        blocks = markdown_to_blocks(markdown_text)

        _register_fonts()
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        client_label = params.get('client_full_name') or getattr(
            getattr(diagnostic, 'client', None), 'name', '',
        ) or ''
        ps = {'num': 1, 'client': client_label}

        _draw_header_bar(c)
        y = PAGE_H - MARGIN_T

        y = _draw_title_page(c, y, params, ps)

        for block in blocks:
            block_type = block.get('type', '')
            if block_type in ('heading', 'section_header'):
                y -= 12
            y = _render_block(c, y, block, ps)

        _draw_signature_block(c, y, params, ps)

        _draw_footer(c, ps['num'], client_name=ps['client'])
        c.save()
        return buf.getvalue()

    except Exception:
        logger.exception(
            'Failed to generate NDA PDF for diagnostic %s', getattr(diagnostic, 'pk', '?'),
        )
        return None
