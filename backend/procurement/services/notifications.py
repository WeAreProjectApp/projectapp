"""Durable eligibility records and per-recipient outbox, shared by all channels."""
from datetime import timedelta
from smtplib import SMTPException, SMTPServerDisconnected

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from content.services.email_delivery_service import DeliveryClassification, EmailDeliveryGateway
from procurement.filters import apply_filters
from procurement.models import Alert, Delivery, Notification, Opportunity, Settings
from procurement.serializers import OpportunityListSerializer


FILTER_LABELS = {
    'search': 'Texto', 'keywords': 'Palabras clave (alternativas)', 'unspsc_codes': 'Códigos UNSPSC (alternativas)',
    'entity_names': 'Entidades', 'departments': 'Departamentos de la entidad', 'methods': 'Modalidades',
    'contract_types': 'Tipos de contrato', 'statuses': 'Estados SECOP', 'min_budget': 'Presupuesto mínimo COP',
    'max_budget': 'Presupuesto máximo COP', 'published_from': 'Publicado desde', 'published_to': 'Publicado hasta',
    'closing_from': 'Cierre desde', 'closing_to': 'Cierre hasta', 'is_open': 'Sólo procesos abiertos',
}


def filter_labels(filters):
    return [{'label': FILTER_LABELS[key], 'value': ', '.join(value) if isinstance(value, list)
             else ('Sí' if value is True else 'No' if value is False else str(value))}
            for key, value in filters.items()]


def evaluate_opportunities(ids, alert_id=None):
    alerts = Alert.objects.filter(is_active=True)
    if alert_id:
        alerts = alerts.filter(pk=alert_id)
    for alert in alerts.iterator(chunk_size=50):
        matches = apply_filters(Opportunity.objects.filter(pk__in=ids), {**alert.filters, 'is_open': True})
        rows = [Notification(alert=alert, opportunity_id=pk, recipient=recipient, filters_snapshot=alert.filters)
                for pk in matches.values_list('pk', flat=True) for recipient in alert.recipients]
        Notification.objects.bulk_create(rows, ignore_conflicts=True, batch_size=250)
        Notification.objects.filter(alert=alert, opportunity_id__in=[row.opportunity_id for row in rows],
            recipient__in=alert.recipients, status='skipped').update(status='pending', delivery=None)
    from procurement.tasks import flush_notifications
    transaction.on_commit(lambda: flush_notifications('immediate'))


def eligible_ids(rows, frequency):
    """One match query per alert rather than one query per recipient/process row."""
    groups = {}
    for row in rows:
        alert = row.alert
        if alert.is_active and alert.frequency == frequency and row.recipient in alert.recipients:
            groups.setdefault(alert.pk, {'alert': alert, 'rows': []})['rows'].append(row)
    result = set()
    for group in groups.values():
        candidates = group['rows']
        ids = apply_filters(Opportunity.objects.filter(pk__in={row.opportunity_id for row in candidates}),
                            {**group['alert'].filters, 'is_open': True}).values_list('pk', flat=True)
        matches = set(ids)
        result.update(row.pk for row in candidates if row.opportunity_id in matches)
    return result


@transaction.atomic
def prepare_delivery(frequency, cutoff=None):
    # A small transaction claims rows; SMTP never holds database row locks.
    pending = Notification.objects.filter(status='pending', delivery__isnull=True)
    if cutoff is not None:
        pending = pending.filter(created_at__lte=cutoff)
    first = pending.filter(
                                        alert__frequency=frequency, alert__is_active=True).order_by('pk').first()
    if first is None:
        return None
    selected = pending.filter(recipient=first.recipient, alert__frequency=frequency)
    opportunity_ids = list(selected.order_by('opportunity_id').values_list('opportunity_id', flat=True).distinct()[:100])
    if frequency == 'immediate':
        opportunity_ids = opportunity_ids[:1]
    # Include every matching alert for the selected processes in the same digest.
    rows = list(selected.select_for_update().filter(opportunity_id__in=opportunity_ids)
                .select_related('alert', 'opportunity').defer('opportunity__description', 'opportunity__source_data').order_by('pk'))
    matches = eligible_ids(rows, frequency)
    valid = [row for row in rows if row.pk in matches]
    invalid_ids = [row.pk for row in rows if row.pk not in matches]
    Notification.objects.filter(pk__in=invalid_ids).update(status='skipped')
    if not valid:
        return False
    delivery = Delivery.objects.create(recipient=first.recipient, frequency=frequency)
    Notification.objects.filter(pk__in=[row.pk for row in valid]).update(delivery=delivery)
    return delivery.pk


def send_delivery(delivery_id):
    if not Settings.current().email_enabled:
        return
    claimed = Delivery.objects.filter(pk=delivery_id, status='pending').update(status='sending', attempted_at=timezone.now())
    if not claimed:
        return
    delivery = Delivery.objects.get(pk=delivery_id)
    delivery.attempts += 1
    rows = list(delivery.notifications.select_related('alert', 'opportunity').defer('opportunity__description', 'opportunity__source_data'))
    matches = eligible_ids(rows, delivery.frequency)
    valid = [row for row in rows if row.pk in matches]
    invalid = set(row.pk for row in rows) - set(row.pk for row in valid)
    Notification.objects.filter(pk__in=invalid).update(status='skipped')
    if not valid:
        delivery.status = 'skipped'
        delivery.save()
        return
    grouped = {}
    for row in valid:
        item = grouped.setdefault(row.opportunity_id, {
            **dict(OpportunityListSerializer(row.opportunity).data), 'matched_alerts': [],
        })
        effective_filters = {**row.alert.filters, 'is_open': True}
        item['matched_alerts'].append({'name': row.alert.name, 'filters': effective_filters,
                                     'filter_labels': filter_labels(effective_filters)})
    items = list(grouped.values())
    from procurement.services.source import BOGOTA
    from content.utils import format_cop_email
    for item in items:
        opportunity = next(row.opportunity for row in valid if row.opportunity_id == item['id'])
        item['closing_label'] = opportunity.closing_at.astimezone(BOGOTA).strftime('%d/%m/%Y %H:%M Bogotá') if opportunity.closing_at else 'Sin informar'
        item['budget_label'] = format_cop_email(opportunity.budget) if opportunity.budget is not None else 'Sin informar'
    delivery.snapshot = {'opportunities': items, 'recipient': delivery.recipient}
    delivery.opportunity_count = len(items)
    delivery.save(update_fields=['snapshot', 'opportunity_count', 'attempts'])
    period = dict(Alert.FREQUENCIES)[delivery.frequency]
    subject = f'[SECOP · ProjectApp] {len(items)} oportunidad(es) · {period}'
    context = {'items': items, 'subject': subject}
    message = EmailMultiAlternatives(subject, render_to_string('procurement/alert.txt', context),
                                    django_settings.DEFAULT_FROM_EMAIL, [delivery.recipient],
                                    connection=EmailDeliveryGateway.bounded_connection(timeout_seconds=20))
    message.attach_alternative(render_to_string('procurement/alert.html', context), 'text/html')
    try:
        result = EmailDeliveryGateway.send(message, template_key='procurement_alert',
                                           classification=DeliveryClassification.INTERNAL)
        if result != 1:
            raise SMTPException('No se confirmó la entrega.')
        delivery.status = 'sent'
        delivery.error = ''
        delivery.sent_at = timezone.now()
        Notification.objects.filter(pk__in=[row.pk for row in valid]).update(status='sent')
    except (TimeoutError, SMTPServerDisconnected):
        delivery.status = 'uncertain'
        delivery.error = 'El servidor no confirmó el resultado. Verifica el correo antes de reintentar: podría haberse enviado.'
    except Exception:
        delivery.status = 'failed'
        delivery.error = 'No fue posible entregar el correo. La entrega queda disponible para reintento.'
    delivery.save()


def flush(frequency):
    if not Settings.current().email_enabled:
        return
    # Recover crashed senders without automatically repeating a possibly accepted SMTP envelope.
    Delivery.objects.filter(status='sending', attempted_at__lt=timezone.now()-timedelta(minutes=10)).update(
        status='uncertain', error='Envío interrumpido. Verifica el buzón antes de reintentar.')
    from procurement.models import ScheduleSlot
    cutoff = None
    if frequency != 'immediate':
        from procurement.services.source import BOGOTA
        slot = ScheduleSlot.objects.filter(kind=frequency, day=timezone.now().astimezone(BOGOTA).date()).first()
        if slot is None:
            return
        cutoff = slot.created_at
    for _ in range(20):
        delivery_id = prepare_delivery(frequency, cutoff)
        if delivery_id is None:
            break
        if delivery_id:
            from procurement.tasks import deliver
            transaction.on_commit(lambda pk=delivery_id: deliver(pk))


def retry_delivery(pk):
    if not Delivery.objects.filter(pk=pk, status__in=['failed', 'uncertain']).update(status='pending'):
        raise ValidationError('Sólo se reintentan entregas fallidas o de resultado incierto.')
    from procurement.tasks import deliver
    transaction.on_commit(lambda: deliver(pk))
    return {'id': pk, 'status': 'pending'}
