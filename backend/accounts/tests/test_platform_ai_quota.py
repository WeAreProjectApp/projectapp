"""Behavioral coverage for the shared rolling quota of Platform AI."""
from datetime import timedelta
from uuid import uuid4

import pytest
from freezegun import freeze_time
from django.utils import timezone
from rest_framework.exceptions import Throttled

from accounts.models import UserProfile
from accounts.models_ai import (
    PlatformAICredential,
    PlatformAIJob,
    PlatformAIQuotaReservation,
    PlatformAISettings,
)
from accounts.services import platform_ai_quota
from accounts.services.platform_ai import AIConflict


pytestmark = pytest.mark.django_db


def configure_quota(client_user, *, limit=20, minutes=300, client_limit=None):
    UserProfile.objects.filter(user=client_user).update(
        ai_request_limit=client_limit,
        ai_window_minutes=minutes if client_limit is not None else None,
    )
    PlatformAISettings.objects.update_or_create(
        pk=1,
        defaults={'ai_request_limit': limit, 'ai_window_minutes': minutes},
    )


def configure_chatbot_audio(client_user, *, limit=20):
    configure_quota(client_user, limit=limit)
    UserProfile.objects.filter(user=client_user).update(chatbot_enabled=True)
    PlatformAISettings.objects.filter(pk=1).update(chatbot_enabled=True)
    PlatformAICredential.objects.bulk_create([
        PlatformAICredential(provider='anthropic', encrypted_value='configured'),
        PlatformAICredential(provider='openai', encrypted_value='configured'),
        PlatformAICredential(provider='jev', encrypted_value='configured'),
    ])


def expired_chat_audio(client_user, project):
    reservation = PlatformAIQuotaReservation.objects.create(
        actor=client_user,
        request_id=uuid4(),
        purpose='chatbot',
        fingerprint='recorded-question',
        status='consumed',
    )
    PlatformAIQuotaReservation.objects.filter(pk=reservation.pk).update(
        created_at=timezone.now() - timedelta(hours=6),
    )
    job = PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='chatbot',
        operation='transcription',
        request_id=uuid4(),
        fingerprint='recorded-question',
        status='ready',
        payload={'quota_id': str(reservation.pk)},
        expires_at=timezone.now() + timedelta(hours=1),
    )
    reservation.refresh_from_db()
    return reservation, job


def test_voice_reservation_observes_existing_chatbot_consumption(client_user):
    """Fails if chatbot requests can bypass the voice report quota."""
    configure_quota(client_user, limit=2)
    platform_ai_quota.reserve(client_user, uuid4(), 'chatbot', 'chat-one')
    platform_ai_quota.reserve(client_user, uuid4(), 'voice_report', 'voice-one')

    with pytest.raises(Throttled, match='cupo compartido'):
        platform_ai_quota.reserve(client_user, uuid4(), 'chatbot', 'chat-two')

    assert platform_ai_quota.snapshot(client_user)['used'] == 2
    assert platform_ai_quota.snapshot(client_user)['remaining'] == 0


def test_client_override_wins_over_the_global_request_limit(client_user):
    """Fails if a stricter client quota is ignored in favor of the global value."""
    configure_quota(client_user, limit=5, client_limit=1)
    platform_ai_quota.reserve(client_user, uuid4(), 'voice_report', 'voice-one')

    with pytest.raises(Throttled):
        platform_ai_quota.reserve(client_user, uuid4(), 'chatbot', 'chat-one')

    usage = platform_ai_quota.snapshot(client_user)
    assert usage['limit'] == 1
    assert usage['inherited'] is False


def test_refunded_reservation_can_reuse_its_request_id(client_user):
    """Fails if a technical failure permanently spends the user's shared quota."""
    configure_quota(client_user, limit=1)
    request_id = uuid4()
    reservation = platform_ai_quota.reserve(client_user, request_id, 'voice_report', 'voice-one')

    platform_ai_quota.refund(reservation.pk)
    retried = platform_ai_quota.reserve(client_user, request_id, 'voice_report', 'voice-one')

    assert retried.pk == reservation.pk
    assert retried.status == 'reserved'
    assert platform_ai_quota.snapshot(client_user)['remaining'] == 0


@freeze_time('2026-10-24 15:00:00')
def test_rolling_window_ignores_reservations_that_expired_before_the_window(client_user):
    """Fails if an old completed request blocks a new request after the rolling window."""
    configure_quota(client_user, limit=2, minutes=300)
    old = PlatformAIQuotaReservation.objects.create(
        actor=client_user, request_id=uuid4(), purpose='chatbot', fingerprint='old', status='consumed',
    )
    PlatformAIQuotaReservation.objects.filter(pk=old.pk).update(
        created_at=old.created_at - timedelta(minutes=301),
    )
    platform_ai_quota.reserve(client_user, uuid4(), 'voice_report', 'current')

    usage = platform_ai_quota.snapshot(client_user)

    assert usage['used'] == 1
    assert usage['remaining'] == 1
    assert usage['retry_after'] == 0


@freeze_time('2026-10-24 15:00:00')
def test_chat_voice_redemption_uses_the_existing_consumed_reservation(client_user, project):
    """Fails if sending a ready dictated chatbot question spends the quota twice."""
    configure_quota(client_user)
    UserProfile.objects.filter(user=client_user).update(chatbot_enabled=True)
    PlatformAISettings.objects.filter(pk=1).update(chatbot_enabled=True)
    PlatformAICredential.objects.bulk_create([
        PlatformAICredential(provider='anthropic', encrypted_value='configured'),
        PlatformAICredential(provider='openai', encrypted_value='configured'),
        PlatformAICredential(provider='jev', encrypted_value='configured'),
    ])
    reservation = platform_ai_quota.reserve(client_user, uuid4(), 'chatbot', 'recorded-question')
    platform_ai_quota.consume(reservation.pk)
    job = PlatformAIJob.objects.create(
        actor=client_user, project=project, purpose='chatbot', operation='transcription',
        request_id=uuid4(), fingerprint='recorded-question', status='ready',
        payload={'quota_id': str(reservation.pk)}, expires_at=timezone.now() + timedelta(hours=1),
    )
    request_id = uuid4()

    first = platform_ai_quota.redeem_chat_audio(client_user, job.pk, request_id, project_id=project.pk)
    repeated = platform_ai_quota.redeem_chat_audio(client_user, job.pk, request_id, project_id=project.pk)

    assert first.pk == reservation.pk
    assert repeated.pk == reservation.pk
    with pytest.raises(AIConflict, match='ya se usó'):
        platform_ai_quota.redeem_chat_audio(client_user, job.pk, uuid4(), project_id=project.pk)


@freeze_time('2026-10-24 15:00:00')
def test_redeeming_expired_audio_reenters_the_current_window(client_user, project):
    """Fails if an old dictated question becomes an uncharged new chatbot request."""
    configure_chatbot_audio(client_user, limit=2)
    reservation, job = expired_chat_audio(client_user, project)
    request_id = uuid4()

    redeemed = platform_ai_quota.redeem_chat_audio(client_user, job.pk, request_id, project_id=project.pk)
    usage = platform_ai_quota.snapshot(client_user)

    assert redeemed.pk == reservation.pk
    assert redeemed.created_at == timezone.now()
    assert redeemed.redemption_request_id == request_id
    assert PlatformAIQuotaReservation.objects.filter(actor=client_user).count() == 1
    assert usage['used'] == 1


@freeze_time('2026-10-24 15:00:00')
def test_current_quota_blocks_expired_audio_redemption(client_user, project):
    """Fails if an old dictated question can bypass a full current quota window."""
    configure_chatbot_audio(client_user, limit=1)
    reservation, job = expired_chat_audio(client_user, project)
    platform_ai_quota.reserve(client_user, uuid4(), 'chatbot', 'current-question')

    with pytest.raises(Throttled, match='cupo compartido'):
        platform_ai_quota.redeem_chat_audio(client_user, job.pk, uuid4(), project_id=project.pk)

    reservation.refresh_from_db()
    assert reservation.redemption_request_id is None
    assert reservation.created_at == timezone.now() - timedelta(hours=6)


@freeze_time('2026-10-24 15:00:00')
def test_repeated_redemption_preserves_the_reentry_timestamp(client_user, project):
    """Fails if retrying one redeemed dictated question prolongs its quota window."""
    configure_chatbot_audio(client_user)
    _, job = expired_chat_audio(client_user, project)
    request_id = uuid4()
    first = platform_ai_quota.redeem_chat_audio(client_user, job.pk, request_id, project_id=project.pk)
    timestamp = first.created_at

    with freeze_time('2026-10-24 15:10:00'):
        repeated = platform_ai_quota.redeem_chat_audio(client_user, job.pk, request_id, project_id=project.pk)

    assert repeated.redemption_request_id == request_id
    assert repeated.created_at == timestamp
