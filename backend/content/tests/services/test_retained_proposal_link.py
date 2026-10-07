"""A proposal whose deliverable outlived a forced project deletion stays explainable.

Its deliverable keeps no project but a retention context: every reader must name
the deleted project instead of crashing, and every writer that cannot handle it
must say so instead of sending the operator back to the approval review.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Deliverable, Project, ProjectPhase, UserProfile
from content.models import (
    BusinessProposal, McpActionIntent, McpConnector, ProjectRetentionContext, ProposalProjectReassignment,
)
from content.serializers.proposal import ProposalDetailSerializer
from content.services.proposal_approval_service import ApprovalConflict, review_proposal
from content.services.proposal_project_reassignment import preview_reassignment, reassign_proposal

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def retained_proposal(proposal, admin_user):
    client_user = User.objects.create_user(username='littigio-client', email='littigio@example.test')
    profile = UserProfile.objects.create(user=client_user, role=UserProfile.ROLE_CLIENT)
    target = Project.objects.create(name='Littigio', client=client_user)
    context = ProjectRetentionContext.objects.create(
        client=client_user, original_project_id=9015, project_name='Plataforma educativa fase 1',
        retained_records={}, category_counts={}, created_by=admin_user,
    )
    deliverable = Deliverable.objects.create(
        project=None, retention_context=context, title='Paquete aprobado',
        uploaded_by=admin_user, category=Deliverable.CATEGORY_DOCUMENTS,
    )
    phase = ProjectPhase.objects.create(project=None, business_proposal=proposal, order=1, retention_context=context)
    # Direct update: the state is the input of these tests, not a transition.
    BusinessProposal.objects.filter(pk=proposal.pk).update(
        client=profile, status=BusinessProposal.Status.ACCEPTED, deliverable=deliverable,
    )
    proposal.refresh_from_db()
    context.retained_records = {'accounts.deliverable': [str(deliverable.pk)], 'accounts.projectphase': [str(phase.pk)]}
    context.category_counts = {'accounts.deliverable': 1, 'accounts.projectphase': 1}
    context.save(update_fields=['retained_records', 'category_counts'])
    return {'proposal': proposal, 'profile': profile, 'target': target, 'context': context,
            'deliverable': deliverable, 'phase': phase}


def test_linked_project_names_the_deleted_project(retained_proposal):
    """Fails if a retained deliverable crashes the property or reads as "no project"."""
    proposal = BusinessProposal.objects.get(pk=retained_proposal['proposal'].pk)

    assert proposal.linked_project == {
        'id': None, 'name': 'Plataforma educativa fase 1', 'retained': True,
        'retention_context_id': retained_proposal['context'].pk, 'original_project_id': 9015,
        'client_profile_id': retained_proposal['profile'].pk,
    }


def test_detail_serializer_keeps_the_retained_link(retained_proposal):
    """Fails if the panel receives no linked_project and reopens the proposal client."""
    proposal = BusinessProposal.objects.get(pk=retained_proposal['proposal'].pk)
    data = ProposalDetailSerializer(proposal, context={'is_admin': True}).data

    assert data['linked_project']['retained'] is True
    assert data['linked_project']['name'] == 'Plataforma educativa fase 1'


def test_approval_preview_answers_and_requires_reassignment(admin_client, retained_proposal):
    """Fails if get_proposal_approval still fails with a 500 for a retained deliverable."""
    response = admin_client.get(reverse('proposal-approval', kwargs={'proposal_id': retained_proposal['proposal'].pk}))

    assert response.status_code == 200
    assert response.data['project_reassignment_required'] is True
    assert response.data['linked_project']['name'] == 'Plataforma educativa fase 1'


def test_review_retry_conflicts_instead_of_crashing(retained_proposal, admin_user):
    """Fails if the review tries to bind (or sync) a deliverable that has no project."""
    with pytest.raises(ApprovalConflict) as raised:
        review_proposal(retained_proposal['proposal'].pk, {'action': 'retry', 'request_id': 'retained-retry'}, actor=admin_user)

    assert str(raised.value.detail['code']) == 'retained_project'
    assert 'Plataforma educativa fase 1' in str(raised.value.detail['detail'])
    assert Project.objects.count() == 1


def test_review_defer_still_answers_with_the_retained_link(retained_proposal, admin_user):
    """Fails if postponing the review is blocked or crashes for a retained deliverable."""
    result = review_proposal(retained_proposal['proposal'].pk, {'action': 'defer'}, actor=admin_user)

    assert result['action'] == 'defer'
    assert result['project_reassignment_required'] is True
    assert Project.objects.count() == 1


def test_reassignment_preview_starts_from_the_deleted_project(retained_proposal):
    """Fails if the preview sends the operator back to the approval review (the circle)."""
    impact = preview_reassignment(retained_proposal['proposal'].pk, retained_proposal['target'].pk)

    assert impact['blockers'] == []
    assert impact['source_project'] == {'id': None, 'name': 'Plataforma educativa fase 1', 'retained': True}


def test_reassignment_without_any_source_stops_before_moving_anything(retained_proposal, admin_user):
    """Fails if a proposal with no deliverable at all reaches the move (or locks rows of other clients)."""
    orphan = BusinessProposal.objects.create(
        title='Sin vínculo', client=retained_proposal['profile'], client_name='Littigio',
        client_email='littigio@example.test', status=BusinessProposal.Status.ACCEPTED,
    )
    impact = preview_reassignment(orphan.pk, retained_proposal['target'].pk)

    with pytest.raises(ApprovalConflict) as raised:
        reassign_proposal(orphan.pk, {
            'target_project_id': retained_proposal['target'].pk, 'reason': 'Unificar Littigio',
            'expected_impact_hash': impact['impact_hash'], 'request_id': 'orphan-move',
        }, actor=admin_user)

    assert [blocker['code'] for blocker in impact['blockers']] == ['no_source_project']
    assert str(raised.value.detail['code']) == 'reassignment_blocked'
    assert not ProposalProjectReassignment.objects.exists()


def test_commercial_phase_names_the_deleted_project(admin_client, retained_proposal):
    """Fails if adding the phase answers with the approval-review loop message."""
    response = admin_client.post(
        reverse('project-commercial-phases', kwargs={'project_id': retained_proposal['target'].pk}),
        {'proposal_id': retained_proposal['proposal'].pk}, format='json',
    )

    assert response.status_code == 400
    assert 'Plataforma educativa fase 1' in str(response.data['proposal_id'])
    assert not ProjectPhase.objects.filter(project=retained_proposal['target']).exists()


@pytest.fixture
def proposals_token():
    connector, _ = McpConnector.objects.get_or_create(slug='proposals')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


def _rpc(api_client, token, name, arguments):
    response = api_client.post(f'/api/mcp/proposals/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, format='json')
    return json.loads(response.data['result']['content'][0]['text'])


def test_mcp_approval_preview_no_longer_fails(api_client, proposals_token, retained_proposal):
    """Fails if get_proposal_approval answers INTERNAL_ERROR for a retained deliverable."""
    result = _rpc(api_client, proposals_token, 'get_proposal_approval', {'proposal_id': retained_proposal['proposal'].pk})

    assert result['project_reassignment_required'] is True
    assert result['linked_project']['retained'] is True


def test_mcp_review_rejects_before_a_confirmation_exists(api_client, proposals_token, retained_proposal):
    """Fails if the MCP review offers a confirmation it can never apply."""
    result = _rpc(api_client, proposals_token, 'review_proposal_approval', {
        'proposal_id': retained_proposal['proposal'].pk, 'action': 'retry', 'request_id': 'retained-mcp-retry',
    })

    assert result['ok'] is False
    assert result['error']['code'] == 'RETAINED_PROJECT'
    assert not McpActionIntent.objects.exists()
