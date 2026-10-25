"""Lifecycle guarantees for private Platform AI jobs."""
import json
import wave
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, Throttled, ValidationError

from accounts.models import (
    DeliveryPublication,
    DeliveryStage,
    Project,
    Requirement,
    UserProfile,
)
from accounts.models_ai import (
    PlatformAICredential,
    PlatformAIJob,
    PlatformAIQuotaReservation,
    PlatformAISettings,
    PlatformAITemplate,
    PlatformAIUsage,
)
from accounts.services import platform_ai_jobs
from accounts.services.platform_ai import AIConflict
from accounts.services.platform_ai_quota import reserve
from accounts.tests.delivery_helpers import GUIDE, build_delivery_context, publish

pytestmark = pytest.mark.django_db


REPORT_PROPOSAL = {
    'title': 'Guardar no responde',
    'description': 'El usuario no puede guardar.',
    'expected_behavior': 'El botón debe guardar.',
    'actual_behavior': 'El botón no hace nada.',
    'module_or_screen': 'Etapa de revisión',
    'message': '',
    'steps_to_reproduce': ['Abrir etapa', 'Pulsar Guardar'],
    'missing_details': [],
}


def configure_voice(client_user, *, daily_limit=20):
    """Enable voice reporting with explicit credentials, limits and templates."""
    UserProfile.objects.filter(user=client_user).update(voice_reporting_enabled=True)
    PlatformAISettings.objects.update_or_create(
        pk=1,
        defaults={
            'voice_reporting_enabled': True,
            'daily_user_audio_limit': daily_limit,
            'monthly_audio_limit': 1000,
            'report_cache_enabled': True,
            'report_cache_hours': 24,
        },
    )
    for provider in ('anthropic', 'openai'):
        PlatformAICredential.objects.update_or_create(
            provider=provider,
            defaults={'encrypted_value': 'configured'},
        )
    PlatformAITemplate.objects.get_or_create(
        family='report', scenario='voice_base', language='es',
        defaults={'content': 'Organiza únicamente lo dicho.'},
    )
    PlatformAITemplate.objects.get_or_create(
        family='report', scenario='bug', language='es',
        defaults={'content': 'Describe el problema sin inventar detalles.'},
    )


def ready_transcription(client_user, project):
    """Create a private transcription ready for report drafting."""
    return PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint=f'ready-{uuid4().hex}',
        status='ready',
        result={'transcript': 'El botón Guardar no responde.'},
        expires_at=timezone.now() + timedelta(hours=1),
    )


def pending_transcription(client_user, project):
    """Store a private WAV and reserve quota for a queued transcription."""
    reservation = reserve(client_user, uuid4(), 'voice_report', uuid4().hex)
    storage = storages['private']
    audio_name = storage.save(
        f'platform-ai/queued-{uuid4()}.wav',
        SimpleUploadedFile('queued.wav', private_wav(), content_type='audio/wav'),
    )
    return PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint=f'pending-{uuid4().hex}',
        audio_name=audio_name,
        payload={'quota_id': str(reservation.pk)},
        expires_at=timezone.now() + timedelta(hours=1),
    ), reservation


def private_wav(*, sample=100):
    """Build a short valid PCM recording for a private worker input."""
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as item:
        item.setparams((1, 2, 16000, 4000, 'NONE', 'not compressed'))
        item.writeframes(sample.to_bytes(2, 'little', signed=True) * 4000)
    return buffer.getvalue()


def report_values(transcription):
    """Build a reviewed transcript submitted for a bug draft."""
    return {
        'request_id': uuid4(),
        'transcription_id': transcription.pk,
        'transcript': 'El botón Guardar no responde.',
        'scenario': 'bug',
        'language': 'es',
    }


def pending_report_draft(client_user, project, fingerprint):
    """Create a queued report job with an explicit cache fingerprint."""
    return PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='draft',
        request_id=uuid4(),
        fingerprint=fingerprint,
        payload={
            'policy': {'model': 'claude-haiku-5-5'},
            'instructions': 'Return report JSON.',
            'transcript': 'Guardar no responde.',
            'context': {'project_id': project.pk},
            'scenario': 'bug',
        },
        expires_at=timezone.now() + timedelta(hours=1),
    )


class SuccessfulReportResponse:
    """Represent a completed provider response with concrete cache usage."""

    status_code = 200

    @staticmethod
    def json():
        """Return the fixed JSON payload supplied by the provider fixture."""
        return {
            'content': [{'type': 'text', 'text': json.dumps(REPORT_PROPOSAL)}],
            'usage': {
                'input_tokens': 100,
                'output_tokens': 50,
                'cache_read_input_tokens': 30,
                'cache_creation_input_tokens': 10,
            },
        }


def mock_successful_report_provider(monkeypatch):
    """Replace only the HTTP and credential boundaries of report generation."""
    monkeypatch.setattr('accounts.services.platform_ai_providers.credential', lambda provider: 'provider-key')
    monkeypatch.setattr('accounts.services.platform_ai_providers.requests.post', lambda *args, **kwargs: SuccessfulReportResponse())


@pytest.fixture
def published_delivery_context():
    """Build one client-visible delivery hierarchy for report-context tests."""
    context = build_delivery_context()
    publish(context)
    return context


def visible_sibling_stage(context):
    """Publish a second stage so context mismatch validation uses real visibility."""
    stage = DeliveryStage.objects.create(phase=context.phase, key='sibling', title='Etapa alternativa')
    requirement = Requirement.objects.create(stage=stage, key='sibling-guide', title='Guía alternativa', guide=GUIDE)
    DeliveryPublication.objects.create(
        stage=stage,
        round=1,
        published_by=context.admin,
        payload={'requirements': [{'id': requirement.pk}]},
    )
    return stage


def exhaust_daily_generation_allowance(client_user, project):
    """Create the three terminal drafts permitted by one daily audio allowance."""
    expiry = timezone.now() + timedelta(hours=1)
    PlatformAIJob.objects.bulk_create([
        PlatformAIJob(
            actor=client_user, project=project, purpose='voice_report', operation='draft',
            request_id=uuid4(), fingerprint='prior-draft-one', status='failed', expires_at=expiry,
        ),
        PlatformAIJob(
            actor=client_user, project=project, purpose='voice_report', operation='draft',
            request_id=uuid4(), fingerprint='prior-draft-two', status='failed', expires_at=expiry,
        ),
        PlatformAIJob(
            actor=client_user, project=project, purpose='voice_report', operation='draft',
            request_id=uuid4(), fingerprint='prior-draft-three', status='failed', expires_at=expiry,
        ),
    ])


def test_report_context_requires_a_requirement_for_a_change(client_user, project):
    """Fails if a change report can be drafted without its source requirement."""
    with pytest.raises(ValidationError) as error:
        platform_ai_jobs.report_context(project, client_user, {'scenario': 'change'})

    assert error.value.detail['source_requirement_id'] == 'Selecciona el requerimiento al que aplica el cambio.'


def test_report_context_requires_a_stage_for_an_observation(client_user, project):
    """Fails if a stage observation can be drafted without a visible stage."""
    with pytest.raises(ValidationError) as error:
        platform_ai_jobs.report_context(project, client_user, {'scenario': 'stage_observation'})

    assert error.value.detail['stage_id'] == 'Selecciona una etapa o requerimiento.'


def test_report_context_snapshots_a_visible_requirement(published_delivery_context):
    """Fails if a voice change draft loses the published requirement identity or version."""
    context = published_delivery_context

    result = platform_ai_jobs.report_context(context.project, context.client, {
        'scenario': 'change', 'source_requirement_id': context.first.pk,
    })

    assert result == {
        'project_id': context.project.pk,
        'requirement_id': context.first.pk,
        'requirement_title': 'Guardar registro',
        'requirement_version': context.first.version,
        'stage_id': context.stage.pk,
        'stage_title': 'Etapa',
    }


def test_report_context_hides_an_unpublished_requirement(published_delivery_context):
    """Fails if a client can use an editorial requirement absent from their publication."""
    context = published_delivery_context
    hidden = Requirement.objects.create(stage=context.stage, key='hidden-guide', title='Guía privada', guide=GUIDE)

    with pytest.raises(NotFound, match='Requerimiento no disponible'):
        platform_ai_jobs.report_context(context.project, context.client, {
            'scenario': 'change', 'source_requirement_id': hidden.pk,
        })

    assert context.stage.publications.count() == 1


def test_report_context_rejects_a_stage_inconsistent_with_the_requirement(published_delivery_context):
    """Fails if a voice change connects a published requirement to another visible stage."""
    context = published_delivery_context
    sibling = visible_sibling_stage(context)
    visible_context = platform_ai_jobs.report_context(context.project, context.client, {
        'scenario': 'stage_observation', 'stage_id': sibling.pk,
    })

    with pytest.raises(NotFound, match='Etapa no disponible'):
        platform_ai_jobs.report_context(context.project, context.client, {
            'scenario': 'change', 'source_requirement_id': context.first.pk, 'stage_id': sibling.pk,
        })

    assert visible_context == {
        'project_id': context.project.pk,
        'stage_id': sibling.pk,
        'stage_title': 'Etapa alternativa',
    }


def test_report_context_snapshots_a_visible_stage_observation(published_delivery_context):
    """Fails if a stage observation draft loses its published stage destination."""
    context = published_delivery_context

    result = platform_ai_jobs.report_context(context.project, context.client, {
        'scenario': 'stage_observation', 'stage_id': context.stage.pk,
    })

    assert result == {
        'project_id': context.project.pk,
        'stage_id': context.stage.pk,
        'stage_title': 'Etapa',
    }


@freeze_time('2026-10-24 15:00:00')
def test_daily_audio_limit_blocks_another_recording_before_storage(client_user, project):
    """Fails if the per-client daily recording cap permits a second upload."""
    configure_voice(client_user, daily_limit=1)
    PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint='today-audio',
        status='ready',
        expires_at=timezone.now() + timedelta(hours=1),
    )
    values = {
        'purpose': 'voice_report',
        'project_id': project.pk,
        'request_id': uuid4(),
        'audio': SimpleUploadedFile('voice.webm', b'\x1aE\xdf\xa3short-recording', content_type='audio/webm'),
    }

    with pytest.raises(Throttled, match='límite de notas de voz'):
        platform_ai_jobs.create_transcription(client_user, values)

    assert PlatformAIJob.objects.filter(actor=client_user, operation='transcription').count() == 1


@freeze_time('2026-10-24 15:00:00')
def test_transcription_request_id_rejects_different_audio_without_another_reservation(client_user, project, monkeypatch):
    """Fails if retrying an upload ID with different audio stores another private recording or spends quota twice."""
    configure_voice(client_user)
    monkeypatch.setattr(platform_ai_jobs, '_enqueue', lambda job: None)
    request_id = uuid4()
    first = {
        'purpose': 'voice_report', 'project_id': project.pk, 'request_id': request_id,
        'audio': SimpleUploadedFile('first.wav', private_wav(), content_type='audio/wav'),
    }
    second = {
        **first,
        'audio': SimpleUploadedFile('second.wav', private_wav(sample=200), content_type='audio/wav'),
    }

    created = platform_ai_jobs.create_transcription(client_user, first)
    with pytest.raises(AIConflict, match='identificador ya pertenece'):
        platform_ai_jobs.create_transcription(client_user, second)

    assert PlatformAIJob.objects.filter(actor=client_user, operation='transcription').count() == 1
    assert PlatformAIQuotaReservation.objects.filter(actor=client_user).count() == 1
    with storages['private'].open(created.audio_name, 'rb') as audio:
        assert audio.read() == private_wav()


@freeze_time('2026-10-24 15:00:00')
def test_active_job_blocks_a_second_report_draft(client_user, project, monkeypatch):
    """Fails if one client can start a report draft while another AI job is pending."""
    configure_voice(client_user)
    transcription = ready_transcription(client_user, project)
    PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='draft',
        request_id=uuid4(),
        fingerprint='still-processing',
        status='pending',
        expires_at=timezone.now() + timedelta(hours=1),
    )
    monkeypatch.setattr(platform_ai_jobs, '_enqueue', lambda job: None)

    with pytest.raises(Throttled, match='procesándose'):
        platform_ai_jobs.create_report_draft(client_user, project.pk, report_values(transcription))

    assert PlatformAIJob.objects.filter(actor=client_user, operation='draft').count() == 1


@freeze_time('2026-10-24 15:00:00')
def test_daily_generation_limit_blocks_a_new_uncached_draft(client_user, project, monkeypatch):
    """Fails if more than three daily report drafts per audio allowance reach model processing."""
    configure_voice(client_user, daily_limit=1)
    transcription = ready_transcription(client_user, project)
    exhaust_daily_generation_allowance(client_user, project)

    def forbidden_enqueue(job):
        pytest.fail('A daily-limit rejection must not enqueue model work.')

    monkeypatch.setattr(platform_ai_jobs, '_enqueue', forbidden_enqueue)

    with pytest.raises(Throttled, match='límite diario de generación'):
        platform_ai_jobs.create_report_draft(client_user, project.pk, report_values(transcription))

    assert PlatformAIJob.objects.filter(actor=client_user, operation='draft').count() == 3


def test_worker_refunds_a_job_after_project_ownership_changes(client_user, project, admin_user, monkeypatch):
    """Fails if queued audio is billed after its project moves to another client."""
    configure_voice(client_user)
    job, reservation = pending_transcription(client_user, project)
    other = get_user_model().objects.create_user(
        username='lifecycle-other@test.com', email='lifecycle-other@test.com', password='pass12345',
    )
    UserProfile.objects.create(user=other, role=UserProfile.ROLE_CLIENT, created_by=admin_user)
    Project.objects.filter(pk=project.pk).update(client=other)
    monkeypatch.setattr(
        'accounts.services.platform_ai_providers.transcribe',
        lambda **kwargs: (_ for _ in ()).throw(AssertionError('provider must not receive revoked audio')),
    )

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()
    reservation.refresh_from_db()

    assert job.status == 'failed'
    assert job.error_code == 'unavailable'
    assert reservation.status == 'refunded'


def test_post_transcription_shutdown_preserves_consumed_quota(client_user, project, monkeypatch):
    """Fails if a later shutdown reveals the transcript or refunds completed transcription work."""
    configure_voice(client_user)
    job, reservation = pending_transcription(client_user, project)
    audio_name = job.audio_name
    seen = {}
    monkeypatch.setattr('accounts.services.platform_ai_audio.inspect_audio', lambda path: 12.5)

    def transcribe_then_disable(**kwargs):
        seen['audio_header'] = kwargs['audio'].read(4)
        PlatformAISettings.objects.filter(pk=1).update(voice_reporting_enabled=False)
        return 'El botón Guardar no responde.'

    monkeypatch.setattr('accounts.services.platform_ai_providers.transcribe', transcribe_then_disable)

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()
    reservation.refresh_from_db()

    assert job.status == 'failed'
    assert job.error_code == 'unavailable'
    assert job.result == {}
    assert job.audio_name == ''
    assert not storages['private'].exists(audio_name)
    assert reservation.status == 'consumed'
    assert seen['audio_header'] == b'RIFF'


def test_worker_consumes_reservation_after_a_successful_transcription(client_user, project, monkeypatch):
    """Fails if a completed transcription does not consume its shared request reservation."""
    configure_voice(client_user)
    job, reservation = pending_transcription(client_user, project)
    seen = {}
    monkeypatch.setattr('accounts.services.platform_ai_audio.inspect_audio', lambda path: 12.5)

    def transcribe_audio(**kwargs):
        seen['audio_header'] = kwargs['audio'].read(4)
        return 'El botón Guardar no responde.'

    monkeypatch.setattr('accounts.services.platform_ai_providers.transcribe', transcribe_audio)

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()
    reservation.refresh_from_db()

    assert job.status == 'ready'
    assert job.result == {'transcript': 'El botón Guardar no responde.', 'audio_seconds': 12.5}
    assert reservation.status == 'consumed'
    assert seen['audio_header'] == b'RIFF'


def test_worker_refunds_a_provider_failure_without_storing_error_content(client_user, project, monkeypatch):
    """Fails if a transcription failure retains provider text or consumes the request quota."""
    configure_voice(client_user)
    job, reservation = pending_transcription(client_user, project)
    seen = {}
    monkeypatch.setattr('accounts.services.platform_ai_audio.inspect_audio', lambda path: 12.5)

    def failing_transcription(**kwargs):
        seen['audio_header'] = kwargs['audio'].read(4)
        raise RuntimeError('provider returned transcript content')

    monkeypatch.setattr('accounts.services.platform_ai_providers.transcribe', failing_transcription)

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()
    reservation.refresh_from_db()

    assert job.status == 'failed'
    assert job.error_code == 'processing_failed'
    assert job.result == {}
    assert reservation.status == 'refunded'
    assert seen['audio_header'] == b'RIFF'


@freeze_time('2026-10-24 15:00:00')
def test_worker_rejects_an_invalid_draft_schema(client_user, project, monkeypatch):
    """Fails if malformed model JSON is exposed as a report proposal."""
    configure_voice(client_user)
    job = pending_report_draft(client_user, project, 'invalid-draft-schema')
    monkeypatch.setattr(
        'accounts.services.platform_ai_providers.generate_text',
        lambda **kwargs: ('{"title":"incomplete"}', uuid4()),
    )

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()

    assert job.status == 'failed'
    assert job.error_code == 'processing_failed'
    assert job.result == {}


@freeze_time('2026-10-24 15:00:00')
def test_worker_records_concrete_usage_for_a_successful_report_draft(client_user, project, monkeypatch):
    """Fails if a completed report draft loses provider token, cache, or cost accounting."""
    configure_voice(client_user)
    job = pending_report_draft(client_user, project, 'usage-accounted-draft')
    mock_successful_report_provider(monkeypatch)

    platform_ai_jobs.process_job(job.pk)
    job.refresh_from_db()
    usage = PlatformAIUsage.objects.get(actor=client_user, operation='generation')

    assert job.status == 'ready'
    assert job.result == {'proposal': REPORT_PROPOSAL}
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cache_read_tokens == 30
    assert usage.cache_write_tokens == 10
    assert usage.estimated_cost == Decimal('0.00003655')


@freeze_time('2026-10-24 15:00:00')
def test_discarding_a_ready_transcription_keeps_its_consumed_quota(client_user, project):
    """Fails if discarding a completed transcript refunds a request that already used provider work."""
    configure_voice(client_user)
    reservation = reserve(client_user, uuid4(), 'voice_report', 'completed-audio')
    PlatformAIQuotaReservation.objects.filter(pk=reservation.pk).update(status='consumed')
    storage = storages['private']
    audio_name = storage.save(
        f'platform-ai/test-{uuid4()}.webm',
        SimpleUploadedFile('completed.webm', b'private-audio', content_type='audio/webm'),
    )
    job = PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint='completed-audio',
        status='ready',
        audio_name=audio_name,
        payload={'quota_id': str(reservation.pk)},
        result={'transcript': 'Privado'},
        expires_at=timezone.now() + timedelta(hours=1),
    )

    platform_ai_jobs.discard_job(client_user, job.pk)
    job.refresh_from_db()
    reservation.refresh_from_db()

    assert job.status == 'cancelled'
    assert job.payload == {}
    assert job.result == {}
    assert job.audio_name == ''
    assert storage.exists(audio_name) is False
    assert reservation.status == 'consumed'


@freeze_time('2026-10-24 15:00:00')
def test_cleanup_refunds_a_stale_pending_recording(client_user, project):
    """Fails if a stuck recording remains active and charged after the worker timeout."""
    configure_voice(client_user)
    job, reservation = pending_transcription(client_user, project)
    PlatformAIJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(minutes=51))

    platform_ai_jobs.cleanup_jobs()
    job.refresh_from_db()
    reservation.refresh_from_db()

    assert job.status == 'cancelled'
    assert job.payload == {}
    assert reservation.status == 'refunded'


@freeze_time('2026-10-24 15:00:00')
def test_cleanup_deletes_terminal_job_metadata_after_retention_period(client_user, project):
    """Fails if terminal private AI job metadata survives longer than the documented retention period."""
    job = PlatformAIJob.objects.create(
        actor=client_user,
        project=project,
        purpose='voice_report',
        operation='draft',
        request_id=uuid4(),
        fingerprint='old-terminal-metadata',
        status='expired',
        expires_at=timezone.now() - timedelta(days=1),
    )
    PlatformAIJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=63))

    platform_ai_jobs.cleanup_jobs()

    assert PlatformAIJob.objects.filter(pk=job.pk).count() == 0
