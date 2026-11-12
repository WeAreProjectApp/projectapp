"""Tests targeting uncovered branches in proposal_email_service.py.

Covers: _get_notification_recipients list/fallback branches,
_check_cooldown cooldown-active path, _build_platform_context with deliverable,
send_finished_confirmation, send_magic_link_email,
send_documents_to_client (template disabled + fallback),
send_standalone_branded_email.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from content.models import BusinessProposal
from content.services.proposal_email_service import ProposalEmailService
from content.tests.email_stubs import stub_email_message

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def proposal(db):
    return BusinessProposal.objects.create(
        title='Gap Test Proposal',
        client_name='Gap Client',
        client_email='gapclient@example.com',
        language='es',
        total_investment=Decimal('8000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=7),
        discount_percent=10,
    )


@pytest.fixture
def no_email_proposal(db):
    return BusinessProposal.objects.create(
        title='No Email',
        client_name='No Email Client',
        client_email='',
        status='sent',
    )


# ===========================================================================
# _get_notification_recipients
# ===========================================================================

class TestGetNotificationRecipients:
    @override_settings(NOTIFICATION_EMAILS=['admin@a.com', 'ops@b.com'])
    def test_returns_list_when_setting_is_a_list(self):
        result = ProposalEmailService._get_notification_recipients()

        assert 'admin@a.com' in result
        assert 'ops@b.com' in result

    @override_settings(NOTIFICATION_EMAILS=None, NOTIFICATION_EMAIL=None)
    def test_returns_fallback_email_when_no_setting_configured(self):
        result = ProposalEmailService._get_notification_recipients()

        assert result == ['team@projectapp.co']


# ===========================================================================
# _check_cooldown
# ===========================================================================

class TestCheckCooldown:
    @freeze_time('2026-03-01 12:00:00')
    def test_returns_false_when_within_cooldown_period(self, proposal):
        # Set last_automated_email_at to 1 hour ago (within 24-hour cooldown)
        proposal.last_automated_email_at = timezone.now() - timezone.timedelta(hours=1)
        proposal.save()

        result = ProposalEmailService._check_cooldown(proposal)

        assert result is False

    @freeze_time('2026-03-01 12:00:00')
    def test_returns_true_and_updates_timestamp_when_cooldown_passed(self, proposal):
        # Set last_automated_email_at to 25 hours ago (outside cooldown)
        proposal.last_automated_email_at = timezone.now() - timezone.timedelta(hours=25)
        proposal.save()

        result = ProposalEmailService._check_cooldown(proposal)

        assert result is True
        proposal.refresh_from_db()
        assert proposal.last_automated_email_at == timezone.now()


# ===========================================================================
# _build_platform_context — deliverable present
# ===========================================================================

class TestBuildPlatformContextWithDeliverable:
    def test_includes_project_name_and_deliverable_title_when_deliverable_set(
        self, proposal, admin_user,
    ):
        from accounts.models import Deliverable, Project, UserProfile
        from django.contrib.auth import get_user_model
        from django.core.files.base import ContentFile

        User = get_user_model()
        client = User.objects.create_user(
            username='platclient@x.com', email='platclient@x.com', password='pass1!',
        )
        UserProfile.objects.create(user=client, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
        project = Project.objects.create(
            name='Platform Project', client=client, status=Project.STATUS_ACTIVE,
        )
        d = Deliverable.objects.create(
            project=project, title='API Module',
            category=Deliverable.CATEGORY_DOCUMENTS,
            file=ContentFile(b'pdf', name='api.pdf'),
            uploaded_by=admin_user,
        )
        proposal.deliverable = d
        proposal.save()

        ctx = ProposalEmailService._build_platform_context(proposal)

        assert ctx['project_name'] == 'Platform Project'
        assert ctx['deliverable_title'] == 'API Module'


@pytest.fixture
def admin_user(db):
    from accounts.models import UserProfile
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user(
        username='admin@gaps.com', email='admin@gaps.com', password='adminpass1!',
    )
    UserProfile.objects.create(user=u, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return u


# ===========================================================================
# send_finished_confirmation
# ===========================================================================

class TestSendFinishedConfirmation:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    def test_sends_finished_email_successfully(self, mock_render, mock_email_cls, proposal):
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        result = ProposalEmailService.send_finished_confirmation(proposal)

        assert result is True
        mock_email.send.assert_called_once()

    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_finished_confirmation(no_email_proposal)

        assert result is False

    @patch('content.services.proposal_email_service.render_to_string', side_effect=Exception('render fail'))
    def test_returns_false_on_exception(self, mock_render, proposal):
        result = ProposalEmailService.send_finished_confirmation(proposal)

        assert result is False


# ===========================================================================
# send_magic_link_email
# ===========================================================================

class TestSendMagicLinkEmail:
    def test_returns_false_when_proposals_list_is_empty(self):
        result = ProposalEmailService.send_magic_link_email('user@x.com', [])

        assert result is False

    def test_sends_magic_link_with_one_proposal(self, proposal, mailoutbox):
        result = ProposalEmailService.send_magic_link_email(
            'user@x.com', [proposal],
        )

        assert result is True
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['user@x.com']
        assert proposal.title in mailoutbox[0].body

    def test_sends_magic_link_with_multiple_proposals(self, proposal, db, mailoutbox):
        second = BusinessProposal.objects.create(
            title='Second Proposal',
            client_name='Gap Client',
            client_email='gapclient@example.com',
            status='sent',
        )
        result = ProposalEmailService.send_magic_link_email(
            'user@x.com', [proposal, second],
        )

        assert result is True
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['user@x.com']
        assert proposal.title in mailoutbox[0].body
        assert second.title in mailoutbox[0].body

    @patch('content.services.proposal_email_service.EmailMultiAlternatives.send', side_effect=Exception('smtp error'))
    def test_returns_false_on_send_exception(self, mock_send, proposal):
        result = ProposalEmailService.send_magic_link_email('user@x.com', [proposal])

        assert result is False
        mock_send.assert_called_once()


# ===========================================================================
# send_documents_to_client — template disabled + fallback content
# ===========================================================================

class TestSendDocumentsToClient:
    def test_returns_false_when_no_client_email(self, no_email_proposal):
        result = ProposalEmailService.send_documents_to_client(
            no_email_proposal, attachments=[],
        )

        assert result is False

    @patch('content.services.proposal_email_service.ProposalEmailService._is_template_active', return_value=False)
    def test_returns_false_when_template_disabled(self, mock_active, proposal):
        result = ProposalEmailService.send_documents_to_client(
            proposal, attachments=[],
        )

        assert result is False

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    def test_uses_fallback_content_when_fields_missing(
        self, mock_render, mock_email_cls, proposal,
    ):
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        # Call with no subject, greeting, body, or footer — triggers fallback
        result = ProposalEmailService.send_documents_to_client(
            proposal,
            attachments=[],
            subject=None,
            greeting=None,
            body=None,
            footer=None,
        )

        assert result is True
        assert mock_render.call_count == 2
        mock_email_cls.assert_called_once()
        mock_email.send.assert_called_once_with()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    def test_uses_provided_content_when_all_fields_given(
        self, mock_render, mock_email_cls, proposal,
    ):
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        result = ProposalEmailService.send_documents_to_client(
            proposal,
            attachments=[],
            subject='Custom Subject',
            greeting='Hi Client',
            body='Here are your docs.',
            footer='Thanks!',
        )

        assert result is True
        assert mock_render.call_count == 2
        mock_email_cls.assert_called_once()
        mock_email.send.assert_called_once_with()


# ===========================================================================
# send_standalone_branded_email
# ===========================================================================

class TestSendStandaloneBrandedEmail:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    def test_sends_standalone_branded_email(self, mock_render, mock_email_cls):
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        result = ProposalEmailService.send_standalone_branded_email(
            recipient_email='recipient@x.com',
            subject='Test Subject',
            greeting='Hello there',
            sections=[{'heading': 'Section', 'content': 'Body text.'}],
            footer='Footer text',
        )

        assert result is True
        assert mock_render.call_count == 2
        mock_email_cls.assert_called_once()
        mock_email.send.assert_called_once_with()


# ===========================================================================
# _check_cooldown return False in automated email functions
# ===========================================================================

class TestCheckCooldownReturnInEmailFunctions:
    @patch('content.services.proposal_email_service.ProposalEmailService._check_cooldown', return_value=False)
    def test_reminder_returns_false_when_cooldown_active(self, mock_cooldown, proposal):
        result = ProposalEmailService.send_reminder(proposal)

        assert result is False

    @patch('content.services.proposal_email_service.ProposalEmailService._check_cooldown', return_value=False)
    def test_urgency_returns_false_when_cooldown_active(self, mock_cooldown, proposal):
        result = ProposalEmailService.send_urgency_email(proposal)

        assert result is False

    @patch('content.services.proposal_email_service.ProposalEmailService._check_cooldown', return_value=False)
    def test_abandonment_followup_returns_false_when_cooldown_active(self, mock_cooldown, proposal):
        """send_abandonment_followup returns False when cooldown is active (line 1076)."""
        result = ProposalEmailService.send_abandonment_followup(proposal)

        assert result is False

    @patch('content.services.proposal_email_service.ProposalEmailService._check_cooldown', return_value=False)
    def test_investment_interest_followup_returns_false_when_cooldown_active(self, mock_cooldown, proposal):
        """send_investment_interest_followup returns False when cooldown is active (line 1152)."""
        result = ProposalEmailService.send_investment_interest_followup(proposal)

        assert result is False


# ===========================================================================
# send_finished_confirmation — template disabled
# ===========================================================================

class TestSendFinishedConfirmationTemplateDisabled:
    @patch('content.services.proposal_email_service.ProposalEmailService._is_template_active', return_value=False)
    def test_returns_false_when_template_disabled(self, mock_active, proposal):
        """send_finished_confirmation returns False when template is disabled (lines 673-674)."""
        result = ProposalEmailService.send_finished_confirmation(proposal)

        assert result is False


# ===========================================================================
# send_acceptance_confirmation — tech PDF + guide PDF exception branches
# ===========================================================================

class TestSendAcceptanceConfirmationPdfBranches:
    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    @patch('content.services.platform_onboarding_pdf.generate_platform_onboarding_pdf', return_value=None)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=b'%PDF-tech')
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
    def test_attaches_tech_pdf_when_generated(
        self, mock_pdf, mock_tech, mock_guide, mock_render, mock_email_cls, proposal,
    ):
        """email.attach is called for tech PDF when generate_technical_document_pdf returns bytes (line 597)."""
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        result = ProposalEmailService.send_acceptance_confirmation(proposal)

        assert result is True
        mock_email.attach.assert_called_once()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    @patch('content.services.platform_onboarding_pdf.generate_platform_onboarding_pdf', return_value=None)
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', side_effect=Exception('tech fail'))
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
    def test_continues_after_tech_pdf_exception(
        self, mock_pdf, mock_tech, mock_guide, mock_render, mock_email_cls, proposal,
    ):
        """Exception in tech PDF generation is silenced and email still sends (lines 602-603)."""
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        result = ProposalEmailService.send_acceptance_confirmation(proposal)

        assert result is True
        mock_email.send.assert_called_once()

    @patch('content.services.proposal_email_service.EmailMultiAlternatives')
    @patch('content.services.proposal_email_service.render_to_string', return_value='html')
    @patch('content.services.platform_onboarding_pdf.generate_platform_onboarding_pdf', side_effect=Exception('guide fail'))
    @patch('content.services.technical_document_pdf.generate_technical_document_pdf', return_value=None)
    @patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=None)
    def test_continues_after_guide_pdf_exception(
        self, mock_pdf, mock_tech, mock_guide, mock_render, mock_email_cls, proposal,
    ):
        """Exception in platform guide PDF generation is silenced and email still sends (lines 628-629)."""
        mock_email = stub_email_message()
        mock_email_cls.return_value = mock_email

        result = ProposalEmailService.send_acceptance_confirmation(proposal)

        assert result is True
        mock_email.send.assert_called_once()
