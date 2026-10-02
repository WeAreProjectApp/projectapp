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

    def test_accepted_transition_triggers_platform_onboarding(self, admin_client, negotiating_proposal):
        # negotiating → accepted now auto-enqueues platform onboarding.
        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.patch(
                self._url(negotiating_proposal), {'status': 'accepted'}, format='json'
            )

        assert resp.status_code == 200
        negotiating_proposal.refresh_from_db()
        assert negotiating_proposal.status == 'accepted'
        mock_task.assert_called_once()
        # Admin inline accept sends no client email today, so the task suppresses
        # its own acceptance email.
        assert mock_task.call_args.kwargs.get('send_email') is False

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


class TestRespondToProposalTriggersOnboarding:
    """Client acceptance (respond_to_proposal) auto-provisions the platform project."""

    def _url(self, proposal):
        return reverse('respond-to-proposal', kwargs={'proposal_uuid': proposal.uuid})

    def test_client_accept_enqueues_onboarding_and_sends_single_email(
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
        # ...and the onboarding task is enqueued with its own email suppressed.
        mock_task.assert_called_once()
        assert mock_task.call_args.kwargs.get('send_email') is False
        assert mock_task.call_args.kwargs.get('acting_user_id') is None

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
    """Tests for the launch_to_platform view.

    The view queues a Huey task (run_platform_onboarding) for the heavy
    lifting.  We mock the task itself so we only test view logic here:
    validation, teardown, status flags, and changelog creation.
    """

    def _url(self, proposal):
        return reverse('launch-to-platform', kwargs={'proposal_id': proposal.id})

    def test_launch_to_platform_first_time(self, admin_client, accepted_proposal):
        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.post(self._url(accepted_proposal), format='json')

        assert resp.status_code == 200
        assert resp.json()['platform_onboarding_status'] == 'pending'
        mock_task.assert_called_once_with(
            accepted_proposal.id,
            acting_user_id=resp.wsgi_request.user.id,
            is_relaunch=False,
        )

    def test_launch_to_platform_not_accepted_returns_400(self, admin_client, sent_proposal):
        resp = admin_client.post(self._url(sent_proposal), format='json')

        assert resp.status_code == 400
        assert 'aceptada' in resp.json()['error']

    def test_launch_to_platform_from_negotiating_returns_200(
        self, admin_client, negotiating_proposal
    ):
        with patch('content.tasks.run_platform_onboarding') as mock_task:
            resp = admin_client.post(self._url(negotiating_proposal), format='json')

        assert resp.status_code == 200
        assert resp.json()['platform_onboarding_status'] == 'pending'
        mock_task.assert_called_once_with(
            negotiating_proposal.id,
            acting_user_id=resp.wsgi_request.user.id,
            is_relaunch=False,
        )

    def test_launch_to_platform_already_onboarded_no_force_returns_409(self, admin_client, accepted_proposal):
        accepted_proposal.platform_onboarding_completed_at = '2026-04-01T10:00:00Z'
        accepted_proposal.save(update_fields=['platform_onboarding_completed_at'])

        resp = admin_client.post(self._url(accepted_proposal), format='json')

        assert resp.status_code == 409
        assert resp.json()['warning'] == 'already_onboarded'

    def test_launch_to_platform_already_onboarded_with_force_calls_teardown(
        self, admin_client, accepted_proposal
    ):
        accepted_proposal.platform_onboarding_completed_at = '2026-04-01T10:00:00Z'
        accepted_proposal.save(update_fields=['platform_onboarding_completed_at'])

        with patch(
            'accounts.services.proposal_platform_onboarding.teardown_platform_for_proposal'
        ) as mock_teardown, patch(
            'content.tasks.run_platform_onboarding'
        ) as mock_task:
            resp = admin_client.post(
                self._url(accepted_proposal), {'force': True}, format='json'
            )

        assert resp.status_code == 200
        mock_teardown.assert_called_once()
        mock_task.assert_called_once()
        _, kwargs = mock_task.call_args
        assert kwargs['is_relaunch'] is True

    def test_force_relaunch_with_platform_information_preserves_existing_onboarding(
        self, admin_client, admin_user, accepted_proposal,
    ):
        """Fails if a blocked force relaunch unlinks evidence or enqueues background work."""
        project = Project.objects.create(name='Relaunch evidence', client=admin_user)
        deliverable = Deliverable.objects.create(
            project=project, category=Deliverable.CATEGORY_DOCUMENTS,
            title='Proposal evidence', uploaded_by=admin_user,
        )
        completed_at = timezone.now()
        accepted_proposal.deliverable = deliverable
        accepted_proposal.platform_onboarding_completed_at = completed_at
        accepted_proposal.save(update_fields=[
            'deliverable_id', 'platform_onboarding_completed_at',
        ])
        idea = ProjectIdea.objects.create(
            project=project, author=admin_user, author_label='Equipo', origin='team',
            text='Esta información impide el reinicio.', archived_at=completed_at,
            archived_by=admin_user,
        )

        with patch('content.tasks.run_platform_onboarding') as onboarding_task, patch(
            'content.services.proposal_email_service.ProposalEmailService.send_acceptance_confirmation',
        ) as acceptance_email:
            response = admin_client.post(
                self._url(accepted_proposal), {'force': True}, format='json',
            )

        accepted_proposal.refresh_from_db()
        idea.refresh_from_db()
        assert response.status_code == 409
        assert (
            accepted_proposal.deliverable_id,
            accepted_proposal.platform_onboarding_completed_at,
            Project.objects.filter(pk=project.pk).exists(),
            idea.project_id,
        ) == (deliverable.pk, completed_at, True, project.pk)
        onboarding_task.assert_not_called()
        acceptance_email.assert_not_called()

    def test_launch_to_platform_creates_changelog(self, admin_client, accepted_proposal):
        with patch('content.tasks.run_platform_onboarding'):
            admin_client.post(self._url(accepted_proposal), format='json')

        assert ProposalChangeLog.objects.filter(
            proposal=accepted_proposal,
            change_type='platform_launch',
        ).exists()

    def test_launch_to_platform_requires_admin(self, api_client, accepted_proposal):
        resp = api_client.post(self._url(accepted_proposal), format='json')

        assert resp.status_code == 401


class TestRunPlatformOnboardingTask:
    """Tests for the run_platform_onboarding Huey task logic."""

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
        assert kwargs['send_email'] is True

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
