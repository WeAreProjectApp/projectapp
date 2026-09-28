"""
Frontend prerender rebuild service.

The public site is a static `nuxi generate` build served by Django from
backend/static/frontend/ (see projectapp.views.serve_nuxt). Blog posts and the
canonical additional-modules catalog are prerendered into that build, so their
static HTML goes stale after a publish or catalog change. This service runs the
frontend build and tracks the last successful build in a marker file so
unnecessary rebuilds are skipped.

No service restarts are involved: serve_nuxt reads the files from disk on
every request, and collectstatic only copies hashed assets.
"""
import json
import logging
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(settings.BASE_DIR).parent / 'frontend'
MARKER_PATH = Path(settings.BASE_DIR) / 'logs' / 'frontend-build-marker.json'
BUILD_TIMEOUT_SECONDS = 30 * 60
FAILURE_ALERT_CACHE_KEY = 'frontend_rebuild_failure_alerted'
FAILURE_ALERT_INTERVAL_SECONDS = 60 * 60 * 6


def latest_published_change():
    """Most recent change that affects a prerendered public content surface."""
    from content.models import (
        AdditionalModule,
        AdditionalModuleCategory,
        BlogPost,
        ExplainerVideoSettings,
        VideoResource,
    )

    candidates = []
    for queryset in (
        BlogPost.objects.filter(is_published=True),
        AdditionalModuleCategory.objects.all(),
        AdditionalModule.objects.all(),
        # The video switches change what the prerendered module pages show.
        ExplainerVideoSettings.objects.all(),
        VideoResource.objects.filter(proposal__isnull=True),
    ):
        row = queryset.order_by('-updated_at').first()
        if row:
            candidates.append(row.updated_at)
    return max(candidates) if candidates else None


def last_build_started_at():
    """Start time of the last successful build, or None if never built."""
    try:
        data = json.loads(MARKER_PATH.read_text())
        return parse_datetime(data.get('started_at') or '')
    except (OSError, ValueError):
        return None


def _write_marker(started_at):
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKER_PATH.write_text(json.dumps({'started_at': started_at.isoformat()}))


def rebuild_needed():
    """True when prerendered public content changed after the last build start.

    Using the build *start* time means content edited mid-build (and therefore
    possibly missing from that build's API snapshot) still triggers the next
    rebuild.
    """
    latest = latest_published_change()
    if latest is None:
        return False
    last = last_build_started_at()
    return last is None or latest > last


def _notify_failure(detail):
    """Email staff that the rebuild failed, at most once per alert window.

    The rebuild runs unattended inside Huey; without this, failures only show
    up in logs and published posts silently never reach the public HTML.
    """
    if cache.get(FAILURE_ALERT_CACHE_KEY):
        return
    cache.set(FAILURE_ALERT_CACHE_KEY, True, timeout=FAILURE_ALERT_INTERVAL_SECONDS)

    recipients = list(
        get_user_model().objects.filter(is_staff=True, is_active=True)
        .exclude(email='').values_list('email', flat=True)
    )
    if not recipients:
        logger.warning('[FrontendRebuild] failure alert due but no staff recipients.')
        return

    body = (
        'El rebuild automático del frontend (nuxi generate) está fallando.\n\n'
        'Mientras siga fallando, el contenido publicado no aparece actualizado '
        'en el HTML público que leen los crawlers y los previews de enlaces.\n\n'
        f'Último error:\n{(detail or "(sin detalle)")[:2000]}\n\n'
        'Diagnóstico: backend/logs/blog_publish.log y '
        'journalctl -u projectapp-huey.'
    )
    email = EmailMultiAlternatives(
        subject='ProjectApp: el rebuild del frontend está fallando',
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    EmailDeliveryGateway.send(
        email,
        template_key='frontend_build_failure',
        classification=DeliveryClassification.INTERNAL,
        fail_silently=True,
    )
    logger.info('[FrontendRebuild] failure alert sent to %s', ', '.join(recipients))


def run_frontend_rebuild(force=False):
    """Run the static frontend build and swap it live.

    Returns {'status': 'success'|'skipped'|'failed', 'detail': str}.
    """
    if not settings.FRONTEND_REBUILD_ENABLED:
        return {'status': 'skipped', 'detail': 'FRONTEND_REBUILD_ENABLED is off'}
    if not force and not rebuild_needed():
        return {'status': 'skipped', 'detail': 'no published changes since last build'}

    started_at = timezone.now()
    env = os.environ.copy()
    env.setdefault('PRERENDER_API_ORIGIN', settings.PRERENDER_API_ORIGIN)
    # A production build that silently drops the prerendered posts is a
    # regression — make the build fail instead (see nuxt.config.ts).
    env.setdefault('PRERENDER_REQUIRE_BLOG', '0' if settings.DEBUG else '1')
    # Under the huey service cgroup, Node derives a V8 heap cap too small for
    # `nuxi generate` (observed OOM at ~750MB) — pin it explicitly.
    env.setdefault('NODE_OPTIONS', '--max-old-space-size=2048')

    logger.info(
        '[FrontendRebuild] starting: %s (cwd=%s, api=%s)',
        settings.FRONTEND_BUILD_COMMAND, FRONTEND_DIR, env['PRERENDER_API_ORIGIN'],
    )
    try:
        result = subprocess.run(
            settings.FRONTEND_BUILD_COMMAND,
            shell=True,
            cwd=FRONTEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.error('[FrontendRebuild] build timed out after %ss', BUILD_TIMEOUT_SECONDS)
        detail = f'timeout after {BUILD_TIMEOUT_SECONDS}s'
        _notify_failure(detail)
        return {'status': 'failed', 'detail': detail}

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or '')[-2000:]
        logger.error('[FrontendRebuild] build failed (rc=%s): %s', result.returncode, tail)
        _notify_failure(tail)
        return {'status': 'failed', 'detail': tail}

    if not settings.DEBUG:
        call_command('collectstatic', interactive=False, verbosity=0, clear=True)

    # A success closes the incident: the next failure is a new one and
    # should alert immediately instead of waiting out the dedupe window.
    cache.delete(FAILURE_ALERT_CACHE_KEY)
    _write_marker(started_at)
    logger.info('[FrontendRebuild] success (started_at=%s)', started_at.isoformat())
    return {'status': 'success', 'detail': ''}


def schedule_rebuild_after_publish(delay_seconds=120):
    """Enqueue a frontend rebuild shortly after a publish-state change.

    The small delay lets bursts of consecutive saves coalesce: the first task
    to run rebuilds with everything published so far, and the rest see a
    fresh marker and skip. Never raises — a failed enqueue must not break the
    publish flow it hooks into.
    """
    if not settings.FRONTEND_REBUILD_ENABLED:
        return
    try:
        from content.tasks import rebuild_frontend_prerender
        rebuild_frontend_prerender.schedule(delay=delay_seconds)
        logger.info('[FrontendRebuild] rebuild enqueued (delay=%ss)', delay_seconds)
    except Exception:
        logger.exception('[FrontendRebuild] failed to enqueue rebuild')
