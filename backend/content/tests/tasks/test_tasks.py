"""Tests for Huey tasks.

Covers: send_proposal_reminder, send_urgency_reminder, expire_stale_proposals,
send_rejection_reengagement, check_engagement_followups, send_scheduled_followup.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    BusinessProposal,
    ProposalChangeLog,
    ProposalSectionView,
    ProposalViewEvent,
)

pytestmark = pytest.mark.django_db


class TestSendProposalReminderTask:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder',
           return_value=True)
    def test_sends_reminder_for_sent_proposal(self, mock_send_reminder):
        proposal = BusinessProposal.objects.create(
            title='Reminder Test',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send_reminder.call_count == 1

    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder',
           return_value=True)
    def test_sends_reminder_for_viewed_proposal(self, mock_send_reminder):
        proposal = BusinessProposal.objects.create(
            title='Viewed Test',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send_reminder.call_count == 1

    def test_skips_when_proposal_not_found(self):
        import content.tasks as tasks_module
        result = tasks_module.send_proposal_reminder.call_local(99999)
        assert result is None

    def test_skips_when_status_is_draft(self):
        proposal = BusinessProposal.objects.create(
            title='Draft',
            client_name='Client',
            client_email='client@test.com',
            status='draft',
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)
        assert proposal.status == 'draft'

    def test_skips_when_no_client_email(self):
        proposal = BusinessProposal.objects.create(
            title='No Email',
            client_name='Client',
            client_email='',
            status='sent',
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)
        assert proposal.reminder_sent_at is None

    @freeze_time('2026-03-01 12:00:00')
    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    def test_skips_when_reminder_already_sent(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Already Sent',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            reminder_sent_at=timezone.now(),
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    def test_skips_when_status_is_accepted(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Accepted',
            client_name='Client',
            client_email='client@test.com',
            status='accepted',
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    def test_skips_when_status_is_finished(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Finished',
            client_name='Client',
            client_email='client@test.com',
            status='finished',
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    def test_skips_when_automations_are_paused(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Paused Reminder',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=True,
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    def test_skips_when_client_email_is_placeholder(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Placeholder Reminder',
            client_name='Client',
            client_email='cliente_10@temp.example.com',
            status='sent',
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0


class TestSendUrgencyReminderTask:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email',
           return_value=True)
    def test_sends_urgency_for_sent_proposal(self, mock_send):
        """One-shot urgency task sends email for a sent proposal."""
        proposal = BusinessProposal.objects.create(
            title='Urgency Test',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 1

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email',
           return_value=True)
    def test_sends_urgency_for_viewed_proposal(self, mock_send):
        """One-shot urgency task sends email for a viewed proposal."""
        proposal = BusinessProposal.objects.create(
            title='Viewed Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 1

    def test_skips_when_proposal_not_found(self):
        """Task should not raise when proposal ID does not exist."""
        import content.tasks as tasks_module
        result = tasks_module.send_urgency_reminder.call_local(99999)
        assert result is None

    def test_skips_when_status_is_draft(self):
        """Urgency task should skip draft proposals."""
        proposal = BusinessProposal.objects.create(
            title='Draft Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='draft',
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)
        proposal.refresh_from_db()
        assert proposal.urgency_email_sent_at is None

    def test_skips_when_no_client_email(self):
        """Urgency task should skip proposals without client_email."""
        proposal = BusinessProposal.objects.create(
            title='No Email Urgency',
            client_name='Client',
            client_email='',
            status='sent',
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)
        proposal.refresh_from_db()
        assert proposal.urgency_email_sent_at is None

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email',
           return_value=True)
    def test_skips_auto_send_when_discount_configured(self, mock_send):
        """Discount offers are sent manually, so the auto task must skip them."""
        proposal = BusinessProposal.objects.create(
            title='Discount Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=False,
            discount_percent=15,
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @freeze_time('2026-03-01 12:00:00')
    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email')
    def test_skips_when_urgency_already_sent(self, mock_send):
        """Urgency task should skip if urgency_email_sent_at is already set."""
        proposal = BusinessProposal.objects.create(
            title='Already Sent Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            urgency_email_sent_at=timezone.now(),
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email')
    def test_skips_when_status_is_accepted(self, mock_send):
        """Urgency task should skip accepted proposals."""
        proposal = BusinessProposal.objects.create(
            title='Accepted Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='accepted',
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email')
    def test_skips_when_automations_are_paused(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Paused Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=True,
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email')
    def test_skips_when_client_email_is_placeholder(self, mock_send):
        proposal = BusinessProposal.objects.create(
            title='Placeholder Urgency',
            client_name='Client',
            client_email='cliente_11@temp.example.com',
            status='sent',
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0


class TestExpireStaleProposalsTask:
    @freeze_time('2026-03-10 10:00:00')
    def test_marks_expired_proposals(self):
        proposal = BusinessProposal.objects.create(
            title='Should Expire',
            client_name='Client',
            status='sent',
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'expired'

    @freeze_time('2026-03-10 10:00:00')
    def test_does_not_expire_draft_proposals(self):
        proposal = BusinessProposal.objects.create(
            title='Draft Expired',
            client_name='Client',
            status='draft',
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'draft'

    @freeze_time('2026-03-10 10:00:00')
    def test_does_not_expire_proposals_with_future_expiry(self):
        proposal = BusinessProposal.objects.create(
            title='Not Yet',
            client_name='Client',
            status='sent',
            expires_at=timezone.now() + timezone.timedelta(days=5),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'sent'

    @freeze_time('2026-03-10 10:00:00')
    def test_expires_multiple_proposals(self):
        for i in range(3):
            BusinessProposal.objects.create(
                title=f'Expire {i}',
                client_name=f'Client {i}',
                status='viewed',
                expires_at=timezone.now() - timezone.timedelta(days=1),
            )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        assert BusinessProposal.objects.filter(status='expired').count() == 3

    @freeze_time('2026-03-10 10:00:00')
    @patch('content.tasks.logger.info')
    def test_logs_expired_count_when_stale_proposals_are_marked_expired(self, mock_info):
        BusinessProposal.objects.create(
            title='Log Expiration',
            client_name='Client',
            status='sent',
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        assert BusinessProposal.objects.filter(status='expired').count() == 1
        mock_info.assert_any_call('Expired %d stale proposals.', 1)

    @freeze_time('2026-03-10 10:00:00')
    def test_does_not_expire_inactive_proposals(self):
        """Inactive proposals should not be auto-expired."""
        proposal = BusinessProposal.objects.create(
            title='Inactive Expired',
            client_name='Client',
            status='sent',
            is_active=False,
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'sent'

    @freeze_time('2026-03-10 10:00:00')
    def test_does_not_expire_finished_proposals(self):
        """Finished proposals must never be auto-expired even if their date passed."""
        proposal = BusinessProposal.objects.create(
            title='Finished Project',
            client_name='Client',
            status='finished',
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'finished'

    @freeze_time('2026-03-10 10:00:00')
    def test_auto_extends_proposal_with_recent_view_activity(self):
        proposal = BusinessProposal.objects.create(
            title='Recently Viewed',
            client_name='Client',
            status='sent',
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )
        ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='recent-view',
            ip_address='127.0.0.1',
            viewed_at=timezone.now() - timezone.timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'sent'
        assert proposal.expires_at == timezone.now() + timezone.timedelta(days=7)
        assert ProposalChangeLog.objects.filter(
            proposal=proposal,
            description='Auto-extended expiration by 7 days due to recent client activity.',
        ).exists()


class TestSendRejectionReengagementTask:
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_rejection_reengagement',
        return_value=True,
    )
    def test_sends_reengagement_for_rejected_proposal(self, mock_send):
        """Rejected proposal triggers re-engagement email and changelog entry."""
        proposal = BusinessProposal.objects.create(
            title='Rejected',
            client_name='Client',
            client_email='client@test.com',
            status='rejected',
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)

        mock_send.assert_called_once()
        assert ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='reengagement'
        ).exists()

    def test_skips_when_proposal_not_found(self):
        import content.tasks as tasks_module
        result = tasks_module.send_rejection_reengagement.call_local(99999)
        assert result is None

    def test_skips_when_status_is_not_rejected(self):
        proposal = BusinessProposal.objects.create(
            title='Sent',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)
        assert not ProposalChangeLog.objects.filter(change_type='reengagement').exists()

    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_rejection_reengagement',
        return_value=True,
    )
    def test_skips_auto_send_when_discount_configured(self, mock_send):
        """A discount-bearing re-engagement is offered manually, not auto-sent."""
        proposal = BusinessProposal.objects.create(
            title='Discount Reengage',
            client_name='Client',
            client_email='client@test.com',
            status='rejected',
            discount_percent=20,
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)

        assert mock_send.call_count == 0
        assert not ProposalChangeLog.objects.filter(change_type='reengagement').exists()

    def test_skips_when_no_client_email(self):
        proposal = BusinessProposal.objects.create(
            title='No Email',
            client_name='Client',
            client_email='',
            status='rejected',
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)
        assert not ProposalChangeLog.objects.filter(change_type='reengagement').exists()

    def test_skips_when_client_email_is_placeholder(self):
        proposal = BusinessProposal.objects.create(
            title='Placeholder Email',
            client_name='Client',
            client_email='cliente_12@temp.example.com',
            status='rejected',
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)

        assert not ProposalChangeLog.objects.filter(change_type='reengagement').exists()

    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_rejection_reengagement',
        return_value=True,
    )
    def test_skips_when_already_sent(self, mock_send):
        """Re-engagement skips when a changelog entry already exists."""
        proposal = BusinessProposal.objects.create(
            title='Already Sent',
            client_name='Client',
            client_email='client@test.com',
            status='rejected',
        )
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='reengagement',
            description='Already sent.',
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)

        mock_send.assert_not_called()
        assert ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='reengagement'
        ).count() == 1  # unchanged

    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_rejection_reengagement',
        return_value=False,
    )
    def test_does_not_log_when_send_fails(self, mock_send):
        """No changelog entry created when email sending returns False."""
        proposal = BusinessProposal.objects.create(
            title='Fail Send',
            client_name='Client',
            client_email='client@test.com',
            status='rejected',
        )

        import content.tasks as tasks_module
        tasks_module.send_rejection_reengagement.call_local(proposal.id)

        mock_send.assert_called_once()
        assert not ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='reengagement'
        ).exists()


class TestCheckEngagementFollowupsTask:
    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_abandonment_followup',
        return_value=True,
    )
    def test_sends_abandonment_followup(self, mock_send):
        """Proposal viewed >4h ago without investment section triggers abandonment email."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Abandoned',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=5),
            automations_paused=False,
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-1',
            ip_address='127.0.0.1',
        )
        ProposalSectionView.objects.create(
            view_event=ve,
            section_type='greeting',
            time_spent_seconds=10,
            entered_at=now - timedelta(hours=5),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        mock_send.assert_called_once()
        assert mock_send.call_args[0][0].pk == proposal.pk

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_abandonment_followup',
        return_value=True,
    )
    def test_skips_abandonment_when_investment_visited(self, mock_send):
        """Abandonment email skipped when client visited the investment section."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Visited Investment',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=5),
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-1',
            ip_address='127.0.0.1',
        )
        ProposalSectionView.objects.create(
            view_event=ve,
            section_type='investment',
            time_spent_seconds=30,
            entered_at=now - timedelta(hours=5),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        assert mock_send.call_count == 0



class TestSuggestPreExpirationDiscountTask:
    @freeze_time('2026-03-10 12:00:00')
    def test_creates_discount_suggestion_for_viewed_candidate(self):
        proposal = BusinessProposal.objects.create(
            title='Discount Candidate',
            client_name='Client',
            status='viewed',
            is_active=True,
            discount_percent=0,
            responded_at=None,
            expires_at=timezone.now() + timezone.timedelta(days=3),
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert proposal.manual_alerts.filter(alert_type='discount_suggestion').exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_creating_duplicate_discount_suggestion(self):
        proposal = BusinessProposal.objects.create(
            title='Existing Suggestion',
            client_name='Client',
            status='viewed',
            is_active=True,
            discount_percent=0,
            responded_at=None,
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )
        proposal.manual_alerts.create(
            alert_type='discount_suggestion',
            message='Already suggested',
            alert_date=timezone.now(),
            is_dismissed=False,
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert proposal.manual_alerts.filter(alert_type='discount_suggestion').count() == 1

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_non_candidate_proposal(self):
        proposal = BusinessProposal.objects.create(
            title='Already Discounted',
            client_name='Client',
            status='viewed',
            is_active=True,
            discount_percent=10,
            responded_at=None,
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert proposal.manual_alerts.count() == 0

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup',
        return_value=True,
    )
    def test_sends_investment_interest_followup(self, mock_send):
        """Proposal with >60s on investment and last view >2h ago triggers interest email."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Interested',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            automations_paused=False,
            first_viewed_at=now - timedelta(hours=5),
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-1',
            ip_address='127.0.0.1',
        )
        # auto_now_add ignores kwargs, so force via update()
        ProposalViewEvent.objects.filter(pk=ve.pk).update(
            viewed_at=now - timedelta(hours=3),
        )
        ProposalSectionView.objects.create(
            view_event=ve,
            section_type='investment',
            time_spent_seconds=90,
            entered_at=now - timedelta(hours=3),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        mock_send.assert_called_once()
        assert mock_send.call_args[0][0].pk == proposal.pk

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup',
        return_value=True,
    )
    def test_skips_interest_when_investment_time_under_60s(self, mock_send):
        """Interest email skipped when total investment time is under 60 seconds."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Short Investment',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=5),
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-1',
            ip_address='127.0.0.1',
        )
        ProposalViewEvent.objects.filter(pk=ve.pk).update(
            viewed_at=now - timedelta(hours=3),
        )
        ProposalSectionView.objects.create(
            view_event=ve,
            section_type='investment',
            time_spent_seconds=30,
            entered_at=now - timedelta(hours=3),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        assert mock_send.call_count == 0

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup',
        return_value=True,
    )
    def test_skips_interest_when_last_view_is_recent(self, mock_send):
        """Interest email skipped when the last view event is less than 2 hours ago."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recent View',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=5),
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-1',
            ip_address='127.0.0.1',
        )
        ProposalViewEvent.objects.filter(pk=ve.pk).update(
            viewed_at=now - timedelta(minutes=30),
        )
        ProposalSectionView.objects.create(
            view_event=ve,
            section_type='investment',
            time_spent_seconds=90,
            entered_at=now - timedelta(minutes=30),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        assert mock_send.call_count == 0

    @freeze_time('2026-03-10 12:00:00')
    @patch('content.tasks.logger.info')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup',
        return_value=True,
    )
    def test_logs_when_investment_interest_followup_is_sent(self, mock_send, mock_log_info):
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Interest Log',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            automations_paused=False,
            first_viewed_at=now - timedelta(hours=5),
        )
        view_event = ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-interest-log',
            ip_address='127.0.0.1',
        )
        ProposalViewEvent.objects.filter(pk=view_event.pk).update(
            viewed_at=now - timedelta(hours=3),
        )
        ProposalSectionView.objects.create(
            view_event=view_event,
            section_type='investment',
            time_spent_seconds=75,
            entered_at=now - timedelta(hours=3),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        assert mock_send.call_count == 1
        assert mock_send.call_args.args == (proposal, 75)
        assert (
            'Sent investment interest followup for proposal %s (time=%ds)',
            proposal.uuid,
            75,
        ) in [call.args for call in mock_log_info.call_args_list]


class TestSendScheduledFollowupTask:
    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_scheduled_followup',
        return_value=True,
    )
    def test_sends_followup_for_scheduled_proposal(self, mock_send):
        """Scheduled followup task calls email service for a valid proposal."""
        proposal = BusinessProposal.objects.create(
            title='Scheduled',
            client_name='Client',
            client_email='client@test.com',
            status='rejected',
            followup_scheduled_at=timezone.now(),
        )

        import content.tasks as tasks_module
        tasks_module.send_scheduled_followup.call_local(proposal.id)

        mock_send.assert_called_once()
        assert mock_send.call_args[0][0].pk == proposal.pk

    def test_skips_when_proposal_not_found(self):
        import content.tasks as tasks_module
        result = tasks_module.send_scheduled_followup.call_local(99999)
        assert result is None

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_scheduled_followup',
    )
    def test_skips_when_no_client_email(self, mock_send):
        """Scheduled followup skips when proposal has no client_email."""
        proposal = BusinessProposal.objects.create(
            title='No Email',
            client_name='Client',
            client_email='',
            status='rejected',
            followup_scheduled_at=timezone.now(),
        )

        import content.tasks as tasks_module
        tasks_module.send_scheduled_followup.call_local(proposal.id)

        assert mock_send.call_count == 0

    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_scheduled_followup',
    )
    def test_skips_when_no_scheduled_date(self, mock_send):
        """Scheduled followup skips when followup_scheduled_at is not set."""
        proposal = BusinessProposal.objects.create(
            title='No Date',
            client_name='Client',
            client_email='client@test.com',
            status='rejected',
        )

        import content.tasks as tasks_module
        tasks_module.send_scheduled_followup.call_local(proposal.id)

        assert mock_send.call_count == 0


class TestCheckEngagementFollowupsExceptionPaths:
    """Tests for exception handling in check_engagement_followups."""

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_abandonment_followup',
        side_effect=Exception('SMTP error'),
    )
    def test_abandonment_exception_is_caught(self, mock_send):
        """Exception in send_abandonment_followup is caught and logged, not raised."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Abandon Err',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=5),
            automations_paused=False,
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-err',
        )
        ProposalSectionView.objects.create(
            view_event=ve, section_type='greeting',
            time_spent_seconds=10, entered_at=now - timedelta(hours=5),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        mock_send.assert_called_once()
        proposal.refresh_from_db()
        assert proposal.abandonment_email_sent_at is None

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup',
        side_effect=Exception('SMTP error'),
    )
    def test_investment_interest_exception_is_caught(self, mock_send):
        """Exception in send_investment_interest_followup is caught and logged, not raised."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Interest Err',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=5),
            automations_paused=False,
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-err2',
        )
        ProposalViewEvent.objects.filter(pk=ve.pk).update(
            viewed_at=now - timedelta(hours=3),
        )
        ProposalSectionView.objects.create(
            view_event=ve, section_type='investment',
            time_spent_seconds=90, entered_at=now - timedelta(hours=3),
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        mock_send.assert_called_once()
        proposal.refresh_from_db()
        assert proposal.investment_interest_email_sent_at is None


class TestNotifyFirstViewTask:
    """Tests for the notify_first_view Huey task."""

    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_first_view_notification',
        return_value=True,
    )
    def test_sends_notification_for_valid_proposal(self, mock_send):
        """Task sends first-view notification for an existing proposal."""
        proposal = BusinessProposal.objects.create(
            title='First View',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            first_viewed_at=timezone.now(),
            first_view_notification_status='pending',
        )

        import content.tasks as tasks_module
        tasks_module.notify_first_view.call_local(proposal.id)

        mock_send.assert_called_once()
        assert mock_send.call_args[0][0].pk == proposal.pk
        proposal.refresh_from_db()
        assert proposal.first_view_notification_status == 'sent'

    def test_skips_when_proposal_not_found(self):
        """Task returns early when proposal ID does not exist."""
        import content.tasks as tasks_module
        result = tasks_module.notify_first_view.call_local(99999)
        assert result is None


class TestPublishScheduledBlogPostsTask:
    """Tests for the publish_scheduled_blog_posts periodic task."""

    @freeze_time('2026-03-10 12:00:00')
    def test_publishes_scheduled_posts(self):
        """Posts with published_at in the past and is_published=False get published."""
        from content.models import BlogPost
        post = BlogPost.objects.create(
            title_es='Programado', title_en='Scheduled',
            excerpt_es='E', excerpt_en='E',
            is_published=False,
            published_at=timezone.now() - timedelta(hours=1),
        )

        import content.tasks as tasks_module
        tasks_module.publish_scheduled_blog_posts.call_local()

        post.refresh_from_db()
        assert post.is_published is True

    @freeze_time('2026-03-10 12:00:00')
    def test_does_not_publish_future_posts(self):
        """Posts with published_at in the future remain unpublished."""
        from content.models import BlogPost
        post = BlogPost.objects.create(
            title_es='Futuro', title_en='Future',
            excerpt_es='E', excerpt_en='E',
            is_published=False,
            published_at=timezone.now() + timedelta(hours=1),
        )

        import content.tasks as tasks_module
        tasks_module.publish_scheduled_blog_posts.call_local()

        post.refresh_from_db()
        assert post.is_published is False


class TestSuggestPreExpirationDiscountTaskExpiryWindow:
    @freeze_time('2026-03-10 12:00:00')
    def test_creates_alert_for_viewed_proposal_expiring_soon(self):
        """Creates discount_suggestion alert for viewed proposal expiring within 5 days."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Expiring Soon',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            discount_percent=0,
            expires_at=now + timedelta(days=3),
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='discount_suggestion',
        ).first()
        assert alert is not None
        assert 'Expira en' in alert.message

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_proposal_with_existing_discount(self):
        """No alert created for proposals that already have a discount."""
        from content.models import ProposalAlert
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Has Discount',
            client_name='Client',
            status='viewed',
            discount_percent=10,
            expires_at=now + timedelta(days=3),
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert ProposalAlert.objects.filter(alert_type='discount_suggestion').count() == 0

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_proposal_expiring_beyond_5_days(self):
        """No alert for proposals expiring more than 5 days from now."""
        from content.models import ProposalAlert
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Far Expiry',
            client_name='Client',
            status='viewed',
            discount_percent=0,
            expires_at=now + timedelta(days=10),
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert ProposalAlert.objects.filter(alert_type='discount_suggestion').count() == 0

    @freeze_time('2026-03-10 12:00:00')
    def test_does_not_duplicate_existing_alert(self):
        """No duplicate alert created if one already exists."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Already Alerted',
            client_name='Client',
            status='viewed',
            discount_percent=0,
            expires_at=now + timedelta(days=3),
        )
        ProposalAlert.objects.create(
            proposal=proposal,
            alert_type='discount_suggestion',
            message='Existing alert',
            alert_date=now,
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert ProposalAlert.objects.filter(
            proposal=proposal, alert_type='discount_suggestion',
        ).count() == 1

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_responded_proposals(self):
        """No alert for proposals that have been responded to."""
        from content.models import ProposalAlert
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Responded',
            client_name='Client',
            status='viewed',
            discount_percent=0,
            expires_at=now + timedelta(days=3),
            responded_at=now - timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.suggest_pre_expiration_discount.call_local()

        assert ProposalAlert.objects.filter(alert_type='discount_suggestion').count() == 0


class TestEscalateSellerInactivityTask:
    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        return_value=True,
    )
    def test_escalates_inactive_proposal(self, mock_send):
        """Sends escalation for proposal with no seller activity for 5+ days."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Inactive',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            sent_at=now - timedelta(days=7),
            first_viewed_at=now - timedelta(days=6),
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        mock_send.assert_called_once()
        assert ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='seller_inactivity_escalation',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        return_value=True,
    )
    def test_skips_when_recent_seller_activity(self, mock_send):
        """No escalation when seller logged activity within 5 days."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Active Seller',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            sent_at=now - timedelta(days=7),
            first_viewed_at=now - timedelta(days=6),
        )
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='call',
            description='Called client',
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        assert mock_send.call_count == 0
        assert not ProposalChangeLog.objects.filter(
            change_type='seller_inactivity_escalation',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        return_value=True,
    )
    def test_skips_when_already_escalated(self, mock_send):
        """No duplicate escalation when one already exists."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Already Escalated',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            sent_at=now - timedelta(days=7),
            first_viewed_at=now - timedelta(days=6),
        )
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='seller_inactivity_escalation',
            description='Already sent.',
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        assert mock_send.call_count == 0
        assert ProposalChangeLog.objects.filter(
            change_type='seller_inactivity_escalation',
        ).count() == 1  # unchanged from setup

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        return_value=True,
    )
    def test_skips_when_automations_paused(self, mock_send):
        """No escalation when automations are paused."""
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Paused',
            client_name='Client',
            status='viewed',
            automations_paused=True,
            sent_at=now - timedelta(days=7),
            first_viewed_at=now - timedelta(days=6),
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        assert mock_send.call_count == 0
        assert not ProposalChangeLog.objects.filter(
            change_type='seller_inactivity_escalation',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        side_effect=Exception('SMTP error'),
    )
    def test_exception_is_caught_and_logged(self, mock_send):
        """Exception in send_seller_inactivity_escalation is caught, not raised."""
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Error',
            client_name='Client',
            status='viewed',
            sent_at=now - timedelta(days=7),
            first_viewed_at=now - timedelta(days=6),
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        mock_send.assert_called_once()
        assert not ProposalChangeLog.objects.filter(
            change_type='seller_inactivity_escalation',
        ).exists()


class TestAutomationsPausedPaths:
    @patch('content.services.proposal_email_service.ProposalEmailService.send_reminder')
    def test_reminder_skips_when_automations_paused(self, mock_send):
        """Reminder task skips when automations_paused=True."""
        proposal = BusinessProposal.objects.create(
            title='Paused Reminder',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=True,
        )

        import content.tasks as tasks_module
        tasks_module.send_proposal_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0
        proposal.refresh_from_db()
        assert proposal.reminder_sent_at is None

    @patch('content.services.proposal_email_service.ProposalEmailService.send_urgency_email')
    def test_urgency_skips_when_automations_paused(self, mock_send):
        """Urgency task skips when automations_paused=True."""
        proposal = BusinessProposal.objects.create(
            title='Paused Urgency',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=True,
        )

        import content.tasks as tasks_module
        tasks_module.send_urgency_reminder.call_local(proposal.id)

        assert mock_send.call_count == 0
        proposal.refresh_from_db()
        assert proposal.urgency_email_sent_at is None


class TestSuggestActionForProposal:
    """Tests for the _suggest_action_for_proposal helper function."""

    @freeze_time('2026-03-10 12:00:00')
    def test_negotiating_proposal_returns_negotiation_action(self):
        """Negotiating proposals get a follow-up negotiation suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Negotiating', client_name='Client', status='negotiating',
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'negociación' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_high_view_count_returns_call_action(self):
        """Proposals with 3+ views get a call suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='High Views', client_name='Client', status='viewed',
            view_count=5,
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Llamar hoy' in result
        assert '5' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_expiring_soon_without_discount_returns_discount_suggestion(self):
        """Proposals expiring in <=3 days without discount get discount suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Expiring', client_name='Client', status='sent',
            view_count=0, discount_percent=0,
            expires_at=now + timedelta(days=2),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'descuento' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_expiring_soon_with_discount_returns_urgency_reminder(self):
        """Proposals expiring in <=3 days with discount get urgency reminder."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Expiring Discount', client_name='Client', status='sent',
            view_count=0, discount_percent=10,
            expires_at=now + timedelta(days=2),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'urgencia' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_viewed_with_old_activity_returns_whatsapp_suggestion(self):
        """Viewed proposals with no response >2 days get WhatsApp suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Old Viewed', client_name='Client', status='viewed',
            view_count=1,
            last_activity_at=now - timedelta(days=4),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'WhatsApp' in result
        assert '4d' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_viewed_recently_returns_wait_suggestion(self):
        """Recently viewed proposals get a wait/reinforce suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recent Viewed', client_name='Client', status='viewed',
            view_count=1,
            last_activity_at=now - timedelta(hours=12),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Visto recientemente' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_sent_old_returns_resend_suggestion(self):
        """Sent proposals not opened after >3 days get re-send suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Old Sent', client_name='Client', status='sent',
            view_count=0,
            sent_at=now - timedelta(days=5),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Sin abrir' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_sent_recently_returns_wait_suggestion(self):
        """Recently sent proposals get a wait suggestion."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recent Sent', client_name='Client', status='sent',
            view_count=0,
            sent_at=now - timedelta(hours=12),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Enviada recientemente' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_fallback_returns_generic_followup(self):
        """Other statuses get the generic follow-up string."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Draft', client_name='Client', status='draft',
            view_count=0,
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Revisar estado' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_viewed_with_first_viewed_at_fallback(self):
        """When last_activity_at is None, falls back to first_viewed_at."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='First View Fallback', client_name='Client', status='viewed',
            view_count=1,
            last_activity_at=None,
            first_viewed_at=now - timedelta(days=3),
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'WhatsApp' in result


class TestSendDailyPipelineDigestTask:
    """Tests for the send_daily_pipeline_digest periodic task."""

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_daily_pipeline_digest',
        return_value=True,
    )
    def test_sends_digest_with_viewed_yesterday(self, mock_send):
        """Digest includes proposals that were viewed yesterday."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Viewed Yesterday', client_name='Client',
            status='viewed', view_count=1,
            sent_at=now - timedelta(days=3),
        )
        yesterday = now - timedelta(hours=18)
        ve = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-digest',
        )
        ProposalViewEvent.objects.filter(pk=ve.pk).update(viewed_at=yesterday)

        import content.tasks as tasks_module
        tasks_module.send_daily_pipeline_digest.call_local()

        mock_send.assert_called_once()
        digest = mock_send.call_args[0][0]
        assert digest['date'] == 'Mar, 10 mar 2026'
        assert digest['total_active'] >= 1
        assert len(digest['viewed_yesterday']) == 1
        assert digest['viewed_yesterday'][0]['client_name'] == 'Client'

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_daily_pipeline_digest',
        return_value=True,
    )
    def test_includes_inactive_proposals(self, mock_send):
        """Digest includes proposals with no activity >3 days."""
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Inactive Digest', client_name='Inactive Client',
            status='sent',
            sent_at=now - timedelta(days=5),
            last_activity_at=now - timedelta(days=4),
        )

        import content.tasks as tasks_module
        tasks_module.send_daily_pipeline_digest.call_local()

        mock_send.assert_called_once()
        digest = mock_send.call_args[0][0]
        assert len(digest['inactive']) >= 1
        assert digest['inactive'][0]['client_name'] == 'Inactive Client'

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_daily_pipeline_digest',
        return_value=True,
    )
    def test_includes_expiring_soon_proposals(self, mock_send):
        """Digest includes proposals expiring within 5 days."""
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Expiring Digest', client_name='Expiring Client',
            status='viewed', view_count=1,
            expires_at=now + timedelta(days=3),
        )

        import content.tasks as tasks_module
        tasks_module.send_daily_pipeline_digest.call_local()

        mock_send.assert_called_once()
        digest = mock_send.call_args[0][0]
        assert len(digest['expiring_soon']) >= 1
        assert digest['expiring_soon'][0]['client_name'] == 'Expiring Client'

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_daily_pipeline_digest',
        return_value=True,
    )
    def test_empty_digest_when_no_active_proposals(self, mock_send):
        """Digest is sent even when there are no active proposals."""
        import content.tasks as tasks_module
        tasks_module.send_daily_pipeline_digest.call_local()

        mock_send.assert_called_once()
        digest = mock_send.call_args[0][0]
        assert digest['total_active'] == 0
        assert digest['viewed_yesterday'] == []
        assert digest['inactive'] == []
        assert digest['expiring_soon'] == []


class TestDetectHighEngagementTodayTask:
    """Tests for the detect_high_engagement_today periodic task."""

    @freeze_time('2026-03-10 12:00:00')
    def test_creates_alert_for_3_sessions_today(self):
        """Alert created when proposal has 3+ unique sessions today."""
        from content.models import ProposalAlert
        proposal = BusinessProposal.objects.create(
            title='High Engagement', client_name='Engaged Client',
            status='viewed',
        )
        for i in range(3):
            ProposalViewEvent.objects.create(
                proposal=proposal, session_id=f'sess-he-{i}',
            )

        import content.tasks as tasks_module
        tasks_module.detect_high_engagement_today.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='high_engagement_today',
        ).first()
        assert alert is not None
        assert 'Engaged Client' in alert.message
        assert '3' in alert.message

    @freeze_time('2026-03-10 12:00:00')
    def test_no_alert_for_fewer_than_3_sessions(self):
        """No alert when proposal has fewer than 3 sessions today."""
        from content.models import ProposalAlert
        proposal = BusinessProposal.objects.create(
            title='Low Engagement', client_name='Client',
            status='viewed',
        )
        for i in range(2):
            ProposalViewEvent.objects.create(
                proposal=proposal, session_id=f'sess-low-{i}',
            )

        import content.tasks as tasks_module
        tasks_module.detect_high_engagement_today.call_local()

        assert not ProposalAlert.objects.filter(
            proposal=proposal, alert_type='high_engagement_today',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_no_duplicate_alert_same_day(self):
        """No duplicate alert when one already exists today."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Already Alerted', client_name='Client',
            status='viewed',
        )
        for i in range(3):
            ProposalViewEvent.objects.create(
                proposal=proposal, session_id=f'sess-dup-{i}',
            )
        ProposalAlert.objects.create(
            proposal=proposal, alert_type='high_engagement_today',
            message='Existing', alert_date=now,
        )

        import content.tasks as tasks_module
        tasks_module.detect_high_engagement_today.call_local()

        assert ProposalAlert.objects.filter(
            proposal=proposal, alert_type='high_engagement_today',
        ).count() == 1

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_inactive_proposals(self):
        """No alert for inactive proposals."""
        from content.models import ProposalAlert
        proposal = BusinessProposal.objects.create(
            title='Inactive', client_name='Client',
            status='viewed', is_active=False,
        )
        for i in range(3):
            ProposalViewEvent.objects.create(
                proposal=proposal, session_id=f'sess-inact-{i}',
            )

        import content.tasks as tasks_module
        tasks_module.detect_high_engagement_today.call_local()

        assert not ProposalAlert.objects.filter(
            proposal=proposal, alert_type='high_engagement_today',
        ).exists()


class TestRetiredCalculatorFollowupTask:
    def test_noop_does_not_create_followup_for_legacy_abandonment(self):
        """Falla si un job legado vuelve a crear seguimiento de la calculadora retirada."""
        from content.models import ProposalAlert
        proposal = BusinessProposal.objects.create(
            title='Calculadora retirada', client_name='Cliente', status='viewed',
        )
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.CALCULATOR_ABANDONED,
        )

        import content.tasks as tasks_module
        tasks_module.check_calculator_abandonment_followup.call_local()

        assert not ProposalAlert.objects.filter(
            proposal=proposal, alert_type='calculator_followup',
        ).exists()


class TestGenerateWhatsappSuggestionsTask:
    """Tests for the generate_whatsapp_suggestions periodic task."""

    @freeze_time('2026-03-10 12:00:00')
    def test_creates_suggestion_for_viewed_proposal_with_phone(self):
        """WhatsApp suggestion created for viewed >48h proposal with phone."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='WhatsApp Target', client_name='WA Client',
            status='viewed',
            client_phone='+573001234567',
            first_viewed_at=now - timedelta(hours=50),
            automations_paused=False,
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-wa',
        )
        ProposalSectionView.objects.create(
            view_event=ve, section_type='investment',
            time_spent_seconds=60,
            entered_at=now - timedelta(hours=50),
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='whatsapp_suggestion',
        ).first()
        assert alert is not None
        assert 'WA Client' in alert.message
        assert 'inversión' in alert.message

    @freeze_time('2026-03-10 12:00:00')
    def test_uses_section_type_as_fallback_when_not_in_labels(self):
        """Uses raw section_type when not found in section_labels map."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Unknown Section', client_name='Client',
            status='viewed',
            client_phone='+573001234567',
            first_viewed_at=now - timedelta(hours=50),
            automations_paused=False,
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-wa-unk',
        )
        ProposalSectionView.objects.create(
            view_event=ve, section_type='custom_section',
            time_spent_seconds=60,
            entered_at=now - timedelta(hours=50),
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='whatsapp_suggestion',
        ).first()
        assert alert is not None
        assert 'custom_section' in alert.message

    @freeze_time('2026-03-10 12:00:00')
    def test_no_suggestion_when_no_phone(self):
        """No suggestion for proposals without client_phone."""
        from content.models import ProposalAlert
        now = timezone.now()
        BusinessProposal.objects.create(
            title='No Phone', client_name='Client',
            status='viewed', client_phone='',
            first_viewed_at=now - timedelta(hours=50),
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        assert not ProposalAlert.objects.filter(
            alert_type='whatsapp_suggestion',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_no_duplicate_suggestion(self):
        """No duplicate suggestion when one already exists."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Already Suggested', client_name='Client',
            status='viewed',
            client_phone='+573001234567',
            first_viewed_at=now - timedelta(hours=50),
        )
        ProposalAlert.objects.create(
            proposal=proposal, alert_type='whatsapp_suggestion',
            message='Existing', alert_date=now,
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        assert ProposalAlert.objects.filter(
            proposal=proposal, alert_type='whatsapp_suggestion',
        ).count() == 1

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_recently_viewed_proposals(self):
        """No suggestion for proposals viewed <48h ago."""
        from content.models import ProposalAlert
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Recent View', client_name='Client',
            status='viewed',
            client_phone='+573001234567',
            first_viewed_at=now - timedelta(hours=20),
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        assert not ProposalAlert.objects.filter(
            alert_type='whatsapp_suggestion',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_automations_paused(self):
        """No suggestion when automations are paused."""
        from content.models import ProposalAlert
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Paused WA', client_name='Client',
            status='viewed',
            client_phone='+573001234567',
            first_viewed_at=now - timedelta(hours=50),
            automations_paused=True,
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        assert not ProposalAlert.objects.filter(
            alert_type='whatsapp_suggestion',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_fallback_label_when_no_section_views(self):
        """Uses 'la propuesta' when there are no section view records."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='No Sections', client_name='Client',
            status='viewed',
            client_phone='+573001234567',
            first_viewed_at=now - timedelta(hours=50),
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.generate_whatsapp_suggestions.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='whatsapp_suggestion',
        ).first()
        assert alert is not None
        assert 'la propuesta' in alert.message


class TestAutoArchiveZombieProposalsTask:
    """Tests for the auto_archive_zombie_proposals periodic task."""

    @freeze_time('2026-03-10 12:00:00')
    def test_archives_expired_proposal_with_no_recent_activity(self):
        """Expired proposal with no activity in 30+ days gets archived."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Zombie', client_name='Client',
            status='expired',
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            created_at=now - timedelta(days=60),
        )

        import content.tasks as tasks_module
        tasks_module.auto_archive_zombie_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.is_active is False
        assert ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='auto_archived',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_does_not_archive_recent_expired_proposal(self):
        """Expired proposal with recent activity is not archived."""
        proposal = BusinessProposal.objects.create(
            title='Recent Zombie', client_name='Client',
            status='expired',
        )

        import content.tasks as tasks_module
        tasks_module.auto_archive_zombie_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.is_active is True

    @freeze_time('2026-03-10 12:00:00')
    def test_does_not_archive_non_expired_proposal(self):
        """Non-expired proposals are not archived regardless of age."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Old Active', client_name='Client',
            status='sent',
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            created_at=now - timedelta(days=60),
        )

        import content.tasks as tasks_module
        tasks_module.auto_archive_zombie_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.is_active is True

    @freeze_time('2026-03-10 12:00:00')
    def test_does_not_archive_already_inactive_proposal(self):
        """Already inactive proposals are not processed."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Already Inactive', client_name='Client',
            status='expired', is_active=False,
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            created_at=now - timedelta(days=60),
        )

        import content.tasks as tasks_module
        tasks_module.auto_archive_zombie_proposals.call_local()

        assert not ProposalChangeLog.objects.filter(
            proposal=proposal, change_type='auto_archived',
        ).exists()

    @freeze_time('2026-03-10 12:00:00')
    def test_keeps_expired_proposal_with_recent_view(self):
        """Expired proposal with a view in last 30 days is not archived."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recent View Zombie', client_name='Client',
            status='expired',
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            created_at=now - timedelta(days=60),
        )
        ve = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-zombie',
        )
        ProposalViewEvent.objects.filter(pk=ve.pk).update(
            viewed_at=now - timedelta(days=10),
        )

        import content.tasks as tasks_module
        tasks_module.auto_archive_zombie_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.is_active is True

    @freeze_time('2026-03-10 12:00:00')
    def test_keeps_expired_proposal_with_recent_changelog(self):
        """Expired proposal with a changelog in last 30 days is not archived."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recent Log Zombie', client_name='Client',
            status='expired',
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            created_at=now - timedelta(days=60),
        )
        ProposalChangeLog.objects.create(
            proposal=proposal, change_type='note',
            description='Recent activity',
        )

        import content.tasks as tasks_module
        tasks_module.auto_archive_zombie_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.is_active is True



class TestExpireStaleProposalsAutoExtend:
    """Tests for the auto-extend branch in expire_stale_proposals (lines 255-265, 274)."""

    @freeze_time('2026-03-10 10:00:00')
    def test_auto_extends_proposal_with_recent_view_event(self):
        """Proposal with a view event in last 3 days is extended, not expired."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recent Activity', client_name='Client',
            status='sent', expires_at=now - timedelta(days=1),
        )
        view_event = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-extend-001',
        )
        ProposalViewEvent.objects.filter(pk=view_event.pk).update(
            viewed_at=now - timedelta(hours=6),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'sent'
        assert proposal.expires_at > now

    @freeze_time('2026-03-10 10:00:00')
    def test_extends_expiry_when_client_viewed_in_last_3_days(self):
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recently Viewed',
            client_name='Client',
            status='viewed',
            expires_at=now - timedelta(days=1),
        )
        ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-1',
            viewed_at=now - timedelta(hours=2),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        proposal.refresh_from_db()
        assert proposal.status == 'viewed'
        assert proposal.expires_at == now + timedelta(days=7)

    @freeze_time('2026-03-10 10:00:00')
    def test_auto_extend_creates_change_log(self):
        """A system change log entry is created when a proposal is auto-extended."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Extend Log', client_name='Client',
            status='sent', expires_at=now - timedelta(days=1),
        )
        view_event = ProposalViewEvent.objects.create(
            proposal=proposal, session_id='sess-extend-002',
        )
        ProposalViewEvent.objects.filter(pk=view_event.pk).update(
            viewed_at=now - timedelta(hours=6),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        assert ProposalChangeLog.objects.filter(
            proposal=proposal,
            actor_type='system',
            change_type='updated',
        ).exists()

    @freeze_time('2026-03-10 10:00:00')
    def test_creates_changelog_when_auto_extended(self):
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Recently Viewed',
            client_name='Client',
            status='sent',
            expires_at=now - timedelta(hours=1),
        )
        ProposalViewEvent.objects.create(
            proposal=proposal,
            session_id='sess-2',
            viewed_at=now - timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.expire_stale_proposals.call_local()

        assert ProposalChangeLog.objects.filter(
            proposal=proposal,
            change_type='updated',
            actor_type='system',
        ).exists()


class TestEscalateSellerInactivityContinue:
    """Tests for the continue branch in escalate_seller_inactivity (line 304)."""

    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        return_value=True,
    )
    def test_skips_proposal_sent_within_five_days(self, mock_send):
        """Proposal with sent_at within 5 days triggers continue — no escalation."""
        now = timezone.now()
        BusinessProposal.objects.create(
            title='Recently Sent', client_name='Client',
            client_email='client@test.com',
            status='viewed',
            sent_at=now - timedelta(days=2),
            first_viewed_at=now - timedelta(days=1),
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        assert mock_send.call_count == 0


class TestEscalateSellerInactivityRefDateFallback:
    @freeze_time('2026-03-10 12:00:00')
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_seller_inactivity_escalation',
        return_value=True,
    )
    def test_skips_candidate_without_last_activity_or_sent_at(self, mock_send):
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='No Dates',
            client_name='Client',
            client_email='client@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(days=6),
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            last_activity_at=None,
            sent_at=None,
        )

        import content.tasks as tasks_module
        tasks_module.escalate_seller_inactivity.call_local()

        assert mock_send.call_count == 0


class TestSuggestActionForProposalBranches:
    """Tests for uncovered branches in _suggest_action_for_proposal (branch 524->530)."""

    @freeze_time('2026-03-10 12:00:00')
    def test_returns_viewed_message_when_expires_more_than_3_days_away(self):
        """When expires_at is >3 days away the expiry block is skipped and viewed branch runs."""
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Far Expiry Viewed', client_name='Client',
            status='viewed',
            expires_at=now + timedelta(days=10),
            first_viewed_at=now - timedelta(days=3),
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            last_activity_at=now - timedelta(days=3),
        )
        proposal.refresh_from_db()

        result = _suggest_action_for_proposal(proposal, now)

        assert 'WhatsApp' in result


class TestRetiredCalculatorFollowupEmptyDescription:
    """Legacy queued jobs remain observational regardless of old payload shape."""

    @freeze_time('2026-03-10 12:00:00')
    def test_empty_legacy_payload_does_not_create_alert(self):
        """Falla si una carga histórica vacía revive el seguimiento retirado."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Empty Desc Calc', client_name='Client',
            status='viewed',
            automations_paused=False,
        )
        log = ProposalChangeLog.objects.create(
            proposal=proposal, change_type='calc_abandoned',
            description='',
        )
        ProposalChangeLog.objects.filter(pk=log.pk).update(
            created_at=now - timedelta(hours=30),
        )

        import content.tasks as tasks_module
        tasks_module.check_calculator_abandonment_followup.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='calculator_followup',
        ).first()
        assert alert is None


class TestRefreshCachedHeatScoresTask:
    @patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal')
    def test_updates_cached_score_when_new_value_differs(self, mock_score):
        mock_score.return_value = 7
        proposal = BusinessProposal.objects.create(
            title='Heat Update',
            client_name='Client',
            status='sent',
            cached_heat_score=3,
        )

        import content.tasks as tasks_module
        tasks_module.refresh_cached_heat_scores.call_local()

        proposal.refresh_from_db()
        assert proposal.cached_heat_score == 7

    @patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal')
    def test_skips_update_when_new_value_matches_current(self, mock_score):
        mock_score.return_value = 5
        proposal = BusinessProposal.objects.create(
            title='Heat Same',
            client_name='Client',
            status='viewed',
            cached_heat_score=5,
        )
        original_updated_at = proposal.updated_at

        import content.tasks as tasks_module
        tasks_module.refresh_cached_heat_scores.call_local()

        proposal.refresh_from_db()
        assert proposal.cached_heat_score == 5
        assert proposal.updated_at == original_updated_at

    @patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal')
    def test_ignores_inactive_proposals(self, mock_score):
        mock_score.return_value = 9
        proposal = BusinessProposal.objects.create(
            title='Inactive',
            client_name='Client',
            status='sent',
            is_active=False,
            cached_heat_score=1,
        )

        import content.tasks as tasks_module
        tasks_module.refresh_cached_heat_scores.call_local()

        proposal.refresh_from_db()
        assert proposal.cached_heat_score == 1
        assert mock_score.call_count == 0

    @patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal')
    def test_ignores_draft_proposals(self, mock_score):
        mock_score.return_value = 9
        proposal = BusinessProposal.objects.create(
            title='Draft',
            client_name='Client',
            status='draft',
            cached_heat_score=1,
        )

        import content.tasks as tasks_module
        tasks_module.refresh_cached_heat_scores.call_local()

        proposal.refresh_from_db()
        assert proposal.cached_heat_score == 1
        assert mock_score.call_count == 0


class TestRetiredCalculatorFollowupDescriptionFallback:
    @freeze_time('2026-03-10 12:00:00')
    def test_legacy_log_does_not_update_followup_timestamp(self):
        """Falla si ejecutar el job legado cambia el estado comercial de la propuesta."""
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='No Description',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
            automations_paused=False,
        )
        log = ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='calc_abandoned',
            description='',
        )
        ProposalChangeLog.objects.filter(pk=log.pk).update(
            created_at=now - timedelta(days=2),
        )

        import content.tasks as tasks_module
        tasks_module.check_calculator_abandonment_followup.call_local()

        proposal.refresh_from_db()
        assert proposal.calculator_followup_sent_at is None


class TestRefreshCachedHeatScores:
    """Tests for the refresh_cached_heat_scores periodic task (lines 909-928)."""

    @freeze_time('2026-03-10 12:00:00')
    def test_updates_cached_heat_score_when_score_changes(self):
        """Proposal's cached_heat_score is written when computed score differs."""
        proposal = BusinessProposal.objects.create(
            title='Heat Proposal', client_name='Client',
            status='viewed', cached_heat_score=3,
        )
        with patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal', return_value=8):
            import content.tasks as tasks_module
            tasks_module.refresh_cached_heat_scores.call_local()

        proposal.refresh_from_db()
        assert proposal.cached_heat_score == 8

    @freeze_time('2026-03-10 12:00:00')
    def test_does_not_write_when_score_is_unchanged(self):
        """No DB update is issued when computed score matches cached_heat_score."""
        proposal = BusinessProposal.objects.create(
            title='Same Score', client_name='Client',
            status='sent', cached_heat_score=5,
        )
        with patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal', return_value=5):
            import content.tasks as tasks_module
            tasks_module.refresh_cached_heat_scores.call_local()

        proposal.refresh_from_db()
        assert proposal.cached_heat_score == 5

    @freeze_time('2026-03-10 12:00:00')
    def test_skips_proposals_not_in_sent_or_viewed_status(self):
        """Draft proposals are excluded from the heat score refresh query."""
        BusinessProposal.objects.create(
            title='Draft Proposal', client_name='Client',
            status='draft', cached_heat_score=0,
        )
        with patch('content.services.proposal_analytics_service.compute_heat_score_for_proposal', return_value=9) as mock_compute:
            import content.tasks as tasks_module
            tasks_module.refresh_cached_heat_scores.call_local()

        assert mock_compute.call_count == 0, "Draft proposals should be excluded from heat score refresh"
        mock_compute.assert_not_called()


class TestNotifyProposalStageDeadlines:
    @patch(
        'content.services.proposal_stage_tracker.ProposalStageTracker.process',
    )
    def test_calls_tracker_for_proposals_with_active_stages(self, mock_process):
        """A proposal with at least one stage having dates and no completion is processed."""
        from datetime import date

        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='With Active Stage', client_name='C',
            client_email='c@x.com', status='accepted',
            automations_paused=False,
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
        )

        import content.tasks as tasks_module
        tasks_module.notify_proposal_stage_deadlines.call_local()

        assert mock_process.call_count == 1
        assert mock_process.call_args.args[0].pk == proposal.pk

    @patch(
        'content.services.proposal_stage_tracker.ProposalStageTracker.process',
    )
    def test_skips_paused_automations(self, mock_process):
        from datetime import date

        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='Paused', client_name='C',
            status='accepted', automations_paused=True,
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
        )

        import content.tasks as tasks_module
        tasks_module.notify_proposal_stage_deadlines.call_local()

        assert mock_process.call_count == 0

    @patch(
        'content.services.proposal_stage_tracker.ProposalStageTracker.process',
    )
    def test_skips_inactive_proposals(self, mock_process):
        from datetime import date

        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='Inactive', client_name='C',
            status='accepted', is_active=False,
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
        )

        import content.tasks as tasks_module
        tasks_module.notify_proposal_stage_deadlines.call_local()

        assert mock_process.call_count == 0

    @freeze_time('2026-04-10 12:00:00')
    @patch(
        'content.services.proposal_stage_tracker.ProposalStageTracker.process',
    )
    def test_skips_proposals_with_only_completed_stages(self, mock_process):
        from datetime import date

        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='Done', client_name='C', status='accepted',
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
            completed_at=timezone.now(),
        )

        import content.tasks as tasks_module
        tasks_module.notify_proposal_stage_deadlines.call_local()

        assert mock_process.call_count == 0

    @patch(
        'content.services.proposal_stage_tracker.ProposalStageTracker.process',
    )
    def test_skips_proposals_with_unscheduled_stages_only(self, mock_process):
        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='Empty', client_name='C', status='accepted',
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
        )

        import content.tasks as tasks_module
        tasks_module.notify_proposal_stage_deadlines.call_local()

        assert mock_process.call_count == 0

    @patch(
        'content.tasks.logger.exception',
    )
    @patch(
        'content.services.proposal_stage_tracker.ProposalStageTracker.process',
        side_effect=RuntimeError('tracker failed'),
    )
    def test_logs_and_continues_when_tracker_raises(self, mock_process, mock_log_exception):
        from datetime import date

        from content.models import ProposalProjectStage

        proposal = BusinessProposal.objects.create(
            title='Broken Stage Tracker', client_name='C',
            client_email='c@x.com', status='accepted',
            automations_paused=False,
        )
        ProposalProjectStage.objects.create(
            proposal=proposal, stage_key='design', order=0,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
        )

        import content.tasks as tasks_module
        tasks_module.notify_proposal_stage_deadlines.call_local()

        assert mock_process.call_count == 1
        assert mock_log_exception.call_count == 1
        mock_process.assert_called_once_with(proposal)
        mock_log_exception.assert_called_once()


class TestRunPlatformOnboardingTask:
    @pytest.fixture(autouse=True)
    def confirmed_link(self, accepted_proposal, django_user_model):
        from accounts.models import Deliverable, Project
        actor = django_user_model.objects.create_user(username='confirmed-task-admin', is_staff=True)
        project = Project.objects.create(client=actor, name='Confirmed')
        accepted_proposal.deliverable = Deliverable.objects.create(project=project, uploaded_by=actor, title='Confirmed')
        accepted_proposal.platform_approval_manifest = {'request_id': 'confirmed'}
        accepted_proposal.save()

    def test_returns_none_when_proposal_does_not_exist(self):
        import content.tasks as tasks_module

        result = tasks_module.run_platform_onboarding.call_local(99999)

        assert result is None

    def test_sets_completed_and_passes_acting_user(self, accepted_proposal, django_user_model):
        accepted_proposal.platform_onboarding_status = 'pending'
        accepted_proposal.save(update_fields=['platform_onboarding_status'])
        acting_user = django_user_model.objects.create_user(
            username='onboard-actor',
            password='pass123',
        )

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform'
        ) as mock_onboard:
            mock_onboard.return_value = {'skipped': False, 'deliverable_id': None, 'sync': {}}

            import content.tasks as tasks_module
            tasks_module.run_platform_onboarding.call_local(
                accepted_proposal.id,
                acting_user_id=acting_user.id,
                is_relaunch=False,
            )

        accepted_proposal.refresh_from_db()
        assert accepted_proposal.platform_onboarding_status == 'completed'
        _, kwargs = mock_onboard.call_args
        assert kwargs['acting_user'] == acting_user
        assert kwargs['send_email'] is False

    def test_sets_failed_when_onboarding_raises(self, accepted_proposal):
        accepted_proposal.platform_onboarding_status = 'pending'
        accepted_proposal.save(update_fields=['platform_onboarding_status'])

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform',
            side_effect=RuntimeError('sync failed'),
        ):
            import content.tasks as tasks_module
            tasks_module.run_platform_onboarding.call_local(accepted_proposal.id)

        accepted_proposal.refresh_from_db()
        assert accepted_proposal.platform_onboarding_status == 'failed'


# ── Task deadline notifications ────────────────────────────────────────────

class TestCheckSingleTaskDeadlines:
    """Unit tests for the _check_single_task_deadlines helper."""

    def _make_task(self, creation_date, due_date):
        """Create a Task with a controlled created_at date."""
        from datetime import datetime

        from content.models import Task

        with freeze_time(datetime.combine(creation_date, datetime.min.time())):
            task = Task.objects.create(title='Test task', due_date=due_date)
        return task

    def test_sends_40_pct_email_when_threshold_reached(self, mailoutbox):
        """Email sent at 40% elapsed; task flagged as notified_40."""
        from datetime import date

        from content.tasks import _check_single_task_deadlines

        # Created April 12, due May 12 (30 days total). Today April 24 = 40%.
        task = self._make_task(date(2026, 4, 12), date(2026, 5, 12))
        _check_single_task_deadlines(task, date(2026, 4, 24))

        task.refresh_from_db()
        assert task.notified_40 is True
        assert len(mailoutbox) == 1
        assert '40%' in mailoutbox[0].subject or 'límite' in mailoutbox[0].subject

    def test_sends_70_pct_email_when_threshold_reached(self, mailoutbox):
        """Email sent at 70% elapsed; task flagged as notified_70."""
        from datetime import date

        from content.tasks import _check_single_task_deadlines

        # Created April 3, due May 3 (30 days total). Today April 24 = 70%.
        task = self._make_task(date(2026, 4, 3), date(2026, 5, 3))
        task.notified_40 = True
        task.save(update_fields=['notified_40'])
        _check_single_task_deadlines(task, date(2026, 4, 24))

        task.refresh_from_db()
        assert task.notified_70 is True
        assert any('70%' in m.subject or 'límite' in m.subject for m in mailoutbox)

    def test_sends_100_pct_email_on_due_date(self, mailoutbox):
        """Email sent when today equals due_date; task flagged as notified_100."""
        from datetime import date

        from content.tasks import _check_single_task_deadlines

        task = self._make_task(date(2026, 4, 1), date(2026, 4, 24))
        task.notified_40 = True
        task.notified_70 = True
        task.save(update_fields=['notified_40', 'notified_70'])
        _check_single_task_deadlines(task, date(2026, 4, 24))

        task.refresh_from_db()
        assert task.notified_100 is True
        assert len(mailoutbox) >= 1

    def test_sends_overdue_reminder_when_past_due_date(self, mailoutbox):
        """Overdue reminder sent when today is after due_date."""
        from datetime import date

        from content.tasks import _check_single_task_deadlines

        task = self._make_task(date(2026, 4, 1), date(2026, 4, 23))
        task.notified_40 = True
        task.notified_70 = True
        task.notified_100 = True
        task.save(update_fields=['notified_40', 'notified_70', 'notified_100'])
        _check_single_task_deadlines(task, date(2026, 4, 24))

        task.refresh_from_db()
        assert task.last_overdue_notified_at == date(2026, 4, 24)
        assert len(mailoutbox) >= 1

    def test_suppresses_overdue_reminder_when_recently_notified(self, mailoutbox):
        """No overdue reminder sent if last_overdue_notified_at < 2 days ago."""
        from datetime import date

        from content.tasks import _check_single_task_deadlines

        task = self._make_task(date(2026, 4, 1), date(2026, 4, 23))
        task.notified_40 = True
        task.notified_70 = True
        task.notified_100 = True
        task.last_overdue_notified_at = date(2026, 4, 24)  # same day = < 2 days
        task.save(update_fields=['notified_40', 'notified_70', 'notified_100', 'last_overdue_notified_at'])
        _check_single_task_deadlines(task, date(2026, 4, 24))

        assert len(mailoutbox) == 0

    def test_skips_all_notifications_when_already_notified(self, mailoutbox):
        """No emails sent when all thresholds already flagged and no overdue."""
        from datetime import date

        from content.tasks import _check_single_task_deadlines

        # Task not yet at due date but all notifications already sent.
        task = self._make_task(date(2026, 4, 12), date(2026, 5, 12))
        task.notified_40 = True
        task.notified_70 = True
        task.save(update_fields=['notified_40', 'notified_70'])
        _check_single_task_deadlines(task, date(2026, 4, 24))

        assert len(mailoutbox) == 0


class TestCheckTaskDeadlineNotifications:
    """Integration tests for the periodic check_task_deadline_notifications task."""

    @freeze_time('2026-04-24')
    def test_periodic_task_processes_eligible_task(self, mailoutbox):
        """Periodic task sends email for task at 40% threshold."""
        from datetime import date

        from content.models import Task

        with freeze_time('2026-04-12 08:00:00'):
            task = Task.objects.create(title='Overdue task', due_date=date(2026, 5, 12))

        import content.tasks as tasks_module
        tasks_module.check_task_deadline_notifications.call_local()

        task.refresh_from_db()
        assert task.notified_40 is True
        assert len(mailoutbox) >= 1

    @freeze_time('2026-04-24')
    def test_periodic_task_skips_done_tasks(self, mailoutbox):
        """Periodic task ignores tasks with status DONE."""
        from datetime import date

        from content.models import Task

        with freeze_time('2026-04-12 08:00:00'):
            task = Task.objects.create(
                title='Done task', due_date=date(2026, 5, 12),
                status=Task.Status.DONE,
            )

        import content.tasks as tasks_module
        tasks_module.check_task_deadline_notifications.call_local()

        task.refresh_from_db()
        assert task.notified_40 is False
        assert len(mailoutbox) == 0


class TestCheckTaskAlertNotifications:
    """Tests for the check_task_alert_notifications periodic task."""

    @freeze_time('2026-04-24')
    def test_dispatches_pending_alert_and_marks_sent(self, mailoutbox):
        """Pending alert with notify_at <= today is sent and marked sent=True."""
        from datetime import date

        from content.models import Task, TaskAlert

        with freeze_time('2026-04-01 08:00:00'):
            task = Task.objects.create(title='Alert task', due_date=date(2026, 5, 1))
        alert = TaskAlert.objects.create(task=task, notify_at=date(2026, 4, 24), note='Check this')

        import content.tasks as tasks_module
        tasks_module.check_task_alert_notifications.call_local()

        alert.refresh_from_db()
        assert alert.sent is True
        assert len(mailoutbox) == 1
        assert 'Alert task' in mailoutbox[0].subject

    @freeze_time('2026-04-24')
    def test_skips_already_sent_alerts(self, mailoutbox):
        """Alerts with sent=True are not dispatched again."""
        from datetime import date

        from content.models import Task, TaskAlert

        with freeze_time('2026-04-01 08:00:00'):
            task = Task.objects.create(title='Sent alert task', due_date=date(2026, 5, 1))
        TaskAlert.objects.create(task=task, notify_at=date(2026, 4, 24), sent=True)

        import content.tasks as tasks_module
        tasks_module.check_task_alert_notifications.call_local()

        assert len(mailoutbox) == 0

    @freeze_time('2026-04-24')
    def test_skips_future_alerts(self, mailoutbox):
        """Alert with notify_at > today is not sent."""
        from datetime import date

        from content.models import Task, TaskAlert

        with freeze_time('2026-04-01 08:00:00'):
            task = Task.objects.create(title='Future alert task', due_date=date(2026, 5, 1))
        TaskAlert.objects.create(task=task, notify_at=date(2026, 5, 1))

        import content.tasks as tasks_module
        tasks_module.check_task_alert_notifications.call_local()

        assert len(mailoutbox) == 0


class TestNotifyProposalStageDeadlinesIntegration:
    """Tests for the notify_proposal_stage_deadlines periodic task."""

    def test_calls_tracker_for_eligible_proposals(self):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        """Proposals with active stages are passed to ProposalStageTracker.process."""
        from datetime import date

        proposal = BusinessProposal.objects.create(
            title='Staged proposal',
            client_name='Client',
            client_email='c@test.com',
            status='sent',
            is_active=True,
            automations_paused=False,
        )
        from content.models import ProposalProjectStage
        ProposalProjectStage.objects.create(
            proposal=proposal,
            stage_key=ProposalProjectStage.StageKey.DESIGN,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 5, 1),
        )

        with patch(
            'content.services.proposal_stage_tracker.ProposalStageTracker.process',
        ) as mock_process:
            import content.tasks as tasks_module
            tasks_module.notify_proposal_stage_deadlines.call_local()

        # quality: allow-call-contract (tracker boundary: verifies the task delegates to ProposalStageTracker.process with the correct proposal)
        mock_process.assert_called_once_with(proposal)

    def test_skips_paused_proposals(self):
        """Proposals with automations_paused=True are not processed."""
        from datetime import date

        proposal = BusinessProposal.objects.create(
            title='Paused proposal',
            client_name='Client',
            client_email='c@test.com',
            status='sent',
            is_active=True,
            automations_paused=True,
        )
        from content.models import ProposalProjectStage
        ProposalProjectStage.objects.create(
            proposal=proposal,
            stage_key=ProposalProjectStage.StageKey.DEVELOPMENT,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 5, 1),
        )

        with patch(
            'content.services.proposal_stage_tracker.ProposalStageTracker.process',
        ) as mock_process:
            import content.tasks as tasks_module
            tasks_module.notify_proposal_stage_deadlines.call_local()

        # quality: allow-call-contract (skip boundary: assert_not_called verifies the tracker is not invoked for paused proposals)
        mock_process.assert_not_called()


# -- Coverage gap tests: _suggest_action_for_proposal expiry branches --------


class TestSuggestActionExpiryBranches:
    @freeze_time('2026-03-10 12:00:00')
    def test_returns_urgency_message_when_expires_in_1_day_with_discount(self):
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Urgency With Discount', client_name='Client',
            status='sent',
            expires_at=now + timedelta(days=1),
            discount_percent=15,
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Expira en 1d.' in result
        assert 'urgencia' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_returns_discount_message_when_expires_in_2_days_without_discount(self):
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='No Discount', client_name='Client',
            status='sent',
            expires_at=now + timedelta(days=2),
            discount_percent=0,
        )
        result = _suggest_action_for_proposal(proposal, now)
        assert 'descuento' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_returns_viewed_recently_message_when_activity_within_2_days(self):
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Viewed Recent', client_name='Client',
            status='viewed',
            first_viewed_at=now - timedelta(hours=12),
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            last_activity_at=now - timedelta(hours=12),
        )
        proposal.refresh_from_db()
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Visto recientemente' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_returns_sent_long_ago_message_when_proposal_not_opened_in_3_days(self):
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Sent Long Ago', client_name='Client',
            status='sent',
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            sent_at=now - timedelta(days=4),
        )
        proposal.refresh_from_db()
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Sin abrir' in result

    @freeze_time('2026-03-10 12:00:00')
    def test_returns_sent_recently_message_when_proposal_sent_within_3_days(self):
        from content.tasks import _suggest_action_for_proposal
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Sent Recent', client_name='Client',
            status='sent',
        )
        BusinessProposal.objects.filter(pk=proposal.pk).update(
            sent_at=now - timedelta(days=1),
        )
        proposal.refresh_from_db()
        result = _suggest_action_for_proposal(proposal, now)
        assert 'Enviada recientemente' in result


# -- Coverage gap tests: calculator abandonment JSON parse error -------------


class TestRetiredCalculatorFollowupInvalidJson:
    @freeze_time('2026-03-10 12:00:00')
    def test_invalid_legacy_payload_does_not_create_alert(self):
        """Falla si un JSON histórico inválido vuelve a generar seguimiento."""
        from content.models import ProposalAlert
        now = timezone.now()
        proposal = BusinessProposal.objects.create(
            title='Invalid JSON Calc', client_name='Client',
            status='viewed',
            automations_paused=False,
        )
        log = ProposalChangeLog.objects.create(
            proposal=proposal, change_type='calc_abandoned',
            description='not-valid-json',
        )
        ProposalChangeLog.objects.filter(pk=log.pk).update(
            created_at=now - timedelta(hours=30),
        )

        import content.tasks as tasks_module
        tasks_module.check_calculator_abandonment_followup.call_local()

        alert = ProposalAlert.objects.filter(
            proposal=proposal, alert_type='calculator_followup',
        ).first()
        assert alert is None


# -- Coverage gap tests: engagement followup last_event is None --------------


class TestCheckEngagementFollowupsLastEventNone:
    @freeze_time('2026-03-10 12:00:00')
    @patch('content.services.proposal_email_service.ProposalEmailService.send_investment_interest_followup')
    def test_skips_investment_interest_when_no_view_events(self, mock_send):  # quality: disable no_assertions (mock assertion replaces assert keyword)
        now = timezone.now()
        BusinessProposal.objects.create(
            title='No View Events',
            client_name='Client',
            client_email='noevents@test.com',
            status='viewed',
            first_viewed_at=now - timedelta(hours=1),
            automations_paused=False,
        )

        import content.tasks as tasks_module
        tasks_module.check_engagement_followups.call_local()

        # quality: allow-call-contract (skip boundary: assert_not_called verifies no email is sent when there are no view events)
        mock_send.assert_not_called()


# -- Coverage gap tests: run_platform_onboarding is_relaunch -----------------


class TestRunPlatformOnboardingIsRelaunch:
    @pytest.fixture(autouse=True)
    def confirmed_link(self, accepted_proposal, django_user_model):
        from accounts.models import Deliverable, Project
        actor = django_user_model.objects.create_user(username='confirmed-retry-admin', is_staff=True)
        project = Project.objects.create(client=actor, name='Confirmed')
        accepted_proposal.deliverable = Deliverable.objects.create(project=project, uploaded_by=actor, title='Confirmed')
        accepted_proposal.platform_approval_manifest = {'request_id': 'confirmed'}
        accepted_proposal.save()

    def test_passes_send_email_false_when_is_relaunch_is_true(self, accepted_proposal):
        accepted_proposal.platform_onboarding_status = 'pending'
        accepted_proposal.save(update_fields=['platform_onboarding_status'])

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform',
        ) as mock_onboard:
            mock_onboard.return_value = {'skipped': False}

            import content.tasks as tasks_module
            tasks_module.run_platform_onboarding.call_local(
                accepted_proposal.id,
                is_relaunch=True,
            )

        _, kwargs = mock_onboard.call_args
        assert kwargs['send_email'] is False
