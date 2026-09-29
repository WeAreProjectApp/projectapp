"""Tests for ProposalEmailService.

Covers: send_reminder, send_urgency_email, send_response_notification —
happy paths, missing email, template rendering, error handling.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    BusinessProposal,
    EmailDeliverySnapshot,
    EmailLog,
    EmailTemplateConfig,
    ProposalChangeLog,
    ProposalShareLink,
)
from content.services.proposal_email_service import ProposalEmailService
from content.tests.email_stubs import stub_email_message

pytestmark = pytest.mark.django_db


def _stub_email():
    """Return a MIME-capable mock for EmailMultiAlternatives stubs."""
    return stub_email_message()


@pytest.fixture
def email_proposal(db):
    """A proposal with client_email set for email tests."""
    return BusinessProposal.objects.create(
        title='Email Test Proposal',
        client_name='Email Client',
        client_email='client@email-test.com',
        language='es',
        total_investment=Decimal('5000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=10),
        discount_percent=20,
    )


@pytest.fixture
def no_email_proposal(db):
    """A proposal without client_email."""
    return BusinessProposal.objects.create(
        title='No Email Proposal',
        client_name='No Email',
        client_email='',
        status='sent',
    )


class TestSendReminder:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_reminder_email_successfully(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Reminder</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        result = ProposalEmailService.send_reminder(email_proposal)

        assert result is True
        mock_email_instance.send.assert_called_once_with()
        email_proposal.refresh_from_db()
        assert email_proposal.reminder_sent_at is not None

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_reminder(no_email_proposal)

        assert result is False
        no_email_proposal.refresh_from_db()
        assert no_email_proposal.reminder_sent_at is None

    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_false_on_send_exception(self, mock_render, email_proposal):
        mock_render.side_effect = Exception('Template not found')

        result = ProposalEmailService.send_reminder(email_proposal)

        assert result is False

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_reminder_subject_contains_client_name(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>content</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        ProposalEmailService.send_reminder(email_proposal)

        mock_email_cls.assert_called_once()
        mock_email_instance.send.assert_called_once()
        call_kwargs = mock_email_cls.call_args[1]
        assert 'Email Client' in call_kwargs['subject']


class TestSendUrgencyEmail:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_urgency_email_with_discount(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Urgency</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        result = ProposalEmailService.send_urgency_email(email_proposal)

        assert result is True
        mock_email_instance.send.assert_called_once_with()
        email_proposal.refresh_from_db()
        assert email_proposal.urgency_email_sent_at is not None

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_urgency_email(no_email_proposal)

        assert result is False

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_no_discount_template_when_discount_is_zero(
        self, mock_render, mock_email_cls, email_proposal,
    ):
        """When discount_percent is 0, urgency email still sends but uses no-discount template."""
        email_proposal.discount_percent = 0
        email_proposal.save()
        mock_render.return_value = '<html>No discount urgency</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        result = ProposalEmailService.send_urgency_email(email_proposal)

        assert result is True
        mock_email_instance.send.assert_called_once_with()
        # Verify it uses the no-discount template
        template_calls = [c[0][0] for c in mock_render.call_args_list]
        assert 'emails/proposal_urgency_no_discount.html' in template_calls
        assert 'emails/proposal_urgency_no_discount.txt' in template_calls
        # Subject should NOT contain discount percentage
        call_kwargs = mock_email_cls.call_args[1]
        assert '20%' not in call_kwargs['subject']
        assert 'expira pronto' in call_kwargs['subject']

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_urgency_subject_contains_discount_percent(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>content</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        ProposalEmailService.send_urgency_email(email_proposal)

        mock_email_cls.assert_called_once()
        mock_email_instance.send.assert_called_once()
        call_kwargs = mock_email_cls.call_args[1]
        assert '20%' in call_kwargs['subject']

    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_false_on_send_exception(self, mock_render, email_proposal):
        mock_render.side_effect = Exception('Template error')

        result = ProposalEmailService.send_urgency_email(email_proposal)

        assert result is False


class TestSendResponseNotification:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_accepted_notification(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Accepted</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        result = ProposalEmailService.send_response_notification(email_proposal, 'accepted')

        assert result is True
        mock_email_instance.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_rejected_notification(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Rejected</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        result = ProposalEmailService.send_response_notification(email_proposal, 'rejected')

        assert result is True
        mock_email_cls.assert_called_once()
        mock_email_instance.send.assert_called_once()
        call_kwargs = mock_email_cls.call_args[1]
        assert 'REJECTED' in call_kwargs['subject']

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_accepted_subject_contains_tag(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>content</html>'
        mock_email_instance = _stub_email()
        mock_email_cls.return_value = mock_email_instance

        ProposalEmailService.send_response_notification(email_proposal, 'accepted')

        mock_email_cls.assert_called_once()
        mock_email_instance.send.assert_called_once()
        call_kwargs = mock_email_cls.call_args[1]
        assert '[ACCEPTED]' in call_kwargs['subject']
        assert email_proposal.title in call_kwargs['subject']

    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        mock_render.side_effect = Exception('Template error')

        result = ProposalEmailService.send_response_notification(email_proposal, 'accepted')

        assert result is False

    @override_settings(
        NOTIFICATION_EMAIL='team@projectapp.co,carlos18bp@gmail.com'
    )
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_to_all_notification_recipients(
        self, mock_render, mock_email_cls, email_proposal,
    ):
        mock_render.return_value = '<html>Accepted</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_response_notification(email_proposal, 'accepted')

        assert result is True
        call_kwargs = mock_email_cls.call_args[1]
        assert call_kwargs['to'] == [
            'team@projectapp.co',
            'carlos18bp@gmail.com',
        ]


class TestGetFromEmail:
    def test_returns_default_from_email_from_settings(self):
        with patch.object(ProposalEmailService, 'FROM_EMAIL', None):
            from_email = ProposalEmailService._get_from_email()
            assert from_email is not None

    def test_returns_class_from_email_when_set(self):
        with patch.object(ProposalEmailService, 'FROM_EMAIL', 'custom@test.com'):
            assert ProposalEmailService._get_from_email() == 'custom@test.com'


# ---------------------------------------------------------------------------
# Acceptance confirmation
# ---------------------------------------------------------------------------

class TestSendAcceptanceConfirmation:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    @patch('content.services.platform_onboarding_pdf.generate_platform_onboarding_pdf', return_value=None)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'%PDF-fake')
    def test_sends_with_pdf_attachment(self, mock_pdf, mock_tech, mock_guide, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Accepted</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_acceptance_confirmation(email_proposal)

        assert result is True
        mock_instance.attach.assert_called_once()
        mock_instance.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    @patch('content.services.platform_onboarding_pdf.generate_platform_onboarding_pdf', return_value=None)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
    def test_sends_without_pdf_when_generation_returns_none(self, mock_pdf, mock_tech, mock_guide, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Accepted</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_acceptance_confirmation(email_proposal)

        assert result is True
        mock_instance.attach.assert_not_called()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', side_effect=Exception('PDF error'))
    def test_sends_without_pdf_when_generation_fails(self, mock_pdf, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Accepted</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_acceptance_confirmation(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once()

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_acceptance_confirmation(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('Template error'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_acceptance_confirmation(email_proposal)
        assert result is False


# ---------------------------------------------------------------------------
# Rejection thank-you
# ---------------------------------------------------------------------------

class TestSendRejectionThankYou:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_rejection_thank_you(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Thank you</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_rejection_thank_you(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_rejection_thank_you(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_rejection_thank_you(email_proposal)
        assert result is False


# ---------------------------------------------------------------------------
# First-view notification
# ---------------------------------------------------------------------------

class TestSendFirstViewNotification:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_first_view_notification(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>First view</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_first_view_notification(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()
        call_kwargs = mock_email_cls.call_args[1]
        assert '[OPENED]' in call_kwargs['subject']

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_first_view_notification(email_proposal)
        assert result is False

    @patch(
        'content.services.proposal_email_service.EmailDeliveryGateway.send',
        return_value=0,
    )
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_false_when_backend_rejects_delivery(
        self, mock_render, mock_email_cls, mock_send, email_proposal,
    ):
        mock_render.return_value = '<html>First view</html>'
        mock_email_cls.return_value = _stub_email()

        result = ProposalEmailService.send_first_view_notification(email_proposal)

        assert result is False

    @patch(
        'content.services.email_log_service.record_send',
        side_effect=RuntimeError('database unavailable'),
    )
    @patch(
        'content.services.proposal_email_service.EmailDeliveryGateway.send',
        return_value=1,
    )
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_logging_failure_does_not_reinterpret_successful_delivery(
        self, mock_render, mock_email_cls, mock_send, mock_record,
        email_proposal,
    ):
        mock_render.return_value = '<html>First view</html>'
        mock_email_cls.return_value = _stub_email()

        result = ProposalEmailService.send_first_view_notification(
            email_proposal,
            raise_on_error=True,
        )

        assert result is True

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_context_without_additional_modules_matches_base(
        self, mock_render, mock_email_cls, email_proposal,
    ):
        mock_render.return_value = '<html>First view</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_first_view_notification(email_proposal)

        ctx = mock_render.call_args_list[0][0][1]
        assert ctx['has_additional_modules'] is False
        assert ctx['effective_total_investment'] == ctx['total_investment']

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_context_with_module_interest_preserves_manual_total(
        self, mock_render, mock_email_cls, email_proposal,
    ):
        email_proposal.module_interests = [{
            'id': 1,
            'slug': 'analytics',
            'name': 'Analítica avanzada',
        }]
        email_proposal.save(update_fields=['module_interests'])

        mock_render.return_value = '<html>First view</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_first_view_notification(email_proposal)

        ctx = mock_render.call_args_list[0][0][1]
        assert ctx['has_additional_modules'] is False
        assert ctx['effective_total_investment'] == ctx['total_investment']
        assert ctx['effective_total_investment'] == "5'000.000"


# ---------------------------------------------------------------------------
# Comment notification
# ---------------------------------------------------------------------------

class TestSendCommentNotification:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_comment_notification(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Comment</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_comment_notification(
            email_proposal, 'Can we negotiate?'
        )

        assert result is True
        mock_instance.send.assert_called_once_with()
        call_kwargs = mock_email_cls.call_args[1]
        assert '[COMENTARIO]' in call_kwargs['subject']

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_comment_notification(email_proposal, 'test')
        assert result is False


# ---------------------------------------------------------------------------
# Rejection re-engagement
# ---------------------------------------------------------------------------

class TestSendRejectionReengagement:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_reengagement_with_discount(self, mock_render, mock_email_cls, email_proposal):
        email_proposal.discount_percent = 15
        email_proposal.save(update_fields=['discount_percent'])
        mock_render.return_value = '<html>Reengage</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_rejection_reengagement(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_reengagement_without_discount(self, mock_render, mock_email_cls, email_proposal):
        """Re-engagement email sends successfully when discount_percent is zero."""
        email_proposal.discount_percent = 0
        email_proposal.save(update_fields=['discount_percent'])
        mock_render.return_value = '<html>Reengage</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_rejection_reengagement(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_rejection_reengagement(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_rejection_reengagement(email_proposal)
        assert result is False


# ---------------------------------------------------------------------------
# Revisit alert
# ---------------------------------------------------------------------------

class TestSendRevisitAlert:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_revisit_alert(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Alert</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_revisit_alert(
            email_proposal, visit_count=5, top_section='Investment', top_section_time=120,
        )

        assert result is True
        mock_instance.send.assert_called_once_with()
        email_proposal.refresh_from_db()
        assert email_proposal.revisit_alert_sent_at is not None

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_handles_empty_top_section(self, mock_render, mock_email_cls, email_proposal):
        """Revisit alert sends successfully when top_section is not provided."""
        mock_render.return_value = '<html>Alert</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_revisit_alert(email_proposal, visit_count=3)

        assert result is True
        mock_instance.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_revisit_alert(email_proposal, visit_count=3)
        assert result is False


# ---------------------------------------------------------------------------
# Abandonment followup
# ---------------------------------------------------------------------------

class TestSendAbandonmentFollowup:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_abandonment_followup(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Abandoned</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_abandonment_followup(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()
        email_proposal.refresh_from_db()
        assert email_proposal.abandonment_email_sent_at is not None

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_abandonment_followup(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_abandonment_followup(email_proposal)
        assert result is False


# ---------------------------------------------------------------------------
# Investment interest followup
# ---------------------------------------------------------------------------

class TestSendInvestmentInterestFollowup:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_investment_interest_followup(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Interest</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_investment_interest_followup(
            email_proposal, time_on_investment=120,
        )

        assert result is True
        mock_instance.send.assert_called_once_with()
        email_proposal.refresh_from_db()
        assert email_proposal.investment_interest_email_sent_at is not None

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_investment_interest_followup(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_investment_interest_followup(email_proposal, 90)
        assert result is False


# ---------------------------------------------------------------------------
# Share notification
# ---------------------------------------------------------------------------

class TestSendShareNotification:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_share_notification(self, mock_render, mock_email_cls, email_proposal):
        """Share notification sends to team with [SHARED] subject tag."""
        from content.models import ProposalShareLink
        share = ProposalShareLink.objects.create(
            proposal=email_proposal,
            shared_by_name='Alice',
            shared_by_email='alice@co.com',
        )
        mock_render.return_value = '<html>Shared</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_share_notification(email_proposal, share)

        assert result is True
        mock_instance.send.assert_called_once_with()
        call_kwargs = mock_email_cls.call_args[1]
        assert '[SHARED]' in call_kwargs['subject']

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        from content.models import ProposalShareLink
        share = ProposalShareLink.objects.create(
            proposal=email_proposal,
            shared_by_name='Alice',
        )
        result = ProposalEmailService.send_share_notification(email_proposal, share)
        assert result is False


# ---------------------------------------------------------------------------
# Scheduled followup
# ---------------------------------------------------------------------------

class TestSendScheduledFollowup:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_scheduled_followup(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Followup</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_scheduled_followup(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_scheduled_followup(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        result = ProposalEmailService.send_scheduled_followup(email_proposal)
        assert result is False


class TestSendStakeholderDetectedNotification:
    """Tests for send_stakeholder_detected_notification."""

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_notification_successfully(self, mock_render, mock_email_cls, email_proposal):
        """Stakeholder notification sends email and returns True."""
        mock_render.return_value = '<html>Stakeholder</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_stakeholder_detected_notification(
            email_proposal, 3
        )

        assert result is True
        mock_instance.send.assert_called_once_with()
        assert mock_render.call_count == 2

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        """Returns False when template rendering raises an exception."""
        result = ProposalEmailService.send_stakeholder_detected_notification(
            email_proposal, 2
        )
        assert result is False


class TestSendProposalToClientEdgePaths:
    def test_returns_placeholder_email_reason_when_no_client_email(self, no_email_proposal):
        """send_proposal_to_client reports placeholder_email when client_email is missing."""
        result = ProposalEmailService.send_proposal_to_client(no_email_proposal)
        assert result['ok'] is False
        assert result['reason'] == 'placeholder_email'

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('Template error'))
    def test_returns_send_failed_on_exception(self, mock_render, email_proposal):
        """send_proposal_to_client reports send_failed when template rendering fails."""
        result = ProposalEmailService.send_proposal_to_client(email_proposal)
        assert result['ok'] is False
        assert result['reason'] == 'send_failed'
        # The raw exception text is kept in logs, not surfaced to the user.
        assert 'Template error' not in result['detail']
        assert 'No se pudo enviar el correo' in result['detail']


class TestSendSellerInactivityEscalation:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_escalation_email_successfully(self, mock_render, mock_email_cls, email_proposal):
        """Escalation email sent to notification address with correct context."""
        mock_render.return_value = '<html>Escalation</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_seller_inactivity_escalation(email_proposal, 7)

        assert result is True
        mock_instance.send.assert_called_once_with()
        assert mock_render.call_count == 2

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        """Returns False when template rendering raises an exception."""
        result = ProposalEmailService.send_seller_inactivity_escalation(email_proposal, 5)
        assert result is False


class TestSendNegotiationNotification:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_notification_successfully(self, mock_render, mock_email_cls, email_proposal):
        """Negotiation notification sent to team with comment in context."""
        mock_render.return_value = '<html>Negotiate</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_negotiation_notification(
            email_proposal, comment='Reduce modules please'
        )

        assert result is True
        mock_instance.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        """Returns False when template rendering fails."""
        result = ProposalEmailService.send_negotiation_notification(email_proposal)
        assert result is False


class TestSendNegotiationConfirmation:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_confirmation_to_client(self, mock_render, mock_email_cls, email_proposal):
        """Negotiation confirmation sent to client_email."""
        mock_render.return_value = '<html>Confirm</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_negotiation_confirmation(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        """Returns False when proposal has no client_email."""
        result = ProposalEmailService.send_negotiation_confirmation(no_email_proposal)
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        """Returns False when template rendering fails."""
        result = ProposalEmailService.send_negotiation_confirmation(email_proposal)
        assert result is False


class TestSendPostExpirationVisitAlert:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_alert_successfully(self, mock_render, mock_email_cls, email_proposal):
        """Post-expiration visit alert sent to notification address."""
        mock_render.return_value = '<html>Expired Visit</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_post_expiration_visit_alert(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()
        assert mock_render.call_count == 2

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        """Returns False when template rendering fails."""
        result = ProposalEmailService.send_post_expiration_visit_alert(email_proposal)
        assert result is False


class TestSendProposalToClient:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_email_successfully(self, mock_render, mock_email_cls, email_proposal):
        """Sends initial proposal email to client."""
        mock_render.return_value = '<html>Proposal</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_proposal_to_client(email_proposal)

        assert result['ok'] is True
        assert result['reason'] == 'sent'
        mock_instance.send.assert_called_once_with()
        assert mock_render.call_count == 2

    def test_reports_placeholder_email_when_no_client_email(self, no_email_proposal):
        """Reports placeholder_email when proposal has no client_email."""
        result = ProposalEmailService.send_proposal_to_client(no_email_proposal)
        assert result['ok'] is False
        assert result['reason'] == 'placeholder_email'

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_reports_send_failed_on_exception(self, mock_render, email_proposal):
        """Reports send_failed when template rendering fails."""
        result = ProposalEmailService.send_proposal_to_client(email_proposal)
        assert result['ok'] is False
        assert result['reason'] == 'send_failed'


class TestSendProposalToClientEnrichedContext:
    """Tests for the enriched email context (email_intro, payment_options, total_duration) and PDF attachment added to send_proposal_to_client."""

    @pytest.fixture
    def proposal_with_sections(self, db):
        """Proposal with INVESTMENT and TIMELINE sections populated."""
        from content.models import ProposalSection

        proposal = BusinessProposal.objects.create(
            title='Fase 1 — Plataforma Jurídica',
            client_name='Juan García',
            client_email='juan@cliente.com',
            language='es',
            total_investment=Decimal('4320000'),
            currency='COP',
            status='sent',
            expires_at=timezone.now() + timezone.timedelta(days=15),
            email_intro='Esta primera fase contempla la plataforma base.',
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inversión',
            order=1,
            content_json={
                'paymentOptions': [
                    {'label': '40% al firmar', 'description': '$1.728.000 COP'},
                    {'label': '30% al aprobar diseño', 'description': '$1.296.000 COP'},
                    {'label': '30% al desplegar', 'description': '$1.296.000 COP'},
                ],
            },
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='timeline',
            title='Cronograma',
            order=2,
            content_json={'totalDuration': 'Aproximadamente 1 mes'},
        )
        return proposal

    def test_build_context_reads_sections(self, proposal_with_sections):
        ctx = ProposalEmailService._build_initial_email_context(proposal_with_sections)

        assert ctx['email_intro'] == 'Esta primera fase contempla la plataforma base.'
        assert ctx['total_duration'] == 'Aproximadamente 1 mes'
        assert len(ctx['payment_options']) == 3
        assert ctx['payment_options'][0]['label'] == '40% al firmar'
        assert ctx['payment_options'][0]['description'] == '$1.728.000 COP'
        assert ctx['payment_summary'] == '40/30/30'

    def test_build_context_keeps_email_intro_blank(self, db):
        proposal = BusinessProposal.objects.create(
            title='Sitio Demo',
            client_name='Carla',
            client_email='carla@x.com',
            email_intro='',
            status='sent',
        )

        ctx = ProposalEmailService._build_initial_email_context(proposal)

        assert ctx['email_intro'] == ''
        assert ctx['payment_options'] == []
        assert ctx['total_duration'] == ''
        assert ctx['payment_summary'] == ''

    @patch.object(
        ProposalEmailService,
        '_resolve_content',
        return_value={'body': 'CUERPO PREDEFINIDO'},
    )
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    def test_places_message_after_body_before_commercial_blocks(
        self, mock_email_cls, mock_pdf, mock_content, proposal_with_sections,
    ):
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_proposal_to_client(proposal_with_sections)

        assert result['ok'] is True
        text_body = mock_email_cls.call_args.kwargs['body']
        rendered_html = mock_instance.attach_alternative.call_args.args[0]
        for rendered in (text_body, rendered_html):
            assert rendered.index('CUERPO PREDEFINIDO') < rendered.index(
                proposal_with_sections.email_intro,
            )
            assert rendered.index(proposal_with_sections.email_intro) < rendered.index(
                'Inversión',
            )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    @patch.object(
        ProposalEmailService,
        '_resolve_content',
        return_value={'body': 'Cuerpo estable de la plantilla.'},
    )
    @patch.object(ProposalEmailService, '_attach_commercial_pdf', return_value=False)
    def test_saved_email_history_keeps_original_message(
        self, mock_attach, mock_content, proposal_with_sections,
    ):
        original = proposal_with_sections.email_intro

        result = ProposalEmailService.send_proposal_to_client(proposal_with_sections)
        snapshot = EmailDeliverySnapshot.objects.get(
            template_key='proposal_sent_client',
        )
        retained_text = snapshot.body.text
        proposal_with_sections.email_intro = 'Mensaje editado después del envío.'
        proposal_with_sections.save(update_fields=['email_intro'])

        assert result['ok'] is True
        snapshot.refresh_from_db()
        assert original in snapshot.body.text
        assert snapshot.body.text == retained_text
        assert proposal_with_sections.email_intro not in snapshot.body.text

    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_attaches_commercial_pdf(
        self, mock_render, mock_email_cls, mock_pdf, proposal_with_sections,
    ):
        mock_render.return_value = '<html>x</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance
        mock_pdf.return_value = b'%PDF-fake-bytes'

        result = ProposalEmailService.send_proposal_to_client(proposal_with_sections)

        assert result['ok'] is True
        mock_pdf.assert_called_once_with(proposal_with_sections)
        attach_calls = mock_instance.attach.call_args_list
        assert len(attach_calls) == 1
        filename, payload, mime = attach_calls[0].args
        assert filename.startswith('Propuesta_Comercial_')
        assert filename.endswith('.pdf')
        assert payload == b'%PDF-fake-bytes'
        assert mime == 'application/pdf'

        log = EmailLog.objects.get(template_key='proposal_sent_client')
        assert log.metadata.get('pdf_attached') is True

    @patch(
        'content.services.proposal_pdf_service.ProposalPdfService.generate',
        side_effect=RuntimeError('boom'),
    )
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_pdf_failure_does_not_block_send(
        self, mock_render, mock_email_cls, mock_pdf, proposal_with_sections,
    ):
        mock_render.return_value = '<html>x</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_proposal_to_client(proposal_with_sections)

        assert result['ok'] is True
        assert result['reason'] == 'sent'
        mock_instance.send.assert_called_once_with()
        mock_instance.attach.assert_not_called()

        log = EmailLog.objects.get(template_key='proposal_sent_client')
        assert log.metadata.get('pdf_attached') is False

    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    def test_renders_payment_options_in_html(
        self, mock_email_cls, mock_pdf, proposal_with_sections,
    ):
        """End-to-end render: the HTML template includes payment rows and intro text."""
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        ProposalEmailService.send_proposal_to_client(proposal_with_sections)

        html_call = mock_instance.attach_alternative.call_args
        assert html_call is not None
        rendered_html = html_call.args[0]
        assert 'Esta primera fase contempla la plataforma base.' in rendered_html
        assert 'Aproximadamente 1 mes' in rendered_html
        assert '40% al firmar' in rendered_html
        assert '$1.728.000 COP' in rendered_html
        assert 'team@projectapp.co' in rendered_html


class TestSendMultiProposalToClient:
    """Tests for ProposalEmailService.send_multi_proposal_to_client — multi-proposal envelope with N PDF attachments."""

    @pytest.fixture
    def two_proposals(self, db):
        from content.models import ProposalSection
        common_kwargs = dict(
            client_name='Juan García',
            client_email='juan@cliente.com',
            language='es',
            currency='COP',
            status='sent',
            expires_at=timezone.now() + timezone.timedelta(days=15),
        )
        p1 = BusinessProposal.objects.create(
            title='Fase 1 — Plataforma',
            total_investment=Decimal('4320000'),
            email_intro='Esta primera fase contempla la plataforma base.',
            **common_kwargs,
        )
        p2 = BusinessProposal.objects.create(
            title='Fase 2 — Vigilancia',
            total_investment=Decimal('14100000'),
            email_intro='La segunda fase suma un módulo de vigilancia.',
            **common_kwargs,
        )
        for proposal in (p1, p2):
            ProposalSection.objects.create(
                proposal=proposal, section_type='investment', title='Inversión',
                order=1,
                content_json={
                    'paymentOptions': [
                        {'label': '40% al firmar', 'description': '$x COP'},
                        {'label': '30% al aprobar', 'description': '$y COP'},
                        {'label': '30% al desplegar', 'description': '$z COP'},
                    ],
                },
            )
            ProposalSection.objects.create(
                proposal=proposal, section_type='timeline', title='Cronograma',
                order=2,
                content_json={'totalDuration': '1 mes'},
            )
        return [p1, p2]

    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    def test_sends_one_email_with_n_attachments(
        self, mock_email_cls, mock_pdf, two_proposals,
    ):
        """Single email is sent with one PDF attachment per proposal."""
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService.send_multi_proposal_to_client(two_proposals)

        assert result['ok'] is True
        assert result['reason'] == 'sent'
        mock_instance.send.assert_called_once_with()
        assert mock_instance.attach.call_count == 2

    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    def test_attachment_filenames_follow_naming_convention(
        self, mock_email_cls, mock_pdf, two_proposals,
    ):
        """Each PDF attachment follows the Propuesta_Comercial_*.pdf convention."""
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        ProposalEmailService.send_multi_proposal_to_client(two_proposals)

        for call in mock_instance.attach.call_args_list:
            filename, payload, mime = call.args
            assert filename.startswith('Propuesta_Comercial_')
            assert filename.endswith('.pdf')
            assert mime == 'application/pdf'

    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    def test_email_logs_one_entry_per_proposal_with_group_uuid(
        self, mock_email_cls, mock_pdf, two_proposals,
    ):
        """One EmailLog per proposal, all sharing the same group_uuid."""
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_multi_proposal_to_client(two_proposals)

        logs = EmailLog.objects.filter(template_key='proposal_multi_sent_client')
        assert logs.count() == 2
        group_uuids = {log.metadata.get('group_uuid') for log in logs}
        assert len(group_uuids) == 1
        assert all(log.metadata.get('group_size') == 2 for log in logs)
        assert all(log.metadata.get('pdfs_attached') == 2 for log in logs)

    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    def test_rendered_html_includes_each_proposal(
        self, mock_email_cls, mock_pdf, two_proposals,
    ):
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        ProposalEmailService.send_multi_proposal_to_client(two_proposals)

        rendered_html = mock_instance.attach_alternative.call_args.args[0]
        assert 'Fase 1 — Plataforma' in rendered_html
        assert 'Fase 2 — Vigilancia' in rendered_html
        assert 'Esta primera fase contempla la plataforma base.' in rendered_html
        assert 'La segunda fase suma un módulo de vigilancia.' in rendered_html
        assert 'Propuesta 1 de 2' in rendered_html
        assert 'Propuesta 2 de 2' in rendered_html

    def test_rejects_empty_proposals(self):
        result = ProposalEmailService.send_multi_proposal_to_client([])
        assert result['ok'] is False
        assert result['reason'] == 'no_proposals'

    def test_rejects_when_primary_email_missing(self, db):
        proposal = BusinessProposal.objects.create(
            title='Sin email', client_name='X', client_email='', status='draft',
        )
        result = ProposalEmailService.send_multi_proposal_to_client([proposal])
        assert result['ok'] is False
        assert result['reason'] == 'placeholder_email'


class TestSendMultiProposalsService:
    """Tests for ProposalService.send_multi_proposals — side effects."""

    @pytest.fixture
    def client_with_proposals(self, db):
        from accounts.models import UserProfile
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            username='multi_test_client',
            email='multi@cliente.com',
            password='x',
        )
        profile = UserProfile.objects.create(user=user, role='client')
        now = timezone.now()
        p_draft = BusinessProposal.objects.create(
            title='Draft', client=profile, client_name='Cli',
            client_email='multi@cliente.com', status='draft',
            email_intro='La primera propuesta resuelve el flujo inicial del cliente.',
            total_investment=Decimal('1000'),
        )
        p_expired = BusinessProposal.objects.create(
            title='Expired', client=profile, client_name='Cli',
            client_email='multi@cliente.com', status='expired',
            email_intro='La segunda propuesta recupera el alcance pendiente del cliente.',
            expires_at=now - timezone.timedelta(days=5),
            total_investment=Decimal('2000'),
        )
        p_sent = BusinessProposal.objects.create(
            title='Sent', client=profile, client_name='Cli',
            client_email='multi@cliente.com', status='sent',
            email_intro='La tercera propuesta amplía el resultado de negocio esperado.',
            sent_at=now - timezone.timedelta(days=3),
            expires_at=now + timezone.timedelta(days=10),
            total_investment=Decimal('3000'),
        )
        return [p_draft, p_expired, p_sent]

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    def test_applies_status_transitions(
        self, mock_pdf, mock_email_cls, client_with_proposals,
    ):
        """send_multi_proposals returns the correct per-proposal transition labels."""
        mock_email_cls.return_value = _stub_email()
        from content.services.proposal_service import ProposalService

        result = ProposalService.send_multi_proposals(client_with_proposals)

        assert result['ok'] is True
        transitions = result['transitions']
        p_draft, p_expired, p_sent = client_with_proposals
        assert transitions[p_draft.id] == 'sent'
        assert transitions[p_expired.id] == 'reopened'
        assert transitions[p_sent.id] == 'resent'

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
    def test_applies_status_transitions_updates_db_state(
        self, mock_pdf, mock_email_cls, client_with_proposals,
    ):
        """send_multi_proposals persists status changes and extends expiry for reopened proposals."""
        mock_email_cls.return_value = _stub_email()
        from content.services.proposal_service import ProposalService

        ProposalService.send_multi_proposals(client_with_proposals)

        p_draft, p_expired, _ = client_with_proposals
        p_draft.refresh_from_db()
        p_expired.refresh_from_db()
        assert p_draft.status == 'sent'
        assert p_draft.sent_at is not None
        assert p_expired.status in ('sent', 'viewed')
        assert p_expired.expires_at > timezone.now()

    def test_rejects_mixed_clients(self, db, client_with_proposals):
        # Create a proposal under a different client
        from accounts.models import UserProfile
        from django.contrib.auth import get_user_model
        User = get_user_model()
        other_user = User.objects.create_user(
            username='other', email='other@x.com', password='x',
        )
        other_profile = UserProfile.objects.create(user=other_user, role='client')
        other = BusinessProposal.objects.create(
            title='Other', client=other_profile, client_name='Otro',
            client_email='other@x.com', status='draft',
        )
        from content.services.proposal_service import ProposalService

        with pytest.raises(ValueError, match='mismo cliente') as exc_info:
            ProposalService.send_multi_proposals(
                [client_with_proposals[0], other],
            )
        assert 'mismo cliente' in str(exc_info.value)


class TestSendPostRejectionRevisitAlert:
    @freeze_time('2026-03-10 12:00:00')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_alert_successfully(self, mock_render, mock_email_cls, email_proposal):
        """Post-rejection revisit alert sent to notification address."""
        mock_render.return_value = '<html>Revisit</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance
        email_proposal.status = 'rejected'
        email_proposal.responded_at = timezone.now() - timezone.timedelta(days=10)
        email_proposal.save(update_fields=['status', 'responded_at'])

        result = ProposalEmailService.send_post_rejection_revisit_alert(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()
        assert mock_render.call_count == 2

    @freeze_time('2026-03-10 12:00:00')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_calculates_days_since_rejection(self, mock_render, mock_email_cls, email_proposal):
        """Days since rejection is computed from responded_at."""
        mock_render.return_value = '<html>Revisit</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance
        email_proposal.responded_at = timezone.now() - timezone.timedelta(days=15)
        email_proposal.save(update_fields=['responded_at'])

        result = ProposalEmailService.send_post_rejection_revisit_alert(email_proposal)

        assert result is True
        mock_instance.send.assert_called_once_with()
        call_ctx = mock_render.call_args_list[0][0][1]
        assert call_ctx['days_since_rejection'] == 15

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render, email_proposal):
        """Returns False when template rendering fails."""
        result = ProposalEmailService.send_post_rejection_revisit_alert(email_proposal)
        assert result is False


class TestSendDailyPipelineDigest:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_digest_successfully(self, mock_render, mock_email_cls):
        """Daily pipeline digest sent to notification address."""
        mock_render.return_value = '<html>Digest</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance
        digest_data = {
            'viewed_yesterday': [],
            'inactive': [],
            'expiring_soon': [],
            'total_active': 5,
            'date': '2026-03-10',
        }

        result = ProposalEmailService.send_daily_pipeline_digest(digest_data)

        assert result is True
        mock_instance.send.assert_called_once_with()
        assert mock_render.call_count == 2

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('err'))
    def test_returns_false_on_exception(self, mock_render):
        """Returns False when template rendering fails."""
        digest_data = {
            'viewed_yesterday': [], 'inactive': [], 'expiring_soon': [],
            'total_active': 0, 'date': '2026-03-10',
        }
        result = ProposalEmailService.send_daily_pipeline_digest(digest_data)
        assert result is False


# ---------------------------------------------------------------------------
# _log_email exception handling (lines 40-41)
# ---------------------------------------------------------------------------

class TestLogEmailExceptionHandling:
    @patch('content.services.proposal_email_service.logger')
    @patch(
        'content.services.email_log_service.record_send',
        side_effect=Exception('DB error'),
    )
    def test_logs_exception_when_email_log_writer_fails(
        self, mock_record_send, mock_logger,
    ):
        """_log_email logs an exception when the shared writer fails."""
        ProposalEmailService._log_email(
            'proposal_sent_client', 'test@example.com',
            subject='Test', proposal=None, status='sent',
        )

        mock_record_send.assert_called_once()
        assert mock_logger.exception.call_count == 1
        mock_logger.exception.assert_called_once_with('Failed to create EmailLog entry')


# ---------------------------------------------------------------------------
# _is_template_active with existing config (line 52)
# ---------------------------------------------------------------------------

class TestIsTemplateActiveWithConfig:
    def test_returns_false_when_config_exists_and_inactive(self):
        """_is_template_active returns False when EmailTemplateConfig.is_active is False."""
        EmailTemplateConfig.objects.create(
            template_key='proposal_sent_client',
            is_active=False,
        )

        result = ProposalEmailService._is_template_active('proposal_sent_client')

        assert result is False

    def test_returns_true_when_config_exists_and_active(self):
        """_is_template_active returns True when EmailTemplateConfig.is_active is True."""
        EmailTemplateConfig.objects.create(
            template_key='proposal_sent_client',
            is_active=True,
        )

        result = ProposalEmailService._is_template_active('proposal_sent_client')

        assert result is True


# ---------------------------------------------------------------------------
# Template-disabled early returns (lines 99-100, 181-182, ... 1454-1455)
# ---------------------------------------------------------------------------

class TestSendDocumentsToClient:
    """ProposalEmailService.send_documents_to_client — all code paths."""

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_email_with_multiple_attachments(self, mock_render, mock_email_cls, email_proposal):
        """Email is sent successfully with each attachment appended."""
        mock_render.return_value = '<html>Docs</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        attachments = [
            ('contrato.pdf', b'%PDF-1.4 contract', 'application/pdf'),
            ('anexo.pdf', b'%PDF-1.4 annex', 'application/pdf'),
        ]
        result = ProposalEmailService.send_documents_to_client(
            email_proposal,
            attachments=attachments,
            subject='Documentos de tu proyecto',
            greeting='Hola Test',
            body='Adjuntamos los documentos.',
            footer='Gracias.',
        )

        assert result is True
        mock_instance.send.assert_called_once_with()
        assert mock_instance.attach.call_count == 2

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_uses_provided_subject_and_body_fields(self, mock_render, mock_email_cls, email_proposal):
        """Custom subject, greeting, body, footer are passed to the email constructor."""
        mock_render.return_value = 'plain text'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        ProposalEmailService.send_documents_to_client(
            email_proposal,
            attachments=[],
            subject='Asunto personalizado',
            greeting='Querido Cliente',
            body='Cuerpo del mensaje.',
            footer='Pie de mensaje.',
        )

        call_kwargs = mock_email_cls.call_args
        assert call_kwargs[1]['subject'] == 'Asunto personalizado'

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        """Returns False immediately when proposal has no client_email."""
        result = ProposalEmailService.send_documents_to_client(
            no_email_proposal,
            attachments=[('doc.pdf', b'%PDF', 'application/pdf')],
        )
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('SMTP failure'))
    def test_returns_false_on_send_exception(self, mock_render, email_proposal):
        """Returns False and logs when email sending raises an exception."""
        result = ProposalEmailService.send_documents_to_client(
            email_proposal,
            attachments=[('doc.pdf', b'%PDF', 'application/pdf')],
            subject='S',
            greeting='G',
            body='B',
            footer='F',
        )
        assert result is False


class TestTemplateDisabledReturnsEarly:
    """Each send method returns False when its template is disabled via EmailTemplateConfig."""

    def _disable_template(self, template_key):
        EmailTemplateConfig.objects.create(
            template_key=template_key,
            is_active=False,
        )

    def test_send_proposal_to_client_reports_template_disabled(self, email_proposal):
        self._disable_template('proposal_sent_client')
        result = ProposalEmailService.send_proposal_to_client(email_proposal)
        assert result['ok'] is False
        assert result['reason'] == 'template_disabled'

    def test_send_reminder_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_reminder')
        assert ProposalEmailService.send_reminder(email_proposal) is False

    def test_send_urgency_email_returns_false_when_discount_template_disabled(self, email_proposal):
        self._disable_template('proposal_urgency')
        assert ProposalEmailService.send_urgency_email(email_proposal) is False

    def test_send_urgency_email_returns_false_when_no_discount_template_disabled(self, email_proposal):
        email_proposal.discount_percent = 0
        email_proposal.save(update_fields=['discount_percent'])
        self._disable_template('proposal_urgency_no_discount')
        assert ProposalEmailService.send_urgency_email(email_proposal) is False

    def test_send_response_notification_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_response_notification')
        assert ProposalEmailService.send_response_notification(email_proposal, 'accepted') is False

    def test_send_acceptance_confirmation_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_accepted_client')
        assert ProposalEmailService.send_acceptance_confirmation(email_proposal) is False

    def test_send_rejection_thank_you_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_rejected_client')
        assert ProposalEmailService.send_rejection_thank_you(email_proposal) is False

    def test_send_first_view_notification_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_first_view_notification')
        assert ProposalEmailService.send_first_view_notification(email_proposal) is False

    def test_send_comment_notification_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_comment_notification')
        assert ProposalEmailService.send_comment_notification(email_proposal, 'test') is False

    def test_send_rejection_reengagement_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_reengagement')
        assert ProposalEmailService.send_rejection_reengagement(email_proposal) is False

    def test_send_revisit_alert_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_revisit_alert')
        assert ProposalEmailService.send_revisit_alert(email_proposal, visit_count=3) is False

    def test_send_abandonment_followup_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_abandonment_followup')
        assert ProposalEmailService.send_abandonment_followup(email_proposal) is False

    def test_send_investment_interest_followup_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_investment_interest_followup')
        assert ProposalEmailService.send_investment_interest_followup(email_proposal) is False

    def test_send_share_notification_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_share_notification')
        share = ProposalShareLink.objects.create(
            proposal=email_proposal, shared_by_name='Alice',
        )
        assert ProposalEmailService.send_share_notification(email_proposal, share) is False

    def test_send_scheduled_followup_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_scheduled_followup')
        assert ProposalEmailService.send_scheduled_followup(email_proposal) is False

    def test_send_stakeholder_detected_notification_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_stakeholder_detected')
        assert ProposalEmailService.send_stakeholder_detected_notification(email_proposal, 3) is False

    def test_send_seller_inactivity_escalation_returns_false_when_disabled(self, email_proposal):
        self._disable_template('seller_inactivity_escalation')
        assert ProposalEmailService.send_seller_inactivity_escalation(email_proposal, 7) is False

    def test_send_negotiation_notification_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_negotiation_notification')
        assert ProposalEmailService.send_negotiation_notification(email_proposal) is False

    def test_send_negotiation_confirmation_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_negotiation_confirmation')
        assert ProposalEmailService.send_negotiation_confirmation(email_proposal) is False

    def test_send_post_rejection_revisit_alert_returns_false_when_disabled(self, email_proposal):
        self._disable_template('post_rejection_revisit_alert')
        assert ProposalEmailService.send_post_rejection_revisit_alert(email_proposal) is False

    def test_send_daily_pipeline_digest_returns_false_when_disabled(self):
        self._disable_template('daily_pipeline_digest')
        digest_data = {
            'viewed_yesterday': [], 'inactive': [], 'expiring_soon': [],
            'total_active': 0, 'date': '2026-03-10',
        }
        assert ProposalEmailService.send_daily_pipeline_digest(digest_data) is False

    def test_send_post_expiration_visit_alert_returns_false_when_disabled(self, email_proposal):
        self._disable_template('proposal_post_expiration_visit')
        assert ProposalEmailService.send_post_expiration_visit_alert(email_proposal) is False


# ── User-composed emails (branded & proposal) ──────────────────

class TestSendComposedEmail:
    """Tests for _send_composed_email shared implementation."""

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_sends_email_with_html_and_text_alternatives(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Test</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Subject',
            'Hola', ['Section 1'],
        )

        assert result is True
        mock_instance.attach_alternative.assert_called_once()
        mock_instance.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_logs_email_on_success(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>OK</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Subject',
            'Hola', ['Sec 1'], footer='Bye',
        )

        log = EmailLog.objects.get(proposal=email_proposal, template_key='branded_email')
        assert log.status == 'sent'
        assert log.metadata['greeting'] == 'Hola'
        assert log.metadata['sections'] == [{'text': 'Sec 1', 'markdown': False}]
        assert log.metadata['footer'] == 'Bye'

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_logs_email_on_failure(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>Fail</html>'
        mock_instance = _stub_email()
        mock_instance.send.side_effect = Exception('SMTP down')
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Subject',
            'Hi', ['Content'],
        )

        assert result is False
        log = EmailLog.objects.get(proposal=email_proposal, template_key='branded_email')
        assert log.status == 'failed'
        assert 'SMTP down' in log.error_message

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_renders_templates_from_registry(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>T</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Sub',
            'Hi', ['Sec'],
        )

        template_paths = [call[0][0] for call in mock_render.call_args_list]
        assert 'emails/branded_email.html' in template_paths
        assert 'emails/branded_email.txt' in template_paths

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_attaches_files_when_provided(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>A</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        attachments = [
            ('doc.pdf', b'pdfdata', 'application/pdf'),
            ('img.png', b'pngdata', 'image/png'),
        ]
        ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Sub',
            'Hi', ['Sec'], attachments=attachments,
        )

        assert mock_instance.attach.call_count == 2
        mock_instance.attach.assert_any_call('doc.pdf', b'pdfdata', 'application/pdf')

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_skips_attachments_when_none(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>N</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Sub',
            'Hi', ['Sec'], attachments=None,
        )

        assert mock_instance.attach.call_count == 0, "attach should not be called when attachments is None"
        mock_instance.attach.assert_not_called()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_metadata_includes_attachment_names(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>M</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Sub',
            'Hi', ['Sec'], attachments=[('file.pdf', b'data', 'application/pdf')],
        )

        log = EmailLog.objects.get(proposal=email_proposal, template_key='branded_email')
        assert log.metadata['attachment_names'] == ['file.pdf']

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_false_on_smtp_error(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>E</html>'
        mock_instance = _stub_email()
        mock_instance.send.side_effect = ConnectionError('refused')
        mock_email_cls.return_value = mock_instance

        result = ProposalEmailService._send_composed_email(
            'branded_email', email_proposal, 'test@example.com', 'Sub',
            'Hi', ['Sec'],
        )

        assert result is False


class TestSendBrandedEmail:
    """Tests for the send_branded_email wrapper."""

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_delegates_with_branded_template_key(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>B</html>'
        mock_email_cls.return_value = _stub_email()

        result = ProposalEmailService.send_branded_email(
            email_proposal, 'test@example.com', 'Subject', 'Hi', ['Sec'],
        )

        assert result is True
        log = EmailLog.objects.get(proposal=email_proposal)
        assert log.template_key == 'branded_email'

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_does_not_create_change_log(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>B</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_branded_email(
            email_proposal, 'test@example.com', 'Subject', 'Hi', ['Sec'],
        )

        assert not ProposalChangeLog.objects.filter(
            proposal=email_proposal, change_type='email_sent',
        ).exists()


class TestSendProposalEmailMethod:
    """Tests for the send_proposal_email wrapper with activity logging."""

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_creates_change_log_on_success(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>P</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_proposal_email(
            email_proposal, 'test@example.com', 'Proposal Email', 'Hi', ['Sec'],
        )

        log = ProposalChangeLog.objects.get(
            proposal=email_proposal, change_type='email_sent',
        )
        assert 'test@example.com' in log.description
        assert 'Proposal Email' in log.description

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_updates_last_activity_at_on_success(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>P</html>'
        mock_email_cls.return_value = _stub_email()
        old_activity = email_proposal.last_activity_at

        ProposalEmailService.send_proposal_email(
            email_proposal, 'test@example.com', 'Sub', 'Hi', ['Sec'],
        )

        email_proposal.refresh_from_db()
        assert email_proposal.last_activity_at != old_activity

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_does_not_create_change_log_on_failure(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>F</html>'
        mock_instance = _stub_email()
        mock_instance.send.side_effect = Exception('fail')
        mock_email_cls.return_value = mock_instance

        ProposalEmailService.send_proposal_email(
            email_proposal, 'test@example.com', 'Sub', 'Hi', ['Sec'],
        )

        assert not ProposalChangeLog.objects.filter(
            proposal=email_proposal, change_type='email_sent',
        ).exists()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_change_log_uses_enum_constants(self, mock_render, mock_email_cls, email_proposal):
        mock_render.return_value = '<html>E</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_proposal_email(
            email_proposal, 'test@example.com', 'Sub', 'Hi', ['Sec'],
        )

        log = ProposalChangeLog.objects.get(proposal=email_proposal)
        assert log.change_type == ProposalChangeLog.ChangeType.EMAIL_SENT
        assert log.actor_type == ProposalChangeLog.ActorType.SELLER


# ---------------------------------------------------------------------------
# Project-stage notifications (internal team)
# ---------------------------------------------------------------------------

from datetime import date  # noqa: E402

from content.models import ProposalProjectStage  # noqa: E402


@pytest.fixture
def stage_proposal(db):
    """A proposal in `accepted` status with stage rows attached."""
    proposal = BusinessProposal.objects.create(
        title='Stage Test Proposal',
        client_name='Stage Client',
        client_email='stageclient@test.com',
        language='es',
        total_investment=Decimal('15000000'),
        currency='COP',
        status='accepted',
        expires_at=timezone.now() + timezone.timedelta(days=10),
    )
    return proposal


@pytest.fixture
def design_stage(db, stage_proposal):
    return ProposalProjectStage.objects.create(
        proposal=stage_proposal,
        stage_key='design',
        order=0,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 11),
    )


class TestSendStageWarning:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_true_on_successful_send(
        self, mock_render, mock_email_cls, stage_proposal, design_stage,
    ):
        mock_render.return_value = '<html>warn</html>'
        mock_email_cls.return_value = _stub_email()

        result = ProposalEmailService.send_stage_warning(
            stage_proposal, design_stage, days_remaining=2,
        )

        assert result is True
        mock_email_cls.return_value.send.assert_called_once()

    @override_settings(NOTIFICATION_EMAIL='team@projectapp.co,carlos18bp@gmail.com')
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_uses_notification_recipients_from_settings(
        self, mock_render, mock_email_cls, stage_proposal, design_stage,
    ):
        mock_render.return_value = '<html>warn</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_stage_warning(
            stage_proposal, design_stage, days_remaining=2,
        )

        call_kwargs = mock_email_cls.call_args[1]
        assert call_kwargs['to'] == [
            'team@projectapp.co',
            'carlos18bp@gmail.com',
        ]

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_subject_contains_stage_label_and_client(
        self, mock_render, mock_email_cls, stage_proposal, design_stage,
    ):
        mock_render.return_value = '<html>warn</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_stage_warning(
            stage_proposal, design_stage, days_remaining=2,
        )

        subject = mock_email_cls.call_args[1]['subject']
        assert 'Diseño' in subject
        assert stage_proposal.client_name in subject

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_attaches_html_alternative(
        self, mock_render, mock_email_cls, stage_proposal, design_stage,
    ):
        mock_render.return_value = '<html>warn</html>'
        mock_instance = _stub_email()
        mock_email_cls.return_value = mock_instance

        ProposalEmailService.send_stage_warning(
            stage_proposal, design_stage, days_remaining=2,
        )

        mock_instance.attach_alternative.assert_called_once()
        args = mock_instance.attach_alternative.call_args.args
        assert args[1] == 'text/html'

    def test_returns_false_when_template_disabled(
        self, stage_proposal, design_stage,
    ):
        EmailTemplateConfig.objects.create(
            template_key='proposal_stage_warning_notification',
            is_active=False,
        )
        result = ProposalEmailService.send_stage_warning(
            stage_proposal, design_stage, days_remaining=2,
        )
        assert result is False

    @patch('content.services.proposal_email_service.render_to_string')
    def test_returns_false_on_exception(
        self, mock_render, stage_proposal, design_stage,
    ):
        mock_render.side_effect = Exception('boom')
        result = ProposalEmailService.send_stage_warning(
            stage_proposal, design_stage, days_remaining=2,
        )
        assert result is False


class TestSendStageOverdue:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_subject_contains_vencida_marker(
        self, mock_render, mock_email_cls, stage_proposal, design_stage,
    ):
        mock_render.return_value = '<html>overdue</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_stage_overdue(
            stage_proposal, design_stage, days_overdue=3,
        )

        subject = mock_email_cls.call_args[1]['subject']
        assert 'VENCIDA' in subject
        assert 'Diseño' in subject

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string')
    def test_text_body_includes_overdue_humanized_label(
        self, mock_render, mock_email_cls, stage_proposal, design_stage,
    ):
        mock_render.return_value = '<html>overdue</html>'
        mock_email_cls.return_value = _stub_email()

        ProposalEmailService.send_stage_overdue(
            stage_proposal, design_stage, days_overdue=8,
        )

        # The shared helper builds the context dict and passes it to
        # render_to_string. Inspect the second positional arg of the first call.
        first_call_context = mock_render.call_args_list[0].args[1]
        assert first_call_context['days_overdue'] == 8
        assert first_call_context['time_overdue_human'] == '1 semana 1 día'

    def test_returns_false_when_template_disabled(
        self, stage_proposal, design_stage,
    ):
        EmailTemplateConfig.objects.create(
            template_key='proposal_stage_overdue_notification',
            is_active=False,
        )
        result = ProposalEmailService.send_stage_overdue(
            stage_proposal, design_stage, days_overdue=3,
        )
        assert result is False


class TestRenderComposedEmail:
    """render_composed_email — shared render step for send + preview."""

    def test_plain_string_sections_render_pre_wrap_paragraphs(self):
        html, txt = ProposalEmailService.render_composed_email(
            'branded_email', None, 'Asunto', 'Hola',
            ['linea uno\nlinea dos'], 'Pie', [],
        )
        assert 'white-space:pre-wrap' in html
        assert 'linea uno' in html
        assert 'linea uno' in txt

    def test_markdown_sections_render_html_only_in_html_alternative(self):
        html, txt = ProposalEmailService.render_composed_email(
            'branded_email', None, 'Asunto', 'Hola',
            [{'text': '**negrita** y [web](https://projectapp.co)', 'markdown': True}],
            '', [],
        )
        assert '<strong style="font-weight:500;">negrita</strong>' in html
        assert '<a href="https://projectapp.co"' in html
        # The plain-text alternative keeps the raw markdown source.
        assert '**negrita**' in txt
        assert '<strong' not in txt

    def test_mixed_sections_and_elegant_footer_present(self):
        html, _ = ProposalEmailService.render_composed_email(
            'branded_email', None, 'Asunto', 'Hola',
            ['plano', {'text': '## Titulo', 'markdown': True}], '', ['doc.pdf'],
        )
        assert 'plano' in html
        assert 'font-size:19px' in html  # h2 heading from markdown
        assert 'background:#001713' in html  # dark contact footer
        assert 'doc.pdf' in html

    @override_settings(
        MAILERS={
            'default': {
                'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
            },
        },
    )
    def test_send_composed_email_logs_normalized_dict_metadata(self):
        result = ProposalEmailService._send_composed_email(
            'branded_email', None, 'client@example.com', 'Asunto', 'Hola',
            ['plano', {'text': '**md**', 'markdown': True}], 'Pie',
        )
        assert result is True
        log = EmailLog.objects.get(template_key='branded_email')
        assert log.metadata['sections'] == [
            {'text': 'plano', 'markdown': False},
            {'text': '**md**', 'markdown': True},
        ]
