"""Pure monetary VAT calculations; totals remain the accounting source of truth."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')
MAX_MONEY = Decimal('999999999999.99')


def quantize_money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def vat_breakdown(amount, rate, mode='vat_included'):
    """Return (base, VAT, total), preserving an included total exactly."""
    amount = quantize_money(amount)
    if mode not in {'before_vat', 'vat_included'}:
        raise ValueError('Selecciona un modo de importe válido.')
    if amount < 0 or amount > MAX_MONEY:
        raise ValueError('El importe está fuera del rango permitido.')
    if rate is None:
        if mode == 'before_vat':
            raise ValueError('Define el porcentaje de IVA antes de introducir la base.')
        return None, None, amount
    rate = Decimal(rate)
    if not rate.is_finite() or not 0 <= rate <= 100:
        raise ValueError('El porcentaje de IVA debe estar entre 0 y 100.')
    if mode == 'before_vat':
        base = amount
        vat = quantize_money(base * rate / 100)
        total = base + vat
    else:
        total = amount
        base = quantize_money(total / (1 + rate / 100))
        vat = total - base
    if total > MAX_MONEY:
        raise ValueError('El total con IVA supera el importe máximo permitido.')
    return base, vat, total
