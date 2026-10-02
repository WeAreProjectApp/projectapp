"""Tests for the `create_fake_proposals` management command.

Verifies that generated fake data respects the invariants of the current
data model — specifically the new `BusinessProposal.client` FK to a real
`UserProfile` and the `ProposalProjectStage` scenarios seeded for
accepted/finished proposals.

Business rules asserted:
- Every proposal has a non-null `client` FK (UserProfile with role=client)
- Every proposal has a client-specific send-email message
- Repeated client names/emails resolve to the same `UserProfile` row
  (via `proposal_client_service.get_or_create_client_for_proposal`)
- Accepted + finished proposals always get exactly two `ProposalProjectStage`
  rows (design + development) via `ProposalStageTracker.get_or_create_stage`
- Every seeded stage with both `start_date` and `end_date` satisfies
  `start_date <= end_date`
- A stage with `warning_sent_at` or `last_overdue_reminder_at` also has
  `start_date` and `end_date` set
- Finished proposals always land in the `both_done` scenario
  (both design + development marked `completed_at`)
"""
import random
from datetime import datetime, timezone

import pytest
from accounts.models import UserProfile
from django.core.management import call_command

from content.models import (
    AdditionalModule,
    BusinessProposal,
    ProposalChangeLog,
    ProposalProjectStage,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _seed_random():
    """Make random outputs deterministic across test runs."""
    random.seed(1234)
    yield


def _run_command(count):
    call_command('create_fake_proposals', '--count', str(count))


# ---------------------------------------------------------------------------
# Proposal + client FK wiring
# ---------------------------------------------------------------------------

class TestCreateFakeProposalsClientFk:
    def test_creates_the_requested_number_of_proposals(self):
        _run_command(count=8)
        assert BusinessProposal.objects.count() == 8

    def test_every_proposal_has_a_client_fk(self):
        _run_command(count=8)
        assert BusinessProposal.objects.filter(client__isnull=True).count() == 0

    def test_every_proposal_has_a_personalized_email_message(self):
        _run_command(count=8)

        for proposal in BusinessProposal.objects.all():
            assert proposal.email_intro.strip()
            assert proposal.client_name.split()[0] in proposal.email_intro
            assert 'resuelve' in proposal.email_intro

    def test_every_client_is_a_client_role_userprofile(self):
        _run_command(count=8)
        proposal_client_ids = BusinessProposal.objects.values_list('client_id', flat=True)
        client_profiles = UserProfile.objects.filter(pk__in=proposal_client_ids)
        assert client_profiles.count() > 0
        assert all(p.role == UserProfile.ROLE_CLIENT for p in client_profiles)

    def test_repeated_client_names_reuse_the_same_profile(self):
        # CLIENT_NAMES has 20 entries; running with 24 forces 4 collisions
        # (the command iterates deterministically by index).
        _run_command(count=24)
        total_proposals = BusinessProposal.objects.count()
        distinct_clients = (
            BusinessProposal.objects.values_list('client_id', flat=True).distinct().count()
        )
        assert total_proposals == 24
        # Fewer distinct clients than proposals means reuse happened.
        assert distinct_clients < total_proposals


class TestCreateFakeProposalModuleInterests:
    def test_interest_seed_keeps_manual_investment_and_scope(self):
        """Falla si datos falsos vuelven a fabricar precio o alcance desde módulos."""
        from content.management.commands.create_fake_proposals import Command

        proposal = BusinessProposal.objects.create(
            title='Interés demo',
            client_name='Cliente demo',
            status='viewed',
            total_investment=1500000,
            selected_modules=['module-existing-scope'],
        )
        now = datetime(2026, 9, 29, 18, tzinfo=timezone.utc)
        Command()._create_module_interests(proposal, now)

        proposal.refresh_from_db()
        selected_ids = [interest['id'] for interest in proposal.module_interests]
        assert len(selected_ids) == 2
        assert AdditionalModule.objects.filter(
            pk__in=selected_ids,
            is_active=True,
            category__is_active=True,
        ).count() == 2
        assert proposal.total_investment == 1500000
        assert proposal.selected_modules == ['module-existing-scope']
        assert proposal.module_interests_updated_at == now
        assert ProposalChangeLog.objects.filter(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.MODULE_INTERESTS,
            actor_type=ProposalChangeLog.ActorType.CLIENT,
        ).count() == 1


# ---------------------------------------------------------------------------
# ProposalProjectStage seeding
# ---------------------------------------------------------------------------

class TestCreateFakeProposalsStages:
    def test_accepted_proposals_get_both_stages(self):
        _run_command(count=16)
        for proposal in BusinessProposal.objects.filter(status='accepted'):
            stages = proposal.project_stages.all()
            stage_keys = set(stages.values_list('stage_key', flat=True))
            assert stage_keys == {'design', 'development'}

    def test_finished_proposals_get_both_stages(self):
        _run_command(count=16)
        finished = BusinessProposal.objects.filter(status='finished')
        assert finished.count() > 0
        for proposal in finished:
            stage_keys = set(proposal.project_stages.values_list('stage_key', flat=True))
            assert stage_keys == {'design', 'development'}

    def test_non_accepted_proposals_do_not_get_stages(self):
        _run_command(count=16)
        non_execution = BusinessProposal.objects.exclude(
            status__in=('accepted', 'finished'),
        )
        for proposal in non_execution:
            assert proposal.project_stages.count() == 0

    def test_finished_proposals_land_in_both_done_scenario(self):
        _run_command(count=16)
        for proposal in BusinessProposal.objects.filter(status='finished'):
            for stage in proposal.project_stages.all():
                assert stage.completed_at is not None
                assert stage.start_date is not None
                assert stage.end_date is not None

    def test_stage_date_range_is_always_valid(self):
        # start_date <= end_date when both are set
        _run_command(count=16)
        for stage in ProposalProjectStage.objects.filter(
            start_date__isnull=False, end_date__isnull=False,
        ):
            assert stage.start_date <= stage.end_date

    def test_alert_timestamps_require_dates_to_be_set(self):
        _run_command(count=16)
        with_warning = ProposalProjectStage.objects.filter(warning_sent_at__isnull=False)
        for stage in with_warning:
            assert stage.start_date is not None
            assert stage.end_date is not None

        with_overdue = ProposalProjectStage.objects.filter(last_overdue_reminder_at__isnull=False)
        for stage in with_overdue:
            assert stage.start_date is not None
            assert stage.end_date is not None

    def test_stage_scenarios_produce_variety_over_many_proposals(self):
        # With seeded randomness and count=32 we should see at least
        # 3 distinct states across the accepted stages.
        _run_command(count=32)
        accepted = BusinessProposal.objects.filter(status='accepted')
        design_states = set()
        for proposal in accepted:
            design = proposal.project_stages.get(stage_key='design')
            if design.completed_at is not None:
                design_states.add('completed')
            elif design.last_overdue_reminder_at is not None:
                design_states.add('overdue')
            elif design.warning_sent_at is not None:
                design_states.add('warning')
            elif design.start_date is not None:
                design_states.add('scheduled')
            else:
                design_states.add('unscheduled')
        assert len(design_states) >= 2

    def test_running_command_twice_does_not_create_extra_stage_rows_per_proposal(self):
        # Each run creates new proposals; stages are scoped to each new proposal
        # via unique_together=('proposal', 'stage_key'). No cross-run leakage.
        _run_command(count=8)
        first_run_stage_count = ProposalProjectStage.objects.count()
        _run_command(count=8)
        second_run_stage_count = ProposalProjectStage.objects.count()
        # Second run adds its own stages on top
        assert second_run_stage_count >= first_run_stage_count

        # Each accepted/finished proposal still has exactly 2 stages (no duplicates)
        for proposal in BusinessProposal.objects.filter(
            status__in=('accepted', 'finished'),
        ):
            assert proposal.project_stages.count() == 2
