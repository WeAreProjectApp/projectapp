"""Behavioral coverage for private, expiring Platform AI jobs."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import NotFound

from accounts.models import Project, UserProfile
from accounts.models_ai import PlatformAICredential, PlatformAIJob, PlatformAISettings, PlatformAITemplate
from accounts.services import platform_ai_jobs


pytestmark = pytest.mark.django_db


def configure_voice(client_user):
    UserProfile.objects.filter(user=client_user).update(voice_reporting_enabled=True)
    PlatformAISettings.objects.update_or_create(
        pk=1,
        defaults={'voice_reporting_enabled': True, 'report_cache_enabled': True, 'report_cache_hours': 24},
    )
    PlatformAICredential.objects.bulk_create([
        PlatformAICredential(provider='anthropic', encrypted_value='configured'),
        PlatformAICredential(provider='openai', encrypted_value='configured'),
    ])
    PlatformAITemplate.objects.get_or_create(
        family='report', scenario='voice_base', language='es',
        defaults={'content': 'Organiza únicamente lo dicho.'},
    )
    PlatformAITemplate.objects.get_or_create(
        family='report', scenario='bug', language='es',
        defaults={'content': 'Describe el problema sin inventar detalles.'},
    )


def ready_transcription(client_user, project, *, expires_at=None):
    return PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint='ready-transcription',
        status='ready',
        result={'transcript': 'El botón Guardar no responde.'},
        expires_at=expires_at or timezone.now() + timedelta(hours=1),
    )


def test_owned_job_hides_a_ready_transcription_from_another_client(client_user, project, admin_user):
    """Fails if one client can fetch another client's ready voice transcript."""
    other = get_user_model().objects.create_user(
        username='ai-other@test.com', email='ai-other@test.com', password='pass12345',
    )
    UserProfile.objects.create(user=other, role=UserProfile.ROLE_CLIENT, created_by=admin_user)
    job = ready_transcription(client_user, project)

    with pytest.raises(NotFound, match='Borrador no encontrado'):
        platform_ai_jobs.owned_job(other, job.pk)


def test_owned_job_rejects_an_expired_transcript_even_for_its_owner(client_user, project):
    """Fails if an owner can recover a voice transcript after its 24-hour expiry."""
    configure_voice(client_user)
    job = ready_transcription(client_user, project, expires_at=timezone.now() - timedelta(seconds=1))

    with pytest.raises(NotFound, match='borrador expiró'):
        platform_ai_jobs.owned_job(client_user, job.pk)


def test_report_draft_reuses_the_ready_cache_for_an_equivalent_new_request(client_user, project, monkeypatch):
    """Fails if equivalent report drafts call a provider instead of reusing a safe cached result."""
    configure_voice(client_user)
    transcription = ready_transcription(client_user, project)
    monkeypatch.setattr(platform_ai_jobs, '_enqueue', lambda job: None)
    first_values = {
        'request_id': uuid4(), 'transcription_id': transcription.pk,
        'transcript': 'El botón Guardar no responde.', 'scenario': 'bug', 'language': 'es',
    }
    first = platform_ai_jobs.create_report_draft(client_user, project.pk, first_values)
    PlatformAIJob.objects.filter(pk=first.pk).update(
        status='ready', result={'proposal': {'title': 'Guardar'}},
    )

    second = platform_ai_jobs.create_report_draft(client_user, project.pk, {
        **first_values, 'request_id': uuid4(),
    })

    assert second.pk != first.pk
    assert second.status == 'ready'
    assert second.result == {'proposal': {'title': 'Guardar'}}


def test_report_draft_returns_the_original_job_for_a_retried_request_id(client_user, project, monkeypatch):
    """Fails if retrying one draft request creates duplicate pending model work."""
    configure_voice(client_user)
    transcription = ready_transcription(client_user, project)
    monkeypatch.setattr(platform_ai_jobs, '_enqueue', lambda job: None)
    values = {
        'request_id': uuid4(), 'transcription_id': transcription.pk,
        'transcript': 'El botón Guardar no responde.', 'scenario': 'bug', 'language': 'es',
    }

    first = platform_ai_jobs.create_report_draft(client_user, project.pk, values)
    retried = platform_ai_jobs.create_report_draft(client_user, project.pk, values)

    assert retried.pk == first.pk
    assert PlatformAIJob.objects.filter(actor=client_user, operation='draft').count() == 1


def test_cleanup_expiry_erases_private_report_content(client_user, project):
    """Fails if expired AI drafts retain transcripts or generated report content."""
    job = PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='draft',
        request_id=uuid4(),
        fingerprint='expired-draft',
        status='ready',
        payload={'transcript': 'Privado'},
        result={'proposal': {'description': 'Privado'}},
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    platform_ai_jobs.cleanup_jobs()
    job.refresh_from_db()

    assert job.status == 'expired'
    assert job.payload == {}
    assert job.result == {}


def test_worker_marks_a_queued_job_failed_when_voice_is_disabled_before_processing(client_user, project):
    """Fails if a queued voice job reaches processing after its feature is switched off."""
    configure_voice(client_user)
    job = PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint='revoked-before-worker',
        status='pending',
        expires_at=timezone.now() + timedelta(hours=1),
    )
    PlatformAISettings.objects.filter(pk=1).update(voice_reporting_enabled=False)

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()

    assert job.status == 'failed'
    assert job.error_code == 'unavailable'
