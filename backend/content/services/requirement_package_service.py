"""Requirement package prices. Unit values and market factors stay staff-only."""
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

SIZES = ('XS', 'S', 'M')
DEFAULT_PACKAGES = [
    {'name_es': 'Paquete Ágil', 'name_en': 'Agile Pack', 'xs_count': 30, 's_count': 0,
         'm_count': 0, 'discount_percent': 10, 'order': 1},
    {'name_es': 'Paquete Pro', 'name_en': 'Pro Pack', 'xs_count': 30, 's_count': 20,
         'm_count': 0, 'discount_percent': 15, 'order': 2},
    {'name_es': 'Paquete Premium', 'name_en': 'Premium Pack', 'xs_count': 30, 's_count': 20,
         'm_count': 10, 'discount_percent': 25, 'order': 3},
]


def package_terms(language='es', validity=12):
    if language == 'en':
        return (
            f'One purchase, valid for {validity} months from payment to request and validate work. '
            'Describe the change, agree on the expected result, and confirm its size before scheduling. '
            'Approved requests within an already purchased package do not need a separate individual quote. '
            'Each request uses one allowance of its own size; sizes cannot be exchanged. '
            'L/XL work requires separate discovery and a quote. Warranty corrections do not use allowances. '
            'Delivery dates are agreed separately; unused allowances expire. No automatic renewal.'
        )
    return (
        f'Compra única, con {validity} meses desde el pago para solicitar y validar requerimientos. '
        'Describe el cambio, acuerda el resultado esperado y confirma la talla antes de programarlo. '
        'Los requerimientos aprobados dentro de un paquete ya contratado no necesitan una cotización individual. '
        'Cada requerimiento usa un cupo de su propia talla, sin intercambios. '
        'Los alcances L/XL requieren levantamiento y cotización independientes. Las correcciones '
        'cubiertas por garantía no consumen cupos. La ejecución se agenda de común acuerdo; '
        'los cupos no usados vencen. Sin renovación automática.'
    )


def price_context(nationality, settings=None):
    from content.models import AccountingSettings, HourPackageSettings
    settings = settings or HourPackageSettings.load()
    if nationality == 'COL':
        return Decimal(1), Decimal(1), 'COP'
    rate = AccountingSettings.load().usd_exchange_rate
    if not rate or rate <= 0:
        raise ValidationError({'exchange_rate': 'Configura una tasa COP/USD mayor a cero en Contabilidad.'})
    factor = settings.foreign_multiplier if nationality == 'EXT' else settings.usa_multiplier
    return rate, factor, 'USD'


def amounts(reference, discount, currency):
    reference = Decimal(str(reference))
    net = reference * (Decimal(100) - Decimal(str(discount))) / 100
    quantum = Decimal(1) if currency == 'COP' else Decimal('.01')
    base = reference.quantize(quantum, rounding=ROUND_HALF_UP)
    total = net.quantize(quantum, rounding=ROUND_HALF_UP)
    return {'reference_price': str(base), 'total_price': str(total), 'savings': str(base - total)}


def priced_package(package, *, settings=None, context=None):
    from content.models import HourPackageSettings
    settings = settings or HourPackageSettings.load()
    rate, factor, currency = context or price_context(package.nationality, settings)
    reference = sum(getattr(package, f'{size.lower()}_count') * getattr(settings, f'{size.lower()}_price_cop')
                    for size in SIZES) / rate * factor
    return amounts(reference, package.discount_percent, currency)


def seed_requirement_packages(content, *, nationality, language):
    from content.models import HourPackage, HourPackageSettings
    seeded = deepcopy(content)
    settings = HourPackageSettings.load()
    context = price_context(nationality, settings)
    rows = HourPackage.objects.filter(pricing_model='requirements', nationality=nationality,
                                      is_active=True).order_by('order', 'pk')
    # An empty catalog means no packages on offer, never invented fallback capacity.
    seeded['pricingModel'] = 'requirements'
    seeded['currency'] = context[2]
    seeded['packages'] = []
    for pkg in rows:
        price = priced_package(pkg, settings=settings, context=context)
        seeded['packages'].append({
            'id': pkg.pk, 'name': pkg.name_en if language == 'en' else pkg.name_es,
            'note': pkg.note_en if language == 'en' else pkg.note_es,
            **({'text_formats': {'/note': pkg.text_formats['/note_' + language]}}
               if '/note_' + language in pkg.text_formats else {}),
            'xsCount': pkg.xs_count, 'sCount': pkg.s_count, 'mCount': pkg.m_count,
            'validityMonths': pkg.validity_months, 'discountPercent': pkg.discount_percent,
            'referencePrice': price['reference_price'], 'totalPrice': price['total_price'],
            'terms': package_terms(language, pkg.validity_months),
        })
    for key in ('hourlyRate', 'manualHourlyRate', 'manualPackageRates'):
        seeded.pop(key, None)
    return seeded


def freeze_proposal_packages(proposal):
    """Freeze the negotiated totals and private FX context before first issue."""
    for section in proposal.sections.filter(section_type='commercial_conditions'):
        data = section.content_json or {}
        if data.get('pricingModel') != 'requirements' or data.get('packagesFrozen'):
            continue
        if data.get('hourPackagesMode') != 'manual':
            data = seed_requirement_packages(data, nationality=proposal.nationality, language=proposal.language)
        rate, factor, _ = price_context(proposal.nationality)
        # Separate server-owned context survives legal form replacements.
        proposal.package_pricing_context = {'exchange_rate': format(rate.normalize(), 'f'), 'factor': format(factor.normalize(), 'f')}
        proposal.save(update_fields=['package_pricing_context'])
        data['packagesFrozen'] = True
        section.content_json = data
        section.save(update_fields=['content_json'])

    getattr(proposal, '_prefetched_objects_cache', {}).pop('sections', None)


def normalize_section(data, proposal, previous=None):
    """Validate manual commercial commitments and calculate all derived totals."""
    data = deepcopy(data)
    if data.get('pricingModel') != 'requirements':
        return data
    if previous is not None and previous.get('pricingModel') != 'requirements':
        if proposal.status != 'draft':
            raise ValidationError('Sólo un borrador puede adoptar los nuevos paquetes.')
        from content.services.proposal_service import (
            DEFAULT_SECTIONS,
            DEFAULT_SECTIONS_EN,
        )
        defaults = DEFAULT_SECTIONS_EN if proposal.language == 'en' else DEFAULT_SECTIONS
        template = next(row['content_json'] for row in defaults if row['section_type'] == 'commercial_conditions')
        for key in ('packagesTitle', 'packagesIntro', 'effortBadge', 'scopeParagraphs'):
            data[key] = deepcopy(template[key])
        data['packagesFrozen'] = False
    # Only issuance can freeze a new offer. A client cannot invent a frozen
    # automatic snapshot to bypass catalog pricing and validation.
    if data.get('packagesFrozen') and not (previous or {}).get('packagesFrozen'):
        data['packagesFrozen'] = False
    if data.get('packagesFrozen') and data.get('hourPackagesMode') != 'manual':
        data['packages'] = deepcopy((previous or {}).get('packages', []))
        data['currency'] = (previous or {}).get('currency', data.get('currency'))
    currency = 'COP' if proposal.nationality == 'COL' else 'USD'
    if data.get('hourPackagesMode') == 'manual':
        if data.get('manualCurrency', currency) != currency or data.get('currency', currency) != currency:
            raise ValidationError('La moneda manual no corresponde al mercado de la propuesta.')
        if not data.get('packages'):
            raise ValidationError('Agrega al menos un paquete.')
        for pkg in data['packages']:
            counts = [pkg.get(key, 0) for key in ('xsCount', 'sCount', 'mCount')]
            validity = pkg.get('validityMonths', 12)
            discount = pkg.get('discountPercent', 0)
            if any(type(n) is not int or n < 0 for n in counts) or not sum(counts):
                raise ValidationError('Los cupos deben ser enteros no negativos e incluir al menos uno.')
            if type(validity) is not int or validity < 1:
                raise ValidationError('La vigencia debe ser un número entero de meses mayor a cero.')
            try:
                reference = Decimal(str(pkg.get('referencePrice', 0)))
                discount = Decimal(str(discount))
                valid = reference.is_finite() and 0 < reference <= Decimal('999999999999.99') and discount.is_finite() and 0 <= discount < 100
            except (InvalidOperation, TypeError, ValueError):
                valid = False
            if not valid:
                raise ValidationError('Revisa el valor de referencia y el descuento (0 a 99 %).')
            price = amounts(reference, discount, currency)
            prior = next((p for p in (previous or {}).get('packages', [])
                          if pkg.get('id') is not None and p.get('id') == pkg.get('id')
                          and Decimal(str(p.get('referencePrice', 0))) == reference
                          and Decimal(str(p.get('discountPercent', 0))) == discount), None)
            if prior and 'totalPrice' in prior and (previous or {}).get('currency') == currency:
                price['total_price'] = prior['totalPrice']
            elif pkg.get('id') is not None:
                from content.models import HourPackage
                try:
                    package_id = int(str(pkg['id']))
                except (TypeError, ValueError):
                    raise ValidationError('La referencia del paquete debe ser un identificador entero.')
                catalog = HourPackage.objects.filter(pk=package_id, nationality=proposal.nationality,
                    pricing_model='requirements', is_active=True).first()
                if catalog and Decimal(str(catalog.discount_percent)) == discount:
                    current = priced_package(catalog)
                    if Decimal(current['reference_price']) == reference:
                        price['total_price'] = current['total_price']
            pkg['referencePrice'] = price['reference_price']
            pkg['totalPrice'] = price['total_price']
            pkg['terms'] = package_terms(proposal.language, validity)
        data['currency'] = currency
        if (previous or {}).get('packagesFrozen') and data['packages'] != (previous or {}).get('packages', []):
            # An explicit manual edit prepares a revision. Historical PDF bytes
            # stay unchanged; the next issuance freezes its own pricing context.
            data['packagesFrozen'] = False
    elif not data.get('packagesFrozen'):
        data = seed_requirement_packages(data, nationality=proposal.nationality, language=proposal.language)
    for key in ('hourlyRate', 'manualHourlyRate', 'manualPackageRates'):
        data.pop(key, None)
    return data
