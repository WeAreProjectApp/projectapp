"""Resolve hosting once for proposal PDFs and standalone service contracts."""

import re

from content.services.markdown_export import literal, table
from content.services.pdf_utils import _format_cop
from content.services.proposal_service import normalize_hosting_plan

DEFAULT_RENEWAL_NOTE = (
    'Renovaciones para cada año de renovación (a partir del segundo año): '
    'el costo se ajusta una vez al año tomando como referencia el porcentaje '
    'en que aumentó el SMLMV (Salario Mínimo Legal Mensual Vigente en Colombia) '
    'ese año, más un 8% fijo, aplicado sobre el costo del año anterior:\n\n'
    'Costo de renovación = Costo del año anterior × '
    '(1 + (% de aumento del SMLMV + 8%))\n\n'
    'Por ejemplo, si el SMLMV aumentó 5%, el incremento total sería '
    '5% + 8% = 13%. Si venías pagando $100.000 COP, el nuevo costo sería '
    '$113.000 COP (un aumento de $13.000).'
)
SERVICE_CONDITIONS_HEADING = '### Condiciones particulares del servicio'
SERVICE_CONDITIONS_END = 'Fin de las condiciones particulares del servicio.'


class ServiceConditionsError(ValueError):
    """The proposal cannot supply the economic terms of a service contract."""


def resolve_hosting_terms(proposal, hosting_plan, investment):
    """Preserve the rounding and historical tiers of the proposal PDF."""
    plan = normalize_hosting_plan(proposal, hosting_plan)
    percent = plan.get('hostingPercent', 0) or 0
    annual_reference = round(float(investment or 0) * percent / 100) if percent else 0
    monthly_base = round(annual_reference / 12)
    tiers = []
    for tier in plan.get('billingTiers') or []:
        discount = tier.get('discountPercent', 0) or 0
        months = tier.get('months', 1) or 1
        monthly_price = round(monthly_base * (100 - discount) / 100)
        tiers.append({**tier, 'months': months, 'discountPercent': discount,
                      'monthly_price': monthly_price, 'period_total': monthly_price * months})
    return {
        'plan': plan, 'annual_reference': annual_reference, 'tiers': tiers,
        'renewal_note': plan.get('renewalNote') or DEFAULT_RENEWAL_NOTE,
    }


def service_conditions_markdown(proposal):
    """Build the proposal-specific block without changing any saved sections."""
    investment = next((section for section in proposal.sections.all()
                       if section.section_type == 'investment' and section.is_enabled), None)
    hosting = (investment.content_json or {}).get('hostingPlan') if investment else {}
    terms = resolve_hosting_terms(proposal, hosting, proposal.total_investment)
    if terms['annual_reference'] <= 0 or not terms['tiers']:
        raise ServiceConditionsError('Completa la inversión y las condiciones de hosting antes de generar el contrato de servicio.')
    plan = terms['plan']
    currency = proposal.currency
    tax = '+ IVA' if currency == 'COP' else '+ Tax'
    parts = [SERVICE_CONDITIONS_HEADING, literal(plan.get('title') or 'Hosting, mantenimiento y soporte')]
    if plan.get('description'):
        parts.append(literal(plan['description']))
    specs = [[literal(spec.get('label', '')), literal(spec.get('value', ''))]
             for spec in plan.get('specs') or [] if spec.get('label') or spec.get('value')]
    if specs:
        parts.append(table(['Infraestructura', 'Capacidad incluida'], specs))
    parts.append(
        'EL CONTRATANTE elegirá una de las modalidades de pago anticipado que se '
        'detallan a continuación y comunicará por escrito su elección a EL CONTRATISTA '
        'antes del inicio del primer periodo de cobro. Los descuentos corresponden '
        'al pago anticipado del periodo completo; ninguna modalidad se considera '
        'seleccionada por su sola inclusión en este contrato.'
    )
    rows = []
    for tier in terms['tiers']:
        rows.append([
            literal(tier.get('label') or f'Cada {tier["months"]} meses'),
            f'{tier["discountPercent"]:g}%' if tier['discountPercent'] else 'Sin descuento',
            f'{_format_cop(tier["monthly_price"])} {currency} {tax}',
            f'{_format_cop(tier["period_total"])} {currency} {tax}',
        ])
    parts.append(table(['Modalidad', 'Descuento', 'Equivalente mensual', 'Total del periodo'], rows))
    if plan.get('coverageNote'):
        parts.extend(['**Cobertura**', literal(plan['coverageNote'])])
    if plan.get('freeMonthsVisible') and plan.get('freeMonthNote'):
        parts.extend(['**Cortesía**', literal(plan['freeMonthNote'])])
    parts.extend(['**Condiciones de renovación**', literal(terms['renewal_note']), SERVICE_CONDITIONS_END])
    return '\n\n'.join(parts)


def append_service_conditions(markdown, conditions):
    """Replace only a previously generated block, retaining custom prose."""
    pattern = re.escape(SERVICE_CONDITIONS_HEADING) + r'.*?' + re.escape(SERVICE_CONDITIONS_END)
    body = re.sub(pattern, '', markdown, flags=re.DOTALL).rstrip()
    return f'{body}\n\n{conditions}' if body else conditions
