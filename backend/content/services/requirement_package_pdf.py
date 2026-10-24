"""Public package table; no internal size prices or exchange context."""
from decimal import Decimal


def render_requirement_packages(c, y, data, currency, enabled, ps):
    # Import lazily: this renderer shares the proposal's pagination engine.
    from content.services.proposal_pdf_service import (
        _draw_paragraphs,
        _draw_subtitle,
        _draw_table,
        _format_currency,
        _tax_suffix,
    )
    english = (ps or {}).get('_pdf_lang') == 'en'
    if enabled:
        y = _draw_subtitle(c, y, data.get('packagesTitle', ''), ps=ps)
        y = _draw_paragraphs(c, y, [data.get('packagesIntro', '')], ps=ps)
        rows = []
        for pkg in data.get('packages', []):
            base = Decimal(str(pkg['referencePrice']))
            from content.services.requirement_package_service import amounts
            price = amounts(base, pkg.get('discountPercent', 0), currency)
            money = lambda value: _format_currency(float(value), currency)
            rows.append([
                '**' + pkg.get('name', '') + '**' + (' — ' + pkg['note'] if pkg.get('note') else ''),
                f"{pkg['xsCount']} XS / {pkg['sCount']} S / {pkg['mCount']} M",
                money(price['reference_price']),
                f"-{pkg.get('discountPercent', 0)}%",
                money(pkg.get('totalPrice', price['total_price'])),
            ])
        if rows:
            headers = ['Package', 'Allowances', 'Reference', 'Disc.', 'Total'] if english else [
                'Paquete', 'Cupos', 'Referencia', 'Dcto.', 'Total']
            headers[-1] += ' (' + _tax_suffix(currency).strip() + ')'
            y = _draw_table(c, y, headers, rows, ps=ps)
        for pkg in data.get('packages', []):
            savings = Decimal(str(pkg['referencePrice'])) - Decimal(str(pkg.get('totalPrice', 0)))
            saving_label = 'Savings' if english else 'Ahorro'
            y = _draw_paragraphs(c, y, [
                f"**{pkg.get('name', '')} — {saving_label}: {_format_currency(float(savings), currency)}.** "
                + pkg.get('terms', '')], ps=ps)
        y = _draw_paragraphs(c, y, [data.get('effortBadge', '')], ps=ps)
    if data.get('scopeTitle'):
        y = _draw_subtitle(c, y, data['scopeTitle'], ps=ps)
    return _draw_paragraphs(c, y, data.get('scopeParagraphs', []), ps=ps)
