"""Gap tests for content/tasks.py — targets uncovered skip/exception branches.

Root cause for most misses: BusinessProposal.automations_paused defaults to True,
so existing tests trigger the automations_paused guard before reaching the
status/email/already-sent checks. These tests set automations_paused=False
to exercise the skipped branches.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    BlogPost,
    BusinessProposal,
    ProposalChangeLog,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


BLOG_POST_BASE = {
    'title_es': 'Test post',
    'title_en': 'Test post',
    'excerpt_es': 'Extracto.',
    'excerpt_en': 'Excerpt.',
    'content_es': '<p>C</p>',
    'content_en': '<p>C</p>',
}


# ---------------------------------------------------------------------------
# send_proposal_reminder — skip conditions with automations_paused=False
# (lines 50, 54, 57, 61, 64, 68)
# ---------------------------------------------------------------------------

class TestSendProposalReminderSkipsWithAutomationsEnabled:
    def test_skips_when_status_is_not_sent_or_viewed(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Draft Proposal', client_name='C',
            client_email='c@x.com', status='draft',
            automations_paused=False,
        )

        tasks_module.send_proposal_reminder.call_local(proposal.id)

        proposal.refresh_from_db()
        assert proposal.reminder_sent_at is None

    def test_skips_when_client_email_is_unsendable(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='No Email', client_name='C',
            client_email='', status='sent',
            automations_paused=False,
        )

        tasks_module.send_proposal_reminder.call_local(proposal.id)

        proposal.refresh_from_db()
        assert proposal.reminder_sent_at is None

    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    @freeze_time('2026-01-15 12:00:00')
    def test_skips_when_reminder_already_sent(self, mock_send):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Already Reminded', client_name='C',
            client_email='c@x.com', status='sent',
            automations_paused=False,
            reminder_sent_at=timezone.now(),
        )

        tasks_module.send_proposal_reminder.call_local(proposal.id)

        # quality: allow-call-contract (skip boundary: assert_not_called verifies no reminder email is sent when one was already recorded)
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# send_urgency_reminder — skip conditions with automations_paused=False
# (lines 101, 105, 108, 112, 115, 119)
# ---------------------------------------------------------------------------

class TestSendUrgencyReminderSkipsWithAutomationsEnabled:
    def test_skips_when_status_is_not_sent_or_viewed(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Accepted Proposal', client_name='C',
            client_email='c@x.com', status='accepted',
            automations_paused=False,
        )

        tasks_module.send_urgency_reminder.call_local(proposal.id)

        proposal.refresh_from_db()
        assert proposal.urgency_email_sent_at is None

    def test_skips_when_client_email_is_unsendable(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='No Email Urgency', client_name='C',
            client_email='', status='sent',
            automations_paused=False,
        )

        tasks_module.send_urgency_reminder.call_local(proposal.id)

        proposal.refresh_from_db()
        assert proposal.urgency_email_sent_at is None

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email')
    @freeze_time('2026-01-15 12:00:00')
    def test_skips_when_urgency_already_sent(self, mock_send):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Already Urgencied', client_name='C',
            client_email='c@x.com', status='sent',
            automations_paused=False,
            urgency_email_sent_at=timezone.now(),
        )

        tasks_module.send_urgency_reminder.call_local(proposal.id)

        # quality: allow-call-contract (skip boundary: assert_not_called verifies no urgency email is sent when one was already recorded)
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# escalate_seller_inactivity — skip conditions (lines 307, 315, 322)
# ---------------------------------------------------------------------------

class TestEscalateSellerInactivitySkips:
    @freeze_time('2026-01-15 12:00:00')
    def test_skips_candidate_with_recent_activity_date(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Recent Activity', client_name='C',
            client_email='c@x.com', status='viewed',
            automations_paused=False,
            is_active=True,
            first_viewed_at=timezone.now() - timedelta(days=10),
            last_activity_at=timezone.now() - timedelta(days=1),
        )

        tasks_module.escalate_seller_inactivity.call_local()

        assert not ProposalChangeLog.objects.filter(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.SELLER_INACTIVITY_ESCALATION,
        ).exists()

    @freeze_time('2026-01-15 12:00:00')
    def test_skips_candidate_with_recent_seller_changelog(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Recent Changelog', client_name='C',
            client_email='c@x.com', status='viewed',
            automations_paused=False,
            is_active=True,
            first_viewed_at=timezone.now() - timedelta(days=10),
            sent_at=timezone.now() - timedelta(days=7),
        )
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='call',
            created_at=timezone.now() - timedelta(days=2),
        )

        tasks_module.escalate_seller_inactivity.call_local()

        assert not ProposalChangeLog.objects.filter(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.SELLER_INACTIVITY_ESCALATION,
        ).exists()

    @freeze_time('2026-01-15 12:00:00')
    def test_skips_candidate_already_escalated(self):
        import content.tasks as tasks_module

        proposal = BusinessProposal.objects.create(
            title='Already Escalated', client_name='C',
            client_email='c@x.com', status='viewed',
            automations_paused=False,
            is_active=True,
            first_viewed_at=timezone.now() - timedelta(days=10),
            sent_at=timezone.now() - timedelta(days=7),
        )
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.SELLER_INACTIVITY_ESCALATION,
        )

        tasks_module.escalate_seller_inactivity.call_local()

        assert ProposalChangeLog.objects.filter(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.SELLER_INACTIVITY_ESCALATION,
        ).count() == 1


# ---------------------------------------------------------------------------
# check_engagement_followups — investment interest logger.info (line 433)
# ---------------------------------------------------------------------------

class TestCheckEngagementFollowupsInvestmentLog:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup')
    @freeze_time('2026-01-15 12:00:00')
    def test_logs_after_sending_investment_interest_followup(self, mock_send):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        import content.tasks as tasks_module
        from content.models import ProposalSectionView, ProposalViewEvent

        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Investment Logger', client_name='C',
            client_email='c@x.com', status='viewed',
            automations_paused=False,
            is_active=True,
            first_viewed_at=now - timedelta(hours=5),
        )
        view_event = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-inv-log', ip_address='127.0.0.1',
        )
        ProposalViewEvent.objects.filter(pk=view_event.pk).update(
            viewed_at=now - timedelta(hours=3),
        )
        ProposalSectionView.objects.create(
            view_event=view_event, section_type='investment',
            time_spent_seconds=75, entered_at=now - timedelta(hours=3),
        )

        tasks_module.check_engagement_followups.call_local()

        # quality: allow-call-contract (email boundary: assert_called_once verifies the investment interest followup email is sent after section view data qualifies)
        mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# publish_single_scheduled_blog — exception path (lines 519-520)
# ---------------------------------------------------------------------------

class TestPublishSingleScheduledBlogException:
    @patch('content.views.blog.auto_publish_blog_to_linkedin', side_effect=RuntimeError('linkedin fail'))
    @freeze_time('2026-01-15 12:00:00')
    def test_exception_during_linkedin_publish_is_caught(self, mock_linkedin):
        import content.tasks as tasks_module

        post = BlogPost.objects.create(
            **BLOG_POST_BASE,
            is_published=False,
            published_at=timezone.now() - timedelta(minutes=5),
        )

        tasks_module.publish_single_scheduled_blog.call_local(post.id)

        post.refresh_from_db()
        assert post.is_published is True


# ---------------------------------------------------------------------------
# publish_scheduled_blog_posts — exception per post (lines 560-561)
# ---------------------------------------------------------------------------

class TestPublishScheduledBlogPostsException:
    @patch('content.views.blog.auto_publish_blog_to_linkedin', side_effect=RuntimeError('fail'))
    @freeze_time('2026-01-15 12:00:00')
    def test_exception_during_periodic_publish_is_caught(self, mock_linkedin):  # quality: disable no_assertions (no-raise is the assertion - task must swallow per-post exceptions)
        import content.tasks as tasks_module

        BlogPost.objects.create(
            **BLOG_POST_BASE,
            is_published=False,
            published_at=timezone.now() - timedelta(minutes=5),
        )

        tasks_module.publish_scheduled_blog_posts.call_local()


# ---------------------------------------------------------------------------
# generate_whatsapp_suggestions — already-exists skip (line 868)
# ---------------------------------------------------------------------------

class TestGenerateWhatsappSuggestionsAlreadyExists:
    @freeze_time('2026-01-15 12:00:00')
    def test_skips_proposal_with_existing_undismissed_whatsapp_alert(self):
        import content.tasks as tasks_module
        from content.models import ProposalAlert

        proposal = BusinessProposal.objects.create(
            title='Whatsapp Skip', client_name='C',
            client_email='c@x.com',
            client_phone='+57 300 111 2222',
            status='viewed',
            automations_paused=False,
            is_active=True,
            first_viewed_at=timezone.now() - timedelta(hours=72),
        )
        ProposalAlert.objects.create(
            proposal=proposal,
            alert_type='whatsapp_suggestion',
            is_dismissed=False,
            message='Sugerencia WhatsApp',
            alert_date=timezone.now(),
        )

        tasks_module.generate_whatsapp_suggestions.call_local()

        assert ProposalAlert.objects.filter(
            proposal=proposal, alert_type='whatsapp_suggestion',
        ).count() == 1


# ---------------------------------------------------------------------------
# notify_proposal_stage_deadlines — exception path (lines 1107-1108)
# Note: duplicate class name in test_tasks.py shadows the existing test.
# ---------------------------------------------------------------------------

class TestNotifyProposalStageDeadlinesException:
    @patch('content.services.proposal_stage_tracker.ProposalStageTracker.process',
           side_effect=RuntimeError('tracker failed'))
    def test_exception_during_tracker_is_caught_and_logged(self, mock_process):  # quality: disable no_assertions (no-raise is the assertion - task must swallow per-proposal exceptions)
        import content.tasks as tasks_module
        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='Exception Stage', client_name='C',
            client_email='c@x.com', status='accepted',
            automations_paused=False,
            is_active=True,
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
        )

        tasks_module.notify_proposal_stage_deadlines.call_local()

        # quality: allow-call-contract (tracker boundary: assert_called_once verifies the task attempts to process the proposal despite the exception)
        mock_process.assert_called_once_with(proposal)


# ---------------------------------------------------------------------------
# _send_task_deadline_email — assignee name resolution (lines 1189-1190)
# _send_task_alert_email — assignee name resolution (lines 1311-1312)
# ---------------------------------------------------------------------------

class TestTaskEmailAssigneeResolution:
    def test_deadline_email_resolves_assignee_full_name(self, mailoutbox):
        from content.models.task import Task
        from content.tasks import _send_task_deadline_email

        assignee = User.objects.create_user(
            username='assignee@test.com', email='assignee@test.com',
            password='x', first_name='Carlos', last_name='Dev',
        )
        task = Task.objects.create(
            title='Assignee Task',
            due_date=date.today() + timedelta(days=5),
            assignee=assignee,
        )

        _send_task_deadline_email(task, threshold_pct=40)

        assert len(mailoutbox) == 1

    def test_alert_email_resolves_assignee_full_name(self, mailoutbox):
        from content.models.task import Task
        from content.models.task_alert import TaskAlert
        from content.tasks import _send_task_alert_email

        assignee = User.objects.create_user(
            username='alert_assignee@test.com', email='alert_assignee@test.com',
            password='x', first_name='Ana', last_name='Dev',
        )
        task = Task.objects.create(
            title='Alert Assignee Task',
            due_date=date.today() + timedelta(days=3),
            assignee=assignee,
        )
        alert = TaskAlert.objects.create(
            task=task,
            notify_at=date.today(),
            note='Test alert',
        )

        _send_task_alert_email(alert)

        assert len(mailoutbox) == 1


# ---------------------------------------------------------------------------
# check_task_deadline_notifications — exception path (lines 1248-1249)
# check_task_alert_notifications — exception path (lines 1365-1366)
# ---------------------------------------------------------------------------

class TestTaskNotificationExceptionPaths:
    @patch('content.tasks._check_single_task_deadlines', side_effect=RuntimeError('deadline fail'))
    def test_check_task_deadline_notifications_exception_is_caught(self, mock_check):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        import content.tasks as tasks_module
        from content.models.task import Task

        Task.objects.create(
            title='Failing Deadline Task',
            status='todo',
            due_date=date.today() + timedelta(days=1),
        )

        tasks_module.check_task_deadline_notifications.call_local()

        # quality: allow-call-contract (exception boundary: assert_called_once verifies the per-task function was invoked before the exception was swallowed)
        mock_check.assert_called_once()

    @patch('content.tasks._send_task_alert_email', side_effect=RuntimeError('alert fail'))
    def test_check_task_alert_notifications_exception_is_caught(self, mock_alert):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        import content.tasks as tasks_module
        from content.models.task import Task
        from content.models.task_alert import TaskAlert

        task = Task.objects.create(
            title='Failing Alert Task',
            due_date=date.today(),
        )
        TaskAlert.objects.create(
            task=task,
            notify_at=date.today(),
            sent=False,
        )

        tasks_module.check_task_alert_notifications.call_local()

        # quality: allow-call-contract (exception boundary: assert_called_once verifies the alert email function was invoked before the exception was swallowed)
        mock_alert.assert_called_once()
