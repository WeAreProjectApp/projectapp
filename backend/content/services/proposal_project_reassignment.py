"""Audited project corrections without replaying acceptance or issuing documents.

The source is the live project of the proposal's deliverable or, after a
forced deletion, the retention context that kept it: its phases, deliverables
and documents then leave retention for the target, keeping their ids.
"""
import hashlib
import json
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.models import Deliverable, HostingSubscription, Project, ProjectPhase
from content.models import (
    BusinessProposal, Document, ProjectRetentionContext, ProjectRetentionOperation,
    ProposalApprovalFile, ProposalChangeLog, ProposalProjectReassignment,
)
from content.serializers.proposal_project_reassignment import ProposalProjectReassignmentSerializer
from content.services.proposal_approval_service import ApprovalConflict, load_proposal


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _summary(proposal):
    return {'id': proposal.pk, 'linked_project': proposal.linked_project,
            'project_review_required': proposal.project_review_required,
            'status': proposal.status}


def _source(proposal):
    """(live source project, retention context of a deleted one): at most one is set."""
    if not proposal.deliverable_id:
        return None, None
    deliverable = proposal.deliverable
    if deliverable.project_id:
        return deliverable.project, None
    return None, (deliverable.retention_context if deliverable.retention_context_id else None)


def preview_reassignment(proposal_id, target_project_id, *, hosting_start_date=None, accept_hosting_start=False):
    proposal = get_object_or_404(BusinessProposal.objects.select_related('client', 'deliverable__project', 'deliverable__retention_context'), pk=proposal_id)
    target = get_object_or_404(Project, pk=target_project_id)
    source, context = _source(proposal)
    blockers = []

    def block(code, message):
        blockers.append({'code': code, 'message': message})

    if source is None and context is None:
        block('no_source_project', 'Vincula primero la propuesta mediante su revisión de aprobación.')
    if source and source.pk == target.pk:
        block('same_project', 'La propuesta ya pertenece al proyecto de destino.')
    if (not proposal.client_id or target.client_id != proposal.client.user_id
            or (source and source.client_id != target.client_id)
            or (context and context.client_id != target.client_id)):
        block('different_client', 'El origen y el destino deben pertenecer al mismo cliente de la propuesta.')
    from accounts.services.project_catalog_service import project_catalog_bucket
    if project_catalog_bucket(target) == 'archived':
        block('archived_target', 'Selecciona un proyecto de destino activo.')
    if proposal.client_id and proposal.client.archived_at:
        block('archived_client', 'El cliente está archivado.')
    source_id = source.pk if source else None
    # Never "project IS NULL": that would reach retained rows of every client.
    scope = Q(project_id=source_id) if source else Q(retention_context=context) if context else Q(pk__in=[])
    phases = list(ProjectPhase.objects.filter(business_proposal=proposal).order_by('pk').values('id', 'project_id', 'order', 'hosting_start_date', 'hosting_activated_at', 'retention_context_id'))
    if context is not None:
        phase_mismatch = any(item['project_id'] is not None or item['retention_context_id'] != context.pk for item in phases)
    else:
        phase_mismatch = any(item['project_id'] != source_id for item in phases)
    if phase_mismatch:
        block('inconsistent_phases', 'Hay fases de esta propuesta vinculadas a otros proyectos. Revisa esa relación primero.')
    owners, attributed = set(), []
    if source:
        owners = set(source.phases.values_list('business_proposal_id', flat=True)) | set(BusinessProposal.objects.filter(deliverable__project=source).values_list('pk', flat=True))
        unknown = Deliverable.objects.filter(project=source, source_proposal__isnull=True).exclude(source_epic_key='')
        if unknown.exists():
            block('unowned_resources', 'Hay recursos técnicos sin propuesta de origen; revisa su procedencia antes de trasladarlos.')
    elif context:
        owners = set(ProjectPhase.objects.filter(retention_context=context).values_list('business_proposal_id', flat=True)) | set(BusinessProposal.objects.filter(deliverable__retention_context=context).values_list('pk', flat=True))
        unknown = Deliverable.objects.filter(retention_context=context, source_proposal__isnull=True).exclude(source_epic_key='').exclude(pk=proposal.deliverable_id)
        if owners <= {proposal.pk}:
            # The deleted project had this proposal as its only owner: its
            # unattributed technical resources can only be this proposal's.
            attributed = sorted(unknown.values_list('pk', flat=True))
        elif unknown.exists():
            block('unowned_resources', 'Hay recursos técnicos sin propuesta de origen; revisa su procedencia antes de trasladarlos.')
    resources = Deliverable.objects.filter(scope).filter(Q(pk=proposal.deliverable_id) | Q(source_proposal=proposal) | Q(pk__in=attributed))
    deliverables = list(resources.order_by('pk').values('id', 'project_id', 'source_proposal_id', 'source_epic_key', 'title', 'description', 'file', 'current_version', 'is_archived', 'updated_at', 'retention_context_id'))
    if proposal.deliverable_id and not any(row['id'] == proposal.deliverable_id for row in deliverables):
        block('missing_deliverable', 'El entregable de la propuesta ya no pertenece al origen.')
    keys = [row['source_epic_key'] for row in deliverables if row['source_epic_key']]
    if Deliverable.objects.filter(project=target, source_proposal=proposal, source_epic_key__in=keys).exists():
        block('duplicate_resources', 'El destino ya contiene recursos de esta propuesta; no se sobrescribirán.')
    files = list(ProposalApprovalFile.objects.filter(proposal=proposal).order_by('pk').values('id', 'project_id', 'deliverable_id', 'sha256', 'size', 'file'))
    if any(row['project_id'] != source_id or row['deliverable_id'] != proposal.deliverable_id for row in files):
        block('inconsistent_packet', 'El paquete confirmado tiene relaciones diferentes del proyecto de origen.')
    documents = list(Document.objects.filter(scope, source_proposal=proposal).order_by('pk').values('id', 'project_id', 'folder_id', 'updated_at', 'generated_file', 'document_type__code'))
    if any(row['document_type__code'] == 'collection_account' for row in documents):
        block('financial_document', 'Una cuenta de cobro requiere el flujo de reasignación contable, que conserva su evidencia financiera.')
    # A commercial phase inside an authored delivery graph cannot be moved
    # independently of its contract and signed project-level evidence.
    if ProjectPhase.objects.filter(pk__in=[row['id'] for row in phases], delivery_phases__isnull=False).exists():
        block('delivery_graph', 'La fase tiene un cronograma de entrega contractual. Conserva su proyecto hasta revisar ese grafo completo.')
    if any(row['hosting_activated_at'] for row in phases):
        block('active_hosting', 'La fase ya activó hosting. Revisa su vínculo financiero antes de trasladarla.')
    # A due, never-activated phase joining an active subscription is billed
    # (prorated, card charged) by the next daily run: never as a side effect.
    today = timezone.localdate()
    due = [row['id'] for row in phases
           if (hosting_start_date or row['hosting_start_date']) and (hosting_start_date or row['hosting_start_date']) <= today]
    if due and not accept_hosting_start and HostingSubscription.objects.filter(project=target, status=HostingSubscription.STATUS_ACTIVE).exists():
        block('pending_hosting_start', 'El destino tiene hosting activo y la fase ya alcanzó su fecha de inicio: la próxima corrida diaria la cobraría '
                                       '(prorrateado, con la tarjeta guardada). Indica una fecha de inicio futura o acepta ese cobro explícitamente.')
    from accounts.models import ProjectContract
    if ProjectContract.objects.filter(scope, proposal_document__proposal=proposal).exists():
        block('delivery_contract', 'Hay contratos registrados en Entrega para esta propuesta. Revisa su traslado contractual antes de reasignarla.')
    if source:
        metadata = {'name': source.name, 'description': source.description, 'payment_milestones': source.payment_milestones, 'hosting_tiers': source.hosting_tiers}
    elif context:
        metadata = {'name': context.project_name, 'deleted': True, 'retention_context_id': context.pk, 'original_project_id': context.original_project_id}
    else:
        metadata = {}
    from accounts.views import _extract_proposal_financial_data
    payments, hosting = _extract_proposal_financial_data(proposal)
    clear_mirrors = bool(source and owners == {proposal.pk} and source.payment_milestones == payments and source.hosting_tiers == hosting)
    public = {
        'proposal_id': proposal.pk,
        'source_project': {'id': source_id, 'name': source.name if source else (context.project_name if context else ''),
                           'retained': context is not None},
        'target_project': {'id': target.pk, 'name': target.name},
        'deliverable_ids': [row['id'] for row in deliverables],
        'attributed_resource_ids': attributed,
        'phase_ids': [row['id'] for row in phases],
        'creates_phase': not phases and (source is not None or context is not None),
        'approval_file_ids': [row['id'] for row in files],
        'document_ids': [row['id'] for row in documents],
        'source_metadata': metadata,
        'clear_generated_commercial_mirrors': clear_mirrors,
        'hosting_start_date': hosting_start_date.isoformat() if hosting_start_date else None,
        'accept_hosting_start': bool(accept_hosting_start),
        'blockers': blockers,
    }
    public['impact_hash'] = _digest({'impact': public, 'proposal': [proposal.updated_at, proposal.client_id, proposal.deliverable_id, proposal.platform_approval_manifest], 'target': [target.updated_at, target.client_id, target.current_state_id], 'phases': phases, 'deliverables': deliverables, 'files': files, 'documents': documents})
    return public


def _release_retained(context, target, impact, proposal, *, hosting_start_date, next_order):
    """Move the retained graph into the target keeping ids; return (items, rows)."""
    from content.services.entity_history import capture_instance
    from content.services.retained_adoption import ownership
    released = []
    phases = list(ProjectPhase.objects.filter(pk__in=impact['phase_ids'], retention_context=context).order_by('order', 'pk'))
    for offset, phase in enumerate(phases):
        updates = {'project_id': target.pk, 'order': next_order + offset, 'retention_context_id': None}
        if hosting_start_date:
            updates['hosting_start_date'] = hosting_start_date
        released.append((phase, ownership(phase), updates))
    attributed = set(impact['attributed_resource_ids'])
    for deliverable in Deliverable.objects.filter(pk__in=impact['deliverable_ids'], retention_context=context):
        updates = {'project_id': target.pk, 'retention_context_id': None}
        if deliverable.pk in attributed:
            updates['source_proposal_id'] = proposal.pk
        released.append((deliverable, ownership(deliverable), updates))
    for document in Document.objects.filter(pk__in=impact['document_ids'], retention_context=context):
        released.append((document, ownership(document), {'retention_context_id': None}))
    expected = len(impact['phase_ids']) + len(impact['deliverable_ids']) + len(impact['document_ids'])
    if len(released) != expected:
        raise ApprovalConflict({'detail': 'La propuesta o sus relaciones cambiaron. Revisa nuevamente el impacto.', 'code': 'stale_impact'})
    for row, _, updates in released:
        capture_instance(row)
        if type(row)._base_manager.filter(pk=row.pk, retention_context=context).update(**updates) != 1:
            raise ApprovalConflict({'detail': 'La propuesta o sus relaciones cambiaron. Revisa nuevamente el impacto.', 'code': 'stale_impact'})
    return released


@transaction.atomic
def reassign_proposal(proposal_id, payload, *, actor):
    if not actor.is_active or not actor.is_staff:
        raise PermissionDenied('La reasignación requiere permisos administrativos.')
    serializer = ProposalProjectReassignmentSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    options = {'hosting_start_date': data.get('hosting_start_date'), 'accept_hosting_start': data.get('accept_hosting_start', False)}
    fingerprint = _digest({'proposal_id': proposal_id, **data})
    original = load_proposal(proposal_id)
    original_source, original_context = _source(original)
    source_id = original_source.pk if original_source else None
    if original_source is None and original_context is None:
        # No live source and nothing retained: the "project IS NULL" locks below
        # would reach rows of every client; the preview already names the blocker.
        impact = preview_reassignment(proposal_id, data['target_project_id'], **options)
        raise ApprovalConflict({'detail': 'La reasignación tiene dependencias pendientes.', 'blockers': impact['blockers'], 'code': 'reassignment_blocked'})
    # Same order as financial/approval writers: projects, then proposal and children.
    projects = list(Project.objects.select_for_update().filter(pk__in=[pk for pk in (source_id, data['target_project_id']) if pk]).order_by('pk'))
    context = ProjectRetentionContext.objects.select_for_update().get(pk=original_context.pk) if original_context else None
    proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
    existing = ProposalProjectReassignment.objects.select_for_update().filter(request_id=data['request_id']).first()
    if existing:
        if existing.payload_hash != fingerprint:
            raise ApprovalConflict({'detail': 'Este request_id pertenece a otra operación.', 'code': 'request_conflict'})
        return {**existing.result, 'idempotent': True, 'proposal': _summary(load_proposal(proposal_id))}
    if proposal.deliverable_id != original.deliverable_id:
        raise ApprovalConflict({'detail': 'El vínculo cambió. Revisa nuevamente.', 'code': 'link_changed'})
    deliverable = Deliverable.objects.select_for_update().get(pk=proposal.deliverable_id)
    if deliverable.project_id != source_id or (context and deliverable.retention_context_id != context.pk):
        raise ApprovalConflict({'detail': 'El proyecto de origen cambió. Revisa nuevamente.', 'code': 'link_changed'})
    scope = Q(retention_context=context) if context else Q(project_id=source_id)
    list(ProjectPhase.objects.select_for_update().filter(business_proposal=proposal).values_list('pk', flat=True))
    list(Deliverable.objects.select_for_update().filter(scope).values_list('pk', flat=True))
    list(ProposalApprovalFile.objects.select_for_update().filter(proposal=proposal).values_list('pk', flat=True))
    list(Document.objects.select_for_update().filter(source_proposal=proposal).values_list('pk', flat=True))
    impact = preview_reassignment(proposal_id, data['target_project_id'], **options)
    if impact['impact_hash'] != data['expected_impact_hash']:
        raise ApprovalConflict({'detail': 'La propuesta o sus relaciones cambiaron. Revisa nuevamente el impacto.', 'code': 'stale_impact'})
    if impact['blockers']:
        raise ApprovalConflict({'detail': 'La reasignación tiene dependencias pendientes.', 'blockers': impact['blockers'], 'code': 'reassignment_blocked'})
    target = next(project for project in projects if project.pk == data['target_project_id'])
    source = next((project for project in projects if project.pk == source_id), None)
    next_order = (target.phases.aggregate(value=Max('order'))['value'] or 0) + 1
    released = []
    if context:
        released = _release_retained(context, target, impact, proposal, hosting_start_date=options['hosting_start_date'], next_order=next_order)
    else:
        for offset, phase in enumerate(ProjectPhase.objects.filter(pk__in=impact['phase_ids']).order_by('order', 'pk')):
            phase.project = target
            phase.order = next_order + offset
            fields = ['project', 'order']
            if options['hosting_start_date']:
                phase.hosting_start_date = options['hosting_start_date']
                fields.append('hosting_start_date')
            phase.save(update_fields=fields)
    if impact['creates_phase']:
        ProjectPhase.objects.create(project=target, business_proposal=proposal, order=next_order)
    if source:
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
            leaving = (document.folder.retention_context_id == context.pk) if (context and document.folder) else (document.folder and source and document.folder.project_id == source.pk)
            if leaving:
                kind = document.document_type.code if document.document_type_id else ''
                document.folder = DocumentFolder.objects.filter(parent=root, system_key=project_category_system_key(target.pk, kind)).first() or root
            document.save(update_fields=['project', 'client_user', 'folder'])
    if source and impact['clear_generated_commercial_mirrors']:
        source.payment_milestones = []
        source.hosting_tiers = []
        source.save(update_fields=['payment_milestones', 'hosting_tiers'])
    proposal.save(update_fields=['updated_at'])
    result = {'proposal': _summary(load_proposal(proposal_id)), 'impact': impact, 'idempotent': False}
    source_ref = source.pk if source else context.original_project_id
    source_name = source.name if source else f'«{context.project_name}» (eliminado)'
    try:
        with transaction.atomic():
            ProposalProjectReassignment.objects.create(proposal=proposal, request_id=data['request_id'], payload_hash=fingerprint, source_project_id=source_ref, target_project_id=target.pk, reason=data['reason'], impact=impact, result=result, actor=actor)
    except IntegrityError as exc:
        if ProposalProjectReassignment.objects.select_for_update().filter(request_id=data['request_id']).exists():
            raise ApprovalConflict({'detail': 'Este request_id pertenece a otra operación.', 'code': 'request_conflict'}) from exc
        raise
    if context:
        from content.services.retained_adoption import ownership, remove_from_inventory
        rows = [row for row, _, _ in released]
        items = [{'model': row._meta.label_lower, 'id': row.pk, 'before': before,
                  'after': ownership(type(row)._base_manager.get(pk=row.pk))} for row, before, _ in released]
        ProjectRetentionOperation.objects.create(
            context=context, operation=ProjectRetentionOperation.Operation.PROPOSAL_REASSIGNMENT,
            origin='proposal_reassignment', target_project_id=target.pk, target_project_name=target.name,
            request_id=uuid.uuid4().hex, reason=data['reason'], items=items,
            removed_records=remove_from_inventory(context, rows), actor=actor,
        )
    ProposalChangeLog.objects.create(proposal=proposal, change_type='updated', field_name='project', old_value=str(source_ref), new_value=str(target.pk), description=f'Reasignación {source_name} → {target.name}: {data["reason"]}', actor_type='seller')
    return result
