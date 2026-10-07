"""Delivery lifecycle shared by JWT endpoints and administrative MCP tools.

Commercial ProjectPhase rows are never changed here. Client approval is a fact
about an immutable publication, not a status imported from authoring JSON.
"""
import copy
import hashlib
import json
from collections import defaultdict

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models import (
    ContractAmendment, ContractSignatureEvidence, DeliveryDocumentLink,
    DeliveryMessage, DeliveryOperation, DeliveryPhase, DeliveryPublication,
    DeliveryScope, DeliveryStage, DeliveryWorkspace, Notification, Project,
    ProjectContract, ProjectPhase, Requirement, RequirementReview, UserProfile,
)
from accounts.serializers_delivery import (
    GuideSerializer, LinkSerializer, MessageSerializer, NODE_SERIALIZERS, guide_publication_fields,
    PublishSerializer, ReviewSerializer, SignatureSerializer, VersionedSerializer,
)
from accounts.services.delivery_access import (
    DeliveryConflict, fail, is_admin, project_for_actor, require_admin,
)
from content.models import Document, ProposalDocument

NODE_MODELS = {
    'contracts': ProjectContract, 'amendments': ContractAmendment,
    'scopes': DeliveryScope, 'phases': DeliveryPhase,
    'stages': DeliveryStage, 'requirements': Requirement,
}
NODE_PROJECT_PATHS = {
    'contracts': 'project_id', 'amendments': 'contract__project_id',
    'scopes': 'contract__project_id', 'phases': 'scope__contract__project_id',
    'stages': 'phase__scope__contract__project_id',
    'requirements': 'stage__phase__scope__contract__project_id',
}
LEVEL_KIND = {
    'contract': 'contracts', 'amendment': 'amendments', 'scope': 'scopes',
    'phase': 'phases', 'stage': 'stages', 'requirement': 'requirements',
}
PARENT_FIELDS = {
    'contracts': 'project_id', 'amendments': 'contract_id',
    'scopes': 'contract_id', 'phases': 'scope_id',
    'stages': 'phase_id', 'requirements': 'stage_id',
}


def _validate(serializer_class, data, *, partial=False):
    serializer = serializer_class(data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def _node(project, kind, node_id):
    if kind not in NODE_MODELS:
        fail('Tipo de elemento desconocido.')
    node = NODE_MODELS[kind].objects.filter(
        **{NODE_PROJECT_PATHS[kind]: project.pk, 'pk': node_id},
    ).first()
    if node is None:
        raise NotFound('Elemento de seguimiento no encontrado.')
    return node


def _target(project, level, target_id):
    if level == 'project':
        if target_id != project.pk:
            raise NotFound('Proyecto no encontrado.')
        return project
    if level not in LEVEL_KIND:
        fail('Nivel documental desconocido.')
    return _node(project, LEVEL_KIND[level], target_id)


def _workspace_version(project):
    return DeliveryWorkspace.objects.filter(project=project).values_list('version', flat=True).first() or 0


def _perform(project_id, actor, operation, data, change, *, idempotent=False):
    """Serialize writes; retries check their receipt before checking the version."""
    fingerprint = hashlib.sha256(json.dumps(
        {'operation': operation, 'data': data}, sort_keys=True, default=str,
    ).encode()).hexdigest()
    request_id = data.get('request_id')
    if idempotent and not request_id:
        fail('La operación necesita un identificador de petición.', 'request_id_required')
    if len(str(request_id or '')) > 100:
        fail('El identificador de petición es demasiado largo.')
    from accounts.services.delivery_documents import artifact_scope
    try:
        with artifact_scope(), transaction.atomic():
            project = project_for_actor(project_id, actor, lock=True)
            workspace, _ = DeliveryWorkspace.objects.get_or_create(project=project)
            if request_id:
                receipt = DeliveryOperation.objects.filter(project=project, request_id=request_id).first()
                if receipt:
                    if receipt.actor_id != actor.pk or receipt.fingerprint != fingerprint:
                        raise DeliveryConflict('El identificador ya pertenece a otra operación.')
                    return receipt.response
            expected = data.get('expected_version')
            if isinstance(expected, bool) or not isinstance(expected, int) or expected != workspace.version:
                raise DeliveryConflict()
            result = change(project)
            from accounts.services.delivery_notifications import record_operation_notice
            record_operation_notice(project, actor, operation, result, data)
            workspace.version += 1
            workspace.save(update_fields=['version'])
            response = overview(project.pk, actor)
            if result:
                response['result'] = result
            if request_id:
                DeliveryOperation.objects.create(
                    project=project, request_id=request_id, actor=actor,
                    fingerprint=fingerprint, response=response,
                )
            return response
    except IntegrityError as exc:
        fail('Hay un identificador duplicado o una referencia inválida.', 'delivery_integrity')


def _stage_approved(stage):
    statuses = list(stage.requirements.values_list('review_status', flat=True))
    return bool(statuses) and all(status == 'approved' for status in statuses) and stage.publications.exists()


def _phase_approved(phase):
    stages = list(phase.stages.all())
    return bool(stages) and all(_stage_approved(stage) for stage in stages)


def _has_publication(kind, node):
    if kind == 'requirements':
        return any(item['id'] == node.pk for publication in node.stage.publications.all() for item in publication.payload.get('requirements', []))
    if kind == 'stages':
        return node.publications.exists()
    if kind == 'phases':
        return DeliveryPublication.objects.filter(stage__phase=node).exists()
    if kind == 'scopes':
        return DeliveryPublication.objects.filter(stage__phase__scope=node).exists()
    if kind == 'amendments':
        return DeliveryPublication.objects.filter(stage__phase__scope__amendment=node).exists()
    return DeliveryPublication.objects.filter(stage__phase__scope__contract=node).exists()


def _editable(kind, node, *, delete=False):
    if kind == 'requirements' and node.review_status == 'approved':
        fail('Un requerimiento aprobado está congelado. Registra una ampliación.', 'approved_frozen')
    if kind == 'stages' and _stage_approved(node):
        fail('La etapa aprobada está congelada. Registra otra etapa.', 'approved_frozen')
    if kind == 'phases' and _phase_approved(node):
        fail('La fase aprobada está congelada. Registra otra fase.', 'approved_frozen')
    if delete and _has_publication(kind, node):
        fail('No puedes eliminar evidencia publicada.', 'published_frozen')


def _mark_draft(stage):
    stage.editorial_status = 'draft'
    stage.version += 1
    stage.save(update_fields=['editorial_status', 'version', 'updated_at'])


def _document_source(project, data, existing=None):
    document_id = data.get('document_id', getattr(existing, 'document_id', None))
    proposal_document_id = data.get('proposal_document_id', getattr(existing, 'proposal_document_id', None))
    approval_file_id = data.get('approval_file_id', getattr(existing, 'approval_file_id', None))
    if sum(bool(source_id) for source_id in (document_id, proposal_document_id, approval_file_id)) != 1:
        fail('Selecciona una sola fuente: documento, PDF de propuesta o archivo confirmado.')
    if document_id:
        _owned_document(project, document_id)
    elif approval_file_id:
        from accounts.services.delivery_contract_sources import approval_file_for_project, read_approval_file
        read_approval_file(approval_file_for_project(project, approval_file_id))
    else:
        allowed = ProposalDocument.objects.filter(pk=proposal_document_id).filter(
            Q(proposal__project_phases__project=project) | Q(proposal__deliverable__project=project),
        )
        if not allowed.exists():
            fail('El PDF de propuesta no pertenece a este proyecto.', 'document_context')


def _owned_document(project, document_id):
    doc = Document.objects.select_related('document_type', 'project').filter(pk=document_id, is_archived=False).first()
    if doc is None:
        fail('Documento no disponible.')
    if doc.project_id not in (None, project.pk) or doc.client_user_id not in (None, project.client_id):
        fail('El documento pertenece a otro proyecto o cliente.', 'document_context')
    if doc.project_id is None and doc.client_user_id != project.client_id:
        fail('El documento no está asociado a este proyecto o cliente.', 'document_context')
    if doc.document_type and doc.document_type.code == 'collection_account':
        fail('Las cuentas de cobro conservan su portal financiero.')
    return doc


def _validate_relations(project, kind, values, node):
    if kind in ('contracts', 'amendments'):
        _document_source(project, values, node)
    if kind in ('amendments', 'scopes'):
        contract_id = values.get('contract_id', getattr(node, 'contract_id', None))
        contract = _node(project, 'contracts', contract_id)
        if kind == 'amendments' and node is not None:
            from accounts.services.billing_reassignment import validate_amendment_billing_reassignment
            validate_amendment_billing_reassignment(node, contract)
        if kind == 'scopes':
            amendment_id = values.get('amendment_id', getattr(node, 'amendment_id', None))
            if amendment_id:
                amendment = _node(project, 'amendments', amendment_id)
                if amendment.contract_id != contract_id:
                    fail('El otrosí debe modificar el contrato de este alcance.', 'amendment_contract')
    if kind == 'phases':
        scope_id = values.get('scope_id', getattr(node, 'scope_id', None))
        _node(project, 'scopes', scope_id)
        commercial_id = values.get('commercial_phase_id', getattr(node, 'commercial_phase_id', None))
        if commercial_id and not ProjectPhase.objects.filter(pk=commercial_id, project=project).exists():
            fail('La referencia comercial no pertenece al proyecto.')
    if kind == 'stages':
        parent = _node(project, 'phases', values.get('phase_id', getattr(node, 'phase_id', None)))
        if node is None and _phase_approved(parent):
            fail('La fase aprobada está congelada. Registra otra fase.', 'approved_frozen')
    if kind == 'requirements':
        parent = _node(project, 'stages', values.get('stage_id', getattr(node, 'stage_id', None)))
        if _stage_approved(parent):
            fail('La etapa aprobada está congelada.', 'approved_frozen')
        from accounts.services.delivery_authoring import requirement_provenance
        requirement_provenance(project, parent, values, node)
    if node and kind in ('contracts', 'amendments') and signature_state(node)['signature_status'] != 'unsigned':
        if any(field in values and values[field] != getattr(node, field, None) for field in ('document_id', 'proposal_document_id', 'approval_file_id', 'contract_id', 'key', 'title')):
            fail('La fuente del contrato firmado y su identidad están congeladas.', 'signed_source_frozen')
    if node and _has_publication(kind, node):
        protected = [PARENT_FIELDS[kind], 'document_id', 'proposal_document_id', 'approval_file_id', 'amendment_id', 'commercial_phase_id', 'key']
        if any(field in values and values[field] != getattr(node, field, None) for field in protected):
            fail('Las referencias publicadas se conservan. Registra una ampliación.', 'published_frozen')
        if kind in ('contracts', 'amendments', 'scopes', 'phases'):
            changed = [field for field in values if getattr(node, field, None) != values[field]]
            if changed:
                fail('El contexto contractual publicado se conserva. Registra una ampliación.', 'published_frozen')


def mutate_node(project_id, actor, kind, data, node_id=None, delete=False):
    require_admin(actor)
    if kind not in NODE_MODELS:
        fail('Tipo de elemento desconocido.')
    values = _validate(VersionedSerializer if delete else NODE_SERIALIZERS[kind], data, partial=node_id is not None)
    if 'expected_version' not in values:
        fail('Se requiere la versión del seguimiento.')

    def change(project):
        node = _node(project, kind, node_id) if node_id else None
        if node:
            _editable(kind, node, delete=delete)
        if delete:
            result = {'kind': kind, 'id': node.pk, 'deleted': True}
            stage = node.stage if kind == 'requirements' else None
            if kind in ('contracts', 'amendments') and node.signature_evidence.exists():
                fail('No puedes eliminar evidencia de firma.')
            try:
                node.delete()
            except ProtectedError:
                fail('Este contenido sustenta un contexto o evidencia que debe conservarse.', 'context_retained')
            if stage:
                _mark_draft(stage)
            return result
        fields = {key: value for key, value in values.items() if key not in ('expected_version', 'request_id')}
        _validate_relations(project, kind, fields, node)
        if kind in ('contracts', 'amendments') and fields.get('approval_file_id') and (
                node is None or node.approval_file_id != fields['approval_file_id']):
            if fields.get('client_visible'):
                fail('El archivo confirmado se registra primero en privado. Habilita su consulta después de revisarlo.', 'source_visibility')
            fields['client_visible'] = False
        if kind == 'contracts':
            fields['project_id'] = project.pk
        parent_field = PARENT_FIELDS[kind]
        parent_id = fields.get(parent_field, getattr(node, parent_field, None))
        key = fields.get('key', getattr(node, 'key', None))
        duplicates = NODE_MODELS[kind].objects.filter(**{parent_field: parent_id, 'key': key})
        if node:
            duplicates = duplicates.exclude(pk=node.pk)
        if duplicates.exists():
            fail('Ya existe este identificador en el nivel seleccionado.', 'duplicate_key')
        if node:
            for field, value in fields.items():
                setattr(node, field, value)
            node.version += 1
            if kind == 'requirements':
                node.review_status = 'pending'
            if kind == 'stages':
                node.editorial_status = 'draft'
            node.save()
        else:
            node = NODE_MODELS[kind].objects.create(**fields)
        if kind == 'requirements':
            _mark_draft(node.stage)
        if kind in ('contracts', 'amendments') and node.document_id:
            DeliveryDocumentLink.objects.get_or_create(
                project=project, document_id=node.document_id, level='contract' if kind == 'contracts' else 'amendment',
                **{'contract' if kind == 'contracts' else 'amendment': node}, defaults={'created_by': actor},
            )
        if kind in ('contracts', 'amendments'):
            from accounts.services.delivery_documents import ensure_portal_signature_capture
            ensure_portal_signature_capture(node, actor)
        if kind == 'scopes' and node.is_current:
            DeliveryScope.objects.filter(contract=node.contract, is_current=True).exclude(pk=node.pk).update(is_current=False)
        return {'kind': kind, 'id': node.pk}

    return _perform(project_id, actor, f'{kind}:{node_id}:{delete}', values, change)


def signature_state(node):
    evidence = node.signature_evidence.first()
    if evidence:
        return {'signature_status': evidence.method, 'signed_at': evidence.signed_at.isoformat(), 'signer_name': evidence.signer_name}
    doc = node.document if node.document_id else None
    project = node.project
    if doc and doc.requires_signature and doc.signed_at and doc.signed_by_id == project.client_id:
        return {'signature_status': 'portal', 'signed_at': doc.signed_at.isoformat(), 'signer_name': doc.signature_name or project.client.get_full_name() or project.client.email}
    return {'signature_status': 'unsigned', 'signed_at': None, 'signer_name': ''}


def _contract_ready(scope):
    from accounts.services.delivery_documents import ensure_portal_signature_capture
    ensure_portal_signature_capture(scope.contract, scope.contract.project.client)
    if scope.amendment_id:
        ensure_portal_signature_capture(scope.amendment, scope.contract.project.client)
    if signature_state(scope.contract)['signature_status'] == 'unsigned':
        fail('El contrato debe estar firmado antes de publicar.', 'contract_unsigned')
    if scope.amendment_id and signature_state(scope.amendment)['signature_status'] == 'unsigned':
        fail('El otrosí aplicable debe estar firmado antes de publicar.', 'amendment_unsigned')
    if not scope.contract.client_visible or (scope.amendment_id and not scope.amendment.client_visible):
        fail('El cliente debe poder consultar el contrato y sus modificaciones.')


def _requirement_payload(req):
    return {'id': req.pk, 'key': req.key, 'title': req.title, 'description': req.description,
            'created_at': req.created_at.isoformat(), 'updated_at': req.updated_at.isoformat(),
            'guide': req.guide, 'order': req.order, 'version': req.version,
            'review_status': req.review_status,
            'context_id': str(req.context_id) if req.context_id else None,
            'source_references': req.source_references}


def _validate_guide(req):
    guide = _validate(GuideSerializer, req.guide)
    labels = guide_publication_fields(
        guide, sourced=bool(req.context_id), approved=req.review_status == 'approved',
    )
    for field, label in labels.items():
        if not guide.get(field):
            fail(f'Completa {label} en «{req.title}» antes de publicar.', 'guide_incomplete')


def _notify(project, actor, title, message='', *, client=False, stage_id=None):
    users = [project.client_id] if client else list(UserProfile.objects.filter(role='admin', user__is_active=True).values_list('user_id', flat=True))
    users = sorted(set(users) - {actor.pk})
    Notification.objects.bulk_create([
        Notification(user_id=user_id, type='general', title=title, message=message,
                     project=project, related_object_type='delivery_stage' if stage_id else 'project',
                     related_object_id=stage_id or project.pk)
        for user_id in users
    ])


def publish_stage(project_id, actor, stage_id, data):
    require_admin(actor)
    values = _validate(PublishSerializer, data)

    def change(project):
        stage = _node(project, 'stages', stage_id)
        _editable('stages', stage)
        _contract_ready(stage.phase.scope)
        requirements = list(stage.requirements.all())
        if not requirements:
            fail('Agrega al menos un requerimiento antes de publicar.', 'empty_stage')
        for req in requirements:
            _validate_guide(req)
        stage.editorial_status = 'published'
        stage.version += 1
        stage.save(update_fields=['editorial_status', 'version', 'updated_at'])
        for req in requirements:
            if req.review_status != 'approved':
                req.review_status = 'in_review'
                req.save(update_fields=['review_status', 'updated_at'])
        previous = stage.publications.first()
        publication = DeliveryPublication.objects.create(
            stage=stage, round=(previous.round + 1 if previous else 1), published_by=actor,
            payload={'id': stage.pk, 'key': stage.key, 'title': stage.title,
                     'description': stage.description, 'version': stage.version,
                     'requirements': [_requirement_payload(req) for req in requirements],
                     'contract_signature': signature_state(stage.phase.scope.contract),
                     'amendment_signature': signature_state(stage.phase.scope.amendment) if stage.phase.scope.amendment_id else None},
        )
        from accounts.services.delivery_documents import capture_publication_documents
        capture_publication_documents(project, stage, publication)
        return {'kind': 'publications', 'id': publication.pk}

    return _perform(project_id, actor, f'publish:{stage_id}', values, change, idempotent=True)


def _level_visible(project, actor, level, target):
    if is_admin(actor):
        return True
    if level == 'project':
        return True
    if level == 'contract':
        return target.client_visible
    if level == 'amendment':
        return target.client_visible and target.contract.client_visible
    if level == 'scope':
        return target.contract.client_visible and (not target.amendment_id or target.amendment.client_visible) and DeliveryPublication.objects.filter(stage__phase__scope=target).exists()
    if level == 'phase':
        return _level_visible(project, actor, 'scope', target.scope) and DeliveryPublication.objects.filter(stage__phase=target).exists()
    if level == 'stage':
        return target.phase.scope.contract.client_visible and (not target.phase.scope.amendment_id or target.phase.scope.amendment.client_visible) and target.publications.exists()
    return _level_visible(project, actor, 'stage', target.stage) and any(
        req['id'] == target.pk for req in target.stage.publications.first().payload.get('requirements', [])
    )


def visible_requirements(project_id, actor):
    project = project_for_actor(project_id, actor)
    qs = Requirement.objects.filter(stage__phase__scope__contract__project=project)
    if is_admin(actor):
        return qs
    ids = []
    latest = {}
    publications = DeliveryPublication.objects.filter(
        stage__phase__scope__contract__project=project, stage__phase__scope__contract__client_visible=True,
    ).order_by('stage_id', '-round')
    for pub in publications:
        latest.setdefault(pub.stage_id, pub)
    for pub in latest.values():
        ids.extend(req['id'] for req in pub.payload.get('requirements', []))
    return qs.filter(pk__in=ids)


def _accessible_evidence_docs(project, actor, ids, *, allow_private=False):
    docs = []
    if len(ids) != len(set(ids)):
        fail('No repitas documentos en la respuesta.')
    for doc_id in ids:
        doc = _owned_document(project, doc_id)
        if not allow_private:
            from accounts.services.delivery_documents import document_is_visible
            if not document_is_visible(actor, doc):
                raise NotFound('Documento no disponible para este cliente.')
        docs.append(doc)
    return docs


def _message(project, actor, values):
    level, target_id = values['level'], values['target_id']
    target = _target(project, level, target_id)
    if not _level_visible(project, actor, level, target):
        raise NotFound('Este nivel aún no está publicado.')
    internal = values.get('is_internal', False)
    if internal and not is_admin(actor):
        raise PermissionDenied('Solo el equipo puede escribir notas internas.')
    if not internal and is_admin(actor) and not _level_visible(project, project.client, level, target):
        fail('Publica este contenido antes de enviar una respuesta al cliente.', 'target_unpublished')
    req_ids = values.get('requirement_ids', [])
    reqs = list(visible_requirements(project.pk, actor).filter(pk__in=req_ids))
    if len(reqs) != len(set(req_ids)):
        fail('Hay requerimientos fuera del seguimiento visible.')
    if not internal and is_admin(actor):
        visible_ids = set(visible_requirements(project.pk, project.client).filter(pk__in=req_ids).values_list('pk', flat=True))
        if visible_ids != set(req_ids):
            fail('La respuesta pública solo puede referenciar requerimientos publicados.', 'target_unpublished')
    for req in reqs:
        parents = {'project': project.pk, 'contract': req.stage.phase.scope.contract_id,
                   'amendment': req.stage.phase.scope.amendment_id, 'scope': req.stage.phase.scope_id,
                   'phase': req.stage.phase_id, 'stage': req.stage_id, 'requirement': req.pk}
        if parents[level] != target_id:
            fail('La respuesta debe referenciar requerimientos del nivel seleccionado.')
    docs = _accessible_evidence_docs(project, actor, values.get('document_ids', []), allow_private=is_admin(actor))
    if docs and not internal:
        from accounts.services.delivery_documents import document_can_be_shared
        if any(not document_can_be_shared(project, doc) for doc in docs):
            fail('Un documento asociado a contenido privado necesita publicarse antes de compartirse.', 'document_unpublished')
    from accounts.services.delivery_authoring import message_provenance
    provenance = message_provenance(project, actor, values)
    msg = DeliveryMessage.objects.create(project=project, actor=actor, level=level, target_id=target_id,
                                         message=values['message'], is_internal=internal, **provenance)
    msg.requirements.set(reqs)
    msg.documents.set(docs)
    if docs and not internal:
        from accounts.services.delivery_documents import share_message_documents
        share_message_documents(project, actor, level, target, docs)
    return msg


def add_message(project_id, actor, data):
    values = _validate(MessageSerializer, data)
    return _perform(project_id, actor, 'message', values,
                    lambda project: {'kind': 'messages', 'id': _message(project, actor, values).pk}, idempotent=True)


def review_stage(project_id, actor, stage_id, data, historical=False):
    if historical:
        require_admin(actor)
    elif is_admin(actor):
        raise PermissionDenied('La revisión corresponde al cliente propietario, no al administrador.')
    values = _validate(ReviewSerializer, data)
    if not historical and any(key in values for key in ('evidence_message', 'evidence_document_ids', 'client_statement', 'source_message_id', 'original_reviewer', 'occurred_at', 'evidence_channel', 'external_reference')):
        fail('La evidencia histórica solo corresponde al registro administrativo.')
    if historical and (values.get('client_statement') is not True or not values.get('evidence_message', '').strip()):
        fail('Transcribe la aprobación explícita del cliente y confirma su procedencia.', 'client_evidence_required')
    if historical and any(decision['decision'] != 'approved' for decision in values['decisions']):
        fail('El registro histórico solo admite aprobaciones expresas.')

    def change(project):
        stage = _node(project, 'stages', stage_id)
        if not _level_visible(project, actor, 'stage', stage):
            raise NotFound('La etapa no está publicada.')
        publication = stage.publications.first()
        if publication is None:
            fail('Publica primero la etapa que el cliente validó.')
        snapshots = {req['id']: req for req in publication.payload.get('requirements', [])}
        decision_ids = [decision['requirement_id'] for decision in values['decisions']]
        if len(decision_ids) != len(set(decision_ids)):
            fail('No repitas un requerimiento en una respuesta.')
        evidence_docs = _accessible_evidence_docs(project, actor, values.get('evidence_document_ids', []), allow_private=historical)
        evidence = _historical_evidence(project, values, evidence_docs) if historical else {
            'original_reviewer': actor.get_full_name() or actor.email, 'reviewed_at': timezone.now(),
            'source_message': None, 'source_snapshot': {'channel': 'platform', 'client_user_id': actor.pk},
        }
        for decision in values['decisions']:
            req = _node(project, 'requirements', decision['requirement_id'])
            snapshot = snapshots.get(req.pk)
            if req.stage_id != stage.pk or snapshot is None:
                fail('El requerimiento no pertenece a esta publicación.')
            if req.version != decision['version'] or snapshot['version'] != decision['version']:
                raise DeliveryConflict('La guía cambió. Espera su nueva publicación antes de revisarla.')
            if req.review_status == 'approved':
                fail('La aprobación previa se conserva.', 'approved_frozen')
            if req.review_status != 'in_review':
                fail('Este requerimiento necesita una nueva publicación antes de otra revisión.', 'review_round_closed')
            if decision['decision'] != 'approved' and not decision.get('message', '').strip():
                fail('Describe el motivo de la objeción o rechazo.', 'decision_reason_required')
            review = RequirementReview.objects.create(
                publication=publication, requirement=req, actor=actor,
                requirement_version=req.version, content_snapshot=snapshot,
                decision=decision['decision'], message=decision.get('message', ''),
                environment=decision.get('environment', ''), is_external=historical,
                client_statement=values.get('evidence_message', ''),
                evidence_document_ids=[doc.pk for doc in evidence_docs], **evidence,
            )
            if evidence_docs:
                from accounts.services.delivery_review_evidence import capture_review_documents
                capture_review_documents(review, evidence_docs)
            req.review_status = decision['decision']
            req.save(update_fields=['review_status', 'updated_at'])
        message_text = values.get('message') or values.get('evidence_message')
        if message_text:
            _message(project, actor, {'level': 'stage', 'target_id': stage.pk,
                                     'requirement_ids': decision_ids, 'message': message_text,
                                     'document_ids': values.get('document_ids', [])})
        return {'kind': 'reviews', 'stage_id': stage.pk}

    return _perform(project_id, actor, f'review:{stage_id}:{historical}', values, change, idempotent=True)


def attest_signature(project_id, actor, kind, node_id, data, file):
    require_admin(actor)
    if kind not in ('contracts', 'amendments'):
        fail('La evidencia de firma debe pertenecer a un contrato u otrosí.')
    values = _validate(SignatureSerializer, data)
    if values['signed_at'] > timezone.now():
        fail('La fecha de firma no puede estar en el futuro.')
    if file is None:
        fail('Adjunta el PDF firmado.')
    from accounts.services.delivery_documents import validated_pdf_bytes, store_private_pdf
    pdf = validated_pdf_bytes(file)
    values['sha256'] = hashlib.sha256(pdf).hexdigest()

    def change(project):
        node = _node(project, kind, node_id)
        if _has_publication(kind, node) or node.signature_evidence.exists():
            fail('La evidencia contractual firmada está congelada.', 'published_frozen')
        evidence = ContractSignatureEvidence(
            **{'contract' if kind == 'contracts' else 'amendment': node},
            signer_name=values['signer_name'], signed_at=values['signed_at'],
            attestation=values['attestation'], attested_by=actor, sha256=values['sha256'],
            method='external', source_sha256=values['sha256'],
            source_snapshot={'title': node.title, 'document_id': node.document_id,
                             'proposal_document_id': node.proposal_document_id,
                             'approval_file_id': node.approval_file_id},
        )
        store_private_pdf(evidence, pdf, 'signed.pdf')
        evidence.save()
        return {'kind': 'signature_evidence', 'id': evidence.pk}

    return _perform(project_id, actor, f'signature:{kind}:{node_id}', values, change, idempotent=True)


def link_document(project_id, actor, data):
    require_admin(actor)
    values = _validate(LinkSerializer, data)

    def change(project):
        target = _target(project, values['level'], values['target_id'])
        if values['level'] in ('stage', 'requirement', 'phase'):
            _editable(LEVEL_KIND[values['level']], target)
        doc = _owned_document(project, values['document_id'])
        filters = {'project': project, 'level': values['level'], 'document': doc}
        if values['level'] != 'project':
            filters[values['level']] = target
        if DeliveryDocumentLink.objects.filter(**filters).exists():
            fail('Este documento ya está asociado al nivel seleccionado.')
        link = DeliveryDocumentLink.objects.create(**filters, created_by=actor)
        stage = target if values['level'] == 'stage' else target.stage if values['level'] == 'requirement' else None
        if stage:
            _mark_draft(stage)
        return {'kind': 'documents', 'id': link.pk}

    return _perform(project_id, actor, 'link-document', values, change)


def unlink_document(project_id, actor, link_id, data):
    require_admin(actor)
    values = _validate(VersionedSerializer, data)

    def change(project):
        link = DeliveryDocumentLink.objects.filter(project=project, pk=link_id).first()
        if not link:
            raise NotFound('Asociación documental no encontrada.')
        if link.snapshots.exists():
            fail('Los documentos publicados se conservan como evidencia.', 'published_frozen')
        target = getattr(link, link.level) if link.level != 'project' else project
        if link.level in ('stage', 'requirement', 'phase'):
            _editable(LEVEL_KIND[link.level], target)
        link.delete()
        return {'kind': 'documents', 'id': link_id, 'deleted': True}

    return _perform(project_id, actor, 'unlink-document', values, change)


# File authorization and generation live separately to keep lifecycle writes small.
def list_documents(project_id, actor, level=None, target_id=None):
    from accounts.services.delivery_documents import list_documents as implementation
    return implementation(project_id, actor, level, target_id)


def document_options(project_id, actor):
    from accounts.services.delivery_documents import document_options as implementation
    return implementation(project_id, actor)


def document_pdf(project_id, actor, link_id):
    from accounts.services.delivery_documents import document_pdf as implementation
    return implementation(project_id, actor, link_id)


def contract_pdf(project_id, actor, kind, node_id):
    from accounts.services.delivery_documents import contract_pdf as implementation
    return implementation(project_id, actor, kind, node_id)


def _status(statuses, *, published=True):
    if statuses and all(status == 'approved' for status in statuses):
        return 'approved'
    if not published:
        return 'draft'
    if 'rejected' in statuses:
        return 'rejected'
    if 'objected' in statuses:
        return 'objected'
    return 'in_review'


def _base(node):
    result = {'id': node.pk, 'key': node.key, 'title': node.title, 'version': node.version,
              'created_at': node.created_at.isoformat(), 'updated_at': node.updated_at.isoformat()}
    for field in ('description', 'order', 'contract_id', 'amendment_id', 'scope_id', 'phase_id', 'stage_id', 'commercial_phase_id', 'is_current'):
        if hasattr(node, field):
            result[field] = getattr(node, field)
    return result


def overview(project_id, actor):
    project = project_for_actor(project_id, actor)
    admin = is_admin(actor)
    contracts = list(ProjectContract.objects.filter(project=project).select_related('project__client', 'document', 'proposal_document', 'approval_file').prefetch_related('signature_evidence'))
    amendments = list(ContractAmendment.objects.filter(contract__project=project).select_related('contract__project__client', 'document', 'proposal_document', 'approval_file').prefetch_related('signature_evidence'))
    scopes = list(DeliveryScope.objects.filter(contract__project=project))
    phases = list(DeliveryPhase.objects.filter(scope__contract__project=project))
    stages = list(DeliveryStage.objects.filter(phase__scope__contract__project=project))
    requirements = list(Requirement.objects.filter(stage__phase__scope__contract__project=project))
    publications = list(DeliveryPublication.objects.filter(stage__phase__scope__contract__project=project).select_related('stage__phase__scope').order_by('stage_id', '-round'))
    latest = {}
    for publication in publications:
        latest.setdefault(publication.stage_id, publication)
    reviews = list(RequirementReview.objects.filter(requirement__stage__phase__scope__contract__project=project).select_related('actor').prefetch_related('document_evidence').order_by('created_at', 'id'))
    from accounts.services.delivery_review_evidence import evidence_data
    review_states = {}
    review_records = defaultdict(list)
    for review in reviews:
        review_states[(review.requirement_id, review.requirement_version, review.publication_id)] = review.decision
        review_records[review.requirement_id].append({
            'id': review.pk, 'decision': review.decision, 'message': review.message,
            'environment': review.environment, 'is_external': review.is_external,
            'actor_name': review.actor.get_full_name() or review.actor.email,
            'original_reviewer': review.original_reviewer,
            'reviewed_at': review.reviewed_at.isoformat(), 'recorded_at': review.created_at.isoformat(),
            'version': review.requirement_version, 'publication_id': review.publication_id,
            'client_statement': review.client_statement,
            'actor_id': review.actor_id, 'requirement_id': review.requirement_id,
            'evidence_channel': review.source_snapshot.get('channel', 'platform'),
            'source_message_id': review.source_message_id,
            'evidence_document_ids': review.evidence_document_ids,
            'evidence_documents': [evidence_data(item, project.pk) for item in review.document_evidence.all()],
            **({'source_snapshot': review.source_snapshot, 'content_snapshot': review.content_snapshot} if admin else {}),
        })
    from accounts.services.delivery_documents import DeliveryDocumentIndex, list_documents, visible_message_documents
    document_index = DeliveryDocumentIndex(project, actor, publications=publications, reviews=reviews)
    links = list_documents(project.pk, actor, index=document_index)['documents']
    documents = defaultdict(list)
    for link in links:
        documents[(link['level'], link['target_id'])].append(link)
    messages = defaultdict(list)
    qs = DeliveryMessage.objects.filter(project=project).select_related('actor').prefetch_related('requirements', 'documents')
    if not admin:
        qs = qs.filter(is_internal=False)
    for message in qs:
        messages[(message.level, message.target_id)].append({
            'id': message.pk, 'actor_name': message.actor.get_full_name() or message.actor.email,
            'message': message.message, 'requirement_ids': [req.pk for req in message.requirements.all()],
            'documents': visible_message_documents(project, actor, message, index=document_index),
            'is_internal': message.is_internal, 'created_at': message.created_at.isoformat(),
            **({'context_id': str(message.context_id) if message.context_id else None,
                'source_references': message.source_references,
                'classifications': message.reply_classifications} if admin else {}),
        })

    def add_attachments(result, level, node_id):
        result['documents'] = documents[(level, node_id)]
        result['messages'] = messages[(level, node_id)]
        return result

    def contract_data(node, kind):
        result = _base(node)
        result.update({'document_id': node.document_id, 'document_uuid': str(node.document.uuid) if node.document_id else None,
                       'proposal_document_id': node.proposal_document_id, 'client_visible': node.client_visible,
                       'pdf_url': f'/api/accounts/projects/{project.pk}/delivery/{kind}/{node.pk}/pdf/'})
        result.update(signature_state(node))
        if node.approval_file_id:
            from accounts.services.delivery_contract_sources import file_metadata
            metadata = file_metadata(node.approval_file)
            evidence = node.signature_evidence.first()
            result.update({'approval_file_id': node.approval_file_id,
                           'source_download_url': f'/api/accounts/projects/{project.pk}/delivery/{kind}/{node.pk}/source/',
                           'source_filename': 'signed-contract.pdf' if evidence else metadata['filename'],
                           'source_content_type': 'application/pdf' if evidence else metadata['content_type'],
                           'source_sha256': evidence.sha256 if evidence else metadata['sha256']})
            if not evidence and metadata['content_type'] != 'application/pdf':
                result['pdf_url'] = None
        else:
            result['approval_file_id'] = None
        if admin:
            result['signature_evidence'] = [
                {'id': evidence.pk, 'sha256': evidence.sha256, 'signer_name': evidence.signer_name,
                 'signed_at': evidence.signed_at.isoformat(), 'attestation': evidence.attestation,
                 'attested_by_id': evidence.attested_by_id, 'recorded_at': evidence.created_at.isoformat(),
                 'method': evidence.method, 'source_sha256': evidence.source_sha256, 'source_snapshot': evidence.source_snapshot}
                for evidence in node.signature_evidence.all()
            ]
        return add_attachments(result, 'contract' if kind == 'contracts' else 'amendment', node.pk)

    amendment_map = defaultdict(list)
    for node in amendments:
        if admin or (node.client_visible and any(contract.pk == node.contract_id and contract.client_visible for contract in contracts)):
            amendment_map[node.contract_id].append(contract_data(node, 'amendments'))
    contract_map = {}
    for node in contracts:
        if admin or node.client_visible:
            result = contract_data(node, 'contracts')
            result['amendments'] = amendment_map[node.pk]
            contract_map[node.pk] = result
    requirement_map = defaultdict(list)
    all_stage_states = defaultdict(list)
    for req in requirements:
        all_stage_states[req.stage_id].append(req.review_status)
        if admin:
            result = _requirement_payload(req)
            result['stage_id'] = req.stage_id
            result['reviews'] = review_records[req.pk]
            requirement_map[req.stage_id].append(add_attachments(result, 'requirement', req.pk))
    stage_map = defaultdict(list)
    all_phase_states = defaultdict(list)
    for stage in stages:
        publication = latest.get(stage.pk)
        statuses = all_stage_states[stage.pk]
        state = _status(statuses, published=stage.editorial_status == 'published' and publication is not None)
        # An empty/draft stage prevents a whole phase from being approved.
        all_phase_states[stage.phase_id].append(state)
        if not admin and publication is None:
            continue
        result = _base(stage) if admin else copy.deepcopy(publication.payload)
        if not admin:
            client_requirements = []
            for snapshot in result.get('requirements', []):
                snapshot.pop('context_id', None)
                snapshot.pop('source_references', None)
                snapshot['review_status'] = ('approved' if snapshot.get('review_status') == 'approved' else review_states.get(
                    (snapshot['id'], snapshot['version'], publication.pk), 'in_review',
                ))
                snapshot['reviews'] = review_records[snapshot['id']]
                client_requirements.append(add_attachments(snapshot, 'requirement', snapshot['id']))
            result['requirements'] = client_requirements
            state = _status([req['review_status'] for req in client_requirements], published=True)
            # A newly drafted, unexposed guide still blocks formal aggregate closure.
            if state == 'approved' and any(status != 'approved' for status in statuses):
                state = 'in_review'
        else:
            result['requirements'] = requirement_map[stage.pk]
        result.update({'phase_id': stage.phase_id, 'publication_id': publication.pk if publication else None,
                       'editorial_status': stage.editorial_status if admin else 'published', 'status': state})
        stage_map[stage.phase_id].append(add_attachments(result, 'stage', stage.pk))
    phase_map = defaultdict(list)
    all_scope_states = defaultdict(list)
    for phase in phases:
        visible_stages = stage_map[phase.pk]
        phase_states = all_phase_states[phase.pk] if admin else [stage['status'] for stage in visible_stages] + ['draft'] * (len(all_phase_states[phase.pk]) - len(visible_stages))
        phase_status = _status(phase_states, published=bool(visible_stages))
        all_scope_states[phase.scope_id].append(phase_status)
        if not admin and not visible_stages:
            continue
        result = _base(phase)
        result['stages'] = visible_stages
        result['status'] = phase_status
        phase_map[phase.scope_id].append(add_attachments(result, 'phase', phase.pk))
    scope_results = []
    for scope in scopes:
        if scope.contract_id not in contract_map:
            continue
        if not admin and (not phase_map[scope.pk] or (scope.amendment_id and not any(amendment['id'] == scope.amendment_id for amendment in amendment_map[scope.contract_id]))):
            continue
        result = _base(scope)
        result['phases'] = phase_map[scope.pk]
        result['status'] = _status(all_scope_states[scope.pk], published=bool(result['phases']))
        scope_results.append(add_attachments(result, 'scope', scope.pk))
    return {'project': add_attachments({'id': project.pk, 'name': project.name}, 'project', project.pk),
            'version': _workspace_version(project), 'is_admin': admin,
            'contracts': list(contract_map.values()), 'scopes': scope_results}


IMPORT_FIELDS = {
    'scopes': {'key', 'title', 'description', 'contract_id', 'amendment_id', 'is_current', 'phases'},
    'phases': {'key', 'title', 'description', 'commercial_phase_id', 'order', 'stages'},
    'stages': {'key', 'title', 'description', 'order', 'requirements'},
    'requirements': {'key', 'title', 'description', 'guide', 'order'},
}
IMPORT_CHILDREN = {'scopes': 'phases', 'phases': 'stages', 'stages': 'requirements'}


def _validate_import(project, payload, *, allow_provenance=False):
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'scopes'} or type(payload['schema_version']) is not int or payload['schema_version'] != 1:
        fail('El JSON debe incluir schema_version: 1 y scopes.', 'import_schema')
    count = {'scopes': 0, 'phases': 0, 'stages': 0, 'requirements': 0}

    def walk(kind, items, parent=None):
        if not isinstance(items, list) or len(items) > 100:
            fail('Cada nivel debe ser una lista de hasta 100 elementos.')
        keys = set()
        for item in items:
            allowed_fields = IMPORT_FIELDS[kind] | ({'context_id', 'source_references'} if allow_provenance and kind == 'requirements' else set())
            if not isinstance(item, dict) or set(item) - allowed_fields:
                fail('El JSON contiene campos no permitidos. No importes estados, firmas ni aprobaciones.', 'import_fields')
            child_kind = IMPORT_CHILDREN.get(kind)
            values = {key: value for key, value in item.items() if key != child_kind}
            parent_field = PARENT_FIELDS[kind]
            if kind != 'scopes':
                values[parent_field] = parent.pk if parent else 1
            validated = _validate(NODE_SERIALIZERS[kind], {**values, 'expected_version': 0})
            validated.pop('expected_version')
            if validated['key'] in keys:
                fail('Hay identificadores duplicados en el mismo nivel.', 'duplicate_key')
            keys.add(validated['key'])
            query = None
            if kind == 'scopes':
                _validate_relations(project, kind, validated, None)
                query = DeliveryScope.objects.filter(contract_id=validated['contract_id'], key=validated['key'])
            elif parent:
                query = NODE_MODELS[kind].objects.filter(**{parent_field: parent.pk, 'key': validated['key']})
            node = query.first() if query is not None else None
            if node and kind == 'requirements' and node.context_id and not allow_provenance:
                fail('La guía conserva sus fuentes. Usa JSON v2 con contexto y citas para actualizarla.', 'context_required')
            if node and _has_publication(kind, node):
                provided_fields = {key: validated[key] for key in item if key != child_kind}
                if any(getattr(node, key) != value for key, value in provided_fields.items()):
                    fail('La importación solo puede actualizar borradores sin publicar. Conserva el contenido publicado.', 'import_drafts_only')
            if parent and not node:
                _validate_relations(project, kind, validated, None)
            if kind == 'phases' and validated.get('commercial_phase_id'):
                if not ProjectPhase.objects.filter(project=project, pk=validated['commercial_phase_id']).exists():
                    fail('La referencia comercial no pertenece al proyecto.')
            count[kind] += 1
            if sum(count.values()) > 1000:
                fail('Importa como máximo 1000 elementos por operación.')
            if child_kind:
                walk(child_kind, item.get(child_kind, []), node)
    walk('scopes', payload['scopes'])
    if not count['scopes']:
        fail('El JSON debe incluir al menos un alcance.')
    return count


def import_payload(project_id, actor, payload, expected_version, apply=False, request_id=None):
    require_admin(actor)
    project = project_for_actor(project_id, actor)
    values = _validate(VersionedSerializer, {'expected_version': expected_version, **({'request_id': request_id} if request_id else {})})

    def prepared(locked_project):
        cited = isinstance(payload, dict) and payload.get('schema_version') == 2
        if cited:
            from accounts.services.delivery_authoring import validate_guides_payload
            normalized = validate_guides_payload(locked_project, actor, payload)
        else:
            normalized = payload
        return normalized, cited

    if not apply:
        if values['expected_version'] != _workspace_version(project):
            raise DeliveryConflict()
        normalized, cited = prepared(project)
        summary = _validate_import(project, normalized, allow_provenance=cited)
        return {'valid': True, 'summary': summary, 'payload': payload, 'version': values['expected_version']}
    values['payload'] = payload

    def change(locked_project):
        normalized, cited = prepared(locked_project)
        _validate_import(locked_project, normalized, allow_provenance=cited)
        def walk(kind, items, parent=None):
            child_kind = IMPORT_CHILDREN.get(kind)
            for position, item in enumerate(items):
                fields = {key: value for key, value in item.items() if key != child_kind}
                if kind != 'scopes':
                    fields[PARENT_FIELDS[kind]] = parent.pk
                    fields.setdefault('order', position)
                parent_id = fields[PARENT_FIELDS[kind]]
                lookup = {PARENT_FIELDS[kind]: parent_id, 'key': fields['key']}
                node = NODE_MODELS[kind].objects.filter(**lookup).first()
                if node is None or not _has_publication(kind, node):
                    node, _ = NODE_MODELS[kind].objects.update_or_create(
                        **lookup,
                        defaults={key: value for key, value in fields.items() if key not in (PARENT_FIELDS[kind], 'key')},
                    )
                    node.version += 1
                    node.save(update_fields=['version', 'updated_at'])
                    if kind == 'requirements':
                        _mark_draft(node.stage)
                if kind == 'scopes' and node.is_current:
                    DeliveryScope.objects.filter(contract=node.contract, is_current=True).exclude(pk=node.pk).update(is_current=False)
                if child_kind:
                    walk(child_kind, item.get(child_kind, []), node)
        walk('scopes', normalized['scopes'])
        return {'kind': 'import', 'summary': _validate_import(locked_project, normalized, allow_provenance=cited)}

    return _perform(project_id, actor, 'import', values, change, idempotent=True)


def authoring_prompt(project_id, actor):
    """Discover explicit selections without loading any source body."""
    from accounts.services.delivery_authoring import prompt_options
    return prompt_options(project_id, actor)


def evidence_options(project_id, actor):
    require_admin(actor)
    project = project_for_actor(project_id, actor)
    from content.models import CommunicationMessage
    messages = CommunicationMessage.objects.filter(
        thread__client__user=project.client, direction='incoming', status='received', voided_at__isnull=True,
    ).filter(Q(thread__project=project) | Q(thread__project__isnull=True)).order_by('-occurred_at', '-id')[:100]
    return {'messages': [{'id': message.pk, 'subject': message.subject, 'content': message.content,
                          'occurred_at': message.occurred_at.isoformat(), 'channel': message.channel,
                          'original_reviewer': project.client.get_full_name() or project.client.email}
                         for message in messages]}


def _historical_evidence(project, values, documents):
    source_message_id = values.get('source_message_id')
    if source_message_id:
        from content.models import CommunicationMessage
        source = CommunicationMessage.objects.filter(
            pk=source_message_id, direction='incoming', status='received', voided_at__isnull=True,
            thread__client__user=project.client,
        ).filter(Q(thread__project=project) | Q(thread__project__isnull=True)).first()
        if source is None:
            fail('La aprobación debe provenir de un mensaje entrante de este cliente.', 'client_evidence_required')
        if values['evidence_message'].strip() not in source.content:
            fail('La evidencia debe citar el contenido recibido del cliente.', 'client_evidence_required')
        snapshot = {'channel': source.channel, 'direction': source.direction, 'subject': source.subject,
                    'content': source.content, 'occurred_at': source.occurred_at.isoformat(),
                    'client_user_id': project.client_id, 'message_id': source.pk,
                    'sha256': hashlib.sha256(source.content.encode()).hexdigest()}
        return {'original_reviewer': project.client.get_full_name() or project.client.email,
                'reviewed_at': source.occurred_at, 'source_message': source, 'source_snapshot': snapshot}
    required = ('original_reviewer', 'occurred_at', 'evidence_channel', 'external_reference')
    if any(not values.get(field) for field in required) or not documents:
        fail('Indica autor, fecha y fuente de la aprobación, y adjunta la evidencia del cliente.', 'client_evidence_required')
    if values['occurred_at'] > timezone.now():
        fail('La fecha de aprobación no puede estar en el futuro.')
    return {'original_reviewer': values['original_reviewer'], 'reviewed_at': values['occurred_at'],
            'source_message': None, 'source_snapshot': {
                'channel': values['evidence_channel'], 'direction': 'incoming',
                'external_reference': values['external_reference'], 'client_statement': values['evidence_message'],
                'documents': [{'id': doc.pk, 'title': doc.title, 'content_sha256': hashlib.sha256(
                    json.dumps({'markdown': doc.content_markdown, 'json': doc.content_json}, sort_keys=True).encode(),
                ).hexdigest()} for doc in documents],
            }}


def import_schema():
    """The exact structural JSON contract used by authoring and MCP discovery."""
    guide = {'type': 'object', 'additionalProperties': False, 'properties': {
        field: ({'type': 'array', 'items': {'type': 'string'}, 'maxItems': 100} if field in ('steps', 'blocked_steps') else {'type': 'string'})
        for field in GuideSerializer().fields
    }}
    schemas = {}
    for kind in ('requirements', 'stages', 'phases', 'scopes'):
        properties = {}
        for field in sorted(IMPORT_FIELDS[kind]):
            if field == IMPORT_CHILDREN.get(kind):
                properties[field] = {'type': 'array', 'items': schemas[field], 'maxItems': 100}
            elif field == 'guide':
                properties[field] = guide
            elif field == 'is_current':
                properties[field] = {'type': 'boolean'}
            elif field.endswith('_id'):
                properties[field] = {'type': ['integer', 'null'] if field != 'contract_id' else 'integer', 'minimum': 1}
            elif field == 'order':
                properties[field] = {'type': 'integer', 'minimum': 0}
            else:
                properties[field] = {'type': 'string', **({'pattern': '^[-a-zA-Z0-9_]+$', 'maxLength': 100} if field == 'key' else {})}
        schemas[kind] = {'type': 'object', 'additionalProperties': False,
                         'required': ['key', 'title'] + (['contract_id'] if kind == 'scopes' else []),
                         'properties': properties}
    return {'type': 'object', 'additionalProperties': False, 'required': ['schema_version', 'scopes'],
            'properties': {'schema_version': {'const': 1}, 'scopes': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': schemas['scopes']}}}
