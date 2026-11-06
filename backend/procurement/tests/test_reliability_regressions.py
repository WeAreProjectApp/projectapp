"""Regression coverage for failure-safe procurement source and delivery work."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from freezegun import freeze_time
from procurement.models import (
    Classification,
    Delivery,
    Notification,
    ScheduleSlot,
    Settings,
    SyncRun,
)
from procurement.services.notifications import (
    flush,
    prepare_delivery,
    retry_delivery,
    send_delivery,
)
from procurement.services.source import (
    PAGE_SIZE,
    PublicClient,
    normalized_record,
    quote,
    source_datetime,
)
from procurement.services.sync import request_sync, synchronize_page
from procurement.tasks import evaluate_alert, procurement_clock, sync_page
from rest_framework.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def source_row(source_id='SECOP-1', **changes):
    """Build a minimal public record accepted by the SECOP normalizer."""
    row = {
        'id_del_proceso': source_id,
        'referencia_del_proceso': f'REF-{source_id}',
        'nombre_del_procedimiento': f'Proceso {source_id}',
        'entidad': 'Entidad Nacional',
        'departamento_entidad': 'Bogotá D.C.',
        'estado_del_procedimiento': 'Abierto',
        'codigo_principal_de_categoria': '80101500',
        'precio_base': '1000000',
    }
    row.update(changes)
    return row


class PublicResponse:
    """Minimal requests response that keeps the public HTTP boundary deterministic."""

    def __init__(self, payload):
        """Store the JSON payload returned by the public source."""
        self.payload = payload

    def raise_for_status(self):
        """Model a successful HTTP response without making a network call."""

    def json(self):
        """Return the source payload exactly as a requests response would."""
        return self.payload


class StaticSourceClient:
    """Return one configured page for synchronization tests."""

    def __init__(self, records):
        """Keep records local so the test cannot contact the public source."""
        self.records = records
        self.calls = []

    def page(self, **kwargs):
        """Record the requested cursor and return the configured records."""
        self.calls.append(kwargs)
        return self.records


def configured_settings(**changes):
    """Create deterministic schedule settings for a single clock behavior."""
    values = {
        'sync_enabled': False,
        'email_enabled': True,
        'sync_time': timezone.datetime(2026, 1, 1, 2).time(),
        'daily_time': timezone.datetime(2026, 1, 1, 7).time(),
        'weekly_time': timezone.datetime(2026, 1, 1, 7).time(),
        'weekly_day': 3,
    }
    values.update(changes)
    return Settings.objects.update_or_create(pk=1, defaults=values)[0]


def test_source_datetime_returns_none_for_empty_value():
    """Falla si una fecha pública vacía se convierte en una fecha ficticia."""
    assert source_datetime('') is None


def test_source_datetime_localizes_naive_public_timestamp():
    """Falla si una fecha SECOP sin zona horaria pierde la hora local Bogotá."""
    parsed = source_datetime('2026-11-05T08:30:00')

    assert (parsed.tzinfo.key, parsed.hour) == ('America/Bogota', 8)


def test_source_datetime_preserves_aware_public_timestamp():
    """Falla si normalizar una fecha ya zonificada cambia su instante público."""
    parsed = source_datetime('2026-11-05T08:30:00+00:00')

    assert parsed.utcoffset() == timedelta(0)


def test_quote_escapes_public_process_identifier():
    """Falla si un identificador SECOP con apóstrofe altera la consulta pública."""
    assert quote("SECOP'42") == "'SECOP''42'"


def test_public_client_queries_explicit_process_identifiers(monkeypatch):
    """Falla si actualizar procesos rastreados deja identificadores sin escapar."""
    get = Mock(return_value=PublicResponse([]))
    monkeypatch.setattr('procurement.services.source.requests.get', get)

    assert PublicClient().page(ids=["A'1", 'B']) == []

    get.assert_called_once()
    assert get.call_args.kwargs['params']['$where'] == "id_del_proceso in ('A''1','B')"


def test_public_client_queries_changed_since_cursor(monkeypatch):
    """Falla si una recuperación incremental ignora el cursor de última publicación."""
    get = Mock(return_value=PublicResponse([]))
    monkeypatch.setattr('procurement.services.source.requests.get', get)

    PublicClient().page(since='2026-10-01')

    get.assert_called_once()
    assert get.call_args.kwargs['params']['$where'] == "fecha_de_ultima_publicaci >= '2026-10-01'"


@freeze_time('2026-11-05 12:00:00')
def test_public_client_queries_open_records_with_lookback(monkeypatch):
    """Falla si la primera carga pide procedimientos fuera de la ventana configurada."""
    get = Mock(return_value=PublicResponse([]))
    monkeypatch.setattr('procurement.services.source.requests.get', get)

    PublicClient().page(lookback=10)

    get.assert_called_once()
    assert get.call_args.kwargs['params']['$where'].endswith("fecha_de_publicacion_del >= '2026-10-26'")


def test_public_client_rejects_non_list_payload(monkeypatch):
    """Falla si una respuesta pública con forma inesperada entra al sincronizador."""
    get = Mock(return_value=PublicResponse({'error': 'bad'}))
    monkeypatch.setattr('procurement.services.source.requests.get', get)

    with pytest.raises(ValueError, match='Respuesta pública no válida'):
        PublicClient().page()

    get.assert_called_once()


def test_normalized_record_rejects_oversized_process_identifier():
    """Falla si un identificador fuera del límite rompe la clave local de oportunidad."""
    with pytest.raises(ValueError, match='identificador válido'):
        normalized_record(source_row('X' * 101))


@freeze_time('2026-11-05 12:00:00')
def test_request_sync_recovers_stale_run_before_creating_replacement(
        django_capture_on_commit_callbacks, monkeypatch):
    """Falla si un worker interrumpido bloquea una sincronización nueva indefinidamente."""
    stale = SyncRun.objects.create(cursor={'offset': 0, 'since': None, 'phase': 'source'})
    SyncRun.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(hours=3))
    last = SyncRun.objects.create(status='success', cursor={}, started_at=timezone.now() - timedelta(days=4))
    enqueue = Mock()
    monkeypatch.setattr('procurement.tasks.sync_page', enqueue)

    with django_capture_on_commit_callbacks(execute=True):
        replacement = request_sync()

    stale.refresh_from_db()
    assert stale.status == 'failed'
    assert replacement.cursor == {
        'offset': 0,
        'since': (last.started_at - timedelta(days=2)).date().isoformat(),
        'phase': 'source',
    }
    enqueue.assert_called_once_with(replacement.pk)


def test_request_sync_returns_active_run_without_second_job(monkeypatch):
    """Falla si dos solicitudes simultáneas crean trabajos de sincronización competidores."""
    active = SyncRun.objects.create(cursor={'offset': 0, 'since': None, 'phase': 'source'})
    enqueue = Mock()
    monkeypatch.setattr('procurement.tasks.sync_page', enqueue)

    assert request_sync().pk == active.pk

    enqueue.assert_not_called()


def test_sync_ignores_terminal_run_without_contacting_source():
    """Falla si un run cerrado vuelve a consultar SECOP después de terminar."""
    run = SyncRun.objects.create(status='success', cursor={'offset': 0, 'since': None, 'phase': 'source'})
    client = Mock()

    assert synchronize_page(run.pk, client) is False

    client.page.assert_not_called()


def test_sync_advances_source_cursor_after_full_page():
    """Falla si una página SECOP completa no continúa desde el siguiente offset."""
    run = SyncRun.objects.create(cursor={'offset': 0, 'since': None, 'phase': 'source'})
    client = StaticSourceClient([source_row('PAGE-SAME')] * PAGE_SIZE)

    assert synchronize_page(run.pk, client) is True

    run.refresh_from_db()
    assert run.cursor['offset'] == PAGE_SIZE


def test_sync_advances_tracked_cursor_after_full_tracked_page(opportunity, staff_user):
    """Falla si refrescar cien procesos rastreados repite siempre el primer bloque."""
    records = [opportunity(f'TRACK-{position}') for position in range(100)]
    Classification.objects.bulk_create([
        Classification(opportunity=record, owner=staff_user) for record in records
    ])
    run = SyncRun.objects.create(cursor={'offset': 0, 'since': None, 'phase': 'tracked'})
    client = StaticSourceClient([source_row(record.source_id) for record in records])

    assert synchronize_page(run.pk, client) is True

    run.refresh_from_db()
    assert run.cursor['offset'] == 100


def test_sync_page_schedules_continuation_for_running_run(monkeypatch):
    """Falla si una página incompleta termina el trabajo Huey antes del siguiente cursor."""
    continuation = Mock()
    monkeypatch.setattr('procurement.services.sync.synchronize_page', lambda _run_id: True)
    monkeypatch.setattr('procurement.tasks.sync_page.schedule', continuation)

    sync_page.call_local(42)

    continuation.assert_called_once_with(args=(42,), delay=2)


def test_evaluate_alert_schedules_next_page_when_opportunities_exist(opportunity, monkeypatch):
    """Falla si una alerta deja oportunidades posteriores sin evaluar por límite de lote."""
    record = opportunity('TASK-ALERT')
    evaluated = Mock()
    continuation = Mock()
    monkeypatch.setattr('procurement.services.notifications.evaluate_opportunities', evaluated)
    monkeypatch.setattr('procurement.tasks.evaluate_alert.schedule', continuation)

    evaluate_alert.call_local(77)

    evaluated.assert_called_once_with([record.pk], alert_id=77)
    continuation.assert_called_once_with(args=(77, record.pk), delay=1)


@freeze_time('2026-11-05 12:00:00')
def test_clock_waits_for_running_sync_before_creating_digest_slots(monkeypatch):
    """Falla si un digest se abre mientras SECOP aún puede cambiar oportunidades."""
    configured_settings()
    SyncRun.objects.create(status='running', cursor={'offset': 0, 'since': None, 'phase': 'source'})
    monkeypatch.setattr('procurement.tasks.flush_notifications', lambda _frequency: None)

    procurement_clock.call_local()

    assert ScheduleSlot.objects.filter(kind__in=['daily', 'weekly']).count() == 0


@freeze_time('2026-11-05 12:00:00')
def test_clock_enqueues_pending_delivery(monkeypatch):
    """Falla si una entrega pendiente queda sin trabajo de entrega del reloj."""
    configured_settings()
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily')
    enqueue = Mock()
    monkeypatch.setattr('procurement.tasks.deliver', enqueue)
    monkeypatch.setattr('procurement.tasks.flush_notifications', Mock())

    procurement_clock.call_local()

    enqueue.assert_called_once_with(delivery.pk)


@freeze_time('2026-11-05 12:00:00')
def test_clock_retries_old_failed_delivery(monkeypatch):
    """Falla si un fallo SMTP conocido no vuelve a la cola tras el período de espera."""
    configured_settings()
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily', status='failed')
    Delivery.objects.filter(pk=delivery.pk).update(attempted_at=timezone.now() - timedelta(minutes=6))
    retried = Mock()
    monkeypatch.setattr('procurement.services.notifications.retry_delivery', retried)
    monkeypatch.setattr('procurement.tasks.flush_notifications', Mock())
    monkeypatch.setattr('procurement.tasks.deliver', Mock())

    procurement_clock.call_local()

    retried.assert_called_once_with(delivery.pk)


def test_send_delivery_keeps_pending_state_when_global_email_is_disabled():
    """Falla si desactivar correo global reclama una entrega pendiente del outbox."""
    Settings.objects.update_or_create(pk=1, defaults={'email_enabled': False})
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily')

    send_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert (delivery.status, delivery.attempts) == ('pending', 0)


def test_send_delivery_marks_unconfirmed_gateway_result_as_failed(opportunity, alert, monkeypatch):
    """Falla si un SMTP sin confirmación se acredita como correo enviado."""
    Settings.objects.update_or_create(pk=1, defaults={'email_enabled': True})
    record = opportunity('SMTP-ZERO')
    configured_alert = alert(frequency='daily')
    Notification.objects.create(alert=configured_alert, opportunity=record, recipient='carlos@example.com')
    monkeypatch.setattr(
        'procurement.services.notifications.EmailDeliveryGateway.bounded_connection',
        lambda *, timeout_seconds: object(),
    )
    monkeypatch.setattr('procurement.services.notifications.EmailDeliveryGateway.send', lambda *_args, **_kwargs: 0)

    delivery_id = prepare_delivery('daily')
    send_delivery(delivery_id)

    assert Delivery.objects.get(pk=delivery_id).status == 'failed'


def test_prepare_delivery_skips_row_when_alert_recipient_was_removed(opportunity, alert):
    """Falla si un destinatario retirado conserva una entrega que ya no es elegible."""
    record = opportunity('REMOVED-RECIPIENT')
    configured_alert = alert(frequency='daily', recipients=[])
    notification = Notification.objects.create(
        alert=configured_alert,
        opportunity=record,
        recipient='carlos@example.com',
    )

    assert prepare_delivery('daily') is False

    notification.refresh_from_db()
    assert notification.status == 'skipped'


@freeze_time('2026-11-05 12:00:00')
def test_flush_marks_abandoned_sender_as_uncertain():
    """Falla si un worker caído deja una entrega en estado enviando para siempre."""
    Settings.objects.update_or_create(pk=1, defaults={'email_enabled': True})
    delivery = Delivery.objects.create(
        recipient='carlos@example.com',
        frequency='immediate',
        status='sending',
    )
    Delivery.objects.filter(pk=delivery.pk).update(attempted_at=timezone.now() - timedelta(minutes=11))

    flush('immediate')

    delivery.refresh_from_db()
    assert delivery.status == 'uncertain'


def test_retry_delivery_returns_failed_delivery_to_pending_queue(
        django_capture_on_commit_callbacks, monkeypatch):
    """Falla si un reintento manual no deja la entrega fallida disponible para Huey."""
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily', status='failed')
    enqueue = Mock()
    monkeypatch.setattr('procurement.tasks.deliver', enqueue)

    with django_capture_on_commit_callbacks(execute=True):
        result = retry_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert (result, delivery.status) == ({'id': delivery.pk, 'status': 'pending'}, 'pending')
    enqueue.assert_called_once_with(delivery.pk)


def test_retry_delivery_rejects_pending_delivery():
    """Falla si reintentar una entrega pendiente duplica un correo todavía no enviado."""
    delivery = Delivery.objects.create(recipient='carlos@example.com', frequency='daily')

    with pytest.raises(ValidationError, match='Sólo se reintentan'):
        retry_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert delivery.status == 'pending'
