"""
Service for generating professional PDF business proposals
using ReportLab.

Each enabled section is rendered on portrait-A4 pages with the
Project App brand palette (esmerald / lemon / bone) and Ubuntu
typography.  Long sections flow across multiple pages automatically.

Shared PDF utilities (fonts, colours, drawing helpers) live in
``pdf_utils.py`` and are re-exported here for backward compatibility.
"""

import io
import logging
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.services.hour_package_service import (
    apply_manual_hour_rates,
    seed_commercial_conditions_from_catalog,
)
from content.services.proposal_hosting_terms import resolve_hosting_terms
from content.services.proposal_pdf_sections import ordered_commercial_sections
from content.services.pdf_utils import (  # noqa: F401 — re-exported
    _register_fonts,
    _font,
    # Brand colours
    ESMERALD,
    ESMERALD_DARK,
    ESMERALD_LIGHT,
    GREEN_LIGHT,
    LEMON,
    BONE,
    WINDOW_BLACK,
    GRAY_700,
    GRAY_500,
    GRAY_300,
    GRAY_200,
    WHITE,
    ESMERALD_80,
    # Cover paths
    COVER_PDF,
    BACK_COVER_PDF,
    # Page dimensions
    PAGE_W,
    PAGE_H,
    MARGIN_L,
    MARGIN_R,
    MARGIN_T,
    MARGIN_B,
    CONTENT_W,
    TEXT_AREA_W,
    SIDEBAR_X,
    SIDEBAR_W,
    # Accent / semantic colours
    MINT_TEXT,
    LINK_GREEN,
    # Text utilities
    _strip_emoji,
    _sanitize_pdf_text,
    _draw_mixed_string,
    _draw_mixed_centred,
    _string_width_mixed,
    _measure_inline_width,
    _wrap_by_width,
    _fit_text_ellipsis,
    _format_cop,
    _clean_url_display,
    _replace_urls_with_placeholders,
    _draw_line_with_links,
    _safe,
    # Pagination helpers
    _new_page,
    _check_y,
    _check_y_with_redraw,
    _split_lines_for_page,
    # Drawing helpers
    _draw_header_bar,
    _draw_footer,
    _draw_section_header,
    _section_header_height,
    _draw_bullet_list,
    _sidebar_box_height,
    _draw_sidebar_box,
    _draw_pill,
    _draw_banner_box,
    _draw_callout_box,
    _draw_blockquote,
    _draw_kpi_tile_row,
    _draw_priority_pill,
    _priority_pill_width,
    _clean_cell_text,
    _REQ_PRIORITY_LABELS,
    _apply_toc_links,
    _draw_toc_page,
    format_date_es,
    # Markdown helpers
    _parse_markdown_lines,
    _clean_inline_bold,
    _BR_TAG_RE,
    _HTML_TAG_RE,
)

from content.services.proposal_pdf_layout import (
    _draw_paragraphs, _estimate_text_height, _draw_subtitle, _draw_table,
    _draw_badge_group, _draw_heading_badge, _draw_requirements_table,
    _draw_linked_row, BADGE_GAP, _paint_badge, _draw_feature_row,
    _draw_badge_panel, _payment_option_height, _draw_payment_option, _heading_badge_height,
    _draw_contact_value,
)

logger = logging.getLogger(__name__)


def _filter_calculator_groups(groups, sel_ids):
    """Filter out calculator-module groups that were not selected.

    Non-calculator groups always pass through. Calculator modules
    (``is_calculator_module=True``) are only kept when their ID appears
    in *sel_ids*.  When *sel_ids* is ``None`` (no selection provided),
    **all** calculator modules are excluded.

    A calc module with an explicit ``selected=False`` is also excluded,
    even if its ID is in *sel_ids* (the totals canonical rule includes it
    via ``default_selected``, but the FR display follows the frontend
    nullish-coalescing rule ``selected ?? default_selected`` so the PDF
    list matches what the client sees in the public view).
    """
    kept = []
    for g in groups:
        if not _safe(g, 'is_calculator_module'):
            kept.append(g)
            continue
        if sel_ids is None or f"module-{_safe(g, 'id')}" not in sel_ids:
            continue
        # Display-only override: if the admin explicitly set selected=False,
        # hide it from the FR section even though it counts toward effective.
        if isinstance(g, dict) and g.get('selected') is False:
            continue
        kept.append(g)
    return kept


def default_selected_modules_from_content(proposal, has_confirmed=None):
    """Resolve default selected module IDs for a PDF render.

    The ``has_confirmed`` flag determines whether
    ``BusinessProposal.selected_modules`` is authoritative. When ``True``,
    the persisted list is used literally (an empty list means "client
    confirmed zero modules" — the PDF must hide all optional sections).
    When ``False``, the list is ignored and the admin's
    ``selected`` / ``default_selected`` flags in ``content_json`` are used
    as the initial scope — the client has not customized yet.

    If ``has_confirmed`` is ``None`` (default), it is resolved from the
    model property so external callers without the flag in hand keep
    working.

    Returns a list of canonical module IDs (``module-<id>`` / ``group-<id>``)
    ready to be passed as ``selected_modules`` to
    :meth:`ProposalPdfService.generate`.
    """
    from content.services.proposal_service import (
        admin_default_calculator_group_ids,
        admin_pinned_calculator_group_ids,
        normalize_selected_module_ids,
    )

    if has_confirmed is None:
        has_confirmed = proposal.has_confirmed_module_selection

    sections = list(proposal.sections.all())
    fr = next(
        (s for s in sections if s.section_type == 'functional_requirements'),
        None,
    )
    fr_content = fr.content_json if fr else None

    if has_confirmed:
        # The client's confirmed list — unioned with the calculator modules the
        # admin pinned explicitly (``selected is True``), which always win even
        # over an empty confirmation, mirroring the public client view.
        pinned = [
            f'module-{gid}'
            for gid in admin_pinned_calculator_group_ids(fr_content)
        ]
        return normalize_selected_module_ids(
            list(getattr(proposal, 'selected_modules', None) or []) + pinned,
            fr_content,
        )

    selected = []

    inv = next((s for s in sections if s.section_type == 'investment'), None)
    if inv and inv.content_json:
        for mod in inv.content_json.get('modules') or []:
            mid = mod.get('id') if isinstance(mod, dict) else None
            if mid:
                selected.append(mid)

    # Preserve the scope established in the panel before the calculator retired.
    # Hidden groups remain outside the PDF render scope.
    calc_default_ids = admin_default_calculator_group_ids(fr_content)
    if calc_default_ids and fr_content:
        hidden_ids = {
            str(g.get('id') or '')
            for arr_key in ('groups', 'additionalModules')
            for g in (fr_content.get(arr_key) or [])
            if isinstance(g, dict) and g.get('is_visible') is False
        }
        calc_default_ids = {
            gid for gid in calc_default_ids if gid not in hidden_ids
        }
    for gid in calc_default_ids:
        selected.append(f'module-{gid}')

    if fr_content:
        groups = list(fr_content.get('groups') or []) + list(fr_content.get('additionalModules') or [])
        for grp in groups:
            if not isinstance(grp, dict):
                continue
            if grp.get('is_visible') is False:
                continue
            if grp.get('is_calculator_module') is True:
                continue  # already handled via admin_default_calculator_group_ids
            default_sel = grp.get('selected')
            if default_sel is None:
                default_sel = grp.get('default_selected')
            if default_sel is None:
                default_sel = True  # non-calc groups default to included
            if not default_sel:
                continue
            gid = grp.get('id')
            if not gid:
                continue
            selected.append(f'group-{gid}')

    return selected


# ─────────────────────────────────────────────────────────────
# Section renderers
# ─────────────────────────────────────────────────────────────

def _render_greeting(c, data, proposal, ps=None):
    """Render the greeting/title page."""
    # Subtle decorative circle top-right
    c.saveState()
    c.setFillColor(ESMERALD_LIGHT)
    c.circle(PAGE_W - 40, PAGE_H - 40, 140, fill=1, stroke=0)
    c.restoreState()

    # Small accent circle bottom-left
    c.saveState()
    c.setFillColor(BONE)
    c.circle(50, 60, 70, fill=1, stroke=0)
    c.restoreState()

    mid_y = PAGE_H / 2 + 80

    # "Propuesta de Desarrollo Web," label
    c.setFont(_font('light'), 14)
    c.setFillColor(GREEN_LIGHT)
    c.drawCentredString(PAGE_W / 2, mid_y + 60,
                        'PROPUESTA DE DESARROLLO WEB')

    # Client name — large, centred, wrapped by real width. The font
    # steps down (36 -> 30 -> 26) until the name fits in three lines,
    # so very long names never overprint the divider below.
    name = _sanitize_pdf_text(
        str(_safe(data, 'clientName', proposal.client_name) or 'Cliente'))
    name_size = 36
    name_lines = [name]
    for size in (36, 30, 26):
        name_size = size
        name_lines = _wrap_by_width(name, _font('light'), size,
                                    PAGE_W - 120)
        if len(name_lines) <= 3:
            break
    if len(name_lines) > 3:
        name_lines = name_lines[:3]
        name_lines[-1] = _fit_text_ellipsis(
            name_lines[-1] + '…', _font('light'), name_size, PAGE_W - 120)
    name_leading = name_size + 8
    c.setFont(_font('light'), name_size)
    c.setFillColor(ESMERALD)
    ny = mid_y + 10
    for line in name_lines:
        _draw_mixed_centred(c, PAGE_W / 2, ny, line, _font('light'),
                            name_size)
        ny -= name_leading

    # Decorative divider line with lemon accent — flows 50pt below the
    # last name baseline instead of sitting at a fixed height.
    line_y = ny + name_leading - 50
    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(PAGE_W / 2 - 60, line_y, PAGE_W / 2 + 60, line_y)
    c.setFillColor(LEMON)
    c.circle(PAGE_W / 2 - 60, line_y, 2.5, fill=1, stroke=0)
    c.circle(PAGE_W / 2 + 60, line_y, 2.5, fill=1, stroke=0)

    # Quote — clamped to the space above the bottom branding so a long
    # quote can never collide with it.
    quote = _safe(data, 'inspirationalQuote')
    if quote:
        qy = line_y - 30
        q_leading = 16
        max_q_lines = int((qy - (MARGIN_B + 30)) // q_leading)
        if max_q_lines > 0:
            c.setFont(_font('italic'), 11)
            c.setFillColor(GREEN_LIGHT)
            q_lines = _wrap_by_width(f'"{_sanitize_pdf_text(quote)}"',
                                     _font('italic'), 11, 400)
            if len(q_lines) > max_q_lines:
                q_lines = q_lines[:max_q_lines]
                q_lines[-1] = _fit_text_ellipsis(
                    q_lines[-1] + '…', _font('italic'), 11, 400)
            for ql in q_lines:
                _draw_mixed_centred(c, PAGE_W / 2, qy, ql,
                                    _font('italic'), 11)
                qy -= q_leading

    # Bottom branding
    c.setFont(_font('regular'), 8)
    c.setFillColor(GRAY_500)
    c.drawCentredString(PAGE_W / 2, MARGIN_B + 10,
                        'Project App  |  projectapp.co')


def _render_executive_summary(c, data, _proposal, ps=None, y=None):
    """Render executive summary with paragraphs + sidebar highlights."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    paragraphs = _safe(data, 'paragraphs', [])
    highlights = _safe(data, 'highlights', [])
    hl_title = _safe(data, 'highlightsTitle', 'Aspectos Clave')
    content_top = y

    if highlights:
        sb_h = _sidebar_box_height(highlights)
        text_h = _estimate_text_height(paragraphs, TEXT_AREA_W)
        need = max(sb_h, text_h) + 20
        has_room = (content_top - MARGIN_B) > need
        if has_room:
            y = _draw_paragraphs(c, y, paragraphs, max_width=TEXT_AREA_W, ps=ps)
            sb = _draw_sidebar_box(c, content_top, hl_title, highlights)
            y = min(y, sb - 8)
        else:
            y = _draw_paragraphs(c, y, paragraphs, ps=ps)
            y -= 6
            y = _draw_subtitle(c, y, hl_title, ps=ps)
            y = _draw_bullet_list(c, y, highlights, ps=ps)
    else:
        y = _draw_paragraphs(c, y, paragraphs, ps=ps)
    return y


def _render_context_diagnostic(c, data, _proposal, ps=None, y=None):
    """Render context & diagnostic section."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    y = _draw_paragraphs(c, y, _safe(data, 'paragraphs', []), ps=ps)
    opp = _safe(data, 'opportunity')
    if opp:
        y -= 6
        opp_title = _safe(data, 'opportunityTitle')
        y = _draw_subtitle(c, y, opp_title or 'La oportunidad', ps=ps)
        y = _draw_paragraphs(c, y, [opp], ps=ps)

    issues = _safe(data, 'issues', [])
    if issues:
        y -= 8
        issues_title = _safe(data, 'issuesTitle', 'Problemas Identificados')
        y = _draw_badge_panel(c, y, issues_title, issues, ps=ps)
    return y


def _render_conversion_strategy(c, data, _proposal, ps=None, y=None):
    """Render conversion strategy section."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 4

    steps = _safe(data, 'steps', [])
    for i, step in enumerate(steps):
        y = _draw_feature_row(
            c, y, _safe(step, 'title'), ps=ps, index=i + 1,
            children=_safe(step, 'bullets', []))

    # Result — highlighted callout
    result = _safe(data, 'result')
    if result:
        y -= 6
        y = _draw_callout_box(c, y, str(result), style='tip', ps=ps,
                              label='RESULTADO')
    return y


def _render_design_ux(c, data, _proposal, ps=None, y=None):
    """Render design & UX section."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    focus_items = _safe(data, 'focusItems', [])
    focus_title = _safe(data, 'focusTitle', 'Enfoque')

    # Render paragraphs + objective first (full width or left column)
    paragraphs = _safe(data, 'paragraphs', [])
    obj_title = _safe(data, 'objectiveTitle')
    obj = _safe(data, 'objective')

    if focus_items:
        # Always render inline (full-width) to avoid whitespace gaps
        y = _draw_paragraphs(c, y, paragraphs, ps=ps)
        if obj:
            y -= 6
            y = _draw_subtitle(c, y, obj_title or 'Objetivo', ps=ps)
            y = _draw_blockquote(c, y, str(obj), ps=ps)
        y -= 10
        # Focus items grouped in a branded panel with numbered chips
        y = _draw_badge_panel(c, y, focus_title, focus_items, ps=ps)
    else:
        y = _draw_paragraphs(c, y, paragraphs, ps=ps)
        if obj:
            y -= 6
            y = _draw_subtitle(c, y, obj_title or 'Objetivo', ps=ps)
            y = _draw_blockquote(c, y, str(obj), ps=ps)
    return y


def _render_creative_support(c, data, _proposal, ps=None, y=None):
    """Render creative support section."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    includes = _safe(data, 'includes', [])
    inc_title = _safe(data, 'includesTitle', 'Incluye')
    content_top = y

    if includes:
        sb_h = _sidebar_box_height(includes)
        paragraphs = _safe(data, 'paragraphs', [])
        para_h = _estimate_text_height(paragraphs, TEXT_AREA_W)
        closing = _safe(data, 'closing')
        full_left_h = para_h
        if closing:
            full_left_h += _estimate_text_height([closing], TEXT_AREA_W)
        avail = content_top - MARGIN_B

        # Tier 1: full two-column (paragraphs + closing alongside sidebar)
        full_need = max(sb_h, full_left_h) + 20
        # Tier 2: partial two-column (paragraphs alongside sidebar,
        #         closing rendered below at full width)
        partial_need = max(sb_h, para_h) + 20

        if avail > full_need:
            y = _draw_paragraphs(c, y, paragraphs,
                                 max_width=TEXT_AREA_W, ps=ps)
            if closing:
                y -= 6
                y = _draw_paragraphs(c, y, [closing], max_width=TEXT_AREA_W,
                                     ps=ps)
            sb = _draw_sidebar_box(c, content_top, inc_title, includes)
            y = min(y, sb - 8)
        elif avail > partial_need:
            y = _draw_paragraphs(c, y, paragraphs,
                                 max_width=TEXT_AREA_W, ps=ps)
            sb = _draw_sidebar_box(c, content_top, inc_title, includes)
            y = min(y, sb - 8)
            if closing:
                y -= 6
                y = _draw_paragraphs(c, y, [closing], ps=ps)
        else:
            # Tier 3: linear fallback — everything full-width
            y = _draw_paragraphs(c, y, paragraphs, ps=ps)
            if closing:
                y -= 6
                y = _draw_paragraphs(c, y, [closing], ps=ps)
            y -= 6
            y = _draw_subtitle(c, y, inc_title, ps=ps)
            y = _draw_bullet_list(c, y, includes, ps=ps)
    else:
        y = _draw_paragraphs(c, y, _safe(data, 'paragraphs', []), ps=ps)
        closing = _safe(data, 'closing')
        if closing:
            y -= 6
            y = _draw_paragraphs(c, y, [closing], ps=ps)
    return y


def _render_development_stages(c, data, _proposal, ps=None, y=None):
    """Render development stages as a vertical timeline."""
    if y is None:
        y = PAGE_H - MARGIN_T
    index_str = _safe(data, 'index')
    title = _safe(data, 'title', 'Etapas de Desarrollo')
    y = _draw_section_header(c, y, index_str, title)
    y -= 8

    stages = _safe(data, 'stages', [])
    for i, stage in enumerate(stages):
        stage_title = _safe(stage, 'title')
        desc = _safe(stage, 'description')
        is_current = _safe(stage, 'current', False)

        # Feature row: numbered chip + title + "Etapa actual" pill +
        # description. The connector line is drawn afterwards spanning the
        # real block height, and skipped if the block crossed a page.
        page_before = ps['num'] if ps else 0
        circle_top = y + 3.5
        y = _draw_feature_row(
            c, y, stage_title, description=desc, ps=ps, index=i + 1,
            pill_text=('Etapa actual' if is_current else None),
            pill_bg=LEMON, pill_fg=ESMERALD)

        # Vertical connector to the next stage — only within the same page.
        if i < len(stages) - 1 and (not ps or ps['num'] == page_before):
            c.setStrokeColor(GRAY_200)
            c.setLineWidth(1)
            c.line(MARGIN_L + 8, circle_top - 13, MARGIN_L + 8, y + 6)
    return y


def _render_functional_requirements(c, data, proposal, ps=None, y=None):
    """Render functional requirements overview page."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 6

    groups = _safe(data, 'groups', [])
    additional = _safe(data, 'additionalModules', [])
    all_groups = [g for g in list(groups) + list(additional) if _safe(g, 'is_visible', True) is not False]

    # Hide groups rendered in the dedicated value-added section.
    hidden_ids = ps.get('_value_added_ids', set()) if ps else set()
    if hidden_ids:
        all_groups = [g for g in all_groups if _safe(g, 'id') not in hidden_ids]

    # Filter out calculator-module groups not selected
    sel_ids = ps.get('selected_modules') if ps else None
    all_groups = _filter_calculator_groups(all_groups, sel_ids)

    # Overview index table (# | Módulo | Descripción | Ítems). Full-width,
    # zebra rows, header repeats across pages — no truncation, unlike the
    # old 2-column card grid that clipped titles and descriptions to two
    # lines each. The detail sub-sections that follow use this as an index.
    def _count_items(grp):
        grp_items = _safe(grp, 'items', [])
        if sel_ids is not None and grp_items:
            grp_key = (_safe(grp, 'id') or _safe(grp, 'title') or '')
            kept = []
            for it in grp_items:
                is_req = _safe(it, 'is_required')
                if is_req is True:
                    kept.append(it)
                else:
                    configurable = _safe(it, 'price') or is_req is False
                    if not configurable:
                        kept.append(it)
                    else:
                        fr_id = re.sub(
                            r'\s+', '-',
                            f'fr-{grp_key}-{_safe(it, "name") or ""}').lower()
                        if fr_id in sel_ids:
                            kept.append(it)
            grp_items = kept
        return len(grp_items)

    overview_rows = []
    for gi, grp in enumerate(all_groups):
        overview_rows.append([
            str(gi + 1),
            f"**{_safe(grp, 'title')}**",
            _safe(grp, 'description'),
            str(_count_items(grp)),
        ])
    if overview_rows:
        row_y = _draw_table(
            c, y, ['#', 'Módulo', 'Descripción', 'Ítems'], overview_rows,
            ps=ps, col_widths=[0.07, 0.28, 0.53, 0.12],
            aligns=['center', 'left', 'left', 'center'])
    else:
        row_y = y

    # Store groups for generate() to render detail sub-sections
    if ps is not None:
        ps['_func_req_groups'] = all_groups

    return row_y - 8


def _render_linked_requirements(c, item, ps, row_y, redraw=None):
    """Render complete linked requirements inside compact, measured sub-rows."""
    linked = ((ps or {}).get('_item_requirements_map') or {}).get(_safe(item, 'id')) or []
    for req in linked:
        if req.get('title') or req.get('description'):
            row_y = _draw_linked_row(c, row_y, req, ps, redraw)
    return row_y


def _render_requirement_group_page(c, grp, ps=None, y=None,
                                    sub_index=''):
    """Render a single requirement group detail with cards layout."""
    if y is None:
        y = PAGE_H - MARGIN_T

    # Sub-index numeral (e.g. "07.1")
    if ps:
        count = len(_safe(grp, 'items', []))
        label = f'{count} elemento{"s" if count != 1 else ""}' if count else ''
        need = _heading_badge_height(c, _safe(grp, 'title'), label,
                                     font_size=20, font_name=_font('light'))
        y = _check_y(c, y, ps, need=need + (22 if sub_index else 0))
    if sub_index:
        c.setFont(_font('light'), 11)
        c.setFillColor(GREEN_LIGHT)
        c.drawString(MARGIN_L, y, str(sub_index))
        y -= 22

    items = _safe(grp, 'items', [])
    title_text = _strip_emoji(_safe(grp, 'title'))
    pill_label = f'{len(items)} elemento{"s" if len(items) != 1 else ""}' if items else ''
    y = _draw_heading_badge(c, y, title_text, pill_label, ps=ps,
                            font_size=20, font_name=_font('light'))

    # Thin accent line
    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(MARGIN_L, y + 6, MARGIN_L + 40, y + 6)
    y -= 12

    desc = _safe(grp, 'description')
    if desc:
        y = _draw_paragraphs(c, y, [desc], ps=ps)
        y -= 6

    # Render items as a full-width table — one row per requirement
    if not items:
        return y

    rows = [dict(item, title=_safe(item, 'name')) for item in items]
    return _draw_requirements_table(c, y, rows, ps, _render_linked_requirements)


def _render_timeline(c, data, _proposal, ps=None, y=None):
    """Render timeline section with phases."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    intro = _safe(data, 'introText')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)

    phases = _safe(data, 'phases', [])

    # Headline KPI tiles: total duration + phase / milestone counts.
    total = _safe(data, 'totalDuration')
    tiles = []
    if total:
        tiles.append({'value': _sanitize_pdf_text(str(total)),
                      'label': 'Duración total'})
    if len(phases) >= 2:
        tiles.append({'value': str(len(phases)), 'label': 'Fases'})
        milestones = sum(1 for ph in phases if _safe(ph, 'milestone'))
        if milestones:
            tiles.append({'value': str(milestones), 'label': 'Hitos'})
    if tiles:
        y = _draw_kpi_tile_row(c, y, tiles, ps=ps, accent_first=True)
        y -= 8

    for i, phase in enumerate(phases):
        if ps:
            y = _check_y(c, y, ps, need=50)
        elif y < MARGIN_B + 50:
            break

        cx = MARGIN_L + 12
        cy = y - 2
        c.setFillColor(ESMERALD)
        c.circle(cx, cy, 9, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(_font('bold'), 8)
        c.drawCentredString(cx, cy - 3, str(i + 1))

        tx = MARGIN_L + 30

        duration = _safe(phase, 'duration')
        y = _draw_heading_badge(c, y, _safe(phase, 'title'), duration,
                                ps=ps, font_size=11, x=tx,
                                max_width=PAGE_W - MARGIN_R - tx)
        weeks = _safe(phase, 'weeks')
        if weeks:
            y = _draw_paragraphs(c, y, [weeks], x=tx, font_size=8,
                                 max_width=CONTENT_W - 30, ps=ps)

        desc = _safe(phase, 'description')
        if desc:
            y = _draw_paragraphs(c, y, [desc], x=tx,
                                 max_width=PAGE_W - MARGIN_R - tx,
                                 font_size=9, leading=12, ps=ps)

        tasks = _safe(phase, 'tasks', [])
        if tasks:
            y = _draw_bullet_list(
                c, y, tasks, x=tx, font_size=8, leading=11,
                max_width=CONTENT_W - 40, ps=ps,
            )

        milestone = _safe(phase, 'milestone')
        if milestone:
            label = 'Hito'
            y = _draw_badge_group(c, y, [{'text': f'{label}: {milestone}', 'bg': BONE}],
                                  ps=ps, x=tx, max_width=CONTENT_W - 30)

        y -= 6
    return y


def _format_currency(n, currency):
    """Format a money amount for the PDF, mirroring the frontend rules.

    Mirrors frontend/utils/hourPackagePricing.js formatPackageMoney: COP has
    no cents (es-CO dots); USD keeps cents when fractional (en-US commas) so
    discounted rates and their totals stay arithmetically consistent.
    """
    try:
        num = round(float(n), 2)
    except (TypeError, ValueError):
        return str(n)
    if currency == 'USD':
        formatted = f'{int(num):,}' if num == int(num) else f'{num:,.2f}'
    else:
        formatted = f'{int(round(num)):,}'.replace(',', '.')
    return f'${formatted} {currency}'


def _tax_suffix(currency):
    """Tax label appended after amounts, by market/currency.

    COP (Colombian market) -> ' + IVA'; USD (American market) -> ' + Tax'.
    Defaults to IVA when currency is missing/unknown.
    """
    return ' + Tax' if str(currency or '').upper() == 'USD' else ' + IVA'


def _payment_pill_desc(label, desc, display_num, tax_suffix=''):
    """Build the amount pill for a single payment option.

    Mirrors Investment.vue ``computedPaymentOptions``: derive the amount from
    the percentage embedded in the label times the live display total, instead
    of scaling whatever amount the backend last persisted in ``description``
    (which already equals ``effective × pct`` and would double-scale).

    ``tax_suffix`` (e.g. ' + IVA' / ' + Tax') is appended only when an amount
    pill is produced; options without a percentage/amount return their raw
    description unchanged.
    """
    if not display_num or display_num <= 0:
        return desc
    pct_match = re.search(r'(\d+)\s*%', str(label or ''))
    if not pct_match:
        return desc
    pct = int(pct_match.group(1))
    new_amount = round(display_num * pct / 100)
    formatted = _format_cop(new_amount).lstrip('$')
    desc_str = _strip_emoji(desc or '')
    if desc_str and re.search(r'[\$]?[\d.,]+', desc_str):
        pill = re.sub(r'[\$]?[\d.,]+', formatted, desc_str, count=1)
    else:
        pill = formatted
    pill = pill if pill.startswith('$') else '$' + pill
    if tax_suffix:
        # Stored proposal copy may already declare the tax. Normalize that
        # trailing label before appending the renderer-owned suffix so PDF
        # amounts never read "+ IVA + IVA" or "+ Tax + Tax".
        pill = re.sub(
            r'\s*(?:\+\s*|m[aá]s\s+)(?:IVA|Tax)\s*\.?\s*$',
            '',
            pill,
            flags=re.IGNORECASE,
        ).rstrip()
    return f'{pill}{tax_suffix}'


def _render_investment(c, data, _proposal, ps=None, y=None):
    """Render investment section with two-column layout.

    Left column:  Formas de Pago (payment options).
    Right column: Incluye (what's included).
    Below both:   Compact Inversión Total line.
    """
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    intro = _safe(data, 'introText')
    included = _safe(data, 'whatsIncluded', [])
    # BusinessProposal fields are the source of truth; content_json is the
    # stale mirror (matches frontend override in pages/proposal/[uuid]/index.vue).
    _model_total = getattr(_proposal, 'total_investment', None)
    total = (_format_cop(int(_model_total))
             if _model_total else _safe(data, 'totalInvestment'))
    currency = (getattr(_proposal, 'currency', None)
                or _safe(data, 'currency'))
    tax_suffix = _tax_suffix(currency)
    options = _safe(data, 'paymentOptions', [])

    # Scope selection never changes the manually agreed investment.
    display_num = float(_proposal.total_investment) if _proposal is not None else int(re.sub(r'[^\d]', '', str(total)) or '0')
    display_total = _format_cop(display_num) if display_num else (total or '')

    # ── Hosting figures (hoisted: reused by the KPI tiles and the
    # hosting block below) ──
    hosting = _safe(data, 'hostingPlan', {})
    hosting_terms = resolve_hosting_terms(_proposal, hosting, display_num)
    normalized_hosting = hosting_terms['plan']
    hosting_twelve_month_reference = hosting_terms['annual_reference']
    include_hosting = (ps or {}).get('include_hosting', True)

    duration_value = ''
    duration_sub = ''
    if ps and ps.get('base_weeks'):
        duration_value = f"{ps['base_weeks']} semanas"

    # Intro text — full width, brief
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 10

    # ── Headline KPI tiles: the figures that matter, at a glance ──
    tiles = []
    if display_total:
        total_label = 'Inversión Total'
        if currency:
            total_label = f'{total_label} · {currency}'
        tiles.append({'value': display_total, 'label': total_label,
                      'sub': tax_suffix.strip()})
    if duration_value:
        tiles.append({'value': duration_value,
                      'label': 'Duración estimada', 'sub': duration_sub})
    if include_hosting and hosting_twelve_month_reference > 0:
        first_tier = (hosting_terms['tiers'] or [{}])[0]
        if _safe(first_tier, 'frequency') == 'nine_month':
            nine_month_total = first_tier['period_total']
            hosting_kpi = f'{_format_cop(nine_month_total)}/9 meses'
        else:
            # Closed historical proposals preserve their original annual KPI.
            hosting_kpi = f'{_format_cop(hosting_twelve_month_reference)}/año'
        tiles.append({'value': hosting_kpi, 'label': 'Hosting y mantenimiento',
                      'sub': tax_suffix.strip()})
    if tiles:
        y = _draw_kpi_tile_row(c, y, tiles, ps=ps, accent_first=True)
        y -= 6

    # ── Layout: Formas de Pago + Incluye ──
    col_gap = 20
    left_w = CONTENT_W * 0.58
    right_w = CONTENT_W - left_w - col_gap
    right_x = MARGIN_L + left_w + col_gap

    # Pre-calculate heights to decide two-column vs linear layout
    payment_rows = [(_strip_emoji(_safe(opt, 'label')),
                     _payment_pill_desc(_strip_emoji(_safe(opt, 'label')),
                                        _strip_emoji(_safe(opt, 'description')),
                                        display_num, tax_suffix=tax_suffix))
                    for opt in options]
    left_need = 20 + sum(_payment_option_height(c, label, badge, left_w)
                         for label, badge in payment_rows) if options else 0
    items_text = []
    if included:
        items_text = [
            f'{_strip_emoji(_safe(it, "title"))} \u2014 '
            f'{_strip_emoji(_safe(it, "description"))}'
            for it in included
        ]
    right_need = _sidebar_box_height(items_text, sidebar_w=right_w) if items_text else 0
    total_need = max(left_need, right_need)
    use_two_col = (y - MARGIN_B) > total_need + 30

    if use_two_col:
        # ── Two-column layout ──
        columns_top = y

        # LEFT COLUMN: Formas de Pago
        left_y = columns_top
        if options:
            c.setFont(_font('bold'), 12)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, left_y, 'Formas de Pago')
            left_y -= 20

            for label, badge in payment_rows:
                left_y = _draw_payment_option(c, left_y, label, badge, left_w)

        # RIGHT COLUMN: Incluye
        right_bottom = columns_top
        if items_text:
            right_bottom = _draw_sidebar_box(c, columns_top, 'Incluye', items_text,
                                              sidebar_x=right_x, sidebar_w=right_w)

        y = min(left_y, right_bottom) - 12
    else:
        # ── Linear layout (paginated) ──
        if options:
            if ps:
                y = _check_y(c, y, ps, need=40)
            c.setFont(_font('bold'), 12)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, y, 'Formas de Pago')
            y -= 20

            for label, badge in payment_rows:
                y = _draw_payment_option(c, y, label, badge, CONTENT_W, ps)

        if included:
            y -= 10
            y = _draw_subtitle(c, y, 'Incluye', ps=ps)
            for it in included:
                y = _draw_feature_row(
                    c, y, _safe(it, 'title'),
                    description=_safe(it, 'description'), ps=ps)
            y -= 4


    # ── Interactive Modules (if present) ──────────────────────────
    modules = _safe(data, 'modules', [])
    selected_ids = ps.get('selected_modules') if ps else None
    # Only show selected modules (or all if no filter)
    visible_modules = [
        mod for mod in modules
        if selected_ids is None or _safe(mod, 'id') in (selected_ids or [])
    ]
    if visible_modules:
        y -= 14
        if ps:
            y = _check_y(c, y, ps, need=60)
        y = _draw_subtitle(c, y, 'Módulos del Proyecto', ps=ps)
        mod_rows = [[_safe(mod, 'name')] for mod in visible_modules]
        y = _draw_table(c, y, ['Módulo'], mod_rows, ps=ps)

    # ── Hosting plan (detailed specs + pricing) ───────────────────
    # Read the NORMALIZED plan hoisted above, not the raw content_json: that is
    # where the free-month copy and its visibility flag get resolved, and where
    # the web view reads them from too.
    hosting = normalized_hosting
    h_title = _safe(hosting, 'title')
    if include_hosting and h_title:
        y -= 14
        if ps:
            y = _check_y(c, y, ps, need=120)
        # Title
        c.setFont(_font('bold'), 12)
        c.setFillColor(ESMERALD)
        c.drawString(MARGIN_L, y, _strip_emoji(str(h_title)))
        y -= 16
        # Description
        h_desc = _safe(hosting, 'description')
        if h_desc:
            y = _draw_paragraphs(c, y, [h_desc], font_size=9,
                                 leading=13, ps=ps)
            y -= 6

        # Specs — full-width table (label | detail): long values wrap
        # inside their column instead of overflowing a fixed-height badge.
        specs = [s for s in _safe(hosting, 'specs', [])
                 if _safe(s, 'label') or _safe(s, 'value')]
        if specs:
            spec_rows = [[_safe(s, 'label'), _safe(s, 'value')]
                         for s in specs]
            y -= 2
            y = _draw_table(c, y, ['Especificación', 'Detalle'], spec_rows,
                            ps=ps, col_widths=[0.30, 0.70])

        # Billing tiers — one full-width table instead of N fixed-height
        # side-by-side cards (labels/prices can never collide again).
        # normalized_hosting / hosting_twelve_month_reference are hoisted at
        # the top of the renderer (shared with the KPI tiles). Hosting is
        # a percentage of the SAME "Inversión Total" the client sees —
        # parity with Investment.vue ``hostingTwelveMonthReference``.
        billing_tiers = hosting_terms['tiers']

        tier_headers = ['Frecuencia', 'Ahorro',
                        f'Precio/mes ({tax_suffix.strip()})',
                        f'Equivalente ({tax_suffix.strip()})']
        tier_col_widths = [0.28, 0.14, 0.27, 0.31]
        tier_aligns = ['left', 'center', 'right', 'right']
        if billing_tiers and hosting_twelve_month_reference > 0:
            tier_rows = []
            for tier in billing_tiers:
                discount = _safe(tier, 'discountPercent', 0)
                months = _safe(tier, 'months', 1) or 1
                label = _safe(tier, 'label', '')
                badge = _safe(tier, 'badge', '')
                monthly_discounted = tier['monthly_price']
                period_total = tier['period_total']
                freq_cell = f'**{label}**' if label else ''
                if badge:
                    freq_cell = f'{freq_cell} — {badge}' if freq_cell else badge
                tier_rows.append([
                    freq_cell,
                    f'-{int(discount)}%' if discount else '—',
                    f'{_format_cop(monthly_discounted)} /mes',
                    f'{_format_cop(period_total)} cada {months} '
                    f'mes{"es" if months > 1 else ""}',
                ])
            y -= 4
            y = _draw_table(c, y, tier_headers, tier_rows, ps=ps,
                            col_widths=tier_col_widths, aligns=tier_aligns)
        else:
            # Historical fallback for closed proposals that predate billingTiers.
            m_price = _safe(hosting, 'monthlyPrice')
            a_price = _safe(hosting, 'annualPrice')
            legacy_rows = []
            if m_price:
                legacy_rows.append([
                    f"**{_safe(hosting, 'monthlyLabel', 'por mes')}**",
                    '—', str(m_price), '—',
                ])
            if a_price:
                legacy_rows.append([
                    f"**{_safe(hosting, 'annualLabel', 'pago anual')}**",
                    '—', '—', str(a_price),
                ])
            if legacy_rows:
                y -= 4
                y = _draw_table(c, y, tier_headers, legacy_rows, ps=ps,
                                col_widths=tier_col_widths,
                                aligns=tier_aligns)

        # Coverage note — callout describing the 3 hosting components
        coverage = _safe(hosting, 'coverageNote')
        if coverage:
            y -= 8
            y = _draw_callout_box(c, y, str(coverage), style='note',
                                  ps=ps, label='COBERTURA')

        # Free-month gift block. Visibility is the explicit flag resolved by
        # normalize_hosting_plan — the same gate the web view uses — and the
        # copy is already filled in with the per-language default when the
        # operator left the field empty.
        free_note = _safe(hosting, 'freeMonthNote')
        if hosting.get('freeMonthsVisible') and free_note:
            y -= 8
            y = _draw_callout_box(c, y, str(free_note), style='tip',
                                  ps=ps, label='REGALO')

        # Renewal note — SMLMV formula text
        renewal = hosting_terms['renewal_note']
        if renewal:
            y -= 8
            # Split on double-newlines to preserve paragraph breaks. The
            # intro goes in a labelled callout, the formula line stands
            # out as a blockquote, remaining paragraphs as fine print.
            renewal_paras = [
                p.strip() for p in str(renewal).split('\n\n') if p.strip()
            ]
            if renewal_paras:
                y = _draw_callout_box(c, y, renewal_paras[0], style='note',
                                      ps=ps, label='RENOVACIONES')
                for para in renewal_paras[1:]:
                    if para.lower().startswith('costo de renovación'):
                        y = _draw_blockquote(c, y, para, ps=ps)
                    else:
                        y = _draw_paragraphs(c, y, [para], font_size=8,
                                             leading=11, ps=ps)

    # Value reasons \u2014 grouped in a branded panel with numbered chips
    reasons = _safe(data, 'valueReasons', [])
    if reasons:
        y -= 8
        reasons_title = ('Why this investment?'
                         if (ps or {}).get('_pdf_lang') == 'en'
                         else '\u00bfPor qu\u00e9 esta inversi\u00f3n?')
        normalized = [
            r if isinstance(r, str)
            else _safe(r, 'description', _safe(r, 'title'))
            for r in reasons
        ]
        y = _draw_badge_panel(c, y, reasons_title, normalized, ps=ps)
    return y


def _clause_bullets(clauses, fallback_terms=None):
    """Turn a `terms_clauses` list into bullet strings for the PDF annex.

    Each clause becomes `**Label.** text`, matching what the web modal shows so
    both surfaces read identically. Proposals created before the clause format
    only carry the flat `terms` string: those fall back to one bullet per line,
    which is exactly how flatten_terms_clauses() writes them.
    """
    items = []
    for clause in (clauses or []):
        if not isinstance(clause, dict):
            continue
        text = str(clause.get('text') or '').strip()
        if not text:
            continue
        label = str(clause.get('label') or '').strip()
        items.append(f'**{label}.** {text}' if label else text)
    if items:
        return items
    fallback = str(fallback_terms or '').strip()
    if not fallback:
        return []
    return [line.strip() for line in fallback.split('\n') if line.strip()]


def _render_value_added_modules(c, data, _proposal, ps=None, y=None):
    """Render the "Incluido sin costo adicional" section as cards.

    Mirrors frontend/components/BusinessProposal/ValueAddedModules.vue:
    resolves each module_id against the functional_requirements catalog
    (ps['_value_added_catalog']) and renders one tinted card per module
    with title, separate "Sin costo adicional" pill, justification
    (primary) and optional description (secondary). Each card's full
    height is pre-computed so it never splits across a page break.
    """
    if y is None:
        y = PAGE_H - MARGIN_T

    catalog = ps.get('_value_added_catalog', {}) if ps else {}
    module_ids = _safe(data, 'module_ids', []) or []
    # No resolvable module means no section at all — not a header with nothing
    # under it. Mirrors ValueAddedModules.vue, whose root element is guarded by
    # `v-if="resolvedCards.length > 0"`.
    if not any(mid in catalog for mid in module_ids):
        return y

    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 12

    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 8

    justifications = _safe(data, 'justifications', {}) or {}
    conditions = _safe(data, 'conditions', {}) or {}
    lang = ps.get('_pdf_lang', 'es') if ps else 'es'
    currency = (ps.get('_currency') if ps else '') or 'COP'
    effective_total = ps.get('_effective_total') if ps else None

    def _cc_money(n):
        return _format_currency(n, currency)

    def _module_condition_lines(mid):
        """Build the condition lines shown under a value-added card.

        Mirrors the web gating: a "disponible desde $X" note only when the
        effective total does NOT reach the module minimum (condicionado),
        plus the duration and discretionary notes.
        """
        cond = conditions.get(mid) if isinstance(conditions, dict) else None
        if not isinstance(cond, dict):
            return []
        lines = []
        minimum = (cond.get('min_price_cop') if currency == 'COP'
                   else cond.get('min_price_usd'))
        if minimum:
            try:
                unmet = (effective_total is not None
                         and float(effective_total) < float(minimum))
            except (TypeError, ValueError):
                unmet = False
            if unmet:
                lines.append((
                    (f'Disponible en proyectos desde {_cc_money(minimum)}'
                     if lang != 'en'
                     else f'Available for projects from {_cc_money(minimum)}'),
                    False,
                ))
        months = cond.get('duration_months')
        if months:
            lines.append((
                (f'Disponible por {int(months)} meses' if lang != 'en'
                 else f'Available for {int(months)} months'),
                False,
            ))
        note = cond.get('discretionary_note')
        if note:
            lines.append((str(note), True))
        return lines

    card_pad_x = 14
    card_pad_y = 12
    icon_size = 22
    icon_gap = 10
    title_font_size = 11
    just_font_size = 9
    just_leading = 13
    desc_font_size = 8
    desc_leading = 11
    pill_text = 'Sin costo adicional'
    content_area_w = CONTENT_W - card_pad_x * 2 - icon_size - icon_gap
    title_max_w = content_area_w

    for mid in module_ids:
        module = catalog.get(mid)
        if not module:
            continue
        title = _strip_emoji(_safe(module, 'title')) or 'Módulo'
        description = _strip_emoji(_safe(module, 'description'))
        justification = (justifications.get(mid)
                         if isinstance(justifications, dict) else None)

        # Wrap by real width; the card height grows to fit — no silent
        # 2-line truncation of the title anymore.
        title_lines = _wrap_by_width(title, _font('bold'), title_font_size,
                                     max(title_max_w, 40)) or [title]
        just_h = (_estimate_text_height(
                      [justification], max_width=content_area_w,
                      font_size=just_font_size, leading=just_leading)
                  if justification else 0)
        desc_h = (_estimate_text_height(
                      [description], max_width=content_area_w,
                      font_size=desc_font_size, leading=desc_leading,
                      font_name=_font('italic'))
                  if description else 0)
        cond_lines = _module_condition_lines(mid)
        cond_h = sum(
            _estimate_text_height(
                [ct], max_width=content_area_w,
                font_size=desc_font_size, leading=desc_leading,
                font_name=_font('italic') if is_italic else _font('medium'))
            for ct, is_italic in cond_lines
        )
        card_h = (
            card_pad_y
            + len(title_lines) * 14
            + BADGE_GAP * 2 + 13
            + (6 + just_h if justification else 0)
            + (4 + desc_h if description else 0)
            + (4 + cond_h if cond_lines else 0)
            + card_pad_y
        )

        if ps and card_h > PAGE_H - MARGIN_T - MARGIN_B:
            # Oversized cards flow as normal blocks instead of clipping text.
            y = _draw_feature_row(c, y, title, pill_text=pill_text,
                                  pill_bg=LEMON, ps=ps)
            for text, font_style in [(justification, 'regular'), (description, 'italic')]:
                if text:
                    y = _draw_paragraphs(c, y, [text], ps=ps,
                                         font_name=_font(font_style))
            for text, is_italic in cond_lines:
                y = _draw_paragraphs(c, y, [text], ps=ps,
                                     font_name=_font('italic' if is_italic else 'medium'))
            continue
        if ps:
            y = _check_y(c, y, ps, need=card_h + 14)

        card_top = y
        card_bottom = y - card_h
        c.setFillColor(ESMERALD_LIGHT)
        c.roundRect(MARGIN_L, card_bottom, CONTENT_W, card_h, 8,
                    fill=1, stroke=0)

        # Decorative icon square — emoji glyphs don't render in Ubuntu,
        # so we fall back to the title's first letter.
        icon_x = MARGIN_L + card_pad_x
        icon_y = card_top - card_pad_y - icon_size
        c.setFillColor(BONE)
        c.roundRect(icon_x, icon_y, icon_size, icon_size, 5,
                    fill=1, stroke=0)
        c.setFillColor(ESMERALD)
        c.setFont(_font('bold'), 11)
        c.drawCentredString(icon_x + icon_size / 2,
                            icon_y + icon_size / 2 - 3.5,
                            title[:1].upper() if title else '•')

        text_x = icon_x + icon_size + icon_gap
        title_y = card_top - card_pad_y - 10
        c.setFont(_font('bold'), title_font_size)
        c.setFillColor(ESMERALD)
        for line in title_lines:
            c.drawString(text_x, title_y, line)
            title_y -= 14

        _paint_badge(c, text_x, title_y - BADGE_GAP,
                     {'text': pill_text, 'bg': LEMON, 'fg': ESMERALD}, content_area_w)
        next_y = title_y - BADGE_GAP * 2 - 13 - 2

        if justification:
            next_y -= 4
            next_y = _draw_paragraphs(
                c, next_y, [str(justification)],
                max_width=content_area_w,
                font_size=just_font_size, leading=just_leading,
                color=ESMERALD, x=text_x,
            )

        if description:
            next_y -= 2
            next_y = _draw_paragraphs(
                c, next_y, [str(description)],
                max_width=content_area_w,
                font_size=desc_font_size, leading=desc_leading,
                color=ESMERALD_80, x=text_x,
                font_name=_font('italic'),
            )

        if cond_lines:
            next_y -= 2
            for ct, is_italic in cond_lines:
                next_y = _draw_paragraphs(
                    c, next_y, [ct],
                    max_width=content_area_w,
                    font_size=desc_font_size, leading=desc_leading,
                    color=ESMERALD_80, x=text_x,
                    font_name=_font('italic') if is_italic
                    else _font('medium'),
                )

        y = card_bottom - 12

    # Terms & conditions annex for the included modules (Req 3).
    # The web shows the same clauses per module in a modal; the PDF has no
    # modal, so they are printed here as a closing annex. Both surfaces read the
    # very same source (conditions[mid].terms_clauses + general_terms), so the
    # wording, the clause order and the **bold** emphasis stay identical.
    tc_blocks = []
    for mid in module_ids:
        cond = conditions.get(mid) if isinstance(conditions, dict) else None
        if not isinstance(cond, dict):
            continue
        items = _clause_bullets(cond.get('terms_clauses'), cond.get('terms'))
        if not items:
            continue
        module = catalog.get(mid) or {}
        mtitle = _strip_emoji(_safe(module, 'title')) or str(mid)
        tc_blocks.append((mtitle, items))

    general = _safe(data, 'general_terms', {}) or {}
    general_items = _clause_bullets(
        general.get('clauses') if isinstance(general, dict) else None)

    if tc_blocks or general_items:
        y -= 6
        tc_title = ('Términos y condiciones de los módulos incluidos'
                    if lang != 'en'
                    else 'Terms & conditions of the included modules')
        if ps:
            y = _check_y(c, y, ps, need=40)
        y = _draw_subtitle(c, y, tc_title, ps=ps)
        for mtitle, items in tc_blocks:
            if ps:
                y = _check_y(c, y, ps, need=34)
            y = _draw_paragraphs(c, y, [f'**{mtitle}**'], ps=ps,
                                 font_size=9, leading=12, color=ESMERALD)
            y = _draw_bullet_list(c, y, items, ps=ps, font_size=8, leading=11)
            y -= 2
        if general_items:
            gtitle = (str(general.get('title') or '').strip()
                      if isinstance(general, dict) else '')
            if not gtitle:
                gtitle = ('Disposiciones generales aplicables a los módulos incluidos'
                          if lang != 'en'
                          else 'General provisions applicable to the included modules')
            if ps:
                y = _check_y(c, y, ps, need=40)
            y = _draw_subtitle(c, y, gtitle, ps=ps)
            y = _draw_bullet_list(c, y, general_items, ps=ps,
                                  font_size=8, leading=11)
        y -= 4

    footer_note = _safe(data, 'footer_note')
    if footer_note:
        footer_h = _estimate_text_height(
            [str(footer_note)], max_width=CONTENT_W - 24,
            font_size=9, leading=12,
        )
        if ps:
            y = _check_y(c, y, ps, need=footer_h + 32)
        y -= 4
        y = _draw_banner_box(
            c, MARGIN_L, y, CONTENT_W, str(footer_note),
            bg_color=BONE, text_color=ESMERALD,
            font_size=9, icon_text='✓', ps=ps,
        )

    return y


def _render_final_note(c, data, proposal, ps=None, y=None):
    """Render final note section."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    badges = _safe(data, 'commitmentBadges', [])

    message = _safe(data, 'message')
    if message:
        y = _draw_paragraphs(c, y, [message], ps=ps)

    personal = _safe(data, 'personalNote')
    if personal:
        y -= 6
        c.setFillColor(GREEN_LIGHT)
        for pl in _wrap_by_width(_sanitize_pdf_text(str(personal)),
                                 _font('italic'), 10, CONTENT_W):
            if ps:
                y = _check_y(c, y, ps)
            c.setFont(_font('italic'), 10)
            c.setFillColor(GREEN_LIGHT)
            _draw_mixed_string(c, MARGIN_L, y, pl, _font('italic'), 10)
            y -= 14

    # Validity — computed once in ProposalService.compute_validity_text and
    # shared with the proposal serializer, so PDF and web can never drift.
    # Proposals without an expiry date show no validity badge at all.
    from content.services.proposal_service import ProposalService
    validity = ProposalService.compute_validity_text(proposal)
    if validity:
        y -= 12
        lang = (ps or {}).get('_pdf_lang', 'es')
        y = _draw_callout_box(c, y, validity, style='important', ps=ps,
                              label='VALIDITY' if lang == 'en' else 'VIGENCIA')

    # Client name
    client_name = getattr(proposal, 'client_name', '')
    if client_name:
        y -= 6
        if ps:
            y = _check_y(c, y, ps, need=20)
        c.setFont(_font('regular'), 8)
        c.setFillColor(GRAY_500)
        c.drawString(MARGIN_L, y,
                     f'Propuesta elaborada para: {client_name}')
        y -= 14

    # Signature
    if ps:
        y = _check_y(c, y, ps, need=60)
    y -= 16
    c.setStrokeColor(GRAY_300)
    c.setLineWidth(0.4)
    c.line(MARGIN_L, y, MARGIN_L + 180, y)
    y -= 16
    team = _safe(data, 'teamName')
    role = _safe(data, 'teamRole')
    email = _safe(data, 'contactEmail')
    if team:
        c.setFillColor(ESMERALD)
        _draw_mixed_string(
            c, MARGIN_L, y,
            _fit_text_ellipsis(_sanitize_pdf_text(team), _font('bold'), 12,
                               CONTENT_W), _font('bold'), 12)
        y -= 15
    if role:
        c.setFont(_font('regular'), 9)
        c.setFillColor(GRAY_500)
        c.drawString(MARGIN_L, y,
                     _fit_text_ellipsis(_strip_emoji(role), _font('regular'),
                                        9, CONTENT_W))
        y -= 13
    if email:
        c.setFont(_font('regular'), 9)
        c.setFillColor(GRAY_500)
        c.drawString(MARGIN_L, y,
                     _fit_text_ellipsis(_strip_emoji(email), _font('regular'),
                                        9, CONTENT_W))
        y -= 13

    # The whole badge group shares its exterior spacing.
    if badges:
        y = _draw_heading_badge(c, y, 'Compromisos', '', ps=ps, font_size=10)
        y = _draw_badge_group(c, y, [
            {'text': _strip_emoji(_safe(b, 'title'))} for b in badges
        ], ps=ps)

    return y


def _render_next_steps(c, data, _proposal, ps=None, y=None):
    """Render next steps section."""
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    contacts = _safe(data, 'contactMethods', [])

    intro = _safe(data, 'introMessage')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 6

    steps = _safe(data, 'steps', [])
    for i, step in enumerate(steps):
        y = _draw_feature_row(
            c, y, _safe(step, 'title'),
            description=_safe(step, 'description'), ps=ps, index=i + 1)

    # CTA message
    cta = _safe(data, 'ctaMessage')
    if cta:
        y -= 8
        if ps:
            y = _check_y(c, y, ps, need=24)
        c.setFillColor(ESMERALD)
        for cl in _wrap_by_width(_sanitize_pdf_text(str(cta)),
                                 _font('bold'), 12, CONTENT_W):
            if ps:
                y = _check_y(c, y, ps, need=16)
            _draw_mixed_string(c, MARGIN_L, y, cl, _font('bold'), 12)
            y -= 16

    # CTA buttons — clickable link pills (primary + secondary), side by side
    ctas = []
    for key, primary in (('primaryCTA', True), ('secondaryCTA', False)):
        obj = _safe(data, key, {})
        if isinstance(obj, dict) and _safe(obj, 'text'):
            ctas.append((obj, primary))
    if ctas:
        y = _draw_badge_group(c, y, [
            {'text': _safe(obj, 'text'), 'link': _safe(obj, 'link'),
             'bg': ESMERALD if primary else ESMERALD_LIGHT,
             'fg': WHITE if primary else ESMERALD, 'font_size': 9,
             'padding_h': 12, 'padding_v': 5}
            for obj, primary in ctas
        ], ps=ps)

    # Contact methods as pills (value is a clickable link when present)
    if contacts:
        y -= 10
        if ps:
            y = _check_y(c, y, ps, need=40)
        y = _draw_subtitle(c, y, 'Contacto', ps=ps)
        for ct in contacts:
            ct_title = _sanitize_pdf_text(_safe(ct, 'title'))
            ct_value = _sanitize_pdf_text(_safe(ct, 'value'))
            ct_link = _safe(ct, 'link')
            if not ct_title:
                continue
            y = _draw_badge_group(c, y, [{'text': ct_title, 'bg': ESMERALD,
                                          'fg': WHITE}], ps=ps)
            y = _draw_contact_value(c, y, ct_value, ct_link, ps)
    return y


def _render_raw_text(c, data, _proposal, ps=None, y=None):
    """Render a paste-mode section with parsed markdown content."""
    if y is None:
        y = PAGE_H - MARGIN_T
    index_str = _safe(data, 'index')
    title = _safe(data, 'title', 'Sección')
    y = _draw_section_header(c, y, index_str, title)
    y -= 8

    raw = _safe(data, 'rawText')
    if not raw:
        return y

    tokens = _parse_markdown_lines(raw)
    for kind, text in tokens:
        text = _strip_emoji(_clean_inline_bold(text))

        if kind == 'blank':
            y -= 6
            continue

        if kind == 'h1':
            if ps:
                y = _check_y(c, y, ps, need=30)
            y -= 4
            c.setFont(_font('bold'), 16)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, y, text)
            y -= 22
        elif kind == 'h2':
            if ps:
                y = _check_y(c, y, ps, need=26)
            y -= 4
            c.setFont(_font('bold'), 13)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, y, text)
            y -= 19
        elif kind in ('h3', 'h4'):
            if ps:
                y = _check_y(c, y, ps, need=22)
            y -= 2
            c.setFont(_font('bold'), 11)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, y, text)
            y -= 16
        elif kind == 'bold_line':
            if ps:
                y = _check_y(c, y, ps, need=18)
            c.setFont(_font('bold'), 10)
            c.setFillColor(ESMERALD)
            c.drawString(MARGIN_L, y, text)
            y -= 15
        elif kind == 'bullet':
            y = _draw_bullet_list(c, y, [text], ps=ps)
        elif kind == 'numbered':
            y = _draw_bullet_list(c, y, [text], ps=ps)
        else:  # paragraph
            y = _draw_paragraphs(c, y, [text], ps=ps)
    return y


def _render_commercial_conditions(c, data, _proposal, ps=None, y=None):
    """PDF-only section: hour packages + scope-exclusion clause (Req 1 + 2).

    Draws three hour-bank packages (fixed hours + discount over an admin base
    rate → cost/hour and total), a badge clarifying that medium-or-higher
    effort requirements are quoted independently, and the scope-exclusion
    clause. Has no web component — it is skipped by the public carousel.
    """
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    currency = (_safe(data, 'currency')
                or (ps.get('_currency') if ps else '') or 'COP')

    def _money(n):
        return _format_currency(n, currency)

    # A proposal can opt out of printing the hour packages while keeping the
    # scope-exclusion clause, which is legal boilerplate that stands on its own.
    # Absent key → printed, so every existing proposal is unaffected. The effort
    # badge goes with the packages: it explains how requirements are quoted
    # against them, so on its own it references a table that is not there.
    packages_enabled = data.get('hourPackagesEnabled') is not False

    # ── Hour packages ──────────────────────────────────────────
    packages_title = _safe(data, 'packagesTitle')
    if packages_enabled and packages_title:
        y = _draw_subtitle(c, y, packages_title, ps=ps)
    intro = _safe(data, 'packagesIntro')
    if packages_enabled and intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 4

    try:
        hourly_rate = float(_safe(data, 'hourlyRate', 0) or 0)
    except (TypeError, ValueError):
        hourly_rate = 0

    # One full-width table replaces the stack of fixed-height cards:
    # long names/notes wrap inside their cell, the header repeats across
    # pages, and money columns align right for easy comparison.
    pkg_rows = []
    for pkg in ((_safe(data, 'packages', []) or []) if packages_enabled else []):
        name = _safe(pkg, 'name') or 'Paquete'
        try:
            hours = float(_safe(pkg, 'hours', 0) or 0)
        except (TypeError, ValueError):
            hours = 0
        try:
            discount = float(_safe(pkg, 'discountPercent', 0) or 0)
        except (TypeError, ValueError):
            discount = 0
        try:
            pkg_rate = float(_safe(pkg, 'hourlyRate', 0) or 0)
        except (TypeError, ValueError):
            pkg_rate = 0
        rate_eff = (pkg_rate or hourly_rate) * (1 - discount / 100)
        total_price = hours * rate_eff
        note = _safe(pkg, 'note')

        pkg_cell = f'**{name}**'
        if note:
            pkg_cell = f'{pkg_cell} — *{note}*'
        pkg_rows.append([
            pkg_cell,
            f'{int(hours)} h',
            f'-{int(discount)}%' if discount else '—',
            f'{_money(rate_eff)}/h',
            _money(total_price),
        ])
    if pkg_rows:
        y -= 2
        lang = (ps or {}).get('_pdf_lang', 'es')
        tax = _tax_suffix(currency).strip()
        headers = (
            ['Package', 'Hours', 'Disc.', f'Rate/hour ({tax})', f'Total ({tax})']
            if lang == 'en' else
            ['Paquete', 'Horas', 'Dcto.', f'Tarifa/hora ({tax})', f'Total ({tax})']
        )
        y = _draw_table(
            c, y, headers,
            pkg_rows, ps=ps, col_widths=[0.34, 0.10, 0.10, 0.22, 0.24],
            aligns=['left', 'center', 'center', 'right', 'right'])

    effort_badge = _safe(data, 'effortBadge')
    if packages_enabled and effort_badge:
        y -= 4
        y = _draw_callout_box(c, y, str(effort_badge), style='warning',
                              ps=ps, label='IMPORTANTE')

    # ── Scope-exclusion clause ─────────────────────────────────
    scope_title = _safe(data, 'scopeTitle')
    scope_paras = _safe(data, 'scopeParagraphs', []) or []
    if scope_paras:
        y -= 12
        label = _strip_emoji(str(scope_title)).upper() if scope_title else None
        y = _draw_callout_box(
            c, y, '\n\n'.join(str(p) for p in scope_paras),
            style='scope', ps=ps, label=label,
        )
    elif scope_title:
        y -= 12
        y = _draw_subtitle(c, y, scope_title, ps=ps)
    return y


def _render_process_methodology(c, data, _proposal, ps=None, y=None):
    """Render the process methodology section as numbered feature rows.

    Each step shows a numbered chip + title + description, with the
    client's contribution ("Tu aporte: …") as a right-anchored BONE pill.
    Mirrors ProcessMethodology.vue; previously the PDF skipped it.
    """
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
        y -= 6

    # clientAction already carries its own "Tu aporte:" / "Your input:"
    # label in the stored content, so it is used verbatim as the pill.
    for i, step in enumerate(_safe(data, 'steps', [])):
        action = _safe(step, 'clientAction')
        pill = _sanitize_pdf_text(str(action)) if action else None
        y = _draw_feature_row(
            c, y, _safe(step, 'title'),
            description=_safe(step, 'description'), ps=ps, index=i + 1,
            pill_text=pill, pill_bg=BONE, pill_fg=ESMERALD)
    return y


def _roi_has_content(data):
    """True when a roi_projection section has anything worth a PDF page.

    Defaults ship empty kpis/scenarios; without this gate every default
    proposal would grow a blank ROI section (and a stray TOC entry).
    """
    return bool(
        [k for k in _safe(data, 'kpis', []) if isinstance(k, dict)
         and (_safe(k, 'value') or _safe(k, 'label'))]
        or [s for s in _safe(data, 'scenarios', []) if isinstance(s, dict)
            and (_safe(s, 'metrics') or _safe(s, 'assumptions')
                 or _safe(s, 'name') or _safe(s, 'label'))]
    )


def _render_roi_projection(c, data, _proposal, ps=None, y=None):
    """Render the ROI projection: KPI tiles + per-scenario metric tables.

    Mirrors RoiProjection.vue. The generator only calls this when
    _roi_has_content(data) is True, so empty defaults are skipped.
    """
    if y is None:
        y = PAGE_H - MARGIN_T
    y = _draw_section_header(c, y, _safe(data, 'index'), _safe(data, 'title'))
    y -= 8

    subtitle = _safe(data, 'subtitle')
    if subtitle:
        y = _draw_paragraphs(c, y, [subtitle], ps=ps)
        y -= 4

    methodology = _safe(data, 'methodology')
    if methodology:
        y = _draw_callout_box(c, y, str(methodology), style='note',
                              ps=ps, label='METODOLOGÍA')

    # Headline KPI tiles (value + label; source as a sub-line).
    kpis = [k for k in _safe(data, 'kpis', []) if isinstance(k, dict)
            and (_safe(k, 'value') or _safe(k, 'label'))]
    if kpis:
        tiles = [{'value': _safe(k, 'value'), 'label': _safe(k, 'label'),
                  'sub': _safe(k, 'source')} for k in kpis]
        y = _draw_kpi_tile_row(c, y, tiles, ps=ps, accent_first=True)
        y -= 6

    scenarios = [s for s in _safe(data, 'scenarios', [])
                 if isinstance(s, dict)]
    if scenarios:
        sc_title = _safe(data, 'scenariosTitle')
        if sc_title:
            y -= 4
            y = _draw_subtitle(c, y, sc_title, ps=ps)
        for sc in scenarios:
            name = _safe(sc, 'label') or _safe(sc, 'name')
            if name:
                y = _draw_subtitle(c, y, name, ps=ps)
            assumptions = [a for a in _safe(sc, 'assumptions', []) if a]
            if assumptions:
                y = _draw_bullet_list(c, y, [str(a) for a in assumptions],
                                      ps=ps, font_size=8, leading=11)
            metrics = [m for m in _safe(sc, 'metrics', [])
                       if isinstance(m, dict)
                       and (_safe(m, 'label') or _safe(m, 'value'))]
            if metrics:
                rows = []
                for m in metrics:
                    label = _safe(m, 'label')
                    val = _safe(m, 'value')
                    basis = _safe(m, 'basis')
                    if _safe(m, 'emphasis'):
                        label = f'**{label}**'
                        val = f'**{val}**'
                    # Basis reads as a lighter inline note after the label
                    # (table cells wrap by width, not on newlines).
                    cell = label + (f' — *{basis}*' if basis else '')
                    rows.append([cell, val])
                y = _draw_table(c, y, ['Métrica', 'Proyección'], rows,
                                ps=ps, col_widths=[0.68, 0.32],
                                aligns=['left', 'right'])
            y -= 6

    cta = _safe(data, 'ctaNote')
    if cta:
        y -= 4
        y = _draw_callout_box(c, y, str(cta), style='tip', ps=ps)
    return y


# Map section_type → renderer
SECTION_RENDERERS = {
    'greeting': _render_greeting,
    'executive_summary': _render_executive_summary,
    'context_diagnostic': _render_context_diagnostic,
    'conversion_strategy': _render_conversion_strategy,
    'design_ux': _render_design_ux,
    'creative_support': _render_creative_support,
    'development_stages': _render_development_stages,
    'process_methodology': _render_process_methodology,
    'functional_requirements': _render_functional_requirements,
    'timeline': _render_timeline,
    'investment': _render_investment,
    'value_added_modules': _render_value_added_modules,
    'commercial_conditions': _render_commercial_conditions,
    'roi_projection': _render_roi_projection,
    'final_note': _render_final_note,
    'next_steps': _render_next_steps,
    # 'proposal_summary' stays web-only: its cards resolve dynamic server
    # sources (total_investment, timeline_duration, expires_at) the PDF
    # already shows in Investment / Timeline / Final Note.
    # Sections without a renderer are silently skipped by the generator.
}


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

class ProposalPdfService:
    """
    Generate a professional PDF of a business proposal using ReportLab.

    Usage:
        pdf_bytes = ProposalPdfService.generate(proposal)
    """

    @classmethod
    def generate(cls, proposal, selected_modules=None, *, sections_override=None,
                 include_hosting=True, _content_start=3):
        """
        Build a multi-page portrait-A4 PDF from the proposal's
        enabled sections and return the raw bytes.

        Sections flow continuously — each section starts where the
        previous one ended.  The greeting/cover page is the only
        section that always gets its own page.

        Args:
            proposal: BusinessProposal instance with related sections.
            selected_modules: Optional list of contracted module IDs for scope filtering.
            sections_override: Original section snapshots after whole-section exclusions.
            include_hosting: Whether investment includes the hosting block and KPI.

        Returns:
            bytes: The PDF content, or None on failure.
        """
        try:
            _register_fonts()

            if sections_override is not None:
                sections = list(sections_override)
            else:
                sections = list(proposal.sections.filter(is_enabled=True).order_by('order'))

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setTitle(f'Propuesta \u2014 {proposal.client_name}')
            c.setAuthor('Project App')
            # PDF metadata: creation date
            from django.utils import timezone as _tz
            _created = proposal.created_at or _tz.now()
            c.setSubject(
                f'Propuesta de negocio — {proposal.client_name} — '
                f'{_created.strftime("%Y-%m-%d")}'
            )

            ps = {
                'num': _content_start,
                'client': proposal.client_name,
                'selected_modules': selected_modules,
                'include_hosting': include_hosting,

            }

            _value_added_ids = set()
            _value_added_catalog = {}
            for _sec in sections:
                _cj = _sec.content_json or {}
                if _sec.section_type == 'value_added_modules':
                    _value_added_ids.update(_cj.get('module_ids') or [])
                elif _sec.section_type == 'functional_requirements':
                    for _grp in list(_cj.get('groups') or []) + list(_cj.get('additionalModules') or []):
                        _gid = _safe(_grp, 'id')
                        if _gid and _gid not in _value_added_catalog:
                            _value_added_catalog[_gid] = _grp
            ps['_value_added_ids'] = _value_added_ids
            ps['_value_added_catalog'] = _value_added_catalog

            # Extract base_weeks from timeline section for dynamic duration
            base_weeks = 0
            if selected_modules is not None:
                for _sec in sections:
                    if _sec.section_type == 'timeline':
                        _td = (_sec.content_json or {}).get('totalDuration', '')
                        _wm = re.search(r'(\d+)\s*(?:semana|week)', str(_td), re.IGNORECASE)
                        if _wm:
                            base_weeks = int(_wm.group(1))
                        break
            ps['base_weeks'] = base_weeks

            # Item → technical requirements map for the per-group detail
            # pages. Shares the technical PDF's normalize+filter pipeline
            # so both documents stay consistent.
            from content.services.proposal_module_links import (
                build_item_requirements_map,
            )
            from content.services.technical_document_filter import (
                get_filtered_technical_document,
            )
            item_req_map = {}
            tech_sec = next(
                (s for s in sections if s.section_type == 'technical_document'),
                None,
            )
            if tech_sec and isinstance(tech_sec.content_json, dict):
                section_payloads = [
                    {
                        'section_type': s.section_type,
                        'content_json': s.content_json if isinstance(s.content_json, dict) else {},
                    }
                    for s in sections
                ]
                tech_data = get_filtered_technical_document(
                    tech_sec.content_json, section_payloads, selected_modules,
                )
                item_req_map = build_item_requirements_map(tech_data)
            ps['_item_requirements_map'] = item_req_map
            ps['_pdf_lang'] = 'en' if proposal.language == 'en' else 'es'

            # Agreed investment and currency,
            # used by the value-added renderer to gate module minimums
            # ("condicionado"). Canonical source shared with panel/serializer.
            from content.services.proposal_totals_service import (
                effective_total_for_proposal,
            )
            ps['_effective_total'] = effective_total_for_proposal(proposal)
            ps['_currency'] = getattr(proposal, 'currency', 'COP') or 'COP'

            # ── Pass A: Content canvas (pages 3+) ────────────────────
            # Pages 1 = greeting, 2 = TOC; content starts at page 3.
            date_str = format_date_es(_created)

            _draw_header_bar(c)
            y = PAGE_H - MARGIN_T
            first_content = True
            toc_entries = []

            for sec in ordered_commercial_sections(sections):
                stype = sec.section_type
                if stype in ('technical_document', 'greeting'):
                    continue
                # Shallow copy: the index/title defaults below write into
                # ``data``, and without this they would mutate the stored
                # ``sec.content_json`` for every section that is not re-seeded.
                data = dict(sec.content_json or {})

                # Two modes, and they are genuinely different sources:
                #
                # auto (default): the catalog owns the packages. Re-seed
                # currency/hourlyRate/packages on every generation so catalog
                # edits reach every downloaded PDF. Titles, intros, effort badge
                # and scope clause stay from the stored section. Empty catalog →
                # seed returns its input untouched (snapshot fallback).
                #
                # manual: the proposal owns its own package list — it can add,
                # remove and rename rows — so the stored snapshot is
                # authoritative and the catalog never touches it. The overlay
                # only applies the legacy manualHourlyRate/manualPackageRates
                # shape and is a no-op once a proposal has been re-saved from
                # the panel.
                #
                # Any failure → keep the stored snapshot.
                if stype == 'commercial_conditions':
                    try:
                        if data.get('hourPackagesMode') == 'manual':
                            data = apply_manual_hour_rates(data)
                        else:
                            data = seed_commercial_conditions_from_catalog(
                                data,
                                nationality=proposal.nationality,
                                language=ps['_pdf_lang'],
                            )
                    except Exception:
                        logger.warning(
                            'Hour-package re-seed failed for proposal %s; '
                            'using stored snapshot', proposal.pk,
                            exc_info=True,
                        )

                if 'title' not in data or not data['title']:
                    data['title'] = sec.title
                is_paste = (
                    data.get('_editMode') == 'paste'
                    and data.get('rawText')
                )
                renderer = SECTION_RENDERERS.get(stype)

                # Web-only sections have no renderer and no paste content;
                # skip them entirely so they don't pollute the TOC.
                if not is_paste and not renderer:
                    continue

                # ROI has a renderer but ships empty by default — skip
                # (before the TOC entry) when there is nothing to show.
                if (stype == 'roi_projection' and not is_paste
                        and not _roi_has_content(data)):
                    continue

                # The value-added renderer also skips unresolved module IDs.
                # Apply that visibility guard before numbering or adding a TOC row.
                if (stype == 'value_added_modules' and not is_paste
                        and not any(mid in _value_added_catalog
                                    for mid in (data.get('module_ids') or []))):
                    continue

                data['index'] = str(len(toc_entries) + 1).zfill(2)

                if first_content:
                    first_content = False
                else:
                    y -= 28
                    # Reserve the measured height of the section header so a
                    # multi-line title is never orphaned at the page bottom.
                    y = _check_y(c, y, ps,
                                 need=_section_header_height(data['title']) + 38)

                # Record TOC entry at the page where this section starts
                toc_entries.append((data['index'], data['title'], ps['num']))

                if is_paste:
                    y = _render_raw_text(c, data, proposal, ps=ps,
                                         y=y) or y
                elif renderer:
                    y = renderer(c, data, proposal, ps=ps, y=y) or y

                    # Functional requirements: per-group details
                    func_groups = ps.pop('_func_req_groups', None)
                    parent_idx = data.get('index', '')
                    sel_ids = ps.get('selected_modules')
                    if stype == 'functional_requirements' and func_groups:
                        # Filter out hidden groups and calculator-module groups not selected
                        func_groups = [g for g in func_groups if _safe(g, 'is_visible', True) is not False]
                        func_groups = _filter_calculator_groups(func_groups, sel_ids)
                        visible_group_count = 0
                        for grp in func_groups:
                            grp_paste = (
                                _safe(grp, '_editMode') == 'paste'
                                and _safe(grp, 'rawText')
                            )
                            items = _safe(grp, 'items', [])
                            # Filter out deselected configurable FR items only
                            if sel_ids is not None and items:
                                grp_key = (_safe(grp, 'id') or _safe(grp, 'title') or '')
                                filtered = []
                                for it in items:
                                    is_req = _safe(it, 'is_required')
                                    if is_req is True:
                                        filtered.append(it)
                                    else:
                                        configurable = _safe(it, 'price') or is_req is False
                                        if not configurable:
                                            filtered.append(it)
                                        else:
                                            it_name = _safe(it, 'name') or ''
                                            fr_id = re.sub(r'\s+', '-', f'fr-{grp_key}-{it_name}').lower()
                                            if fr_id in sel_ids:
                                                filtered.append(it)
                                items = filtered
                                grp = dict(grp, items=items)
                            if not items and not grp_paste:
                                continue
                            visible_group_count += 1
                            sub_idx = (
                                f'{parent_idx}.{visible_group_count}'
                                if parent_idx else str(visible_group_count)
                            )
                            y -= 28
                            y = _check_y(
                                c, y, ps,
                                need=_section_header_height(
                                    _safe(grp, 'title'), sub_idx))
                            if grp_paste:
                                y = _render_raw_text(
                                    c,
                                    {'title': _safe(grp, 'title'),
                                     'index': sub_idx,
                                     'rawText': _safe(grp, 'rawText')},
                                    proposal, ps=ps, y=y,
                                ) or y
                            else:
                                y = _render_requirement_group_page(
                                    c, grp, ps=ps, y=y,
                                    sub_index=sub_idx,
                                ) or y
                elif data.get('rawText'):
                    y = _render_raw_text(c, data, proposal, ps=ps,
                                         y=y) or y

            # Creation date line at the bottom of the last content page
            y -= 30
            y = _check_y(c, y, ps, need=20)
            c.setFont(_font('regular'), 8)
            c.setFillColor(GRAY_500)
            c.drawCentredString(
                PAGE_W / 2, y,
                f'Fecha de creaci\u00f3n de la propuesta: {date_str}',
            )
            _draw_footer(c, ps['num'], client_name=ps['client'])
            c.save()
            content_bytes = buf.getvalue()
            buf.close()

            # ── Pass B: Greeting + TOC (pages 1-2) ───────────────────
            buf_prefix = io.BytesIO()
            c_prefix = canvas.Canvas(buf_prefix, pagesize=A4)
            c_prefix.setTitle(f'Propuesta \u2014 {proposal.client_name}')
            c_prefix.setAuthor('Project App')
            ps_prefix = {'num': 1, 'client': proposal.client_name}

            greeting_sec = next(
                (s for s in sections if s.section_type == 'greeting'), None
            )
            if greeting_sec:
                g_data = dict(greeting_sec.content_json or {})
                if 'title' not in g_data or not g_data['title']:
                    g_data['title'] = greeting_sec.title
                is_paste_g = (
                    g_data.get('_editMode') == 'paste'
                    and g_data.get('rawText')
                )
                _draw_header_bar(c_prefix)
                if is_paste_g:
                    _render_raw_text(c_prefix, g_data, proposal, ps=ps_prefix)
                else:
                    renderer_g = SECTION_RENDERERS.get('greeting')
                    if renderer_g:
                        renderer_g(c_prefix, g_data, proposal, ps=ps_prefix)
                _draw_footer(c_prefix, ps_prefix['num'],
                             client_name=ps_prefix['client'])
                c_prefix.showPage()
                ps_prefix['num'] += 1

            link_areas = []
            _draw_toc_page(c_prefix, toc_entries, ps_prefix, link_areas=link_areas)
            c_prefix.save()
            prefix_bytes = buf_prefix.getvalue()
            buf_prefix.close()
            content_start = _content_start
            if ps_prefix['num'] != content_start:
                return cls.generate(
                    proposal, selected_modules=selected_modules,
                    sections_override=sections_override, include_hosting=include_hosting, _content_start=ps_prefix['num'],
                )

            pdf_bytes = cls._merge_with_covers(content_bytes, prepend_bytes=prefix_bytes)

            cover_offset = 1 if COVER_PDF.exists() else 0
            pdf_bytes = _apply_toc_links(pdf_bytes, link_areas, cover_offset)

            logger.info(
                'Generated PDF for proposal %s (%d bytes, %d pages)',
                proposal.uuid, len(pdf_bytes), ps['num'],
            )
            return pdf_bytes

        except Exception:
            logger.exception(
                'Failed to generate PDF for proposal %s', proposal.uuid,
            )
            return None

    @staticmethod
    def _merge_with_covers(content_bytes, prepend_bytes=None):
        """Merge static Portada + content + Contraportada.

        Delegates to the shared ``merge_with_covers`` in pdf_utils.
        """
        from content.services.pdf_utils import merge_with_covers
        return merge_with_covers(content_bytes, prepend_bytes=prepend_bytes)

    @classmethod
    def generate_to_file(cls, proposal, output_path=None):
        """
        Generate PDF and save to a file. Returns the file path or None.

        Args:
            proposal: BusinessProposal instance.
            output_path: Optional path. If None, uses a temp file.

        Returns:
            str: Path to the generated PDF file, or None on failure.
        """
        pdf_bytes = cls.generate(proposal)
        if not pdf_bytes:
            return None

        if output_path is None:
            media_temp = Path(settings.MEDIA_ROOT) / 'temp'
            media_temp.mkdir(parents=True, exist_ok=True)
            fd, output_path = tempfile.mkstemp(
                suffix='.pdf',
                prefix=f'proposal_{proposal.uuid}_',
                dir=str(media_temp),
            )
            os.close(fd)

        output_path = str(output_path)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

        logger.info('Saved PDF to %s', output_path)
        return output_path
