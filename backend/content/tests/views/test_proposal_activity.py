"""Cursor pagination for the proposal activity stream."""
from datetime import datetime, timezone

import pytest
from django.core import signing
from django.urls import reverse

from content.models import BusinessProposal, ProposalChangeLog
from content.views.proposal_activity import CURSOR_SALT


def _activity_logs(proposal, count, timestamp):
    """Create logs sharing a timestamp to exercise the primary-key tie-breaker."""
    ProposalChangeLog.objects.bulk_create([
        ProposalChangeLog(
            proposal=proposal,
            change_type='note',
            description=f'Activity {index}',
            actor_type='seller',
        )
        for index in range(count)
    ])
    ProposalChangeLog.objects.filter(proposal=proposal).update(created_at=timestamp)


def _tamper(cursor):
    return f"{cursor[:-1]}{'a' if cursor[-1] != 'a' else 'b'}"


@pytest.mark.django_db
class TestProposalActivity:
    @pytest.mark.parametrize('page_size', [0, 51], ids=('below-minimum', 'above-maximum'))
    def test_activity_rejects_a_page_size_outside_the_bounded_range(self, admin_client, proposal, page_size):
        """Fails if the activity endpoint accepts an unbounded or empty page size."""
        response = admin_client.get(
            reverse('list-proposal-activity', kwargs={'proposal_id': proposal.pk}),
            {'page_size': page_size},
        )

        assert response.status_code == 400
        assert 'page_size' in response.data

    def test_cursor_returns_the_next_twenty_logs_without_duplicates(self, admin_client, proposal):
        """Fails if a later activity page repeats or skips logs that share a timestamp."""
        _activity_logs(proposal, 25, datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc))

        first = admin_client.get(reverse('list-proposal-activity', kwargs={'proposal_id': proposal.pk}))
        second = admin_client.get(
            reverse('list-proposal-activity', kwargs={'proposal_id': proposal.pk}),
            {'cursor': first.data['next_cursor']},
        )

        expected = list(ProposalChangeLog.objects.filter(proposal=proposal).order_by('-created_at', '-pk').values_list('pk', flat=True))
        first_ids = [row['id'] for row in first.data['results']]
        second_ids = [row['id'] for row in second.data['results']]
        assert first.status_code == 200
        assert len(first_ids) == 20
        assert first_ids == expected[:20]
        assert second.status_code == 200
        assert second_ids == expected[20:]
        assert set(first_ids).isdisjoint(second_ids)
        assert second.data['next_cursor'] is None

    def test_cursor_signed_for_a_different_proposal_is_rejected(self, admin_client, proposal):
        """Fails if an activity cursor can continue the stream of another proposal."""
        other = BusinessProposal.objects.create(
            title='Separate proposal', client_name='Other', client_email='other@example.test',
            total_investment=1, status='draft',
        )
        cursor = signing.dumps({
            'proposal_id': other.pk,
            'id': 1,
            'created_at': '2026-10-07T12:00:00+00:00',
        }, salt=CURSOR_SALT)

        response = admin_client.get(
            reverse('list-proposal-activity', kwargs={'proposal_id': proposal.pk}),
            {'cursor': cursor},
        )

        assert response.status_code == 400
        assert 'cursor' in response.data

    def test_tampered_cursor_is_rejected(self, admin_client, proposal):
        """Fails if an altered signed cursor can select an arbitrary activity page."""
        cursor = signing.dumps({
            'proposal_id': proposal.pk, 'id': 1,
            'created_at': '2026-10-07T12:00:00+00:00',
        }, salt=CURSOR_SALT)
        tampered = _tamper(cursor)

        response = admin_client.get(
            reverse('list-proposal-activity', kwargs={'proposal_id': proposal.pk}),
            {'cursor': tampered},
        )

        assert response.status_code == 400
        assert 'cursor' in response.data
