"""PDF generator for the client-facing diagnostic view.

Mirrors the palette and layout primitives of ``ProposalPdfService`` but
renders the diagnostic's enabled sections into a compact A4 document.
Each section type has a small dedicated renderer that walks the
``content_json`` payload and re-uses the shared helpers in ``pdf_utils``.
"""

from content.services.editorial_projection import editorial_projection

import io
import logging
import textwrap

from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.services.pdf_utils import (
    BONE,
    ESMERALD,
    ESMERALD_80,
    GRAY_500,
    GREEN_LIGHT,
    LEMON,
    MARGIN_B,
    MARGIN_L,
    MARGIN_T,
    PAGE_H,
    PAGE_W,
    TEXT_AREA_W,
    _check_y,
    _draw_bullet_list,
    _draw_footer,
    _draw_header_bar,
    _draw_paragraphs,
    _draw_section_header,
    _draw_subtitle,
    _font,
    _format_cop,
    _new_page,
    _register_fonts,
    _safe,
    _strip_emoji,
)

logger = logging.getLogger(__name__)


def _draw_cover(c, diagnostic):
    """Simple branded cover page for the diagnostic."""
    c.setFillColor(BONE)
    c.circle(60, 80, 90, fill=1, stroke=0)
    c.setFillColor(ESMERALD)
    c.circle(PAGE_W - 40, PAGE_H - 40, 140, fill=1, stroke=0)

    mid_y = PAGE_H / 2 + 60

    c.setFont(_font('light'), 13)
    c.setFillColor(GREEN_LIGHT)
    c.drawCentredString(PAGE_W / 2, mid_y + 70, 'DIAGNÓSTICO DE APLICACIÓN WEB')

    client_name = diagnostic.client_name or diagnostic.title or ''
    c.setFont(_font('light'), 34)
    c.setFillColor(ESMERALD)
    if len(client_name) > 22:
        lines = textwrap.wrap(client_name, width=22)
        ny = mid_y + 20
        for line in lines:
            c.drawCentredString(PAGE_W / 2, ny, line)
            ny -= 40
    else:
        c.drawCentredString(PAGE_W / 2, mid_y + 20, client_name)

    line_y = mid_y - 20
    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(PAGE_W / 2 - 60, line_y, PAGE_W / 2 + 60, line_y)
    c.setFillColor(LEMON)
    c.circle(PAGE_W / 2 - 60, line_y, 2.5, fill=1, stroke=0)
    c.circle(PAGE_W / 2 + 60, line_y, 2.5, fill=1, stroke=0)

    title = diagnostic.title or ''
    if title and title != client_name:
        c.setFont(_font('italic'), 12)
        c.setFillColor(GREEN_LIGHT)
        for line in textwrap.wrap(_strip_emoji(title), width=56):
            c.drawCentredString(PAGE_W / 2, line_y - 28, line)
            line_y -= 16

    c.setFont(_font('regular'), 8)
    c.setFillColor(GRAY_500)
    c.drawCentredString(PAGE_W / 2, MARGIN_B + 10, 'Project App  |  projectapp.co')
    c.showPage()


# ─── per-section renderers ──────────────────────────────────────

def _render_purpose(c, y, data, _diagnostic, ps):
    paragraphs = _safe(data, 'paragraphs', []) or []
    y = _draw_paragraphs(c, y, paragraphs, ps=ps)
    scope_note = _safe(data, 'scopeNote')
    if scope_note:
        y -= 6
        y = _draw_subtitle(c, y, 'Alcance', ps=ps)
        y = _draw_paragraphs(c, y, [scope_note], ps=ps)
    levels = _safe(data, 'severityLevels', []) or []
    if levels:
        y -= 6
        y = _draw_subtitle(c, y, _safe(data, 'severityTitle', 'Escala de severidad'), ps=ps)
        bullets = [f"{_safe(lvl, 'level')}: {_safe(lvl, 'meaning')}" for lvl in levels]
        y = _draw_bullet_list(c, y, bullets, ps=ps)
    return y


def _render_radiography(c, y, data, diagnostic, ps):
    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
    includes = _safe(data, 'includes', []) or []
    if includes:
        y -= 6
        y = _draw_subtitle(
            c, y, _safe(data, 'includesTitle', '¿Qué incluye esta radiografía?'), ps=ps,
        )
        bullets = [
            f"{_safe(it, 'title')}: {_safe(it, 'description')}".strip(': ').strip()
            for it in includes
        ]
        y = _draw_bullet_list(c, y, bullets, ps=ps)
    rows = _safe(data, 'classificationRows', []) or []
    if rows:
        y -= 6
        y = _draw_subtitle(
            c, y, _safe(data, 'classificationTitle', 'Clasificación por tamaño'), ps=ps,
        )
        for row in rows:
            y = _check_y(c, y, ps, need=30)
            line = (
                f"{_safe(row, 'dimension')} — "
                f"Pequeña: {_safe(row, 'small')} · "
                f"Mediana: {_safe(row, 'medium')} · "
                f"Grande: {_safe(row, 'large')}"
            )
            y = _draw_paragraphs(c, y, [line], ps=ps)
    return y


def _render_categories(c, y, data, _diagnostic, ps):
    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
    categories = _safe(data, 'categories', []) or []
    for idx, cat in enumerate(categories, start=1):
        y = _check_y(c, y, ps, need=50)
        y -= 4
        y = _draw_subtitle(c, y, f"{idx}. {_safe(cat, 'title')}", ps=ps)
        description = _safe(cat, 'description')
        if description:
            y = _draw_paragraphs(c, y, [description], ps=ps)
        strengths = _safe(cat, 'strengths', []) or []
        if strengths:
            y -= 3
            y = _draw_paragraphs(c, y, ['Fortalezas:'], ps=ps)
            y = _draw_bullet_list(c, y, strengths, ps=ps)
        findings = _safe(cat, 'findings', []) or []
        if findings:
            y -= 3
            y = _draw_paragraphs(c, y, ['Hallazgos:'], ps=ps)
            bullets = [
                f"[{_safe(f, 'level', 'n/a')}] {_safe(f, 'title')}"
                + (f" — {_safe(f, 'detail')}" if _safe(f, 'detail') else '')
                for f in findings
            ]
            y = _draw_bullet_list(c, y, bullets, ps=ps)
        recs = _safe(cat, 'recommendations', []) or []
        if recs:
            y -= 3
            y = _draw_paragraphs(c, y, ['Recomendaciones:'], ps=ps)
            bullets = [
                f"[{_safe(r, 'level', 'n/a')}] {_safe(r, 'title')}"
                + (f" — {_safe(r, 'detail')}" if _safe(r, 'detail') else '')
                for r in recs
            ]
            y = _draw_bullet_list(c, y, bullets, ps=ps)
    return y


def _render_delivery_structure(c, y, data, _diagnostic, ps):
    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
    blocks = _safe(data, 'blocks', []) or []
    for b in blocks:
        y = _check_y(c, y, ps, need=40)
        y -= 4
        y = _draw_subtitle(c, y, _safe(b, 'title'), ps=ps)
        y = _draw_paragraphs(c, y, _safe(b, 'paragraphs', []) or [], ps=ps)
        example = _safe(b, 'example')
        if example:
            y = _draw_paragraphs(c, y, [f"Ejemplo: {example}"], ps=ps)
    return y


def _render_executive_summary(c, y, data, _diagnostic, ps):
    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
    counts = _safe(data, 'severityCounts', {}) or {}
    if counts:
        y -= 4
        labels = {'critico': 'Crítico', 'alto': 'Alto', 'medio': 'Medio', 'bajo': 'Bajo'}
        summary = ' · '.join(
            f"{labels.get(k, k)}: {counts.get(k, 0)}" for k in ('critico', 'alto', 'medio', 'bajo')
        )
        y = _draw_paragraphs(c, y, [summary], ps=ps)
    narrative = _safe(data, 'narrative')
    if narrative:
        y -= 4
        y = _draw_paragraphs(c, y, [narrative], ps=ps)
    highlights = _safe(data, 'highlights', []) or []
    if highlights:
        y -= 4
        y = _draw_bullet_list(c, y, highlights, ps=ps)
    return y


def _render_cost(c, y, data, diagnostic, ps):
    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
    bullets = _safe(data, 'valueBullets', []) or []
    bullets = [b for b in bullets if isinstance(b, str) and b.strip()]
    if bullets:
        y -= 4
        y = _draw_bullet_list(c, y, bullets, ps=ps)
    amount = diagnostic.investment_amount
    if amount:
        currency = diagnostic.currency or ''
        y -= 6
        y = _draw_subtitle(c, y, 'Inversión', ps=ps)
        y = _draw_paragraphs(c, y, [f"{_format_cop(int(amount))} {currency}".strip()], ps=ps)
    terms = getattr(diagnostic, 'payment_terms', {}) or {}
    pcts = [terms.get('initial_pct'), terms.get('final_pct')]
    descs = _safe(data, 'paymentDescription', []) or []
    if descs:
        y -= 4
        y = _draw_subtitle(c, y, 'Formas de pago', ps=ps)
        payment_lines = []
        for idx, item in enumerate(descs):
            pct = pcts[idx] if idx < len(pcts) and pcts[idx] is not None else ''
            prefix = f"{pct}% " if pct != '' else ''
            payment_lines.append(
                f"{prefix}{_safe(item, 'label')}"
                + (f" — {_safe(item, 'detail')}" if _safe(item, 'detail') else '')
            )
        y = _draw_bullet_list(c, y, payment_lines, ps=ps)
    note = _safe(data, 'note')
    if note:
        y -= 4
        y = _draw_paragraphs(c, y, [f"Nota: {note}"], ps=ps)
    return y


def _render_timeline(c, y, data, diagnostic, ps):
    intro = _safe(data, 'intro')
    if intro:
        y = _draw_paragraphs(c, y, [intro], ps=ps)
    duration = getattr(diagnostic, 'duration_label', '') or ''
    if duration:
        y = _draw_paragraphs(c, y, [f"Duración estimada: {duration}."], ps=ps)
    distribution = _safe(data, 'distribution', []) or []
    if distribution:
        y -= 4
        y = _draw_subtitle(c, y, _safe(data, 'distributionTitle', 'Distribución'), ps=ps)
        bullets = [
            f"{_safe(d, 'dayRange')} — {_safe(d, 'description')}".strip(' —')
            for d in distribution
        ]
        y = _draw_bullet_list(c, y, bullets, ps=ps)
    return y


def _render_scope(c, y, data, _diagnostic, ps):
    considerations = _safe(data, 'considerations', []) or []
    if considerations:
        y = _draw_bullet_list(c, y, considerations, ps=ps)
    return y


_RENDERERS = {
    'purpose': _render_purpose,
    'radiography': _render_radiography,
    'categories': _render_categories,
    'delivery_structure': _render_delivery_structure,
    'executive_summary': _render_executive_summary,
    'cost': _render_cost,
    'timeline': _render_timeline,
    'scope': _render_scope,
}


class DiagnosticPdfService:
    """Generate a PDF of a diagnostic's enabled public sections."""

    @classmethod
    def generate(cls, diagnostic):
        try:
            _register_fonts()

            sections = list(
                diagnostic.sections
                .filter(is_enabled=True)
                .order_by('order')
            )

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            client_name = diagnostic.client_name or ''
            c.setTitle(f'Diagnóstico — {client_name or diagnostic.title}')
            c.setAuthor('Project App')
            created = diagnostic.created_at or timezone.now()
            c.setSubject(
                f'Diagnóstico de aplicación web — {client_name} — '
                f'{created.strftime("%Y-%m-%d")}'
            )

            _draw_cover(c, diagnostic)

            ps = {'num': 2, 'client': client_name}
            _draw_header_bar(c)
            y = PAGE_H - MARGIN_T

            for idx, section in enumerate(sections, start=1):
                data = editorial_projection({'content_json': section.content_json or {}}, section.text_formats)['content_json']
                title = section.title or _safe(data, 'title') or section.get_section_type_display()
                index_str = _safe(data, 'index') or f'{idx:02d}'

                y = _check_y(c, y, ps, need=80)
                y = _draw_section_header(c, y, str(index_str), title)
                y -= 6

                renderer = _RENDERERS.get(section.section_type)
                if renderer is None:
                    paragraphs = _safe(data, 'paragraphs', []) or []
                    y = _draw_paragraphs(c, y, paragraphs, ps=ps)
                else:
                    y = renderer(c, y, data, diagnostic, ps)
                y -= 10

            _draw_footer(c, ps['num'], None, ps['client'])
            c.showPage()
            c.save()
            return buf.getvalue()
        except Exception:
            logger.exception('Failed to generate diagnostic PDF')
            return None
