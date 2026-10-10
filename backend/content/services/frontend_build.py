"""
Frontend prerender regeneration.

The public site is a static `nuxi generate` build served by Django from
backend/static/frontend/ (see projectapp.views.serve_nuxt). Blog posts, the
canonical additional-modules catalog, the Partnership Program and Building with Us are
prerendered into that build, so their static HTML goes stale after a publish or
a catalog/policy/presentation change. What happens next depends on
``settings.FRONTEND_REBUILD_MODE``:

``request`` (production)
    The app never builds. The Huey worker runs sandboxed with the project tree
    read-only (only backend/media, backend/logs and backend/private_media are
    writable), so an in-process `nuxi generate` can only fail with EROFS. A
    change writes a regeneration request instead, and the ops toolkit owns the
    build as a typed, integrity-audited operation.

``inline`` (local development)
    The app runs the build itself through the ``rebuild_frontend_prerender``
    Huey task, emailing staff when it fails.

Regeneration contract (``request`` mode)
----------------------------------------
The app writes ``backend/logs/frontend-rebuild-request.json`` atomically
(temp file in the same directory + ``os.replace``)::

    {"requested_at": "<ISO 8601 UTC, first pending request>",
     "updated_at": "<ISO 8601 UTC, latest request>",
     "reasons": ["blog", "partnership-program", ...]}

``requested_at`` survives later requests until the file is consumed;
``reasons`` is deduplicated and keeps the latest ``REQUEST_REASONS_LIMIT``
entries. The regenerator:

1. claims the request before it starts reading content — renames the file away
   (or remembers ``updated_at`` and later deletes it only if unchanged) — so a
   request written while the build runs survives as a new request;
2. regenerates backend/static/frontend and collects static files;
3. on success, writes ``backend/logs/frontend-build-marker.json`` as
   ``{"started_at": "<ISO 8601 UTC build start>"}`` and deletes the claimed
   request; on failure it keeps (or restores) the request for the next attempt.

Any other build that regenerates backend/static/frontend (a deploy) should
write the marker too. ``rebuild_needed()`` compares the marker against the
content timestamps; the nightly reconcile task uses it to re-request a build
when an edit bypassed the views that write requests (admin, shell, bulk
updates).

No service restarts are involved: serve_nuxt reads the files from disk on
every request, and collectstatic only copies hashed assets.
"""
import json
import logging
import os
import subprocess
import tempfile
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
REQUEST_PATH = Path(settings.BASE_DIR) / 'logs' / 'frontend-rebuild-request.json'
REQUEST_REASONS_LIMIT = 20
REQUEST_REASON_MAX_LENGTH = 64
BUILD_TIMEOUT_SECONDS = 30 * 60
FAILURE_ALERT_CACHE_KEY = 'frontend_rebuild_failure_alerted'
FAILURE_ALERT_INTERVAL_SECONDS = 60 * 60 * 6

MODE_INLINE = 'inline'
MODE_REQUEST = 'request'


def rebuild_mode():
    """Configured regeneration mode; anything unrecognized means ``request``.

    Failing towards ``request`` keeps a typo in the environment from turning
    the production worker back into a builder.
    """
    mode = getattr(settings, 'FRONTEND_REBUILD_MODE', MODE_REQUEST)
    if mode in (MODE_INLINE, MODE_REQUEST):
        return mode
    logger.warning(
        '[FrontendRebuild] unknown FRONTEND_REBUILD_MODE %r; using %r', mode, MODE_REQUEST,
    )
    return MODE_REQUEST


def latest_published_change():
    """Latest blog, catalog, policy, video or Building with Us revision change."""
    from content.models import (
        AdditionalModule,
        AdditionalModuleCategory,
        BlogPost,
        BuildingWithUsProgramRevision,
        ExplainerVideoSettings,
        FinancingPolicyRevision,
        HourPackage,
        VideoResource,
    )
    from content.services.financing_program_service import (
        INCLUDED_PACKAGE_HOURS,
        INCLUDED_PACKAGE_NATIONALITY,
    )

    candidates = []
    for queryset, field in (
        (BlogPost.objects.filter(is_published=True), 'updated_at'),
        (AdditionalModuleCategory.objects.all(), 'updated_at'),
        (AdditionalModule.objects.all(), 'updated_at'),
        # The video switches change what the prerendered module pages show.
        (ExplainerVideoSettings.objects.all(), 'updated_at'),
        (VideoResource.objects.filter(proposal__isnull=True), 'updated_at'),
        # Partnership Program: revisions are immutable, so a publish is a new
        # row; the page names the included monthly package from the catalog.
        (FinancingPolicyRevision.objects.all(), 'created_at'),
        # Building with Us publishes append-only presentation revisions.
        (BuildingWithUsProgramRevision.objects.all(), 'created_at'),
        (
            HourPackage.objects.filter(
                nationality=INCLUDED_PACKAGE_NATIONALITY,
                hours=INCLUDED_PACKAGE_HOURS,
            ),
            'updated_at',
        ),
    ):
        row = queryset.order_by(f'-{field}').first()
        if row:
            candidates.append(getattr(row, field))
    return max(candidates) if candidates else None


def last_build_started_at():
    """Start time of the last successful build, or None if never built."""
    try:
        data = json.loads(MARKER_PATH.read_text())
        return parse_datetime(data.get('started_at') or '')
    except (OSError, ValueError, AttributeError):
        return None


def _write_json_atomic(path, payload):
    """Replace ``path`` with ``payload`` so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp',
    )
    try:
        with os.fdopen(fd, 'w') as handle:
            # Not secret, and the toolkit may read it as another user.
            os.fchmod(handle.fileno(), 0o644)
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_marker(started_at):
    _write_json_atomic(MARKER_PATH, {'started_at': started_at.isoformat()})


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


def _read_request():
    try:
        data = json.loads(REQUEST_PATH.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_timestamp(value):
    try:
        return isinstance(value, str) and parse_datetime(value) is not None
    except ValueError:
        return False


def _normalize_reason(reason):
    text = str(reason or '').strip()[:REQUEST_REASON_MAX_LENGTH]
    return text or 'content'


def request_rebuild(reason='content'):
    """Record that the prerendered site must be regenerated by the toolkit.

    Creates or refreshes REQUEST_PATH (see the module docstring for the
    contract) and returns the payload written. Raises on I/O errors; callers
    hooked into a publish flow go through schedule_rebuild_after_publish,
    which never raises. Concurrent writers are last-writer-wins: the worst
    case loses one reason label, never the pending request itself.
    """
    now = timezone.now().isoformat()
    existing = _read_request()

    requested_at = existing.get('requested_at')
    if not _is_timestamp(requested_at):
        requested_at = now

    previous = existing.get('reasons')
    if not isinstance(previous, list):
        previous = []
    reasons = [item for item in previous if isinstance(item, str) and item]
    reason = _normalize_reason(reason)
    reasons = [item for item in reasons if item != reason] + [reason]

    payload = {
        'requested_at': requested_at,
        'updated_at': now,
        'reasons': reasons[-REQUEST_REASONS_LIMIT:],
    }
    _write_json_atomic(REQUEST_PATH, payload)
    return payload


def _notify_failure(detail):
    """Email staff that the in-app rebuild failed, at most once per alert window.

    Only the ``inline`` mode (local development) builds in-process, so only it
    can reach this alert; production regeneration belongs to the ops toolkit.
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
    """Run the static frontend build in-process and swap it live (inline mode).

    Returns {'status': 'success'|'skipped'|'failed', 'detail': str}. In
    ``request`` mode it always skips, so a task queued before the switch can
    neither build nor alert.
    """
    if not settings.FRONTEND_REBUILD_ENABLED:
        return {'status': 'skipped', 'detail': 'FRONTEND_REBUILD_ENABLED is off'}
    if rebuild_mode() != MODE_INLINE:
        return {
            'status': 'skipped',
            'detail': 'FRONTEND_REBUILD_MODE is request: the ops toolkit regenerates the build',
        }
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


def schedule_rebuild_after_publish(delay_seconds=120, reason='content'):
    """Ask for the prerendered site to be regenerated after a content change.

    ``request`` mode writes the regeneration request the ops toolkit consumes
    (``delay_seconds`` does not apply: the toolkit coalesces on its own).
    ``inline`` mode enqueues the in-app build with a small delay so bursts of
    consecutive saves coalesce: the first task to run rebuilds with everything
    published so far, and the rest see a fresh marker and skip.

    ``reason`` is a short label of the surface that changed ('blog',
    'additional-modules', 'explainer-video', 'video-resource',
    'partnership-program', ...). Never raises — a failed request must not break
    the publish flow it hooks into.
    """
    if not settings.FRONTEND_REBUILD_ENABLED:
        return
    mode = rebuild_mode()
    if mode == MODE_INLINE:
        try:
            from content.tasks import rebuild_frontend_prerender
            rebuild_frontend_prerender.schedule(delay=delay_seconds)
            logger.info(
                '[FrontendRebuild] rebuild enqueued (delay=%ss, reason=%s)',
                delay_seconds, reason,
            )
        except Exception:
            logger.exception('[FrontendRebuild] failed to enqueue rebuild (reason=%s)', reason)
        return
    try:
        request_rebuild(reason)
        logger.info('[FrontendRebuild] regeneration requested (reason=%s)', reason)
    except Exception:
        logger.exception('[FrontendRebuild] failed to write rebuild request (reason=%s)', reason)


def reconcile_rebuild_request():
    """Re-request a regeneration when content changed after the last build.

    Safety net for edits that bypass the views writing requests (Django admin,
    shell, bulk updates). Returns True when a request was issued.
    """
    if not settings.FRONTEND_REBUILD_ENABLED or not rebuild_needed():
        return False
    schedule_rebuild_after_publish(reason='reconcile')
    return True
