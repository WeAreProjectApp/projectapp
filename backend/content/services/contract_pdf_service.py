"""
Generate a contract PDF from a markdown template or custom markdown text.

Two modes:
- **default**: Loads the ContractTemplate from the database, substitutes
  {placeholders} with values from ``proposal.contract_params``, parses
  the resulting markdown into blocks, and renders a branded PDF.
- **custom**: Uses the raw markdown stored in
  ``proposal.contract_params['custom_contract_markdown']`` as-is (no
  placeholder substitution).

Both modes share the same markdown → blocks → ReportLab rendering pipeline.
"""

import io
import logging
import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from content.services.contractor_identity import (
    UNKNOWN_LABEL,
    resolve_contractor_identity,
)
from content.services.markdown_parser import markdown_to_blocks
from content.services.pdf_utils import (
    ESMERALD,
    ESMERALD_80,
    GRAY_500,
    GRAY_300,
    LEMON,
    MARGIN_L,
    MARGIN_T,
    PAGE_H,
    PAGE_W,
    CONTENT_W,
    _check_y,
    _draw_footer,
    _draw_header_bar,
    _draw_paragraphs,
    _draw_separator,
    _draw_table,
    _draw_blockquote,
    _draw_code_block,
    _font,
    _register_fonts,
    _strip_emoji,
    _wrap_by_width,
)

logger = logging.getLogger(__name__)

# Placeholder default values when a param is missing
_PLACEHOLDER_BLANK = '_______________'
_PLACEHOLDER_DRAFT = 'XXX-XXX-XXX'

# Helvetica for contract body — clean sans-serif, similar to Arial
_CONTRACT_BODY_FONT = 'Helvetica'
_CONTRACT_BOLD_FONT = 'Helvetica-Bold'
_CONTRACT_BODY_SIZE = 11
_CONTRACT_BODY_LEADING = 15


def _build_params(raw_params: dict, draft: bool = False) -> dict:
    """Build a substitution dict with sensible defaults for missing values.

    When draft=True all fields are replaced with XXX-XXX-XXX regardless of
    what is stored in contract_params, so no sensitive data is exposed in
    draft PDFs sent or downloaded for client review.

    ``contractor_nit`` and ``contractor_cedula`` are carried through raw even
    though the shipped template no longer references them. Templates are
    hand-editable from Django admin and the v7 patch only rewrites anchors it
    finds, so a drifted copy can still hold ``{contractor_nit}``; dropping the
    key would make format() raise and leak a literal ``{contractor_nit}`` into
    a signed PDF. It also keeps a rollback of v7 working with no code change.
    """
    if draft:
        blank = _PLACEHOLDER_DRAFT
        return {
            'contractor_full_name': blank,
            'contractor_nit': blank,
            'contractor_cedula': blank,
            # The type is a label, not sensitive data, so it stays readable in
            # drafts instead of being masked like the values around it.
            'contractor_id_type': UNKNOWN_LABEL,
            'contractor_id_number': blank,
            'contractor_email': blank,
            'bank_name': blank,
            'bank_account_type': blank,
            'bank_account_number': blank,
            'contract_city': blank,
            'client_full_name': blank,
            'client_cedula': blank,
            'client_email': blank,
            'contract_date': blank,
        }
    blank = _PLACEHOLDER_BLANK
    id_type, id_number = resolve_contractor_identity(
        raw_params.get('contractor_nit'),
        raw_params.get('contractor_cedula'),
        blank=blank,
    )
    return {
        'contractor_full_name': raw_params.get('contractor_full_name', blank),
        'contractor_nit': raw_params.get('contractor_nit', blank),
        'contractor_cedula': raw_params.get('contractor_cedula', blank),
        'contractor_id_type': id_type,
        'contractor_id_number': id_number,
        'contractor_email': raw_params.get('contractor_email', blank),
        'bank_name': raw_params.get('bank_name', blank),
        'bank_account_type': raw_params.get('bank_account_type', 'Ahorros'),
        'bank_account_number': raw_params.get('bank_account_number', blank),
        'contract_city': raw_params.get('contract_city', 'Medellín'),
        'client_full_name': raw_params.get('client_full_name', blank),
        'client_cedula': raw_params.get('client_cedula', blank),
        'client_email': raw_params.get('client_email', blank),
        'contract_date': raw_params.get('contract_date', ''),
    }


def _substitute_placeholders(markdown_text: str, params: dict) -> str:
    """Replace {placeholders} in the markdown template with param values."""
    try:
        return markdown_text.format(**params)
    except KeyError as exc:
        logger.warning('Unknown placeholder %s in contract template; falling back to per-key substitution', exc)
        result = markdown_text
        for key, value in params.items():
            result = result.replace('{' + key + '}', str(value))
        return result


def _get_contract_markdown(
    raw_params: dict,
    params: dict,
    *,
    force_default: bool = False,
) -> str:
    """Return the final markdown text for the contract PDF."""
    source = 'default' if force_default else raw_params.get('contract_source', 'default')

    if source == 'custom':
        markdown = raw_params.get('custom_contract_markdown', '')
    else:
        # Default: load template from DB and substitute placeholders
        from content.models import ContractTemplate
        template = ContractTemplate.get_default()
        if not template:
            logger.error('No default ContractTemplate found in DB')
            return ''
        markdown = _substitute_placeholders(template.content_markdown, params)

    return re.sub(r' -- ', ' - ', markdown)


def render_default_contract_draft_markdown():
    """Return the current default template and its safely masked markdown.

    This is the single source for the public contract preview. It deliberately
    ignores every proposal's ``contract_params`` so custom contracts and real
    party data can never leak through the generic legal module.
    """
    from content.models import ContractTemplate

    template = ContractTemplate.get_default()
    if not template:
        return None
    params = _build_params({}, draft=True)
    markdown = _substitute_placeholders(template.content_markdown, params)
    return template, re.sub(r' -- ', ' - ', markdown)


# ---------------------------------------------------------------------------
# Block rendering — reuses pdf_utils primitives
# ---------------------------------------------------------------------------

def _render_block(c, y, block, ps):
    """Render a single markdown block on the canvas. Returns the new y position."""
    block_type = block.get('type', '')

    if block_type == 'heading':
        level = block.get('level', 2)
        text = _strip_emoji(block.get('text', ''))
        if level == 1:
            y = _check_y(c, y, ps, need=50)
            size = 14
        elif level == 2:
            y = _check_y(c, y, ps, need=40)
            y -= 16
            size = 12
        else:
            y = _check_y(c, y, ps, need=30)
            y -= 8
            size = 10
        # Clause titles such as VIGÉSIMA SEGUNDA are wider than the page;
        # drawn on one line they ran off the paper edge.
        lines = _wrap_by_width(text, _font('bold'), size, CONTENT_W)
        for index, line in enumerate(lines):
            if index:
                y -= size + 4
            c.setFont(_font('bold'), size)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, y, line)
        y -= 18

    elif block_type == 'paragraph':
        text = block.get('text', '')
        y = _check_y(c, y, ps, need=30)
        y = _draw_paragraphs(
            c, y, [text], ps=ps,
            color=ESMERALD_80, font_size=_CONTRACT_BODY_SIZE, leading=_CONTRACT_BODY_LEADING,
            font_name=_CONTRACT_BODY_FONT, justify=True,
            bold_font_name=_CONTRACT_BOLD_FONT,
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
            color=ESMERALD_80, font_size=_CONTRACT_BODY_SIZE, leading=_CONTRACT_BODY_LEADING,
            x=MARGIN_L + 12,
            max_width=CONTENT_W - 12,
            font_name=_CONTRACT_BODY_FONT, justify=True,
            bold_font_name=_CONTRACT_BOLD_FONT,
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
    """Draw the contract title section on the first page."""
    c.setFont(_font('light'), 22)
    c.setFillColor(ESMERALD)
    c.drawString(MARGIN_L, y, 'CONTRATO DE PRESTACIÓN')
    y -= 28
    c.drawString(MARGIN_L, y, 'DE SERVICIOS')
    y -= 36

    # Accent line
    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(MARGIN_L, y + 6, MARGIN_L + 80, y + 6)
    y -= 18

    # Party header
    c.setFont(_font('bold'), 10)
    c.setFillColor(ESMERALD)
    c.drawString(MARGIN_L, y, f'ENTRE: {params.get("client_full_name", "")} (EL CONTRATANTE)')
    y -= 16
    c.drawString(MARGIN_L, y, f'Y: {params.get("contractor_full_name", "")} (EL CONTRATISTA)')
    y -= 24

    contract_date = params.get('contract_date', '')
    if contract_date:
        c.setFont(_font('regular'), 9)
        c.setFillColor(GRAY_500)
        c.drawString(MARGIN_L, y, f'Fecha: {contract_date}')
        y -= 20

    return y


def _draw_signature_block(c, y, params, ps, signature_path=None):
    """Draw the signature block at the bottom of the contract."""
    need = 220 if signature_path else 160
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
        'las partes firman el presente contrato en dos (2) ejemplares del mismo tenor.',
    )
    y -= 55

    col1_x = MARGIN_L
    col2_x = MARGIN_L + CONTENT_W / 2 + 10
    sig_width = CONTENT_W / 2 - 20

    # Draw contractor signature image above the line
    if signature_path and os.path.isfile(signature_path):
        img = ImageReader(signature_path)
        iw, ih = img.getSize()
        scale = sig_width / iw * 1.1  # slightly larger than column width
        draw_w = iw * scale
        draw_h = ih * scale
        # Left-align the signature image with the start of the line so the
        # visible signature doesn't sit centered over it. If the PNG has
        # internal left-padding the fix belongs in the upload, not here.
        img_x = col2_x
        img_y = y - draw_h * 0.4  # image sits above the line
        c.drawImage(signature_path, img_x, img_y, width=draw_w, height=draw_h, mask='auto')

    c.setStrokeColor(GRAY_300)
    c.setLineWidth(0.6)
    c.line(col1_x, y, col1_x + sig_width, y)
    c.line(col2_x, y, col2_x + sig_width, y)
    y -= 14

    c.setFont(_font('bold'), 9)
    c.setFillColor(ESMERALD)
    c.drawString(col1_x, y, 'EL CONTRATANTE')
    c.drawString(col2_x, y, 'EL CONTRATISTA')
    y -= 14

    c.setFont(_font('regular'), 8)
    c.setFillColor(ESMERALD_80)
    c.drawString(col1_x, y, params.get('client_full_name', ''))
    c.drawString(col2_x, y, params.get('contractor_full_name', ''))
    y -= 12
    c.drawString(col1_x, y, f'C.C. {params.get("client_cedula", "")}')
    contractor_id = f'{params.get("contractor_id_type", "")} {params.get("contractor_id_number", "")}'
    c.drawString(col2_x, y, contractor_id.strip())

    return y


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_contract_content(proposal, draft=False, *, force_default=False):
    """Resolve once so the saved PDF and its text snapshot cannot drift."""
    from content.services.markdown_export import literal

    raw_params = getattr(proposal, 'contract_params', None) or {}
    source = 'default' if force_default else raw_params.get('contract_source', 'default')
    params = _build_params(raw_params, draft=draft)
    markdown = _get_contract_markdown(raw_params, params, force_default=force_default)
    snapshot = markdown
    if source != 'custom' and markdown:
        client = literal(params.get('client_full_name', ''))
        contractor = literal(params.get('contractor_full_name', ''))
        date = literal(params.get('contract_date', ''))
        snapshot = (
            '# CONTRATO DE PRESTACIÓN DE SERVICIOS\n\n'
            f'ENTRE: {client} (EL CONTRATANTE)\n\n'
            f'Y: {contractor} (EL CONTRATISTA)\n\n'
            + (f'Fecha: {date}\n\n' if date else '')
            + markdown
            + '\n\n## EN CONSTANCIA DE LO ANTERIOR,\n\n'
            'las partes firman el presente contrato en dos (2) ejemplares del mismo tenor.\n\n'
            f'**EL CONTRATANTE**\n\n{client}\n\nC.C. {literal(params.get("client_cedula", ""))}\n\n'
            f'**EL CONTRATISTA**\n\n{contractor}\n\n'
            f'{literal(params.get("contractor_id_type", ""))} {literal(params.get("contractor_id_number", ""))}\n'
        )
    return {'params': params, 'source': source, 'markdown': markdown, 'snapshot': snapshot}


def generate_contract_pdf(
    proposal,
    draft=False,
    *,
    force_default=False,
    resolved_content=None,
) -> bytes | None:
    """Generate a contract PDF and return raw bytes, or None on failure.

    When *draft* is True the contractor signature is omitted.
    """
    try:
        content = resolved_content if resolved_content is not None else resolve_contract_content(proposal, draft, force_default=force_default)
        source = content['source']
        params = content['params']

        sig_path = None
        if not draft:
            from content.models import CompanySettings
            company = CompanySettings.load()
            sig_path = company.contractor_signature.path if company.contractor_signature else None

        markdown_text = content['markdown']
        if not markdown_text:
            logger.warning('Empty contract markdown for proposal %s', getattr(proposal, 'pk', '?'))
            return None

        blocks = markdown_to_blocks(markdown_text)

        _register_fonts()
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        ps = {'num': 1, 'client': params.get('client_full_name', '')}

        _draw_header_bar(c)
        y = PAGE_H - MARGIN_T

        # Title page (only for default contracts with param data)
        if source != 'custom':
            y = _draw_title_page(c, y, params, ps)

        # Render markdown blocks
        for block in blocks:
            block_type = block.get('type', '')
            if block_type in ('heading', 'section_header'):
                y -= 12
            y = _render_block(c, y, block, ps)

        # Signature block (only for default contracts)
        if source != 'custom':
            _draw_signature_block(c, y, params, ps, signature_path=sig_path)

        _draw_footer(c, ps['num'], client_name=ps['client'])
        c.save()
        return buf.getvalue()

    except Exception:
        logger.exception('Failed to generate contract PDF for proposal %s', getattr(proposal, 'pk', '?'))
        return None
