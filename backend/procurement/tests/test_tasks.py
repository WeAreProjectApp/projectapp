"""Clock and retry-boundary coverage for procurement schedules and deliveries."""

from datetime import time
from unittest.mock import Mock

import pytest
from freezegun import freeze_time
from procurement.models import Delivery, Notification, ScheduleSlot, Settings
from procurement.services.notifications import prepare_delivery, send_delivery
from procurement.tasks import procurement_clock

pytestmark = pytest.mark.django_db


def smtp_timeout(*_args, **_kwargs):
    """Represent an SMTP response whose delivery result cannot be known."""
    raise TimeoutError('Timed out waiting for SMTP confirmation')


def configured_settings(**changes):
    """Persist deterministic Bogotá schedule switches for one clock test."""
    values = {
        'sync_enabled': False,
        'email_enabled': True,
        'sync_time': time(2),
        'daily_time': time(7),
        'weekly_time': time(7),
        'weekly_day': 3,
    }
    values.update(changes)
    return Settings.objects.update_or_create(pk=1, defaults=values)[0]


@freeze_time('2026-11-05 12:00:00')
def test_clock_creates_one_daily_slot_when_called_twice_on_the_same_day(monkeypatch):
    """Falla si el reloj reserva dos resúmenes diarios para la misma fecha Bogotá."""
    configured_settings()
    monkeypatch.setattr('procurement.tasks.flush_notifications', lambda _frequency: None)

    procurement_clock.call_local()
    procurement_clock.call_local()

    assert ScheduleSlot.objects.filter(kind='daily').count() == 1
    assert ScheduleSlot.objects.get(kind='daily').day.isoformat() == '2026-11-05'


@freeze_time('2026-11-05 12:00:00')
def test_clock_creates_weekly_slot_only_on_configured_bogota_weekday(monkeypatch):
    """Falla si el digest semanal se agenda fuera del día que eligió el administrador."""
    configured_settings(weekly_day=2)
    monkeypatch.setattr('procurement.tasks.flush_notifications', lambda _frequency: None)

    procurement_clock.call_local()

    assert ScheduleSlot.objects.filter(kind='weekly').count() == 0


@freeze_time('2026-11-05 12:00:00')
def test_clock_does_not_enqueue_email_work_when_global_email_is_disabled(monkeypatch):
    """Falla si desactivar correo global aún crea o ejecuta resúmenes de alertas."""
    configured_settings(email_enabled=False)
    calls = []
    monkeypatch.setattr('procurement.tasks.flush_notifications', lambda frequency: calls.append(frequency))

    procurement_clock.call_local()

    assert ScheduleSlot.objects.filter(kind__in=['daily', 'weekly']).count() == 0
    assert calls == []


@freeze_time('2026-11-05 12:00:00')
def test_smtp_timeout_is_uncertain_and_clock_does_not_automatically_repeat_it(
        opportunity, alert, monkeypatch):
    """Falla si un timeout se acredita como enviado o el reloj repite un correo de resultado incierto."""
    configured_settings()
    record = opportunity('UNCERTAIN-1')
    configured_alert = alert(frequency='daily')
    notification = Notification.objects.create(
        alert=configured_alert, opportunity=record, recipient='carlos@example.com',
    )
    monkeypatch.setattr(
        'procurement.services.notifications.EmailDeliveryGateway.bounded_connection',
        lambda *, timeout_seconds: object(),
    )
    monkeypatch.setattr('procurement.services.notifications.EmailDeliveryGateway.send', smtp_timeout)

    delivery_id = prepare_delivery('daily')
    send_delivery(delivery_id)
    delivery = Delivery.objects.get(pk=delivery_id)
    notification.refresh_from_db()
    enqueued = Mock()
    monkeypatch.setattr('procurement.tasks.deliver', enqueued)
    monkeypatch.setattr('procurement.tasks.flush_notifications', Mock())

    procurement_clock.call_local()

    assert (delivery.status, notification.status) == ('uncertain', 'pending')
    enqueued.assert_not_called()
