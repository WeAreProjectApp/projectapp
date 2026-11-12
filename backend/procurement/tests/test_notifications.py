"""Durable outbox, scheduler, and bounded-delivery behavior coverage."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time
from procurement.models import Delivery, Notification, ScheduleSlot, Settings
from procurement.services.notifications import (
    eligible_ids,
    evaluate_opportunities,
    flush,
    prepare_delivery,
    send_delivery,
)

pytestmark = pytest.mark.django_db


def smtp_unavailable(*_args, **_kwargs):
    """Fail the external SMTP boundary deterministically."""
    raise RuntimeError('SMTP unavailable')


def smtp_forbidden(*_args, **_kwargs):
    """Fail if a scheduler path tries to contact the SMTP boundary."""
    raise AssertionError('SMTP must not run from flush')


def test_reactivated_alert_returns_skipped_notification_to_pending_without_duplicate(opportunity, alert, monkeypatch):
    """Falla si una oportunidad reabierta nunca vuelve al outbox o duplica el correo pendiente."""
    record = opportunity('REACTIVATE-1')
    configured_alert = alert()
    notification = Notification.objects.create(
        alert=configured_alert, opportunity=record, recipient='carlos@example.com', status='skipped',
    )
    monkeypatch.setattr('procurement.tasks.flush_notifications', lambda _frequency: None)

    evaluate_opportunities([record.pk])

    notification.refresh_from_db()
    assert (notification.status, notification.delivery_id) == ('pending', None)
    assert Notification.objects.filter(
        alert=configured_alert, opportunity=record, recipient='carlos@example.com',
    ).count() == 1


@freeze_time('2026-11-05 07:00:00')
def test_daily_delivery_only_claims_notifications_created_before_cutoff(opportunity, alert):
    """Falla si el resumen diario incluye una coincidencia llegada después de abrir su ventana."""
    record = opportunity('DAILY-BEFORE')
    later = opportunity('DAILY-AFTER')
    configured_alert = alert(frequency='daily')
    before = Notification.objects.create(alert=configured_alert, opportunity=record, recipient='carlos@example.com')
    after = Notification.objects.create(alert=configured_alert, opportunity=later, recipient='carlos@example.com')
    cutoff = timezone.now()
    Notification.objects.filter(pk=before.pk).update(created_at=cutoff-timedelta(minutes=1))
    Notification.objects.filter(pk=after.pk).update(created_at=cutoff+timedelta(minutes=1))
    ScheduleSlot.objects.create(kind='daily', day=cutoff.date(), created_at=cutoff)

    delivery_id = prepare_delivery('daily', cutoff)

    before.refresh_from_db()
    after.refresh_from_db()
    assert before.delivery_id == delivery_id
    assert (after.delivery_id, after.status) == (None, 'pending')


def test_delivery_groups_overlapping_alerts(opportunity, alert, monkeypatch):
    """Falla si alertas solapadas mandan dos entradas para el mismo proceso."""
    Settings.objects.update_or_create(pk=1, defaults={'email_enabled': True})
    record = opportunity('GROUPED-1')
    first = alert(name='Servicios', frequency='daily')
    second = alert(name='SECOP', frequency='daily')
    one = Notification.objects.create(alert=first, opportunity=record, recipient='carlos@example.com')
    two = Notification.objects.create(alert=second, opportunity=record, recipient='carlos@example.com')
    timeouts = []
    monkeypatch.setattr(
        'procurement.services.notifications.EmailDeliveryGateway.bounded_connection',
        lambda *, timeout_seconds: timeouts.append(timeout_seconds) or object(),
    )
    monkeypatch.setattr('procurement.services.notifications.EmailDeliveryGateway.send', lambda *_args, **_kwargs: 1)

    sent_id = prepare_delivery('daily')
    send_delivery(sent_id)
    sent = Delivery.objects.get(pk=sent_id)
    one.refresh_from_db()
    two.refresh_from_db()

    assert sent.status == 'sent'
    assert [entry['name'] for entry in sent.snapshot['opportunities'][0]['matched_alerts']] == ['Servicios', 'SECOP']
    assert (one.status, two.status) == ('sent', 'sent')
    assert timeouts == [20]


def test_smtp_failure_keeps_notification_pending(opportunity, alert, monkeypatch):
    """Falla si una entrega SMTP fallida queda acreditada como enviada."""
    Settings.objects.update_or_create(pk=1, defaults={'email_enabled': True})
    record = opportunity('FAILED-1')
    configured_alert = alert(frequency='daily')
    notification = Notification.objects.create(
        alert=configured_alert, opportunity=record, recipient='carlos@example.com',
    )
    monkeypatch.setattr(
        'procurement.services.notifications.EmailDeliveryGateway.bounded_connection',
        lambda *, timeout_seconds: object(),
    )
    monkeypatch.setattr('procurement.services.notifications.EmailDeliveryGateway.send', smtp_unavailable)

    delivery_id = prepare_delivery('daily')
    send_delivery(delivery_id)
    delivery = Delivery.objects.get(pk=delivery_id)
    notification.refresh_from_db()

    assert (delivery.status, notification.status) == ('failed', 'pending')


@pytest.mark.parametrize('amount', [1, 50, 100])
def test_eligibility_query_count_stays_constant_for_one_alert(opportunity, alert, amount):
    """Falla si evaluar muchas coincidencias de una alerta escala consultas junto con el outbox."""
    configured_alert = alert(frequency='daily')
    records = [opportunity(f'ELIGIBLE-{position}') for position in range(amount)]
    Notification.objects.bulk_create([
        Notification(alert=configured_alert, opportunity=record, recipient='carlos@example.com')
        for record in records
    ])
    rows = list(Notification.objects.select_related('alert', 'opportunity').order_by('pk'))

    with CaptureQueriesContext(connection) as queries:
        eligible = eligible_ids(rows, 'daily')

    assert len(eligible) == amount
    assert len(queries) <= 2


@freeze_time('2026-11-05 07:00:00')
def test_flush_queues_delivery_without_contacting_smtp(
        opportunity, alert, django_capture_on_commit_callbacks, monkeypatch):
    """Falla si el programador diario intenta SMTP en su transacción en vez de encolar la entrega."""
    Settings.objects.update_or_create(pk=1, defaults={'email_enabled': True})
    record = opportunity('FLUSH-1')
    configured_alert = alert(frequency='daily')
    Notification.objects.create(alert=configured_alert, opportunity=record, recipient='carlos@example.com')
    now = timezone.now()
    ScheduleSlot.objects.create(kind='daily', day=now.date(), created_at=now)
    enqueued = Mock()
    monkeypatch.setattr('procurement.tasks.deliver', enqueued)
    monkeypatch.setattr('procurement.services.notifications.EmailDeliveryGateway.send', smtp_forbidden)

    with django_capture_on_commit_callbacks(execute=True):
        flush('daily')

    delivery = Delivery.objects.get(recipient='carlos@example.com')
    assert delivery.status == 'pending'
    enqueued.assert_called_once_with(delivery.pk)
