"""Force-deletion boundaries for private Platform AI project records."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.models import Project
from accounts.models_ai import PlatformAIJob, PlatformAIQuotaReservation, PlatformAIUsage
from content.services.project_force_deletion import (
    ProjectForceDeleteError,
    force_delete_project,
    forced_deletion_preview,
)
from content.storage import get_private_storage


pytestmark = pytest.mark.django_db


@pytest.fixture
def ai_project(make_client_profile):
    profile = make_client_profile(company='AI deletion client')
    return Project.objects.create(name='AI deletion project', client=profile.user)


def ai_job(project, *, audio_name=''):
    return PlatformAIJob.objects.create(
        actor=project.client,
        project=project,
        purpose='voice_report',
        operation='transcription',
        request_id=uuid4(),
        fingerprint='ai-draft-for-force-delete',
        status='ready',
        audio_name=audio_name,
        expires_at=timezone.now() + timedelta(hours=1),
    )


def selected_preview(project, actor):
    initial = forced_deletion_preview(project, actor=actor)
    return forced_deletion_preview(
        project,
        actor=actor,
        delete_keys=[entry['key'] for entry in initial['dependencies']],
    )


def force_delete(project, actor, preview):
    force_delete_project(
        project.pk,
        actor=actor,
        confirmation='DELETE',
        impact_token=preview['impact_token'],
        delete_keys=preview['delete_keys'],
    )


def test_preview_requires_ai_drafts_selection_before_removing_private_job(superuser, ai_project):
    """Fails if force deletion can cascade a private AI draft without an explicit selection."""
    job = ai_job(ai_project)
    preview = forced_deletion_preview(ai_project, actor=superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            ai_project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=[],
        )

    ai_dependency = next(entry for entry in preview['dependencies'] if entry['key'] == 'ai_drafts')
    assert preview['can_delete'] is False
    assert ai_dependency['count'] == 1
    assert ai_dependency['selected'] is False
    assert error.value.code == 'project_force_delete_blocked'
    assert PlatformAIJob.objects.filter(pk=job.pk).exists()


def test_selected_ai_drafts_delete_private_audio_after_commit(
    superuser, ai_project, django_capture_on_commit_callbacks,
):
    """Fails if confirmed force deletion leaves a private dictated audio file behind."""
    storage = get_private_storage()
    audio_name = storage.save('force-delete-ai/dictation.webm', ContentFile(b'private audio'))
    job = ai_job(ai_project, audio_name=audio_name)
    preview = selected_preview(ai_project, superuser)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        force_delete(ai_project, superuser, preview)
        assert storage.exists(audio_name)

    assert not Project.objects.filter(pk=ai_project.pk).exists()
    assert not PlatformAIJob.objects.filter(pk=job.pk).exists()
    assert not storage.exists(audio_name)


def test_usage_metrics_keep_a_null_project_after_force_deletion(superuser, ai_project):
    """Fails if force deletion destroys a content-free AI usage metric."""
    usage = PlatformAIUsage.objects.create(
        actor=ai_project.client,
        project=ai_project,
        purpose='voice_report',
        operation='transcription',
        provider='openai',
        model='gpt-transcribe',
        status='succeeded',
    )
    preview = selected_preview(ai_project, superuser)

    force_delete(ai_project, superuser, preview)
    usage.refresh_from_db()

    assert usage.project_id is None
    assert not Project.objects.filter(pk=ai_project.pk).exists()


def test_quota_reservation_survives_project_force_deletion(superuser, ai_project):
    """Fails if force deletion destroys client quota history with no project relation."""
    quota = PlatformAIQuotaReservation.objects.create(
        actor=ai_project.client,
        request_id=uuid4(),
        purpose='voice_report',
        fingerprint='quota-survives-project-deletion',
        status='consumed',
    )
    preview = selected_preview(ai_project, superuser)

    force_delete(ai_project, superuser, preview)

    assert PlatformAIQuotaReservation.objects.filter(pk=quota.pk).exists()
    assert not Project.objects.filter(pk=ai_project.pk).exists()
