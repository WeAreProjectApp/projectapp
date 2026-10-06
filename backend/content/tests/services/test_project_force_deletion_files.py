"""Project force-deletion service protects owned records, shared data, and files."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.db import transaction

from accounts.models import (
    Deliverable,
    DeliverableFile,
    DeliveryEvidenceEmail,
    DeliveryEvidenceEmailFile,
    Project,
    ProjectPhase,
)
from accounts.tests.delivery_helpers import build_delivery_context
from content.models import (
    AccountingChangeLog,
    BusinessProposal,
    CommunicationMessage,
    Document,
    DocumentFolder,
    DocumentType,
    EntityHistory,
    ExpenseRecord,
    IncomeRecord,
    PocketMovement,
    ProjectBrandAsset,
    ProposalDocument,
    ProjectRetentionContext,
)
from content.services.project_force_deletion import (
    ProjectForceDeleteError,
    force_delete_project,
    forced_deletion_preview,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def owned_project(make_client_profile):
    profile = make_client_profile(company='Owned project client')
    return Project.objects.create(name='Owned project', client=profile.user)


def confirmed_preview(project, actor):
    initial = forced_deletion_preview(project, actor=actor)
    delete_keys = [dependency['key'] for dependency in initial['dependencies']]
    return forced_deletion_preview(project, actor=actor, delete_keys=delete_keys)


def force_delete(project, actor):
    preview = confirmed_preview(project, actor)
    force_delete_project(
        project.pk,
        actor=actor,
        confirmation='DELETE',
        impact_token=preview['impact_token'],
        delete_keys=preview['delete_keys'],
    )


def make_income(project, movement, *, concept='Project income'):
    return IncomeRecord.objects.create(
        concept=concept,
        kind=IncomeRecord.Kind.LIQUID,
        project=project,
        client=project.client.profile,
        destination=IncomeRecord.Destination.POCKET,
        period_date=date(2026, 10, 4),
        total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
        pocket_movement=movement,
    )


def make_movement(concept='Project pocket movement'):
    return PocketMovement.objects.create(
        concept=concept,
        movement_date=date(2026, 10, 4),
        direction=PocketMovement.Direction.IN,
        amount=Decimal('100.00'),
    )


def test_force_delete_removes_owned_delivery_graph(superuser, owned_project):
    """Fails if a protected project child prevents deletion of its owned delivery graph."""
    proposal = BusinessProposal.objects.create(
        title='Commercial proposal', client_name='Owned project client',
    )
    phase = ProjectPhase.objects.create(
        project=owned_project, business_proposal=proposal, order=1,
    )
    deliverable = Deliverable.objects.create(
        project=owned_project,
        title='Owned deliverable',
        uploaded_by=superuser,
    )
    document_type, _ = DocumentType.objects.get_or_create(
        code='force-delete-owned', defaults={'name': 'Force delete owned'},
    )
    document = Document.objects.create(
        project=owned_project,
        document_type=document_type,
        title='Owned document',
    )
    folder = DocumentFolder.objects.create(name='Owned folder', project=owned_project)
    message = CommunicationMessage.objects.create(
        thread=owned_project.communication_root_thread,
        content='Owned communication',
        channel='whatsapp',
        direction='incoming',
        status='received',
        occurred_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
    )

    force_delete(owned_project, superuser)

    assert not ProjectPhase.objects.filter(pk=phase.pk).exists()
    assert not Deliverable.objects.filter(pk=deliverable.pk).exists()
    assert not Document.objects.filter(pk=document.pk).exists()
    assert not DocumentFolder.objects.filter(pk=folder.pk).exists()
    assert not CommunicationMessage.objects.filter(pk=message.pk).exists()


def test_force_delete_retains_proposal_after_removing_deliverable(superuser, owned_project):
    """Fails if a project purge destroys its independent commercial proposal."""
    deliverable = Deliverable.objects.create(
        project=owned_project,
        title='Proposal deliverable',
        uploaded_by=superuser,
    )
    proposal = BusinessProposal.objects.create(
        title='Retained commercial proposal',
        client_name='Owned project client',
        deliverable=deliverable,
    )

    force_delete(owned_project, superuser)

    proposal.refresh_from_db()
    assert proposal.deliverable_id is None
    assert proposal.title == 'Retained commercial proposal'


def test_force_delete_records_durable_project_audit(superuser, owned_project):
    """Fails if forced deletion removes the project without a surviving audit trail."""
    project_id = owned_project.pk

    force_delete(owned_project, superuser)

    audit = AccountingChangeLog.objects.get(
        entity_type=AccountingChangeLog.EntityType.PROJECT,
        object_id=project_id,
        action=AccountingChangeLog.Action.DELETED,
    )
    history = EntityHistory.objects.get(entity_type='project', object_id=project_id)
    assert audit.changes[-1]['field'] == 'forced_deletion'
    assert history.entries.order_by('-number').first().action == 'deleted'


def test_force_delete_removes_exclusive_accounting_event(superuser, owned_project):
    """Fails if force deletion leaves an income event, its deduction, or its pocket movement behind."""
    movement = make_movement()
    income = make_income(owned_project, movement)
    deduction = ExpenseRecord.objects.create(
        concept='Income deduction',
        period_date=date(2026, 10, 4),
        total_amount=Decimal('10.00'),
        gustavo_amount=Decimal('5.00'),
        carlos_amount=Decimal('5.00'),
        deduction_type=ExpenseRecord.DeductionType.GATEWAY_FEE,
        source_income=income,
    )
    income_id, movement_id, deduction_id = income.pk, movement.pk, deduction.pk

    force_delete(owned_project, superuser)

    assert not IncomeRecord.objects.filter(pk=income_id).exists()
    assert not PocketMovement.objects.filter(pk=movement_id).exists()
    assert not ExpenseRecord.objects.filter(pk=deduction_id).exists()
    assert AccountingChangeLog.objects.filter(
        entity_type=AccountingChangeLog.EntityType.INCOME,
        object_id=income_id,
        action=AccountingChangeLog.Action.DELETED,
    ).exists()
    assert AccountingChangeLog.objects.filter(
        entity_type=AccountingChangeLog.EntityType.POCKET,
        object_id=movement_id,
        action=AccountingChangeLog.Action.DELETED,
    ).exists()
    assert AccountingChangeLog.objects.filter(
        entity_type=AccountingChangeLog.EntityType.EXPENSE,
        object_id=deduction_id,
        action=AccountingChangeLog.Action.DELETED,
    ).exists()


def test_force_preview_blocks_shared_pocket_event(superuser, make_client_profile):
    """Fails if deleting one project partially reverses a pocket movement shared with another project."""
    target_profile = make_client_profile(company='Target project client')
    other_profile = make_client_profile(company='Other project client')
    target = Project.objects.create(name='Target project', client=target_profile.user)
    other = Project.objects.create(name='Other project', client=other_profile.user)
    movement = make_movement('Shared pocket movement')
    target_income = make_income(target, movement, concept='Target share')
    other_income = make_income(other, movement, concept='Other share')
    preview = confirmed_preview(target, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            target.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    assert preview['can_delete'] is False
    assert error.value.code == 'project_force_delete_blocked'
    assert Project.objects.filter(pk=target.pk).exists()
    assert Project.objects.filter(pk=other.pk).exists()
    assert IncomeRecord.objects.filter(pk=target_income.pk).exists()
    assert IncomeRecord.objects.filter(pk=other_income.pk).exists()
    assert PocketMovement.objects.filter(pk=movement.pk).exists()


def test_force_delete_preserves_immutable_evidence_file(superuser):
    """Fails if force deletion erases legal email evidence or its private attachment bytes."""
    context = build_delivery_context()
    email = DeliveryEvidenceEmail.objects.create(
        project=context.project,
        stage=context.stage,
        prepared_by=context.admin,
        client=context.client,
        to_recipients=['client@example.test'],
        from_email='team@example.test',
        subject='Closure evidence',
        html_body='<p>Closure evidence</p>',
        text_body='Closure evidence',
        captured_version=1,
        request_id='force-delete-evidence',
        manifest_sha256='a' * 64,
    )
    attachment = DeliveryEvidenceEmailFile.objects.create(
        email=email,
        file=ContentFile(b'private closure evidence', name='closure-evidence.pdf'),
        filename='closure-evidence.pdf',
        size_bytes=24,
        sha256='b' * 64,
        position=1,
    )
    preview = confirmed_preview(context.project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            context.project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    attachment.file.open('rb')
    assert error.value.code == 'project_force_delete_blocked'
    assert DeliveryEvidenceEmail.objects.filter(pk=email.pk).exists()
    assert attachment.file.read() == b'private closure evidence'


def test_force_delete_defers_exclusive_file_cleanup_until_commit(
    superuser, owned_project, django_capture_on_commit_callbacks,
):
    """Fails if force deletion removes exclusive brand bytes before the transaction commits."""
    asset = ProjectBrandAsset.objects.create(
        project=owned_project,
        title='Exclusive brand asset',
        category=ProjectBrandAsset.Category.MANUAL,
        file=ContentFile(b'exclusive brand asset', name='exclusive-brand.pdf'),
        filename='exclusive-brand.pdf',
        size=21,
    )
    storage, name = asset.file.storage, asset.file.name

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        force_delete(owned_project, superuser)

    assert storage.exists(name)
    callbacks[0]()
    assert not storage.exists(name)


def test_force_delete_rollback_keeps_exclusive_file(superuser, owned_project):
    """Fails if a rolled-back forced deletion removes an exclusive brand file."""
    asset = ProjectBrandAsset.objects.create(
        project=owned_project,
        title='Rollback brand asset',
        category=ProjectBrandAsset.Category.MANUAL,
        file=ContentFile(b'rollback brand asset', name='rollback-brand.pdf'),
        filename='rollback-brand.pdf',
        size=19,
    )
    storage, name = asset.file.storage, asset.file.name

    with pytest.raises(RuntimeError, match='rollback'):
        with transaction.atomic():
            force_delete(owned_project, superuser)
            raise RuntimeError('rollback')

    assert ProjectBrandAsset.objects.filter(pk=asset.pk).exists()
    assert storage.exists(name)


def test_force_delete_keeps_file_reused_by_proposal(
    superuser, owned_project, django_capture_on_commit_callbacks,
):
    """Fails if cleanup removes a file name still retained by a commercial proposal."""
    asset = ProjectBrandAsset.objects.create(
        project=owned_project,
        title='Shared brand asset',
        category=ProjectBrandAsset.Category.MANUAL,
        file=ContentFile(b'shared brand asset', name='shared-brand.pdf'),
        filename='shared-brand.pdf',
        size=18,
    )
    proposal = BusinessProposal.objects.create(
        title='Proposal retaining brand asset',
        client_name='Owned project client',
    )
    ProposalDocument.objects.create(
        proposal=proposal,
        title='Retained proposal file',
        file=asset.file.name,
    )
    storage, name = asset.file.storage, asset.file.name

    with django_capture_on_commit_callbacks(execute=True):
        force_delete(owned_project, superuser)

    assert storage.exists(name)


def test_empty_selection_retains_phase_under_client_context(superuser, owned_project):
    """Fails if an empty selection deletes a phase instead of retaining its client-owned history."""
    proposal = BusinessProposal.objects.create(
        title='Retained phase proposal', client_name='Owned project client',
    )
    phase = ProjectPhase.objects.create(
        project=owned_project, business_proposal=proposal, order=1,
    )
    preview = forced_deletion_preview(owned_project, actor=superuser, delete_keys=[])

    force_delete_project(
        owned_project.pk,
        actor=superuser,
        confirmation='DELETE',
        impact_token=preview['impact_token'],
        delete_keys=[],
    )

    phase.refresh_from_db()
    context = ProjectRetentionContext.objects.get(pk=phase.retention_context_id)
    assert not Project.objects.filter(pk=owned_project.pk).exists()
    assert phase.project_id is None
    assert context.client_id == owned_project.client_id
    assert context.original_project_id == owned_project.pk
    assert context.retained_records['accounts.projectphase'] == [str(phase.pk)]


def test_deliverable_selection_requires_attached_file_selection(superuser, owned_project):
    """Fails if deleting a deliverable silently deletes its unselected attachment."""
    deliverable = Deliverable.objects.create(
        project=owned_project,
        title='Deliverable with attachment',
        uploaded_by=superuser,
    )
    attachment = DeliverableFile.objects.create(
        deliverable=deliverable,
        file=ContentFile(b'attachment bytes', name='selection-attachment.pdf'),
        title='Contract attachment',
        uploaded_by=superuser,
    )
    blocked_preview = forced_deletion_preview(
        owned_project, actor=superuser, delete_keys=['deliverables'],
    )

    assert blocked_preview['can_delete'] is False
    assert blocked_preview['dependencies'][0]['key'] == 'deliverables'
    assert blocked_preview['dependencies'][0]['requires'] == ['accounts.deliverablefile']
    assert 'Archivos adjuntos de entregables' in blocked_preview['blockers'][0]['message']

    selected_keys = ['deliverables', 'accounts.deliverablefile']
    reviewed_preview = forced_deletion_preview(
        owned_project, actor=superuser, delete_keys=selected_keys,
    )
    force_delete_project(
        owned_project.pk,
        actor=superuser,
        confirmation='DELETE',
        impact_token=reviewed_preview['impact_token'],
        delete_keys=selected_keys,
    )

    assert reviewed_preview['can_delete'] is True
    assert not Deliverable.objects.filter(pk=deliverable.pk).exists()
    assert not DeliverableFile.objects.filter(pk=attachment.pk).exists()
