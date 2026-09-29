"""Tests for the frontend prerender regeneration service."""
import ast
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    AdditionalModule,
    AdditionalModuleCategory,
    BlogPost,
    ExplainerVideoSettings,
    FinancingPolicyRevision,
    HourPackage,
)
from content.services import frontend_build

TWENTY_REASONS = [f'reason-{index:02d}' for index in range(20)]


@pytest.fixture
def marker_path(tmp_path, monkeypatch):
    """Point the build marker at a temp file."""
    path = tmp_path / 'frontend-build-marker.json'
    monkeypatch.setattr(frontend_build, 'MARKER_PATH', path)
    return path


@pytest.fixture
def request_path(tmp_path, monkeypatch):
    """Point the regeneration request at a temp file in a missing directory."""
    path = tmp_path / 'logs' / 'frontend-rebuild-request.json'
    monkeypatch.setattr(frontend_build, 'REQUEST_PATH', path)
    return path


@pytest.fixture
def inline_mode(settings):
    settings.FRONTEND_REBUILD_ENABLED = True
    settings.FRONTEND_REBUILD_MODE = 'inline'
    return settings


@pytest.fixture
def request_mode(settings, request_path):
    settings.FRONTEND_REBUILD_ENABLED = True
    settings.FRONTEND_REBUILD_MODE = 'request'
    return request_path


def read_request(path):
    return json.loads(path.read_text())


@pytest.fixture
def published_post(db):
    return BlogPost.objects.create(
        title_es='Post publicado', title_en='Published post',
        excerpt_es='E', excerpt_en='E',
        is_published=True,
    )


@pytest.fixture
def additional_module_category(db):
    return AdditionalModuleCategory.objects.create(
        slug='rebuild-test-category',
        name_es='Pagos',
        name_en='Payments',
        order=999,
    )


def write_marker_now(marker_path):
    marker_path.write_text(json.dumps({'started_at': timezone.now().isoformat()}))


class TestRebuildNeeded:
    def test_false_without_prerendered_content(self, db, marker_path):
        AdditionalModule.objects.all().delete()
        AdditionalModuleCategory.objects.all().delete()
        FinancingPolicyRevision.objects.all().delete()
        HourPackage.objects.all().delete()
        assert frontend_build.rebuild_needed() is False

    def test_true_when_never_built(self, published_post, marker_path):
        assert frontend_build.rebuild_needed() is True

    def test_false_when_marker_is_newer_than_content(self, published_post, marker_path):
        write_marker_now(marker_path)
        assert frontend_build.rebuild_needed() is False

    def test_true_again_after_post_update(self, published_post, marker_path):
        write_marker_now(marker_path)
        published_post.title_es = 'Editado'
        published_post.save()  # bumps updated_at past the marker
        assert frontend_build.rebuild_needed() is True

    def test_true_again_after_catalog_update(
        self, additional_module_category, marker_path,
    ):
        write_marker_now(marker_path)
        additional_module_category.name_es = 'Pagos digitales'
        additional_module_category.save()

        assert frontend_build.rebuild_needed() is True

    def test_true_again_after_explainer_video_switch(self, db, marker_path):
        """Fails if hiding a video leaves the prerendered public page showing it."""
        AdditionalModule.objects.all().delete()
        AdditionalModuleCategory.objects.all().delete()
        write_marker_now(marker_path)
        video_settings = ExplainerVideoSettings.load()
        video_settings.show_financing_video = False
        video_settings.save()

        assert frontend_build.rebuild_needed() is True

    def test_corrupt_marker_counts_as_never_built(self, published_post, marker_path):
        marker_path.write_text('not json{')
        assert frontend_build.rebuild_needed() is True

    def test_true_again_after_policy_revision_publish(self, db, marker_path):
        """Fails if a new financing policy leaves the prerendered Partnership Program stale."""
        current = FinancingPolicyRevision.get_current()
        write_marker_now(marker_path)
        FinancingPolicyRevision.objects.create(version=current.version + 1, financing_months=18)

        assert frontend_build.rebuild_needed() is True

    def test_true_again_after_included_package_rename(self, db, marker_path):
        """Fails if renaming the program's monthly package keeps the old name public."""
        package = HourPackage.objects.get(nationality='COL', hours=60)
        write_marker_now(marker_path)
        package.name_es = 'Paquete Pro Plus'
        package.save()

        assert frontend_build.rebuild_needed() is True

    def test_false_after_unlisted_package_edit(self, db, marker_path):
        """Fails if a package the public program never shows forces a regeneration."""
        package = HourPackage.objects.create(
            nationality='EXT', name_es='Ágil', name_en='Agile', hours=20, hourly_rate=18,
        )
        write_marker_now(marker_path)
        package.hourly_rate = 25
        package.save()

        assert frontend_build.rebuild_needed() is False


class TestRunFrontendRebuild:
    @pytest.fixture(autouse=True)
    def _inline_mode(self, settings):
        settings.FRONTEND_REBUILD_MODE = 'inline'

    def test_skips_when_disabled(self, settings, marker_path):
        settings.FRONTEND_REBUILD_ENABLED = False
        result = frontend_build.run_frontend_rebuild(force=True)
        assert result['status'] == 'skipped'

    def test_skips_when_no_changes(self, db, settings, marker_path):
        settings.FRONTEND_REBUILD_ENABLED = True
        write_marker_now(marker_path)
        result = frontend_build.run_frontend_rebuild()
        assert result['status'] == 'skipped'

    @patch.object(frontend_build, 'call_command')
    @patch.object(frontend_build.subprocess, 'run')
    def test_success_runs_build_and_writes_marker(
        self, mock_run, mock_collectstatic, published_post, settings, marker_path,
    ):
        settings.FRONTEND_REBUILD_ENABLED = True
        settings.DEBUG = False
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        result = frontend_build.run_frontend_rebuild()

        assert result['status'] == 'success'
        assert marker_path.exists()
        assert mock_run.call_args.kwargs['cwd'] == frontend_build.FRONTEND_DIR
        env = mock_run.call_args.kwargs['env']
        assert env['PRERENDER_REQUIRE_BLOG'] == '1'
        assert env['PRERENDER_API_ORIGIN'] == settings.PRERENDER_API_ORIGIN
        mock_collectstatic.assert_called_once_with(
            'collectstatic', interactive=False, verbosity=0, clear=True,
        )
        assert frontend_build.rebuild_needed() is False

    @patch.object(frontend_build, 'call_command')
    @patch.object(frontend_build.subprocess, 'run')
    def test_collectstatic_skipped_in_debug(
        self, mock_run, mock_collectstatic, published_post, settings, marker_path,
    ):
        settings.FRONTEND_REBUILD_ENABLED = True
        settings.DEBUG = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        result = frontend_build.run_frontend_rebuild()

        assert result['status'] == 'success'
        assert mock_run.call_count == 1
        mock_collectstatic.assert_not_called()

    @patch.object(frontend_build.subprocess, 'run')
    def test_build_failure_reports_and_keeps_marker_untouched(
        self, mock_run, published_post, settings, marker_path,
    ):
        settings.FRONTEND_REBUILD_ENABLED = True
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='boom')

        result = frontend_build.run_frontend_rebuild()

        assert result['status'] == 'failed'
        assert 'boom' in result['detail']
        assert not marker_path.exists()
        mock_run.assert_called_once()

    @patch.object(frontend_build.subprocess, 'run')
    def test_build_timeout_reports_failure(
        self, mock_run, published_post, settings, marker_path,
    ):
        settings.FRONTEND_REBUILD_ENABLED = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='npm', timeout=1)

        result = frontend_build.run_frontend_rebuild()

        assert result['status'] == 'failed'
        assert not marker_path.exists()

    @patch.object(frontend_build.subprocess, 'run')
    def test_request_mode_skips_in_process_build(
        self, mock_run, published_post, settings, marker_path,
    ):
        """Fails if a task queued before the switch still runs npm in production."""
        settings.FRONTEND_REBUILD_ENABLED = True
        settings.FRONTEND_REBUILD_MODE = 'request'

        result = frontend_build.run_frontend_rebuild(force=True)

        assert result['status'] == 'skipped'
        assert 'request' in result['detail']
        assert mock_run.call_count == 0
        assert not marker_path.exists()


class TestFailureAlert:
    """Staff email when the in-app (inline) rebuild fails (deduped per incident)."""

    @pytest.fixture(autouse=True)
    def _clear_alert_cache(self, settings):
        settings.FRONTEND_REBUILD_MODE = 'inline'
        cache.delete(frontend_build.FAILURE_ALERT_CACHE_KEY)
        yield
        cache.delete(frontend_build.FAILURE_ALERT_CACHE_KEY)

    @pytest.fixture
    def staff_user(self, db):
        return get_user_model().objects.create_user(
            username='admin_rebuild', password='x', is_staff=True,
            email='admin@projectapp.co',
        )

    def _run_failing(self, settings, force=False):
        settings.FRONTEND_REBUILD_ENABLED = True
        with patch.object(frontend_build.subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='boom')
            return frontend_build.run_frontend_rebuild(force=force)

    def test_failure_emails_staff_with_detail(
        self, staff_user, published_post, settings, marker_path,
    ):
        result = self._run_failing(settings)
        assert result['status'] == 'failed'
        assert len(mail.outbox) == 1
        assert 'admin@projectapp.co' in mail.outbox[0].to
        assert 'boom' in mail.outbox[0].body

    def test_repeat_failure_within_window_alerts_once(
        self, staff_user, published_post, settings, marker_path,
    ):
        self._run_failing(settings)
        self._run_failing(settings)
        assert len(mail.outbox) == 1

    @patch.object(frontend_build, 'call_command')
    def test_success_closes_incident_so_next_failure_alerts_again(
        self, mock_collectstatic, staff_user, published_post, settings, marker_path,
    ):
        self._run_failing(settings)
        with patch.object(frontend_build.subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            assert frontend_build.run_frontend_rebuild(force=True)['status'] == 'success'
        # force: the success above wrote the marker, which would otherwise skip
        self._run_failing(settings, force=True)
        assert len(mail.outbox) == 2
        mock_collectstatic.assert_called_once()

    def test_no_staff_recipients_sends_nothing(
        self, published_post, settings, marker_path,
    ):
        result = self._run_failing(settings)
        assert result['status'] == 'failed'
        assert len(mail.outbox) == 0

    def test_request_mode_never_emails_staff(
        self, staff_user, published_post, settings, marker_path,
    ):
        """Fails if production can still send «el rebuild del frontend está fallando»."""
        settings.FRONTEND_REBUILD_MODE = 'request'

        result = self._run_failing(settings, force=True)

        assert result['status'] == 'skipped'
        assert len(mail.outbox) == 0


class TestScheduleRebuildInlineMode:
    def test_enqueues_task_with_delay(self, inline_mode, request_path):
        with patch('content.tasks.rebuild_frontend_prerender') as mock_task:
            frontend_build.schedule_rebuild_after_publish(reason='blog')
        assert mock_task.schedule.call_count == 1
        assert mock_task.schedule.call_args.kwargs == {'delay': 120}
        assert not request_path.exists()

    def test_noop_when_disabled(self, settings, request_path):
        settings.FRONTEND_REBUILD_ENABLED = False
        with patch('content.tasks.rebuild_frontend_prerender') as mock_task:
            frontend_build.schedule_rebuild_after_publish(reason='blog')
        assert mock_task.schedule.call_count == 0
        assert not request_path.exists()

    def test_enqueue_failure_does_not_raise(self, inline_mode, caplog):
        with patch('content.tasks.rebuild_frontend_prerender') as mock_task:
            mock_task.schedule.side_effect = RuntimeError('redis down')
            frontend_build.schedule_rebuild_after_publish()  # must not raise
        assert 'failed to enqueue rebuild' in caplog.text


class TestScheduleRebuildRequestMode:
    """Production writes the request file the ops toolkit consumes."""

    @freeze_time('2026-09-28 15:00:00')
    def test_writes_request_file(self, request_mode):
        frontend_build.schedule_rebuild_after_publish(reason='blog')

        assert read_request(request_mode) == {
            'requested_at': '2026-09-28T15:00:00+00:00',
            'updated_at': '2026-09-28T15:00:00+00:00',
            'reasons': ['blog'],
        }

    def test_never_enqueues_in_process_build(self, request_mode):
        """Fails if production hands the build to the read-only Huey worker again."""
        with patch('content.tasks.rebuild_frontend_prerender') as mock_task:
            frontend_build.schedule_rebuild_after_publish(reason='additional-modules')

        assert mock_task.schedule.call_count == 0
        assert read_request(request_mode)['reasons'] == ['additional-modules']

    def test_pending_request_keeps_first_requested_at(self, request_mode):
        with freeze_time('2026-09-28 15:00:00'):
            frontend_build.schedule_rebuild_after_publish(reason='blog')
        with freeze_time('2026-09-28 16:30:00'):
            frontend_build.schedule_rebuild_after_publish(reason='partnership-program')

        request = read_request(request_mode)
        assert request['requested_at'] == '2026-09-28T15:00:00+00:00'
        assert request['updated_at'] == '2026-09-28T16:30:00+00:00'
        assert request['reasons'] == ['blog', 'partnership-program']

    def test_repeated_reason_is_recorded_once(self, request_mode):
        frontend_build.schedule_rebuild_after_publish(reason='blog')
        frontend_build.schedule_rebuild_after_publish(reason='explainer-video')
        frontend_build.schedule_rebuild_after_publish(reason='blog')

        assert read_request(request_mode)['reasons'] == ['explainer-video', 'blog']

    def test_reasons_keep_the_latest_twenty(self, request_mode):
        request_mode.parent.mkdir(parents=True)
        request_mode.write_text(json.dumps({
            'requested_at': '2026-09-27T08:00:00+00:00',
            'updated_at': '2026-09-27T09:00:00+00:00',
            'reasons': TWENTY_REASONS,
        }))

        frontend_build.schedule_rebuild_after_publish(reason='blog')

        reasons = read_request(request_mode)['reasons']
        assert len(reasons) == 20
        assert reasons[0] == 'reason-01'
        assert reasons[-1] == 'blog'

    @freeze_time('2026-09-28 15:00:00')
    def test_corrupt_request_is_replaced(self, request_mode):
        request_mode.parent.mkdir(parents=True)
        request_mode.write_text('not json{')

        frontend_build.schedule_rebuild_after_publish(reason='video-resource')

        assert read_request(request_mode) == {
            'requested_at': '2026-09-28T15:00:00+00:00',
            'updated_at': '2026-09-28T15:00:00+00:00',
            'reasons': ['video-resource'],
        }

    def test_failed_replace_keeps_previous_request_intact(self, request_mode, monkeypatch):
        """Fails if a crash mid-write leaves the toolkit a truncated or missing request."""
        previous = {
            'requested_at': '2026-09-27T08:00:00+00:00',
            'updated_at': '2026-09-27T08:00:00+00:00',
            'reasons': ['blog'],
        }
        request_mode.parent.mkdir(parents=True)
        request_mode.write_text(json.dumps(previous))
        monkeypatch.setattr(
            frontend_build.os, 'replace', MagicMock(side_effect=OSError(30, 'Read-only file system')),
        )

        frontend_build.schedule_rebuild_after_publish(reason='partnership-program')

        assert read_request(request_mode) == previous
        assert [path.name for path in request_mode.parent.iterdir()] == [request_mode.name]

    def test_write_failure_does_not_raise(self, request_mode, monkeypatch, caplog):
        monkeypatch.setattr(
            frontend_build.os, 'replace', MagicMock(side_effect=OSError(30, 'Read-only file system')),
        )

        frontend_build.schedule_rebuild_after_publish(reason='blog')  # must not raise

        assert 'failed to write rebuild request (reason=blog)' in caplog.text
        assert not request_mode.exists()

    def test_unknown_mode_writes_request(self, settings, request_path):
        """Fails if a typo in FRONTEND_REBUILD_MODE turns the worker back into a builder."""
        settings.FRONTEND_REBUILD_ENABLED = True
        settings.FRONTEND_REBUILD_MODE = 'inlined'
        with patch('content.tasks.rebuild_frontend_prerender') as mock_task:
            frontend_build.schedule_rebuild_after_publish(reason='blog')

        assert mock_task.schedule.call_count == 0
        assert read_request(request_path)['reasons'] == ['blog']

    def test_production_settings_pin_request_mode(self):
        """Fails if settings_prod lets the environment select the in-process build."""
        source = Path(django_settings.BASE_DIR, 'projectapp', 'settings_prod.py').read_text()
        pinned = [
            node.value for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and [getattr(target, 'id', None) for target in node.targets] == ['FRONTEND_REBUILD_MODE']
        ]

        assert len(pinned) == 1
        assert isinstance(pinned[0], ast.Constant)
        assert pinned[0].value == 'request'


class TestReconcileRebuildRequest:
    def test_requests_regeneration_for_stale_prerender(self, request_mode, published_post, marker_path):
        """Fails if an edit that bypassed the views never reaches the toolkit."""
        assert frontend_build.reconcile_rebuild_request() is True
        assert read_request(request_mode)['reasons'] == ['reconcile']

    def test_skips_fresh_prerender(self, request_mode, published_post, marker_path):
        write_marker_now(marker_path)

        assert frontend_build.reconcile_rebuild_request() is False
        assert not request_mode.exists()
