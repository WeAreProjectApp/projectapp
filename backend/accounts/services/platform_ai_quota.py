"""Atomic rolling quota shared by logical chatbot requests and voice reports."""
import math
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Min
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, Throttled, ValidationError

from accounts.models import UserProfile
from accounts.models_ai import PlatformAIQuotaReservation, PlatformAISettings
from accounts.services.platform_ai import AIConflict, configuration


def snapshot(actor, config=None, *, profile=None):
    config = config or configuration()
    profile = profile or UserProfile.objects.filter(user_id=actor.pk).first()
    limit = (profile.ai_request_limit if profile else None) or config.ai_request_limit
    minutes = (profile.ai_window_minutes if profile else None) or config.ai_window_minutes
    now = timezone.now()
    rows = PlatformAIQuotaReservation.objects.filter(actor=actor, status__in=['reserved', 'consumed'], created_at__gt=now - timedelta(minutes=minutes))
    totals = rows.aggregate(count=Count('id'), oldest=Min('created_at'))
    count = totals['count']
    offset = max(0, count - limit)
    first = rows.order_by('created_at').values_list('created_at', flat=True)[offset:offset + 1].first() if offset else totals['oldest']
    reset = first + timedelta(minutes=minutes) if first else None
    return {'limit': limit, 'used': count, 'remaining': max(0, limit - count), 'window_minutes': minutes,
            'resets_at': reset.isoformat() if reset else None, 'next_available_at': reset.isoformat() if reset else None,
            'retry_after': max(1, math.ceil((reset - now).total_seconds())) if reset and count >= limit else 0,
            'inherited': not bool(profile and profile.ai_request_limit)}


@transaction.atomic
def reserve(actor, request_id, purpose, fingerprint):
    if purpose not in ('chatbot', 'voice_report'):
        raise ValidationError('Propósito no admitido.')
    # This lock is also used by audio creation: concurrent channels cannot overspend.
    item, _ = PlatformAISettings.objects.get_or_create(pk=1)
    config = PlatformAISettings.objects.select_for_update().get(pk=item.pk)
    profile = UserProfile.objects.select_for_update().filter(user_id=actor.pk).first()
    if not actor.is_active or not profile or not profile.is_client:
        raise PermissionDenied('Se requiere una cuenta de cliente activa.')
    existing = PlatformAIQuotaReservation.objects.filter(actor=actor, request_id=request_id).first()
    if existing:
        if existing.purpose != purpose or existing.fingerprint != fingerprint:
            raise AIConflict('El reintento pertenece a otra solicitud.')
        if existing.status != 'refunded':
            return existing
    usage = snapshot(actor, config)
    if not usage['remaining']:
        raise Throttled(wait=usage['retry_after'], detail='Agotaste el cupo compartido de IA. Espera al próximo cupo o continúa manualmente.')
    if existing:
        existing.status = 'reserved'
        existing.created_at = timezone.now()
        existing.save(update_fields=['status', 'created_at'])
        return existing
    return PlatformAIQuotaReservation.objects.create(actor=actor, request_id=request_id, purpose=purpose, fingerprint=fingerprint)


def consume(reservation_id):
    PlatformAIQuotaReservation.objects.filter(pk=reservation_id, status='reserved').update(status='consumed')


def refund(reservation_id):
    # A successful transcript/result has already provided value and is never refunded.
    PlatformAIQuotaReservation.objects.filter(pk=reservation_id, status='reserved').update(status='refunded')


@transaction.atomic
def redeem_chat_audio(actor, transcription_id, request_id, *, project_id=None):
    """Bind one successful dictation to one chatbot request without charging twice."""
    from accounts.models_ai import PlatformAIJob
    config, _ = PlatformAISettings.objects.get_or_create(pk=1)
    config = PlatformAISettings.objects.select_for_update().get(pk=config.pk)
    from accounts.services.platform_ai import require_ai_feature
    require_ai_feature(actor, 'chatbot', project_id, audio=True, require_project=False)
    job = PlatformAIJob.objects.select_for_update().filter(pk=transcription_id, actor=actor, purpose='chatbot',
        operation='transcription', status='ready', project_id=project_id, expires_at__gt=timezone.now()).first()
    if not job:
        raise AIConflict('La transcripción no está disponible para esta consulta.')
    row = PlatformAIQuotaReservation.objects.select_for_update().filter(pk=job.payload.get('quota_id'), actor=actor, purpose='chatbot', status='consumed').first()
    if not row or row.created_at < timezone.now() - timedelta(hours=24):
        raise AIConflict('La reserva de la grabación no está disponible.')
    if row.redemption_request_id and str(row.redemption_request_id) != str(request_id):
        raise AIConflict('Esta grabación ya se usó en otra consulta.')
    if PlatformAIQuotaReservation.objects.filter(actor=actor, redemption_request_id=request_id).exclude(pk=row.pk).exists():
        raise AIConflict('Esta consulta ya está asociada a otra grabación.')
    if row.redemption_request_id:
        return row
    usage = snapshot(actor, config)
    now = timezone.now()
    if row.created_at <= now - timedelta(minutes=usage['window_minutes']):
        # A transcript cannot bank free questions for a later quota window.
        if not usage['remaining']:
            raise Throttled(wait=usage['retry_after'], detail='Agotaste el cupo compartido de IA. Espera al próximo cupo o continúa manualmente.')
        row.created_at = now
    row.redemption_request_id = request_id
    row.save(update_fields=['redemption_request_id', 'created_at'])
    return row
