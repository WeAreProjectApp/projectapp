"""Explicit, atomic project binding; acceptance alone never provisions resources."""
import hashlib
import json
import io
import zipfile
from copy import copy
from pathlib import Path
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Deliverable, Project, ProjectPhase, UserProfile
from accounts.services.proposal_client_service import build_client_display_name, get_or_create_client_for_proposal, sync_snapshot
from content.models import BusinessProposal, ProposalApprovalFile, ProposalChangeLog, ProposalDocument
from content.serializers.panel_projects import CreatePanelProjectSerializer
from content.serializers.proposal_approval import ProposalApprovalSerializer
from content.services import contract_variants

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_PACKAGE_BYTES = 36 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg'}


class ApprovalConflict(ValidationError):
    status_code = 409


def load_proposal(pk):
    return BusinessProposal.objects.select_related('client__user', 'deliverable__project__client__profile', 'deliverable__retention_context__client__profile').prefetch_related('sections', 'proposal_documents', 'approval_files').get(pk=pk)


def retained_link_conflict(proposal):
    """Its deliverable outlived a forced project deletion: review cannot bind it."""
    name = (proposal.linked_project or {}).get('name') or 'sin nombre'
    return ApprovalConflict({
        'detail': f'El entregable de esta propuesta quedó conservado del proyecto eliminado «{name}». '
                  'La revisión no puede vincularlo: trasládala con la reasignación de proyecto a un '
                  'proyecto vigente del mismo cliente.',
        'code': 'retained_project',
    })


def source_hash(proposal):
    fields = ('status', 'language', 'nationality', 'title', 'client_id', 'client_name', 'client_email', 'currency', 'total_investment', 'selected_modules', 'contract_modality', 'contract_params', 'hosting_percent', 'hosting_discount_nine_month', 'hosting_discount_semiannual', 'hosting_discount_quarterly')
    documents = []
    for doc in proposal.proposal_documents.all():
        digest = ''
        try:
            with doc.file.open('rb') as stream:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: stream.read(64 * 1024), b''):
                    hasher.update(chunk)
                digest = hasher.hexdigest()
        except (OSError, ValueError):
            digest = 'unavailable'
        documents.append([doc.pk, doc.document_type, doc.title, doc.file.name, digest])
    profile = proposal.client
    canonical_client = None if profile is None else {'id': profile.pk, 'user_id': profile.user_id, 'name': build_client_display_name(profile), 'email': profile.user.email, 'company': profile.company_name, 'phone': profile.phone, 'nit': profile.nit, 'billing_code': profile.billing_code, 'archived_at': profile.archived_at}
    from content.services.hour_package_service import seed_commercial_conditions_from_catalog
    sections = list(proposal.sections.values('id', 'section_type', 'title', 'content_json', 'is_enabled', 'order'))
    resolved_commercial_conditions = [
        seed_commercial_conditions_from_catalog(section['content_json'] or {}, nationality=proposal.nationality, language='en' if proposal.language == 'en' else 'es')
        for section in sections
        if section['is_enabled'] and section['section_type'] == 'commercial_conditions'
        and (section['content_json'] or {}).get('hourPackagesMode') != 'manual'
    ]
    value = {'proposal': {key: getattr(proposal, key) for key in fields}, 'canonical_client': canonical_client, 'confirmed_selection': proposal.has_confirmed_module_selection, 'sections': sections, 'resolved_commercial_conditions': resolved_commercial_conditions, 'documents': documents}
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def file_summary(row, *, platform=False):
    return {'id': row.pk, 'title': row.title, 'document_type': row.document_type, 'filename': row.filename, 'size': row.size, 'sha256': row.sha256, 'download_url': f'/api/accounts/projects/{row.project_id}/approval-files/{row.pk}/' if platform else f'/api/proposals/{row.proposal_id}/approval/files/{row.pk}/'}



def _client_summary(profile):
    if profile is None:
        return None
    return {'profile_id': profile.pk, 'name': build_client_display_name(profile), 'email': profile.user.email, 'phone': profile.phone, 'company': profile.company_name, 'nit': profile.nit, 'billing_code': profile.billing_code}


def _commercial_summary(proposal):
    from accounts.views import _extract_proposal_financial_data
    payments, hosting = _extract_proposal_financial_data(proposal)
    return {'title': proposal.title, 'total_investment': str(proposal.total_investment), 'currency': proposal.currency, 'payment_milestones': payments, 'hosting_tiers': hosting, 'scope': _scope(proposal)}


def preview(proposal):
    manifest = proposal.platform_approval_manifest
    client = manifest['client'] if 'client' in manifest else _client_summary(proposal.client)
    commercial_summary = manifest['commercial_summary'] if 'commercial_summary' in manifest else _commercial_summary(proposal)
    docs = []
    for variant in contract_variants.active_variants(proposal):
        row = contract_variants.contract_document(proposal, variant)
        if row:
            docs.append({'id': row.pk, 'title': row.title, 'document_type': row.document_type})
    error = None
    try:
        _original_contracts(proposal)
    except ValidationError as exc:
        error = str(exc.detail['use_proposal_contracts'])
        if isinstance(exc.detail['use_proposal_contracts'], list):
            error = ' '.join(str(message) for message in exc.detail['use_proposal_contracts'])
    linked = proposal.linked_project
    summary = {'id': proposal.pk, 'status': proposal.status, 'platform_onboarding_status': proposal.platform_onboarding_status, 'platform_onboarding_completed_at': proposal.platform_onboarding_completed_at.isoformat() if proposal.platform_onboarding_completed_at else None, 'available_transitions': proposal.available_transitions, 'project_review_required': proposal.project_review_required, 'linked_project': linked}
    return {'source_hash': source_hash(proposal), 'client': client, 'linked_project': linked, 'project_reassignment_required': bool(linked) and linked['id'] is None, 'commercial_summary': commercial_summary, 'contracts': {'modality': contract_variants.modality(proposal), 'available': error is None, 'documents': docs, 'error': error}, 'optional_documents': [{'id': row.pk, 'title': row.title, 'document_type': row.document_type} for row in proposal.proposal_documents.all() if row.document_type not in ProposalDocument.CONTRACT_DOC_TYPES], 'confirmed': bool(proposal.platform_approval_manifest), 'confirmed_files': [file_summary(row) for row in proposal.approval_files.all()], 'proposal': summary}


def _original_contracts(proposal):
    from content.services.proposal_formalization_service import contract_attachments
    from content.services.formalization_content import FormalizationError
    try:
        return contract_attachments(proposal, [contract_variants.VARIANTS[v].doc_type for v in contract_variants.active_variants(proposal)])
    except FormalizationError as exc:
        raise ValidationError({'use_proposal_contracts': str(exc)}) from exc


def _read_file(file):
    if not file:
        raise ValidationError({'files': 'Uno de los archivos no está disponible.'})
    try:
        file.open('rb')
        file.seek(0)
        content = file.read(MAX_FILE_BYTES + 1)
        file.seek(0)
    except (OSError, ValueError) as exc:
        raise ValidationError({'files': 'No se pudo leer uno de los archivos.'}) from exc
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValidationError({'files': 'Cada archivo debe contener datos y pesar como máximo 15 MB.'})
    return content


def _scope(proposal):
    from accounts.services.technical_resources_sync import filtered_technical_doc_for_sync
    section = proposal.sections.filter(section_type='technical_document', is_enabled=True).first()
    content = filtered_technical_doc_for_sync(proposal, section.content_json) if section else {}
    return [epic.get('title') or epic.get('epicKey') for epic in content.get('epics', []) if isinstance(epic, dict) and (epic.get('title') or epic.get('epicKey'))]


def _packet(proposal, data, files, *, profile):
    result = []
    if data['use_proposal_contracts']:
        if files or data['custom_documents']:
            raise ValidationError({'custom_files': 'Desactiva los contratos de la propuesta para adjuntar documentos personalizados.'})
        for key, doc in _original_contracts(proposal):
            result.append((key, doc.title, doc.document_type, Path(doc.file.name).name, _read_file(doc.file)))
    else:
        if not files or len(files) != len(data['custom_documents']):
            raise ValidationError({'custom_files': 'Adjunta al menos un documento e indica el título y tipo de cada archivo.'})
        for index, (file, meta) in enumerate(zip(files, data['custom_documents'])):
            filename = Path(file.name).name
            if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise ValidationError({'custom_files': 'Formato no permitido. Usa PDF, Word, Excel o imágenes.'})
            content = _read_file(file)
            suffix = Path(filename).suffix.lower()
            signatures = {'.pdf': b'%PDF-', '.docx': b'PK', '.xlsx': b'PK', '.xls': b'\xd0\xcf\x11\xe0', '.png': b'\x89PNG', '.jpg': b'\xff\xd8', '.jpeg': b'\xff\xd8', '.doc': b'\xd0\xcf\x11\xe0'}
            if not content.startswith(signatures[suffix]):
                raise ValidationError({'custom_files': 'El contenido del archivo no corresponde a su formato.'})
            if suffix in ('.docx', '.xlsx'):
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as archive:
                        names = set(archive.namelist())
                    required = {'[Content_Types].xml', 'word/document.xml' if suffix == '.docx' else 'xl/workbook.xml'}
                    if not required <= names:
                        raise ValueError('invalid Office file')
                except (ValueError, zipfile.BadZipFile) as exc:
                    raise ValidationError({'custom_files': 'El documento Office no es válido.'}) from exc
            result.append((f'custom-{index}', meta['title'], meta['document_type'], filename, content))
    selected = data['selected_document_ids']
    documents = {row.pk: row for row in proposal.proposal_documents.filter(pk__in=selected)}
    if set(selected) != set(documents) or any(row.document_type in ProposalDocument.CONTRACT_DOC_TYPES for row in documents.values()):
        raise ValidationError({'selected_document_ids': 'Selecciona únicamente anexos de esta propuesta; los contratos usan el switch principal.'})
    for pk in dict.fromkeys(selected):
        row = documents[pk]
        result.append((f'original-{pk}', row.title, row.document_type, Path(row.file.name).name, _read_file(row.file)))
    # Preserve stored contracts; only new commercial/technical copies use the
    # client explicitly validated by the operator. No source model is saved here.
    detail_source = copy(proposal)
    detail_source.client = profile
    detail_source.client_name = build_client_display_name(profile)
    detail_source.client_phone = profile.phone or ''
    if profile.user.email and not profile.is_email_placeholder:
        detail_source.client_email = profile.user.email
    from content.services.proposal_formalization_service import document_bytes
    from content.services.formalization_content import FormalizationError, FormalContent
    detail_content = FormalContent(detail_source)
    for section in detail_content.sections:
        if section.section_type == 'greeting':
            section.content_json['clientName'] = detail_source.client_name
    for key, title in [('commercial', 'Detalle comercial'), ('technical', 'Detalle técnico')]:
        try:
            content = document_bytes(detail_source, key, content=detail_content)
        except FormalizationError as exc:
            raise ValidationError({'documents': str(exc)}) from exc
        if not content:
            raise ValidationError({'documents': f'No se pudo generar el {title.lower()}. Revisa la propuesta.'})
        result.append((key, title, key, key + '.pdf', content))
    if sum(len(item[4]) for item in result) > MAX_PACKAGE_BYTES:
        raise ValidationError({'files': 'El paquete supera el máximo de 36 MB.'})
    return result


def _sync(proposal, actor):
    from accounts.services.technical_resources_sync import _sync_technical_resources_core
    project = proposal.deliverable.project
    if project is None:
        raise retained_link_conflict(proposal)
    manifest = proposal.platform_approval_manifest
    if manifest:
        result = _sync_technical_resources_core(project, proposal, actor, preserve_existing=True, content_json_override=manifest.get('technical_content', {}), content_is_filtered=True)
        if not result.get('ok'):
            raise ValidationError({'technical': result.get('detail', 'No se pudo sincronizar el detalle técnico.')})
    proposal.platform_onboarding_status = BusinessProposal.ONBOARDING_COMPLETED
    proposal.platform_onboarding_completed_at = proposal.platform_onboarding_completed_at or timezone.now()
    proposal.save(update_fields=['platform_onboarding_status', 'platform_onboarding_completed_at'])


def review_proposal(proposal_id, payload, *, actor, files=()):
    serializer = ProposalApprovalSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    written = []
    try:
        with transaction.atomic():
            original = load_proposal(proposal_id)
            if original.deliverable_id and original.deliverable.project_id is None and data['action'] != 'defer':
                raise retained_link_conflict(original)
            project_id = original.deliverable.project_id if original.deliverable_id else data.get('project_id')
            project = Project.objects.select_for_update().filter(pk=project_id).first() if project_id else None
            proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
            if proposal.deliverable_id:
                current_deliverable = Deliverable.objects.select_for_update().get(pk=proposal.deliverable_id)
                if current_deliverable.project_id != project_id:
                    raise ApprovalConflict({'detail': 'El proyecto cambió. Actualiza y vuelve a revisar.', 'code': 'link_changed'})
            if original.deliverable_id != proposal.deliverable_id:
                raise ApprovalConflict({'detail': 'La vinculación cambió. Actualiza y vuelve a revisar.', 'code': 'link_changed'})
            action = data['action']
            if action == 'defer':
                if files:
                    raise ValidationError({'custom_files': 'Posponer no guarda adjuntos.'})
                if data['accept_proposal'] and proposal.status != BusinessProposal.Status.ACCEPTED:
                    from content.services.proposal_status_service import change_status
                    change_status(proposal, BusinessProposal.Status.ACCEPTED, source='approval_review', acting_user_id=actor.pk)
                result = preview(load_proposal(proposal_id))
                return dict(result, action=action, idempotent=False)
            manifest = proposal.platform_approval_manifest
            if action == 'retry':
                mutable = {'client_profile_id', 'new_client', 'project_id', 'new_project', 'custom_documents', 'selected_document_ids', 'use_proposal_contracts', 'accept_proposal'}
                if files or any(key in payload for key in mutable):
                    raise ApprovalConflict({'detail': 'El reintento conserva el vínculo y los archivos confirmados.', 'code': 'immutable_approval'})
                if not proposal.deliverable_id or not manifest:
                    raise ApprovalConflict({'detail': 'Confirma primero la revisión del cliente, proyecto y documentos.', 'code': 'review_required'})
                _sync(proposal, actor)
                return dict(preview(load_proposal(proposal_id)), action=action, idempotent=True)
            fingerprint_payload = {key: value for key, value in data.items() if key not in ('source_hash', 'request_id', 'action')}
            upload_hashes = [{'sha256': hashlib.sha256(_read_file(file)).hexdigest(), 'filename': Path(file.name).name, 'size': file.size} for file in files]
            fingerprint = hashlib.sha256(json.dumps([fingerprint_payload, upload_hashes], sort_keys=True, default=str).encode()).hexdigest()
            if manifest:
                if manifest.get('request_id') == data['request_id'] and manifest.get('payload_hash') == fingerprint:
                    return dict(preview(load_proposal(proposal_id)), action=action, idempotent=True)
                raise ApprovalConflict({'detail': 'La revisión ya fue confirmada. Conserva el vínculo y usa Reintentar si es necesario.', 'code': 'immutable_approval'})
            if data['source_hash'] != source_hash(load_proposal(proposal_id)):
                raise ApprovalConflict({'detail': 'La propuesta o sus documentos cambiaron. Actualiza y revisa nuevamente.', 'code': 'stale_source'})
            if not data['accept_proposal'] and proposal.status not in (BusinessProposal.Status.ACCEPTED, BusinessProposal.Status.NEGOTIATING):
                raise ValidationError({'status': 'La propuesta debe estar aceptada o en negociación.'})
            if project_id and project is None:
                raise ValidationError({'project_id': 'Ese proyecto no existe.'})
            if proposal.deliverable_id and (project is None or data.get('project_id') != project.pk):
                raise ApprovalConflict({'detail': 'La propuesta ya tiene proyecto. No se puede reemplazar el vínculo.', 'code': 'immutable_link'})
            if data.get('client_profile_id'):
                profile = UserProfile.objects.clients().select_related('user').filter(pk=data['client_profile_id'], archived_at__isnull=True).first()
                if profile is None:
                    raise ValidationError({'client_profile_id': 'Selecciona un cliente existente no archivado.'})
            else:
                values = data['new_client']
                # Reusing an existing email must never silently edit its identity.
                from django.contrib.auth import get_user_model
                existing = get_user_model().objects.filter(Q(email__iexact=values['email']) | Q(username__iexact=values['email'])).exists() if values['email'] else False
                if existing:
                    raise ValidationError({'new_client': 'Ese correo ya existe. Selecciona el cliente existente.'})
                profile = get_or_create_client_for_proposal(**values)
            if project and project.client_id != profile.user_id:
                raise ValidationError({'project_id': 'El proyecto debe pertenecer al cliente seleccionado.'})
            if proposal.deliverable_id and proposal.client_id and proposal.client_id != profile.pk:
                raise ApprovalConflict({'detail': 'El proyecto vinculado conserva su cliente.', 'code': 'immutable_link'})
            # Lock package sources before generating and capturing their bytes.
            list(proposal.sections.select_for_update().values_list('pk', flat=True))
            list(proposal.proposal_documents.select_for_update().values_list('pk', flat=True))
            packet = _packet(proposal, data, files, profile=profile)
            if data['source_hash'] != source_hash(load_proposal(proposal_id)):
                raise ApprovalConflict({'detail': 'Los datos cambiaron durante la revisión.', 'code': 'stale_source'})
            if not project:
                project_serializer = CreatePanelProjectSerializer(data=dict(data['new_project'], client_profile_id=profile.pk), context={'request': SimpleNamespace(user=actor)})
                project_serializer.is_valid(raise_exception=True)
                project = project_serializer.save()
                from accounts.views import _extract_proposal_financial_data
                project.payment_milestones, project.hosting_tiers = _extract_proposal_financial_data(proposal)
                project.save(update_fields=['payment_milestones', 'hosting_tiers'])
            if not proposal.deliverable_id:
                proposal.deliverable = Deliverable.objects.create(project=project, category=Deliverable.CATEGORY_DOCUMENTS, title=proposal.title[:300], uploaded_by=actor)
            elif proposal.deliverable.is_archived:
                raise ApprovalConflict({'detail': 'El entregable vinculado está archivado.', 'code': 'archived_deliverable'})
            proposal.client = profile
            sync_snapshot(proposal)
            if data['accept_proposal'] and proposal.status != BusinessProposal.Status.ACCEPTED:
                from content.services.proposal_status_service import change_status
                change_status(proposal, BusinessProposal.Status.ACCEPTED, source='approval_review', acting_user_id=actor.pk)
            technical = proposal.sections.filter(section_type='technical_document', is_enabled=True).first()
            from accounts.services.technical_resources_sync import filtered_technical_doc_for_sync
            frozen_technical = filtered_technical_doc_for_sync(proposal, technical.content_json) if technical else {}
            proposal.platform_approval_manifest = {'request_id': data['request_id'], 'payload_hash': fingerprint, 'source_hash': data['source_hash'], 'client_profile_id': profile.pk, 'project_id': project.pk, 'use_proposal_contracts': data['use_proposal_contracts'], 'confirmed_at': timezone.now().isoformat(), 'confirmed_by': actor.pk, 'technical_content': frozen_technical, 'client': _client_summary(profile), 'commercial_summary': _commercial_summary(proposal)}
            proposal.platform_onboarding_status = BusinessProposal.ONBOARDING_PENDING
            proposal.save(update_fields=['client', 'deliverable', 'platform_approval_manifest', 'platform_onboarding_status'])
            for key, title, doc_type, filename, content in packet:
                row = ProposalApprovalFile(proposal=proposal, project=project, deliverable=proposal.deliverable, source_key=key, title=title, document_type=doc_type, filename=filename[:255], sha256=hashlib.sha256(content).hexdigest(), size=len(content), created_by=actor)
                row.file.save(filename[:255], ContentFile(content), save=False)
                written.append((row.file.storage, row.file.name))
                row.save()
            proposal.platform_approval_manifest['files'] = list(proposal.approval_files.values('id', 'source_key', 'sha256', 'size'))
            proposal.save(update_fields=['platform_approval_manifest'])
            _sync(proposal, actor)
            from accounts.services.proposal_platform_onboarding import _ensure_project_stages
            _ensure_project_stages(proposal)
            ProposalChangeLog.objects.create(proposal=proposal, change_type=ProposalChangeLog.ChangeType.PLATFORM_LAUNCH, actor_type='seller', description=f'Revisión confirmada: cliente {profile.pk}, proyecto {project.pk}; paquete privado conservado.')
            result = dict(preview(load_proposal(proposal_id)), action=action, idempotent=False)
        return result
    except Exception:
        for storage, name in written:
            storage.delete(name)
        raise
