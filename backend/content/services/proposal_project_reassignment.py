"""Audited project corrections without replaying acceptance or issuing documents."""
import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from accounts.models import Deliverable, Project, ProjectPhase
from content.models import BusinessProposal, Document, ProposalApprovalFile, ProposalChangeLog, ProposalProjectReassignment
from content.serializers.proposal_project_reassignment import ProposalProjectReassignmentSerializer
from content.services.proposal_approval_service import ApprovalConflict, load_proposal


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _summary(proposal):
    return {'id': proposal.pk, 'linked_project': proposal.linked_project,
            'project_review_required': proposal.project_review_required,
            'status': proposal.status}


def preview_reassignment(proposal_id, target_project_id):
    proposal = get_object_or_404(BusinessProposal.objects.select_related('client', 'deliverable__project'), pk=proposal_id)
    target = get_object_or_404(Project, pk=target_project_id)
    source = proposal.deliverable.project if proposal.deliverable_id else None
    blockers = []

    def block(code, message):
        blockers.append({'code': code, 'message': message})

    if source is None:
        block('no_source_project', 'Vincula primero la propuesta mediante su revisión de aprobación.')
    if source and source.pk == target.pk:
        block('same_project', 'La propuesta ya pertenece al proyecto de destino.')
    if not proposal.client_id or target.client_id != proposal.client.user_id or (source and source.client_id != target.client_id):
        block('different_client', 'El origen y el destino deben pertenecer al mismo cliente de la propuesta.')
    from accounts.services.project_catalog_service import project_catalog_bucket
    if project_catalog_bucket(target) == 'archived':
        block('archived_target', 'Selecciona un proyecto de destino activo.')
    if proposal.client_id and proposal.client.archived_at:
        block('archived_client', 'El cliente está archivado.')
    source_id = source.pk if source else None
    phases = list(ProjectPhase.objects.filter(business_proposal=proposal).order_by('pk').values('id', 'project_id', 'order', 'hosting_start_date', 'hosting_activated_at'))
    if any(item['project_id'] != source_id for item in phases):
        block('inconsistent_phases', 'Hay fases de esta propuesta vinculadas a otros proyectos. Revisa esa relación primero.')
    if source:
        owners = set(source.phases.values_list('business_proposal_id', flat=True)) | set(BusinessProposal.objects.filter(deliverable__project=source).values_list('pk', flat=True))
        unknown = Deliverable.objects.filter(project=source, source_proposal__isnull=True).exclude(source_epic_key='')
        if unknown.exists():
            block('unowned_resources', 'Hay recursos técnicos sin propuesta de origen; revisa su procedencia antes de trasladarlos.')
    resources = Deliverable.objects.filter(project_id=source_id).filter(Q(pk=proposal.deliverable_id) | Q(source_proposal=proposal))
    deliverables = list(resources.order_by('pk').values('id', 'project_id', 'source_proposal_id', 'source_epic_key', 'title', 'description', 'file', 'current_version', 'is_archived', 'updated_at'))
    if proposal.deliverable_id and not any(row['id'] == proposal.deliverable_id for row in deliverables):
        block('missing_deliverable', 'El entregable de la propuesta ya no pertenece al origen.')
    keys = [row['source_epic_key'] for row in deliverables if row['source_epic_key']]
    if Deliverable.objects.filter(project=target, source_proposal=proposal, source_epic_key__in=keys).exists():
        block('duplicate_resources', 'El destino ya contiene recursos de esta propuesta; no se sobrescribirán.')
    files = list(ProposalApprovalFile.objects.filter(proposal=proposal).order_by('pk').values('id', 'project_id', 'deliverable_id', 'sha256', 'size', 'file'))
    if any(row['project_id'] != source_id or row['deliverable_id'] != proposal.deliverable_id for row in files):
        block('inconsistent_packet', 'El paquete confirmado tiene relaciones diferentes del proyecto de origen.')
    documents = list(Document.objects.filter(source_proposal=proposal, project_id=source_id).order_by('pk').values('id', 'project_id', 'folder_id', 'updated_at', 'generated_file', 'document_type__code'))
    if any(row['document_type__code'] == 'collection_account' for row in documents):
        block('financial_document', 'Una cuenta de cobro requiere el flujo de reasignación contable, que conserva su evidencia financiera.')
    # A commercial phase inside an authored delivery graph cannot be moved
    # independently of its contract and signed project-level evidence.
    if ProjectPhase.objects.filter(pk__in=[row['id'] for row in phases], delivery_phases__isnull=False).exists():
        block('delivery_graph', 'La fase tiene un cronograma de entrega contractual. Conserva su proyecto hasta revisar ese grafo completo.')
    if any(row['hosting_activated_at'] for row in phases):
        block('active_hosting', 'La fase ya activó hosting. Revisa su vínculo financiero antes de trasladarla.')
    from accounts.models import ProjectContract
    if ProjectContract.objects.filter(project_id=source_id, proposal_document__proposal=proposal).exists():
        block('delivery_contract', 'Hay contratos registrados en Entrega para esta propuesta. Revisa su traslado contractual antes de reasignarla.')
    metadata = {'name': source.name, 'description': source.description, 'payment_milestones': source.payment_milestones, 'hosting_tiers': source.hosting_tiers} if source else {}
    from accounts.views import _extract_proposal_financial_data
    payments, hosting = _extract_proposal_financial_data(proposal)
    clear_mirrors = bool(source and owners == {proposal.pk} and source.payment_milestones == payments and source.hosting_tiers == hosting)
    public = {
        'proposal_id': proposal.pk,
        'source_project': {'id': source_id, 'name': source.name if source else ''},
        'target_project': {'id': target.pk, 'name': target.name},
        'deliverable_ids': [row['id'] for row in deliverables],
        'phase_ids': [row['id'] for row in phases],
        'creates_phase': not phases and source is not None,
        'approval_file_ids': [row['id'] for row in files],
        'document_ids': [row['id'] for row in documents],
        'source_metadata': metadata,
        'clear_generated_commercial_mirrors': clear_mirrors,
        'blockers': blockers,
    }
    public['impact_hash'] = _digest({'impact': public, 'proposal': [proposal.updated_at, proposal.client_id, proposal.deliverable_id, proposal.platform_approval_manifest], 'target': [target.updated_at, target.client_id, target.current_state_id], 'phases': phases, 'deliverables': deliverables, 'files': files, 'documents': documents})
    return public


@transaction.atomic
def reassign_proposal(proposal_id, payload, *, actor):
    if not actor.is_active or not actor.is_staff:
        raise PermissionDenied('La reasignación requiere permisos administrativos.')
    serializer = ProposalProjectReassignmentSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    fingerprint = _digest({'proposal_id': proposal_id, **data})
    original = load_proposal(proposal_id)
    source_id = original.deliverable.project_id if original.deliverable_id else None
    # Same order as financial/approval writers: projects, then proposal and children.
    projects = list(Project.objects.select_for_update().filter(pk__in=[pk for pk in (source_id, data['target_project_id']) if pk]).order_by('pk'))
    proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
    existing = ProposalProjectReassignment.objects.select_for_update().filter(request_id=data['request_id']).first()
    if existing:
        if existing.payload_hash != fingerprint:
            raise ApprovalConflict({'detail': 'Este request_id pertenece a otra operación.', 'code': 'request_conflict'})
        return {**existing.result, 'idempotent': True, 'proposal': _summary(load_proposal(proposal_id))}
    if proposal.deliverable_id != original.deliverable_id:
        raise ApprovalConflict({'detail': 'El vínculo cambió. Revisa nuevamente.', 'code': 'link_changed'})
    if proposal.deliverable_id:
        deliverable = Deliverable.objects.select_for_update().get(pk=proposal.deliverable_id)
        if deliverable.project_id != source_id:
            raise ApprovalConflict({'detail': 'El proyecto de origen cambió. Revisa nuevamente.', 'code': 'link_changed'})
    list(ProjectPhase.objects.select_for_update().filter(business_proposal=proposal).values_list('pk', flat=True))
    list(Deliverable.objects.select_for_update().filter(project_id=source_id).values_list('pk', flat=True))
    list(ProposalApprovalFile.objects.select_for_update().filter(proposal=proposal).values_list('pk', flat=True))
    list(Document.objects.select_for_update().filter(source_proposal=proposal).values_list('pk', flat=True))
    impact = preview_reassignment(proposal_id, data['target_project_id'])
    if impact['impact_hash'] != data['expected_impact_hash']:
        raise ApprovalConflict({'detail': 'La propuesta o sus relaciones cambiaron. Revisa nuevamente el impacto.', 'code': 'stale_impact'})
    if impact['blockers']:
        raise ApprovalConflict({'detail': 'La reasignación tiene dependencias pendientes.', 'blockers': impact['blockers'], 'code': 'reassignment_blocked'})
    target = next(project for project in projects if project.pk == data['target_project_id'])
    source = next(project for project in projects if project.pk == source_id)
    next_order = (target.phases.aggregate(value=Max('order'))['value'] or 0) + 1
    for offset, phase in enumerate(ProjectPhase.objects.filter(pk__in=impact['phase_ids']).order_by('order', 'pk')):
        phase.project = target
        phase.order = next_order + offset
        phase.save(update_fields=['project', 'order'])
    if impact['creates_phase']:
        ProjectPhase.objects.create(project=target, business_proposal=proposal, order=next_order)
    for offset, phase in enumerate(source.phases.order_by('order', 'pk'), start=1):
        if phase.order != offset:
            phase.order = offset
            phase.save(update_fields=['order'])
    Deliverable.objects.filter(pk__in=impact['deliverable_ids']).update(project=target)
    ProposalApprovalFile.objects.filter(pk__in=impact['approval_file_ids']).update(project=target)
    from content.services.project_document_folder_service import require_project_folder, project_category_system_key
    from content.models import DocumentFolder
    if impact['document_ids']:
        root = require_project_folder(target)
        for document in Document.objects.filter(pk__in=impact['document_ids']).select_related('folder', 'document_type'):
            document.project = target
            document.client_user_id = target.client_id
            if document.folder and document.folder.project_id == source.pk:
                kind = document.document_type.code if document.document_type_id else ''
                document.folder = DocumentFolder.objects.filter(parent=root, system_key=project_category_system_key(target.pk, kind)).first() or root
            document.save(update_fields=['project', 'client_user', 'folder'])
    if impact['clear_generated_commercial_mirrors']:
        source.payment_milestones = []
        source.hosting_tiers = []
        source.save(update_fields=['payment_milestones', 'hosting_tiers'])
    proposal.save(update_fields=['updated_at'])
    result = {'proposal': _summary(load_proposal(proposal_id)), 'impact': impact, 'idempotent': False}
    try:
        with transaction.atomic():
            ProposalProjectReassignment.objects.create(proposal=proposal, request_id=data['request_id'], payload_hash=fingerprint, source_project_id=source.pk, target_project_id=target.pk, reason=data['reason'], impact=impact, result=result, actor=actor)
    except IntegrityError as exc:
        if ProposalProjectReassignment.objects.select_for_update().filter(request_id=data['request_id']).exists():
            raise ApprovalConflict({'detail': 'Este request_id pertenece a otra operación.', 'code': 'request_conflict'}) from exc
        raise
    ProposalChangeLog.objects.create(proposal=proposal, change_type='updated', field_name='project', old_value=str(source.pk), new_value=str(target.pk), description=f'Reasignación {source.name} → {target.name}: {data["reason"]}', actor_type='seller')
    return result
