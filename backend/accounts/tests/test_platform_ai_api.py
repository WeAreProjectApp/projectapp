"""HTTP contracts for Platform AI secrets, job privacy and voice quota retries."""
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import UserProfile
from accounts.models_ai import (
    PlatformAICredential,
    PlatformAIJob,
    PlatformAIQuotaReservation,
    PlatformAISettings,
)
from accounts.services import platform_ai_jobs


pytestmark = pytest.mark.django_db


def configure_voice(client_user):
    UserProfile.objects.filter(user=client_user).update(voice_reporting_enabled=True)
    PlatformAISettings.objects.update_or_create(
        pk=1,
        defaults={'voice_reporting_enabled': True, 'ai_request_limit': 20, 'ai_window_minutes': 300},
    )
    PlatformAICredential.objects.bulk_create([
        PlatformAICredential(provider='anthropic', encrypted_value='configured'),
        PlatformAICredential(provider='openai', encrypted_value='configured'),
    ])


def voice_payload(project, request_id):
    return {
        'purpose': 'voice_report',
        'project_id': str(project.pk),
        'request_id': str(request_id),
        'audio': SimpleUploadedFile(
            'observation.webm', b'\x1a\x45\xdf\xa3recorded-voice', content_type='audio/webm',
        ),
    }


def test_credential_api_returns_only_configuration_state(api_client, admin_user, settings):
    """Fails if the panel credential API returns the provider key it just saved."""
    settings.PLATFORM_AI_CIPHER_KEY = Fernet.generate_key().decode()
    admin_user.is_staff = True
    admin_user.save(update_fields=['is_staff'])
    api_client.force_authenticate(admin_user)
    secret = 'anthropic-panel-secret-never-returned'

    response = api_client.put(
        '/api/platform/ai/admin/credentials/anthropic/',
        {'api_key': secret, 'expected_version': 0}, format='json',
    )
    stored = PlatformAICredential.objects.get(provider='anthropic')

    assert response.status_code == 200
    assert response.json() == {
        'configured': True, 'version': 1, 'last_test_status': '', 'tested_at': None,
    }
    assert stored.encrypted_value != secret
    assert secret not in response.content.decode()


def test_credential_api_refuses_a_client_before_storing_a_provider_key(api_client, client_user):
    """Fails if a platform client can write an administrator's AI credential."""
    api_client.force_authenticate(client_user)

    response = api_client.put(
        '/api/platform/ai/admin/credentials/openai/',
        {'api_key': 'openai-client-secret-denied', 'expected_version': 0}, format='json',
    )

    assert response.status_code == 403
    assert not PlatformAICredential.objects.filter(provider='openai').exists()


def test_job_endpoint_hides_another_clients_transcript(api_client, client_user, project, admin_user):
    """Fails if a client can discover another client's AI transcription through its UUID."""
    other = get_user_model().objects.create_user(
        username='api-other@test.com', email='api-other@test.com', password='pass12345',
    )
    UserProfile.objects.create(user=other, role=UserProfile.ROLE_CLIENT, created_by=admin_user)
    job = PlatformAIJob.objects.create(
        actor=client_user, project=project, purpose='voice_report', operation='transcription',
        request_id=uuid4(), fingerprint='private-http-job', status='ready',
        result={'transcript': 'No exponer'}, expires_at=timezone.now() + timedelta(hours=1),
    )
    api_client.force_authenticate(other)

    response = api_client.get(f'/api/platform/ai/transcriptions/{job.pk}/')

    assert response.status_code == 404
    assert response['Cache-Control'] == 'no-store'


def test_transcription_retry_preserves_the_original_quota_reservation(api_client, client_user, project, monkeypatch):
    """Fails if retrying one upload spends the shared quota or queues transcription twice."""
    configure_voice(client_user)
    monkeypatch.setattr(platform_ai_jobs, '_enqueue', lambda job: None)
    api_client.force_authenticate(client_user)
    request_id = uuid4()

    first = api_client.post(
        '/api/platform/ai/transcriptions/', voice_payload(project, request_id), format='multipart',
    )
    retried = api_client.post(
        '/api/platform/ai/transcriptions/', voice_payload(project, request_id), format='multipart',
    )

    assert first.status_code == 202
    assert retried.status_code == 202
    assert retried.json()['id'] == first.json()['id']
    assert PlatformAIJob.objects.filter(actor=client_user, purpose='voice_report').count() == 1
    assert PlatformAIQuotaReservation.objects.filter(actor=client_user, purpose='voice_report').count() == 1


def test_cancelling_pending_transcription_refunds_its_quota_reservation(api_client, client_user, project, monkeypatch):
    """Fails if discarding an unprocessed voice note permanently consumes shared quota."""
    configure_voice(client_user)
    monkeypatch.setattr(platform_ai_jobs, '_enqueue', lambda job: None)
    api_client.force_authenticate(client_user)
    created = api_client.post(
        '/api/platform/ai/transcriptions/', voice_payload(project, uuid4()), format='multipart',
    )
    job_id = created.json()['id']

    response = api_client.delete(f'/api/platform/ai/transcriptions/{job_id}/')
    reservation = PlatformAIQuotaReservation.objects.get(actor=client_user)

    assert created.status_code == 202
    assert response.status_code == 200
    assert response.json() == {'discarded': True}
    assert reservation.status == 'refunded'
