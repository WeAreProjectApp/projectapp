"""JWT contracts for a client's private Platform AI job flow."""
import wave
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.models_ai import (
    PlatformAICredential,
    PlatformAIJob,
    PlatformAIQuotaReservation,
    PlatformAISettings,
    PlatformAITemplate,
)
from accounts.services.tokens import get_tokens_for_user

pytestmark = pytest.mark.django_db


def configure_voice(client_user):
    """Enable the complete voice-reporting dependency set for one client."""
    UserProfile.objects.filter(user=client_user).update(voice_reporting_enabled=True)
    PlatformAISettings.objects.update_or_create(
        pk=1,
        defaults={
            'voice_reporting_enabled': True,
            'monthly_audio_limit': 1000,
            'daily_user_audio_limit': 20,
            'ai_request_limit': 20,
            'ai_window_minutes': 300,
            'report_cache_enabled': True,
            'report_cache_hours': 24,
        },
    )
    for provider in ('anthropic', 'openai'):
        PlatformAICredential.objects.update_or_create(
            provider=provider, defaults={'encrypted_value': 'configured'},
        )
    PlatformAITemplate.objects.get_or_create(
        family='report', scenario='voice_base', language='es',
        defaults={'content': 'Organiza únicamente lo dicho.'},
    )
    PlatformAITemplate.objects.get_or_create(
        family='report', scenario='bug', language='es',
        defaults={'content': 'Describe el problema sin inventar detalles.'},
    )


def jwt_headers(user):
    """Return a complete session JWT with the user's profile claims."""
    return {'HTTP_AUTHORIZATION': f'Bearer {get_tokens_for_user(user)["access"]}'}


def wav_upload(name='voice.wav'):
    """Build a short valid WAV upload without invoking an external decoder."""
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as stream:
        stream.setparams((1, 2, 16000, 4000, 'NONE', 'not compressed'))
        stream.writeframes((100).to_bytes(2, 'little', signed=True) * 4000)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='audio/wav')


def ready_transcription(actor, project, transcript='El botón Guardar no responde.'):
    """Persist a non-expired transcription that the supplied client may review."""
    return PlatformAIJob.objects.create(
        actor=actor,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint=uuid4().hex,
        status='ready',
        result={'transcript': transcript},
        expires_at=timezone.now() + timedelta(hours=1),
    )


def ready_draft(actor, project, scenario, context, description):
    """Persist a ready report draft with the context used by list filtering."""
    return PlatformAIJob.objects.create(
        actor=actor,
        project=project,
        purpose='voice_report',
        operation='draft',
        request_id=uuid4(),
        fingerprint=uuid4().hex,
        status='ready',
        payload={'scenario': scenario, 'context': context},
        result={'proposal': {'description': description}},
        expires_at=timezone.now() + timedelta(hours=1),
    )


def other_client(admin_user):
    """Create a separate active client used to prove list isolation."""
    user = get_user_model().objects.create_user(
        username='list-private-other', email='list-private-other@test.com', password='pass12345',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, created_by=admin_user)
    return user


@freeze_time('2026-10-24 15:00:00')
def test_transcription_list_returns_only_matching_private_job_summaries(client_user, project, admin_user):
    """Fails if listing recent reports reveals another client, context, or transcript content."""
    configure_voice(client_user)
    included_transcription = ready_transcription(client_user, project, 'Transcripción privada.')
    included_draft = ready_draft(
        client_user, project, 'bug', {'project_id': project.pk}, 'Borrador privado.',
    )
    ready_draft(client_user, project, 'change', {'project_id': project.pk}, 'Otro escenario.')
    other = other_client(admin_user)
    PlatformAIJob.objects.create(
        actor=other,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint=uuid4().hex,
        status='ready',
        result={'transcript': 'Nunca exponer.'},
        expires_at=timezone.now() + timedelta(hours=1),
    )
    client = APIClient()

    response = client.get(
        f'/api/platform/ai/transcriptions/?purpose=voice_report&project_id={project.pk}&scenario=bug',
        **jwt_headers(client_user),
    )

    rows = response.json()
    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert {row['id'] for row in rows} == {str(included_transcription.pk), str(included_draft.pk)}
    assert all(set(row) == {'id', 'operation', 'scenario', 'created_at'} for row in rows)
    assert 'Transcripción privada.' not in response.content.decode()
    assert 'Nunca exponer.' not in response.content.decode()


@freeze_time('2026-10-24 15:00:00')
def test_transcription_list_rejects_an_unknown_purpose(client_user, project):
    """Fails if an arbitrary job purpose can bypass the client's voice-reporting gate."""
    client = APIClient()

    response = client.get(
        f'/api/platform/ai/transcriptions/?purpose=export&project_id={project.pk}',
        **jwt_headers(client_user),
    )

    assert response.status_code == 400
    assert response['Cache-Control'] == 'no-store'


@freeze_time('2026-10-24 15:00:00')
def test_voice_list_rejects_a_missing_report_scenario(client_user, project):
    """Fails if an unclassified voice-report query can return reports across scenarios."""
    configure_voice(client_user)
    client = APIClient()

    response = client.get(
        f'/api/platform/ai/transcriptions/?purpose=voice_report&project_id={project.pk}',
        **jwt_headers(client_user),
    )

    assert response.status_code == 400
    assert response['Cache-Control'] == 'no-store'


@freeze_time('2026-10-24 15:00:00')
def test_voice_list_rejects_an_invalid_context_identifier(client_user, project):
    """Fails if malformed report context is accepted before the authorized lookup."""
    configure_voice(client_user)
    client = APIClient()

    response = client.get(
        f'/api/platform/ai/transcriptions/?purpose=voice_report&project_id={project.pk}'
        '&scenario=bug&source_requirement_id=not-an-id',
        **jwt_headers(client_user),
    )

    assert response.status_code == 400
    assert response['Cache-Control'] == 'no-store'


@freeze_time('2026-10-24 15:00:00')
def test_session_cookie_cannot_read_a_jwt_only_transcription_list(client_user, project):
    """Fails if a panel session can access the client endpoint reserved for a JWT."""
    client = APIClient()
    client.force_login(client_user)

    response = client.get(
        f'/api/platform/ai/transcriptions/?purpose=voice_report&project_id={project.pk}&scenario=bug',
    )

    assert response.status_code == 401
    assert response['Cache-Control'] == 'no-store'


@freeze_time('2026-10-24 15:00:00')
def test_job_get_returns_its_ready_result_to_the_jwt_owner(client_user, project):
    """Fails if the owner cannot retrieve the transcript needed to review a ready report."""
    configure_voice(client_user)
    job = ready_transcription(client_user, project)
    client = APIClient()

    response = client.get(f'/api/platform/ai/transcriptions/{job.pk}/', **jwt_headers(client_user))

    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert response.json()['id'] == str(job.pk)
    assert response.json()['status'] == 'ready'
    assert response.json()['operation'] == 'transcription'
    assert response.json()['transcript'] == 'El botón Guardar no responde.'
    assert 'payload' not in response.json()


@freeze_time('2026-10-24 15:00:00')
def test_job_delete_refunds_a_pending_reservation_for_its_jwt_owner(client_user, project):
    """Fails if a cancelled JWT recording retains its quota reservation or private audio."""
    configure_voice(client_user)
    reservation = PlatformAIQuotaReservation.objects.create(
        actor=client_user,
        request_id=uuid4(),
        purpose='voice_report',
        fingerprint=uuid4().hex,
        status='reserved',
    )
    storage = storages['private']
    audio_name = storage.save(f'platform-ai/{uuid4()}.wav', wav_upload())
    job = PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint=uuid4().hex,
        status='pending',
        audio_name=audio_name,
        payload={'quota_id': str(reservation.pk)},
        result={'transcript': 'No conservar.'},
        expires_at=timezone.now() + timedelta(hours=1),
    )
    client = APIClient()

    response = client.delete(f'/api/platform/ai/transcriptions/{job.pk}/', **jwt_headers(client_user))

    job.refresh_from_db()
    reservation.refresh_from_db()
    assert (response.status_code, response.json()) == (200, {'discarded': True})
    assert (
        job.status, job.payload, job.result, job.audio_name, reservation.status, storage.exists(audio_name),
    ) == ('cancelled', {}, {}, '', 'refunded', False)


@freeze_time('2026-10-24 15:00:00')
def test_transcription_post_creates_a_private_job_with_a_reservation(
    client_user, project, django_capture_on_commit_callbacks,
):
    """Fails if a valid JWT WAV upload is accepted without a private pending job and quota hold."""
    configure_voice(client_user)
    client = APIClient()
    request_id = uuid4()

    with django_capture_on_commit_callbacks(execute=False):
        response = client.post(
            '/api/platform/ai/transcriptions/',
            {
                'purpose': 'voice_report',
                'project_id': str(project.pk),
                'request_id': str(request_id),
                'audio': wav_upload(),
            },
            format='multipart',
            **jwt_headers(client_user),
        )

    job = PlatformAIJob.objects.get(actor=client_user, request_id=request_id)
    reservation = PlatformAIQuotaReservation.objects.get(actor=client_user, request_id=request_id)
    result = response.json()
    assert (response.status_code, result['id'], result['status']) == (202, str(job.pk), 'pending')
    assert (
        job.audio_name.startswith('platform-ai/audio/'), storages['private'].exists(job.audio_name),
        job.payload, reservation.status, 'audio_name' in result,
    ) == (True, True, {'quota_id': str(reservation.pk)}, 'reserved', False)


@freeze_time('2026-10-24 15:00:00')
def test_report_draft_post_freezes_authorized_project_context(
    client_user, project, django_capture_on_commit_callbacks,
):
    """Fails if a JWT report draft does not retain the authorized project context it will process."""
    configure_voice(client_user)
    transcription = ready_transcription(client_user, project)
    client = APIClient()
    request_id = uuid4()

    with django_capture_on_commit_callbacks(execute=False):
        response = client.post(
            f'/api/platform/ai/projects/{project.pk}/report-drafts/',
            {
                'request_id': str(request_id),
                'transcription_id': str(transcription.pk),
                'transcript': 'El botón Guardar no responde.',
                'scenario': 'bug',
                'language': 'es',
            },
            format='json',
            **jwt_headers(client_user),
        )

    job = PlatformAIJob.objects.get(actor=client_user, request_id=request_id)
    result = response.json()
    assert (response.status_code, result['id'], result['operation']) == (202, str(job.pk), 'draft')
    assert (
        job.status, job.payload['context'], job.payload['policy']['template_version'] >= 1,
        job.payload['transcript'], 'context' in result,
    ) == ('pending', {'project_id': project.pk}, True, 'El botón Guardar no responde.', False)
