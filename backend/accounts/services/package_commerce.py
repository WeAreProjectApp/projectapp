"""One-time package orders, paid capacity and append-only allowance movements."""
from calendar import monthrange
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models_requirement_packages import PackageMovement, PackageOrder, PackageProjectSettings
from accounts.services.package_common import check_version, mutate, notify_client, notify_team, owned
from content.models import HourPackage, HourPackageSettings
from content.services.requirement_package_service import package_terms, price_context, priced_package

SIZES = ('XS', 'S', 'M')


def project_settings(project):
    return PackageProjectSettings.objects.filter(project=project).first()


def settings_payload(project):
    row = project_settings(project)
    return {'nationality': row.nationality if row else 'COL', 'tax_rate': str(row.tax_rate if row else 19),
            'version': row.version if row else 0}


def update_settings(project_id, actor, data):
    def change(project):
        row, _ = PackageProjectSettings.objects.get_or_create(project=project)
        check_version(row, data['expected_version'])
        row.nationality, row.tax_rate, row.version = data['nationality'], data['tax_rate'], row.version + 1
        row.save()
        return settings_payload(project)
    return mutate(project_id, actor, 'settings', data, change, admin=True)


def quote(package, project, *, language='es', config=None, context=None, pricing_settings=None):
    config = config or settings_payload(project)
    pricing_settings = pricing_settings or HourPackageSettings.load()
    context = context or price_context(config['nationality'], pricing_settings)
    price = priced_package(package, settings=pricing_settings, context=context)
    subtotal = Decimal(price['total_price'])
    tax_rate = Decimal(config['tax_rate'])
    quantum = Decimal('1') if context[2] == 'COP' else Decimal('.01')
    tax = (subtotal * tax_rate / 100).quantize(quantum, rounding=ROUND_HALF_UP)
    result = {'package_id': package.pk, 'name': package.name_en if language == 'en' else package.name_es,
            'counts': {size: getattr(package, size.lower() + '_count') for size in SIZES},
            'validity_months': package.validity_months, 'discount_percent': package.discount_percent,
            'reference_price': price['reference_price'], 'subtotal': str(subtotal),
            'tax_rate': str(tax_rate), 'tax': str(tax), 'total': str(subtotal + tax),
            'currency': context[2], 'terms': package_terms(language, package.validity_months),
            'online_available': context[2] == 'COP', 'language': language}
    from content.services.requirement_calculator import digest
    result['quote_digest'] = digest(result)
    return result


def catalog(project, *, language='es'):
    config = settings_payload(project)
    rows = HourPackage.objects.filter(is_active=True, pricing_model='requirements', nationality=config['nationality'])
    pricing_settings = HourPackageSettings.load()
    context = price_context(config['nationality'], pricing_settings)
    return [quote(row, project, language=language, config=config, context=context,
                  pricing_settings=pricing_settings) for row in rows]


def order_payload(order):
    return {'id': str(order.pk), 'project_id': order.project_id, 'snapshot': order.snapshot,
            'method': order.method, 'status': order.status, 'checkout_url': order.checkout_url,
            'currency': order.currency, 'subtotal': str(order.subtotal), 'tax_rate': str(order.tax_rate),
            'total': str(order.total), 'paid_at': order.paid_at.isoformat() if order.paid_at else None,
            'expires_at': order.expires_at.isoformat() if order.expires_at else None,
            'payment_reference': order.payment_reference, 'created_at': order.created_at.isoformat()}


def balances(project):
    rows = PackageMovement.objects.filter(order__project=project, order__client_id=project.client_id,
        order__status='paid', order__expires_at__gt=timezone.now()).values('size').annotate(total=Sum('quantity'))
    result = {size: 0 for size in SIZES}
    result.update({row['size']: row['total'] for row in rows})
    return result


def eligible_order(project, size):
    return (PackageOrder.objects.filter(project=project, client_id=project.client_id, status='paid',
            expires_at__gt=timezone.now(), movements__size=size)
        .annotate(available=Sum('movements__quantity')).filter(available__gt=0)
        .order_by('expires_at', 'created_at', 'pk').first())


def create_order(project_id, actor, data):
    def change(project):
        market = settings_payload(project)['nationality']
        package = HourPackage.objects.filter(pk=data['package_id'], is_active=True,
            pricing_model='requirements', nationality=market).first()
        if package is None:
            raise ValidationError('El paquete no está disponible en el catálogo del proyecto.')
        snapshot = quote(package, project, language=data['language'])
        if snapshot['quote_digest'] != data['quote_digest']:
            from accounts.services.delivery_access import DeliveryConflict
            raise DeliveryConflict('El catálogo o sus condiciones cambiaron. Revisa la oferta antes de comprar.')
        if not sum(snapshot['counts'].values()):
            raise ValidationError('El paquete no tiene cupos configurados.')
        if data['method'] == 'online' and not snapshot['online_available']:
            raise ValidationError('Para esta moneda solicita pago por otro medio.')
        order = PackageOrder.objects.create(project=project, client=project.client, package=package,
            snapshot=snapshot, currency=snapshot['currency'], subtotal=snapshot['subtotal'],
            tax_rate=snapshot['tax_rate'], total=snapshot['total'], method=data['method'], recorded_by=actor)
        notify_team(project, 'Nueva solicitud de compra de paquete')
        return order_payload(order)
    return mutate(project_id, actor, 'create_order', data, change)


def _expiry(paid_at, months):
    month = paid_at.month - 1 + months
    year, month = paid_at.year + month // 12, month % 12 + 1
    if year > 9999:
        raise ValidationError('La vigencia del paquete excede el límite de fechas.')
    return paid_at.replace(year=year, month=month, day=min(paid_at.day, monthrange(year, month)[1]))


def activate(order, *, actor, paid_at, reference):
    if order.status == 'paid':
        return
    if order.status == 'cancelled':
        raise ValidationError('La compra está anulada.')
    order.status, order.paid_at = 'paid', paid_at
    order.payment_reference = reference
    order.expires_at = _expiry(paid_at, order.snapshot['validity_months'])
    order.save()
    PackageMovement.objects.bulk_create([PackageMovement(order=order, size=size, quantity=count,
        kind='credit', actor=actor) for size, count in order.snapshot['counts'].items() if count])
    notify_client(order.project, 'Tu paquete de requerimientos está disponible')


def confirm_external(project_id, actor, order_id, data):
    def change(project):
        order = owned(PackageOrder.objects.select_for_update(), project, pk=order_id)
        if order.method != 'external':
            raise ValidationError('Los pagos en línea se confirman con la pasarela.')
        if order.status == 'paid':
            raise ValidationError('El pago ya está confirmado. Consulta su registro.')
        activate(order, actor=actor, paid_at=data['paid_at'], reference=data['payment_reference'])
        return order_payload(order)
    return mutate(project_id, actor, f'external:{order_id}', data, change, admin=True)


def checkout(project_id, actor, order_id, data):
    """Persist the link before returning it; retries reuse the same provider link."""
    def change(project):
        from accounts.services import wompi
        order = owned(PackageOrder.objects.select_for_update(), project, pk=order_id)
        if order.method != 'online' or order.currency != 'COP' or order.status == 'paid':
            raise ValidationError('Esta compra no admite iniciar un pago en línea.')
        if order.checkout_url:
            return order_payload(order)
        if not settings.WOMPI_PRIVATE_KEY:
            raise ValidationError('El pago en línea no está disponible; solicita pago por otro medio.')
        language = 'en-us' if order.snapshot['language'] == 'en' else 'es-co'
        redirect = f'{settings.FRONTEND_URL.rstrip("/")}/{language}/platform/projects/{project.pk}/packages?order={order.pk}'
        try:
            response = requests.post(f'{settings.WOMPI_API_URL}/payment_links', headers=wompi._get_headers(),
                json={'name': order.snapshot['name'][:100], 'description': f'Paquete {order.pk}',
                      'single_use': True, 'collect_shipping': False, 'currency': 'COP',
                      'amount_in_cents': int(order.total * 100), 'redirect_url': redirect}, timeout=15)
            response.raise_for_status()
            payload = response.json()
            link = payload.get('data') if isinstance(payload, dict) else None
            link_id = link.get('id') if isinstance(link, dict) else None
        except (requests.RequestException, ValueError):
            raise ValidationError('No se pudo preparar el pago. La compra sigue pendiente.') from None
        if not isinstance(link_id, str) or not link_id or len(link_id) > 100:
            raise ValidationError('La pasarela no devolvió un enlace válido.')
        order.payment_link_id = link_id
        order.checkout_url = f'https://checkout.wompi.co/l/{link_id}'
        order.status = 'processing'
        order.save(update_fields=['payment_link_id', 'checkout_url', 'status'])
        return order_payload(order)
    return mutate(project_id, actor, f'checkout:{order_id}', data, change)


def apply_transaction(project_id, actor, order_id, data, transaction_data, *, trusted_webhook=False):
    if trusted_webhook and not PackageOrder.objects.filter(
        pk=order_id, project_id=project_id, recorded_by=actor,
    ).exists():
        raise PermissionDenied('El actor del pago no corresponde a la compra registrada.')

    def change(project):
        order = owned(PackageOrder.objects.select_for_update(), project, pk=order_id)
        tx = transaction_data
        if (order.method != 'online' or order.currency != 'COP' or not order.payment_link_id
            or tx.get('id') != data['transaction_id'] or tx.get('payment_link_id') != order.payment_link_id
            or type(tx.get('amount_in_cents')) is not int or tx['amount_in_cents'] != order.total * 100
            or tx.get('currency') != order.currency):
            raise ValidationError('La transacción no corresponde a esta compra.')
        if order.status == 'paid':
            if order.transaction_id != tx['id']:
                raise ValidationError('La compra ya tiene otro pago acreditado.')
            return order_payload(order)
        if tx.get('status') == 'APPROVED':
            if PackageOrder.objects.filter(transaction_id=tx['id']).exclude(pk=order.pk).exists():
                raise ValidationError('La transacción ya fue acreditada.')
            try:
                paid_at = datetime.fromisoformat(tx.get('finalized_at') or tx['created_at'])
            except (KeyError, ValueError, TypeError):
                raise ValidationError('La transacción no tiene una fecha de pago válida.') from None
            if not timezone.is_aware(paid_at) or paid_at > timezone.now():
                raise ValidationError('La fecha del pago no es válida.')
            order.transaction_id = tx['id']
            activate(order, actor=actor, paid_at=paid_at, reference=tx['id'])
        elif tx.get('status') in ('DECLINED', 'ERROR', 'VOIDED'):
            order.status = 'failed'
            order.save(update_fields=['status'])
        return order_payload(order)
    return mutate(project_id, actor, f'transaction:{order_id}', data, change,
                  allow_inactive_settlement=trusted_webhook, trusted_settlement=trusted_webhook)


def reverse_movement(project_id, actor, movement_id, data):
    def change(project):
        row = PackageMovement.objects.select_related('order').filter(pk=movement_id, order__project=project,
            order__client_id=project.client_id, kind='debit').first()
        if row is None:
            raise NotFound('Consumo no encontrado.')
        if PackageMovement.objects.filter(reverses=row).exists():
            raise ValidationError('El consumo ya fue revertido.')
        reversal = PackageMovement.objects.create(order=row.order, size=row.size, quantity=1,
            kind='reversal', reverses=row, reason=data['reason'], actor=actor)
        notify_client(project, 'Se registró una corrección en tus cupos')
        return {'id': reversal.pk, 'reverses_id': row.pk, 'balances': balances(project)}
    return mutate(project_id, actor, f'reverse:{movement_id}', data, change, admin=True)
