"""Safety and data-preservation tests for proposal project reassignment."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from accounts.models import (
    Deliverable, DeliveryPhase, DeliveryScope, Project, ProjectContract,
    ProjectPhase, UserProfile,
)
from content.models import (
    BusinessProposal,
    Document,
    DocumentType,
    ProposalApprovalFile,
    ProposalChangeLog,
    ProposalDocument,
    ProposalProjectReassignment,
)
from content.services.project_document_folder_service import ensure_project_folder
from content.services.proposal_approval_service import ApprovalConflict
from content.services.proposal_project_reassignment import preview_reassignment, reassign_proposal


User = get_user_model()


def _context():
    actor = User.objects.create_user(username='reassign-admin', password='test', is_staff=True)
    client_user = User.objects.create_user(username='reassign-client', password='test')
    client = UserProfile.objects.create(user=client_user, role=UserProfile.ROLE_CLIENT)
    source = Project.objects.create(name='Source project', client=client_user)
    target = Project.objects.create(name='Target project', client=client_user)
    proposal = BusinessProposal.objects.create(
        title='Phase one', client=client, client_name='Reassignment client',
        client_email='reassignment@example.test', total_investment=Decimal('100.00'),
        status=BusinessProposal.Status.ACCEPTED,
    )
    main = Deliverable.objects.create(
        project=source, title='Approved proposal package', uploaded_by=actor,
        category=Deliverable.CATEGORY_DOCUMENTS,
    )
    proposal.deliverable = main
    proposal.save(update_fields=['deliverable'])
    phase = ProjectPhase.objects.create(project=source, business_proposal=proposal, order=1)
    resource = Deliverable.objects.create(
        project=source, source_proposal=proposal, source_epic_key='scope-1',
        title='Scoped resource', description='Preserved detail', uploaded_by=actor,
        category=Deliverable.CATEGORY_DOCUMENTS,
    )
    approval = ProposalApprovalFile.objects.create(
        proposal=proposal, project=source, deliverable=main, source_key='contract',
        title='Approved contract', document_type='contract', filename='contract.pdf',
        file=ContentFile(b'approval bytes', name='contract.pdf'), sha256='a' * 64,
        size=14, created_by=actor,
    )
    document = Document.objects.create(
        title='Proposal source document', project=source, client_user=client_user,
        source_proposal=proposal,
    )
    document.generated_file.save('proposal-source.pdf', ContentFile(b'document bytes'), save=True)
    ensure_project_folder(target)
    return {
        'actor': actor, 'client': client, 'source': source, 'target': target,
        'proposal': proposal, 'phase': phase, 'main': main, 'resource': resource,
        'approval': approval, 'document': document,
    }


def _payload(impact, request_id='reassign-request-1'):
    return {
        'target_project_id': impact['target_project']['id'],
        'reason': 'Correct the accepted proposal project',
        'expected_impact_hash': impact['impact_hash'],
        'request_id': request_id,
    }


def _add_financial_document(ctx):
    document_type, _ = DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )
    Document.objects.create(
        title='Collection account', project=ctx['source'], client_user=ctx['source'].client,
        source_proposal=ctx['proposal'], document_type=document_type,
    )


def _activate_hosting(ctx):
    ctx['phase'].hosting_activated_at = date(2026, 10, 7)
    ctx['phase'].save(update_fields=['hosting_activated_at'])


def _add_delivery_graph(ctx):
    source = Document.objects.create(title='Project contract', project=ctx['source'])
    contract = ProjectContract.objects.create(
        project=ctx['source'], key='delivery-contract', title='Delivery contract', document=source,
    )
    scope = DeliveryScope.objects.create(contract=contract, key='delivery-scope', title='Delivery scope')
    DeliveryPhase.objects.create(
        scope=scope, commercial_phase=ctx['phase'], key='delivery-phase', title='Delivery phase', order=1,
    )


def _add_delivery_contract(ctx):
    source = ProposalDocument.objects.create(
        proposal=ctx['proposal'], document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        title='Proposal delivery contract', file=ContentFile(b'contract', name='proposal-contract.pdf'),
    )
    ProjectContract.objects.create(
        project=ctx['source'], key='proposal-delivery-contract', title='Proposal delivery contract',
        proposal_document=source,
    )


@pytest.mark.django_db
class TestProposalProjectReassignment:
    def test_reassignment_moves_only_the_proposal_owned_relations(self):
        """Fails if a safe correction leaves a proposal-owned relation in its former project."""
        ctx = _context()
        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)

        result = reassign_proposal(ctx['proposal'].pk, _payload(impact), actor=ctx['actor'])

        ctx['phase'].refresh_from_db()
        ctx['main'].refresh_from_db()
        ctx['resource'].refresh_from_db()
        ctx['approval'].refresh_from_db()
        ctx['document'].refresh_from_db()
        assert result['idempotent'] is False
        assert (
            ctx['phase'].project_id, ctx['main'].project_id, ctx['resource'].project_id,
            ctx['approval'].project_id, ctx['document'].project_id,
        ) == (ctx['target'].pk,) * 5
        assert ctx['document'].client_user_id == ctx['target'].client_id

    def test_reassignment_preserves_approved_file_names_and_bytes(self):
        """Fails if moving approved evidence changes its stored name or immutable bytes."""
        ctx = _context()
        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)
        original_document_name = ctx['document'].generated_file.name

        reassign_proposal(ctx['proposal'].pk, _payload(impact), actor=ctx['actor'])

        ctx['approval'].refresh_from_db()
        ctx['document'].refresh_from_db()
        assert (ctx['approval'].filename, ctx['approval'].file.read()) == ('contract.pdf', b'approval bytes')
        assert (ctx['document'].generated_file.name, ctx['document'].generated_file.read()) == (original_document_name, b'document bytes')

    def test_reassignment_records_one_durable_audit_event(self):
        """Fails if a completed routing correction omits its durable event or change log."""
        ctx = _context()
        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)

        reassign_proposal(ctx['proposal'].pk, _payload(impact), actor=ctx['actor'])

        assert ProposalProjectReassignment.objects.filter(proposal=ctx['proposal']).count() == 1
        assert ProposalChangeLog.objects.filter(
            proposal=ctx['proposal'], field_name='project', old_value=str(ctx['source'].pk),
            new_value=str(ctx['target'].pk),
        ).count() == 1

    def test_preview_blocks_a_target_from_another_client_without_moving_a_phase(self):
        """Fails if a reassignment can cross a client's project boundary."""
        ctx = _context()
        other_user = User.objects.create_user(username='foreign-client', password='test')
        foreign = Project.objects.create(name='Foreign project', client=other_user)

        impact = preview_reassignment(ctx['proposal'].pk, foreign.pk)

        assert [blocker['code'] for blocker in impact['blockers']] == ['different_client']
        ctx['phase'].refresh_from_db()
        assert ctx['phase'].project_id == ctx['source'].pk

    def test_preview_blocks_unowned_technical_resources(self):
        """Fails if a legacy technical resource without a proven owner is transferred with a proposal."""
        ctx = _context()
        Deliverable.objects.create(
            project=ctx['source'], title='Unknown legacy scope', source_epic_key='legacy-key',
            category=Deliverable.CATEGORY_DOCUMENTS, uploaded_by=ctx['actor'],
        )

        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)

        assert 'unowned_resources' in [blocker['code'] for blocker in impact['blockers']]
        ctx['resource'].refresh_from_db()
        assert ctx['resource'].project_id == ctx['source'].pk

    @pytest.mark.parametrize(
        ('prepare', 'expected_code'),
        [
            (_add_financial_document, 'financial_document'),
            (_activate_hosting, 'active_hosting'),
            (_add_delivery_graph, 'delivery_graph'),
            (_add_delivery_contract, 'delivery_contract'),
        ],
        ids=('financial-document', 'active-hosting', 'delivery-graph', 'delivery-contract'),
    )
    def test_preview_blocks_protected_project_evidence(self, prepare, expected_code):
        """Fails if a routing correction can move a protected financial or contractual dependency."""
        ctx = _context()
        prepare(ctx)

        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)

        assert expected_code in [blocker['code'] for blocker in impact['blockers']]

    def test_stale_impact_does_not_move_rows(self):
        """Fails if a reassignment accepts an impact preview after its source documents changed."""
        ctx = _context()
        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)
        Document.objects.create(
            title='Late source document', project=ctx['source'], client_user=ctx['source'].client,
            source_proposal=ctx['proposal'],
        )

        with pytest.raises(ApprovalConflict) as error:
            reassign_proposal(ctx['proposal'].pk, _payload(impact), actor=ctx['actor'])

        ctx['phase'].refresh_from_db()
        assert error.value.detail['code'] == 'stale_impact'
        assert ctx['phase'].project_id == ctx['source'].pk
        assert ProposalProjectReassignment.objects.count() == 0

    def test_reusing_the_same_request_returns_the_original_event_once(self):
        """Fails if retrying an accepted correction creates a second reassignment event."""
        ctx = _context()
        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)
        payload = _payload(impact, request_id='stable-reassignment-request')

        first = reassign_proposal(ctx['proposal'].pk, payload, actor=ctx['actor'])
        retry = reassign_proposal(ctx['proposal'].pk, payload, actor=ctx['actor'])

        assert first['idempotent'] is False
        assert retry['idempotent'] is True
        assert ProposalProjectReassignment.objects.filter(request_id='stable-reassignment-request').count() == 1
        assert ProposalChangeLog.objects.filter(proposal=ctx['proposal'], field_name='project').count() == 1

    def test_reusing_a_request_id_with_another_reason_is_rejected(self):
        """Fails if a request identifier can apply a different administrative correction."""
        ctx = _context()
        impact = preview_reassignment(ctx['proposal'].pk, ctx['target'].pk)
        payload = _payload(impact, request_id='conflicting-reassignment-request')
        reassign_proposal(ctx['proposal'].pk, payload, actor=ctx['actor'])
        conflicting = {**payload, 'reason': 'A different correction'}

        with pytest.raises(ApprovalConflict) as error:
            reassign_proposal(ctx['proposal'].pk, conflicting, actor=ctx['actor'])

        assert error.value.detail['code'] == 'request_conflict'
        assert ProposalProjectReassignment.objects.filter(request_id='conflicting-reassignment-request').count() == 1
