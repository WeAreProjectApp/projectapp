"""Tests for update_proposal_status (ACCEPTED branch) and _generate_and_save_contract_pdf."""
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from django.urls import reverse
from django.utils import timezone

from accounts.models import Deliverable, Project, ProjectIdea
from content.models import ProposalChangeLog, ProposalDocument

pytestmark = pytest.mark.django_db


class TestUpdateProposalStatusAccepted:
    def _url(self, proposal):
        return reverse('update-proposal-status', kwargs={'proposal_id': proposal.id})

    def test_returns_400_for_invalid_status(self, admin_client, proposal):
        resp = admin_client.patch(self._url(proposal), {'status': 'invalid'}, format='json')

        assert resp.status_code == 400
        assert resp.json()['code'] == 'invalid_status'

    def test_forced_transition_succeeds_and_logs_forced_marker(self, admin_client, proposal):
        # proposal fixture is 'draft' — jumping straight to 'accepted' is a
        # forced admin change: allowed, logged, and side-effect free.
        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.patch(self._url(proposal), {'status': 'accepted'}, format='json')

        assert resp.status_code == 200
        proposal.refresh_from_db()
        assert proposal.status == 'accepted'
        log = ProposalChangeLog.objects.get(
            proposal=proposal, change_type='status_change', new_value='accepted',
        )
        assert 'admin forced' in log.description
        mock_task.assert_not_called()

    def test_same_status_returns_400_with_same_status_code(self, admin_client, proposal):
        resp = admin_client.patch(self._url(proposal), {'status': 'draft'}, format='json')

        assert resp.status_code == 400
        body = resp.json()
        assert body['code'] == 'same_status'
        # Human message uses the Spanish status label, not the raw key.
        assert 'Borrador' in body['error']

    def test_forced_to_sent_does_not_send_email_or_set_sent_at(self, admin_client, viewed_proposal):
        # Only the natural draft→sent path may dispatch the client email.
        with patch('content.services.proposal_service.ProposalService.send_proposal') as mock_send:
            resp = admin_client.patch(self._url(viewed_proposal), {'status': 'sent'}, format='json')

        assert resp.status_code == 200
        viewed_proposal.refresh_from_db()
        assert viewed_proposal.status == 'sent'
        mock_send.assert_not_called()

    def test_forced_accepted_does_not_enqueue_onboarding(self, admin_client, sent_proposal):
        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.patch(self._url(sent_proposal), {'status': 'accepted'}, format='json')

        assert resp.status_code == 200
        mock_task.assert_not_called()

    def test_draft_to_sent_without_email_returns_missing_email_code(self, admin_client, proposal):
        # Real path (no mock): sending dispatches the client email, which requires
        # client_email. Empty email -> 400 with a descriptive code + hint.
        proposal.client_email = ''
        proposal.save(update_fields=['client_email'])

        resp = admin_client.patch(self._url(proposal), {'status': 'sent'}, format='json')

        assert resp.status_code == 400
        body = resp.json()
        assert body['error'] == 'Falta el correo del cliente.'
        assert body['code'] == 'missing_client_email'
        assert body['hint']  # actionable hint present
        proposal.refresh_from_db()
        assert proposal.status == 'draft'  # not transitioned

    def test_creates_changelog_on_valid_transition(self, admin_client, sent_proposal):
        # sent → negotiating is an allowed transition
        resp = admin_client.patch(self._url(sent_proposal), {'status': 'negotiating'}, format='json')

        assert resp.status_code == 200
        assert ProposalChangeLog.objects.filter(
            proposal=sent_proposal,
            change_type='status_change',
            new_value='negotiating',
        ).exists()

    def test_accepted_transition_waits_for_internal_review(self, admin_client, negotiating_proposal):
        # Commercial acceptance waits for explicit internal binding.
        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.patch(
                self._url(negotiating_proposal), {'status': 'accepted'}, format='json'
            )

        assert resp.status_code == 200
        negotiating_proposal.refresh_from_db()
        assert negotiating_proposal.status == 'accepted'
        mock_task.assert_not_called()
        assert negotiating_proposal.deliverable_id is None
        assert negotiating_proposal.project_review_required is True

    @freeze_time('2026-01-15 12:00:00')
    def test_accepted_transition_skips_onboarding_when_already_completed(
        self, admin_client, negotiating_proposal,
    ):
        from django.utils import timezone

        negotiating_proposal.platform_onboarding_completed_at = timezone.now()
        negotiating_proposal.save(update_fields=['platform_onboarding_completed_at'])

        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.patch(
                self._url(negotiating_proposal), {'status': 'accepted'}, format='json'
            )

        assert resp.status_code == 200
        mock_task.assert_not_called()

    def test_non_accepted_transition_does_not_call_platform_onboarding(
        self, admin_client, sent_proposal
    ):
        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform'
        ) as mock_accept:
            resp = admin_client.patch(
                self._url(sent_proposal), {'status': 'negotiating'}, format='json'
            )

        assert resp.status_code == 200
        mock_accept.assert_not_called()

    def test_returns_401_for_unauthenticated(self, api_client, sent_proposal):
        resp = api_client.patch(self._url(sent_proposal), {'status': 'negotiating'}, format='json')

        assert resp.status_code == 401


class TestRespondToProposalPendingReview:
    """Public acceptance records the deal without platform provisioning."""

    def _url(self, proposal):
        return reverse('respond-to-proposal', kwargs={'proposal_uuid': proposal.uuid})

    def test_client_accept_leaves_project_review_pending(
        self, api_client, viewed_proposal,
    ):
        with patch('content.tasks.run_platform_onboarding') as mock_task, patch(
            'content.services.proposal_email_service.ProposalEmailService'
        ) as mock_email_svc:
            resp = api_client.post(
                self._url(viewed_proposal), {'action': 'accepted'}, format='json',
            )

        assert resp.status_code == 200
        viewed_proposal.refresh_from_db()
        assert viewed_proposal.status == 'accepted'
        # The view owns the acceptance email (sent exactly once)...
        mock_email_svc.send_acceptance_confirmation.assert_called_once_with(viewed_proposal)
        mock_task.assert_not_called()
        assert viewed_proposal.deliverable_id is None
        assert viewed_proposal.project_review_required is True

    def test_client_reject_does_not_enqueue_onboarding(self, api_client, viewed_proposal):
        with patch('content.tasks.run_platform_onboarding') as mock_task, patch(
            'content.services.proposal_email_service.ProposalEmailService'
        ):
            resp = api_client.post(
                self._url(viewed_proposal), {'action': 'rejected', 'reason': 'x'}, format='json',
            )

        assert resp.status_code == 200
        mock_task.assert_not_called()


class TestUpdateProposalStatusFinished:
    """Tests for transitioning an accepted proposal to the finished state."""

    def _url(self, proposal):
        return reverse('update-proposal-status', kwargs={'proposal_id': proposal.id})

    def test_finished_transition_from_accepted_succeeds(self, admin_client, accepted_proposal):
        with patch(
            'content.services.proposal_email_service.ProposalEmailService.send_finished_confirmation'
        ):
            resp = admin_client.patch(
                self._url(accepted_proposal), {'status': 'finished'}, format='json'
            )

        assert resp.status_code == 200
        accepted_proposal.refresh_from_db()
        assert accepted_proposal.status == 'finished'

    def test_finished_transition_creates_changelog(self, admin_client, accepted_proposal):
        with patch(
            'content.services.proposal_email_service.ProposalEmailService.send_finished_confirmation'
        ):
            admin_client.patch(
                self._url(accepted_proposal), {'status': 'finished'}, format='json'
            )

        assert ProposalChangeLog.objects.filter(
            proposal=accepted_proposal,
            change_type='status_change',
            old_value='accepted',
            new_value='finished',
        ).exists()

    def test_finished_transition_triggers_finished_email(self, admin_client, accepted_proposal):
        with patch(
            'content.services.proposal_email_service.ProposalEmailService.send_finished_confirmation'
        ) as mock_send:
            admin_client.patch(
                self._url(accepted_proposal), {'status': 'finished'}, format='json'
            )

        mock_send.assert_called_once()
        called_with = mock_send.call_args[0][0]
        assert called_with.id == accepted_proposal.id

    def test_forced_finished_from_sent_does_not_send_finished_email(self, admin_client, sent_proposal):
        with patch(
            'content.services.proposal_email_service.ProposalEmailService.send_finished_confirmation'
        ) as mock_send:
            resp = admin_client.patch(
                self._url(sent_proposal), {'status': 'finished'}, format='json'
            )

        assert resp.status_code == 200
        sent_proposal.refresh_from_db()
        assert sent_proposal.status == 'finished'
        mock_send.assert_not_called()

    def test_forced_backwards_to_draft_succeeds(self, admin_client, accepted_proposal):
        resp = admin_client.patch(
            self._url(accepted_proposal), {'status': 'draft'}, format='json'
        )

        assert resp.status_code == 200
        accepted_proposal.refresh_from_db()
        assert accepted_proposal.status == 'draft'
        assert ProposalChangeLog.objects.filter(
            proposal=accepted_proposal,
            change_type='status_change',
            old_value='accepted',
            new_value='draft',
        ).exists()


class TestLaunchToPlatform:
    """The old route cannot provision or destructively relaunch without review."""

    @pytest.mark.parametrize('body', [{}, {'force': True}])
    def test_missing_review_is_rejected(self, admin_client, accepted_proposal, body):
        response = admin_client.post(reverse('launch-to-platform', kwargs={'proposal_id': accepted_proposal.pk}), body, format='json')
        assert response.status_code == 400
        accepted_proposal.refresh_from_db()
        assert accepted_proposal.deliverable_id is None
        assert not Project.objects.exists()

    def test_force_preserves_operational_project(self, admin_client, admin_user, accepted_proposal):
        project = Project.objects.create(client=admin_user, name='Operational')
        deliverable = Deliverable.objects.create(project=project, uploaded_by=admin_user, title='Linked')
        accepted_proposal.deliverable = deliverable
        accepted_proposal.save(update_fields=['deliverable'])
        response = admin_client.post(reverse('launch-to-platform', kwargs={'proposal_id': accepted_proposal.pk}), {'force': True}, format='json')
        assert response.status_code == 400
        accepted_proposal.refresh_from_db()
        assert accepted_proposal.deliverable_id == deliverable.pk
        assert Project.objects.filter(pk=project.pk).exists()

    def test_launch_requires_panel_session(self, api_client, accepted_proposal):
        response = api_client.post(reverse('launch-to-platform', kwargs={'proposal_id': accepted_proposal.pk}), {}, format='json')
        assert response.status_code == 403


class TestRunPlatformOnboardingTask:
    """Task retries require an explicitly confirmed association."""

    @pytest.fixture(autouse=True)
    def confirmed_link(self, accepted_proposal, negotiating_proposal, admin_user):
        project = Project.objects.create(client=admin_user, name='Confirmed')
        first = Deliverable.objects.create(project=project, uploaded_by=admin_user, title='Accepted')
        second = Deliverable.objects.create(project=project, uploaded_by=admin_user, title='Negotiating')
        accepted_proposal.deliverable = first
        accepted_proposal.platform_approval_manifest = {'request_id': 'confirmed'}
        accepted_proposal.save()
        negotiating_proposal.deliverable = second
        negotiating_proposal.platform_approval_manifest = {'request_id': 'confirmed'}
        negotiating_proposal.save()


    def test_task_sets_completed_on_success(self, accepted_proposal):
        accepted_proposal.platform_onboarding_status = 'pending'
        accepted_proposal.save(update_fields=['platform_onboarding_status'])

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform'
        ) as mock_onboard:
            mock_onboard.return_value = {'skipped': False, 'deliverable_id': None, 'sync': {}}
            from content.tasks import run_platform_onboarding
            run_platform_onboarding.call_local(accepted_proposal.id, is_relaunch=False)

        accepted_proposal.refresh_from_db()
        assert accepted_proposal.platform_onboarding_status == 'completed'
        mock_onboard.assert_called_once()
        _, kwargs = mock_onboard.call_args
        assert kwargs['send_email'] is False

    def test_task_sets_failed_on_exception(self, accepted_proposal):
        accepted_proposal.platform_onboarding_status = 'pending'
        accepted_proposal.save(update_fields=['platform_onboarding_status'])

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform'
        ) as mock_onboard:
            mock_onboard.side_effect = RuntimeError('sync failed')
            from content.tasks import run_platform_onboarding
            run_platform_onboarding.call_local(accepted_proposal.id, is_relaunch=False)

        accepted_proposal.refresh_from_db()
        assert accepted_proposal.platform_onboarding_status == 'failed'

    def test_task_skips_email_on_relaunch(self, accepted_proposal):
        accepted_proposal.platform_onboarding_status = 'pending'
        accepted_proposal.save(update_fields=['platform_onboarding_status'])

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform'
        ) as mock_onboard:
            mock_onboard.return_value = {'skipped': False, 'deliverable_id': None, 'sync': {}}
            from content.tasks import run_platform_onboarding
            run_platform_onboarding.call_local(accepted_proposal.id, is_relaunch=True)

        _, kwargs = mock_onboard.call_args
        assert kwargs['send_email'] is False

    def test_task_skips_acceptance_email_when_negotiating(self, negotiating_proposal):
        # First launch from negotiation must NOT send the "propuesta aceptada" email.
        negotiating_proposal.platform_onboarding_status = 'pending'
        negotiating_proposal.save(update_fields=['platform_onboarding_status'])

        with patch(
            'accounts.services.proposal_platform_onboarding.handle_proposal_accepted_for_platform'
        ) as mock_onboard:
            mock_onboard.return_value = {'skipped': False, 'deliverable_id': None, 'sync': {}}
            from content.tasks import run_platform_onboarding
            run_platform_onboarding.call_local(negotiating_proposal.id, is_relaunch=False)

        _, kwargs = mock_onboard.call_args
        assert kwargs['send_email'] is False


class TestGenerateAndSaveContractPdf:
    def test_saves_contract_document_when_pdf_generated(self, proposal):
        with patch('content.services.contract_pdf_service.generate_contract_pdf') as mock_gen:
            mock_gen.return_value = b'%PDF-1.4 fake pdf content'
            from content.views.proposal import _generate_and_save_contract_pdf
            _generate_and_save_contract_pdf(proposal)

        assert ProposalDocument.objects.filter(
            proposal=proposal,
            document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        ).exists()

    def test_returns_early_when_pdf_generation_returns_none(self, proposal):
        with patch('content.services.contract_pdf_service.generate_contract_pdf') as mock_gen:
            mock_gen.return_value = None
            from content.views.proposal import _generate_and_save_contract_pdf
            _generate_and_save_contract_pdf(proposal)

        assert not ProposalDocument.objects.filter(
            proposal=proposal,
            document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        ).exists()

    def test_get_or_create_prevents_duplicate_contract_documents(self, proposal):
        with patch('content.services.contract_pdf_service.generate_contract_pdf') as mock_gen:
            mock_gen.return_value = b'%PDF-1.4 fake pdf content'
            from content.views.proposal import _generate_and_save_contract_pdf
            _generate_and_save_contract_pdf(proposal)
            _generate_and_save_contract_pdf(proposal)

        assert ProposalDocument.objects.filter(
            proposal=proposal,
            document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        ).count() == 1
