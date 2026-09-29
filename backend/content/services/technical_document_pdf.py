"""
Technical-only PDF (ReportLab canvas) for proposal technical_document section.

Commercial proposal PDF excludes this section; ?doc=technical uses this module.
"""

import io
import logging

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.services.pdf_utils import (
    CONTENT_W,
    COVER_PDF,
    COVER_TECHNICAL_PDF,
    ESMERALD,
    ESMERALD_80,
    GRAY_500,
    LEMON,
    MARGIN_L,
    MARGIN_T,
    PAGE_H,
    PAGE_W,
    WHITE,
    _apply_toc_links,
    _check_y,
    _draw_bullet_list,
    _draw_decorative_title_page,
    _draw_footer,
    _draw_header_bar,
    _draw_kpi_tile_row,
    _draw_section_header,
    _section_header_height,
    _draw_separator,
    _draw_toc_page,
    _pdf_label,
    _font,
    _register_fonts,
    _safe,
    _sanitize_pdf_text,
    _strip_emoji,
    _wrap_by_width,
    format_date_es,
    merge_with_covers,
)

from content.services.proposal_pdf_layout import (
    _draw_paragraphs, _draw_subtitle, _draw_table,
    _draw_heading_badge, _draw_requirements_table, _heading_badge_height,
)

logger = logging.getLogger(__name__)

# Each entry owns a whole printed chapter, including all of its fields.
_SECTION_FIELDS = {
    'purpose': ('purpose',),
    'stack': ('stack',),
    'architecture': ('architecture',),
    'dataModel': ('dataModel',),
    'growthReadiness': ('growthReadiness',),
    'epics': ('epics',),
    'api': ('apiSummary', 'apiDomains'),
    'integrations': ('integrations',),
    'environments': ('environmentsNote', 'environments'),
    'security': ('security',),
    'performanceQuality': ('performanceQuality',),
    'backups': ('backupsNote',),
    'quality': ('quality',),
    'decisions': ('decisions',),
}


def _nonempty_str(v):
    return isinstance(v, str) and v.strip()


def _row_any(row, keys):
    if not row or not isinstance(row, dict):
        return False
    return any(_nonempty_str(row.get(k)) for k in keys)


def generate_technical_document_pdf(proposal, selected_modules=None, *, formal=None,
                                    included_sections=None, _content_start=3):
    """
    Build a PDF from the enabled technical_document section only.
    Returns bytes or None if section missing/disabled or on error.

    selected_modules: optional list of module/group ids (module-*, group-*).
    None means "derive the proposal's current selection" (client-confirmed
    list or admin defaults), so epics of unselected optional modules never
    leak into the rendered document. Empty list filters to base-scope
    requirements only.

    included_sections: optional chapter keys from _SECTION_FIELDS, in the
    document's normal order. Only whole chapters are omitted; retained values
    and the module-selection pipeline are unchanged. None keeps all chapters.
    """
    from content.services.proposal_pdf_service import (
        default_selected_modules_from_content,
    )
    from content.services.technical_document_filter import (
        get_filtered_technical_document,
    )

    if formal:
        data = formal.technical_data
    else:
        sec = (
            proposal.sections.filter(is_enabled=True, section_type='technical_document').first()
        )
        if not sec:
            return None
        data = sec.content_json if isinstance(sec.content_json, dict) else {}
        section_payloads = [
            {
                'section_type': section.section_type,
                'content_json': section.content_json if isinstance(section.content_json, dict) else {},
            }
            for section in proposal.sections.all()
        ]
        if selected_modules is None:
            selected_modules = default_selected_modules_from_content(proposal)
        data = get_filtered_technical_document(data, section_payloads, selected_modules)
    if included_sections is not None:
        fields = {field for chapter in included_sections for field in _SECTION_FIELDS[chapter]}
        data = {key: value for key, value in data.items() if key in fields}
    try:
        _register_fonts()
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setTitle(formal.title if formal else f'Detalle t\u00e9cnico \u2014 {proposal.client_name}')
        c.setAuthor('Project App')

        from django.utils import timezone as _tz

        _created = proposal.created_at or _tz.now()
        date_str = format_date_es(_created)

        # ── Pass A: Content pages (ps.num starts at 3) ───────
        # Page 1 = title page, page 2 = TOC; content begins at page 3.
        ps = {'num': formal.content_start if formal else _content_start,
              'client': proposal.client_name, 'formal': formal,
              '_pdf_lang': getattr(proposal, 'language', 'es') or 'es'}

        _draw_header_bar(c)
        y = PAGE_H - MARGIN_T
        section_i = 0
        toc_entries = []

        # Opening KPI tiles — same "product family" glance as the web.
        _epics_for_kpi = [e for e in (data.get('epics') or [])
                          if isinstance(e, dict)]
        _reqs_total = sum(
            len([q for q in (e.get('requirements') or [])
                 if isinstance(q, dict)])
            for e in _epics_for_kpi)
        _integ = data.get('integrations') if isinstance(
            data.get('integrations'), dict) else {}
        _integ_total = len([r for r in (_integ.get('included') or [])
                            if isinstance(r, dict)])
        _kpi_tiles = []
        if _epics_for_kpi:
            _kpi_tiles.append({'value': str(len(_epics_for_kpi)),
                               'label': 'Módulos'})
        if _reqs_total:
            _kpi_tiles.append({'value': str(_reqs_total),
                               'label': 'Requerimientos'})
        if _integ_total:
            _kpi_tiles.append({'value': str(_integ_total),
                               'label': 'Integraciones'})
        if _kpi_tiles:
            y = _draw_kpi_tile_row(c, y, _kpi_tiles, ps=ps,
                                   accent_first=True)

        def next_section(title_es, first_block_height=20):
            nonlocal y, section_i
            title_es = _pdf_label(title_es, ps)
            section_i += 1
            idx = str(section_i).zfill(2)
            y -= 24
            y = _check_y(c, y, ps, need=_section_header_height(title_es) + first_block_height)
            section_page = ps['num']
            y = _draw_section_header(c, y, idx, title_es, ps=ps)
            toc_entries.append((idx, title_es, section_page))
            return y

        # ── 1. Propósito ──────────────────────────────────────
        purpose = data.get('purpose') or ''
        if _nonempty_str(purpose):
            y = next_section('Prop\u00f3sito')
            y = _draw_paragraphs(c, y, [purpose.strip()], ps=ps)

        # ── 2. Stack tecnológico ──────────────────────────────
        stack = data.get('stack') or []
        stack_rows = [
            r for r in stack
            if isinstance(r, dict) and _row_any(r, ('layer', 'technology', 'rationale'))
        ]
        if stack_rows:
            y = next_section('Stack tecnol\u00f3gico')
            headers = ['Capa', 'Tecnolog\u00eda', 'Justificaci\u00f3n']
            rows = [
                [
                    _safe(r, 'layer') or '\u2014',
                    _safe(r, 'technology') or '\u2014',
                    _safe(r, 'rationale') or '',
                ]
                for r in stack_rows
            ]
            y = _draw_table(c, y, headers, rows, ps=ps,
                            col_widths=[0.18, 0.28, 0.54])

        # ── 3. Arquitectura ───────────────────────────────────
        arch = data.get('architecture') if isinstance(data.get('architecture'), dict) else {}
        arch_text = (arch.get('summary') or '').strip()
        arch_note = (arch.get('diagramNote') or '').strip()
        patterns = [p for p in (arch.get('patterns') or []) if isinstance(p, dict) and _row_any(
            p, ('component', 'pattern', 'description')
        )]
        if arch_text or arch_note or patterns:
            y = next_section('Arquitectura')
            if arch_text:
                y = _draw_paragraphs(c, y, [arch_text], ps=ps)
            if patterns:
                y -= 8
                headers = ['Componente', 'Patr\u00f3n', 'Descripci\u00f3n']
                rows = [
                    [
                        _safe(p, 'component') or '\u2014',
                        _safe(p, 'pattern') or '\u2014',
                        _safe(p, 'description') or '',
                    ]
                    for p in patterns
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.20, 0.24, 0.56])
            if arch_note:
                y -= 8
                y = _draw_paragraphs(c, y, [f'{"Note" if formal and formal.language == "en" else "Nota"}: {arch_note}'], ps=ps)

        # ── 4. Modelo de datos ────────────────────────────────
        dm = data.get('dataModel') if isinstance(data.get('dataModel'), dict) else {}
        dm_sum = (dm.get('summary') or '').strip()
        dm_rel = (dm.get('relationships') or '').strip()
        entities = [
            e for e in (dm.get('entities') or [])
            if isinstance(e, dict) and _row_any(e, ('name', 'description', 'keyFields'))
        ]
        if dm_sum or dm_rel or entities:
            y = next_section('Modelo de datos')
            if dm_sum:
                y = _draw_paragraphs(c, y, [dm_sum], ps=ps)
            if entities:
                y -= 8
                headers = ['Entidad', 'Descripci\u00f3n', 'Campos clave']
                rows = [
                    [
                        _safe(e, 'name') or '\u2014',
                        _safe(e, 'description') or '',
                        (f"`{_safe(e, 'keyFields')}`"
                         if _safe(e, 'keyFields') else ''),
                    ]
                    for e in entities
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.18, 0.44, 0.38])
            if dm_rel:
                y -= 8
                y = _draw_subtitle(c, y, 'Relaciones', ps=ps)
                y = _draw_paragraphs(c, y, [dm_rel], ps=ps)

        # ── 5. Preparación para el crecimiento ────────────────
        gr = data.get('growthReadiness') if isinstance(data.get('growthReadiness'), dict) else {}
        gr_sum = (gr.get('summary') or '').strip()
        gr_strat = [
            r for r in (gr.get('strategies') or [])
            if isinstance(r, dict) and _row_any(r, ('dimension', 'preparation', 'evolution'))
        ]
        if gr_sum or gr_strat:
            y = next_section('Preparación técnica incluida' if formal else 'Preparaci\u00f3n para el crecimiento')
            if gr_sum:
                y = _draw_paragraphs(c, y, [gr_sum], ps=ps)
            if gr_strat:
                y -= 8
                headers = ['Dimensi\u00f3n', 'Preparaci\u00f3n'] if formal else ['Dimensi\u00f3n', 'Preparaci\u00f3n', 'Evoluci\u00f3n']
                rows = [
                    [
                        _safe(r, 'dimension') or '\u2014',
                        _safe(r, 'preparation') or '',
                        _safe(r, 'evolution') or '',
                    ]
                    for r in gr_strat
                ]
                if formal:
                    rows = [row[:2] for row in rows]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.3, 0.7] if formal else [0.18, 0.41, 0.41])

        # ── 6. Módulos del producto ───────────────────────────
        epics = [e for e in (data.get('epics') or []) if isinstance(e, dict)]
        epic_blocks = []
        for ep in epics:
            reqs = [
                q for q in (ep.get('requirements') or [])
                if isinstance(q, dict) and _row_any(
                    q, ('title', 'description', 'configuration', 'usageFlow', 'flowKey')
                )
            ]
            if _nonempty_str(ep.get('title')) or _nonempty_str(ep.get('description')) or reqs:
                epic_blocks.append((ep, reqs))
        if epic_blocks:
            first_epic, first_reqs = epic_blocks[0]
            first_title = _safe(first_epic, 'title') or _safe(first_epic, 'epicKey') or 'Módulo'
            first_badge = f'{len(first_reqs)} requerimientos' if first_reqs else ''
            y = next_section('M\u00f3dulos del producto',
                             _heading_badge_height(c, first_title, first_badge))
            for ei, (ep, reqs) in enumerate(epic_blocks):
                if ei > 0:
                    y = _draw_separator(c, y, ps=ps)

                head = _safe(ep, 'title') or _safe(ep, 'epicKey') or 'M\u00f3dulo'
                if formal:
                    head = ' · '.join(filter(None, [ep.get('epicKey'), ep.get('title')]))
                count_label = (
                    f'{len(reqs)} {"requirement" if formal and formal.language == "en" else "requerimiento"}'
                    f'{"s" if len(reqs) != 1 else ""}' if reqs else '')
                y = _draw_heading_badge(c, y, _strip_emoji(head), count_label, ps=ps)

                desc = (_safe(ep, 'description') or '').strip()
                if desc:
                    y = _draw_paragraphs(c, y, [desc], ps=ps)

                if formal and reqs:
                    english = formal.language == 'en'
                    records = []
                    for req in reqs:
                        details = [req.get('description') or '']
                        for label, key in ((('Configuration' if english else 'Configuración'), 'configuration'),
                                           (('Flow' if english else 'Flujo'), 'usageFlow'),
                                           (('Commercial reference' if english else 'Referencia comercial'), 'linked_item_ids')):
                            if req.get(key):
                                details.append(f"**{label}:** {req[key]}")
                        records.append([req.get('flowKey', ''), f"**{req.get('title', '')}**", '\n\n'.join(details)])
                    y = _draw_table(c, y,
                                    ['ID', 'Requirement', 'Description'] if english else ['ID', 'Requerimiento', 'Descripción'],
                                    records, ps=ps, col_widths=[0.18, 0.30, 0.52])
                    continue

                if reqs:
                    records = []
                    for req in reqs:
                        details = [req.get('description') or '']
                        for label, key in (('Config:', 'configuration'), ('Flujo:', 'usageFlow')):
                            if req.get(key):
                                details.append(f"**{label}** {req[key]}")
                        records.append(dict(req, description='\n\n'.join(filter(None, details))))
                    y = _draw_requirements_table(c, y, records, ps)

        # ── 7. API ────────────────────────────────────────────
        api_sum = (data.get('apiSummary') or '').strip()
        api_dom = [
            d for d in (data.get('apiDomains') or [])
            if isinstance(d, dict) and _row_any(d, ('domain', 'summary'))
        ]
        if api_sum or api_dom:
            y = next_section('API')
            if api_sum:
                y = _draw_paragraphs(c, y, [api_sum], ps=ps)
            if api_dom:
                y -= 8
                headers = ['Dominio', 'Descripci\u00f3n']
                rows = [
                    [_safe(d, 'domain') or '\u2014', _safe(d, 'summary') or '']
                    for d in api_dom
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.24, 0.76])

        # ── 8. Integraciones ──────────────────────────────────
        integ = data.get('integrations') if isinstance(data.get('integrations'), dict) else {}
        notes = (integ.get('notes') or '').strip()
        inc = [
            r for r in (integ.get('included') or [])
            if isinstance(r, dict) and _row_any(
                r, ('service', 'provider', 'connection', 'dataExchange', 'accountOwner')
            )
        ]
        exc = [
            r for r in (integ.get('excluded') or [])
            if isinstance(r, dict) and _row_any(r, ('service', 'reason', 'availability'))
        ]
        if inc or exc or notes:
            y = next_section('Integraciones')
            if inc:
                y = _draw_subtitle(c, y, 'Incluidas', ps=ps)
                headers = ['Servicio', 'Proveedor', 'Conexi\u00f3n', 'Datos']
                rows = []
                for r in inc:
                    provider = _safe(r, 'provider') or ''
                    owner = _safe(r, 'accountOwner')
                    if owner:
                        provider = f'{provider} *{owner}*'.strip()
                    rows.append([
                        _safe(r, 'service') or '\u2014',
                        provider,
                        _safe(r, 'connection') or '',
                        _safe(r, 'dataExchange') or '',
                    ])
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.20, 0.20, 0.22, 0.38])
            if exc:
                y -= 8
                y = _draw_subtitle(c, y, 'Excluidas', ps=ps)
                headers = ['Servicio', 'Raz\u00f3n', 'Disponibilidad']
                rows = [
                    [
                        _safe(r, 'service') or '\u2014',
                        _safe(r, 'reason') or '',
                        _safe(r, 'availability') or '',
                    ]
                    for r in exc
                ]
                if formal:
                    headers, rows = headers[:2], [row[:2] for row in rows]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.3, 0.7] if formal else [0.24, 0.46, 0.30])
            if notes:
                y -= 8
                bullets = [b.strip() for b in notes.splitlines() if b.strip()]
                if bullets:
                    y = _draw_bullet_list(c, y, bullets, ps=ps)

        # ── 9. Ambientes ──────────────────────────────────────
        env_note = (data.get('environmentsNote') or '').strip()
        envs = [
            r for r in (data.get('environments') or [])
            if isinstance(r, dict) and _row_any(
                r, ('name', 'purpose', 'url', 'database', 'whoAccesses')
            )
        ]
        if env_note or envs:
            y = next_section('Ambientes')
            if env_note:
                y = _draw_paragraphs(c, y, [env_note], ps=ps)
            if envs:
                y -= 8
                headers = ['Nombre', 'Prop\u00f3sito', 'URL', 'BD', 'Acceso']
                rows = [
                    [
                        _safe(r, 'name') or '\u2014',
                        _safe(r, 'purpose') or '',
                        _safe(r, 'url') or '',
                        _safe(r, 'database') or '',
                        _safe(r, 'whoAccesses') or '',
                    ]
                    for r in envs
                ]
                if formal:
                    headers, rows = [headers[i] for i in (0, 1, 4)], [[row[i] for i in (0, 1, 4)] for row in rows]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.22, 0.5, 0.28] if formal else [0.13, 0.24, 0.23, 0.22, 0.18])

        # ── 10. Seguridad ─────────────────────────────────────
        sec_rows = [
            r for r in (data.get('security') or [])
            if isinstance(r, dict) and _row_any(r, ('aspect', 'implementation'))
        ]
        if sec_rows:
            y = next_section('Seguridad')
            headers = ['Aspecto', 'Implementaci\u00f3n']
            rows = [
                [_safe(r, 'aspect') or '\u2014', _safe(r, 'implementation') or '']
                for r in sec_rows
            ]
            y = _draw_table(c, y, headers, rows, ps=ps,
                            col_widths=[0.24, 0.76])

        # ── 11. Rendimiento ───────────────────────────────────
        pq = data.get('performanceQuality') if isinstance(data.get('performanceQuality'), dict) else {}
        metrics = [
            m for m in (pq.get('metrics') or [])
            if isinstance(m, dict) and _row_any(m, ('metric', 'target', 'howMeasured'))
        ]
        practices = [
            p for p in (pq.get('practices') or [])
            if isinstance(p, dict) and _row_any(p, ('strategy', 'description'))
        ]
        if metrics or practices:
            y = next_section('Rendimiento')
            if metrics:
                headers = ['M\u00e9trica', 'Objetivo', 'Medici\u00f3n']
                rows = [
                    [
                        _safe(m, 'metric') or '\u2014',
                        _safe(m, 'target') or '',
                        _safe(m, 'howMeasured') or '',
                    ]
                    for m in metrics
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.28, 0.30, 0.42],
                                aligns=['left', 'center', 'left'])
            if practices:
                y -= 8
                y = _draw_subtitle(c, y, 'Pr\u00e1cticas', ps=ps)
                headers = ['Estrategia', 'Descripci\u00f3n']
                rows = [
                    [_safe(p, 'strategy') or '\u2014', _safe(p, 'description') or '']
                    for p in practices
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.30, 0.70])

        # ── 12. Backups ───────────────────────────────────────
        bk = (data.get('backupsNote') or '').strip()
        if bk:
            y = next_section('Backups')
            y = _draw_paragraphs(c, y, [bk], ps=ps)

        # ── 13. Calidad ───────────────────────────────────────
        qual = data.get('quality') if isinstance(data.get('quality'), dict) else {}
        dims = [
            x for x in (qual.get('dimensions') or [])
            if isinstance(x, dict) and _row_any(x, ('dimension', 'evaluates', 'standard'))
        ]
        tests = [
            x for x in (qual.get('testTypes') or [])
            if isinstance(x, dict) and _row_any(x, ('type', 'validates', 'tool', 'whenRun'))
        ]
        cf = (qual.get('criticalFlowsNote') or '').strip()
        if dims or tests or cf:
            y = next_section('Calidad')
            if dims:
                headers = ['Dimensi\u00f3n', 'Eval\u00faa', 'Est\u00e1ndar']
                rows = [
                    [
                        _safe(x, 'dimension') or '\u2014',
                        _safe(x, 'evaluates') or '',
                        _safe(x, 'standard') or '',
                    ]
                    for x in dims
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.22, 0.40, 0.38])
            if tests:
                y -= 8
                y = _draw_subtitle(c, y, 'Tipos de prueba', ps=ps)
                headers = ['Tipo', 'Valida', 'Herramienta', 'Cu\u00e1ndo']
                rows = [
                    [
                        _safe(x, 'type') or '\u2014',
                        _safe(x, 'validates') or '',
                        _safe(x, 'tool') or '',
                        _safe(x, 'whenRun') or '',
                    ]
                    for x in tests
                ]
                y = _draw_table(c, y, headers, rows, ps=ps,
                                col_widths=[0.14, 0.34, 0.24, 0.28])
            if cf:
                y -= 8
                y = _draw_subtitle(c, y, 'Flujos cr\u00edticos', ps=ps)
                y = _draw_paragraphs(c, y, [cf], ps=ps)

        # ── 14. Decisiones ────────────────────────────────────
        decisions = [
            r for r in (data.get('decisions') or [])
            if isinstance(r, dict) and _row_any(r, ('decision', 'alternative', 'reason'))
        ]
        if decisions:
            y = next_section('Decisiones')
            headers = ['Decisi\u00f3n', 'Alternativa', 'Raz\u00f3n']
            rows = [
                [
                    _safe(r, 'decision') or '\u2014',
                    _safe(r, 'alternative') or '',
                    _safe(r, 'reason') or '',
                ]
                for r in decisions
            ]
            y = _draw_table(c, y, headers, rows, ps=ps,
                            col_widths=[0.30, 0.26, 0.44])

        # ── Footer note ──────────────────────────────────────
        y -= 20
        y = _check_y(c, y, ps, need=24)
        c.setFont(_font('regular'), 8)
        c.setFillColor(GRAY_500)
        c.drawCentredString(
            PAGE_W / 2,
            y,
            formal.identity_lines[-1] if formal else f'Fecha de creaci\u00f3n del documento: {date_str}',
        )
        y -= 16
        c.drawCentredString(
            PAGE_W / 2,
            y,
            formal.reference if formal else 'Condiciones de soporte seg\u00fan propuesta comercial.',
        )

        _draw_footer(c, ps['num'], client_name=ps['client'])
        c.save()
        content_bytes = buf.getvalue()
        buf.close()

        # ── Pass B: Title page + TOC (pages 1-2) ─────────────
        buf2 = io.BytesIO()
        c2 = canvas.Canvas(buf2, pagesize=A4)
        ps2 = {'num': 1, 'client': proposal.client_name, 'formal': formal,
              '_pdf_lang': getattr(proposal, 'language', 'es') or 'es'}
        _draw_decorative_title_page(
            c2,
            formal.title.upper() if formal else 'DETALLE T\u00c9CNICO',
            proposal.client_name or 'Cliente',
            date_str,
            ps2,
        )
        link_areas = []
        _draw_toc_page(c2, toc_entries, ps2, link_areas=link_areas)
        c2.save()
        prefix_bytes = buf2.getvalue()
        buf2.close()
        content_start = formal.content_start if formal else _content_start
        if ps2['num'] != content_start:
            return generate_technical_document_pdf(
                proposal, selected_modules=selected_modules,
                formal=formal.with_content_start(ps2['num']) if formal else None,
                included_sections=included_sections, _content_start=ps2['num'],
            )

        final_pdf = merge_with_covers(
            content_bytes,
            cover_path=COVER_TECHNICAL_PDF,
            prepend_bytes=prefix_bytes,
        )

        cover_offset = 1 if (COVER_TECHNICAL_PDF.exists() or COVER_PDF.exists()) else 0
        return _apply_toc_links(final_pdf, link_areas, cover_offset)
    except Exception:
        logger.exception('Technical PDF failed for proposal %s', proposal.uuid)
        return None
